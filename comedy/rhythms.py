"""Rhythm archetypes — reusable comedy-performance grammars.

Each rhythm encodes how beats move through time: pauses, holds, laugh
strategy, tag behavior. Matched against a grammar's structure, applied to
delivery by the director. Discovery hook: corpus.rhythm_features() +
reaction events cluster into new archetypes over time (50–200 expected
eventually; seed with the classics).
"""
from __future__ import annotations

from .corpus import rhythm_features

RHYTHMS: dict[str, dict] = {
    "dry_misdirection": {
        "label": "DRY MISDIRECTION",
        "needs": {"has_punch": True, "pivots_min": 1},
        "pace": 1.0,
        "turn_pause_ms": 220,
        "pre_punch_pause_ms": 240,
        "punch_hold_ms": 850,
        "tag_delay_ms": 500,       # tag lands at laugh peak + 500
        "laugh_strategy": "wait_for_peak",
        "close": "deadpan_closer",
    },
    "manic_escalation": {
        "label": "MANIC ESCALATION",
        "needs": {"has_punch": True, "escalating": True},
        "pace": 1.15,
        "turn_pause_ms": 120,
        "pre_punch_pause_ms": 80,
        "punch_hold_ms": 350,
        "tag_delay_ms": 180,       # tags fired early, over the laugh
        "laugh_strategy": "talk_over",
        "close": "hold",
    },
    "awkward_character": {
        "label": "AWKWARD CHARACTER",
        "needs": {"has_punch": True, "beat_count_min": 3},
        "pace": 0.88,
        "turn_pause_ms": 700,
        "pre_punch_pause_ms": 900,  # the long uncomfortable pause
        "punch_hold_ms": 1100,
        "tag_delay_ms": 700,
        "laugh_strategy": "stare_then_tag",
        "close": "long_hold",
    },
    "rapid_tags_v3": {
        "label": "RAPID TAGS",
        "needs": {"has_punch": True, "tags_min": 2},
        "pace": 1.1,
        "turn_pause_ms": 150,
        "pre_punch_pause_ms": 120,
        "punch_hold_ms": 400,
        "tag_delay_ms": 250,
        "laugh_strategy": "rapid_follow",
        "close": "snap",
    },
    "callback_waltz": {
        "label": "CALLBACK WALTZ",
        "needs": {"has_punch": True},
        "pace": 1.02,
        "turn_pause_ms": 260,
        "pre_punch_pause_ms": 300,
        "punch_hold_ms": 650,
        "tag_delay_ms": 450,
        "laugh_strategy": "wait_for_peak",
        "close": "callback_echo",
        "mechanism_pref": "callback",
    },
}


def fits(grammar: dict, rhythm: dict) -> tuple[bool, list[str]]:
    """Does this rhythm's needs hold for this grammar? Returns (ok, misses)."""
    feats = rhythm_features(grammar)
    needs = rhythm.get("needs", {})
    misses = []
    if needs.get("has_punch") and not feats["has_punch"]:
        misses.append("no punchline")
    if needs.get("escalating") and not feats["escalating"]:
        misses.append("not escalating")
    if needs.get("pivots_min", 0) > feats["pivots"]:
        misses.append(f"needs {needs['pivots_min']} pivots, has {feats['pivots']}")
    if needs.get("tags_min", 0) > feats["tags"]:
        misses.append(f"needs {needs['tags_min']} tags, has {feats['tags']}")
    if needs.get("beat_count_min", 0) > feats["beat_count"]:
        misses.append("too few beats")
    pref = rhythm.get("mechanism_pref")
    if pref and feats["mechanism"] != pref:
        misses.append(f"wants {pref} mechanism, got {feats['mechanism']}")
    return (not misses, misses)


def rank(grammar: dict) -> list[dict]:
    """Best-fitting rhythms first: fit count, then mechanism preference."""
    out = []
    for rid, r in RHYTHMS.items():
        ok, misses = fits(grammar, r)
        out.append({"id": rid, "ok": ok, "misses": misses,
                    "score": sum(1 for m in misses),
                    "rhythm": r})
    out.sort(key=lambda x: (not x["ok"], x["score"]))
    return out


def pick(grammar: dict, default: str = "dry_misdirection") -> dict:
    best = rank(grammar)
    return {"id": best[0]["id"], **best[0]["rhythm"]} if best and best[0]["ok"] \
        else {"id": default, **RHYTHMS[default]}
