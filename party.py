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
from harness_adapter import party_reaction

party_bp = Blueprint("party", __name__)

BASE = Path(__file__).parent
PARTY_LOG = BASE / "party_events.jsonl"
RECORDS_FILE = BASE / "party_records.json"
ROOMS_FILE = BASE / "party_rooms.json"

# High-frequency events skip disk snapshots (replay buffer keeps them in RAM).
NO_SNAPSHOT = {"draw.batch", "guess", "laugh", "line.accepted", "vote.accepted",
               "smile.detected", "character.react"}

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
    # Mutuals-style reactions: semantic events, not LLM or TTS calls.
    # Never treat these as laughter labels or scored votes.
    reaction = party_reaction(kind)
    if reaction is not None:
        room["seq"] += 1
        act = {"seq": room["seq"], "kind": "character.react", "t": _now(),
               "actor": "host", "acting": reaction}
        room["events"].append(act)
        room["events"] = room["events"][-500:]
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
                "mode_state": room["mode_state"],
                "players": {pid: {k: v for k, v in p.items() if k != "_last_smile"}
                            for pid, p in room["players"].items()},
                "seq": room["seq"], "events": [e for e in room["events"][-100:]
                     if e.get("kind") not in ("smile.detected", "character.react", "character.act")],
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
        _mq_bots_act(room, "guess")
        return {"ok": True, "correct": False}
    return {"ok": False, "error": "unknown input"}


# ── pi-harness agent backend (ADDITIVE) ─────────────────────────────
# Bots are agents with pi harness backends when PARTY_PI_AGENTS=1;
# otherwise $0 deck fallback (tests never touch network). Fail-closed.

def _pi_line(mode: str, prompt: str, seat: str) -> str | None:
    try:
        import sys as _s
        from pathlib import Path as _P
        _s.path.insert(0, str(_P(__file__).parent / "scripts"))
        import party_pi_agents as _pi  # noqa
        return _pi.agent_line(mode, prompt, seat)
    except Exception:
        return None


def _mq_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "drawing" and not st.get("revealed"):
        st["revealed"] = True  # timeout with no winner: reveal, no points
        _broadcast(room, "round.revealed", {"round": st["round"],
                                            "word": st["word"],
                                            "reason": reason or "timeout"})
    if _pack_quota_met(room):
        _pack_next(room)
        return
    _mq_start_round(room)
    _mq_bots_act(room, "start")


# ── freaktionary solo bots (ADDITIVE, solo-vs-agents) ─────────────────
# Deck bots ($0, no API): bots guess from the word list + seeded decoys;
# a bot drawer lays simple strokes so the room keeps moving. Humans always
# play the same path; bots just fill seats. Jev-1.14 eyes (Box/Noul) and
# Fish s2.1-pro-free voice are optional upgrades via scripts/party_agent_sdk
# — same interface, bots become providers.

MQ_BOT_DECOYS = [
    "pigeon", "dentist", "karaoke", "air fryer", "traffic cone",
    "haunted Roomba", "LinkedIn", "cryptocurrency", "divorce court", "Tesco",
]

MQ_BOT_DRAW_STROKES = [
    [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8], [0.2, 0.2]],
    [[0.5, 0.1], [0.5, 0.9]],
    [[0.1, 0.5], [0.9, 0.5]],
]


def _mq_bots_act(room: dict, stage: str):
    """One seeded bot turn. Safe to call after any human input or round start."""
    st = room["mode_state"]
    if st.get("phase") != "drawing" or st.get("revealed"):
        return
    import random as _r
    rng = _r.Random(hash(room["code"]) % (2 ** 31) + st.get("round", 0) * 131)
    bots = [pid for pid, p in room["players"].items() if p.get("bot")]
    if not bots:
        return
    # Bot drawer lays strokes so humans have something to guess at.
    if stage == "start" and st.get("drawer") in bots and not st.get("strokes"):
        st["strokes"].append({"by": st["drawer"],
                              "points": list(rng.choice(MQ_BOT_DRAW_STROKES))})
        _broadcast(room, "draw.batch", {"round": st["round"],
                                        "points": st["strokes"][-1]["points"]})
    # Bott guessers take one shot each (seeded word-list + decoys).
    if stage in ("start", "guess"):
        for pid in bots:
            if pid == st.get("drawer") or st.get("revealed"):
                continue
            pool = WORDS + MQ_BOT_DECOYS
            guess = (_pi_line("freaktionary", "Guess the drawing in a few words.", pid)
                     or rng.choice(pool)).lower()[:60]
            if guess == (st.get("word") or "").lower():
                st["winner"] = pid
                st["revealed"] = True
                room["players"][pid]["score"] += 2
                room["players"][st["drawer"]]["score"] += 1
                _record_win(room, pid)
                _broadcast(room, "round.won", {
                    "round": st["round"],
                    "winner": room["players"][pid]["name"],
                    "word": st["word"], "scores": _public_players(room)})
                return
            st["guesses"].append({"by": room["players"][pid]["name"],
                                  "text": guess})
        _broadcast(room, "guess", {"round": st["round"],
                                   "by": "bots", "count": len(st["guesses"])})


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
            _rr_bots_act(room, "vote")
        else:
            _rr_bots_act(room, "collect")
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
        else:
            _rr_bots_act(room, "vote")
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
    st["callback"] = _ella_callback(room)
    _broadcast(room, "set.revealed", {"mode": "roast-relay",
                                      "target": st["target"], "clips": clips,
                                      "callback": st["callback"],
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
            _rr_bots_act(room, "collect")
    elif st["phase"] == "voting":
        _rr_score(room)
    else:
        if _pack_quota_met(room):
            _pack_next(room)
            return
        _rr_start_round(room, st.get("target") or "")
        _rr_bots_act(room, "collect")


# ── roast-relay solo bots (ADDITIVE, solo-vs-agents) ──────────────────
# Deck bots ($0, no API): lines from a roast deck, votes seeded + no
# self-vote. Fish s2.1-pro-free voice is the $0 audio upgrade (same TTS
# endpoint, model header only) — room never waits for it.

RR_BOT_LINES = [
    "your air fryer has seen things. it told me. i believe it.",
    "you roast like a microwave beep: loud, short, forgotten.",
    "the pigeon landed on your punchline. it left.",
    "your group chat died Tuesday. we held a eulogy. it slapped.",
    "you defend soup badly and the soup knows.",
    "blackout. one beep. even the usher gave up on you.",
]


def _rr_bots_act(room: dict, stage: str):
    """Fill bot lines/votes. Safe to call after any human input or reveal."""
    st = room["mode_state"]
    import random as _r
    rng = _r.Random(hash(room["code"]) % (2 ** 31) + st.get("round", 0) * 173)
    for pid in room["players"]:
        if pid not in st.get("order", []):
            st["order"].append(pid)
    bots = [pid for pid in st.get("order", [])
            if pid in room["players"] and room["players"][pid].get("bot")]
    if not bots:
        return
    if stage == "collect" and st.get("phase") == "collecting":
        for pid in bots:
            if pid not in st["lines"]:
                used = set(st["lines"].values())
                avail = [line for line in RR_BOT_LINES if line not in used] or RR_BOT_LINES
                st["lines"][pid] = (
                    _pi_line("roast-relay",
                             f"Target: {st.get('target','')}. Roast them in one line.", pid)
                    or rng.choice(avail))
        if len(st["lines"]) >= len(room["players"]) and room["players"]:
            _rr_reveal(room)
            _rr_bots_act(room, "vote")
    elif stage == "vote" and st.get("phase") == "voting":
        for pid in bots:
            if pid in st["votes"]:
                continue
            choices = [str(i) for i in range(len(st["order"]))
                       if st["order"][int(i)] != pid]
            if choices:
                st["votes"][pid] = rng.choice(choices)
        if len(st["votes"]) >= len(room["players"]) and room["players"]:
            _rr_score(room)


# ── stone-face (M1 STONE FACE / format #7 TRY NOT TO SMILE) ─────────────
# Phones submit one funny-true info each. The room assembles a short set
# weaving every confession together, then everyone holds a stone face while
# the set plays line by line. Crack (self-report button) and you're out of
# the survivor pool. Last stone faces standing split the glory.
# Honest limits (v1): the set is template-assembled from submissions ($0,
# no LLM call); cracks are self-reported taps. `smile_detected` is accepted
# as a crack source for the future E1 webcam referee — nothing produces it
# yet, and docs say so loudly.

SF_BOT_INFOS = [
    "I rehearse arguments in the shower and still lose",
    "my plants have a group chat without me",
    "I once waved back at someone who wasn't waving at me. Twice. Same person.",
    "my search history could end a career that never started",
    "I say 'you too' when the waiter says enjoy your meal",
    "I have a PhD in overthinking texts with no reply",
    "my gym membership is a monthly donation to a building I fear",
    "I clap when the plane lands and I am not ashamed. Okay, a little.",
]

SF_CRACK_CHANCE = 0.35  # per bot per set line


def _sf_create(room: dict):
    room["mode_state"] = {
        "round": 0, "phase": "collecting", "infos": {}, "order": [],
        "set": [], "line_i": 0, "cracked": {}, "crack_order": [],
        "deadline_at": None,
    }


def _sf_start_round(room: dict):
    st = room["mode_state"]
    st["round"] = st.get("round", 0) + 1
    st["infos"] = {}
    st["order"] = list(room["players"].keys())
    st["set"] = []
    st["line_i"] = 0
    st["cracked"] = {}
    st["crack_order"] = []
    st["phase"] = "collecting"
    st["deadline_at"] = _now() + 90
    _broadcast(room, "collect.started", {"mode": "stone-face",
                                        "deadline_at": st["deadline_at"]})


def _sf_assemble(room: dict):
    """Weave every confession into the night's set, then start the hold."""
    st = room["mode_state"]
    lines = [{"by": "ELLA",
              "text": "Tonight's set was written by YOU. No refunds. Stone faces ON."}]
    for pid in st["order"]:
        if pid in st["infos"]:
            name = room["players"][pid]["name"]
            lines.append({"by": name,
                          "text": f'{name} confessed: "{st["infos"][pid]}" '
                                  f'— the room has ruled this is now canon.'})
    lines.append({"by": "ELLA",
                  "text": "Smile and you're done. The last stone face takes the points."})
    st["set"] = lines
    st["line_i"] = 0
    st["phase"] = "performing"
    st["deadline_at"] = _now() + 120
    _broadcast(room, "set.revealed", {"mode": "stone-face",
                                     "lines": len(lines),
                                     "deadline_at": st["deadline_at"]})
    _sf_bots_act(room, "perform")


def _sf_input(room: dict, player: dict, data: dict):
    st = room["mode_state"]
    kind = data.get("kind")
    if kind == "info":
        if st["phase"] != "collecting":
            return {"ok": False, "error": "not collecting now"}
        info = _clean(data.get("text", ""), 120)
        if not info:
            return {"ok": False, "error": "empty info"}
        st["infos"][player["id"]] = info  # resubmit overwrites
        _broadcast(room, "info.accepted", {"by": player["name"],
                                          "count": len(st["infos"]),
                                          "needed": len(room["players"])})
        if len(st["infos"]) >= len(room["players"]) and room["players"]:
            _sf_assemble(room)
        return {"ok": True}
    if kind in ("crack", "smile_detected"):
        if st["phase"] != "performing":
            return {"ok": False, "error": "the set is not playing"}
        if player["id"] in st["cracked"]:
            return {"ok": False, "error": "already cracked"}
        st["cracked"][player["id"]] = st["line_i"]
        st["crack_order"].append(player["id"])
        _broadcast(room, "face.cracked", {"by": player["name"],
                                         "at_line": st["line_i"],
                                         "source": kind,
                                         "left": len(room["players"]) - len(st["cracked"])})
        if len(st["cracked"]) >= len(room["players"]) and room["players"]:
            _sf_score(room)
        return {"ok": True}
    return {"ok": False, "error": "unknown input"}


def _sf_survivors(room: dict) -> list:
    st = room["mode_state"]
    return [pid for pid in st["order"]
            if pid in room["players"] and pid not in st["cracked"]]


def _sf_score(room: dict):
    st = room["mode_state"]
    survivors = _sf_survivors(room)
    for pid in survivors:
        room["players"][pid]["score"] += 3
        _record_win(room, pid)
    st["phase"] = "scored"
    st["deadline_at"] = None
    _broadcast(room, "score.updated",
               {"survivors": [room["players"][p]["name"] for p in survivors],
                "crack_order": [room["players"][p]["name"]
                                for p in st["crack_order"]],
                "scores": _public_players(room)})


def _sf_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "collecting":
        if st["infos"]:
            _sf_assemble(room)
        else:
            _sf_start_round(room)
    elif st["phase"] == "performing":
        st["line_i"] += 1
        if st["line_i"] >= len(st["set"]):
            _sf_score(room)
        else:
            st["deadline_at"] = _now() + 120
            _broadcast(room, "line.advanced",
                       {"mode": "stone-face", "line_i": st["line_i"],
                        "of": len(st["set"]),
                        "line": st["set"][st["line_i"]]})
            _sf_bots_act(room, "perform")
    else:
        if _pack_quota_met(room):
            _pack_next(room)
            return
        _sf_start_round(room)


def _sf_bots_act(room: dict, stage: str):
    """Deck bots: infos from the confession deck, cracks from seeded nerve."""
    st = room["mode_state"]
    if room.get("mode_state") is None or st.get("phase") == "scored":
        return
    import random as _r
    rng = _r.Random(hash(room["code"]) % (2 ** 31)
                    + st.get("round", 0) * 101 + st.get("line_i", 0))
    # Mid-night seats (host bots cmd) join the round order, or the room
    # would wait forever for confessions from players outside st["order"].
    for pid in room["players"]:
        if pid not in st["order"]:
            st["order"].append(pid)
    bots = [pid for pid in st["order"]
            if pid in room["players"] and room["players"][pid].get("bot")]
    if not bots:
        return
    if stage == "collect" and st["phase"] == "collecting":
        for pid in bots:
            if pid not in st["infos"]:
                used = set(st["infos"].values())
                avail = [l for l in SF_BOT_INFOS if l not in used] or SF_BOT_INFOS
                st["infos"][pid] = (
                    _pi_line("stone-face", "Confess something TRUE+funny about you.", pid)
                    or rng.choice(avail))
        if len(st["infos"]) >= len(room["players"]) and room["players"]:
            _sf_assemble(room)
    elif stage == "perform" and st["phase"] == "performing":
        for pid in bots:
            if pid in st["cracked"]:
                continue
            if rng.random() < SF_CRACK_CHANCE:
                st["cracked"][pid] = st["line_i"]
                st["crack_order"].append(pid)
                _broadcast(room, "face.cracked",
                           {"by": room["players"][pid]["name"],
                            "at_line": st["line_i"], "source": "bot",
                            "left": len(room["players"]) - len(st["cracked"])})
        if len(st["cracked"]) >= len(room["players"]) and room["players"]:
            _sf_score(room)


def _sf_controller(room: dict, player: dict) -> dict:
    """Phone screens for stone-face: confess, hold, scores."""
    st = room["mode_state"]
    out: dict = {"screen": "wait", "components": []}
    if st["phase"] == "collecting":
        out["screen"] = "prompt"
        out["components"] = [
            {"type": "text",
             "text": "Give the set something TRUE + funny about you (one line). The room roasts it back."},
            {"type": "textarea", "id": "info", "max_length": 120},
            {"type": "submit", "label": "CONFESS"}]
        return out
    if st["phase"] == "performing":
        if player["id"] in st["cracked"]:
            at = st["cracked"][player["id"]] + 1
            out["screen"] = "wait"
            out["components"] = [
                {"type": "text",
                 "text": f"You CRACKED at line {at}. Sit back and watch the strong survive."}]
            return out
        line = st["set"][st["line_i"]] if st["set"] else {"by": "ELLA", "text": "…"}
        out["screen"] = "hold"
        out["components"] = [
            {"type": "text",
             "text": f"LINE {st['line_i'] + 1}/{len(st['set'])} — {line['by']}: “{line['text']}”"},
            {"type": "text", "text": "HOLD IT. Stone face. Do not smile."},
            {"type": "button", "id": "cracked", "label": "I CRACKED 😬"}]
        return out
    out["screen"] = "scores"
    out["components"] = [{"type": "text", "text": "Set over. Stone faces collect."}]
    return out


# ── poker (fixed-limit Texas Hold'em: tells at the table) ─────────────
# Phones hold SECRET hole cards; community + pot are public. Fixed betting
# (2 preflop/flop, 4 turn/river), blinds 1/2, stacks of 100, side pots done
# right. Bots play pot-odds poker with seeded bluffs (the level field).
# Faces: presence roster shows who's on camera; video seats reuse the stage
# monitor pattern (progressive enhancement, not required to play).

PK_RANKS = "23456789TJQKA"
PK_SB, PK_BB, PK_SMALL, PK_BIG, PK_STACK = 1, 2, 2, 4, 100


def _pk_eval5(cards):
    """Score 5 cards -> comparable tuple (bigger wins)."""
    rs = sorted((PK_RANKS.index(c[0]) for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    uniq = sorted(set(rs), reverse=True)
    straight_hi = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_hi = uniq[0]
        elif uniq == [12, 3, 2, 1, 0]:  # wheel A-5
            straight_hi = 3
    from collections import Counter as _C
    cnt = sorted(_C(rs).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    if flush and straight_hi is not None:
        return (8, straight_hi)
    if cnt[0][1] == 4:
        return (7, cnt[0][0], cnt[1][0])
    if cnt[0][1] == 3 and cnt[1][1] == 2:
        return (6, cnt[0][0], cnt[1][0])
    if flush:
        return (5,) + tuple(rs)
    if straight_hi is not None:
        return (4, straight_hi)
    if cnt[0][1] == 3:
        kick = sorted((r for r in rs if r != cnt[0][0]), reverse=True)
        return (3, cnt[0][0]) + tuple(kick)
    if cnt[0][1] == 2 and cnt[1][1] == 2:
        hi, lo = max(cnt[0][0], cnt[1][0]), min(cnt[0][0], cnt[1][0])
        kicker = next(r for r in rs if r != hi and r != lo)
        return (2, hi, lo, kicker)
    if cnt[0][1] == 2:
        kick = sorted((r for r in rs if r != cnt[0][0]), reverse=True)
        return (1, cnt[0][0]) + tuple(kick)
    return (0,) + tuple(rs)


def _pk_best(cards7):
    """Best 5-of-7 score."""
    from itertools import combinations as _comb
    return max(_pk_eval5(list(c)) for c in _comb(cards7, 5))


def _pk_deck(rng):
    suits = "shdc"
    deck = [r + s for r in PK_RANKS for s in suits]
    rng.shuffle(deck)
    return deck


def _pk_live(st, pid):
    return (pid in st["hole"] and pid not in st["folded"]
            and pid not in st.get("allin", []))


def _pk_create(room: dict):
    room["mode_state"] = {"hand": 0, "phase": "lobby", "stacks": {},
                          "button": None, "history": []}


def _pk_start_hand(room: dict):
    import random as _r
    st = room["mode_state"]
    seated = [pid for pid in room["players"]]
    if len([p for p in seated if room["players"][p].get("stack", PK_STACK) > 0]) < 2:
        for pid in seated:
            room["players"][pid]["stack"] = int(room["players"][pid].get("stack", 0) or PK_STACK)
    for pid in seated:
        if room["players"][pid].get("stack", 0) <= 0:
            room["players"][pid]["stack"] = PK_STACK
    order = [pid for pid in seated if room["players"][pid]["stack"] > 0]
    if len(order) < 2:
        return False
    st["hand"] = st.get("hand", 0) + 1
    rng = _r.Random(hash(room["code"]) % (2 ** 31) + st["hand"] * 7919)
    st["deck"] = _pk_deck(rng)
    st["community"] = []
    st["street"] = "preflop"
    st["hole"] = {}
    st["folded"] = []
    st["allin"] = []
    st["pots"] = [{"amount": 0, "eligible": list(order)}]
    st["committed"] = {pid: 0 for pid in order}  # this hand
    st["street_bet"] = {pid: 0 for pid in order}  # this street
    st["current_bet"] = 0
    st["acted"] = []
    st["raises"] = 0
    st["winners"] = []
    st["phase"] = "betting"
    if st["button"] in order:
        btn = (order.index(st["button"]) + 1) % len(order)
    else:
        btn = 0
    st["button"] = order[btn]
    st["order"] = order
    n = len(order)
    sb_i = (btn + 1) % n
    bb_i = (btn + 2) % n if n > 2 else (btn + 1) % n
    if n == 2:
        sb_i, bb_i = btn, (btn + 1) % n
    _pk_post(room, order[sb_i], PK_SB)
    _pk_post(room, order[bb_i], PK_BB)
    for pid in order:
        st["hole"][pid] = [st["deck"].pop(), st["deck"].pop()]
    st["actor"] = order[sb_i] if n == 2 else order[(bb_i + 1) % n]
    if st["actor"] in st.get("allin", []):
        _pk_next_actor(room)
    st["deadline_at"] = _now() + 90
    _broadcast(room, "hand.started", {"mode": "poker", "hand": st["hand"],
                                     "button": room["players"][st["button"]]["name"],
                                     "players": len(order)})
    _pk_drive(room)
    return True


def _pk_post(room: dict, pid: str, amount: int):
    st = room["mode_state"]
    have = room["players"][pid].get("stack", 0)
    put = max(0, min(have, amount))
    room["players"][pid]["stack"] = have - put
    st["committed"][pid] = st["committed"].get(pid, 0) + put
    st["street_bet"][pid] = st["street_bet"].get(pid, 0) + put
    st["pots"][0]["amount"] += put
    if room["players"][pid]["stack"] <= 0 and pid not in st["allin"]:
        st["allin"].append(pid)


def _pk_to_match(room: dict, pid: str) -> int:
    st = room["mode_state"]
    return max(0, st["current_bet"] - st["street_bet"].get(pid, 0))


def _pk_bet_size(room: dict) -> int:
    return PK_SMALL if room["mode_state"]["street"] in ("preflop", "flop") else PK_BIG


def _pk_next_actor(room: dict):
    """Advance actor to next live player; None if betting round is closed."""
    st = room["mode_state"]
    order = st["order"]
    live = [p for p in order if _pk_live(st, p)]
    if len([p for p in order if p in st["hole"] and p not in st["folded"]]) <= 1:
        st["actor"] = None
        return
    if not live:
        st["actor"] = None
        return
    start = order.index(st["actor"]) if st.get("actor") in order else -1
    for k in range(1, len(order) + 1):
        cand = order[(start + k) % len(order)]
        if not _pk_live(st, cand):
            continue
        if cand in st["acted"] and _pk_to_match(room, cand) <= 0:
            continue
        st["actor"] = cand
        return
    st["actor"] = None


def _pk_apply(room: dict, pid: str, action: str):
    """Apply one betting action. Returns (ok, error)."""
    st = room["mode_state"]
    if st.get("phase") != "betting" or st.get("actor") != pid:
        return False, "not your turn"
    if action == "fold":
        st["folded"].append(pid)
        st["acted"].append(pid)
        _broadcast(room, "player.folded", {"by": room["players"][pid]["name"]})
    elif action == "check":
        if _pk_to_match(room, pid) > 0:
            return False, "must call or fold"
        st["acted"].append(pid)
    elif action in ("call", "bet"):
        need = _pk_to_match(room, pid)
        if action == "bet":
            if st.get("raises", 0) >= 3:
                action = "call"  # capped: 3 raises per street, then call-only
            else:
                need += _pk_bet_size(room)
        if need <= 0 and action == "call":
            st["acted"].append(pid)
        else:
            had = _pk_to_match(room, pid)
            _pk_post(room, pid, need)
            if action == "bet" and _pk_to_match(room, pid) <= 0 and need > had:
                st["current_bet"] = st["street_bet"][pid]
                st["raises"] = st.get("raises", 0) + 1
                st["acted"] = [pid]
            else:
                st["acted"].append(pid)
            if room["players"][pid]["stack"] <= 0 and pid not in st["acted"]:
                st["acted"].append(pid)
        _broadcast(room, "player.bet", {"by": room["players"][pid]["name"],
                                       "action": action})
    else:
        return False, "unknown action"
    if len([p for p in st["order"] if p in st["hole"] and p not in st["folded"]]) <= 1:
        _pk_award_uncontested(room)
        return True, ""
    _pk_next_actor(room)
    if st.get("actor") is None:
        _pk_next_street(room)
    else:
        st["deadline_at"] = _now() + 90
    _pk_drive(room)
    return True, ""


def _pk_award_uncontested(room: dict):
    st = room["mode_state"]
    champ = next(p for p in st["order"] if p in st["hole"] and p not in st["folded"])
    total = sum(p["amount"] for p in st["pots"])
    room["players"][champ]["score"] += total
    room["players"][champ]["stack"] += total
    _record_win(room, champ)
    st["winners"] = [{"name": room["players"][champ]["name"], "amount": total,
                      "hand": "everyone else folded"}]
    st["phase"] = "showdown"
    st["actor"] = None
    st["deadline_at"] = None
    _broadcast(room, "hand.won", {"winner": room["players"][champ]["name"],
                                 "amount": total, "uncontested": True})


def _pk_next_street(room: dict):
    st = room["mode_state"]
    order = st["order"]
    if len([p for p in order if p in st["hole"] and p not in st["folded"]]) <= 1:
        _pk_award_uncontested(room)
        return
    flow = ["preflop", "flop", "turn", "river"]
    nxt = flow[flow.index(st["street"]) + 1] if st["street"] in flow[:3] else None
    if nxt is None:
        _pk_showdown(room)
        return
    st["street"] = nxt
    take = {"flop": 3, "turn": 1, "river": 1}[nxt]
    for _ in range(take):
        if st["deck"]:
            st["community"].append(st["deck"].pop())
    st["street_bet"] = {pid: 0 for pid in order}
    st["current_bet"] = 0
    st["acted"] = []
    st["raises"] = 0
    btn = order.index(st["button"])
    st["actor"] = None
    for k in range(1, len(order) + 1):
        cand = order[(btn + k) % len(order)]
        if _pk_live(st, cand):
            st["actor"] = cand
            break
    st["deadline_at"] = _now() + 90
    _broadcast(room, "street.dealt", {"mode": "poker", "street": nxt,
                                     "community": st["community"]})
    if st.get("actor") is None:
        _pk_next_street(room) if nxt != "river" else _pk_showdown(room)
    else:
        _pk_drive(room)


def _pk_showdown(room: dict):
    st = room["mode_state"]
    st["street"] = "showdown"
    st["phase"] = "showdown"
    st["actor"] = None
    st["deadline_at"] = None
    contenders = [p for p in st["order"] if p in st["hole"] and p not in st["folded"]]
    scores = {p: _pk_best(st["hole"][p] + st["community"]) for p in contenders}
    # side pots: peel contribution tiers
    contrib = {p: st["committed"].get(p, 0) for p in st["order"] if p in st["hole"]}
    tiers = sorted(set(contrib.values()))
    prev, winners = 0, []
    for tier in tiers:
        if tier <= 0:
            continue
        amount = sum(min(max(0, contrib[p] - prev), tier - prev)
                     for p in contrib if contrib[p] > prev)
        if amount <= 0:
            prev = tier
            continue
        eligible = [p for p in contenders if contrib[p] >= tier]
        if not eligible:
            prev = tier
            continue
        best = max(scores[p] for p in eligible)
        champs = [p for p in eligible if scores[p] == best]
        share, odd = divmod(amount, len(champs))
        for i, p in enumerate(champs):
            take = share + (1 if i < odd else 0)
            room["players"][p]["stack"] += take
            room["players"][p]["score"] += take
            _record_win(room, p)
            winners.append({"name": room["players"][p]["name"], "amount": take,
                            "hole": st["hole"][p]})
        prev = tier
    st["winners"] = winners
    _broadcast(room, "hand.showdown",
               {"winners": [w["name"] for w in winners],
                "community": st["community"]})


def _pk_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st.get("phase") == "betting":
        if st.get("actor") and reason == "timeout":
            _pk_apply(room, st["actor"],
                      "fold" if _pk_to_match(room, st["actor"]) > 0 else "check")
        elif st.get("actor"):
            _pk_next_street(room)
        else:
            _pk_next_street(room)
    else:
        if _pack_quota_met(room):
            _pack_next(room)
            return
        _pk_start_hand(room)


def _pk_input(room: dict, player: dict, data: dict):
    kind = data.get("kind")
    if kind in ("check", "call", "bet", "fold"):
        ok, err = _pk_apply(room, player["id"], kind)
        return {"ok": ok, **({"error": err} if not ok else {})}
    return {"ok": False, "error": "unknown input"}


def _pk_bot_strength(hole, community):
    """Rough 0..1 hand strength for the bot policy."""
    if not community:
        a, b = sorted((PK_RANKS.index(c[0]) for c in hole), reverse=True)
        pair = 0.85 if a == b else 0.0
        hi = (a / 12.0) * 0.5 + (0.15 if b >= 8 else 0.0)
        suited = 0.08 if hole[0][1] == hole[1][1] else 0.0
        gap = max(0, 0.06 - 0.02 * (a - b - 1)) if a != b else 0.0
        return min(1.0, pair + hi + suited + gap)
    score = _pk_best(hole + community)
    return min(1.0, 0.15 + score[0] / 8.0 * 0.85)


def _pk_bot_act(room: dict, pid: str):
    import random as _r
    st = room["mode_state"]
    rng = _r.Random(hash((room["code"], st["hand"], pid)) % (2 ** 31))
    s = _pk_bot_strength(st["hole"][pid], st["community"])
    need = _pk_to_match(room, pid)
    pot = sum(p["amount"] for p in st["pots"])
    if need <= 0:
        if s > 0.62 or rng.random() < 0.12:
            _pk_apply(room, pid, "bet")
        else:
            _pk_apply(room, pid, "check")
    else:
        odds = need / max(1, pot + need)
        if s > 0.7 or (s > 0.45 and odds < 0.25) or rng.random() < 0.08:
            _pk_apply(room, pid, "call" if rng.random() > 0.15 and s < 0.8 else "bet")
        else:
            _pk_apply(room, pid, "fold")


def _pk_drive(room: dict):
    """Bots never stall: act synchronously while action is on a bot."""
    st = room["mode_state"]
    guard = 0
    while st.get("phase") == "betting" and st.get("actor"):
        pid = st["actor"]
        if not room["players"].get(pid, {}).get("bot"):
            return
        if pid not in st.get("hole", {}) or pid in st.get("folded", []):
            _pk_next_actor(room)
            if st.get("actor") is None:
                _pk_next_street(room)
                continue
            else:
                guard += 1
                if guard > 20:
                    return
                continue
        _pk_bot_act(room, pid)
        guard += 1
        if guard > 20:
            return


def _pk_controller(room: dict, player: dict) -> dict:
    st = room["mode_state"]
    out: dict = {"screen": "wait", "components": []}
    if st.get("phase") in (None, "lobby"):
        out["screen"] = "wait"
        out["components"] = [{"type": "text", "text": "Waiting for the deal…"}]
        return out
    if st.get("phase") == "showdown":
        lines = ", ".join(f"{w['name']} +{w['amount']}" for w in st.get("winners", []))
        out["screen"] = "scores"
        out["components"] = [{"type": "text", "text": f"Hand over: {lines or 'split'}. Host deals again."}]
        return out
    hole = (st.get("hole") or {}).get(player["id"], [])
    yours = "your cards: " + (" ".join(hole) if hole else "(sitting out)")
    pub = (f"{st.get('street', '').upper()} · pot {sum(p['amount'] for p in st['pots'])} · "
           f"board {' '.join(st.get('community', [])) or '—'}")
    if st.get("actor") == player["id"]:
        need = _pk_to_match(room, player["id"])
        size = _pk_bet_size(room)
        comps = [{"type": "text", "text": yours},
                 {"type": "text", "text": pub + f" · to call {need} · your stack {player.get('stack', 0)}"}]
        if need <= 0:
            comps.append({"type": "button", "id": "pk-check", "label": "CHECK"})
        else:
            comps.append({"type": "button", "id": "pk-call", "label": f"CALL {need}"})
        comps.append({"type": "button", "id": "pk-bet",
                      "label": f"{'RAISE' if need > 0 else 'BET'} {size if need <= 0 else need + size}"})
        comps.append({"type": "button", "id": "pk-fold", "label": "FOLD"})
        out["screen"] = "vote"
        out["components"] = comps
        return out
    folded = " (you folded)" if player["id"] in st.get("folded", []) else ""
    out["screen"] = "wait"
    out["components"] = [{"type": "text", "text": yours + folded},
                         {"type": "text", "text": pub}]
    return out


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
                    st["entries"][pid] = (
                        _pi_line("freeze-night",
                                 f"Prompt: {st.get('prompt','')}", pid)
                        or _fz_bot_pick(rng, deck, used))
            if len(st["entries"]) >= len(_fz_players(room)) and _fz_players(room):
                _fz_reveal(room)
                _fz_bots_act(room, "vote")
    elif stage == "vote" and st["phase"] == "voting":
        opts = _fz_assembled(room)
        for pid in bots:
            if pid in st["votes"]:
                continue
            mine = [i for i, _ in enumerate(opts)
                    if st["order"][i] != pid] or [0]
            if st["kind"] == "last-lash":
                st["votes"][pid] = sorted(mine)[:3] or [0]
            else:
                st["votes"][pid] = [rng.choice(mine)]
        if len(st["votes"]) >= len(_fz_players(room)) and _fz_players(room):
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
        if len(st["wheel"]["verdicts"]) >= len(_fz_players(room)) and _fz_players(room):
            st["wheel"]["verdicts"]  # scored via normal input path on next touch
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
    return list(room["players"].keys())


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
        _broadcast(room, "entry.accepted", {"by": player["name"],
                                            "count": len(st["entries"]),
                                            "needed": len(_fz_players(room))})
        if len(st["entries"]) >= len(_fz_players(room)) and _fz_players(room):
            _fz_reveal(room)
        return {"ok": True}
    if kind == "vote":
        if phase != "voting":
            return {"ok": False, "error": "not voting now"}
        try:
            choice = int(data.get("choice"))
        except Exception:
            return {"ok": False, "error": "bad choice"}
        opts = _fz_assembled(room)
        if choice < 0 or choice >= len(opts):
            return {"ok": False, "error": "bad choice"}
        if st["order"][choice] == player["id"] and not st["kind"] == "last-lash":
            # last-lash allows stacking on anyone (even self); prompt rounds don't
            return {"ok": False, "error": "no self-votes"}
        if st["kind"] == "last-lash":
            votes = data.get("choices")
            if not isinstance(votes, list) or not votes:
                votes = [choice]
            mine = []
            for v in votes[:3]:
                try:
                    v = int(v)
                except Exception:
                    continue
                if 0 <= v < len(opts):
                    mine.append(v)
            if not mine:
                return {"ok": False, "error": "bad choices"}
            st["votes"][player["id"]] = mine
        else:
            st["votes"][player["id"]] = [choice]
        _broadcast(room, "vote.accepted", {"by": player["name"],
                                           "count": len(st["votes"])})
        if len(st["votes"]) >= len(_fz_players(room)) and _fz_players(room):
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
    st["deadline_at"] = None
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
    if kind == "rite":
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
    st["deadline_at"] = None
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
    if len(w["verdicts"]) >= len(_fz_players(room)) and _fz_players(room):
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
    st["deadline_at"] = None
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
    st["prompt"] = _r.choice(deck["prompts"])
    st["entries"] = {}
    st["secrets"] = {}
    st["votes"] = {}
    st["caught"] = {}
    st["phase"] = "collecting"
    st["reveal"] = False
    st["deadline_at"] = _now() + 90
    _broadcast(room, "round.started", {
        "mode": room["mode"], "deck": deck_id, "round": st["round"],
        "prompt": st["prompt"], "twist": st["twist"],
        "deadline_at": st["deadline_at"]})
    _qc_bots_act(room, "collect")


def _qc_order(room: dict) -> list:
    return list(room["players"].keys())


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
                                            "needed": len(_qc_order(room))})
        if len(st["entries"]) >= len(_qc_order(room)) and _qc_order(room):
            _qc_reveal(room)
        return {"ok": True}
    if kind == "vote":
        if st["phase"] != "voting":
            return {"ok": False, "error": "not voting now"}
        try:
            choice = int(data.get("choice"))
        except Exception:
            return {"ok": False, "error": "bad choice"}
        opts = _qc_assembled(room)
        if choice < 0 or choice >= len(opts):
            return {"ok": False, "error": "bad choice"}
        if _qc_order(room)[choice] == player["id"] and st["twist"] != "liar":
            return {"ok": False, "error": "no self-votes"}
        st["votes"][player["id"]] = [choice]
        _broadcast(room, "vote.accepted", {"by": player["name"],
                                           "count": len(st["votes"])})
        if len(st["votes"]) >= len(_qc_order(room)) and _qc_order(room):
            _qc_score(room)
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
            # fewest votes wins; ties split (lowest shared count)
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
    st["phase"] = "scored"
    st["deadline_at"] = None
    _broadcast(room, "score.updated", {"round": st["round"], "winner": winner_name,
                                       "scores": _public_players(room), **detail})


def _qc_advance(room: dict, reason: str = ""):
    st = room["mode_state"]
    if st["phase"] == "collecting":
        if st["entries"]:
            _qc_reveal(room)
        else:
            _qc_start_round(room, st.get("deck") or "")
    elif st["phase"] == "voting":
        if st["votes"]:
            _qc_score(room)
        else:
            st["phase"] = "scored"
            _qc_start_round(room, st.get("deck") or "")
    elif st["phase"] == "scored":
        _qc_start_round(room, st.get("deck") or "")
    else:
        _qc_start_round(room, st.get("deck") or "")


def _qc_bots_act(room: dict, stage: str):
    """Deck bots: entries from the bot lines, votes random non-self
    (liar: random suspect). Synchronous — bots never stall."""
    st = room["mode_state"]
    if room.get("mode_state") is None or st.get("phase") == "scored":
        return
    import random as _r
    rng = _r.Random(hash(room["code"]) % (2 ** 31) + st.get("round", 0))
    bots = [pid for pid in _qc_order(room) if room["players"][pid].get("bot")]
    if not bots:
        return
    if stage == "collect" and st["phase"] == "collecting":
        for pid in bots:
            if pid not in st["entries"]:
                used = set(st["entries"].values())
                avail = [l for l in QC_BOT_LINES if l not in used] or QC_BOT_LINES
                st["entries"][pid] = (
                    _pi_line("quip", f"Prompt: {st.get('prompt','')}", pid)
                    or rng.choice(avail))
                if st["twist"] == "liar":
                    st["secrets"][pid] = rng.choice([True, False])
        if len(st["entries"]) >= len(_qc_order(room)) and _qc_order(room):
            _qc_reveal(room)
    elif stage == "vote" and st["phase"] == "voting":
        opts = _qc_assembled(room)
        for pid in bots:
            if pid in st["votes"]:
                continue
            if st["twist"] == "liar":
                mine = list(range(len(opts))) or [0]
            else:
                mine = [i for i in range(len(opts))
                        if _qc_order(room)[i] != pid] or [0]
            st["votes"][pid] = [rng.choice(mine)]
        if len(st["votes"]) >= len(_qc_order(room)) and _qc_order(room):
            _qc_score(room)


def _ella_callback(room: dict) -> str | None:
    """Ella narrates the lore: rivalries get called out on stage.
    Rookies get silence — callbacks are earned, not given."""
    for line in room.get("lore") or []:
        if line.startswith("rivalry:"):
            return f"ELLA: {line}. Settle it on stage."
    return None


def _pack_quota_met(room: dict) -> bool:
    pack = room.get("pack")
    if not pack:
        return False
    st = room.get("mode_state") or {}
    return st.get("round", 0) >= pack.get("rounds_each", 2)


def _start_mode(room: dict, mode: str, target: str = ""):
    room["mode"] = mode
    MODES[mode]["create"](room)
    if mode == "freaktionary":
        _mq_start_round(room)
    elif mode == "freeze-night":
        _fz_next_round(room)
    elif mode == "stone-face":
        _sf_start_round(room)
    elif mode == "poker":
        _pk_start_hand(room)
    elif mode.startswith("quip-"):
        _qc_start_round(room, MODES[mode].get("deck", "endings"))
    else:
        _rr_start_round(room, target)


def _pack_next(room: dict):
    """Advance the playlist: next mode, or crown the night's winner."""
    pack = room.get("pack") or {}
    pack["idx"] = pack.get("idx", 0) + 1
    modes = pack.get("modes", [])
    if pack["idx"] >= len(modes):
        room["phase"] = "done"
        players = sorted(room["players"].values(),
                         key=lambda p: p["score"], reverse=True)
        room["winner"] = players[0]["freak"] if players else None
        line = (f"ELLA: {room['winner']} takes the night. "
                f"The rest of you were witnesses."
                if room["winner"] else "ELLA: Nobody won. Correct.")
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
    "stone-face": {"title": "STONE FACE", "min": 2, "max": 8,
                   "blurb": "Confess something funny, survive the set without smiling. Solo: bots play.",
                   "create": _sf_create, "input": _sf_input,
                   "advance": _sf_advance},
    "poker": {"title": "POKER NIGHT", "min": 2, "max": 8,
              "blurb": "Fixed-limit Hold'em. Secret hole cards, real side pots. Solo: bots play.",
              "create": _pk_create, "input": _pk_input,
              "advance": _pk_advance},
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
    if room["mode"] == "stone-face":
        base.update(_sf_controller(room, player))
        return base
    if room["mode"] == "poker":
        base.update(_pk_controller(room, player))
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
            if st.get("twist") == "liar":
                comps.append({"type": "toggle", "id": "truth",
                              "label": "TRUE (unticked = LIE)"})
            comps.append({"type": "submit", "label": "SEND IT"})
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
                 "options": [{"id": str(c["i"]), "text": c["text"]} for c in opts]}]
        else:
            base["screen"] = "scores"
            base["components"] = [
                {"type": "text", "text": "Scores below. Host advances."}]
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
                {"type": "text",
                 "text": "Callback? Optional event id for x1.5 (see stage archive). Leave blank if none."},
                {"type": "textarea", "id": "callback", "max_length": 64},
                {"type": "submit", "label": "SEND IT"}]
        return out
    if st["phase"] == "voting":
        opts = _fz_assembled(room)
        out["screen"] = "vote"
        out["components"] = [
            {"type": "choice", "id": "winner",
             "action": {"kind": "vote", "as": "choice",
                       "multi": 3 if st["kind"] == "last-lash" else 1},
             "options": [{"id": str(c["i"]), "text": c["text"]} for c in opts]},
            {"type": "button", "id": "caught", "label": "I CAUGHT THAT"}]
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
            others = [p for p in room["players"] if p != player["id"]]
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
    elif str(room["mode"] or "").startswith("quip-"):
        out["quip"] = {
            "deck": st.get("deck"), "round": st.get("round"),
            "twist": st.get("twist"), "phase": st["phase"],
            "prompt": st.get("prompt"),
            "options": _qc_assembled(room) if st.get("reveal") else [],
            "submitted": len(st["entries"]), "needed": len(room["players"]),
            "secrets": ({room["players"][pid]["name"]: v
                         for pid, v in (st.get("secrets_revealed") or {}).items()
                         if pid in room["players"]}
                        if st["phase"] == "scored" else None),
            "deadline_at": st.get("deadline_at")}
    elif room["mode"] == "stone-face":
        out["stone-face"] = {
            "round": st["round"], "phase": st["phase"],
            "set": st.get("set") or [],
            "line_i": st.get("line_i", 0),
            "current": (st["set"][st["line_i"]]
                        if st.get("set") and st.get("line_i", 0) < len(st["set"])
                        else None),
            "cracked": [{"name": room["players"][pid]["name"],
                         "at_line": (st["cracked"][pid] + 1)}
                        for pid in st.get("crack_order", [])
                        if pid in room["players"]],
            "survivors": ([room["players"][pid]["name"]
                           for pid in _sf_survivors(room)]
                          if st["phase"] == "scored" else None),
            "submitted": len(st["infos"]), "needed": len(room["players"]),
            "deadline_at": st.get("deadline_at")}
    elif room["mode"] == "poker":
        st = room["mode_state"]
        out["poker"] = {
            "hand": st.get("hand", 0), "street": st.get("street"),
            "phase": st.get("phase"), "community": st.get("community", []),
            "pot": sum(p["amount"] for p in st.get("pots", [])),
            "actor": (room["players"][st["actor"]]["name"]
                      if st.get("actor") in room["players"] else None),
            "folded": [room["players"][p]["name"] for p in st.get("folded", [])
                       if p in room["players"]],
            "stacks": {room["players"][p]["name"]: room["players"][p].get("stack", 0)
                       for p in room["players"]},
            "winners": st.get("winners", []),
            "deadline_at": st.get("deadline_at")}
    elif room["mode"] == "freeze-night":
        out["freeze-night"] = {
            "round": st["round_id"], "kind": st["kind"], "phase": st["phase"],
            "prompt": st.get("prompt"),
            "options": _fz_assembled(room) if st.get("reveal") else [],
            "submitted": len(st["entries"]), "needed": len(room["players"]),
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
                _mq_bots_act(room, "start")
            elif mode == "freeze-night":
                _fz_next_round(room)
            elif mode == "stone-face":
                _sf_start_round(room)
            elif mode == "poker":
                _pk_start_hand(room)
            elif mode.startswith("quip-"):
                _qc_start_round(room, data.get("deck") or MODES[mode].get("deck", "endings"))
            else:
                _rr_start_round(room, data.get("target", ""))
                _rr_bots_act(room, "collect")
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
        if cmd == "bots":
            # seat AI contestants (solo-vs-agents). Works in lobby or mid-night.
            try:
                n = max(1, min(7, int(data.get("n", 3))))
            except Exception:
                n = 3
            free = MAX_PLAYERS - len(room["players"])
            n = max(0, min(n, free))
            if room.get("mode") not in (None, "freeze-night", "stone-face", "poker", "roast-relay", "freaktionary") and not str(room.get("mode") or "").startswith("quip-"):
                return jsonify({"ok": False, "error": "bots need freeze-night, stone-face, poker, roast-relay, freaktionary or quip games"}), 400
            before = set(room["players"])
            made = _fz_add_bots(room, n)
            # _fz_add_bots returns display names; resolve to player ids.
            made_pids = [pid for pid in room["players"] if pid not in before]
            if room["phase"] == "playing":
                st = room["mode_state"]
                if st.get("phase") == "collecting":
                    if str(room.get("mode") or "").startswith("quip-"):
                        _qc_bots_act(room, "collect")
                    elif room.get("mode") == "stone-face":
                        _sf_bots_act(room, "collect")
                    elif room.get("mode") == "roast-relay":
                        _rr_bots_act(room, "collect")
                    elif room.get("mode") == "freaktionary":
                        _mq_bots_act(room, "start")
                    else:
                        _fz_bots_act(room, "collect")
                elif st.get("phase") in ("voting", "drawing"):
                    if room.get("mode") == "roast-relay":
                        _rr_bots_act(room, "vote")
                    elif room.get("mode") == "freaktionary":
                        _mq_bots_act(room, "guess")
                elif room.get("mode") == "poker":
                    for pid in made_pids:
                        room["players"][pid]["stack"] = PK_STACK
                    _pk_drive(room)
            else:
                for pid in made_pids:
                    if room["players"][pid].get("stack", 0) <= 0:
                        room["players"][pid]["stack"] = PK_STACK
            return jsonify({"ok": True, "bots": made})
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


@party_bp.route("/party/<code>/harness", methods=["POST"])
def harness_party_input(code):
    """Trusted upstream harness extension relay; event output is PUBLIC.

    This endpoint does not run, or charge for, any model. A room host token
    is required. No conversation history, mic audio or user memories accepted.
    """
    room = _get_room(code)
    if not room:
        return jsonify({"ok": False, "error": "no such room"}), 404
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not _is_host(room, data.get("host_token", "")):
        return jsonify({"ok": False, "error": "not host"}), 403
    actor = _clean(data.get("actor", ""), 48)
    text = _clean(data.get("text", ""), 400)
    raw = data.get("beats", [])
    if not actor or not text or not isinstance(raw, list) or len(raw) > 16:
        return jsonify({"ok": False, "error": "invalid actor, text or beats"}), 400
    from harness_adapter import EMOTIONS, GESTURES, CAMERAS
    beat_list = []
    for b in raw:
        if not isinstance(b, dict):
            return jsonify({"ok": False, "error": "invalid beat"}), 400
        e, g, c = b.get("emotion"), b.get("gesture"), b.get("camera")
        if (e and e not in EMOTIONS or g and g not in (*GESTURES, "none")
                or c and c not in (*CAMERAS, "none", "hold")):
            return jsonify({"ok": False, "error": "invalid acting vocabulary"}), 400
        beat_list.append({"span": _clean(b.get("span", ""), 120),
                          "emotion": e or "", "gesture": g or "none",
                          "camera": c or "none", "register": _clean(b.get("register", ""), 24)})
    with LOCK:
        if room["phase"] != "playing":
            return jsonify({"ok": False, "error": "room not playing"}), 409
        room["seq"] += 1
        # Volatile public stream only. No disk log, no player secrets.
        ev = {"seq": room["seq"], "kind": "character.act", "t": _now(),
              "actor": actor, "text": text, "beats": beat_list}
        room["events"].append(ev)
        room["events"] = room["events"][-500:]
    return jsonify({"ok": True, "seq": ev["seq"]})


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
        if data.get("kind") == "smile":
            # Explicit camera opt-in happens client-side. Accept a boolean
            # ONLY; no frames, landmarks, probabilities or calibration data.
            if data.get("smiling") is not True:
                return jsonify({"ok": False, "error": "expected smiling=true"}), 400
            now = _now()
            if now - p.get("_last_smile", 0) < 3:
                return jsonify({"ok": False, "error": "smile cooldown"}), 429
            p["_last_smile"] = now
            room["seq"] += 1
            ev = {"seq": room["seq"], "kind": "smile.detected", "t": now,
                  "by": p["name"], "acting": party_reaction("smile.detected", smiling=True)}
            room["events"].append(ev)
            room["events"] = room["events"][-500:]
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
        room["_seen_at"] = _now()  # someone is watching (chatter viewer gate)
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
<div id=acting style='min-height:24px;color:#ffb7dc;font-size:13px' aria-live=polite></div>
<div id=scores></div>
<div id=host style='margin:12px'>
<button onclick="hostCmd('lock')">LOCK</button>
<button onclick="hostCmd('start','freeze-night')">START FREEZE NIGHT</button>
<button onclick="hostCmd('advance')">ADVANCE ➜</button>
<button onclick="hostCmd('bots','')">+3 BOTS</button>
<span id=hmsg style='color:#888;font-size:12px'></span>
<div id=decks style='margin-top:8px;font-size:12px'></div></div>
<script>
const HOST_KEY = 'ft_host___CODE__';
let hostToken = '';
try{ hostToken = localStorage.getItem(HOST_KEY) || ''; }catch(e){}
async function hostCmd(cmd, mode){
  const body = {host_token: hostToken, cmd};
  if(mode) body.mode = mode;
  if(cmd === 'bots'){ body.n = 3; }
  try{
    const r = await fetch('/party/__CODE__/host',{method:'POST',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    const d = await r.json();
    document.getElementById('hmsg').textContent = d.ok ? (cmd+' ok') : ('ERR: '+(d.error||'?'));
  }catch(e){ document.getElementById('hmsg').textContent = 'ERR: offline'; }
}
const DECKS = ['endings','walkins','objects','least-funny','wrong-answers','lies','monologues','dubs','eulogies','lyrics','nonsense'];
document.getElementById('decks').innerHTML = DECKS.map(d=>
  "<button style='font-size:11px;padding:6px 10px' onclick=\"hostCmd('start','quip-"+d+"')\">"+d+"</button>").join(' ');
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
      if(ev.kind === 'character.react' || ev.kind === 'smile.detected' || ev.kind === 'character.act'){
        const mood = ev.acting && ev.acting.emotion;
        const who = ev.kind === 'smile.detected' ? (ev.by+' smiled') :
          (ev.kind === 'character.act' ? ev.actor+': '+ev.text : 'host reacted');
        document.getElementById('acting').textContent = who + (mood ? ' · '+mood : '');
      }
      if(ev.kind === 'chat'){
        document.getElementById('acting').textContent =
          (ev.by||'bot') + ': ' + (ev.text||'');
      }
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
  } else if(s['freeze-night']){
    renderFreeze(s['freeze-night'], s, cap, sc);
    return;
  } else if(s['quip']){
    renderQuip(s['quip'], s, cap, sc);
    return;
  }
  sc.textContent = (s.scores||[]).map(p=>p.name+': '+p.score).join(' · ');
}
function countdown(dl){ if(!dl) return ''; const s2=Math.max(0,Math.round(dl-Date.now()/1000));
  return s2 ? (' · ⏱'+s2+'s') : ''; }
function renderQuip(q, s, cap, sc){
  const cap2 = document.getElementById('cap'), sc2 = document.getElementById('scores');
  const board = (s.scores||[]).map(p=>escapeHtml(p.name)+': '+p.score).join(' · ');
  if(q.phase === 'collecting'){
    cap2.textContent = (q.prompt||'') + ' (' + q.submitted + '/' + q.needed + ')' + countdown(q.deadline_at);
    sc2.textContent = board; return;
  }
  if(q.phase === 'voting'){
    cap2.textContent = (q.twist === 'liar' ? 'WHO IS LYING?' : (q.prompt||'')) + countdown(q.deadline_at);
    sc2.innerHTML = (q.options||[]).map(c=>'<div>“'+escapeHtml(c.text)+'”</div>').join('')
      + '<div>' + board + '</div>';
    return;
  }
  cap2.textContent = 'round ' + (q.round||'');
  let extra = '';
  if(q.secrets){ extra = '<div>' + Object.entries(q.secrets).map(([name,v])=>escapeHtml(name)+': '+(v?'TRUE':'LIE')).join(' · ') + '</div>'; }
  sc2.innerHTML = extra + '<div>' + board + '</div>';
}
function renderFreeze(f, s, cap, sc){
  const cap2 = document.getElementById('cap'), sc2 = document.getElementById('scores');
  const board = (s.scores||[]).map(p=>escapeHtml(p.name)+': '+p.score).join(' · ');
  if(f.phase === 'done'){
    cap2.textContent = 'NIGHT OVER — champion crowned';
    sc2.innerHTML = board; return;
  }
  if(f.phase === 'collecting'){
    cap2.textContent = (f.prompt||'') + ' (' + f.submitted + '/' + f.needed + ')' + countdown(f.deadline_at);
    sc2.textContent = board; return;
  }
  if(f.phase === 'voting'){
    cap2.textContent = (f.prompt||'') + countdown(f.deadline_at);
    sc2.innerHTML = (f.options||[]).map(c=>'<div>“'+escapeHtml(c.text)+'”</div>').join('')
      + '<div>' + board + '</div>';
    return;
  }
  if(f.phase === 'passfail' || f.phase === 'author'){
    cap2.textContent = (f.ritual_victim||'?') + ' performs…' + countdown(f.deadline_at);
    sc2.innerHTML = (f.ritual_line ? '<div>“'+escapeHtml(f.ritual_line)+'”</div>' : '')
      + '<div>' + board + '</div>';
    return;
  }
  if(f.phase === 'verdict'){
    cap2.textContent = 'WHEEL: ' + (f.wheel.victim||'?') + ' — ' + (f.wheel.segment||'…');
    sc2.innerHTML = '<div>' + board + '</div>';
    return;
  }
  cap2.textContent = (f.round||'') + countdown(f.deadline_at);
  sc2.innerHTML = '<div>archive: ' + (f.archive||0) + ' events · callbacks caught: '
    + Object.keys(f.recognized||{}).length + '</div><div>' + board + '</div>';
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
<div style='margin:12px auto;max-width:520px'>
<button id=smile-toggle onclick='toggleSmile()'>ENABLE CAMERA SMILES (OPTIONAL)</button>
<div id=smile-msg style='font-size:12px;color:#aaa'>Local detection; only yes/no smile events leave this device.</div>
<video id=smile-video muted autoplay playsinline style='display:none;width:120px'></video>
</div>
<script src='/static/smile-referee.js'></script>
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
    if(c.type === 'toggle'){ const lab=document.createElement('label');
      lab.style.display='block'; lab.style.margin='8px';
      const cb=document.createElement('input'); cb.type='checkbox'; cb.id='fld_'+c.id;
      lab.appendChild(cb); lab.appendChild(document.createTextNode(' '+(c.label||c.id)));
      b.appendChild(lab); }
    if(c.type === 'submit'){ const btn=document.createElement('button'); btn.className='big';
      btn.textContent=c.label||'SEND'; btn.onclick=()=>submit(c); b.appendChild(btn); }
    if(c.type === 'button'){ const btn=document.createElement('button');
      btn.textContent=c.label||c.id; btn.onclick=()=>press(c.id); b.appendChild(btn); }
    if(c.type === 'choice'){ const act = c.action || {kind:'vote', as:'choice'};
      if((act.multi||1) > 1){ // last-lash: tap up to N, then send
        const sel = [];
        (c.options||[]).forEach(o=>{ const btn=document.createElement('button');
          btn.className='opt'; btn.textContent=o.text;
          btn.onclick=()=>{ const ix=sel.indexOf(o.id);
            if(ix>=0){ sel.splice(ix,1); btn.style.borderColor='#333'; }
            else if(sel.length < act.multi){ sel.push(o.id); btn.style.borderColor='#ff2fa8'; } };
          b.appendChild(btn); });
        const send=document.createElement('button'); send.className='big';
        send.textContent='SEND VOTES ('+act.multi+' max)';
        send.onclick=()=>sendInput(act.kind, {[act.as==='choice'?'choices':act.as]: sel});
        b.appendChild(send);
      } else { (c.options||[]).forEach(o=>{ const btn=document.createElement('button');
        btn.className='opt'; btn.textContent=o.text;
        btn.onclick=()=>sendInput(act.kind, {[act.as]: o.id}); b.appendChild(btn); }); } }
    if(c.type === 'canvas'){ const cv=document.createElement('canvas'); cv.id='draw';
      cv.width=520; cv.height=340; b.appendChild(cv); wireDraw(cv); }
  });
}
function titleFor(v){
  if(v.screen==='lobby') return 'LOBBY';
  if(v.screen==='drawer') return 'DRAW: ' + (v.secret||'');
  if(v.screen==='vote') return 'VOTE WINNER';
  if(v.screen==='perform') return 'PERFORM';
  if(v.screen==='scores') return 'SCORES';
  if(v.screen==='reveal') return 'REVEAL';
  if(v.screen==='audience') return 'AUDIENCE';
  return v.mode ? v.mode.toUpperCase() : 'FREAK TOWN';
}
async function submit(c){
  const areas = Array.from(document.querySelectorAll('textarea'));
  const get = id => { const el = document.getElementById(id); return el ? el.value : ''; };
  const first = areas.length ? areas[0].id : '';
  const kind = first === 'fld_guess' ? 'guess' : (first === 'fld_line' ? 'line' : (first === 'fld_info' ? 'info' : 'entry'));
  const extra = {text: get(first) || (areas.length ? areas[0].value : '')};
  const cb = get('fld_callback');
  if(cb && cb.trim()) extra.callback = cb.trim();
  const tg = document.querySelector('input[type=checkbox][id^=fld_]');
  if(tg) extra[tg.id.replace('fld_','')] = tg.checked;
  await sendInput(kind, extra);
  lastScreen = '';
}
async function sendInput(kind, extra){
  const body = Object.assign({seat_token: seat, client_seq: ++cseq, kind}, extra||{});
  await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)});
  lastScreen = '';
}
async function vote(id){
  await sendInput('vote', {choice: String(id)});
}
async function press(id){
  if(id==='ready') await fetch('/party/'+CODE+'/ready',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, ready: true})});
  if(id==='laugh') await fetch('/party/'+CODE+'/input',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({seat_token: seat, client_seq: ++cseq, kind:'laugh'})});
  if(id==='caught'){
    const ev = window.prompt('Which event id did you catch? (see stage archive)');
    if(ev && ev.trim()) await sendInput('caught', {event: ev.trim()});
  }
  if(id==='cracked') await sendInput('crack', {});
  if(id==='pk-check') await sendInput('check', {});
  if(id==='pk-call') await sendInput('call', {});
  if(id==='pk-bet') await sendInput('bet', {});
  if(id==='pk-fold') await sendInput('fold', {});
}
let smileStream = null, smileRef = null, smilePoll = null;
let smileWasHigh = false;
function loadScript(url){
  return new Promise((resolve,reject)=>{const s=document.createElement('script');
    s.src=url; s.onload=resolve; s.onerror=reject; document.head.appendChild(s);});
}
async function toggleSmile(){
  const msg=document.getElementById('smile-msg');
  const btn=document.getElementById('smile-toggle');
  if(smileStream){
    clearInterval(smilePoll); smilePoll=null;
    smileStream.getTracks().forEach(t=>t.stop()); smileStream=null;
    if(smileRef){smileRef.dispose(); smileRef=null;}
    document.getElementById('smile-video').srcObject=null;
    smileWasHigh=false; btn.textContent='ENABLE CAMERA SMILES (OPTIONAL)';
    msg.textContent='Camera stopped. No frames were sent.';
    return;
  }
  try {
    if(!seat){msg.textContent='Only seated players can enable this option.';return;}
    btn.disabled=true;
    if(typeof tf==='undefined') await loadScript('https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@latest');
    const v=document.getElementById('smile-video');
    smileStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user'},audio:false});
    v.srcObject=smileStream; await v.play(); v.style.display='inline-block';
    msg.textContent='Calibrating: follow neutral/smile prompts.';
    smileRef=await SmileReferee.calibrate(v,{samples:30,ephemeral:true,
      onStep:s=>{ if(s.smiling!==undefined) msg.textContent=s.smiling?'Smile now':'Hold a neutral face'; }});
    const cv=document.createElement('canvas'), ctx=cv.getContext('2d');
    let cooldown=0;
    smilePoll=setInterval(()=>{
      if(!smileRef||!v.videoWidth)return;
      cv.width=v.videoWidth;cv.height=v.videoHeight;ctx.drawImage(v,0,0);
      const p=smileRef.predict(cv), high=p>0.82, now=Date.now();
      if(high && !smileWasHigh && now>cooldown){
        cooldown=now+4000;sendInput('smile',{smiling:true}).catch(()=>{});
      }
      smileWasHigh=high;
      msg.textContent='Camera on · smile detection local · '+(high?'smile':'neutral');
    },350);
    btn.textContent='DISABLE CAMERA SMILES';
  }catch(e){
    if(smileStream){smileStream.getTracks().forEach(t=>t.stop());smileStream=null;}
    msg.textContent='Camera unavailable or declined: '+String(e);
  }finally{btn.disabled=false;}
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
