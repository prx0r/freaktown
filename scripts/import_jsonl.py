#!/usr/bin/env python3
"""Replayable, idempotent JSONL importers (§15).

Reads legacy freaktown JSONL state (funnel/reactions/votes/party rooms),
normalizes each line to {"source","ts",...}, dedupes by content hash, and
writes var/imports/<name>.jsonl. Reruns produce byte-identical output.
Missing sources are skipped (exit 0) — import what exists.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "var" / "imports"

SOURCES = {
    "funnel": "funnel.jsonl",
    "reactions": "reactions.jsonl",
    "votes": "votes.jsonl",
    "party_rooms": "party_rooms.json",
}


def _canon(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def import_file(name: str, path: Path) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    if path.suffix == ".json" and path.name == "party_rooms.json":
        try:
            rooms = json.loads(path.read_text())
            items = [{"room": code, **r} for code, r in rooms.items()]
        except Exception:
            items = []
    else:
        items = []
        try:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        except FileNotFoundError:
            return 0
    for it in items:
        if not isinstance(it, dict):
            continue
        rec = {"source": name, **it}
        seen[hashlib.sha256(_canon(rec).encode()).hexdigest()] = rec
    dest = OUT / f"{name}.jsonl"
    dest.write_text("".join(_canon(r) + "\n" for r in sorted(seen)))
    return len(seen)


def main() -> int:
    total = 0
    for name, fname in SOURCES.items():
        n = import_file(name, ROOT / fname)
        print(f"{name}: {n} records")
        total += n
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
