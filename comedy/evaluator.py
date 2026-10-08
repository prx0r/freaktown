"""Evaluator: predicted audience response from grammar + rhythm + profile.

Deterministic first (heuristics derived from the Ella rubric's structural
insights), then learn() from real Freaktown reaction events — laugh latency,
magnitude, audience fatigue — so predictions become empirical. No neural net
needed initially; a gradient-boosted ranker slots in behind the same API.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_EVENTS = Path(__file__).resolve().parents[1] / "data" / "comedy_events.jsonl"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def predict(grammar: dict, rhythm: dict | None = None, profile: dict | None = None) -> dict:
    """Expected audience response for a compiled bit. 0..1 scores."""
    feats = grammar.get("beats", [])
    n = grammar.get("total_words", 0)
    score = 0.5
    reasons = []
    # structure: full-minute material, punch + closer present
    types = [b["type"] for b in feats]
    if "punchline" in types:
        score += 0.12
        reasons.append("has a punch")
    if types[-1:] == ["closer"]:
        score += 0.10
        reasons.append("sticks the closer")
    if 80 <= n <= 180:
        score += 0.10
        reasons.append("right length")
    elif n > 240:
        score -= 0.10
        reasons.append("overlong")
    if types.count("tag") >= 1 and "punchline" in types:
        score += 0.05
        reasons.append("tags off the punch")
    # rhythm coherence: holds that match the character's natural hold
    if rhythm:
        prof = profile or {}
        hold = float(prof.get("punchline_hold_ms", 850))
        rhold = float(rhythm.get("punch_hold_ms", 850))
        drift = abs(hold - rhold) / 1500.0
        score += 0.10 * (1 - _clamp01(drift))
        if drift < 0.25:
            reasons.append("rhythm fits the character")
        if rhythm.get("laugh_strategy") == "talk_over" and \
                float(prof.get("energy", 0.65)) < 0.6:
            score -= 0.08
            reasons.append("talk-over fights a calm character")
    # mechanism clarity: named mechanism lifts confidence
    if grammar.get("mechanism") in ("callback", "misdirection"):
        score += 0.05
    return {"predicted_laugh": round(_clamp01(score), 2),
            "predicted_groan": round(_clamp01(0.15 - 0.1 * (score - 0.5)), 2),
            "confidence": 0.6,
            "reasons": reasons}


def record_event(event: dict, path: Path | None = None) -> None:
    """One reaction event: {laugh_latency_ms, laugh_duration_ms,
    laugh_strength, groove?, character, mechanism, rhythm}."""
    p = path or DEFAULT_EVENTS
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(event) + "\n")


def learn(path: Path | None = None) -> dict:
    """Aggregate real reaction events → latency/strength distributions per
    mechanism. Pure stdlib stats; a ranker consumes these later."""
    p = path or DEFAULT_EVENTS
    if not p.exists():
        return {"events": 0}
    buckets: dict[str, dict] = {}
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        m = str(e.get("mechanism") or "unknown")
        b = buckets.setdefault(m, {"n": 0, "latency": [], "strength": []})
        b["n"] += 1
        if e.get("laugh_latency_ms") is not None:
            b["latency"].append(float(e["laugh_latency_ms"]))
        if e.get("laugh_strength") is not None:
            b["strength"].append(float(e["laugh_strength"]))
    out = {"events": sum(b["n"] for b in buckets.values()), "mechanisms": {}}
    for m, b in buckets.items():
        lat = sorted(b["latency"])
        out["mechanisms"][m] = {
            "n": b["n"],
            "median_laugh_latency_ms": lat[len(lat) // 2] if lat else None,
            "mean_strength": round(sum(b["strength"]) / len(b["strength"]), 3)
            if b["strength"] else None,
        }
    return out
