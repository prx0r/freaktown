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
DRAW_MIN_INTERVAL = 0.05  # 50-100ms batching, per CF WS guidance (advisory)
MQ_DRAW_SECONDS = 120
DRAW_MAX_PER_SEC = 30
ADVANCE_GRACE = 2.5  # a screen younger than this ignores the stage's ADVANCE
SKIP_MIN_AGE = 7.5  # a round must run this long before the stage may skip it
MQ_MAX_POINTS = 12000  # per drawing; keeps /view small enough to poll

# A reveal/score screen holds this long, then the lazy timer moves on, so a
# room keeps playing when the host's stage tab closes (host disconnect).
SCORED_HOLD = 12
# Standalone games end after this many rounds (host "start" may pass
# rounds=N). Freaktionary defaults to one turn at the pen per player.
DEFAULT_ROUNDS = {"roast-relay": 3, "quip": 3}
MAX_ROUNDS = 20

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


def _body() -> dict:
    """Request JSON as a dict. Bad/missing JSON or a non-object body is {}."""
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def _active(room: dict) -> list:
    """Seated players still in the game (a player who left keeps their seat
    record, so vote indexes and names stay stable, but nobody waits on them)."""
    return [pid for pid, p in room["players"].items() if not p.get("left")]


def _clean(s: str, limit: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:limit]


def _broadcast(room: dict, kind: str, public: dict) -> dict:
    """Persist-then-queue. The ONLY way stage-visible state changes."""
    room["seq"] += 1
    if room.get("players") is not None:
        k = _phase_key(room)
        if (room.get("phase_mark") or {}).get("key") != k:
            room["phase_mark"] = {"key": k, "t": _now()}
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
    st = room.get("mode_state") or {}
    if room["phase"] == "playing" and room.get("mode") in MODES \
            and st.get("deadline_at"):
        if _now() > st["deadline_at"]:
            MODES[room["mode"]]["advance"](room, reason="timeout")


def _public_players(room: dict) -> list:
    return [{"id": pid, "name": p["name"], "freak": p["freak"],
             "ready": p["ready"], "score": p["score"],
             "bot": bool(p.get("bot")), "left": bool(p.get("left"))}
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
                "seen_seq": {k: sorted(str(x) for x in v) for k, v in
                             room.get("seen_seq", {}).items()},
                "created_at": room["created_at"],
                "pack": room.get("pack"), "lore": room.get("lore"),
                "winner": room.get("winner"), "rounds": room.get("rounds")}
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
    room["mode_state"] = {
        "round": 0, "drawer_idx": -1, "drawer": None, "word": None,
        "guesses": [], "winner": None, "phase": "idle", "deadline_at": None,
        "strokes": [], "revealed": False, "batches": 0, "clears": 0,
        "points": 0,
    }


def _norm_guess(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _mq_start_round(room: dict):
    import random as _r
    st = room["mode_state"]
    order = _active(room)
    if not order:
        return
    st["round"] += 1
    st["drawer_idx"] = (st["drawer_idx"] + 1) % len(order)
    st["drawer"] = order[st["drawer_idx"]]
    used = st.setdefault("used", [])
    st["word"] = _r.choice([w for w in WORDS if w not in used] or WORDS)
    used.append(st["word"])
    st["guesses"] = []
    st["winner"] = None
    st["phase"] = "drawing"
    st["revealed"] = False
    st["strokes"] = []
    st["batches"] = 0
    st["points"] = 0
    st["clears"] = 0
    st["deadline_at"] = _now() + MQ_DRAW_SECONDS
    _broadcast(room, "round.started", {
        "mode": "freaktionary", "round": st["round"],
        "drawer": room["players"][st["drawer"]]["name"],
        "deadline_at": st["deadline_at"]})
    _mq_bots_act(room)


def _mq_reveal(room: dict, winner_pid: str | None, reason: str = ""):
    """Close the drawing: word goes public, screens flip to the reveal, and
    the room auto-advances after SCORED_HOLD (or on host advance)."""
    st = room["mode_state"]
    st["revealed"] = True
    st["phase"] = "revealed"
    st["winner"] = winner_pid
    st["deadline_at"] = _now() + SCORED_HOLD
    if winner_pid:
        room["players"][winner_pid]["score"] += 2
        if st["drawer"] in room["players"]:
            room["players"][st["drawer"]]["score"] += 1
        _record_win(room, winner_pid)
        _broadcast(room, "round.won", {
            "round": st["round"], "winner": room["players"][winner_pid]["name"],
            "word": st["word"], "scores": _public_players(room)})
    else:
        _broadcast(room, "round.revealed", {"round": st["round"],
                                            "word": st["word"],
                                            "reason": reason or "timeout"})


def _mq_guess(room: dict, player: dict, text: str) -> dict:
    st = room["mode_state"]
    guess = _clean(text, 60).lower()
    if not guess:
        return {"ok": False, "error": "empty guess"}
    if _norm_guess(guess) == _norm_guess(st["word"]):
        _mq_reveal(room, player["id"])
        return {"ok": True, "correct": True}
    st["guesses"].append({"by": player["name"], "text": guess})
    _broadcast(room, "guess", {"round": st["round"], "by": player["name"]})
    return {"ok": True, "correct": False}


def _mq_bots_act(room: dict):
    """Deck bots ($0): a bot drawer scribbles; bot guessers take a shot per
    stroke batch and land the word once the drawing has had a few strokes."""
    st = room["mode_state"]
    if room.get("mode") != "freaktionary" or st.get("phase") != "drawing":
        return
    import random as _r
    rng = _r.Random(f"{room['code']}:{st['round']}:{st.get('batches', 0)}")
    drawer = room["players"].get(st["drawer"]) or {}
    if drawer.get("bot") and not st["strokes"]:
        for k in range(3):
            pts = [[round(0.2 + 0.6 * rng.random(), 4),
                    round(0.2 + 0.6 * rng.random(), 4)] for _ in range(12)]
            st["strokes"].append({"id": f"bot{k}", "by": st["drawer"],
                                  "points": pts})
            st["batches"] += 1
            st["points"] = st.get("points", 0) + len(pts)
            _broadcast(room, "draw.batch", {"round": st["round"], "points": pts})
    if st["batches"] < 3:
        return
    for pid in _active(room):
        p = room["players"][pid]
        if not p.get("bot") or pid == st["drawer"]:
            continue
        if st["phase"] != "drawing":
            return
        if rng.random() < 0.4:
            _mq_guess(room, p, st["word"])
        else:
            _mq_guess(room, p, rng.choice([w for w in WORDS if w != st["word"]]))


def _mq_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    kind = data.get("kind")
    if st["phase"] != "drawing" or st.get("revealed"):
        return {"ok": False, "error": "not accepting input now"}
    if kind == "draw.clear":
        if player["id"] != st["drawer"]:
            return {"ok": False, "error": "only the drawer draws"}
        st["strokes"] = []
        st["points"] = 0
        st["clears"] = st.get("clears", 0) + 1
        _broadcast(room, "draw.clear", {"round": st["round"]})
        return {"ok": True}
    if kind == "draw.batch":
        if player["id"] != st["drawer"]:
            return {"ok": False, "error": "only the drawer draws"}
        pts = data.get("points") or []
        if not isinstance(pts, list) or len(pts) > 400:
            return {"ok": False, "error": "bad batch"}
        clean = []
        for pt in pts:
            try:
                x, y = float(pt[0]), float(pt[1])
                if 0 <= x <= 1 and 0 <= y <= 1:
                    clean.append([round(x, 3), round(y, 3)])
            except Exception:
                continue
        if not clean:
            return {"ok": True, "empty": True}
        if st.get("points", 0) + len(clean) > MQ_MAX_POINTS:
            return {"ok": False, "error": "canvas full"}
        # flood guard: a real phone sends ~7 batches/s; a burst far past
        # that is a script, not a finger
        win = [t for t in player.get("draw_times", []) if _now() - t < 1.0]
        if len(win) >= DRAW_MAX_PER_SEC:
            return {"ok": False, "error": "slow down"}
        win.append(_now())
        player["draw_times"] = win
        player["last_draw"] = _now()
        # a stroke arrives in ~150 ms batches; batches carrying the same
        # stroke id extend one continuous line instead of starting new ones
        sid = str(data.get("stroke") or "")[:24]
        target = None
        if sid:
            for s_ in reversed(st["strokes"][-8:]):
                if s_.get("id") == sid and s_.get("by") == player["id"]:
                    target = s_
                    break
        if target is not None:
            target["points"].extend(clean)
        else:
            st["strokes"].append({"id": sid or f"s{st.get('batches', 0)}",
                                  "by": player["id"], "points": clean})
        st["batches"] = st.get("batches", 0) + 1
        st["points"] = st.get("points", 0) + len(clean)
        _broadcast(room, "draw.batch", {"round": st["round"], "stroke": sid,
                                        "points": clean})
        _mq_bots_act(room)
        return {"ok": True}
    if kind == "guess":
        if player["id"] == st["drawer"]:
            return {"ok": False, "error": "drawer cannot guess"}
        return _mq_guess(room, player, data.get("text", ""))
    return {"ok": False, "error": "unknown input"}


def _mq_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "drawing" and not st.get("revealed"):
        _mq_reveal(room, None, reason)  # no winner: reveal, no points
        return
    if _pack_quota_met(room):
        _pack_next(room)
        return
    if _rounds_done(room):
        _finish_game(room)
        return
    _mq_start_round(room)


def _rr_create(room: dict):
    room["mode_state"] = {
        "round": 0, "target": None, "lines": {}, "order": [], "votes": {},
        "phase": "collecting", "deadline_at": None, "revealed": False,
        "audio": None, "audio_status": "none", "callback": None,
    }


def _rr_start_round(room: dict, target: str = ""):
    st = room["mode_state"]
    st["round"] = st.get("round", 0) + 1
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
                                         "round": st["round"],
                                         "target": st["target"],
                                         "deadline_at": st["deadline_at"]})
    _rr_bots_act(room, "collect")


RR_BOT_LINES = [
    "they bought an air fryer and now it's their whole personality",
    "even their smoke alarm cheers them on when they cook",
    "their LinkedIn says 'visionary'. their microwave says otherwise",
    "they once lost an argument to a self-checkout",
    "their group chat has a mute button with their name on it",
    "they still clap when the plane lands. on the train",
]


def _rr_bots_act(room: dict, stage: str):
    """Deck bots ($0): a line each from RR_BOT_LINES, then a non-self vote."""
    st = room["mode_state"]
    if room.get("mode") != "roast-relay":
        return
    import random as _r
    rng = _r.Random(f"{room['code']}:rr:{st.get('round', 0)}")
    bots = [pid for pid in _active(room) if room["players"][pid].get("bot")]
    if not bots:
        return
    if stage == "collect" and st["phase"] == "collecting":
        for pid in bots:
            if pid not in st["lines"]:
                used = set(st["lines"].values())
                avail = [l for l in RR_BOT_LINES if l not in used] or RR_BOT_LINES
                st["lines"][pid] = rng.choice(avail)
        _rr_check_complete(room)
    elif stage == "vote" and st["phase"] == "voting":
        clips = _rr_assembled(room)
        for pid in bots:
            if pid in st["votes"]:
                continue
            mine = [str(c["i"]) for c in clips if st["order"][c["i"]] != pid]
            if mine:
                st["votes"][pid] = rng.choice(mine)
        _rr_check_complete(room)


def _rr_check_complete(room: dict):
    """Everyone still in the game has acted: move on without the timer."""
    st = room["mode_state"]
    act = _active(room)
    if not act:
        return
    if st["phase"] == "collecting" and st["lines"] and \
            all(p in st["lines"] for p in act):
        _rr_reveal(room)
    elif st["phase"] == "voting":
        clips = _rr_assembled(room)
        # a voter whose only option is their own clip can't vote: skip them
        need = [p for p in act
                if any(st["order"][c["i"]] != p for c in clips)]
        if all(p in st["votes"] for p in need):
            _rr_score(room)


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
                                           "needed": len(_active(room))})
        _rr_check_complete(room)
        return {"ok": True}
    if kind == "vote":
        if st["phase"] != "voting":
            return {"ok": False, "error": "not voting now"}
        choice = str(data.get("choice"))
        # only clips that exist are votable (a seat that wrote nothing has
        # an order index but no clip)
        valid_ids = [str(c["i"]) for c in _rr_assembled(room)]
        if choice not in valid_ids:
            return {"ok": False, "error": "bad choice"}
        # no self-vote: the clip at index `choice` must not be yours
        if st["order"][int(choice)] == player["id"]:
            return {"ok": False, "error": "no self-votes"}
        st["votes"][player["id"]] = choice
        _broadcast(room, "vote.accepted", {"by": player["name"],
                                           "count": len(st["votes"])})
        _rr_check_complete(room)
        return {"ok": True}
    return {"ok": False, "error": "unknown input"}


def _rr_assembled(room: dict) -> list:
    st = room["mode_state"]
    clips = []
    for i, pid in enumerate(st["order"]):
        if pid in st["lines"] and pid in room["players"]:
            clips.append({"i": i, "by": room["players"][pid]["name"],
                          "text": st["lines"][pid]})
    return clips


def _rr_reveal(room: dict):
    st = room["mode_state"]
    st["phase"] = "voting"
    st["deadline_at"] = _now() + 60
    clips = _rr_assembled(room)
    st["callback"] = _ella_callback(room)
    _broadcast(room, "set.revealed", {"mode": "roast-relay",
                                      "target": st["target"], "clips": clips,
                                      "callback": st["callback"],
                                      "deadline_at": st["deadline_at"]})
    # SHORT_GENERATION audio upgrade runs async; the room never waits for it.
    _rr_maybe_tts(room, clips)
    _rr_bots_act(room, "vote")


def _rr_maybe_tts(room: dict, clips: list):
    """Best-effort TTS of the assembled set. Text reveal already happened;
    audio arrives later as generation.ready (or never — that's fine)."""
    st = room["mode_state"]
    import os as _os
    if _os.environ.get("PARTY_TTS", "1") == "0":
        return  # offline / tests: text reveal only
    try:
        import edge_tts  # noqa  (free Edge voice; no account, no spend)
    except Exception:
        return
    st["audio_status"] = "pending"
    _broadcast(room, "generation.pending", {"what": "roast-relay audio"})
    want_round = st.get("round")

    def _current() -> bool:
        return (room.get("mode") == "roast-relay"
                and room["mode_state"].get("round") == want_round)

    def _run():
        try:
            import asyncio as _a
            import hashlib as _h
            text = " ".join(c["text"] for c in clips)[:600]
            tag = _h.sha256(text.encode()).hexdigest()[:12]
            outdir = BASE / "audio_output"
            outdir.mkdir(exist_ok=True)
            out = outdir / f"party_{room['code']}_{tag}.mp3"
            _a.run(_a.wait_for(_a_send(text, str(out)), timeout=30))
            with LOCK:
                if _current():
                    room["mode_state"]["audio"] = f"/audio/{out.name}"
                    room["mode_state"]["audio_status"] = "ready"
                    _broadcast(room, "generation.ready",
                               {"what": "roast-relay audio",
                                "audio": f"/audio/{out.name}"})
        except Exception:
            with LOCK:
                if _current():
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
    st["deadline_at"] = _now() + SCORED_HOLD
    _broadcast(room, "score.updated", {"tally": tally,
                                       "scores": _public_players(room)})


def _rr_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "collecting" and st["lines"]:
        _rr_reveal(room)
    elif st["phase"] == "voting":
        _rr_score(room)
    else:  # scored, or nobody wrote anything (skip; still counts a round)
        if _pack_quota_met(room):
            _pack_next(room)
            return
        if _rounds_done(room):
            _finish_game(room)
            return
        _rr_start_round(room, st.get("target") or "")


# ── freeze-night (MVP improv evening) ───────────────────────────────────
# One mode, internal round playlist: prompt rounds (ending/walkin/object/
# answer) + ritual halftime + wheel interlude + last-lash final.
# Modifiers: callback bonus (declared callback:<event-id> pays x1.5 once
# per event), caught-that recognition board, sweep bonus, triple-point final.

FZ_ROUNDS = [
    {"id": "scene1-ending", "format": "funnier-ending", "limit": 180},
    {"id": "scene1-walkin", "format": "freeze-frame", "limit": 60},
    {"id": "ritual-halftime", "format": "humiliation-ritual", "limit": 180},
    {"id": "scene2-object", "format": "pocket-object", "limit": 60},
    {"id": "scene2-ending", "format": "funnier-ending", "limit": 180},
    {"id": "wheel", "format": "wheel-of-shame", "limit": 0},
    {"id": "last-lash", "format": "last-lash", "limit": 180},
]

FZ_SEEDS = {
    "scene1-ending": "The scene freezes mid-argument. How does it end?",
    "scene1-walkin": "The door opens. Who walks through it? (who + trait + want)",
    "ritual-halftime": "Write a cruel line + manner for the victim. Format: LINE // MANNER",
    "scene2-object": "A hand slides into a pocket. What does he pull out?",
    "scene2-ending": "New scene, same cast. The lights dim — how does it end?",
    "last-lash": "The night's epitaph, one line each. Make it count triple.",
}

FZ_RITE_DECK = [
    "Read this breakup text like a weather report",
    "Apologize in an Australian accent to a houseplant",
    "Deliver this news flash while sobbing with joy",
]
FZ_WHEEL = [
    "Accent apology (30s)", "Hostile self-monologue", "Eulogize the object",
    "Room writes your texts", "Dunce Avatar 3 rounds", "Defend the worst take",
    "Nature-doc replay", "Callback tax: invoke 3 events in 30s",
]
FZ_POOL, FZ_SWEEP, FZ_FINAL_POOL = 100, 25, 300

# ── bot contestants (solo-vs-agents) ────────────────────────────────────
# Deck-based ($0, no API): bots submit entries + votes from seeded decks.
# Upgrade path (ask-first spend): Jev choice over entries (~$0.0001/call),
# Qwen omni lines (per-call). Bots are plain players with bot:true and no
# token — they act through _fz_bots_act, never HTTP.
FZ_BOT_DECK = {
    "funnier-ending": [
        "and then the landlord walked in. everyone pretended this was normal.",
        "blackout. a single microwave beep. applause.",
        "they agreed to never speak of the soup again.",
        "the credits rolled but nobody left. the usher gave up.",
        "it was all a rehearsal. the real argument is tuesday.",
        "a pigeon landed on the punchline. it stayed.",
    ],
    "freeze-frame": [
        "a divorced magician who wants his rabbit back",
        "the health inspector, already disappointed",
        "a raccoon in a tiny high-vis vest, here about the bins",
        "your ex, holding a casserole and a grudge",
        "a knight who missed the theme memo by 600 years",
    ],
    "pocket-object": [
        "a single victorious peanut", "divorce papers for his microwave",
        "a Blockbuster card, still hopeful", "someone else's house key",
        "a trophy that says WORLD'S OKAYEST",
    ],
    "humiliation-ritual": [
        "I love you // like a parking ticket",
        "I am so sorry // sobbing with joy",
        "This means everything // in an Australian accent",
        "No regrets // while maintaining aggressive eye contact with a houseplant",
        "We need to talk // like a weather report",
    ],
    "last-lash": [
        "here lies the punchline. it is survived by the callback.",
        "gone but not forgotten. unlike kevin.",
        "they laughed. that was the whole plan.",
        "exit pursued by applause.",
    ],
}
FZ_BOT_NAMES = ["Ralph", "Nolan", "Ella-2", "Kevin"]


def _fz_rng(room: dict):
    import random as _r
    seed = int.from_bytes(__import__("hashlib").sha256(
        room["code"].encode()).digest()[:4], "big")
    return _r.Random(seed + room["mode_state"].get("ri", 0))


def _fz_humans(room: dict) -> list:
    return [pid for pid, p in room["players"].items() if not p.get("bot")]


def _fz_add_bots(room: dict, n: int) -> list:
    """Seat n bot contestants. Returns their names."""
    made = []
    have = sum(1 for p in room["players"].values() if p.get("bot"))
    for i in range(n):
        name = FZ_BOT_NAMES[(have + i) % len(FZ_BOT_NAMES)]
        pid = f"bot{have + i}_{secrets.token_hex(2)}"
        room["players"][pid] = {"id": pid, "name": name + " (AI)",
                                "freak": name, "token": "", "ready": True,
                                "score": 0, "connected": True,
                                "last_draw": 0.0, "bot": True}
        made.append(name)
    if made:
        _broadcast(room, "bots.joined", {"names": made})
    return made


def _fz_bot_pick(rng, deck: list, used: set) -> str:
    avail = [d for d in deck if d not in used] or deck
    return rng.choice(avail)


def _fz_bots_act(room: dict, stage: str):
    """Drive every bot for the current phase/stage. Synchronous: bots never
    stall a night; humans act at their own pace and auto-flow completes."""
    st = room["mode_state"]
    if room.get("mode") != "freeze-night" or st.get("night_done"):
        return
    rng = _fz_rng(room)
    bots = [pid for pid in _fz_players(room)
            if room["players"][pid].get("bot")]
    if not bots:
        return
    if stage == "collect" and st["phase"] == "collecting":
        if st["kind"] == "humiliation-ritual":
            for pid in bots:
                if pid != st["ritual"]["victim"] and pid not in st["entries"]:
                    deck = FZ_BOT_DECK["humiliation-ritual"]
                    used = set(st["entries"].values())
                    st["entries"][pid] = _fz_bot_pick(rng, deck, used)
            others = [p for p in _fz_players(room)
                      if p != st["ritual"]["victim"]]
            if others and all(p in st["entries"] for p in others):
                texts = [(p, st["entries"][p]) for p in others]
                spot = max(texts, key=lambda t: len(t[1]))[0]
                st["ritual"]["spotlight"] = spot
                _fz_add_archive(room, spot, st["entries"][spot])
                st["phase"] = "passfail"
                st["deadline_at"] = _now() + 60
                _broadcast(room, "set.revealed", {
                    "mode": "freeze-night", "round": st["round_id"],
                    "victim": room["players"][st["ritual"]["victim"]]["name"],
                    "line": st["entries"][spot]})
                _fz_bots_act(room, "passfail")
        else:
            deck = FZ_BOT_DECK.get(st["kind"], FZ_BOT_DECK["funnier-ending"])
            for pid in bots:
                if pid not in st["entries"]:
                    used = set(v for k, v in st["entries"].items()
                               if not k.endswith(":cb"))
                    st["entries"][pid] = _fz_bot_pick(rng, deck, used)
            if _fz_all_in(room, st["entries"]):
                _fz_reveal(room)
    elif stage == "vote" and st["phase"] == "voting":
        ids = _fz_option_ids(room)
        for pid in bots:
            if pid in st["votes"] or not ids:
                continue
            mine = [i for i in ids if st["order"][i] != pid] or ids
            if st["kind"] == "last-lash":
                st["votes"][pid] = sorted(mine)[:3]
            else:
                st["votes"][pid] = [rng.choice(mine)]
        if _fz_votes_done(room):
            _fz_score_prompt(room)
    elif stage == "passfail" and st["phase"] == "passfail":
        for pid in bots:
            if pid != st["ritual"]["victim"] and pid not in st["ritual"]["passed"]:
                st["ritual"]["passed"][pid] = rng.choice(["pass", "pass", "fail"])
        others = [p for p in _fz_players(room) if p != st["ritual"]["victim"]]
        if others and all(p in st["ritual"]["passed"] for p in others):
            passes = sum(1 for v in st["ritual"]["passed"].values() if v == "pass")
            share = round(passes / max(1, len(others)) * FZ_POOL)
            _fz_award(room, st["ritual"]["victim"],
                      share * (2 if _fz_self_landed(room) else 1))
            st["phase"] = "author"
            st["deadline_at"] = _now() + 60
            _broadcast(room, "ritual.judged", {
                "victim": room["players"][st["ritual"]["victim"]]["name"],
                "passes": passes, "of": len(others)})
            _fz_bots_act(room, "author")
    elif stage == "author" and st["phase"] == "author":
        for pid in bots:
            if pid != st["ritual"]["victim"] and pid not in st["ritual"]["guesses"]:
                cands = [p for p in _fz_players(room)
                         if p != st["ritual"]["victim"] and p != pid]
                st["ritual"]["guesses"][pid] = rng.choice(cands) if cands else pid
        others = [p for p in _fz_players(room) if p != st["ritual"]["victim"]]
        if others and all(p in st["ritual"]["guesses"] for p in others):
            _fz_score_ritual(room)
    elif stage == "verdict" and st["phase"] == "verdict":
        for pid in bots:
            if pid not in st["wheel"]["verdicts"]:
                st["wheel"]["verdicts"][pid] = rng.choice(["served", "served", "double"])
        if _fz_all_in(room, st["wheel"]["verdicts"]):
            _fz_score_wheel(room)


def _fz_create(room: dict):
    room["mode_state"] = {
        "ri": -1, "round_id": None, "kind": None, "phase": "idle",
        "prompt": None, "entries": {}, "order": [], "votes": {},
        "caught": {}, "archive": [], "paid": [], "recognized": {},
        "ritual": {"victim": None, "order": [], "passed": {},
                   "guesses": {}, "spotlight": None},
        "wheel": {"segments": list(FZ_WHEEL), "burned": [],
                  "victim": None, "segment": None, "verdicts": {},
                  "doubles": 0},
        "reveal": False, "deadline_at": None, "winner": None,
        "night_done": False,
    }


def _fz_players(room: dict) -> list:
    return _active(room)


def _fz_all_in(room: dict, got: dict) -> bool:
    """Every active player has a key in `got` (entries, votes, verdicts).
    Callback markers (<pid>:cb) never count as a player's entry."""
    act = _fz_players(room)
    return bool(act) and all(p in got for p in act)


def _fz_option_ids(room: dict) -> list:
    return [o["i"] for o in _fz_assembled(room)]


def _fz_votes_done(room: dict) -> bool:
    """All active voters are in. In prompt rounds a player whose only
    option is their own entry has nothing to vote for, so nobody waits."""
    st = room["mode_state"]
    ids = _fz_option_ids(room)
    need = [p for p in _fz_players(room)
            if st["kind"] == "last-lash" or any(st["order"][i] != p for i in ids)]
    return bool(st["votes"]) and all(p in st["votes"] for p in need)


def _fz_next_round(room: dict):
    st = room["mode_state"]
    st["ri"] += 1
    if st["ri"] >= len(FZ_ROUNDS):
        _fz_finish(room)
        return
    spec = FZ_ROUNDS[st["ri"]]
    st["round_id"] = spec["id"]
    st["kind"] = spec["format"]
    st["entries"] = {}
    st["votes"] = {}
    st["caught"] = {}
    st["order"] = _fz_players(room)
    st["reveal"] = False
    r = st["ritual"]
    r["victim"] = r["order"] = r["spotlight"] = None
    r["passed"] = {}
    r["guesses"] = {}
    w = st["wheel"]
    w["victim"] = w["segment"] = None
    w["verdicts"] = {}
    w["doubles"] = 0
    kind = st["kind"]
    if kind == "humiliation-ritual":
        st["prompt"] = FZ_SEEDS[st["round_id"]]
        if _fz_players(room):
            r["victim"] = _fz_players(room)[st["ri"] % len(_fz_players(room))]
        st["phase"] = "collecting"
        st["deadline_at"] = _now() + 90
    elif kind == "wheel-of-shame":
        st["prompt"] = "Spin the wheel. Somebody pays."
        _fz_spin(room)
        st["phase"] = "verdict"
        st["deadline_at"] = _now() + 60
        _fz_bots_act(room, "verdict")
    else:
        st["prompt"] = FZ_SEEDS[st["round_id"]]
        st["phase"] = "collecting"
        st["deadline_at"] = _now() + 90
    _broadcast(room, "round.started", {
        "mode": "freeze-night", "round": st["round_id"], "format": kind,
        "prompt": st["prompt"], "deadline_at": st["deadline_at"]})
    if st["phase"] == "collecting":
        _fz_bots_act(room, "collect")


def _fz_archive_id(room: dict) -> str:
    return f"e{len(room['mode_state']['archive']) + 1}"


def _fz_add_archive(room: dict, by_pid: str, text: str) -> dict:
    st = room["mode_state"]
    ev = {"id": _fz_archive_id(room), "round": st["round_id"],
          "by": room["players"][by_pid]["name"] if by_pid in room["players"]
          else by_pid, "text": text, "invokes": 0}
    st["archive"].append(ev)
    return ev


def _fz_assembled(room: dict) -> list:
    """Entries as votable options. Authorship hidden until scored."""
    st = room["mode_state"]
    return [{"i": i, "text": st["entries"][pid]}
            for i, pid in enumerate(st["order"]) if pid in st["entries"]]


def _fz_award(room: dict, pid: str, points: int):
    if pid in room["players"]:
        room["players"][pid]["score"] += points


def _fz_cb_multiplier(room: dict, data: dict) -> float:
    """Declared callback:<event-id> pays x1.5 once per event per night."""
    st = room["mode_state"]
    want = str(data.get("callback") or "").strip()
    if not want:
        return 1.0
    ids = {e["id"] for e in st["archive"]}
    if want not in ids or want in st["paid"]:
        return 1.0
    st["paid"].append(want)
    for e in st["archive"]:
        if e["id"] == want:
            e["invokes"] += 1
    return 1.5


def _fz_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    kind = data.get("kind")
    phase = st["phase"]
    if kind == "caught":
        ev = str(data.get("event") or "")
        if any(e["id"] == ev for e in st["archive"]):
            st["caught"][player["id"]] = ev
            st["recognized"][ev] = st["recognized"].get(ev, 0) + 1
            _broadcast(room, "caught.that",
                       {"by": player["name"], "event": ev})
            return {"ok": True}
        return {"ok": False, "error": "unknown event"}
    if st["kind"] == "humiliation-ritual":
        return _fz_ritual_input(room, player, data)
    if st["kind"] == "wheel-of-shame":
        return _fz_wheel_input(room, player, data)
    # prompt rounds: entry → vote
    if kind == "entry":
        if phase != "collecting":
            return {"ok": False, "error": "not collecting now"}
        limit = FZ_ROUNDS[st["ri"]]["limit"] or MAX_TEXT
        text = _clean(data.get("text", ""), limit)
        if not text:
            return {"ok": False, "error": "empty entry"}
        mult = _fz_cb_multiplier(room, data)
        st["entries"][player["id"]] = text
        if mult > 1.0:
            st["entries"][player["id"] + ":cb"] = mult
        _broadcast(room, "entry.accepted", {
            "by": player["name"],
            "count": sum(1 for k in st["entries"] if not k.endswith(":cb")),
            "needed": len(_fz_players(room))})
        if _fz_all_in(room, st["entries"]):
            _fz_reveal(room)
        return {"ok": True}
    if kind == "vote":
        if phase != "voting":
            return {"ok": False, "error": "not voting now"}
        ids = _fz_option_ids(room)  # option ids are seat-order indexes
        if st["kind"] == "last-lash":
            # up to 3 stacked votes; anyone (even self). The phone sends
            # only `choices`, the API may send `choice` too.
            votes = data.get("choices")
            if not isinstance(votes, list) or not votes:
                votes = [data.get("choice")]
            mine = []
            for v in votes[:3]:
                try:
                    v = int(v)
                except Exception:
                    continue
                if v in ids:
                    mine.append(v)
            if not mine:
                return {"ok": False, "error": "bad choices"}
            st["votes"][player["id"]] = mine
        else:
            try:
                choice = int(data.get("choice"))
            except Exception:
                return {"ok": False, "error": "bad choice"}
            if choice not in ids:
                return {"ok": False, "error": "bad choice"}
            if st["order"][choice] == player["id"]:
                return {"ok": False, "error": "no self-votes"}
            st["votes"][player["id"]] = [choice]
        _broadcast(room, "vote.accepted", {"by": player["name"],
                                           "count": len(st["votes"])})
        if _fz_votes_done(room):
            _fz_score_prompt(room)
        return {"ok": True}
    return {"ok": False, "error": "unknown input"}


def _fz_reveal(room: dict):
    st = room["mode_state"]
    st["phase"] = "voting"
    st["reveal"] = True
    st["deadline_at"] = _now() + 60
    for pid, text in list(st["entries"].items()):
        if pid.endswith(":cb"):
            continue
        _fz_add_archive(room, pid, text)
    _broadcast(room, "set.revealed", {"mode": "freeze-night",
                                      "round": st["round_id"],
                                      "options": _fz_assembled(room),
                                      "deadline_at": st["deadline_at"]})
    _fz_bots_act(room, "vote")


def _fz_score_prompt(room: dict):
    """Vote-% of pool + sweep bonus; callback multiplier on winner's cut."""
    st = room["mode_state"]
    final = st["kind"] == "last-lash"
    pool = FZ_FINAL_POOL if final else FZ_POOL
    tally: dict = {}
    total = 0
    for voter, choices in st["votes"].items():
        for c in choices:
            tally[str(c)] = tally.get(str(c), 0) + 1
            total += 1
    winner_pid = None
    if tally and total:
        win = max(tally, key=tally.get)
        if tally[win] == total and total >= 2 and len(_fz_assembled(room)) > 1:
            share = pool + FZ_SWEEP  # sweep: unanimous
        else:
            share = round(tally[win] / total * pool)
        winner_pid = st["order"][int(win)]
        mult = st["entries"].get(winner_pid + ":cb", 1.0)
        share = round(share * mult)
        _fz_award(room, winner_pid, share)
        _record_win(room, winner_pid)
    st["phase"] = "scored"
    st["deadline_at"] = _now() + SCORED_HOLD
    _broadcast(room, "score.updated", {
        "round": st["round_id"], "tally": tally,
        "winner": (room["players"][winner_pid]["name"]
                   if winner_pid else None),
        "scores": _public_players(room)})


def _fz_ritual_input(room: dict, player: dict, data: dict):
    """One victim, one spotlight line (longest submitted). Ballots:
    pass/fail on the performance, then author-guess on the spotlight."""
    st = room["mode_state"]
    r = st["ritual"]
    kind = data.get("kind")
    if kind in ("rite", "entry"):  # the phone's textarea sends "entry"
        if st["phase"] != "collecting":
            return {"ok": False, "error": "not collecting now"}
        if player["id"] == r["victim"]:
            return {"ok": False, "error": "victim doesn't write"}
        text = _clean(data.get("text", ""), MAX_TEXT)
        if not text:
            return {"ok": False, "error": "empty line"}
        st["entries"][player["id"]] = text
        _broadcast(room, "entry.accepted", {"by": player["name"],
                                            "count": len(st["entries"])})
        others = [p for p in _fz_players(room) if p != r["victim"]]
        if others and all(p in st["entries"] for p in others):
            texts = [(pid, st["entries"][pid]) for pid in others]
            spot = max(texts, key=lambda t: len(t[1]))[0]
            r["spotlight"] = spot
            _fz_add_archive(room, spot, st["entries"][spot])
            st["phase"] = "passfail"
            st["deadline_at"] = _now() + 60
            _broadcast(room, "set.revealed", {
                "mode": "freeze-night", "round": st["round_id"],
                "victim": room["players"][r["victim"]]["name"],
                "line": st["entries"][spot], "deadline_at": st["deadline_at"]})
            _fz_bots_act(room, "passfail")
        return {"ok": True}
    if kind == "pass":
        if st["phase"] != "passfail":
            return {"ok": False, "error": "not judging now"}
        if player["id"] == r["victim"]:
            return {"ok": False, "error": "victim doesn't judge"}
        if data.get("verdict") not in ("pass", "fail"):
            return {"ok": False, "error": "verdict must be pass/fail"}
        r["passed"][player["id"]] = data["verdict"]
        others = [p for p in _fz_players(room) if p != r["victim"]]
        if all(p in r["passed"] for p in others):
            passes = sum(1 for v in r["passed"].values() if v == "pass")
            share = round(passes / max(1, len(others)) * FZ_POOL)
            _fz_award(room, r["victim"], share * (2 if _fz_self_landed(room) else 1))
            st["phase"] = "author"
            st["deadline_at"] = _now() + 60
            _broadcast(room, "ritual.judged", {
                "victim": room["players"][r["victim"]]["name"],
                "passes": passes, "of": len(others)})
            _fz_bots_act(room, "author")
        return {"ok": True}
    if kind == "author":
        if st["phase"] != "author":
            return {"ok": False, "error": "not guessing now"}
        if player["id"] == r["victim"]:
            return {"ok": False, "error": "victim doesn't guess"}
        guess = str(data.get("player_id") or "")
        if guess not in _fz_players(room):
            return {"ok": False, "error": "bad guess"}
        if guess == player["id"]:
            return {"ok": False, "error": "no self-guess"}
        r["guesses"][player["id"]] = guess
        others = [p for p in _fz_players(room) if p != r["victim"]]
        if all(p in r["guesses"] for p in others):
            _fz_score_ritual(room)
        return {"ok": True}
    return {"ok": False, "error": "unknown input"}


def _fz_self_landed(room: dict) -> bool:
    """The dare landed on its own author: victim wrote the spotlight line."""
    st = room["mode_state"]
    return st["ritual"]["spotlight"] == st["ritual"]["victim"]


def _fz_score_ritual(room: dict):
    st = room["mode_state"]
    r = st["ritual"]
    spot = r["spotlight"]
    correct = sum(1 for g in r["guesses"].values() if g == spot)
    for voter, g in r["guesses"].items():
        if g == spot:
            _fz_award(room, voter, 10)
    if correct == 0 and spot:
        _fz_award(room, spot, 20)  # perfect crime: unrecognized x2 value
    elif spot:
        _fz_award(room, spot, 10)  # good material is performable
    st["phase"] = "scored"
    st["deadline_at"] = _now() + SCORED_HOLD
    _broadcast(room, "score.updated", {
        "round": st["round_id"],
        "spotlight_author": (room["players"][spot]["name"] if spot else None),
        "correct_guesses": correct,
        "scores": _public_players(room)})


def _fz_spin(room: dict):
    st = room["mode_state"]
    w = st["wheel"]
    players = _fz_players(room)
    if not players:
        return
    w["victim"] = min(players,
                       key=lambda p: (room["players"][p]["score"], p))
    avail = [s for s in w["segments"] if s not in w["burned"]]
    if not avail:
        w["burned"] = []
        avail = list(w["segments"])
    import random as _r
    w["segment"] = _r.choice(avail)
    w["burned"].append(w["segment"])
    w["verdicts"] = {}
    _broadcast(room, "wheel.spun", {
        "victim": room["players"][w["victim"]]["name"],
        "segment": w["segment"]})


def _fz_wheel_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    w = st["wheel"]
    if data.get("kind") != "verdict" or st["phase"] != "verdict":
        return {"ok": False, "error": "not judging now"}
    if data.get("verdict") not in ("served", "double"):
        return {"ok": False, "error": "verdict must be served/double"}
    w["verdicts"][player["id"]] = data["verdict"]
    if _fz_all_in(room, w["verdicts"]):
        _fz_score_wheel(room)
    return {"ok": True}


def _fz_score_wheel(room: dict):
    """Resolve wheel verdicts. Majority double (and doubles left) respins
    with stakes stacked; else served (+2 dignity) or doubled (-2)."""
    st = room["mode_state"]
    w = st["wheel"]
    doubles = sum(1 for v in w["verdicts"].values() if v == "double")
    if doubles > len(w["verdicts"]) / 2 and w["doubles"] < 2:
        w["doubles"] += 1
        _fz_spin(room)  # stakes stack: spin again, same victim
        _fz_bots_act(room, "verdict")
        return
    if doubles > len(w["verdicts"]) / 2:
        _fz_award(room, w["victim"], -2)
    else:
        _fz_award(room, w["victim"], 2)
    st["phase"] = "scored"
    st["deadline_at"] = _now() + SCORED_HOLD
    _broadcast(room, "score.updated", {
        "round": st["round_id"], "victim": room["players"][w["victim"]]["name"],
        "segment": w["segment"], "doubles": w["doubles"],
        "scores": _public_players(room)})


def _fz_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    phase = st["phase"]
    if phase == "collecting":
        if st["kind"] == "humiliation-ritual":
            others = [p for p in _fz_players(room)
                      if p != st["ritual"]["victim"]]
            if any(p in st["entries"] for p in others):
                texts = [(p, st["entries"][p]) for p in others
                         if p in st["entries"]]
                spot = max(texts, key=lambda t: len(t[1]))[0]
                st["ritual"]["spotlight"] = spot
                _fz_add_archive(room, spot, st["entries"][spot])
                st["phase"] = "passfail"
                st["deadline_at"] = _now() + 60
                _broadcast(room, "set.revealed", {
                    "mode": "freeze-night", "round": st["round_id"],
                    "victim": room["players"][st["ritual"]["victim"]]["name"],
                    "line": st["entries"][spot]})
                return
            _fz_next_round(room)  # nobody wrote: skip
            return
        if st["entries"]:
            _fz_reveal(room)
        else:
            _fz_next_round(room)
    elif phase in ("voting", "passfail", "author", "verdict"):
        if st["kind"] == "humiliation-ritual" and phase == "passfail":
            st["phase"] = "author"  # timeout: judge on votes cast (or none)
            st["deadline_at"] = _now() + 60
            _broadcast(room, "ritual.judged", {
                "victim": room["players"][st["ritual"]["victim"]]["name"],
                "passes": sum(1 for v in st["ritual"]["passed"].values()
                              if v == "pass"),
                "of": len(st["ritual"]["passed"])})
        elif st["kind"] == "humiliation-ritual" and phase == "author":
            _fz_score_ritual(room)
        elif st["kind"] == "wheel-of-shame":
            _fz_award(room, st["wheel"]["victim"], 2)
            st["phase"] = "scored"
            _broadcast(room, "score.updated", {
                "round": st["round_id"], "scores": _public_players(room)})
            _fz_next_round(room)
        else:
            if st["votes"]:
                _fz_score_prompt(room)
            else:
                st["phase"] = "scored"
            if st["phase"] == "scored":
                _fz_next_round(room)
    elif phase == "scored":
        _fz_next_round(room)
    else:
        _fz_next_round(room)


def _fz_finish(room: dict):
    st = room["mode_state"]
    st["phase"] = "done"
    st["night_done"] = True
    players = sorted(room["players"].values(),
                     key=lambda p: p["score"], reverse=True)
    champ = players[0] if players else None
    gag = None
    if st["archive"]:
        gag = max(st["archive"], key=lambda e: e["invokes"])
    st["winner"] = champ["freak"] if champ else None
    room["winner"] = st["winner"]
    room["phase"] = "done"
    if champ:
        for pid, p in room["players"].items():
            if p is champ:
                _record_win(room, pid)
                break
    _broadcast(room, "night.done", {
        "mode": "freeze-night",
        "champion": champ["name"] if champ else None,
        "running_gag": gag,
        "recognition": st["recognized"],
        "scores": _public_players(room),
        "ella": (f"ELLA: {champ['name']} takes the night. "
                 f"The rest of you were witnesses."
                 if champ else "ELLA: Nobody won. Correct.")})
    _save_rooms()
    if room.get("pack"):
        _pack_next(room)  # freeze-night inside a playlist hands on


# ── quip-clash (one engine, every prompt game) ───────────────────────────
# Prompt → entries → vote → score, with a twist per game:
# normal (most votes wins), inverted (fewest votes wins: least-funny),
# liar (entries carry a secret truth flag; votes name the lie).
# A game = a deck + a twist. Decks are content; the engine never changes.

QC_DECKS = {
    "endings": {
        "title": "FUNNIER ENDING", "twist": "normal",
        "blurb": "Scene freezes. Who ends it funniest?",
        "prompts": [
            "The argument peaks. The door slams. How does it end?",
            "Blackout mid-sentence. Lights up — what happened?",
            "The wedding stops. The priest faints. End it.",
            "The heist succeeds. The getaway driver is asleep. End it.",
        ]},
    "walkins": {
        "title": "WHO WALKS IN", "twist": "normal",
        "blurb": "The door opens. Who walks through it?",
        "prompts": [
            "A door opens mid-scene. Who walks in? (who + trait + want)",
            "The phone rings. Who is it and what do they want?",
            "A car pulls up outside. Who gets out?",
        ]},
    "objects": {
        "title": "POCKET OBJECT", "twist": "normal",
        "blurb": "A hand slides into a pocket. What comes out?",
        "prompts": [
            "He reaches into his pocket. What does he pull out?",
            "She opens the box. What's inside?",
            "The will is read. The surprise bequest is…?",
        ]},
    "least-funny": {
        "title": "LEAST FUNNY ANSWER", "twist": "inverted",
        "blurb": "Worst answer wins. Fewest votes takes it — wait, most? Play and see.",
        "prompts": [
            "What's the worst thing to hear during surgery?",
            "Write the least funny punchline to 'Why did the chicken cross the road?'",
            "The worst possible last words?",
            "What's the worst superpower?",
        ]},
    "wrong-answers": {
        "title": "WRONG ANSWERS ONLY", "twist": "inverted",
        "blurb": "Question on screen. Worst answer wins.",
        "prompts": [
            "What is the moon made of? (wrong answers only)",
            "How do fish sleep? (wrong answers only)",
            "Why is the sky blue? (wrong answers only)",
            "What do astronauts eat? (wrong answers only)",
        ]},
    "lies": {
        "title": "WOULD I LIE TO YOU", "twist": "liar",
        "blurb": "State a claim, secretly true or lie. Room names the lies.",
        "prompts": [
            "State something bizarre about yourself. Mark it TRUE or LIE (secret).",
            "Your claim: something nobody would believe. True or lie?",
        ]},
    "monologues": {
        "title": "INTERNAL MONOLOGUE", "twist": "normal",
        "blurb": "The voice in their head. Winner gets read aloud.",
        "prompts": [
            "His boss says 'we need to talk'. His internal monologue?",
            "She's smiling. Her internal monologue, nature-documentary style?",
            "The first date is going great. Their internal monologue?",
            "Caught in the rain with no umbrella. Internal monologue, noir narrator?",
        ]},
    "dubs": {
        "title": "DUB THE CLIP", "twist": "normal",
        "blurb": "The clip plays silent. You write the line.",
        "prompts": [
            "Security footage: a man stares at a microwave. His line?",
            "Nature doc: two owls stare at each other. The voiceover?",
            "Soap opera: she slaps him. His response?",
            "CCTV: a raccoon opens a bin at 3am. Narrate it.",
        ]},
    "eulogies": {
        "title": "EULOGY FOR A THING", "twist": "normal",
        "blurb": "Bury it beautifully. 60 seconds of grief.",
        "prompts": [
            "Eulogize: the office microwave (1998–2026).",
            "Eulogize: his last good pen.",
            "Eulogize: the group chat, dead since Tuesday.",
        ]},
    "lyrics": {
        "title": "FINISH THE LYRIC", "twist": "normal",
        "blurb": "Two bars dealt. Complete the curse.",
        "prompts": [
            "Complete the shanty: 'Oh the HR department called me down… shit, forgot the next line, it was about…'",
            "Power ballad for a parking warden. First line: 'You ticketed my heart on Tuesday…' Finish it.",
            "The divorce certificate jingle. Go.",
        ]},
    "nonsense": {
        "title": "COURT OF NONSENSE", "twist": "normal",
        "blurb": "Maximum nonsense density. The room is the judge (auto-rater later).",
        "prompts": [
            "Defend soup in 3 sentences. None may make sense.",
            "Explain taxes using only breakfast. Go.",
            "Your closing argument: the moon is biased. Prove it badly.",
        ]},
}

QC_BOT_LINES = [
    "the landlord walked in and pretended this was normal",
    "blackout. one microwave beep. applause.",
    "it was all a rehearsal. the real one is tuesday.",
    "a pigeon landed on the punchline and stayed",
    "they agreed to never speak of the soup again",
    "exit pursued by applause",
]


def _qc_create(room: dict):
    room["mode_state"] = {
        "round": 0, "deck": None, "prompt": None, "twist": "normal",
        "entries": {}, "secrets": {}, "votes": {}, "caught": {},
        "phase": "idle", "reveal": False, "deadline_at": None,
        "archive": [], "history": [],
    }


def _qc_start_round(room: dict, deck_id: str = ""):
    import random as _r
    st = room["mode_state"]
    if deck_id not in QC_DECKS:
        deck_id = st.get("deck") or "endings"
    deck = QC_DECKS[deck_id]
    st["deck"] = deck_id
    st["twist"] = deck["twist"]
    st["round"] = st.get("round", 0) + 1
    used = st.setdefault("used", [])
    st["prompt"] = _r.choice([q for q in deck["prompts"] if q not in used]
                             or deck["prompts"])
    used.append(st["prompt"])
    st["entries"] = {}
    st["secrets"] = {}
    st["votes"] = {}
    st["caught"] = {}
    st["results"] = []
    st["round_winner"] = None
    st["phase"] = "collecting"
    st["reveal"] = False
    st["deadline_at"] = _now() + 90
    _broadcast(room, "round.started", {
        "mode": room["mode"], "deck": deck_id, "round": st["round"],
        "prompt": st["prompt"], "twist": st["twist"],
        "deadline_at": st["deadline_at"]})
    _qc_bots_act(room, "collect")


def _qc_order(room: dict) -> list:
    """Seat order. Stable within a game: a player who leaves keeps their
    index (they are flagged `left`), so option ids never shift mid-vote."""
    return list(room["players"].keys())


def _qc_option_ids(room: dict) -> list:
    return [o["i"] for o in _qc_assembled(room)]


def _qc_check_complete(room: dict):
    st = room["mode_state"]
    act = _active(room)
    if not act:
        return
    if st["phase"] == "collecting":
        if st["entries"] and all(p in st["entries"] for p in act):
            _qc_reveal(room)
    elif st["phase"] == "voting":
        order = _qc_order(room)
        ids = _qc_option_ids(room)
        need = [p for p in act if st["twist"] == "liar"
                or any(order[i] != p for i in ids)]
        if st["votes"] and all(p in st["votes"] for p in need):
            _qc_score(room)


def _qc_assembled(room: dict) -> list:
    st = room["mode_state"]
    return [{"i": i, "text": st["entries"][pid]}
            for i, pid in enumerate(_qc_order(room)) if pid in st["entries"]]


def _qc_archive(room: dict, pid: str, text: str):
    st = room["mode_state"]
    st["archive"].append({"id": f"q{len(st['archive']) + 1}",
                          "round": st["round"], "by": room["players"][pid]["name"],
                          "text": text, "invokes": 0})


def _qc_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    kind = data.get("kind")
    if kind == "caught":
        ev = str(data.get("event") or "")
        if any(e["id"] == ev for e in st["archive"]):
            st["caught"][player["id"]] = ev
            _broadcast(room, "caught.that", {"by": player["name"], "event": ev})
            return {"ok": True}
        return {"ok": False, "error": "unknown event"}
    if kind == "entry":
        if st["phase"] != "collecting":
            return {"ok": False, "error": "not collecting now"}
        text = _clean(data.get("text", ""), MAX_TEXT)
        if not text:
            return {"ok": False, "error": "empty entry"}
        st["entries"][player["id"]] = text
        if st["twist"] == "liar":
            # secret truth flag: never leaves the server until scoring
            st["secrets"][player["id"]] = bool(data.get("truth", False))
        _broadcast(room, "entry.accepted", {"by": player["name"],
                                            "count": len(st["entries"]),
                                            "needed": len(_active(room))})
        _qc_check_complete(room)
        return {"ok": True}
    if kind == "vote":
        if st["phase"] != "voting":
            return {"ok": False, "error": "not voting now"}
        try:
            choice = int(data.get("choice"))
        except Exception:
            return {"ok": False, "error": "bad choice"}
        # option ids are seat-order indexes; a seat that wrote nothing has
        # no option, so its index is not votable
        if choice not in _qc_option_ids(room):
            return {"ok": False, "error": "bad choice"}
        if _qc_order(room)[choice] == player["id"] and st["twist"] != "liar":
            return {"ok": False, "error": "no self-votes"}
        st["votes"][player["id"]] = [choice]
        _broadcast(room, "vote.accepted", {"by": player["name"],
                                           "count": len(st["votes"])})
        _qc_check_complete(room)
        return {"ok": True}
    return {"ok": False, "error": "unknown input"}


def _qc_reveal(room: dict):
    st = room["mode_state"]
    st["phase"] = "voting"
    st["reveal"] = True
    st["deadline_at"] = _now() + 60
    for pid, text in list(st["entries"].items()):
        _qc_archive(room, pid, text)
    _broadcast(room, "set.revealed", {"mode": room["mode"],
                                      "round": st["round"],
                                      "options": _qc_assembled(room),
                                      "liar": st["twist"] == "liar",
                                      "deadline_at": st["deadline_at"]})
    _qc_bots_act(room, "vote")


def _qc_score(room: dict):
    """normal: vote-% of 100 + sweep. inverted: fewest votes wins.
    liar: votes name the lie; liars paid per fooled voter, spotters per catch."""
    st = room["mode_state"]
    before = {pid: p["score"] for pid, p in room["players"].items()}
    tally: dict = {}
    total = 0
    for voter, choices in st["votes"].items():
        for c in choices:
            tally[str(c)] = tally.get(str(c), 0) + 1
            total += 1
    winner_name, detail = None, {"tally": tally}
    order = _qc_order(room)
    if tally and total:
        if st["twist"] == "inverted":
            # fewest votes wins; ties split (lowest shared count). An answer
            # nobody voted for has 0 votes and is the least-voted of all.
            for i in _qc_option_ids(room):
                tally.setdefault(str(i), 0)
            low = min(tally.values())
            winners = [c for c, v in tally.items() if v == low]
            win = winners[0]
            for w in winners:
                pid = order[int(w)]
                room["players"][pid]["score"] += round(FZ_POOL / len(winners))
            winner_name = room["players"][order[int(win)]]["name"]
            detail["inverted"] = True
        elif st["twist"] == "liar":
            # every vote names a suspected lie
            for voter, choices in st["votes"].items():
                for c in choices:
                    pid = order[int(c)]
                    if st["secrets"].get(pid) is False:
                        room["players"][pid]["score"] += 15  # fooled them
                        room["players"][voter]["score"] += 0
                    else:
                        room["players"][voter]["score"] += 10  # caught one
            st["secrets_revealed"] = dict(st["secrets"])
            winner_name = "the truth"
            tops = sorted(tally, key=tally.get, reverse=True)
            detail["most_suspect"] = tops[0] if tops else None
        else:
            win = max(tally, key=tally.get)
            share = FZ_POOL + FZ_SWEEP if (
                tally[win] == total and total >= 2 and len(_qc_assembled(room)) > 1
            ) else round(tally[win] / total * FZ_POOL)
            pid = order[int(win)]
            room["players"][pid]["score"] += share
            _record_win(room, pid)
            winner_name = room["players"][pid]["name"]
    after = {pid: room["players"][pid]["score"] for pid in room["players"]}
    st["results"] = sorted((
        {"text": o["text"], "by": room["players"][order[o["i"]]]["name"],
         "votes": tally.get(str(o["i"]), 0),
         "points": after[order[o["i"]]] - before.get(order[o["i"]], 0)}
        for o in _qc_assembled(room)), key=lambda r: -r["votes"])
    st["round_winner"] = winner_name
    st["phase"] = "scored"
    st["deadline_at"] = _now() + SCORED_HOLD
    _broadcast(room, "score.updated", {"round": st["round"], "winner": winner_name,
                                       "scores": _public_players(room), **detail})


def _qc_next(room: dict):
    st = room["mode_state"]
    if _pack_quota_met(room):
        _pack_next(room)
        return
    if _rounds_done(room):
        _finish_game(room)
        return
    _qc_start_round(room, st.get("deck") or "")


def _qc_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "collecting":
        if st["entries"]:
            _qc_reveal(room)
        elif reason == "host":
            # host skipped a prompt nobody answered: new prompt, same round
            st["round"] -= 1
            _qc_start_round(room, st.get("deck") or "")
        else:
            _qc_next(room)  # timer ran out with nobody writing (counts a round)
    elif st["phase"] == "voting":
        if st["votes"]:
            _qc_score(room)
        else:
            st["phase"] = "scored"
            st["results"] = []
            _qc_next(room)
    else:
        _qc_next(room)


def _qc_bots_act(room: dict, stage: str):
    """Deck bots: entries from the bot lines, votes random non-self
    (liar: random suspect). Synchronous — bots never stall."""
    st = room["mode_state"]
    if room.get("mode_state") is None or st.get("phase") == "scored":
        return
    import random as _r
    rng = _r.Random(hash(room["code"]) % (2 ** 31) + st.get("round", 0))
    bots = [pid for pid in _active(room) if room["players"][pid].get("bot")]
    if not bots:
        return
    if stage == "collect" and st["phase"] == "collecting":
        for pid in bots:
            if pid not in st["entries"]:
                used = set(st["entries"].values())
                avail = [l for l in QC_BOT_LINES if l not in used] or QC_BOT_LINES
                st["entries"][pid] = rng.choice(avail)
                if st["twist"] == "liar":
                    st["secrets"][pid] = rng.choice([True, False])
        _qc_check_complete(room)
    elif stage == "vote" and st["phase"] == "voting":
        ids = _qc_option_ids(room)
        order = _qc_order(room)
        for pid in bots:
            if pid in st["votes"]:
                continue
            if st["twist"] == "liar":
                mine = list(ids)
            else:
                mine = [i for i in ids if order[i] != pid]
            if mine:
                st["votes"][pid] = [rng.choice(mine)]
        _qc_check_complete(room)


def _ella_callback(room: dict) -> str | None:
    """Ella narrates the lore: rivalries get called out on stage.
    Rookies get silence — callbacks are earned, not given."""
    for line in room.get("lore") or []:
        if line.startswith("rivalry:"):
            return f"ELLA: {line}. Settle it on stage."
    return None


def _rounds_done(room: dict) -> bool:
    """Standalone game length reached (packs use _pack_quota_met)."""
    if room.get("pack"):
        return False
    total = room.get("rounds") or 0
    st = room.get("mode_state") or {}
    return bool(total) and st.get("round", 0) >= total


def _default_rounds(room: dict, mode: str) -> int:
    if mode == "freaktionary":
        return max(2, len(_active(room)))  # everyone draws once
    if mode == "freeze-night":
        return 0  # fixed playlist (FZ_ROUNDS), ends itself
    if mode.startswith("quip-"):
        return DEFAULT_ROUNDS["quip"]
    return DEFAULT_ROUNDS.get(mode, 3)


def _final_result(room: dict, players: list) -> dict:
    """Crown honestly: one clear leader wins; a shared top score is a tie;
    nobody above zero means nobody scored. Never a fake winner."""
    ranked = sorted(players, key=lambda p: p["score"], reverse=True)
    top = ranked[0]["score"] if ranked else 0
    leaders = [p for p in ranked if p["score"] == top] if ranked else []
    if not ranked or top <= 0:
        kind, names, headline = "none", [], "NOBODY SCORED"
    elif len(leaders) > 1:
        kind = "tie"
        names = [p["name"] for p in leaders]
        headline = "IT'S A TIE: " + " & ".join(names)
    else:
        kind, names = "win", [leaders[0]["name"]]
        headline = f"{leaders[0]['name']} WINS!"
    res = {"kind": kind, "names": names, "headline": headline, "top": top,
           "scores": [{"name": p["name"], "score": p["score"]} for p in ranked]}
    room["result"] = res
    room["winner"] = leaders[0]["freak"] if kind == "win" else None
    room["winner_pid"] = leaders[0]["id"] if kind == "win" else None
    return res


def _finish_game(room: dict, reason: str = "rounds"):
    """Crown the winner of a standalone game. Room stays open: the host can
    start again (scores reset) or send everyone back to the lobby."""
    st = room.get("mode_state") or {}
    st["phase"] = "done"
    st["deadline_at"] = None
    room["phase"] = "done"
    res = _final_result(room, [room["players"][p] for p in _active(room)])
    champ = res["names"][0] if res["kind"] == "win" else None
    line = (f"ELLA: {champ} takes it. The rest of you were witnesses."
            if res["kind"] == "win" else
            "ELLA: A tie. Nobody won. Correct." if res["kind"] == "tie" else
            "ELLA: Nobody scored. Correct.")
    _broadcast(room, "game.done", {
        "mode": room.get("mode"), "reason": reason,
        "champion": champ, "tie": res["kind"] == "tie",
        "result": res,
        "winner": room["winner"], "scores": _public_players(room),
        "ella": line})


def _pack_quota_met(room: dict) -> bool:
    pack = room.get("pack")
    if not pack:
        return False
    st = room.get("mode_state") or {}
    return st.get("round", 0) >= pack.get("rounds_each", 2)


def _start_mode(room: dict, mode: str, target: str = "", deck: str = ""):
    room["mode"] = mode
    room["phase"] = "playing"
    MODES[mode]["create"](room)
    if mode == "freaktionary":
        _mq_start_round(room)
    elif mode == "freeze-night":
        _fz_next_round(room)
    elif mode.startswith("quip-"):
        _qc_start_round(room, deck or MODES[mode].get("deck", "endings"))
    else:
        _rr_start_round(room, target)


def _pack_next(room: dict):
    """Advance the playlist: next mode, or crown the night's winner."""
    pack = room.get("pack") or {}
    pack["idx"] = pack.get("idx", 0) + 1
    modes = pack.get("modes", [])
    if pack["idx"] >= len(modes):
        room["phase"] = "done"
        _final_result(room, [p for p in room["players"].values()
                             if not p.get("left")])
        line = (f"ELLA: {room['winner']} takes the night. "
                f"The rest of you were witnesses."
                if room["winner"] else "ELLA: Nobody won. Correct.")
        if room.get("mode_state"):
            room["mode_state"]["phase"] = "done"
            room["mode_state"]["deadline_at"] = None
        _broadcast(room, "pack.done",
                   {"pack": pack.get("name"), "winner": room["winner"],
                    "scores": _public_players(room), "ella": line})
        return
    mode = modes[pack["idx"]]
    _start_mode(room, mode)
    _broadcast(room, "mode.changed",
               {"pack": pack.get("name"), "mode": mode,
                "idx": pack["idx"], "of": len(modes)})


MODES = {
    "freaktionary": {"title": "FREAKTIONARY", "min": 2, "max": 8,
                     "blurb": "Draw the word, room guesses. Solo: bots guess + draw.",
                     "create": _mq_create, "input": _mq_input,
                     "advance": _mq_advance},
    "roast-relay": {"title": "ROAST RELAY", "min": 3, "max": 8,
                    "blurb": "Everyone roasts the target, room votes.",
                    "create": _rr_create, "input": _rr_input,
                    "advance": _rr_advance},
    "freeze-night": {"title": "FREEZE NIGHT", "min": 3, "max": 8,
                     "blurb": "Improv night: endings, walk-ins, ritual, wheel, final.",
                     "create": _fz_create, "input": _fz_input,
                     "advance": _fz_advance},
}

PACKS = {
    "FREAK NIGHT": ["freaktionary", "roast-relay", "freaktionary"],
    "QUICK FIRE": ["roast-relay"],
}

# One engine, one mode key per deck: dash cards + host buttons address
# games; all of them run _qc_* with a different deck + twist.
for _deck_id, _deck in QC_DECKS.items():
    _key = f"quip-{_deck_id}"
    if _key not in MODES:
        MODES[_key] = {
            "title": _deck["title"], "min": 2, "max": 8,
            "blurb": _deck["blurb"] + " Solo: bots play.",
            "deck": _deck_id,
            "create": _qc_create, "input": _qc_input,
            "advance": _qc_advance,
        }


# ── views (per-role; secrets only here, never on the stream) ─────────

MQ_RULES = "Guess it: +2 · the drawer gets +1 when someone does"


def _qc_rules(twist: str) -> str:
    if twist == "inverted":
        return f"Fewest votes wins the round: +{FZ_POOL}"
    if twist == "liar":
        return "Vote for the LIE · fool a voter +15 · catch a liar +10"
    return (f"Most votes wins the round: up to +{FZ_POOL} (your share of "
            f"the votes), +{FZ_SWEEP} bonus if everyone picks you")


def _phase_key(room: dict) -> str:
    """Identifies the screen the host is looking at, so a stale ADVANCE
    (sent just as the timer moved the room on) is ignored, not applied
    to the next round."""
    st = room.get("mode_state") or {}
    return (f"{room.get('phase')}:{room.get('mode')}:"
            f"{st.get('round_id') or st.get('round')}:{st.get('phase')}")


def _result_components(room: dict, player: dict | None) -> list:
    res = room.get("result") or {}
    comps = [{"type": "text", "text": "GAME OVER"},
             {"type": "banner", "text": ("🏆 " if res.get("kind") == "win" else "")
              + (res.get("headline") or "Game over")}]
    medals = ["🥇", "🥈", "🥉"]
    levels = sorted({r["score"] for r in res.get("scores") or []}, reverse=True)
    for r in res.get("scores") or []:
        rank = levels.index(r["score"])  # equal scores share a medal
        comps.append({"type": "text", "text":
                      f"{medals[rank] if rank < 3 and r['score'] > 0 else '·'} "
                      f"{r['name']}: {r['score']}"})
    if player:
        comps.append({"type": "text", "text": f"You scored {player['score']}."})
    comps.append({"type": "text",
                  "text": "Host can PLAY AGAIN or go BACK TO LOBBY on the big screen."})
    return comps

def _already_sent(room: dict, player: dict) -> str:
    """Waiting text when this phone already acted in the current phase."""
    mode = str(room.get("mode") or "")
    st = room.get("mode_state") or {}
    pid, ph = player["id"], st.get("phase")
    act = _active(room)
    if mode == "roast-relay":
        if ph == "collecting" and pid in st["lines"]:
            return f"Sent. Waiting for the others ({len(st['lines'])}/{len(act)})."
        if ph == "voting" and pid in st["votes"]:
            return f"Voted. Waiting for the others ({len(st['votes'])}/{len(act)})."
    elif mode.startswith("quip-"):
        if ph == "collecting" and pid in st["entries"]:
            return f"Sent. Waiting for the others ({len(st['entries'])}/{len(act)})."
        if ph == "voting" and pid in st["votes"]:
            return f"Voted. Waiting for the others ({len(st['votes'])}/{len(act)})."
    elif mode == "freeze-night":
        n = sum(1 for k in st.get("entries", {}) if not k.endswith(":cb"))
        if ph == "collecting" and pid in st["entries"]:
            return f"Sent. Waiting for the others ({n}/{len(act)})."
        if ph == "voting" and pid in st["votes"]:
            return f"Voted. Waiting for the others ({len(st['votes'])}/{len(act)})."
        if ph == "passfail" and pid in st["ritual"]["passed"]:
            return "Verdict in. Waiting for the room."
        if ph == "author" and pid in st["ritual"]["guesses"]:
            return "Guess in. Waiting for the room."
        if ph == "verdict" and pid in st["wheel"]["verdicts"]:
            return "Verdict in. Waiting for the room."
    return ""


def _controller_view(room: dict, player: dict | None) -> dict:
    """playerView: what ONE phone displays. Server-driven screens."""
    base = {"room": room["code"], "phase": room["phase"],
            "seq": room["seq"], "players": _public_players(room),
            "locked": room["locked"]}
    if room["phase"] == "lobby":
        base["screen"] = "lobby"
        is_ready = bool(player and player["ready"])
        base["components"] = [
            {"type": "text", "text": ("You're in. Waiting for the host to start."
                                      if is_ready else
                                      "Waiting for host to lock + start.")},
            {"type": "text", "text": f"{len(room['players'])} seated: " +
             ", ".join(p["name"] for p in room["players"].values())}] + (
            [] if is_ready else
            [{"type": "button", "id": "ready", "label": "I'M READY"}])
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
    base["you"] = {"id": player["id"], "name": player["name"],
                   "score": player["score"], "left": bool(player.get("left"))}
    if room["phase"] == "done" or st.get("phase") == "done":
        base["screen"] = "scores"
        if room.get("result"):
            base["components"] = _result_components(room, player)
            return base
        champ = base.get("champion")
        base["components"] = [
            {"type": "text", "text": "GAME OVER"},
            {"type": "banner", "text": (f"🏆 {champ} WINS!" if champ
                                        else "Nobody won")},
            {"type": "text", "text": f"You scored {player['score']}."},
            {"type": "text", "text": "Host can play again or go back to the lobby."}]
        return base
    if player.get("left"):
        base["screen"] = "wait"
        base["components"] = [
            {"type": "text", "text": "You left this game."},
            {"type": "button", "id": "rejoin", "label": "REJOIN"}]
        return base
    sent = _already_sent(room, player)
    if sent:
        base["screen"] = "wait"
        base["components"] = [{"type": "text", "text": sent}]
        return base
    if room["mode"] == "freaktionary":
        drawer_name = (room["players"][st["drawer"]]["name"]
                       if st.get("drawer") in room["players"] else "?")
        if st["drawer"] == player["id"] and st["phase"] == "drawing":
            base["screen"] = "drawer"
            base["secret"] = st["word"]  # ONLY the drawer gets this
            base["components"] = [
                {"type": "text", "text": f"Draw: {st['word']}"},
                {"type": "canvas", "id": "draw"},
                {"type": "button", "id": "clear", "label": "CLEAR"},
                {"type": "text", "text": "No letters or words. The room is guessing."},
                {"type": "text", "text": MQ_RULES}]
        elif st["phase"] == "drawing":
            base["screen"] = "guess"
            base["components"] = [
                {"type": "text", "text": f"{drawer_name} is drawing. Guess the word!"},
                {"type": "canvas", "id": "watch", "readonly": True},
                {"type": "textarea", "id": "guess", "max_length": 60},
                {"type": "submit", "label": "GUESS", "kind": "guess"},
                {"type": "text", "text": MQ_RULES}]
        else:
            winner = (room["players"][st["winner"]]["name"]
                      if st.get("winner") in room["players"] else None)
            base["screen"] = "reveal"
            base["components"] = [
                {"type": "text",
                 "text": f"Word was: {st.get('word') or '?'}"},
                {"type": "text",
                 "text": ("Guessed by: " + winner + f" (+2, {drawer_name} +1)")
                 if winner else "Guessed by: nobody (no points)"},
                {"type": "canvas", "id": "watch", "readonly": True},
                {"type": "text", "text": "Next round starts in a few seconds."}]
        return base
    if room["mode"] == "roast-relay":
        if st["phase"] == "collecting":
            base["screen"] = "prompt"
            base["components"] = [
                {"type": "text", "text": f"Target: {st['target']}"},
                {"type": "textarea", "id": "line", "max_length": MAX_TEXT},
                {"type": "submit", "label": "SEND IT", "kind": "line"}]
        elif st["phase"] == "voting":
            clips = _rr_assembled(room)
            base["screen"] = "vote"
            # hide authorship until scored (deception-safe reveal)
            base["components"] = [
                {"type": "text", "text": f"Best roast of {st['target']}?"},
                {"type": "choice", "id": "winner",
                 "options": [{"id": str(c["i"]), "text": c["text"]}
                             for c in clips
                             if st["order"][c["i"]] != player["id"]]}]
        else:
            base["screen"] = "scores"
            base["components"] = [
                {"type": "text", "text": "Scores below. Host advances."}]
        return base
    if room["mode"] == "freeze-night":
        base.update(_fz_controller(room, player))
        return base
    if str(room["mode"] or "").startswith("quip-"):
        st = room["mode_state"]
        if st["phase"] == "collecting":
            comps = [
                {"type": "text", "text": st["prompt"] or ""},
                {"type": "textarea", "id": "entry", "max_length": MAX_TEXT},
            ]
            comps.append({"type": "text", "text": _qc_rules(st.get("twist"))})
            if st.get("twist") == "liar":
                comps.append({"type": "toggle", "id": "truth",
                              "label": "TRUE (unticked = LIE)"})
            comps.append({"type": "submit", "label": "SEND IT", "kind": "entry"})
            base["screen"] = "prompt"
            base["components"] = comps
        elif st["phase"] == "voting":
            opts = _qc_assembled(room)
            base["screen"] = "vote"
            base["components"] = [
                {"type": "text", "text": ("Who is LYING?" if st.get("twist") == "liar"
                                         else (st.get("prompt") or ""))},
                {"type": "choice", "id": "winner",
                 "action": {"kind": "vote", "as": "choice"},
                 "options": [{"id": str(c["i"]), "text": c["text"]} for c in opts
                             if st.get("twist") == "liar"
                             or _qc_order(room)[c["i"]] != player["id"]]},
                {"type": "text", "text": _qc_rules(st.get("twist"))}]
            if st.get("twist") != "liar" and player["id"] in st["entries"]:
                base["components"].insert(2, {"type": "text", "text":
                                              "(Your own answer isn't on your ballot.)"})
        else:
            base["screen"] = "scores"
            comps = [{"type": "text", "text": f"Round {st.get('round')} results"}]
            for r in st.get("results") or []:
                comps.append({"type": "text", "text":
                              f"“{r['text']}” — {r['by']}: {r['votes']} vote"
                              f"{'' if r['votes'] == 1 else 's'}"
                              + (f" (+{r['points']})" if r["points"] else "")})
            comps.append({"type": "text", "text": "You have "
                          f"{player['score']} points. Next round in a few seconds."})
            base["components"] = comps
        return base
    base["screen"] = "wait"
    base["components"] = [{"type": "text", "text": "Waiting…"}]
    return base


def _fz_controller(room: dict, player: dict) -> dict:
    """Phone screens for freeze-night. Prompts, ballots, teleprompter."""
    st = room["mode_state"]
    out: dict = {"screen": "wait", "components": []}
    if st["phase"] == "done":
        out["screen"] = "scores"
        out["components"] = [
            {"type": "text", "text": "Night over. Champion crowned."}]
        return out
    kind = st["kind"]
    if st["phase"] == "collecting":
        if kind == "humiliation-ritual" and player["id"] == st["ritual"]["victim"]:
            out["screen"] = "wait"
            out["components"] = [{"type": "text",
                                  "text": "Lines are being written about you. Stay calm."}]
        else:
            out["screen"] = "prompt"
            limit = 180
            for spec in FZ_ROUNDS:
                if spec["id"] == st["round_id"]:
                    limit = spec["limit"] or 180
            out["components"] = [
                {"type": "text", "text": st["prompt"] or ""},
                {"type": "textarea", "id": "entry", "max_length": limit},
                {"type": "submit", "label": "SEND IT",
                 "kind": "rite" if kind == "humiliation-ritual" else "entry"}]
        return out
    if st["phase"] == "voting":
        opts = _fz_assembled(room)
        lash = st["kind"] == "last-lash"
        out["screen"] = "vote"
        out["components"] = [
            {"type": "text", "text": ("Stack up to 3 votes (yourself allowed)."
                                      if lash else "Vote the funniest.")},
            {"type": "choice", "id": "winner",
             "action": {"kind": "vote", "as": "choice",
                       "multi": 3 if lash else 1},
             "options": [{"id": str(c["i"]), "text": c["text"]} for c in opts
                         if lash or st["order"][c["i"]] != player["id"]]}]
        return out
    if st["phase"] == "passfail":
        spot = st["ritual"]["spotlight"]
        line = st["entries"].get(spot, "") if spot else ""
        if player["id"] == st["ritual"]["victim"]:
            out["screen"] = "perform"
            out["components"] = [
                {"type": "text", "text": "PERFORM THIS. The room judges you now."},
                {"type": "text", "text": f"“{line}”"}]
        else:
            out["screen"] = "vote"
            out["components"] = [
                {"type": "text", "text": "Did they commit?"},
                {"type": "choice", "id": "verdict",
                 "action": {"kind": "pass", "as": "verdict"},
                 "options": [{"id": "pass", "text": "PASS"},
                             {"id": "fail", "text": "FAIL"}]}]
        return out
    if st["phase"] == "author":
        if player["id"] == st["ritual"]["victim"]:
            out["screen"] = "wait"
            out["components"] = [{"type": "text", "text": "Who wrote it? Not your call."}]
        else:
            others = [p for p in _fz_players(room) if p != player["id"]
                      and p != st["ritual"]["victim"]]
            out["screen"] = "vote"
            out["components"] = [
                {"type": "text", "text": "Who wrote the spotlight line?"},
                {"type": "choice", "id": "author",
                 "action": {"kind": "author", "as": "player_id"},
                 "options": [{"id": p, "text": room["players"][p]["name"]}
                             for p in others]}]
        return out
    if st["phase"] == "verdict":
        out["screen"] = "vote"
        out["components"] = [
            {"type": "text",
             "text": f"Punishment: {st['wheel']['segment']}"},
            {"type": "choice", "id": "verdict",
             "action": {"kind": "verdict", "as": "verdict"},
             "options": [{"id": "served", "text": "SERVED"},
                         {"id": "double", "text": "DOUBLE IT"}]}]
        return out
    out["screen"] = "scores"
    out["components"] = [{"type": "text", "text": "Scores below. Host advances."}]
    return out


def _stage_public(room: dict) -> dict:
    """publicView: everything the big screen may show. No secrets."""
    out = {"mode": room["mode"], "room_phase": room["phase"],
           "scores": _public_players(room),
           "title": MODES[room["mode"]]["title"] if room.get("mode") in MODES else None,
           "rounds": room.get("rounds"), "winner": room.get("winner"),
           "pack": ({"name": room["pack"].get("name"),
                     "idx": room["pack"].get("idx", 0),
                     "of": len(room["pack"].get("modes", []))}
                    if room.get("pack") else None)}
    out["phase_key"] = _phase_key(room)
    if room.get("result"):
        out["result"] = room["result"]
    if room.get("winner_pid") in room["players"]:
        out["champion"] = room["players"][room["winner_pid"]]["name"]
    elif room.get("winner"):
        out["champion"] = next((p["name"] for p in room["players"].values()
                                if p["freak"] == room["winner"]), None)
    if room.get("lore"):
        out["lore"] = room["lore"]
    if room["phase"] == "lobby":
        out["lobby"] = {"code": room["code"], "count": len(room["players"])}
        return out
    st = room["mode_state"]
    if room["mode"] == "freaktionary":
        out["freaktionary"] = {
            "round": st["round"], "phase": st.get("phase"),
            "drawer": (room["players"][st["drawer"]]["name"]
                       if st.get("drawer") in room["players"] else None),
            "strokes": [{"id": x.get("id"), "points": x["points"]}
                        for x in st["strokes"]],
            "rev": f"{st['round']}:{st.get('clears', 0)}:{st.get('points', 0)}",
            "rules": MQ_RULES,
            "guesses": st["guesses"][-10:],
            "revealed": st.get("revealed"),
            "word": st["word"] if st.get("revealed") else None,
            "winner": (room["players"][st["winner"]]["name"]
                       if st.get("winner") in room["players"] else None),
            "deadline_at": st.get("deadline_at")}
    elif room["mode"] == "roast-relay":
        out["roast-relay"] = {
            "target": st["target"], "phase": st["phase"],
            "clips": _rr_assembled(room) if st["phase"] != "collecting" else [],
            "round": st.get("round"),
            "submitted": len(st["lines"]), "needed": len(_active(room)),
            "audio": st.get("audio"), "audio_status": st.get("audio_status"),
            "deadline_at": st.get("deadline_at")}
    elif str(room["mode"] or "").startswith("quip-"):
        out["quip"] = {
            "deck": st.get("deck"), "round": st.get("round"),
            "twist": st.get("twist"), "phase": st["phase"],
            "prompt": st.get("prompt"),
            "options": _qc_assembled(room) if st.get("reveal") else [],
            "results": st.get("results") if st["phase"] == "scored" else [],
            "round_winner": st.get("round_winner") if st["phase"] == "scored" else None,
            "rules": _qc_rules(st.get("twist")),
            "submitted": len(st["entries"]), "needed": len(_active(room)),
            "secrets": ({room["players"][pid]["name"]: v
                         for pid, v in (st.get("secrets_revealed") or {}).items()
                         if pid in room["players"]}
                        if st["phase"] == "scored" else None),
            "deadline_at": st.get("deadline_at")}
    elif room["mode"] == "freeze-night":
        out["freeze-night"] = {
            "round": st["round_id"], "kind": st["kind"], "phase": st["phase"],
            "prompt": st.get("prompt"),
            "options": _fz_assembled(room) if st.get("reveal") else [],
            "submitted": sum(1 for k in st["entries"] if not k.endswith(":cb")),
            "needed": len(_active(room)),
            "archive": len(st["archive"]),
            "recognized": st["recognized"],
            "ritual_victim": (room["players"][st["ritual"]["victim"]]["name"]
                              if st["ritual"]["victim"] else None),
            "ritual_line": (st["entries"].get(st["ritual"]["spotlight"], "")
                            if st.get("reveal") or st["phase"] in
                            ("passfail", "author", "scored") else None),
            "wheel": {"victim": (room["players"][st["wheel"]["victim"]]["name"]
                                 if st["wheel"]["victim"] else None),
                      "segment": st["wheel"]["segment"],
                      "burned": len(st["wheel"]["burned"])},
            "deadline_at": st.get("deadline_at")}
    return out


# ── routes ──────────────────────────────────────────────────────────

@party_bp.route("/play", methods=["GET"])
def play_home():
    cards = "".join(
        f"<div style='border:1px solid #333;border-radius:12px;padding:16px;margin:10px auto;max-width:520px'>"
        f"<div style='font-size:18px'>{m['title']}</div>"
        f"<div style='color:#888;font-size:13px'>{m.get('blurb','')} · {m['min']}-{m['max']} players</div>"
        f"<p><button data-mode='{mode}' onclick=\"mk(this.dataset.mode)\""
        f" style='font-size:16px;padding:10px 24px'>CREATE + HOST</button></p></div>"
        for mode, m in MODES.items())
    return ("<!DOCTYPE html><html><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Freak Town Party</title></head><body style='background:#0a0a0f;"
            "color:#eee;font-family:monospace;text-align:center;padding:32px 16px'>"
            "<div style='color:#ff2fa8;letter-spacing:2px'>FREAK TOWN PARTY</div>"
            "<h1>GAME MODES</h1>"
            "<p style='color:#888'>Create a room, share the code, phones join. "
            "Add bots to play solo vs agents.</p>"
            + cards +
            "<script>"
            "async function mk(mode){"
            " const r = await fetch('/party/create',{method:'POST'}).then(r=>r.json());"
            " try{localStorage.setItem('ft_host_'+r.code,r.host_token);}catch(e){}"
            " location='/party/'+r.code+'/stage?mode='+encodeURIComponent(mode);"
            "}</script></body></html>")


ROOM_TTL = 24 * 3600  # idle rooms are dropped from RAM + snapshot


def _prune_rooms():
    cutoff = _now() - ROOM_TTL
    for code in [c for c, r in ROOMS.items()
                 if (r["events"][-1]["t"] if r.get("events")
                     else r.get("created_at", 0)) < cutoff]:
        ROOMS.pop(code, None)


@party_bp.route("/party/create", methods=["POST"])
def create_room():
    with LOCK:
        _prune_rooms()
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
    code = re.sub(r"[^A-Z0-9]", "", (code or "").upper())[:8]
    return JOIN_TEMPLATE.replace("__CODE__", code)


@party_bp.route("/party/<code>/join", methods=["POST"])
def join_room(code):
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = _body()
    # idempotent rejoin: same seat token gets its player back (reconnect),
    # including a player who left mid-game
    tok = str(data.get("seat_token") or "")
    with LOCK:
        if tok:
            p = _player_by_token(room, tok)
            if p:
                p["connected"] = True
                if p.get("left"):
                    p["left"] = False
                    _broadcast(room, "player.rejoined", {"name": p["name"]})
                return jsonify({"ok": True, "reconnected": True,
                                "seat_token": tok, "role": "player",
                                "name": p["name"]})
        name = _clean(data.get("name", ""), MAX_NAME) or "Anonymous"
        freak = _clean(data.get("freak", ""), MAX_NAME) or "Mystery Freak"
        if not room["locked"] and room["phase"] == "lobby" \
                and len(room["players"]) < MAX_PLAYERS:
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


def _maybe_complete(room: dict):
    """Re-check the current phase after the roster shrank (a leave)."""
    mode = room.get("mode")
    st = room.get("mode_state") or {}
    if room["phase"] != "playing" or not mode:
        return
    if len(_active(room)) < 2:
        _finish_game(room, reason="not enough players")
        return
    if mode == "freaktionary":
        if st.get("phase") == "drawing" and st.get("drawer") in room["players"] \
                and room["players"][st["drawer"]].get("left"):
            _mq_reveal(room, None, "drawer left")
    elif mode == "roast-relay":
        _rr_check_complete(room)
    elif mode.startswith("quip-"):
        _qc_check_complete(room)
    elif mode == "freeze-night":
        ph = st.get("phase")
        if ph == "collecting":
            if st["kind"] == "humiliation-ritual":
                others = [p for p in _fz_players(room)
                          if p != st["ritual"]["victim"]]
                if others and all(p in st["entries"] for p in others):
                    _fz_advance(room, reason="leave")
            elif st["entries"] and _fz_all_in(room, st["entries"]):
                _fz_reveal(room)
        elif ph == "voting" and _fz_votes_done(room):
            _fz_score_prompt(room)
        elif ph in ("passfail", "author"):
            others = [p for p in _fz_players(room)
                      if p != st["ritual"]["victim"]]
            got = st["ritual"]["passed" if ph == "passfail" else "guesses"]
            if all(p in got for p in others):
                _fz_advance(room, reason="leave")
        elif ph == "verdict" and _fz_all_in(room, st["wheel"]["verdicts"]):
            _fz_score_wheel(room)


@party_bp.route("/party/<code>/leave", methods=["POST"])
def leave_room(code):
    """A player walks away. In the lobby the seat is freed; mid-game the
    seat is kept (scores, vote indexes) but nobody waits on it, and the
    same seat token rejoins."""
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = _body()
    with LOCK:
        p = _player_by_token(room, str(data.get("seat_token") or ""))
        if not p:
            return jsonify({"ok": False, "error": "bad seat"}), 403
        if room["phase"] == "lobby":
            room["players"].pop(p["id"], None)
            _broadcast(room, "player.left", {"name": p["name"],
                                             "count": len(room["players"])})
            return jsonify({"ok": True, "freed": True})
        p["left"] = True
        p["connected"] = False
        _broadcast(room, "player.left", {"name": p["name"],
                                         "count": len(_active(room))})
        _maybe_complete(room)
        return jsonify({"ok": True, "freed": False})


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


def _reset_scores(room: dict):
    for p in room["players"].values():
        p["score"] = 0


@party_bp.route("/party/<code>/host", methods=["POST"])
def host_cmd(code):
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = _body()
    if not _is_host(room, str(data.get("host_token") or "")):
        return jsonify({"ok": False, "error": "not host"}), 403
    cmd = str(data.get("cmd") or "")
    with LOCK:
        _check_timer(room)
        if cmd == "lock":
            room["locked"] = True
            _broadcast(room, "roster.locked",
                       {"count": len(room["players"])})
            return jsonify({"ok": True, "locked": True})
        if cmd == "unlock":
            room["locked"] = False
            _broadcast(room, "roster.unlocked",
                       {"count": len(room["players"])})
            return jsonify({"ok": True, "locked": False})
        if cmd == "start":
            # also "play again": restarting resets scores
            pack_name = str(data.get("pack") or "")
            if pack_name:
                if pack_name not in PACKS:
                    return jsonify({"ok": False, "error": "unknown pack"}), 400
                modes = PACKS[pack_name]
                need = max(MODES[m]["min"] for m in modes)
            else:
                mode = str(data.get("mode") or "freaktionary")
                if mode not in MODES:
                    return jsonify({"ok": False, "error": "unknown mode"}), 400
                modes = [mode]
                need = MODES[mode]["min"]
            if len(_active(room)) < need:
                return jsonify({"ok": False, "error": "not enough players",
                                "need": need,
                                "have": len(_active(room))}), 400
            try:
                rounds = int(data.get("rounds") or 0)
            except Exception:
                rounds = 0
            rounds = max(0, min(MAX_ROUNDS, rounds))
            # players who left last game are dropped before a new one
            for pid in [p for p, pl in room["players"].items() if pl.get("left")]:
                room["players"].pop(pid, None)
            _reset_scores(room)
            room["winner"] = None
            room["winner_pid"] = None
            room["result"] = None
            room["pack"] = ({"name": pack_name, "modes": modes, "idx": 0,
                             "rounds_each": rounds or 2}
                            if pack_name else None)
            room["rounds"] = (None if pack_name else
                              (rounds or _default_rounds(room, modes[0])))
            _start_mode(room, modes[0], target=str(data.get("target") or ""),
                        deck=str(data.get("deck") or ""))
            # persistent-freak memory: the room now knows who these
            # performers are, not just what they typed tonight.
            _record_game(room)
            room["lore"] = _room_lore(room)
            _broadcast(room, "lore", {"lines": room["lore"]})
            return jsonify({"ok": True, "mode": modes[0],
                            "rounds": room["rounds"],
                            "pack": pack_name or None})
        if cmd == "advance":
            if room["phase"] != "playing":
                return jsonify({"ok": False, "error": "not playing"}), 400
            exp = str(data.get("expect") or "")
            if exp and exp != _phase_key(room):
                # the room already moved on (timer or a double click):
                # never skip the screen the players are now on
                return jsonify({"ok": False, "error": "already moved on",
                                "stale": True}), 409
            mark = room.get("phase_mark") or {}
            mid_round = (room.get("mode_state") or {}).get("phase") not in (
                "revealed", "scored", "done")
            need = SKIP_MIN_AGE if mid_round else ADVANCE_GRACE
            if exp and mark.get("key") == _phase_key(room) \
                    and _now() - mark.get("t", 0) < need:
                # this screen only just appeared (a double click, or the
                # timer moved on under the host's finger): never skip a
                # round the players have not seen yet
                return jsonify({"ok": False, "error": "just started",
                                "stale": True}), 409
            MODES[room["mode"]]["advance"](room, reason="host")
            return jsonify({"ok": True})
        if cmd == "end":
            if room["phase"] != "playing":
                return jsonify({"ok": False, "error": "not playing"}), 400
            if room["mode"] == "freeze-night":
                _fz_finish(room)
            else:
                _finish_game(room, reason="host")
            return jsonify({"ok": True})
        if cmd == "lobby":
            # back to the lobby: same seats, scores cleared, open to joins
            for pid in [p for p, pl in room["players"].items() if pl.get("left")]:
                room["players"].pop(pid, None)
            room.update({"phase": "lobby", "mode": None, "mode_state": {},
                         "pack": None, "winner": None, "rounds": None,
                         "winner_pid": None, "result": None,
                         "locked": False})
            for pl in room["players"].values():
                pl["score"] = 0
                pl["ready"] = bool(pl.get("bot"))
            _broadcast(room, "room.lobby", {"count": len(room["players"])})
            return jsonify({"ok": True})
        if cmd == "bots":
            # seat deck-driven AI contestants ($0). Lobby or mid-game.
            try:
                n = max(1, min(7, int(data.get("n", 3))))
            except Exception:
                n = 3
            free = MAX_PLAYERS - len(room["players"])
            n = max(0, min(n, free))
            if n == 0:
                return jsonify({"ok": False, "error": "room full"}), 400
            made = _fz_add_bots(room, n)
            if room["phase"] == "playing":
                mode = str(room.get("mode") or "")
                st = room["mode_state"]
                if st.get("phase") == "collecting":
                    if mode.startswith("quip-"):
                        _qc_bots_act(room, "collect")
                    elif mode == "roast-relay":
                        _rr_bots_act(room, "collect")
                    elif mode == "freeze-night":
                        _fz_bots_act(room, "collect")
            return jsonify({"ok": True, "bots": made})
        if cmd == "reject":
            # moderator action: drop one submission before reveal
            st = room["mode_state"]
            pid = str(data.get("player_id") or "")
            if room.get("mode") == "roast-relay" and pid in st.get("lines", {}) \
                    and st.get("phase") == "collecting":
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
    data = _body()
    with LOCK:
        p = _player_by_token(room, str(data.get("seat_token") or ""))
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
    data = _body()
    with LOCK:
        _check_timer(room)
        p = _player_by_token(room, str(data.get("seat_token") or ""))
        if not p:
            return jsonify({"ok": False, "error": "bad seat"}), 403
        if p.get("left"):
            return jsonify({"ok": False, "error": "left the game; rejoin first"}), 409
        # client_seq dedup: retries never double-apply
        cseq = data.get("client_seq")
        if cseq is not None:
            cseq = str(cseq)[:32]
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
        if p:
            p["connected"] = True
        return jsonify({"ok": True,
                        "view": _controller_view(room, p)})


@party_bp.route("/party/<code>/stream", methods=["GET"])
def stream(code):
    """Shared public event stream. Secrets NEVER appear here.
    ?last_seq=N replays missed events; ?once=1 returns JSON (poll fallback).
    The stage polls this, so it also drives the lazy timer: a room with
    only the big screen open still moves on when a deadline passes."""
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False}), 404
    try:
        last = int(request.args.get("last_seq", 0))
    except Exception:
        last = 0
    with LOCK:
        _check_timer(room)
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
    modes = [{"id": k, "title": m["title"], "min": m["min"]}
             for k, m in MODES.items()]
    return (STAGE_TEMPLATE.replace("__CODE__", room["code"])
            .replace("__MODES__", json.dumps(modes).replace("</", "<\\/"))
            .replace("__PACKS__", json.dumps(sorted(PACKS))))


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
<input id=f placeholder='your freak (optional, e.g. Martin Lamp)' maxlength=24 style='padding:10px;font-size:16px;width:220px'><br><br>
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

STAGE_TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>__CODE__ — Freak Town Party Stage</title>
<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;margin:0;padding-bottom:24px}
.top{padding:8px;font-size:12px;letter-spacing:3px;color:#ff2fa8}
#code{font-size:44px;letter-spacing:8px;margin:4px}
#cvwrap{max-width:640px;margin:0 auto}
#cv{background:#111;border:1px solid #333;border-radius:12px;width:100%;height:auto;display:block}
#cap{font-size:20px;min-height:30px;margin:8px}
#big{font-size:26px;margin:10px auto;max-width:900px;color:#fff}
#rules{color:#ff9bd2;font-size:13px;margin:6px}
#scores{color:#aaa;font-size:15px}
.opt{font-size:20px;margin:8px auto;max-width:800px;padding:10px;border:1px solid #333;border-radius:10px}
.win{border-color:#ff2fa8}
button{background:#1a1a2e;border:1px solid #444;color:#eee;padding:8px 14px;border-radius:18px;font-family:monospace;margin:3px;cursor:pointer}
button.big{background:#ff2fa8;border-color:#ff2fa8;color:#fff;font-size:18px;padding:12px 28px}
button.sel{border-color:#ff2fa8;color:#ff2fa8}
#over{padding:10px}
#banner{font-size:46px;color:#ff2fa8;margin:14px}
.row{font-size:22px;margin:6px}</style></head><body>
<div class=top>FREAK TOWN PARTY</div>
<div id=code>__CODE__</div>
<div id=joinhint style='color:#777;font-size:13px'>Join on your phone: <b id=joinurl></b></div>
<img id=qr data-show=inline src='/party/__CODE__/qr.png' style='width:120px;margin:6px' alt='join qr'>
<div id=picker style='margin:10px'>
  <div style='color:#888;font-size:12px;margin-bottom:4px'>PICK A GAME</div>
  <div id=decks></div>
  <div id=primary style='margin:10px'></div>
  <label style='font-size:12px;color:#888'> rounds <input id=rounds type=number min=0 max=20 value=0 style='width:44px'></label>
  <label style='font-size:12px;color:#888'> roast target <input id=target maxlength=60 placeholder='the host' style='width:140px'></label>
</div>
<div id=cap></div>
<div id=big></div>
<div id=cvwrap><canvas id=cv width=520 height=340></canvas></div>
<div id=rules></div>
<div id=scores></div>
<div id=over style='display:none'>
  <div style='color:#888'>GAME OVER</div>
  <div id=banner data-testid=winner></div>
  <div id=final></div>
  <p><button class=big data-act=again data-testid=again>PLAY AGAIN</button>
     <button data-act=lobby data-testid=lobby-over>BACK TO LOBBY</button></p>
</div>
<div id=host style='margin:12px'>
<button data-act=advance data-testid=advance id=advbtn data-show=inline-block class=big>NEXT ROUND ➜</button>
<button data-act=lock id=lockbtn data-show=inline-block>LOCK</button>
<button data-act=bots data-testid=bots id=botsbtn data-show=inline-block>+3 BOTS</button>
<button data-act=end id=endbtn data-show=inline-block>END GAME</button>
<button data-act=skip data-testid=skip id=skipbtn data-show=inline-block style='display:none;margin-left:24px;border-style:dashed'>SKIP</button>
<button data-act=lobby data-testid=lobby id=lobbybtn data-show=inline-block>LOBBY</button>
<div id=hmsg style='color:#888;font-size:12px;min-height:16px' data-testid=hmsg></div>
</div>
<script>
const CODE = '__CODE__';
const HOST_KEY = 'ft_host___CODE__';
const MODES = __MODES__;
const PACKS = __PACKS__;
const QS = new URLSearchParams(location.search);
let hostToken = '';
try{ hostToken = QS.get('host') || localStorage.getItem(HOST_KEY) || '';
     if(QS.get('host')) localStorage.setItem(HOST_KEY, hostToken); }catch(e){ hostToken = QS.get('host') || ''; }
let selMode = QS.get('mode') || '', selPack = '', last = null, seq = 0, rev = '';
document.getElementById('joinurl').textContent = location.host + '/join/' + CODE;
const $ = id => document.getElementById(id);
// only touch the DOM when the content really changed: buttons stay put
// between polls, so clicks never land on an element that was just replaced
function setHTML(el, html){ if(el._h !== html){ el._h = html; el.innerHTML = html; } }
function setText(el, t){ el._h = null; if(el.textContent !== t) el.textContent = t; }
function show(el, on){ const d = on ? (el.dataset.show || 'block') : 'none'; if(el.style.display !== d) el.style.display = d; }
// a fresh screen can't be skipped for a moment (server enforces it too)
function cool(){ const ab = $('advbtn'); ab.disabled = true; ab.style.opacity = .4;
  clearTimeout(cool.t); cool.t = setTimeout(()=>{ ab.disabled = false; ab.style.opacity = 1; }, 2600); }
// NEXT ROUND (between rounds) and SKIP (mid-round) are different buttons in
// different places, and SKIP only appears once a round has run a while, so a
// late click on NEXT ROUND can never skip the round that just started.
const SKIP_AFTER = 8000;
let phaseSince = Date.now();
function gamePhase(s){ const g = s.freaktionary || s.quip || s['roast-relay'] || s['freeze-night'] || {}; return [g.phase, g.round, g]; }
function hostButtons(s){
  const playing = s.room_phase === 'playing';
  const [ph, rnd, g] = gamePhase(s);
  const between = ph === 'revealed' || ph === 'scored';
  const lastRound = s.rounds && Number(rnd) >= s.rounds;
  show($('advbtn'), playing && between);
  setText($('advbtn'), lastRound ? 'FINAL SCORES ➜' : 'NEXT ROUND ➜');
  const label = s.freaktionary ? 'REVEAL WORD (skip round)' : ph === 'collecting' ? 'SKIP TO VOTING' :
                ph === 'voting' ? 'END VOTING NOW' : 'SKIP';
  setText($('skipbtn'), label);
  show($('skipbtn'), playing && !between && ph !== 'done' && Date.now() - phaseSince >= SKIP_AFTER);
}
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
async function hostCmd(cmd, extra){
  const body = Object.assign({host_token: hostToken, cmd}, extra||{});
  if(cmd === 'bots') body.n = 3;
  if(cmd === 'skip'){ cmd = body.cmd = 'advance'; body.skip = true; }
  if(cmd === 'advance'){ if(last) body.expect = last.phase_key; cool(); }
  if(cmd === 'start'){
    const n = parseInt($('rounds').value||'0', 10);
    if(n > 0 && !body.rounds) body.rounds = n;
    const tg = $('target').value;
    if(tg) body.target = tg;
  }
  try{
    const r = await fetch('/party/'+CODE+'/host',{method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const d = await r.json();
    setText($('hmsg'), d.ok ? (cmd+' ok') : d.stale ? (d.error === 'just started' ? 'That screen just appeared, so ADVANCE was ignored. Give the players a moment.' : 'Already moved on: the room is on the next screen.') :
      ('ERR: '+(d.error||'?') + (d.need ? (' (need '+d.need+' players, have '+d.have+')') : '')));
  }catch(e){ setText($('hmsg'), 'ERR: offline'); }
  poll(true);
}
function drawPicker(){
  setHTML($('decks'), MODES.map(m=>"<button data-pick='"+esc(m.id)+"' data-testid='start-"+esc(m.id)+"'"+
      (m.id===selMode && !selPack ? " class=sel" : "")+">"+esc(m.title)+"</button>").join(' ')
    + ' · packs: ' + PACKS.map(p=>"<button data-pickpack='"+esc(p)+"'"+(p===selPack?" class=sel":"")+">"+esc(p)+"</button>").join(' '));
  const t = selPack ? selPack : ((MODES.find(m=>m.id===selMode)||{}).title||'');
  setHTML($('primary'), t ? "<button class=big data-act=start data-testid=start>START "+esc(t)+"</button>"
                          : "<span style='color:#888'>Pick a game above, then START.</span>");
}
document.addEventListener('click', e=>{
  const b = e.target.closest('button'); if(!b) return;
  if(b.dataset.pick){ selMode = b.dataset.pick; selPack = ''; drawPicker(); return; }
  if(b.dataset.pickpack){ selPack = b.dataset.pickpack; drawPicker(); return; }
  const a = b.dataset.act; if(!a) return;
  if(a === 'start') return selPack ? hostCmd('start', {pack: selPack}) : hostCmd('start', {mode: selMode});
  if(a === 'again'){ const s = last||{};
    return (s.pack && s.pack.name) ? hostCmd('start', {pack: s.pack.name}) : hostCmd('start', {mode: s.mode || selMode, rounds: s.rounds || 0}); }
  if(a === 'lock') return hostCmd((last && last.locked) ? 'unlock' : 'lock');
  hostCmd(a);
});
const cv = $('cv'), ctx = cv.getContext('2d');
function paint(strokes){
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.strokeStyle = '#ff2fa8'; ctx.fillStyle = '#ff2fa8'; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  (strokes||[]).forEach(st=>{ const p = st.points||[]; if(!p.length) return;
    if(p.length === 1){ ctx.beginPath(); ctx.arc(p[0][0]*cv.width, p[0][1]*cv.height, 2, 0, 7); ctx.fill(); return; }
    ctx.beginPath(); p.forEach((q,i)=>{ const x=q[0]*cv.width, y=q[1]*cv.height; i ? ctx.lineTo(x,y) : ctx.moveTo(x,y); });
    ctx.stroke(); });
}
function countdown(dl, pre){ if(!dl) return ''; const s2=Math.max(0,Math.round(dl-Date.now()/1000));
  return s2 ? (' · ' + (pre||'⏱') + s2 + 's') : ''; }
let timer = null;
function tmo(ms){ try{ return AbortSignal.timeout(ms); }catch(e){ const c = new AbortController(); setTimeout(()=>c.abort(), ms); return c.signal; } }
async function poll(once){
  try{
    const r = await fetch('/party/'+CODE+'/stream?last_seq='+seq+'&once=1', {signal: tmo(6000)});
    const d = await r.json();
    seq = d.seq; last = d.snapshot; render(d.snapshot);
  }catch(e){}
  if(once) return;
  const fast = last && last.freaktionary && last.freaktionary.phase === 'drawing';
  timer = setTimeout(poll, fast ? 450 : 800);
}
function board(s){ return (s.scores||[]).filter(p=>!p.left).map(p=>esc(p.name)+': '+p.score).join(' · '); }
function render(s){
  if(!s) return;
  const lobby = s.room_phase === 'lobby', done = s.room_phase === 'done', playing = s.room_phase === 'playing';
  show($('picker'), lobby); show($('qr'), lobby); show($('joinhint'), lobby || playing);
  show($('over'), done); show($('endbtn'), playing);
  show($('lobbybtn'), playing); show($('lockbtn'), lobby); show($('botsbtn'), !done);
  if(render._k !== s.phase_key){ render._k = s.phase_key; phaseSince = Date.now(); if(render._k0){ setText($('hmsg'), ''); cool(); } render._k0 = 1; }
  hostButtons(s);
  setText($('lockbtn'), s.locked ? 'UNLOCK' : 'LOCK');
  show($('cvwrap'), !!(s.freaktionary && playing));
  if(lobby){ drawPicker();
    setText($('cap'), 'Waiting for players… ' + ((s.lobby&&s.lobby.count)||0) + ' joined');
    setHTML($('big'), ''); setText($('rules'), '');
    setHTML($('scores'), (s.scores||[]).map(p=>esc(p.name)+' '+(p.ready?'✓':'…')).join('  '));
    return; }
  if(done){
    const res = s.result || {kind: s.champion ? 'win' : 'none', headline: s.champion ? (s.champion+' WINS!') : 'NOBODY SCORED', scores: (s.scores||[]).slice().sort((a,b)=>b.score-a.score)};
    setText($('cap'), (s.title||'') + ' — FINAL');
    setHTML($('big'), ''); setText($('rules'), ''); setHTML($('scores'), '');
    setText($('banner'), (res.kind==='win' ? '🏆 ' : res.kind==='tie' ? '🤝 ' : '') + res.headline);
    const medals = ['🥇','🥈','🥉'];
    const lv = [...new Set((res.scores||[]).map(p=>p.score))].sort((a,b)=>b-a);  // ties share a medal
    setHTML($('final'), (res.scores||[]).map(p=>{ const k = lv.indexOf(p.score);
      return "<div class=row>"+((k<3 && p.score>0)?medals[k]:'·')+' '+esc(p.name)+': '+p.score+'</div>'; }).join(''));
    return; }
  if(s.freaktionary){
    const f = s.freaktionary;
    setText($('cap'), (s.title||'') + ' · round ' + f.round + (s.rounds ? ('/'+s.rounds) : ''));
    setText($('big'), f.revealed ? ('Word was: ' + f.word + (f.winner ? (' · guessed by ' + f.winner + ' (+2, ' + f.drawer + ' +1)') : ' · nobody got it')) + countdown(f.deadline_at, 'next round in ')
                                 : (f.drawer + ' is drawing…' + countdown(f.deadline_at)));
    setText($('rules'), f.rules || '');
    if(f.rev !== rev){ rev = f.rev; paint(f.strokes); }
    setHTML($('scores'), '<div style="color:#666">' + ((f.guesses||[]).length ? 'Wrong guesses: ' : '') + (f.guesses||[]).map(g=>esc(g.by)+': '+esc(g.text)).join(' · ') + '</div><div>' + board(s) + '</div>');
    return; }
  rev = '';
  if(s.quip){ renderQuip(s.quip, s); return; }
  if(s['roast-relay']){
    const r = s['roast-relay'];
    setText($('cap'), 'ROAST RELAY · round ' + (r.round||1) + (s.rounds ? ('/'+s.rounds) : ''));
    setText($('big'), r.phase === 'collecting' ? ('Roast: ' + r.target + ' (' + r.submitted + '/' + r.needed + ')' + countdown(r.deadline_at))
      : r.phase === 'voting' ? ('VOTE the best roast of ' + r.target + countdown(r.deadline_at)) : ('Scores — ' + r.target));
    setText($('rules'), 'Most votes wins the round');
    setHTML($('scores'), (r.clips||[]).map(c=>'<div class=opt>“'+esc(c.text)+'”</div>').join('') + '<div>' + board(s) + '</div>');
    return; }
  if(s['freeze-night']){
    const f = s['freeze-night'];
    setText($('cap'), 'FREEZE NIGHT · ' + (f.round||''));
    setText($('big'), (f.prompt||'') + (f.phase==='collecting' ? (' (' + f.submitted + '/' + f.needed + ')') : '') + countdown(f.deadline_at));
    setText($('rules'), '');
    setHTML($('scores'), (f.options||[]).map(c=>'<div class=opt>“'+esc(c.text)+'”</div>').join('') + '<div>' + board(s) + '</div>');
    return; }
  setText($('cap'), s.title||''); setHTML($('scores'), board(s));
}
function renderQuip(q, s){
  setText($('cap'), (s.title||'') + ' · round ' + (q.round||'') + (s.rounds ? ('/'+s.rounds) : ''));
  setText($('rules'), q.rules || '');
  if(q.phase === 'collecting'){
    setText($('big'), (q.prompt||'') + '  (' + q.submitted + '/' + q.needed + ' answers in)' + countdown(q.deadline_at));
    setHTML($('scores'), '<div>' + board(s) + '</div>'); return; }
  if(q.phase === 'voting'){
    setText($('big'), 'VOTE ON YOUR PHONE: ' + (q.twist === 'liar' ? 'WHO IS LYING?' : (q.prompt||'')) + countdown(q.deadline_at));
    setHTML($('scores'), (q.options||[]).map(c=>'<div class=opt>“'+esc(c.text)+'”</div>').join('') + '<div>' + board(s) + '</div>');
    return; }
  setText($('big'), 'ROUND ' + (q.round||'') + ' RESULTS' + (q.round_winner ? (' — ' + q.round_winner + ' takes it') : '') + countdown(q.deadline_at, 'next round in '));
  let extra = '';
  if(q.secrets){ extra = '<div>' + Object.entries(q.secrets).map(([name,v])=>esc(name)+': '+(v?'TRUE':'LIE')).join(' · ') + '</div>'; }
  setHTML($('scores'), (q.results||[]).map((r,i)=>'<div class="opt'+(i===0&&r.votes?' win':'')+'">“'+esc(r.text)+'” — <b>'+esc(r.by)+'</b> · '+r.votes+' vote'+(r.votes===1?'':'s')+(r.points?(' · +'+r.points):'')+'</div>').join('')
    + extra + '<div>' + board(s) + '</div>');
}
drawPicker();
poll();
</script></body></html>"""

CONTROLLER_TEMPLATE = r"""<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>
<title>Controller — Freak Town Party</title>
<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;margin:0;padding:16px}
button{background:#1a1a2e;border:1px solid #333;color:#eee;padding:14px 22px;border-radius:24px;font-size:16px;margin:4px;font-family:monospace}
button.big{background:#ff2fa8;border-color:#ff2fa8;color:#fff;width:100%}
textarea{width:100%;box-sizing:border-box;background:#111;border:1px solid #333;color:#eee;border-radius:10px;padding:10px;font-size:16px;min-height:60px}
canvas.pad{background:#111;border:1px solid #333;border-radius:12px;touch-action:none;width:100%;height:auto;display:block;
  -webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
.banner{font-size:30px;color:#ff2fa8;margin:12px 0}
.small{color:#ff9bd2;font-size:12px}
.opt{display:block;width:100%;text-align:left;margin:6px 0}</style></head><body>
<div style='color:#ff2fa8;font-size:11px;letter-spacing:2px'>FREAK TOWN PARTY · __CODE__</div>
<h2 id=t></h2><div id=sub style='color:#888;min-height:18px'></div>
<div id=body style='max-width:520px;margin:0 auto'></div>
<p><button id=leave style='font-size:11px;padding:6px 12px;opacity:.6;display:none' onclick='leaveGame()' data-testid=leave>LEAVE GAME</button></p>
<script>
const CODE = '__CODE__';
let seat = new URLSearchParams(location.search).get('seat') || '';
try{ seat = seat || localStorage.getItem('ft_seat_'+CODE) || ''; }catch(e){}
let cseq = 0, lastKey = '', nodes = [], lastV = null, pollT = null;
async function view(once){
  try{
    const r = await fetch('/party/'+CODE+'/view?seat_token='+encodeURIComponent(seat), {signal: tmo(6000)});
    const d = await r.json();
    if(d.ok) render(d.view);
  }catch(e){}
  if(once) return;
  clearTimeout(pollT);
  const live = lastV && lastV.freaktionary && (lastV.screen === 'guess' || lastV.screen === 'reveal');
  pollT = setTimeout(view, live ? 500 : 1100);
}
function tmo(ms){ try{ return AbortSignal.timeout(ms); }catch(e){ const c = new AbortController(); setTimeout(()=>c.abort(), ms); return c.signal; } }
function setText(el, t){ if(el.textContent !== t) el.textContent = t; }
function draftKey(v, id){ const t = (v.components||[]).find(c=>c.type==='text'); return 'ft_draft_'+CODE+'_'+seat.slice(0,8)+'_'+(v.mode||'')+'_'+roundOf(v)+'_'+id+'_'+((t&&t.text)||'').slice(0,40); }
function dropDraft(t){ try{ if(t && t.dataset.draft) localStorage.removeItem(t.dataset.draft); }catch(e){} }
function roundOf(v){ const g = v.freaktionary || v.quip || v['roast-relay'] || v['freeze-night'] || {}; return String(g.round||''); }
function strokesOf(v){ return (v.freaktionary && v.freaktionary.strokes) || []; }
function revOf(v){ return (v.freaktionary && v.freaktionary.rev) || ''; }
// The screen is rebuilt only when its STRUCTURE changes (new screen, new
// round, new options). Text updates in place; inputs, focus and whatever
// the player is typing are never touched by a poll.
function render(v){
  lastV = v;
  setText(document.getElementById('t'), titleFor(v));
  document.getElementById('leave').style.display = (seat && v.you && !v.you.left && v.screen !== 'audience' && v.screen !== 'lobby') ? '' : 'none';
  const comps = v.components || [];
  const key = [v.screen, v.mode||'', roundOf(v), v.secret||''].concat(comps.map(c=>
    c.type+':'+(c.id||'')+':'+(c.options ? JSON.stringify(c.options) : '')+':'+(c.label||''))).join('|');
  if(key === lastKey){
    comps.forEach((c,i)=>{ const n = nodes[i]; if(!n) return;
      if(c.type === 'text' || c.type === 'banner') setText(n, c.text||'');
      if(c.type === 'canvas' && c.readonly && n._rev !== revOf(v)){ n._rev = revOf(v); paint(n, strokesOf(v)); } });
    return;
  }
  lastKey = key;
  const b = document.getElementById('body');
  b.innerHTML = ''; nodes = [];
  setText(document.getElementById('sub'), '');
  comps.forEach(c=>{
    let n = null;
    if(c.type === 'text'){ n=document.createElement('p'); n.textContent=c.text;
      if(/^(Guess it:|Most votes|Fewest votes|Vote for the LIE)/.test(c.text||'')) n.className='small'; }
    if(c.type === 'banner'){ n=document.createElement('div'); n.className='banner'; n.textContent=c.text; }
    if(c.type === 'textarea'){ n=document.createElement('textarea'); n.id='fld_'+c.id;
      n.maxLength=c.max_length||180;
      // drafts survive a reload / a phone that drops the tab in the background
      const dk = draftKey(v, c.id); n.dataset.draft = dk;
      try{ n.value = localStorage.getItem(dk) || ''; }catch(e){}
      n.addEventListener('input', ()=>{ try{ localStorage.setItem(dk, n.value); }catch(e){} }); if(c.id==='guess'){ n.rows=1; n.style.minHeight='44px'; n.placeholder='type your guess';
        n.addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); const s=comps.find(x=>x.type==='submit'); if(s) submit(s); } }); } }
    if(c.type === 'toggle'){ n=document.createElement('label');
      n.style.display='block'; n.style.margin='8px';
      const cb=document.createElement('input'); cb.type='checkbox'; cb.id='fld_'+c.id;
      n.appendChild(cb); n.appendChild(document.createTextNode(' '+(c.label||c.id))); }
    if(c.type === 'submit'){ n=document.createElement('button'); n.className='big';
      n.textContent=c.label||'SEND'; n.onclick=()=>submit(c); }
    if(c.type === 'button'){ n=document.createElement('button');
      n.textContent=c.label||c.id; n.onclick=()=>press(c.id); }
    if(c.type === 'choice'){ n=document.createElement('div'); const act = c.action || {kind:'vote', as:'choice'};
      if((act.multi||1) > 1){
        const sel = [];
        (c.options||[]).forEach(o=>{ const btn=document.createElement('button');
          btn.className='opt'; btn.textContent=o.text;
          btn.onclick=()=>{ const ix=sel.indexOf(o.id);
            if(ix>=0){ sel.splice(ix,1); btn.style.borderColor='#333'; }
            else if(sel.length < act.multi){ sel.push(o.id); btn.style.borderColor='#ff2fa8'; } };
          n.appendChild(btn); });
        const send=document.createElement('button'); send.className='big';
        send.textContent='SEND VOTES ('+act.multi+' max)';
        send.onclick=()=>sendInput(act.kind, {[act.as==='choice'?'choices':act.as]: sel});
        n.appendChild(send);
      } else { (c.options||[]).forEach(o=>{ const btn=document.createElement('button');
        btn.className='opt'; btn.textContent=o.text;
        btn.onclick=()=>{ btn.style.borderColor='#ff2fa8'; sendInput(act.kind, {[act.as]: o.id}); }; n.appendChild(btn); }); } }
    if(c.type === 'canvas'){ n=document.createElement('canvas'); n.className='pad';
      n.id = c.readonly ? 'watch' : 'draw'; n.width=520; n.height=340;
      n.setAttribute('data-testid', c.readonly ? 'watch-canvas' : 'draw-canvas');
      if(c.readonly){ n._rev = revOf(v); paint(n, strokesOf(v)); }
      else { paint(n, strokesOf(v)); wireDraw(n); } }
    nodes.push(n);
    if(n) b.appendChild(n);
  });
}
function paint(cv, strokes){
  const ctx = cv.getContext('2d');
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.strokeStyle='#ff2fa8'; ctx.fillStyle='#ff2fa8'; ctx.lineWidth=4; ctx.lineCap='round'; ctx.lineJoin='round';
  (strokes||[]).forEach(st=>{ const p = st.points||[]; if(!p.length) return;
    if(p.length === 1){ ctx.beginPath(); ctx.arc(p[0][0]*cv.width, p[0][1]*cv.height, 2, 0, 7); ctx.fill(); return; }
    ctx.beginPath(); p.forEach((q,i)=>{ const x=q[0]*cv.width, y=q[1]*cv.height; i ? ctx.lineTo(x,y) : ctx.moveTo(x,y); });
    ctx.stroke(); });
}
async function leaveGame(){
  if(!confirm('Leave this game? You can rejoin with this phone.')) return;
  await fetch('/party/'+CODE+'/leave',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat})});
  lastKey = ''; view(true);
}
function titleFor(v){
  if(v.screen==='lobby') return 'LOBBY';
  if(v.screen==='drawer') return 'DRAW: ' + (v.secret||'');
  if(v.screen==='guess') return 'GUESS THE DRAWING';
  if(v.screen==='vote') return 'VOTE';
  if(v.screen==='perform') return 'PERFORM';
  if(v.screen==='scores') return (v.room_phase==='done' || v.phase==='done') ? 'FINAL SCORES' : 'SCORES';
  if(v.screen==='reveal') return 'REVEAL';
  if(v.screen==='audience') return 'AUDIENCE';
  return v.title ? v.title : (v.mode ? v.mode.toUpperCase() : 'FREAK TOWN');
}
async function submit(c){
  const t = document.querySelector('#body textarea');
  const fid = t ? t.id : '';
  const kind = c.kind || (fid === 'fld_guess' ? 'guess' : (fid === 'fld_line' ? 'line' : 'entry'));
  const extra = {text: t?t.value:''};
  const tg = document.querySelector('#body input[type=checkbox][id^=fld_]');
  if(tg) extra[tg.id.replace('fld_','')] = tg.checked;
  const d = await sendInput(kind, extra);
  if(d && d.ok) dropDraft(t);
  // a wrong guess clears only the guess box, and keeps the keyboard up
  if(d && d.ok && kind === 'guess' && d.correct === false && t){ t.value = ''; t.focus(); }
}
async function sendInput(kind, extra){
  const body = Object.assign({seat_token: seat, client_seq: Date.now()+'-'+(++cseq), kind}, extra||{});
  let d = null;
  try{
    const r = await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)});
    d = await r.json();
    setText(document.getElementById('sub'), d.ok ? (d.correct === false ? 'Nope — keep guessing' : (d.correct ? 'Correct! +2' : '')) : ('⚠ ' + (d.error||'try again')));
  }catch(e){ setText(document.getElementById('sub'), '⚠ offline'); }
  view(true);
  return d;
}
async function press(id){
  if(id==='ready') await fetch('/party/'+CODE+'/ready',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, ready: true})});
  if(id==='rejoin') await fetch('/party/'+CODE+'/join',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat})});
  if(id==='laugh') await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, client_seq: Date.now()+'-'+(++cseq), kind:'laugh'})});
  if(id==='clear'){ const cv = document.getElementById('draw'); if(cv && cv._reset) cv._reset();
    await sendInput('draw.clear', {}); return; }
  lastKey = ''; view(true);
}
// Drawing: pointer events with capture (mouse, pen, touch), touch/mouse
// fallback, segments drawn between every sampled point, strokes sent in
// ordered ~150 ms batches tagged with a stroke id so the server joins them.
function wireDraw(cv){
  const ctx = cv.getContext('2d');
  let cur = null, lastP = null, queue = [], inflight = false;
  const pos = e=>{ const r=cv.getBoundingClientRect();
    return [Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),
            Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))]; };
  const style = ()=>{ ctx.strokeStyle='#ff2fa8'; ctx.fillStyle='#ff2fa8'; ctx.lineWidth=4; ctx.lineCap='round'; ctx.lineJoin='round'; };
  function add(p){
    style();
    if(lastP){ if(Math.abs(p[0]-lastP[0]) < 0.002 && Math.abs(p[1]-lastP[1]) < 0.002) return;
      ctx.beginPath(); ctx.moveTo(lastP[0]*cv.width,lastP[1]*cv.height); ctx.lineTo(p[0]*cv.width,p[1]*cv.height); ctx.stroke(); }
    else { ctx.beginPath(); ctx.arc(p[0]*cv.width,p[1]*cv.height,2,0,7); ctx.fill(); }
    lastP = p; queue.push({id: cur, p: [Math.round(p[0]*1000)/1000, Math.round(p[1]*1000)/1000]});
  }
  function start(e){ cur = 's' + Date.now().toString(36) + Math.random().toString(36).slice(2,6); lastP = null; add(pos(e)); }
  function move(e){ if(!cur) return;
    const evs = (e.getCoalescedEvents && e.getCoalescedEvents().length) ? e.getCoalescedEvents() : [e];
    evs.forEach(ev=>add(pos(ev))); }
  function end(){ if(!cur) return; cur = null; lastP = null; flush(); }
  async function flush(){
    if(inflight || !queue.length) return;
    const id = queue[0].id; const pts = [];
    while(queue.length && queue[0].id === id && pts.length < 300) pts.push(queue.shift().p);
    inflight = true;
    try{
      const r = await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
        body: JSON.stringify({seat_token: seat, client_seq: Date.now()+'-'+(++cseq), kind:'draw.batch', stroke: id, points: pts})});
      const d = await r.json();
      if(!d.ok) setText(document.getElementById('sub'), '⚠ ' + (d.error||'not sent'));
    }catch(e){ queue = pts.map(p=>({id, p})).concat(queue); }
    inflight = false;
    if(queue.length) setTimeout(flush, 30);
  }
  cv._reset = ()=>{ queue = []; cur = null; lastP = null; ctx.clearRect(0,0,cv.width,cv.height); };
  const iv = setInterval(()=>{ if(!document.body.contains(cv)){ clearInterval(iv); return; } flush(); }, 150);
  if(window.PointerEvent){
    cv.addEventListener('pointerdown', e=>{ e.preventDefault(); try{ cv.setPointerCapture(e.pointerId); }catch(_){} start(e); });
    cv.addEventListener('pointermove', e=>{ if(cur){ e.preventDefault(); move(e); } });
    cv.addEventListener('pointerup', e=>{ try{ cv.releasePointerCapture(e.pointerId); }catch(_){} end(); });
    cv.addEventListener('pointercancel', end);
    cv.addEventListener('lostpointercapture', end);
    // iOS: stop the page scrolling/zooming under the finger
    cv.addEventListener('touchstart', e=>e.preventDefault(), {passive:false});
    cv.addEventListener('touchmove', e=>e.preventDefault(), {passive:false});
  } else {
    cv.addEventListener('touchstart', e=>{ e.preventDefault(); start(e.touches[0]); }, {passive:false});
    cv.addEventListener('touchmove', e=>{ e.preventDefault(); move(e.touches[0]); }, {passive:false});
    cv.addEventListener('touchend', e=>{ e.preventDefault(); end(); }, {passive:false});
    cv.addEventListener('mousedown', e=>start(e));
    window.addEventListener('mousemove', e=>move(e));
    window.addEventListener('mouseup', end);
  }
}
view();
</script></body></html>"""
