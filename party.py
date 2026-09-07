#!/usr/bin/env python3
"""Freak Town Party Mode — a party-game OS extension, not a separate game.

Topology (Jackbox/Netflix-converged, no new backend):
  BIG SCREEN (/party/<code>/stage) + PHONES (/party/<code>/play) + ONE SERVER.
  Transport: SSE stream (room -> clients) + POST inputs (clients -> room).
  No Socket.IO/Redis/Durable Objects. Flask only, like the rest of the repo.

Invariants (kept from the live-show side):
  CONTROLLER -> SERVER COMMAND -> ROOM -> PERSIST -> BROADCAST -> STAGE.
  Controllers never mutate stage state directly.
  Room codes are NOT auth. Every player holds an opaque seat token.
  The server knows everything; each role only receives its own view.
  Secrets are ONLY served from /view (never on the shared SSE stream).

A Party Pack is just a playlist: {"pack": ..., "modes": [...]}.
A mode is data + 4 functions: create / input / views / advance.
"""

import io
import json
import re
import secrets
import threading
import time
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

party_bp = Blueprint("party", __name__)

BASE = Path(__file__).parent
PARTY_LOG = BASE / "party_events.jsonl"
RECORDS_FILE = BASE / "party_records.json"
ROOMS_FILE = BASE / "party_rooms.json"

# High-frequency events skip disk snapshots (replay buffer keeps them in RAM).
NO_SNAPSHOT = {"draw.batch", "guess", "laugh", "line.accepted", "vote.accepted"}

LOCK = threading.Lock()
ROOMS: dict = {}

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no ambiguous chars
MAX_PLAYERS = 8
MAX_NAME = 24
MAX_TEXT = 180
DRAW_MIN_INTERVAL = 0.05  # 50-100ms batching, per CF WS guidance

WORDS = ["air fryer", "traffic cone", "divorce court", "pigeon", "Tesco",
         "haunted Roomba", "LinkedIn", "cryptocurrency", "dentist", "karaoke"]


# ── helpers ───────────────────────────────────────────────────────────

def _now() -> float:
    return time.time()


def _log(room_code: str, kind: str, payload: dict):
    try:
        with open(PARTY_LOG, "a") as f:
            f.write(json.dumps({"t": _now(), "room": room_code,
                                "kind": kind, **payload}) + "\n")
    except Exception:
        pass


def _new_code() -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if code not in ROOMS:
            return code


def _clean(s: str, limit: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:limit]


def _broadcast(room: dict, kind: str, public: dict) -> dict:
    """Persist-then-queue. The ONLY way stage-visible state changes."""
    room["seq"] += 1
    ev = {"seq": room["seq"], "kind": kind, "t": _now(), **public}
    room["events"].append(ev)
    room["events"] = room["events"][-500:]  # bounded replay buffer
    _log(room["code"], kind, public)
    if kind not in NO_SNAPSHOT:
        _save_rooms()
    return ev


def _get_room(code: str) -> dict | None:
    return ROOMS.get((code or "").upper())


def _player_by_token(room: dict, token: str) -> dict | None:
    if not token:
        return None
    for p in room["players"].values():
        if p["token"] == token:
            return p
    return None


def _is_host(room: dict, token: str) -> bool:
    return bool(token) and token == room["host_token"]


def _check_timer(room: dict):
    """Lazy timer enforcement: phases advance on next touch after deadline."""
    st = room["mode_state"]
    if room["phase"] == "playing" and st.get("deadline_at"):
        if _now() > st["deadline_at"]:
            MODES[room["mode"]]["advance"](room, reason="timeout")


def _public_players(room: dict) -> list:
    return [{"id": pid, "name": p["name"], "freak": p["freak"],
             "ready": p["ready"], "score": p["score"]}
            for pid, p in room["players"].items()]


# ── persistent freak memory ──────────────────────────────────────────
# A player is name + answer. A Freak is avatar + voice + history + rivals.
# party_records.json keeps cross-night party wins per freak; freaks/ bundles
# supply sets/replies lore. Both feed the "lore" event at game start so
# Ella and the room can callback earlier nights.

def _freak_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:32]


def _load_records() -> dict:
    try:
        return json.loads(RECORDS_FILE.read_text())
    except Exception:
        return {}


def _save_records(rec: dict):
    try:
        RECORDS_FILE.write_text(json.dumps(rec, indent=1))
    except Exception:
        pass


def _bundle_meta(slug_dir) -> dict | None:
    try:
        return json.loads((slug_dir / "meta.json").read_text())
    except Exception:
        return None


def _freak_lore(freak_name: str) -> dict:
    """Sets/replies/party-wins for one freak. Pure read, safe to call often."""
    slug = _freak_slug(freak_name)
    sets, replies_in = 0, 0
    try:
        fdir = BASE / "freaks"
        mine = set()
        for d in fdir.iterdir():
            if not d.is_dir():
                continue
            m = _bundle_meta(d)
            if not m:
                continue
            if _freak_slug((m.get("character", {}) or {}).get("name", "")) == slug:
                sets += 1
                mine.add(d.name)
        for d in fdir.iterdir():
            if not d.is_dir() or d.name in mine:
                continue
            m = _bundle_meta(d) or {}
            lin = m.get("lineage") or {}
            if lin.get("parent") in mine:
                replies_in += 1
            elif d.name in mine:
                pass
        # replies authored BY this freak = bundles whose parent is someone else's
        replies_out = 0
        for s in mine:
            m = _bundle_meta(fdir / s) or {}
            if (m.get("lineage") or {}).get("parent"):
                replies_out += 1
    except Exception:
        replies_out = 0
    rec = _load_records().get(slug, {})
    return {"freak": freak_name, "sets": sets,
            "replies": replies_in + replies_out,
            "party_wins": rec.get("wins", 0), "party_games": rec.get("games", 0)}


def _room_lore(room: dict) -> list:
    """One line per freak + head-to-head party records between seats."""
    lines = []
    rec = _load_records()
    names = [(pid, p["freak"]) for pid, p in room["players"].items()]
    for _, freak in names:
        lo = _freak_lore(freak)
        bits = []
        if lo["sets"]:
            bits.append(f"{lo['sets']} set{'s' if lo['sets'] != 1 else ''}")
        if lo["replies"]:
            bits.append(f"{lo['replies']} repl{'ies' if lo['replies'] != 1 else 'y'}")
        if lo["party_wins"]:
            bits.append(f"{lo['party_wins']} party win{'s' if lo['party_wins'] != 1 else ''}")
        lines.append(f"{freak}: " + (", ".join(bits) if bits else "rookie night"))
    slugs = {_freak_slug(f) for _, f in names}
    seen = set()
    for _, f in names:
        fs = _freak_slug(f)
        for other, r in (rec.get(fs, {}).get("vs", {}) or {}).items():
            if other in slugs and other != fs and (other, fs) not in seen:
                w, l = r.get("w", 0), r.get("l", 0)
                if w or l:
                    lines.append(f"rivalry: {f} leads {other} {w}-{l}"
                                 if w >= l else
                                 f"rivalry: {other} leads {f} {l}-{w}")
                seen.add((fs, other))
    return lines


def _record_win(room: dict, winner_pid: str):
    """Cross-night memory: winner's freak banks a win + h2h vs every seat."""
    try:
        rec = _load_records()
        wslug = _freak_slug(room["players"][winner_pid]["freak"])
        w = rec.setdefault(wslug, {"wins": 0, "games": 0, "vs": {}})
        w["wins"] += 1
        for pid, p in room["players"].items():
            if pid == winner_pid:
                continue
            o = _freak_slug(p["freak"])
            if o == wslug:
                continue
            vs = w.setdefault("vs", {}).setdefault(o, {"w": 0, "l": 0})
            vs["w"] += 1
            lo = rec.setdefault(o, {"wins": 0, "games": 0, "vs": {}})
            lv = lo.setdefault("vs", {}).setdefault(wslug, {"w": 0, "l": 0})
            lv["l"] += 1
        _save_records(rec)
    except Exception:
        pass


def _record_game(room: dict):
    try:
        rec = _load_records()
        for p in room["players"].values():
            r = rec.setdefault(_freak_slug(p["freak"]),
                               {"wins": 0, "games": 0, "vs": {}})
            r["games"] += 1
        _save_records(rec)
    except Exception:
        pass


# ── room snapshots (survive restart) ─────────────────────────────────

def _save_rooms():
    try:
        snap = {}
        for code, room in ROOMS.items():
            snap[code] = {
                "code": room["code"], "host_token": room["host_token"],
                "phase": room["phase"], "mode": room["mode"],
                "mode_state": room["mode_state"], "players": room["players"],
                "seq": room["seq"], "events": room["events"][-100:],
                "locked": room["locked"],
                "seen_seq": {k: sorted(v) for k, v in
                             room.get("seen_seq", {}).items()},
                "created_at": room["created_at"]}
        ROOMS_FILE.write_text(json.dumps(snap))
    except Exception:
        pass


def _load_rooms():
    try:
        snap = json.loads(ROOMS_FILE.read_text())
    except Exception:
        return
    for code, r in snap.items():
        try:
            r["seen_seq"] = {k: set(v) for k, v in
                             r.get("seen_seq", {}).items()}
            r.setdefault("events", [])
            ROOMS[code] = r
        except Exception:
            continue


_load_rooms()


# ── modes ─────────────────────────────────────────────────────────────
# Mode = create(room) / on_input(room, player, data) / advance(room).
# Views are derived per-role so secrets never leak to the shared stream.

def _mq_create(room: dict):
    order = list(room["players"].keys())
    room["mode_state"] = {
        "round": 0, "drawer_idx": -1, "drawer": None, "word": None,
        "guesses": [], "winner": None, "phase": "idle", "deadline_at": None,
        "strokes": [], "revealed": False,
    }


def _mq_start_round(room: dict):
    import random as _r
    st = room["mode_state"]
    order = list(room["players"].keys())
    if not order:
        return
    st["round"] += 1
    st["drawer_idx"] = (st["drawer_idx"] + 1) % len(order)
    st["drawer"] = order[st["drawer_idx"]]
    st["word"] = _r.choice(WORDS)
    st["guesses"] = []
    st["winner"] = None
    st["phase"] = "drawing"
    st["revealed"] = False
    st["strokes"] = []
    st["deadline_at"] = _now() + 90
    _broadcast(room, "round.started", {
        "mode": "freaktionary", "round": st["round"],
        "drawer": room["players"][st["drawer"]]["name"],
        "deadline_at": st["deadline_at"]})


def _mq_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    kind = data.get("kind")
    if st["phase"] != "drawing" or st.get("revealed"):
        return {"ok": False, "error": "not accepting input now"}
    if kind == "draw.batch":
        if player["id"] != st["drawer"]:
            return {"ok": False, "error": "only the drawer draws"}
        if _now() - player.get("last_draw", 0) < DRAW_MIN_INTERVAL:
            return {"ok": False, "error": "slow down"}
        pts = data.get("points") or []
        if not isinstance(pts, list) or len(pts) > 200:
            return {"ok": False, "error": "bad batch"}
        clean = []
        for pt in pts[:200]:
            try:
                x, y = float(pt[0]), float(pt[1])
                if 0 <= x <= 1 and 0 <= y <= 1:
                    clean.append([round(x, 4), round(y, 4)])
            except Exception:
                continue
        player["last_draw"] = _now()
        st["strokes"].append({"by": player["id"], "points": clean})
        _broadcast(room, "draw.batch", {"round": st["round"],
                                        "points": clean})
        return {"ok": True}
    if kind == "guess":
        if player["id"] == st["drawer"]:
            return {"ok": False, "error": "drawer cannot guess"}
        guess = _clean(data.get("text", ""), 60).lower()
        if not guess:
            return {"ok": False, "error": "empty guess"}
        if guess == st["word"].lower():
            st["winner"] = player["id"]
            st["revealed"] = True
            player["score"] += 2
            room["players"][st["drawer"]]["score"] += 1
            _record_win(room, player["id"])
            _broadcast(room, "round.won", {
                "round": st["round"], "winner": player["name"],
                "word": st["word"], "scores": _public_players(room)})
            return {"ok": True, "correct": True}
        st["guesses"].append({"by": player["name"], "text": guess})
        _broadcast(room, "guess", {"round": st["round"], "by": player["name"]})
        return {"ok": True, "correct": False}
    return {"ok": False, "error": "unknown input"}


def _mq_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "drawing" and not st.get("revealed"):
        st["revealed"] = True  # timeout with no winner: reveal, no points
        _broadcast(room, "round.revealed", {"round": st["round"],
                                            "word": st["word"],
                                            "reason": reason or "timeout"})
    _mq_start_round(room)


def _rr_create(room: dict):
    room["mode_state"] = {
        "target": None, "lines": {}, "order": [], "votes": {},
        "phase": "collecting", "deadline_at": None, "revealed": False,
        "audio": None, "audio_status": "none",
    }


def _rr_start_round(room: dict, target: str = ""):
    st = room["mode_state"]
    st["target"] = _clean(target, 60) or "the host's air fryer obsession"
    st["lines"] = {}
    st["votes"] = {}
    st["phase"] = "collecting"
    st["revealed"] = False
    st["audio"] = None
    st["audio_status"] = "none"
    st["order"] = list(room["players"].keys())
    st["deadline_at"] = _now() + 90
    _broadcast(room, "collect.started", {"mode": "roast-relay",
                                         "target": st["target"],
                                         "deadline_at": st["deadline_at"]})


def _rr_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    kind = data.get("kind")
    if kind == "line":
        if st["phase"] != "collecting":
            return {"ok": False, "error": "not collecting now"}
        line = _clean(data.get("text", ""), MAX_TEXT)
        if not line:
            return {"ok": False, "error": "empty line"}
        st["lines"][player["id"]] = line  # one line each; resubmit overwrites
        _broadcast(room, "line.accepted", {"by": player["name"],
                                           "count": len(st["lines"]),
                                           "needed": len(room["players"])})
        if len(st["lines"]) >= len(room["players"]) and room["players"]:
            _rr_reveal(room)
        return {"ok": True}
    if kind == "vote":
        if st["phase"] != "voting":
            return {"ok": False, "error": "not voting now"}
        choice = data.get("choice")
        valid_ids = [str(i) for i in range(len(st["order"]))]
        if choice not in valid_ids:
            return {"ok": False, "error": "bad choice"}
        # no self-vote: the clip at index `choice` must not be yours
        if st["order"][int(choice)] == player["id"]:
            return {"ok": False, "error": "no self-votes"}
        st["votes"][player["id"]] = choice
        _broadcast(room, "vote.accepted", {"by": player["name"],
                                           "count": len(st["votes"])})
        if len(st["votes"]) >= len(room["players"]) and room["players"]:
            _rr_score(room)
        return {"ok": True}
    return {"ok": False, "error": "unknown input"}


def _rr_assembled(room: dict) -> list:
    st = room["mode_state"]
    clips = []
    for i, pid in enumerate(st["order"]):
        if pid in st["lines"]:
            clips.append({"i": i, "by": room["players"][pid]["name"],
                          "text": st["lines"][pid]})
    return clips


def _rr_reveal(room: dict):
    st = room["mode_state"]
    st["phase"] = "voting"
    st["deadline_at"] = _now() + 60
    clips = _rr_assembled(room)
    _broadcast(room, "set.revealed", {"mode": "roast-relay",
                                      "target": st["target"], "clips": clips,
                                      "deadline_at": st["deadline_at"]})
    # SHORT_GENERATION audio upgrade runs async; the room never waits for it.
    _rr_maybe_tts(room, clips)


def _rr_maybe_tts(room: dict, clips: list):
    """Best-effort TTS of the assembled set. Text reveal already happened;
    audio arrives later as generation.ready (or never — that's fine)."""
    st = room["mode_state"]
    try:
        import edge_tts  # noqa
    except Exception:
        return
    st["audio_status"] = "pending"
    _broadcast(room, "generation.pending", {"what": "roast-relay audio"})

    def _run():
        try:
            import asyncio as _a
            import hashlib as _h
            text = " ".join(c["text"] for c in clips)[:600]
            tag = _h.sha256(text.encode()).hexdigest()[:12]
            out = BASE / "audio_output" / f"party_{room['code']}_{tag}.mp3"
            _a.run(_a_send(text, str(out)))
            with LOCK:
                if room.get("mode") == "roast-relay":
                    room["mode_state"]["audio"] = f"/audio/{out.name}"
                    room["mode_state"]["audio_status"] = "ready"
                    _broadcast(room, "generation.ready",
                               {"what": "roast-relay audio",
                                "audio": f"/audio/{out.name}"})
        except Exception:
            with LOCK:
                room["mode_state"]["audio_status"] = "failed"

    threading.Thread(target=_run, daemon=True).start()


async def _a_send(text: str, path: str):
    import edge_tts
    await edge_tts.Communicate(text, "en-US-GuyNeural").save(path)


def _rr_score(room: dict):
    st = room["mode_state"]
    tally: dict = {}
    for voter, choice in st["votes"].items():
        tally[choice] = tally.get(choice, 0) + 1
    if tally:
        win = max(tally, key=tally.get)
        winner_pid = st["order"][int(win)]
        room["players"][winner_pid]["score"] += 3
        _record_win(room, winner_pid)
    st["phase"] = "scored"
    st["deadline_at"] = None
    _broadcast(room, "score.updated", {"tally": tally,
                                       "scores": _public_players(room)})


def _rr_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "collecting":
        if st["lines"]:
            _rr_reveal(room)
        else:
            _rr_start_round(room, st.get("target") or "")
    elif st["phase"] == "voting":
        _rr_score(room)
    else:
        _rr_start_round(room, st.get("target") or "")


MODES = {
    "freaktionary": {"title": "FREAKTIONARY", "min": 2, "max": 8,
                     "create": _mq_create, "input": _mq_input,
                     "advance": _mq_advance},
    "roast-relay": {"title": "ROAST RELAY", "min": 3, "max": 8,
                    "create": _rr_create, "input": _rr_input,
                    "advance": _rr_advance},
}

PACKS = {
    "FREAK NIGHT": ["freaktionary", "roast-relay", "freaktionary"],
    "QUICK FIRE": ["roast-relay"],
}


# ── views (per-role; secrets only here, never on the stream) ─────────

def _controller_view(room: dict, player: dict | None) -> dict:
    """playerView: what ONE phone displays. Server-driven screens."""
    base = {"room": room["code"], "phase": room["phase"],
            "seq": room["seq"], "players": _public_players(room),
            "locked": room["locked"]}
    if room["phase"] == "lobby":
        base["screen"] = "lobby"
        base["components"] = [
            {"type": "text", "text": "Waiting for host to lock + start."},
            {"type": "button", "id": "ready", "label": "I'M READY"}]
        if player:
            base["you"] = {"name": player["name"], "ready": player["ready"]}
        return base
    if player is None:  # audience controller: reactions only
        base["screen"] = "audience"
        base["components"] = [
            {"type": "button", "id": "laugh", "label": "😂"}]
        base.update(_stage_public(room))
        return base
    st = room["mode_state"]
    base.update(_stage_public(room))
    if room["mode"] == "freaktionary":
        if st["drawer"] == player["id"] and st["phase"] == "drawing":
            base["screen"] = "drawer"
            base["secret"] = st["word"]  # ONLY the drawer gets this
            base["components"] = [
                {"type": "canvas", "id": "draw"},
                {"type": "text", "text": f"Draw: {st['word']}"}]
        elif st["phase"] == "drawing":
            base["screen"] = "prompt"
            base["components"] = [
                {"type": "textarea", "id": "guess", "max_length": 60},
                {"type": "submit", "label": "GUESS"}]
        else:
            base["screen"] = "reveal"
            base["components"] = [
                {"type": "text",
                 "text": f"Word was: {st.get('word') or '?'} "
                         f"Winner: {st.get('winner') or 'nobody'}"}]
        return base
    if room["mode"] == "roast-relay":
        if st["phase"] == "collecting":
            base["screen"] = "prompt"
            base["components"] = [
                {"type": "text", "text": f"Target: {st['target']}"},
                {"type": "textarea", "id": "line", "max_length": MAX_TEXT},
                {"type": "submit", "label": "SEND IT"}]
        elif st["phase"] == "voting":
            clips = _rr_assembled(room)
            base["screen"] = "vote"
            # hide authorship until scored (deception-safe reveal)
            base["components"] = [
                {"type": "choice", "id": "winner",
                 "options": [{"id": str(c["i"]), "text": c["text"]}
                             for c in clips]}]
        else:
            base["screen"] = "scores"
            base["components"] = [
                {"type": "text", "text": "Scores below. Host advances."}]
        return base
    base["screen"] = "wait"
    base["components"] = [{"type": "text", "text": "Waiting…"}]
    return base


def _stage_public(room: dict) -> dict:
    """publicView: everything the big screen may show. No secrets."""
    out = {"mode": room["mode"], "room_phase": room["phase"],
           "scores": _public_players(room)}
    if room.get("lore"):
        out["lore"] = room["lore"]
    if room["phase"] == "lobby":
        out["lobby"] = {"code": room["code"], "count": len(room["players"])}
        return out
    st = room["mode_state"]
    if room["mode"] == "freaktionary":
        out["freaktionary"] = {
            "round": st["round"],
            "drawer": (room["players"][st["drawer"]]["name"]
                       if st.get("drawer") else None),
            "strokes": st["strokes"][-200:],
            "guesses": st["guesses"][-10:],
            "revealed": st.get("revealed"),
            "word": st["word"] if st.get("revealed") else None,
            "winner": (room["players"][st["winner"]]["name"]
                       if st.get("winner") else None),
            "deadline_at": st.get("deadline_at")}
    elif room["mode"] == "roast-relay":
        out["roast-relay"] = {
            "target": st["target"], "phase": st["phase"],
            "clips": _rr_assembled(room) if st["phase"] != "collecting" else [],
            "submitted": len(st["lines"]), "needed": len(room["players"]),
            "audio": st.get("audio"), "audio_status": st.get("audio_status"),
            "deadline_at": st.get("deadline_at")}
    return out


# ── routes ──────────────────────────────────────────────────────────

@party_bp.route("/play", methods=["GET"])
def play_home():
    return ("<!DOCTYPE html><html><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Freak Town Party</title></head><body style='background:#0a0a0f;"
            "color:#eee;font-family:monospace;text-align:center;padding:32px'>"
            "<div style='color:#ff2fa8;letter-spacing:2px'>FREAK TOWN PARTY</div>"
            "<h1>CREATE / JOIN</h1>"
            "<p><button onclick=\"fetch('/party/create',{method:'POST'})"
            ".then(r=>r.json()).then(d=>location='/party/'+d.code+'/stage')\""
            " style='font-size:18px;padding:12px 24px'>CREATE ROOM</button></p>"
            "<p style='color:#555'>or open freak.town/join/&lt;CODE&gt; on your phone</p>"
            "</body></html>")


@party_bp.route("/party/create", methods=["POST"])
def create_room():
    with LOCK:
        code = _new_code()
        host_token = secrets.token_urlsafe(16)
        ROOMS[code] = {"code": code, "host_token": host_token,
                       "phase": "lobby", "mode": None, "mode_state": {},
                       "players": {}, "seq": 0, "events": [],
                       "locked": False, "seen_seq": {},
                       "created_at": _now()}
        _broadcast(ROOMS[code], "room.created", {"code": code})
        return jsonify({"ok": True, "code": code, "host_token": host_token,
                        "stage": f"/party/{code}/stage",
                        "join": f"/join/{code}"})


@party_bp.route("/join/<code>", methods=["GET"])
def join_page(code):
    code = (code or "").upper()
    return JOIN_TEMPLATE.replace("__CODE__", code)


@party_bp.route("/party/<code>/join", methods=["POST"])
def join_room(code):
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = request.json or {}
    # idempotent rejoin: same seat token gets its player back (reconnect)
    tok = data.get("seat_token") or ""
    with LOCK:
        if tok:
            p = _player_by_token(room, tok)
            if p:
                p["connected"] = True
                return jsonify({"ok": True, "reconnected": True,
                                "seat_token": tok, "role": "player",
                                "name": p["name"]})
        name = _clean(data.get("name", ""), MAX_NAME) or "Anonymous"
        freak = _clean(data.get("freak", ""), MAX_NAME) or "Mystery Freak"
        if not room["locked"] and len(room["players"]) < MAX_PLAYERS:
            pid = f"p{len(room['players']) + 1}_{secrets.token_hex(3)}"
            token = secrets.token_urlsafe(16)
            room["players"][pid] = {"id": pid, "name": name, "freak": freak,
                                    "token": token, "ready": False,
                                    "score": 0, "connected": True,
                                    "last_draw": 0.0}
            _broadcast(room, "player.joined",
                       {"name": name, "count": len(room["players"])})
            return jsonify({"ok": True, "role": "player",
                            "seat_token": token, "name": name})
        _broadcast(room, "audience.joined", {"name": name})
        return jsonify({"ok": True, "role": "audience",
                        "seat_token": "", "name": name})


@party_bp.route("/party/<code>/qr.png", methods=["GET"])
def qr(code):
    import qrcode as _qr
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False}), 404
    url = request.host_url.rstrip("/") + f"/join/{room['code']}"
    img = _qr.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@party_bp.route("/party/<code>/host", methods=["POST"])
def host_cmd(code):
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = request.json or {}
    if not _is_host(room, data.get("host_token", "")):
        return jsonify({"ok": False, "error": "not host"}), 403
    cmd = data.get("cmd")
    with LOCK:
        _check_timer(room)
        if cmd == "lock":
            room["locked"] = True
            _broadcast(room, "roster.locked",
                       {"count": len(room["players"])})
            return jsonify({"ok": True, "locked": True})
        if cmd == "start":
            mode = data.get("mode", "freaktionary")
            if mode not in MODES:
                return jsonify({"ok": False, "error": "unknown mode"}), 400
            if len(room["players"]) < MODES[mode]["min"]:
                return jsonify({"ok": False, "error": "not enough players"}), 400
            room["mode"] = mode
            room["phase"] = "playing"
            MODES[mode]["create"](room)
            if mode == "freaktionary":
                _mq_start_round(room)
            else:
                _rr_start_round(room, data.get("target", ""))
            # persistent-freak memory: the room now knows who these
            # performers are, not just what they typed tonight.
            _record_game(room)
            room["lore"] = _room_lore(room)
            _broadcast(room, "lore", {"lines": room["lore"]})
            return jsonify({"ok": True, "mode": mode})
        if cmd == "advance":
            if room["phase"] != "playing":
                return jsonify({"ok": False, "error": "not playing"}), 400
            MODES[room["mode"]]["advance"](room, reason="host")
            return jsonify({"ok": True})
        if cmd == "reject":
            # moderator action: drop one submission before reveal
            st = room["mode_state"]
            pid = data.get("player_id", "")
            if room.get("mode") == "roast-relay" and pid in st.get("lines", {}):
                del st["lines"][pid]
                _broadcast(room, "submission.rejected", {"player_id": pid})
                return jsonify({"ok": True})
            return jsonify({"ok": False, "error": "nothing to reject"}), 400
        return jsonify({"ok": False, "error": "unknown cmd"}), 400


@party_bp.route("/party/<code>/ready", methods=["POST"])
def ready(code):
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False}), 404
    data = request.json or {}
    with LOCK:
        p = _player_by_token(room, data.get("seat_token", ""))
        if not p:
            return jsonify({"ok": False, "error": "bad seat"}), 403
        p["ready"] = bool(data.get("ready", True))
        _broadcast(room, "player.ready",
                   {"name": p["name"], "ready": p["ready"]})
        return jsonify({"ok": True, "ready": p["ready"]})


@party_bp.route("/party/<code>/input", methods=["POST"])
def player_input(code):
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = request.json or {}
    with LOCK:
        _check_timer(room)
        p = _player_by_token(room, data.get("seat_token", ""))
        if not p:
            return jsonify({"ok": False, "error": "bad seat"}), 403
        # client_seq dedup: retries never double-apply
        cseq = data.get("client_seq")
        if cseq is not None:
            seen = room["seen_seq"].setdefault(p["id"], set())
            if cseq in seen:
                return jsonify({"ok": True, "dup": True})
            seen.add(cseq)
            if len(seen) > 500:
                seen.clear()
                seen.add(cseq)
        if room["phase"] != "playing":
            return jsonify({"ok": False, "error": "not playing"}), 400
        if data.get("kind") == "laugh":
            _broadcast(room, "laugh", {"by": p["name"]})
            return jsonify({"ok": True})
        return jsonify(MODES[room["mode"]]["input"](room, p, data))


@party_bp.route("/party/<code>/view", methods=["GET"])
def view(code):
    """Private per-role view. The ONLY endpoint that serves secrets."""
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False}), 404
    with LOCK:
        _check_timer(room)
        p = _player_by_token(room, request.args.get("seat_token", ""))
        return jsonify({"ok": True,
                        "view": _controller_view(room, p)})


@party_bp.route("/party/<code>/stream", methods=["GET"])
def stream(code):
    """Shared public event stream. Secrets NEVER appear here.
    ?last_seq=N replays missed events; ?once=1 returns JSON (poll fallback)."""
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False}), 404
    try:
        last = int(request.args.get("last_seq", 0))
    except Exception:
        last = 0
    with LOCK:
        missed = [e for e in room["events"] if e["seq"] > last]
        snap = _stage_public(room)
        seq = room["seq"]
    if request.args.get("once") == "1":
        return jsonify({"ok": True, "seq": seq, "snapshot": snap,
                        "events": missed})

    def _gen():
        yield f"data: {json.dumps({'type': 'snapshot', 'seq': seq, 'snapshot': snap})}\n\n"
        for e in missed:
            yield f"data: {json.dumps(e)}\n\n"
        # heartbeat; browsers reconnect and resume from last seq
        yield f"data: {json.dumps({'type': 'ping', 'seq': seq})}\n\n"
    return Response(_gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@party_bp.route("/party/<code>/stage", methods=["GET"])
def stage(code):
    room = _get_room(code)
    if not room:
        return "No such room. Create one at /play.", 404
    return STAGE_TEMPLATE.replace("__CODE__", room["code"])


@party_bp.route("/party/<code>/play", methods=["GET"])
def play(code):
    room = _get_room(code)
    if not room:
        return "No such room. Create one at /play.", 404
    return CONTROLLER_TEMPLATE.replace("__CODE__", room["code"])


JOIN_TEMPLATE = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Join __CODE__ — Freak Town Party</title></head>
<body style='background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>
<div style='color:#ff2fa8;letter-spacing:2px;font-size:12px'>FREAK TOWN PARTY</div>
<h1>Room __CODE__</h1>
<p style='color:#888'>No account. Pick a name, pick your freak.</p>
<input id=n placeholder='your name' maxlength=24 style='padding:10px;font-size:16px;width:220px'><br><br>
<input id=f placeholder='your freak (e.g. Martin Lamp)' maxlength=24 style='padding:10px;font-size:16px;width:220px'><br><br>
<button onclick='join()' style='font-size:18px;padding:12px 32px;background:#ff2fa8;border:0;color:#fff;border-radius:24px'>JOIN</button>
<p id=m style='color:#ff2fa8'></p>
<script>
async function join(){
  const r = await fetch('/party/__CODE__/join',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name: document.getElementById('n').value, freak: document.getElementById('f').value})});
  const d = await r.json();
  if(!d.ok){ document.getElementById('m').textContent = d.error||'join failed'; return; }
  if(d.role === 'player'){
    try{ localStorage.setItem('ft_seat___CODE__', d.seat_token); }catch(e){}
    location = '/party/__CODE__/play?seat=' + encodeURIComponent(d.seat_token);
  } else {
    location = '/party/__CODE__/play'; // room full/locked: audience controller
  }
}
</script></body></html>"""

STAGE_TEMPLATE = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>__CODE__ — Freak Town Party Stage</title>
<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;margin:0}
.top{padding:8px;font-size:12px;letter-spacing:3px;color:#ff2fa8}
#code{font-size:44px;letter-spacing:8px;margin:4px}
#cv{background:#111;border:1px solid #333;border-radius:12px;touch-action:none}
#cap{font-size:20px;min-height:30px;margin:8px}
#scores{color:#888;font-size:13px}</style></head><body>
<div class=top>FREAK TOWN PARTY</div>
<div id=code>__CODE__</div>
<div style='color:#555;font-size:12px'>SCAN TO JOIN · freak.town/join/__CODE__</div>
<img src='/party/__CODE__/qr.png' style='width:120px;margin:6px' alt='join qr'>
<div><canvas id=cv width=560 height=360></canvas></div>
<div id=cap></div>
<div id=scores></div>
<script>
let seq = 0;
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
ctx.strokeStyle = '#ff2fa8'; ctx.lineWidth = 3; ctx.lineCap = 'round';
function drawStroke(pts){
  ctx.beginPath();
  pts.forEach((p,i)=>{ const x=p[0]*cv.width, y=p[1]*cv.height;
    i ? ctx.lineTo(x,y) : ctx.moveTo(x,y); });
  ctx.stroke();
}
async function poll(){
  try{
    const r = await fetch('/party/__CODE__/stream?last_seq='+seq+'&once=1');
    const d = await r.json();
    seq = d.seq;
    render(d.snapshot);
    (d.events||[]).forEach(ev=>{
      if(ev.kind === 'draw.batch') drawStroke(ev.points);
      if(ev.kind === 'round.started'){ ctx.clearRect(0,0,cv.width,cv.height); };
    });
  }catch(e){}
  setTimeout(poll, 800);
}
function render(s){
  const cap = document.getElementById('cap'), sc = document.getElementById('scores');
  if(!s || s.room_phase === 'lobby'){
    cap.textContent = 'Waiting for players… ' + ((s.lobby&&s.lobby.count)||0) + ' joined';
    sc.textContent = (s.scores||[]).map(p=>p.name+' '+(p.ready?'✓':'…')).join('  ');
    return;
  }
  if(s.freaktionary){
    const f = s.freaktionary;
    cap.textContent = f.revealed ? ('Word was: ' + f.word) : (f.drawer + ' is drawing…');
    (f.strokes||[]).forEach(st=>drawStroke(st.points));
  } else if(s['roast-relay']){
    const r = s['roast-relay'];
    cap.textContent = r.phase === 'collecting'
      ? ('Roast: ' + r.target + ' (' + r.submitted + '/' + r.needed + ')')
      : ('Target: ' + r.target + (r.audio ? ' 🔊' : ''));
    sc.innerHTML = (r.clips||[]).map(c=>'<div>“'+escapeHtml(c.text)+'”</div>').join('')
      + '<div>' + (s.scores||[]).map(p=>escapeHtml(p.name)+': '+p.score).join(' · ') + '</div>';
    return;
  }
  sc.textContent = (s.scores||[]).map(p=>p.name+': '+p.score).join(' · ');
}
function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
poll();
</script></body></html>"""

CONTROLLER_TEMPLATE = """<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>
<title>Controller — Freak Town Party</title>
<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;margin:0;padding:16px}
button{background:#1a1a2e;border:1px solid #333;color:#eee;padding:14px 22px;border-radius:24px;font-size:16px;margin:4px}
button.big{background:#ff2fa8;border-color:#ff2fa8;color:#fff;width:100%}
textarea{width:100%;background:#111;border:1px solid #333;color:#eee;border-radius:10px;padding:10px;font-size:16px;min-height:80px}
#draw{background:#111;border:1px solid #333;border-radius:12px;touch-action:none;width:100%}
.opt{display:block;width:100%;text-align:left;margin:6px 0}</style></head><body>
<div style='color:#ff2fa8;font-size:11px;letter-spacing:2px'>FREAK TOWN PARTY · __CODE__</div>
<h2 id=t></h2><div id=sub style='color:#888'></div>
<div id=body style='max-width:520px;margin:0 auto'></div>
<script>
const CODE = '__CODE__';
let seat = new URLSearchParams(location.search).get('seat') || '';
try{ seat = seat || localStorage.getItem('ft_seat_'+CODE) || ''; }catch(e){}
let cseq = 0, lastScreen = '';
async function view(){
  try{
    const r = await fetch('/party/'+CODE+'/view?seat_token='+encodeURIComponent(seat));
    const d = await r.json();
    if(d.ok) render(d.view);
  }catch(e){}
  setTimeout(view, 1200);
}
function render(v){
  document.getElementById('t').textContent = titleFor(v);
  const b = document.getElementById('body');
  const key = v.screen + (v.secret||'') + JSON.stringify((v.components||[]).map(c=>c.id||c.type));
  if(key === lastScreen) return;
  lastScreen = key; b.innerHTML = '';
  (v.components||[]).forEach(c=>{
    if(c.type === 'text'){ const p=document.createElement('p'); p.textContent=c.text; b.appendChild(p); }
    if(c.type === 'textarea'){ const t=document.createElement('textarea'); t.id='fld_'+c.id;
      t.maxLength=c.max_length||180; b.appendChild(t); }
    if(c.type === 'submit'){ const btn=document.createElement('button'); btn.className='big';
      btn.textContent=c.label||'SEND'; btn.onclick=()=>submit(c); b.appendChild(btn); }
    if(c.type === 'button'){ const btn=document.createElement('button');
      btn.textContent=c.label||c.id; btn.onclick=()=>press(c.id); b.appendChild(btn); }
    if(c.type === 'choice'){ (c.options||[]).forEach(o=>{ const btn=document.createElement('button');
      btn.className='opt'; btn.textContent=o.text; btn.onclick=()=>vote(o.id); b.appendChild(btn); }); }
    if(c.type === 'canvas'){ const cv=document.createElement('canvas'); cv.id='draw';
      cv.width=520; cv.height=340; b.appendChild(cv); wireDraw(cv); }
  });
}
function titleFor(v){
  if(v.screen==='lobby') return 'LOBBY';
  if(v.screen==='drawer') return 'DRAW: ' + (v.secret||'');
  if(v.screen==='vote') return 'VOTE WINNER';
  if(v.screen==='scores') return 'SCORES';
  if(v.screen==='reveal') return 'REVEAL';
  if(v.screen==='audience') return 'AUDIENCE';
  return v.mode ? v.mode.toUpperCase() : 'FREAK TOWN';
}
async function submit(c){
  const t = document.getElementById('fld_guess') || document.getElementById('fld_line') || document.querySelector('textarea');
  const kind = document.getElementById('fld_guess') ? 'guess' : 'line';
  await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, client_seq: ++cseq, kind, text: t?t.value:''})});
  lastScreen = '';
}
async function vote(id){
  await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, client_seq: ++cseq, kind:'vote', choice: String(id)})});
}
async function press(id){
  if(id==='ready') await fetch('/party/'+CODE+'/ready',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, ready: true})});
  if(id==='laugh') await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, client_seq: ++cseq, kind:'laugh'})});
}
function wireDraw(cv){
  const ctx = cv.getContext('2d');
  ctx.strokeStyle='#ff2fa8'; ctx.lineWidth=4; ctx.lineCap='round';
  let pts = [], drawing = false, lastSend = 0;
  const pos = e=>{ const r=cv.getBoundingClientRect();
    const t=e.touches?e.touches[0]:e;
    return [Math.min(1,Math.max(0,(t.clientX-r.left)/r.width)),
            Math.min(1,Math.max(0,(t.clientY-r.top)/r.height))]; };
  const send = async()=>{ if(!pts.length) return;
    const batch = pts; pts = [];
    await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({seat_token: seat, client_seq: ++cseq,
                            kind:'draw.batch', points: batch})}); };
  cv.onpointerdown = e=>{ drawing=true; pts=[pos(e)]; };
  cv.onpointermove = e=>{ if(!drawing) return; const p=pos(e); pts.push(p);
    if(pts.length>1){ const a=pts[pts.length-2], b2=pts[pts.length-1];
      ctx.beginPath(); ctx.moveTo(a[0]*cv.width,a[1]*cv.height);
      ctx.lineTo(b2[0]*cv.width,b2[1]*cv.height); ctx.stroke(); }
    if(Date.now()-lastSend>80){ lastSend=Date.now(); send(); } };
  cv.onpointerup = ()=>{ drawing=false; send(); };
}
view();
</script></body></html>"""
