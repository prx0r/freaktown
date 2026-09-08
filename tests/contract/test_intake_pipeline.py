#!/usr/bin/env python3
"""Golden fixture through the ported intake pipeline (no DB required).

character + delivery + offsets → validate → score → spans → words →
sealed manifest → stage cues + avatar resolution. Proves the imported
backend/services/freaktown tree works in its new home.
"""

import json
from pathlib import Path

from backend.services.freaktown.bundle import (
    build_performance_manifest,
    bundle_to_score,
    resolve_avatar,
    spans_from_offsets,
    validate_bundle,
    words_from_beats,
)
from backend.services.freaktown.cues import resolve_cues

FIX = Path(__file__).parent.parent.parent / "contracts" / "fixtures" / "golden-freak-v1"


def _load(name):
    return json.loads((FIX / name).read_text())


class TestGoldenIntakePipeline:
    def test_golden_flows_to_stage_cues(self):
        character = _load("character.json")
        delivery = _load("delivery.json")
        offsets = _load("offsets.json")["offsets"]

        assert validate_bundle({"character": character, "delivery": delivery,
                                "audio_url": "set.wav"}).ok
        score = bundle_to_score(delivery)
        spans = spans_from_offsets(offsets)
        words = words_from_beats(delivery["beats"], spans)
        assert words[0].start_ms == 0
        assert words[-1].end_ms == 3337 + 1500

        manifest = build_performance_manifest(
            "perf_golden_1", character, score, words, "set.wav", 5774,
            avatar={"version": "freaktown.avatar.v1", "format": "glb",
                    "asset": "avatar.glb"})
        assert manifest["sha256"] and len(manifest["sha256"]) == 64

        out = resolve_cues(manifest, offsets=offsets, duration_ms=5774)
        assert out["estimated"] is False
        # lean @ b1 (0ms), lean+close+rimshot @ b2 (3337ms)
        assert [m["at_ms"] for m in out["motion"]] == [0, 3337]
        assert out["camera"] == [{"at_ms": 0, "camera": "COMIC_CLOSE"},
                                 {"at_ms": 3337, "camera": "COMIC_CLOSE"}]
        assert out["sfx"] == [{"at_ms": 3337, "name": "rimshot"}]

        url, source = resolve_avatar(manifest)
        assert (url, source) == ("avatar.glb", "provided") or source == "default"
