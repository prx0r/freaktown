#!/usr/bin/env python3
"""Golden convergence gate (§48): one Freak, fixture to sealed manifest.

Automates every migration-gate step that doesn't need Postgres/R2/DO:
CREATE→WRITE→DIRECT→REHEARSE→PUBLISH→SUBMIT(validate)→STORE(hash stable)
→PERFORM(same timing/avatar/delivery)→REPLAY(same event sequence).
DB/DO steps join when infrastructure exists; this test must stay green.
"""

import json
from pathlib import Path

import jsonschema

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
CONTRACTS = FIX.parent.parent


def _load(name):
    return json.loads((FIX / name).read_text())


def _build():
    character, delivery = _load("character.json"), _load("delivery.json")
    offsets = _load("offsets.json")["offsets"]
    assert validate_bundle({"character": character, "delivery": delivery,
                            "audio_url": "set.wav"}).ok
    score = bundle_to_score(delivery)
    spans = spans_from_offsets(offsets)
    words = words_from_beats(delivery["beats"], spans)
    manifest = build_performance_manifest(
        "perf_golden_1", character, score, words, "set.wav", 5774,
        avatar=_load("avatar.json"))
    cues = resolve_cues(manifest, offsets=offsets, duration_ms=5774)
    return manifest, cues, words


class TestGoldenConvergence:
    def test_store_hash_stable(self):
        assert _build()[0]["sha256"] == _build()[0]["sha256"]

    def test_perform_same_timing_avatar_delivery(self):
        m1, c1, w1 = _build()
        m2, c2, w2 = _build()
        assert [(w.start_ms, w.end_ms) for w in w1] == [(w.start_ms, w.end_ms) for w in w2]
        assert c1["motion"] == c2["motion"] and c1["camera"] == c2["camera"]
        url, source = resolve_avatar(m1)
        assert (url, source) == resolve_avatar(m2)
        assert url  # never black: relative asset → default stage avatar
        assert m1["delivery"] == m2["delivery"]

    def test_replay_same_event_sequence(self):
        """Manifest cues → deterministic event stream (seq, type, payload)."""
        schema = json.loads((CONTRACTS / "events.v1.schema.json").read_text())
        _, cues, _ = _build()
        events, seq = [], 0
        for kind, items in (("stage.gesture", cues["motion"]),
                            ("camera.cut", cues["camera"]),
                            ("stage.sfx", cues["sfx"])):
            for it in items:
                seq += 1
                ev = {"seq": seq, "type": kind, "episode_id": "ep1",
                      "performance_id": "perf_golden_1", "payload": it}
                jsonschema.validate(ev, schema)
                events.append(ev)
        assert [e["seq"] for e in events] == [1, 2, 3, 4, 5]
        assert events[0]["payload"]["action"] == "lean_in"

    def test_manifest_matches_performance_schema(self):
        schema = json.loads((CONTRACTS / "performance.v1.schema.json").read_text())
        jsonschema.validate(_build()[0], schema)
