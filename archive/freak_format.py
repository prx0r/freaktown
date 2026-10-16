#!/usr/bin/env python3
"""freak format — init / validate / test for FormatPacks.

  python3 scripts/freak_format.py validate formats/poetry.slam
  python3 scripts/freak_format.py test formats/poetry.slam
  python3 scripts/freak_format.py init formats/my-format
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from format_runtime import FormatRun, load_format, validate_format

ROOT = Path(__file__).parent.parent


def cmd_validate(path):
    m = load_format(path)
    errors = validate_format(m)
    print(f"{m['id']} v{m['version']} format_id={m['_format_id'][:12]}")
    if errors:
        print("INVALID:"); [print(f"  - {e}") for e in errors]
        return 1
    print("VALID")
    return 0


def cmd_test(path):
    d = Path(path)
    m = load_format(d)
    if validate_format(m):
        print("INVALID MANIFEST"); return 1
    fails = 0
    for t in sorted((d / "tests").glob("*.json")):
        fix = json.loads(t.read_text())
        run = FormatRun(m, event_id=f"evt_test_{t.stem}")
        receipt = run.run(fix["participants"], fix["submissions"])
        ok = True
        if "expect_winner" in fix:
            ok = receipt["results"]["winner"] == fix["expect_winner"]
        if fix.get("expect_tiebreak"):
            ok = ok and receipt["results"]["tiebreak"] is True
        print(f"{'PASS' if ok else 'FAIL'} {t.stem} "
              f"winner={receipt['results']['winner']} "
              f"root={receipt['event_log_root'][:12]}")
        fails += 0 if ok else 1
    return 1 if fails else 0


TEMPLATE = {
    "schema": "freaktown.format/v1",
    "id": "my-format",
    "name": "My Format",
    "version": "0.1.0",
    "participants": {"min": 2, "max": 8, "kinds": ["agent", "human"]},
    "states": ["LOBBY", "PERFORMANCE", "JUDGING", "WINNER"],
    "rounds": [{"id": "open", "performers": "all", "durationSeconds": 60,
                "submission": "act", "advance": {"top": 1}}],
    "judging": {"audienceWeight": 0.5, "judgeWeight": 0.5,
                "rubric": "./scoring/rubric.json"},
    "stage": {"preset": "club", "walkouts": False, "audienceReactions": True},
}


def cmd_init(path):
    d = Path(path)
    (d / "scoring").mkdir(parents=True, exist_ok=True)
    (d / "tests").mkdir(parents=True, exist_ok=True)
    (d / "freak-format.json").write_text(json.dumps(TEMPLATE, indent=2) + "\n")
    (d / "scoring" / "rubric.json").write_text(
        json.dumps({"dimensions": []}, indent=2) + "\n")
    print(f"init {d} — edit freak-format.json, then: freak format validate {d}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); raise SystemExit(2)
    cmd, path = sys.argv[1], sys.argv[2]
    raise SystemExit({"validate": cmd_validate, "test": cmd_test,
                      "init": cmd_init}[cmd](path))
