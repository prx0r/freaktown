#!/usr/bin/env python3
"""Human-like laugh harness for agent audience members.

Core claim: a laugh must be DELAYED, not random. Humans laugh after the
line lands — comprehension VerboseTimer + social contagion — never at beat
start. This module turns a judge verdict into a timed laugh:

  onset = beat_end_ms + base(250ms) + comprehension((1-confidence)*900ms)
          - contagion(150ms if room laughed in last 5s) + jitter(seeded)

Plus:
  - contagion boost: recent room laughs raise P(laugh) (their crowd
    physics fits recent=0.204 — same direction, honest magnitude noted).
  - big laughs arrive as a BURST: HAHAHA posts twice (onset, onset+900ms).
  - deterministic under a seed (replays), stochastic live.

No model, no keys, stdlib only. Import from agent_audience or use solo.
"""
import hashlib
import random


BASE_MS = 250          # fastest human recognition laugh
COMPREHENSION_MS = 900  # extra wait when the joke barely parses
CONTAGION_MS = 150      # room already laughing -> you go sooner
CONTAGION_WINDOW_MS = 5000
BURST_GAP_MS = 900      # hahaha second post
CONTAGION_BOOST = 0.08  # additive P(laugh) when room is warm


def _rng(*parts) -> random.Random:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def plan_laugh(beat: dict, confidence: float, heat: float,
               room_laughs_ms: list, now_ms: int, seed: str = "") -> dict | None:
    """Decide AND time a laugh. Returns None for silence.

    beat: {start, end, ...} ms on the set clock. now_ms: agent clock.
    room_laughs_ms: recent laugh timestamps the agent has "heard".
    """
    mechs = None  # decision lives with the caller; here: timing + contagion
    warm = any(now_ms - t < CONTAGION_WINDOW_MS for t in room_laughs_ms)
    p_boost = CONTAGION_BOOST if warm else 0.0
    r = _rng(seed, beat.get("start"), confidence)
    delay = BASE_MS + (1.0 - confidence) * COMPREHENSION_MS
    if warm:
        delay = max(120.0, delay - CONTAGION_MS)
    delay += r.uniform(-60, 120)
    onset = beat["end"] + delay
    wait = max(0.0, (onset - now_ms) / 1000.0)
    return {"react_at_ms": int(onset), "wait_s": round(wait, 2),
            "contagion_boost": p_boost, "warm": warm}


PERSONAS = {
    # name: (haha_s, big_s) score bars, s = 0.6*conf + 0.4*heat.
    "normal": (0.54, 0.69),   # v1 rule: laughs at real jokes + heat
    "easy": (0.46, 0.64),     # laughs generously
    "skeptic": (0.69, 0.78),  # needs proof
}


def laugh_types(confidence: float, heat: float, boost: float = 0.0,
                persona: str = "normal"):
    """haha vs HAHAHA from strength. Returns list of (type, offset_ms).

    Boundaries preserve the v1 rule (haha: conf>=0.7 & heat>=0.3;
    hahaha: conf>=0.85 & heat>=0.45) in score space: s=0.6c+0.4h.
    """
    lo, hi = PERSONAS.get(persona, PERSONAS["normal"])
    s = confidence * 0.6 + heat * 0.4 + boost
    if s >= hi:
        return [("hahaha", 0), ("hahaha", BURST_GAP_MS)]
    if s >= lo:
        return [("haha", 0)]
    return []
