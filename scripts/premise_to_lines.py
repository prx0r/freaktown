#!/usr/bin/env python3
"""Premise-to-lines adapter v1: character + premise + mechanism -> draft lines.

The documented missing joint: the director takes written lines, so accepted
premises had no path to the stage. This builds the first path:

  cast spec (contradictions, callbacks, voice) + premise + mechanism
    -> deterministic 6-line draft (setup, 3x escalation, punch, closer)
    -> optional --polish via local Ollama (same 6 lines, character voice)
    -> comedy.director compile + validate -> verdict on stdout

Output is a DRAFT for human review. Nothing writes into p0-sets.json;
promote by hand after reading it aloud. Usage:
  python3 scripts/premise_to_lines.py --character pog.doug-deadline \\
      --premise "Laundry as a quarterly review." --mechanism escalation [--polish]
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from comedy.director import compile_delivery, validate  # noqa: E402


def cast_spec(character):
    hits = glob.glob(os.path.join(HERE, "assets", "character-meshes", "cast", "*.json"))
    for f in hits:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get("id") == character:
            return d
    sys.exit("no cast spec for " + character)


def draft_lines(spec, premise, mechanism):
    name = spec.get("name", spec["id"])
    contra = spec.get("contradictions", []) or [{}] * 3
    hooks = spec.get("callback_hooks", []) or ["the incident (never discussed)"]
    c = [x.get("engine", "") for x in contra]
    while len(c) < 3:
        c.append("it gets worse in exactly the expected way")
    lines = [
        f"Good evening. Tonight: {premise} {name} presiding, feelings will be minuted.",
        f"First item. {c[0]} This is now policy.",
        f"Second item. {c[1]} Escalated to the full committee.",
        f"Third item. {c[2]} Effective immediately, no exceptions.",
        f"And yet I remain the reasonable one here. That is the tragedy.",
        f"We adjourn. {hooks[0][0].upper() + hooks[0][1:]}. Goodnight.",
    ]
    return lines


def polish(lines, spec, premise):
    prompt = (
        "Rewrite these 6 stand-up lines in the voice of %s (%s). "
        "Keep exactly 6 lines in the same order and roles "
        "(setup, escalation, escalation, escalation, punchline, closer). "
        "Keep the premise: %s. Make no new factual claims about real people. "
        "Reply with the 6 lines only, one per line.\n\n%s"
        % (spec.get("name", ""), json.dumps(spec.get("voice", ""))[:300],
           premise, "\n".join("%d. %s" % (i + 1, l) for i, l in enumerate(lines))))
    r = subprocess.run(["ollama", "run", "hermes3:8b", prompt],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        sys.exit("ollama polish failed: " + r.stderr[-500:])
    out = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    out = [l.split(". ", 1)[1] if l[:2].strip("0123456. ") == "" else l for l in out]
    if len(out) != 6:
        sys.exit(f"polish returned {len(out)} lines, keeping draft (not promoting)")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--premise", required=True)
    ap.add_argument("--mechanism", default="escalation")
    ap.add_argument("--polish", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    spec = cast_spec(a.character)
    lines = draft_lines(spec, a.premise, a.mechanism)
    if a.polish:
        lines = polish(lines, spec, a.premise)
    profile = {"energy": 0.7, "pace": 0.95, "punchline_hold_ms": 850}
    delivery = compile_delivery(lines, profile=profile, voice_id="edge:x",
                                mechanism=a.mechanism)
    errs = validate(delivery)
    doc = {"character": a.character, "premise": a.premise,
           "mechanism": a.mechanism, "polished": a.polish,
           "lines": lines, "delivery_beats": len(delivery.get("beats", [])),
           "validation": errs}
    if a.out:
        json.dump(doc, open(a.out, "w"), indent=1)
    print(json.dumps({"lines": lines, "beats": len(delivery.get("beats", [])),
                      "errors": errs}, indent=1)[:2000])
    print("VERDICT:", "DRAFT-OK" if not errs else "NEEDS-WORK", "- review aloud before p0-sets")


if __name__ == "__main__":
    main()
