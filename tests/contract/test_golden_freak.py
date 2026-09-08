#!/usr/bin/env python3
"""Golden Freak: the treaty between every subsystem.

contracts/fixtures/golden-freak-v1/ must validate against contracts/*.schema.json
with every non-default value intact. If Studio, intake, or the stage drift,
this goes red first.
"""

import json
import wave
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parent.parent.parent
CONTRACTS = ROOT / "contracts"
FIX = CONTRACTS / "fixtures" / "golden-freak-v1"

PAIRS = [
    ("character.v1.schema.json", "character.json"),
    ("avatar.v1.schema.json", "avatar.json"),
    ("delivery.v1.schema.json", "delivery.json"),
    ("offsets.v1.schema.json", "offsets.json"),
    ("lineage.v1.schema.json", "lineage.json"),
    ("performance.v1.schema.json", "performance.json"),
]


def _load(name):
    return json.loads((CONTRACTS / name).read_text()) if name.endswith(".json") and "/" not in name else None


class TestGoldenFreak:
    def test_all_fixtures_validate(self):
        for schema_name, fixture_name in PAIRS:
            schema = json.loads((CONTRACTS / schema_name).read_text())
            doc = json.loads((FIX / fixture_name).read_text())
            jsonschema.validate(doc, schema)

    def test_non_default_values_survive(self):
        d = json.loads((FIX / "delivery.json").read_text())
        b1 = d["beats"][0]
        assert b1["delivery"]["pace"] == 0.85
        assert b1["delivery"]["energy"] == 0.71
        assert b1["delivery"]["emphasis"] in (0.5, 0.82)
        assert b1["performance"]["expression"] == "annoyed"
        assert b1["gesture"] == "lean"
        assert b1["camera"] == "close"
        assert b1["pause_after_ms"] == 937
        assert d["beats"][1]["delivery"]["emphasis"] == 0.82
        assert d["beats"][1]["sound"] == "rimshot"

    def test_offsets_match_beats(self):
        d = json.loads((FIX / "delivery.json").read_text())
        o = json.loads((FIX / "offsets.json").read_text())
        assert [b["id"] for b in d["beats"]] == [x["id"] for x in o["offsets"]]

    def test_set_wav_valid(self):
        with wave.open(str(FIX / "set.wav"), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getframerate() == 24000
            assert w.getnframes() > 0

    def test_lineage_reply_shape(self):
        lin = json.loads((FIX / "lineage.json").read_text())
        assert lin["relation"] == "reply"
        assert lin["depth"] == 3
        assert lin["root_performance_id"] == "perf_a"
