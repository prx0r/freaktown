#!/usr/bin/env python3
"""Format runtime: two radically different formats, zero format-specific code."""

import json
from pathlib import Path

import jsonschema

from format_runtime import FormatRun, load_format, validate_format

ROOT = Path(__file__).parent.parent.parent
FORMATS = ROOT / "formats"


def _receipt_schema():
    return json.loads((ROOT / "contracts" / "receipt.v1.schema.json").read_text())


class TestFormatRuntime:
    def test_engine_has_no_format_words(self):
        src = (ROOT / "format_runtime.py").read_text().lower()
        for word in ("comedy", "poetry", "poem", "joke", "slam", "mic",
                     "stand-up", "standup", "verse"):
            assert word not in src, f"engine mentions {word}"

    def test_both_formats_valid(self):
        for f in ("comedy.open-mic", "poetry.slam"):
            assert validate_format(load_format(FORMATS / f)) == []

    def test_receipts_validate(self):
        schema = _receipt_schema()
        for f in ("comedy.open-mic", "poetry.slam"):
            m = load_format(FORMATS / f)
            fix = json.loads((FORMATS / f / "tests" / "happy-path.json").read_text())
            r = FormatRun(m).run(fix["participants"], fix["submissions"])
            jsonschema.validate(r, schema)
            assert r["format"]["format_id"] == m["_format_id"]

    def test_deterministic_replay(self):
        m = load_format(FORMATS / "poetry.slam")
        fix = json.loads((FORMATS / "poetry.slam" / "tests" / "happy-path.json").read_text())
        r1 = FormatRun(m, event_id="e1").run(fix["participants"], fix["submissions"])
        r2 = FormatRun(m, event_id="e1").run(fix["participants"], fix["submissions"])
        assert r1["event_log_root"] == r2["event_log_root"]
        assert r1["results"] == r2["results"]

    def test_hash_chain_integrity(self):
        import hashlib
        m = load_format(FORMATS / "comedy.open-mic")
        run = FormatRun(m)
        fix = json.loads((FORMATS / "comedy.open-mic" / "tests" / "tie.json").read_text())
        run.run(fix["participants"], fix["submissions"])
        prev = "genesis"
        for ev in run.events:
            assert ev["prev"] == prev
            body = {k: v for k, v in ev.items() if k != "hash"}
            assert ev["hash"] == hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            prev = ev["hash"]
