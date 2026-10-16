"""Comedy compiler tests: corpus → rhythms → director → evaluator."""
import pytest

from comedy import analyze, compile_delivery, predict, learn
from comedy.corpus import rhythm_features
from comedy.rhythms import RHYTHMS, fits, rank, pick
from comedy.director import validate, _line_beat
from comedy import evaluator

BIT = [
    "Dad falls asleep after every Christmas lunch.",
    "Everyone pretends it is intentional, and somehow he still wins the golf.",
    "He wins it asleep. Legend.",
]


def test_corpus_is_anonymous():
    g = analyze(" ".join(BIT))
    dumped = str(g)
    for secret in ("Christmas lunch", "wins the golf"):
        assert secret not in dumped, "grammar must not carry original text"
    assert g["source_hash"] and len(g["source_hash"]) == 16
    assert g["total_words"] > 0


def test_corpus_finds_structure():
    g = analyze("Some joke here. But actually no. Except the punch. Fine. Done.")
    types = [b["type"] for b in g["beats"]]
    assert "setup" in types
    assert any(b["duration_ms"] > 0 for b in g["beats"])
    feats = rhythm_features(g)
    assert feats["has_punch"] or g["beats"][-1]["type"] == "closer"


def test_rhythm_ranking_prefers_fit():
    g = analyze("Setup line one. A turn happens here but with a pivot. And the punch lands hard now. Tag. Done.")
    ranked = rank(g)
    assert ranked[0]["ok"], ranked[0]["misses"]
    assert pick(g)["id"] in RHYTHMS
    # a rhythm needing escalating tags misses a smooth set
    ok, misses = fits(g, {"needs": {"tags_min": 5}})
    assert not ok and misses


def test_director_validates_against_schema():
    d = compile_delivery(BIT, profile={"pace": 1.0, "energy": 0.6,
                                       "punchline_hold_ms": 900},
                         voice_id="edge:ryan")
    assert validate(d) == []
    assert d["version"] == "freaktown.delivery.v1"
    types = [b["type"] for b in d["beats"]]
    assert "punchline" in types or "closer" in types


def test_director_punch_has_timing():
    d = compile_delivery(BIT, rhythm_id="dry_misdirection")
    punch = next(b for b in d["beats"] if b["type"] == "punchline")
    assert punch["pause_before_ms"] == RHYTHMS["dry_misdirection"]["pre_punch_pause_ms"]
    assert punch["pause_after_ms"] > 0
    assert punch["performance"]["expression"] == "deadpan"


def test_multisentence_line_keeps_punch():
    # the original bug: a 2-sentence line swallowed the punchline
    d = compile_delivery(["Open.", "Turn but still builds. And lands the punch hard.", "Close."])
    types = [b["type"] for b in d["beats"]]
    assert "punchline" in types


def test_line_beat_never_closer_mid():
    beat = _line_beat("A single sentence mid-line.", 1, 3)
    assert beat["type"] != "closer"
    assert beat["type"] != "setup"


def test_evaluator_predict_and_learn(tmp_path):
    g = analyze(" ".join(BIT))
    p = predict(g, RHYTHMS["dry_misdirection"], {"punchline_hold_ms": 850})
    assert 0 <= p["predicted_laugh"] <= 1
    assert p["reasons"]
    ev = tmp_path / "events.jsonl"
    evaluator.record_event({"mechanism": "misdirection", "laugh_latency_ms": 320,
                            "laugh_strength": 0.8}, path=ev)
    evaluator.record_event({"mechanism": "misdirection", "laugh_latency_ms": 420,
                            "laugh_strength": 0.6}, path=ev)
    out = evaluator.learn(path=ev)
    assert out["events"] == 2
    # implementation: median = sorted[len//2] → [320,420] → 420
    assert out["mechanisms"]["misdirection"]["median_laugh_latency_ms"] == 420
