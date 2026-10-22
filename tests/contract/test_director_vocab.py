#!/usr/bin/env python3
"""Director vocab: tag synonyms, budgets, beat resolution."""

from backend.services.funnier.director_vocab import (
    Budget,
    beat_emotion,
    emotion_for_tag,
    empty_vocab,
    load_vocab,
    normalize_vocab,
    opening_tag,
)

VOCAB = {
    "emotions": {"happy": "bright", "sad": "low", "deadpan": "flat"},
    "tags": {"giggles": "happy", "sighs": "sad"},
    "intense": ["sad"],
    "gestures": ["lean"],
    "cameras": ["close"],
    "registers": ["regular"],
    "limits": {"cameras": 1, "intense": 1},
}


class TestTags:
    def test_exact_synonym(self):
        assert emotion_for_tag("giggles", VOCAB) == "happy"
        assert emotion_for_tag("GIGGLES", VOCAB) == "happy"

    def test_unmapped_is_none(self):
        assert emotion_for_tag("moonwalk", VOCAB) is None
        assert emotion_for_tag("giggles", empty_vocab()) is None

    def test_opening_tag(self):
        assert opening_tag("[giggles] oh you") == "giggles"
        assert opening_tag("no tag here") is None
        assert opening_tag(None) is None


class TestBeatEmotion:
    def test_tag_wins(self):
        assert beat_emotion("[sighs] alright", "happy", VOCAB) == "sad"

    def test_unmapped_tag_falls_back_to_authored(self):
        assert beat_emotion("[moonwalk] hi", "happy", VOCAB) == "happy"

    def test_no_tag_no_authored_is_none(self):
        assert beat_emotion("plain line", None, VOCAB) is None
        assert beat_emotion("plain line", "", VOCAB) is None


class TestBudget:
    def test_intense_capped(self):
        b = Budget(VOCAB)
        assert b.allow_emotion("sad") is True
        assert b.allow_emotion("sad") is False
        assert b.allow_emotion("happy") is True

    def test_cameras_capped(self):
        b = Budget(VOCAB)
        assert b.allow_camera() is True
        assert b.allow_camera() is False


class TestLoad:
    def test_example_loads_with_notes(self):
        v, errs = load_vocab("docs/DIRECTOR.example.json")
        assert "grin" in v["emotions"]
        assert v["tags"]["giggles"] == "grin"
        # example file carries a _note key: tolerated, no error
        assert not [e for e in errs if "unknown emotion" in e]

    def test_bad_vocab_never_raises(self):
        v, errs = load_vocab("/nonexistent/x.json")
        assert v == empty_vocab() and errs
        v, errs = normalize_vocab({"emotions": [], "tags": {"a": "zzz"}})
        assert errs  # tags must map known emotions... (warns)

    def test_missing_file_ok(self):
        v, errs = load_vocab("/nonexistent/director.json")
        assert beat_emotion("[giggles] hi", "happy", v) == "happy"
