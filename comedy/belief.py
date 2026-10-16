"""ComicBeliefEngine: expected vs observed, surprise, notebook — no fake audience.

Two learning systems, kept separate by construction:
  objective: what do the measurements say (may be null = AWAITING_EVIDENCE)
  subjective: what does the character believe (attribution policy, always defined)

Rules baseline with a typed decision interface a decision model (Jev-class)
can fill later. Real-time timing stays in plain code; the router only makes
bounded psychological/artistic decisions. Never invents reactions: with no
audience observations, observed is None and the state is AWAITING_EVIDENCE.
"""
from __future__ import annotations


RECOVERY_ACTIONS = ("deny", "confuse", "defend", "explain", "blame_mic",
                    "louder_next", "quiet_quit", "double_down", "move_on")
NEXT_MATERIAL = ("callback", "new_premise", "crowdwork", "closing", "hold")


def surprise(expected: float | None, observed: float | None) -> float | None:
    """Delta_c = L - E_c. None in, None out. No observations, no surprise."""
    if expected is None or observed is None:
        return None
    return round(observed - expected, 3)


def route(expected: float | None, observed: float | None, attribution: dict,
          min_evidence: int = 5, n_observed: int = 0) -> dict:
    """Typed decision. Insufficient evidence short-circuits to hold."""
    if observed is None or n_observed < min_evidence:
        return {"state": "AWAITING_EVIDENCE", "action": "hold",
                "shaken_0_5": 0, "recover": False, "next": "hold",
                "note": "no audience observations; rehearsal only"}
    d = observed - (expected if expected is not None else 0.5)
    policy = attribution.get("on_unexpected_silence", {}) if d < -0.25 else {}
    shaken = max(0, min(5, int(round(abs(d) * 6))))
    if d >= -0.1:
        action = "move_on"
    else:
        action = policy.get("primary_action", "defend_competence")
        if action not in RECOVERY_ACTIONS:
            action = "defend"
    return {"state": "REACTING", "action": action,
            "shaken_0_5": shaken,
            "recover": d < -0.25 and shaken >= 2,
            "next": policy.get("secondary_action", "callback") if d < -0.25 else "new_premise",
            "surprise": round(d, 3)}


def notebook(character: dict, observed_summary: dict | None) -> dict:
    """Subjective post-show notebook via the character's attribution policy.

    observed_summary carries ONLY measured facts (or nothing). The
    distortion comes from attribution, never from invented laughs.
    """
    pol = character.get("attribution_policy", {})
    entry = {
        "character_id": character.get("character_id", character.get("id")),
        "objective_facts": observed_summary or {"status": "no audience yet"},
        "interpretation": {},
        "next_plan": "",
    }
    if not observed_summary:
        entry["interpretation"] = {"result": "untested material, full confidence retained"}
        entry["next_plan"] = pol.get("default_plan", "perform as written; the room will catch up")
        return entry
    good = observed_summary.get("strong_bits", [])
    weak = observed_summary.get("weak_bits", [])
    succ = pol.get("success", ["my ability"])
    fail = pol.get("failure", ["the room"])
    entry["interpretation"] = {
        "hits_explained": {b: succ[0] for b in good},
        "misses_explained": {b: fail[0] for b in weak},
    }
    entry["next_plan"] = pol.get("default_plan", "more of what worked (per my analysis)")
    return entry


LIFECYCLE = ["BORN", "DEVELOPING", "AUDITIONING", "AWAITING_EVIDENCE",
             "REGULAR", "STAR", "RETIRED", "REVIVED"]


def advance(state: str, published_attempts: int, eligible_views: int,
            breakout: bool, strong_response: bool, min_views: int = 100) -> str:
    """Three-shot rule: only eligible attempts count. Retired stays in world."""
    if state == "RETIRED":
        return "REVIVED" if (breakout and eligible_views >= min_views) else "RETIRED"
    if published_attempts <= 0 or eligible_views < min_views:
        return "AWAITING_EVIDENCE"
    if breakout or (strong_response and published_attempts >= 2):
        return "REGULAR"
    if published_attempts >= 3:
        return "RETIRED"
    return "AUDITIONING"
