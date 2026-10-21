"""Proactive table talk — bots that talk between actions (additive).

The owner's ask: playing solo against bots that are ALIVE at the table —
poker hands with table talk, not silent pot-odds machines.

Research note (web search 2026-10-21): Inworld/Convai = metered cloud NPC
APIs (spend); NVIDIA ACE Game Agent SDK = free but needs RTX + engines.
We already have the pieces that matter: a persona-per-seat brain
(party_pi_agents → Qwen), machine-readable legal actions (party_agent_sdk
agentRules), and an SSE stage that renders bot speech. This file adds the
missing layer: a HEARTBEAT that speaks unprompted, between your actions.

Design rules (killella + party lessons):
  - Fail-closed: flag off / no key / model dead → the dry DECK line ($0,
    seeded, deterministic). Tests never touch network.
  - Throttled: one line per PARTY_CHATTER_GAP seconds per room. Silence is
    a feature — a chatty room is worse than a mute one.
  - No secrets: the prompt never carries other players' hole cards or
    hidden roles. Context = public state + own seat only.
  - Fire-and-forget from a daemon thread: never inside the SSE poll, never
    inside game input handling. The room's clock never waits on a model.

Enable: PARTY_CHATTER=1 (in freaktown/.env — the loader below reads it,
same rule as interpret_joke: repo .env overrides the shell).
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
GAP = 6.0          # seconds between lines in one room
TICK = 3.0         # heartbeat resolution
VIEWER_WINDOW = 45.0  # room was polled within this → someone's at the table
MAX_SEEN = 40      # recent-line memory cap per room


def _load_env() -> None:
    envf = BASE / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip()


# ── dry deck ($0, seeded — the default and the test path) ─────────────
DECKS = {
    "poker": [
        "you fold like a suspicious lawn chair.",
        "i only bet when i'm wrong. so, constantly.",
        "that raise smelled like cologne and poor judgment.",
        "i'm not tilting. this IS my baseline.",
        "call me. i dare you. seriously, i need the action.",
        "my stack is a personality test and i'm failing.",
        "everyone at this table plays like they're being watched. they are.",
        "i had the best hand once. didn't believe it.",
    ],
    "freeze-night": [
        "yes, and my patience is freezing with you.",
        "i've seen braver furniture.",
        "the scene is carrying you, don't trip it.",
        "i'd freeze too, honestly.",
    ],
    "_generic": [
        "no pressure or anything.",
        "i came here to win. or sit. mainly sit.",
        "this is going on my highlight reel either way.",
        "bold. questionable. bold.",
        "i respect the confidence. that's all i respect.",
    ],
}


def _deck_line(mode: str, seat: str, seed: int) -> str:
    deck = DECKS.get(mode or "", DECKS["_generic"])
    return random.Random(seed).choice(deck)


def _state_context(room: dict) -> str:
    """Public state only — never hole cards, never hidden roles."""
    st = room.get("mode_state", {}) or {}
    bits = [f"mode={room.get('mode')}", f"phase={st.get('phase', room.get('phase'))}"]
    if room.get("mode") == "poker":
        if st.get("board"):
            bits.append(f"board={len(st['board'])} cards")
        if st.get("pot") is not None:
            bits.append(f"pot={st['pot']}")
        bits.append(f"hand={st.get('hand', '?')}")
    elif st.get("round") is not None:
        bits.append(f"round={st.get('round')}")
    # what just happened (public events tail)
    kinds = [e.get("kind") for e in (room.get("events") or [])[-6:]]
    kinds = [k for k in kinds if k]
    if kinds:
        bits.append("recent=" + ",".join(kinds[-4:]))
    return " · ".join(bits)


def _live_line(mode: str, seat: str, room: dict) -> str | None:
    """Qwen turn. Fail-closed on any miss (caller uses the deck)."""
    if os.environ.get("PARTY_PI_AGENTS", "0") != "1":
        return None
    try:
        import scripts.party_pi_agents as pi
        system = (pi._persona(seat)
                  + " You are AT THE TABLE talking out loud. ONE line, "
                    "<=90 chars, in character. Never reveal anyone's hidden "
                    "information. Never mention being an AI.")
        prompt = (f"Table state: {_state_context(room)}. "
                  f"Say one line of table talk as {seat}.")
        line = pi.agent_line("quip", prompt, seat, system=system)
        return (line or "")[:120] or None
    except Exception:
        return None


def _reserve(room: dict, now: float) -> str | None:
    """Eligibility + slot reservation. NO network — safe under party.LOCK."""
    if os.environ.get("PARTY_CHATTER", "0") != "1":
        return None
    if room.get("phase") != "playing":
        return None
    # viewer gate: only tables someone polls (the box has 400+ restored
    # rooms stuck "playing" — ghosts never pull model calls or starve
    # live tables). Mirrors the _loop eligibility.
    if now - (room.get("_seen_at") or 0.0) > VIEWER_WINDOW:
        return None
    bots = [pid for pid, p in room.get("players", {}).items() if p.get("bot")]
    if not bots:
        return None
    last = room.get("_chatter_at") or 0.0
    if now - last < float(os.environ.get("PARTY_CHATTER_GAP", str(GAP))):
        return None
    room["_chatter_at"] = now  # reserve: next line waits a full gap
    return random.Random(int(now * 1000) + room.get("seq", 0)).choice(bots)


def _produce(room: dict, seat: str) -> tuple[str, bool]:
    """The line itself: (text, live). LIVE model call happens here — NEVER
    under the lock (a slow model would freeze every party API; that was the
    first bug). Deck fallback is instant."""
    line = _live_line(room.get("mode", ""), seat, room)
    if line:
        return line, True
    seq = room.get("seq", 0)
    seen = room.get("_chatter_seen", [])
    return _deck_line(room.get("mode", ""), seat, seq + len(seen)), False


def tick(room: dict) -> dict | None:
    """One chatter opportunity (tests + dry path). Returns {by, text,
    live} to broadcast, or None. Throttled per room."""
    now = time.time()
    seat = _reserve(room, now)
    if not seat:
        return None
    line, live = _produce(room, seat)
    seen = room.setdefault("_chatter_seen", [])
    if line in seen[-3:]:
        return None  # never repeat the last three
    seen.append(line)
    del seen[:-MAX_SEEN]
    return {"by": room["players"][seat].get("name", seat),
            "text": line, "live": live}


# ── heartbeat (daemon; started by app.py, never by tests) ─────────────

_thread: threading.Thread | None = None


def _log(msg: str) -> None:
    print(f"[chatter] {msg}", flush=True)  # journalctl -u freaktown


def _loop() -> None:
    """reserve (under lock, no network) → produce (NO lock, model/deck)
    → broadcast (under lock). The room API never waits on a model.
    Fairness: the room that has waited LONGEST talks next — never 'first
    room in the dict' (a restored playing room used to starve every other)."""
    from party import LOCK, ROOMS, _broadcast
    _log(f"heartbeat on (gap={os.environ.get('PARTY_CHATTER_GAP', str(GAP))}s, "
         f"live={'qwen' if os.environ.get('PARTY_PI_AGENTS') == '1' else 'deck'})")
    while True:
        time.sleep(TICK)
        try:
            job_room = job_seat = None
            with LOCK:
                now = time.time()
                gap = float(os.environ.get("PARTY_CHATTER_GAP", str(GAP)))
                eligible = []
                for room in list(ROOMS.values()):
                    if room.get("phase") != "playing":
                        continue
                    # viewer gate: talk only to tables someone polls. The box
                    # has 400+ restored rooms stuck "playing" — ghosts must
                    # never pull model calls or starve live tables.
                    if now - (room.get("_seen_at") or 0.0) > VIEWER_WINDOW:
                        continue
                    if not any(p.get("bot") for p in room.get("players", {}).values()):
                        continue
                    if now - (room.get("_chatter_at") or 0.0) < gap:
                        continue
                    eligible.append(room)
                if eligible:
                    # waited longest first; fresh rooms (never talked) win ties
                    room = min(eligible, key=lambda r: r.get("_chatter_at") or 0.0)
                    bots = [pid for pid, p in room["players"].items() if p.get("bot")]
                    job_room = room
                    job_seat = random.Random(int(now * 1000) + room.get("seq", 0)).choice(bots)
                    room["_chatter_at"] = now  # reserve under lock
            if job_room is None:
                continue
            line, live = _produce(job_room, job_seat)   # model call, no lock
            with LOCK:
                seen = job_room.setdefault("_chatter_seen", [])
                if job_room.get("phase") != "playing" or line in seen[-3:]:
                    continue
                seen.append(line)
                del seen[:-MAX_SEEN]
                _broadcast(job_room, "chat",
                           {"by": job_room["players"][job_seat].get("name", job_seat),
                            "text": line, "live": live})
            _log(f"{job_room['code']} [{job_room['players'][job_seat].get('name')}] "
                 f"{'LIVE' if live else 'deck'}: {line[:60]}")
        except Exception as e:  # never die, never be silent
            _log(f"ERROR {type(e).__name__}: {e}")


def start_service() -> None:
    """Call once from app.py. No-op when the flag is off (tests, tools)."""
    global _thread
    _load_env()
    if os.environ.get("PARTY_CHATTER", "0") != "1":
        _log("off (PARTY_CHATTER != 1)")
        return
    if _thread:
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="party-chatter")
    _thread.start()
    _log("service starting…")
