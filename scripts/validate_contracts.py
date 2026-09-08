#!/usr/bin/env python3
"""CI entry: golden fixture vs canonical schemas. Fails loudly on drift."""

import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parent.parent
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

fails = 0
for schema_name, fixture_name in PAIRS:
    schema = json.loads((CONTRACTS / schema_name).read_text())
    doc = json.loads((FIX / fixture_name).read_text())
    try:
        jsonschema.validate(doc, schema)
        print(f"OK {fixture_name}")
    except jsonschema.ValidationError as e:
        fails += 1
        print(f"FAIL {fixture_name}: {e.message}")
sys.exit(1 if fails else 0)
