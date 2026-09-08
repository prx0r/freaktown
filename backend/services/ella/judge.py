"""EllaJudge accumulator — Tier 2 deep evaluation, scored WHILE the set happens.

Television gives 1-3s of cover (applause, panel wide, ChatGPT), but we
cheat further: every beat updates running dimension means + laugh-curve
features, so by the closer the verdict is nearly final. Finalize is
`closer result + finalize`, not `read the whole minute from scratch`.

Separation from EllaLive is load-bearing: reactive banter must never
corrupt the scientific judge. The accumulator sees beats + reactions;
it never sees dialogue.

Score bands (match the panel):
  0-3 disaster · 3-5 cut · 5-7 survive · 7-8.5 strong · 8.5+ exceptional
  verdict KEEP at >= 6 · GOLDEN_TICKET candidate at >= 9.5
"""

from dataclasses import dataclass, field

DIMENSIONS = ("opening_hook", "escalation", "specificity", "closer", "voice")


@dataclass
class BeatUpdate:
    beat_id: str
    beat_type: str
    text: str
    laugh_events: int = 0
    unique_laughers: int = 0
    active_viewers: int = 0


@dataclass
class AccumulatedBeat:
    beat_id: str
    beat_type: str
    rubric_total: float  # 0-10 material quality for this beat's text
    laugh_share: float  # unique_laughers / active_viewers, 0-1


class EllaJudgeAccumulator:
    """Running judge state for one performance."""

    def __init__(self, rubric_scorer=None, past_scores: list[float] | None = None):
        from backend.services.scoring.rubric import RubricScorer

        self.rubric = rubric_scorer or RubricScorer()
        self.past_scores = list(past_scores or [])
        self.beats: list[AccumulatedBeat] = []
        self.dimensions: dict[str, list[float]] = {d: [] for d in DIMENSIONS}

    def update(self, beat: BeatUpdate) -> dict:
        """Score one beat's material + delivery. Returns running snapshot."""
        scored = self.rubric.score(beat.text)
        for dim in DIMENSIONS:
            value = scored.get(dim, 1)
            try:
                self.dimensions[dim].append(max(0.0, min(2.0, float(value))))
            except (TypeError, ValueError):
                self.dimensions[dim].append(1.0)
        try:
            total = max(0.0, min(10.0, float(scored.get("total", 5))))
        except (TypeError, ValueError):
            total = 5.0

        share = 0.0
        if beat.active_viewers > 0:
            share = max(0.0, min(1.0, beat.unique_laughers / beat.active_viewers))
        self.beats.append(AccumulatedBeat(
            beat_id=beat.beat_id, beat_type=beat.beat_type,
            rubric_total=total, laugh_share=share,
        ))
        return self.snapshot()

    def snapshot(self) -> dict:
        """Current best estimate (what finalize() would return now)."""
        return self._finalize_impl(partial=True)

    def finalize(self, closer_land_share: float = 0.0) -> dict:
        """Final verdict. closer_land_share optionally overrides with the
        measured laugh share of the closing beat."""
        return self._finalize_impl(partial=False, closer_land_share=closer_land_share)

    def _finalize_impl(self, partial: bool, closer_land_share: float = 0.0) -> dict:
        if not self.beats:
            return {
                "score": 5.0, "verdict": "CUT", "award": "none",
                "dimensions": {d: 1.0 for d in DIMENSIONS},
                "confidence": 0.0, "beats_scored": 0,
            }

        dim_means = {
            d: sum(vals) / len(vals) for d, vals in self.dimensions.items() if vals
        }
        for d in DIMENSIONS:
            dim_means.setdefault(d, 1.0)
        material = sum(dim_means.values()) / len(dim_means) * 5  # 0-10

        shares = [b.laugh_share for b in self.beats]
        if not partial and closer_land_share > 0:
            shares[-1] = max(0.0, min(1.0, closer_land_share))
        peak = max(shares)
        mean_share = sum(shares) / len(shares)
        # Delivery score: peak matters most (one killer laugh beats
        # steady chuckles), mean keeps it honest.
        delivery = max(0.0, min(10.0, peak * 7 + mean_share * 3))

        score = round(material * 0.6 + delivery * 0.4, 1)
        score = max(1.0, min(10.0, score))

        verdict = "KEEP" if score >= 6 else "CUT"
        award = "GOLDEN_TICKET" if score >= 9.5 else "none"

        # Confidence: more beats + material/laugh agreement + history.
        agreement = 1 - min(1.0, abs(material - delivery) / 10)
        depth = min(1.0, len(self.beats) / 5)
        history = 0.5
        if self.past_scores:
            avg_past = sum(self.past_scores) / len(self.past_scores)
            history = 1 - min(1.0, abs(avg_past - score) / 10)
        confidence = round(0.4 * agreement + 0.4 * depth + 0.2 * history, 2)

        return {
            "score": score,
            "verdict": verdict,
            "award": award,
            "dimensions": {d: round(v, 2) for d, v in dim_means.items()},
            "material": round(material, 1),
            "delivery": round(delivery, 1),
            "peak_laugh_share": round(peak, 3),
            "confidence": confidence,
            "beats_scored": len(self.beats),
        }
