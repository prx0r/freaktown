"""Corpus: comedy text → anonymous structural/timing grammar.

We don't care that the punchline said X. We care that the set goes:
setup → acceleration → tiny silence → punch → freeze → laugh → tag.

Output is deliberately ANONYMOUS: beat types, durations, words, mechanisms.
No original text is ever emitted or stored — only how it behaved in time.
"""
from __future__ import annotations

import hashlib
import re

# Word rate bands for timing estimates (comedy speech ≈ 2.4–3.4 wps).
PACE_WPS = 2.9
TURN_WORDS = ("but ", "then ", "so ", "and then ", "except ", "only ")

BEAT_TYPES = ("setup", "turn", "escalation", "punchline", "tag", "callback", "closer")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text).strip())
    return [p.strip() for p in parts if p.strip()]


def _classify(lines: list[str]) -> list[dict]:
    """Rule-based beat tagging. First line = setup, last short = closer,
    pivot words = turn, line after a pivot = punchline candidate."""
    beats = []
    n = len(lines)
    for i, line in enumerate(lines):
        low = line.lower()
        words = len(line.split())
        if i == n - 1 and words <= 15:
            btype = "closer"
        elif i == 0:
            btype = "setup"
        elif any(p in low for p in TURN_WORDS) and i + 1 < n:
            btype = "turn"
        elif i > 0 and any(b["type"] == "turn" for b in beats) and \
                beats[-1]["type"] == "turn":
            btype = "punchline"
        elif words <= 6:
            btype = "tag"
        else:
            btype = "escalation"
        beats.append({"type": btype, "words": words,
                      "duration_ms": int(round(words / PACE_WPS * 1000)),
                      "pace_wps": PACE_WPS})
    # guarantee a punchline exists: strongest escalation before the closer
    if n >= 3 and not any(b["type"] == "punchline" for b in beats):
        idx = n - 2 if beats[-1]["type"] == "closer" else n - 1
        beats[idx]["type"] = "punchline"
    if beats and beats[0]["type"] != "setup":
        beats.insert(0, {"type": "setup", "words": 0, "duration_ms": 0,
                         "pace_wps": PACE_WPS})
    return beats


def _mechanism(text: str, beats: list[dict]) -> str:
    """Which comic mechanism dominates (structural only)."""
    words = re.findall(r"[a-z']+", text.lower())
    seen: dict[str, int] = {}
    for w in words:
        if len(w) > 5:
            seen[w] = seen.get(w, 0) + 1
    if any(v >= 4 for v in seen.values()):
        return "callback"            # a word repeated = running gag
    pivots = sum(1 for b in beats if b["type"] == "turn")
    lengths = [b["words"] for b in beats if b["type"] in ("escalation", "punchline")]
    if len(lengths) >= 3 and lengths[-1] > lengths[0]:
        return "escalation"
    if pivots:
        return "misdirection"
    if all(b["words"] <= 8 for b in beats[1:-1]):
        return "deadpan"
    return "absurd"


def analyze(text: str) -> dict:
    """A written set → ComedyGrammar: mechanism + timed beats. Anonymous."""
    lines = _sentences(text)
    beats = _classify(lines)
    total_words = sum(b["words"] for b in beats)
    return {
        "mechanism": _mechanism(text, beats),
        "beats": beats,
        "total_words": total_words,
        "duration_ms": int(round(total_words / PACE_WPS * 1000)),
        # structural fingerprint only — never the original text
        "source_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
    }


def rhythm_features(grammar: dict) -> dict:
    """Compact features rhythm matching runs on."""
    types = [b["type"] for b in grammar["beats"]]
    lens = [b["words"] for b in grammar["beats"]]
    return {
        "has_punch": "punchline" in types,
        "has_closer": types[-1:] == ["closer"],
        "tags": sum(1 for t in types if t == "tag"),
        "pivots": sum(1 for t in types if t == "turn"),
        "escalating": len(lens) >= 3 and lens[-1] > lens[0],
        "beat_count": len(types),
        "mechanism": grammar["mechanism"],
    }
