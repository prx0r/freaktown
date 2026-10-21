#!/usr/bin/env python3
"""Marble Cauldron P0 submission builder + runner (BETA API).

P0 DECISION (2026-10-17): dressed draft is FINE. Goal = a character in the
room, not a perfect shell. Flow (per How To Use Atlas): pose each anchor
SEPARATELY via images2PosedRGBD (fal-b + ang-b are creative, not same-
location — posed apart, placed at OUR positions), then atlasGenerate with
the posed RGBD frames as contextFrames + 4 house targetCameras.
Anchors by public URL — no asset-upload flow needed for inputs.
Official CLI: npm i -g @worldlabsai/cli (installed, Node 24 OK).

  Dry run (default, $0):  /usr/bin/python3 scripts/marble_cauldron.py
  Live (ask-first):       WLT_API_KEY=... /usr/bin/python3 scripts/marble_cauldron.py --live --yes-i-read-the-guide

API: POST https://api.atlas-beta.worldlabs.ai/api/v2/tasks:atlasGenerate
(?wait=true blocks). Key NEVER on CLI, never printed. Beta billing unknown
— first live call reveals it; treat as spend, ask first every time.
Law: docs/VENUEGUIDE.md (P0 waiver: dressed draft accepted, rebuild bare v2).
"""
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
API = "https://api.atlas-beta.worldlabs.ai"
SITE = "https://funnier.si/static/concepts"

# P0 anchors: two views, ONE room (fal-b front + ang-b side).
ANCHORS = [
    {"file": "fal-b.png", "cam": [0, 2.2, 7.0], "fov": 46},
    {"file": "ang-b.jpg", "cam": [3.5, 1.8, 2.0], "fov": 40},
]

# P0 prompt: dressed room (matches anchors). Shell-only rebuild is v2.
PROMPT = (
    "small intimate basement comedy club, matte-black painted brick walls, "
    "worn wooden stage with a single microphone stand center, round tables "
    "and chairs gathered close around the stage, low ceiling, dim warm "
    "light, grungy and worn, empty room, no people"
)

W, H = 1280, 720


def _fx(fov_deg):
    return round((W / 2) / math.tan(math.radians(fov_deg / 2)), 1)


def _cam(pos, fov):
    x, y, z = pos
    fx = _fx(fov)
    return {"extrinsics": {"position": [x, y, z],
                           "quaternion": [0, 0, 0, 1],  # first-pass; verify
                           "coordinateSystem": "rub"},
            "intrinsics": {"fx": fx, "fy": fx, "cx": W / 2, "cy": H / 2,
                           "width": W, "height": H}}


def build():
    v = json.loads((BASE / "docs" / "venues" / "cauldron.json").read_text())
    context = [{"imageAsset": {"url": f"{SITE}/{a['file']}"},
                "camera": _cam(a["cam"], a["fov"])} for a in ANCHORS]
    targets = [_cam(c["pos"], c["fov"]) for c in v["cameras"]]
    return {"contextFrames": context, "targetCameras": targets,
            "prompt": PROMPT, "enhancePrompt": False}, v


def _post(path, key, body):
    import time
    import random
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode(), method="POST",
        headers={"WLT-Api-Key": key, "Content-Type": "application/json",
                 "Idempotency-Key":
                 f"cauldron-{int(time.time())}-{random.randrange(1e9):09d}"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode())


def main():
    args = sys.argv[1:]
    live = "--live" in args
    payload, venue = build()
    print(f"anchors: {len(payload['contextFrames'])} "
          f"({', '.join(a['file'] for a in ANCHORS)}, same room two views)")
    print(f"targets: {len(payload['targetCameras'])} house cameras")
    print(f"venue: {venue['id']} ({venue['size']}, GLB budget "
          f"{venue['budgets']['glb_mb']}MB)")
    print("generate JSON (exact, review before --live):")
    print(json.dumps(payload, indent=2)[:2500])

    if not live:
        print("\nDRY RUN — $0 spent, nothing sent.")
        print("Next after owner yes: tasks:atlasGenerate → splat → "
              "tasks:splats2Mesh → GLB → decimate → pin + load in three.js.")
        print("Law waiver P0: dressed draft accepted (VENUEGUIDE.md); bare rebuild is v2.")
        return 0

    if "--yes-i-read-the-guide" not in args:
        print("REFUSING --live: add --yes-i-read-the-guide (VENUEGUIDE.md).",
              file=sys.stderr)
        return 2
    key = os.environ.get("WLT_API_KEY", "")
    if not key or len(key) < 8:
        print("REFUSING: WLT_API_KEY missing in environment.", file=sys.stderr)
        return 2
    print("\nLIVE — phase 1: posing anchors (key from env, never printed)...")
    posed = []
    for a in ANCHORS:
        op = _post("/api/v2/tasks:images2PosedRGBD?wait=true", key,
                   {"frames": [{"imageAsset": {"url": f"{SITE}/{a['file']}"}}],
                    "targetResolution": [1280, 720]})
        fr = ((op.get("response") or {}).get("frames") or op.get("frames") or [])
        if not fr:
            print(f"POSE FAILED for {a['file']}: {str(op)[:300]}")
            return 1
        f0 = fr[0]
        posed.append({"imageAsset": f0["imageAsset"], "camera": f0["camera"],
                      "depth": f0.get("depth")})
        print(f"  posed {a['file']}")
    print("LIVE — phase 2: generating views...")
    payload = {"contextFrames": posed,
               "targetCameras": [_cam(c["pos"], c["fov"]) for c in
                                 json.loads((BASE / "docs" / "venues" / "cauldron.json").read_text())["cameras"]],
               "prompt": PROMPT, "enhancePrompt": False}
    op = _post("/api/v2/tasks:atlasGenerate?wait=true", key, payload)
    Path("/tmp/cauldron_generate.json").write_text(json.dumps(op, indent=2)[:12000])
    print(f"state: {op.get('state') or op.get('status')}")
    print("op saved: /tmp/cauldron_generate.json — next: splats2Mesh, ONLY on owner yes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
