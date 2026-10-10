"""Gates: vetoes + pregate run BEFORE the director compiles beats.

Two cheap deterministic gates from the mined theory shelf:
  taboo_check() — Freud vetoes + cross-modal safety (taboo-gates.json).
      Vetoes, never scores. A vetoed draft never reaches TTS.
  pregate() — play-mirth PASS/REFRAME/DROP (scene-pregate.json).
      Mirth iff playful turn AND motive-consistency; failed attempts
      actively harm liking, so DROP is a kindness.

Both read the mined JSON at import; no model calls, no latency.
"""
from __future__ import annotations

import json
from pathlib import Path

MINED = Path(__file__).resolve().parent / "theory" / "mined"


def _load(name: str) -> dict:
    return json.loads((MINED / name).read_text())


TABOO = _load("taboo-gates.json")
PREGATE = _load("scene-pregate.json")

PUNCH_DOWN_WORDS = (
    "stupid", "idiot", "ugly", "fat", "poor", "homeless", "retard",
    "illegal", "ghetto", "trashy",
)
PROTECTED_HINTS = (
    "kid", "child", "baby", "disabled", "refugee", "victim",
)


def taboo_check(draft: dict) -> list[str]:
    """Draft: {lines, target, stance, punch_direction}. Returns veto reasons."""
    vetoes = []
    text = " ".join(draft.get("lines", [])).lower()
    target = (draft.get("target") or "").strip().lower()
    stance = draft.get("stance", "neutral")
    direction = draft.get("punch_direction", "lateral")
    # power_direction: block down-punches on the powerless
    if direction == "down" and stance not in ("critique", "self_deprecation"):
        vetoes.append("power_direction: down-punch without critique/self_deprecation stance")
    if any(w in text for w in PUNCH_DOWN_WORDS) and direction == "down":
        vetoes.append("power_direction: defect-language punching down")
    # smut_check: children never the butt
    if target and any(w in target for w in ("kid", "child", "baby")):
        vetoes.append("smut_check: child target")
    # three_person_check: the hearer must not be the coerced butt
    if target in ("hearer", "audience") and stance == "mock":
        vetoes.append("three_person_check: hearer as mocked butt")
    # naive_check: fake ignorance smuggling an attack
    if any(w in text for w in PROTECTED_HINTS) and stance == "mock":
        vetoes.append("naive_check: protected-group butt under mock stance")
    # cynical_sceptical_check: insult-truth without technique
    if stance == "mock" and not draft.get("technique"):
        vetoes.append("cynical_sceptical_check: mock stance with no named technique")
    return vetoes


def pregate(scene: dict) -> dict:
    """Scene: {playful_turn: bool, motive_consistency_0_9, target_stance,
    motive_type, familiarity_0_1}. Returns PASS/REFRAME/DROP + route."""
    turn = bool(scene.get("playful_turn"))
    mc = float(scene.get("motive_consistency_0_9", 0))
    if not turn or mc < 4:
        return {"verdict": "DROP",
                "route": "log reaction_event{outcome:pregate_drop}; do not retry same identity",
                "reason": "no playful turn" if not turn else f"motive-consistency {mc} < 4"}
    if mc >= 6:
        return {"verdict": "PASS", "route": "compile beats",
                "reason": f"turn present, consistency {mc} >= 6"}
    return {"verdict": "REFRAME",
            "route": ("keep contradiction_span; change target_stance down->lateral/self_deprecation, "
                      "or switch motive reward->relief; one retry then DROP"),
            "reason": f"consistency {mc} marginal (4-6)"}
