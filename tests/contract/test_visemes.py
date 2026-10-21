#!/usr/bin/env python3
"""TalkingHead-en viseme bridge: rules run, shapes hold, stage can eat it."""

from backend.services.freaktown.viseme_text import (
    build_take_visemes,
    run_wrapper,
    timeline_to_words,
)

TIMELINE = [
    {"beat_id": "b1", "text": "hello lamp", "start_ms": 0,
     "end_ms": 720, "type": "setup"},
    {"beat_id": "b2", "text": "", "start_ms": 720, "end_ms": 900,
     "type": "pause"},
    {"beat_id": "b3", "text": "good dog", "start_ms": 900,
     "end_ms": 1500, "type": "punchline"},
]


class TestWords:
    def test_split(self):
        words = timeline_to_words(TIMELINE)
        assert [w["text"] for w in words] == [
            "hello", "lamp", "good", "dog"]
        assert words[0]["start_ms"] == 0
        assert words[-1]["end_ms"] == 1500

    def test_empty(self):
        assert timeline_to_words([]) == []
        assert timeline_to_words(None) == []
        assert timeline_to_words([{"text": ""}]) == []


class TestWrapper:
    def test_hello_lamp(self):
        doc = run_wrapper([{"text": "hello", "start_ms": 0,
                            "end_ms": 420}])
        assert doc["words"] == ["hello"]
        # I E nn O — the canonical English opening
        assert doc["visemes"][:4] == ["I", "E", "nn", "O"]
        assert doc["vtimes"][0] == 0
        assert doc["vtimes"][-1] + doc["vdurations"][-1] <= 420

    def test_monotonic_and_bounded(self):
        doc = build_take_visemes(TIMELINE)
        assert len(doc["words"]) == 4
        assert doc["vtimes"] == sorted(doc["vtimes"])
        assert min(doc["vtimes"]) >= 0
        assert max(doc["vtimes"]) <= 1500
        assert all(d >= 20 for d in doc["vdurations"])

    def test_speak_audio_shape(self):
        doc = build_take_visemes(TIMELINE)
        for k in ("words", "wtimes", "wdurations", "visemes",
                  "vtimes", "vdurations"):
            assert isinstance(doc[k], list)
        assert len(doc["wtimes"]) == len(doc["words"])
        assert len(doc["vtimes"]) == len(doc["visemes"])
