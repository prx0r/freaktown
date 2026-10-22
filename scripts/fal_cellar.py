#!/usr/bin/env python3
"""Cellar-DNA via FAL reference-edit models (PAID — owner said yes in chat).

Ref: /tmp/cellar-user.jpg (user-supplied show photo, input ONLY).
Models (all confirmed endpoint IDs):
  fal-a  fal-ai/flux-pro/kontext      $0.04 flat
  fal-b  fal-ai/flux-2/edit           ~$0.024 (per-MP in+out)
  fal-c  fal-ai/nano-banana-2/edit    ~$0.08 (1K)
Max total ≈ $0.15. Failed requests don't bill.

  FAL_API_KEY=... /usr/bin/python3 scripts/fal_cellar.py
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "concepts"
REF = Path("/tmp/cellar-user.jpg")
KEY = os.environ.get("FAL_API_KEY", "")

PROMPT = ("Same intimate brick basement comedy club, completely empty with "
          "no people, matte-black painted brick walls, worn wooden stage "
          "with a single microphone stand, round tables and chairs gathered "
          "close around the stage, low ceiling, dim warm light, grungy and "
          "worn, photorealistic")

JOBS = [
    ("fal-a", "fal-ai/flux-pro/kontext", {"prompt": PROMPT}, 0.04),
    ("fal-b", "fal-ai/flux-2/edit", {"prompt": PROMPT}, 0.03),
    ("fal-c", "fal-ai/nano-banana-2/edit", {"prompt": PROMPT}, 0.09),
]

# Phase 2 (owner: "each from a different angle"): same rooms, new
# viewpoints. Refs are our own published frames (public URLs). Kontext pro
# throughout for consistent scene preservation. $0.04 each = $0.12.
SITE = "https://funnier.si/static/concepts"
ANGLE_JOBS = [
    ("ang-a", "fal-ai/flux-pro/kontext",
     "Same dark-brick basement comedy club as the reference photo, but from the small stage looking out over the room: rows of empty cocktail tables and chairs facing the camera position, low pipe ceiling, wall sconce glowing, red glow at the rear, empty, no people, photorealistic",
     f"{SITE}/fal-a.jpg", 0.04),
    ("ang-b", "fal-ai/flux-pro/kontext",
     "Same black-brick comedy room with lone microphone as the reference, but from a side wing angle: stage diagonal with mic stand in profile, tables wrapping two sides, curtain fold dark at frame edge, moody, empty, no people, photorealistic",
     f"{SITE}/fal-b.png", 0.04),
    ("ang-c", "fal-ai/flux-pro/kontext",
     "Same brick comedy club with pillars and rugs as the reference photo, but from a high rear booth: full room below, tiny stage far away with mic, tables and chairs grid, bar at the back, empty, no people, photorealistic",
     f"{SITE}/fal-c.png", 0.04),
]


# Public source of the ref (user-supplied): FAL fetches it directly, so no
# storage upload is needed. Ref stays input-only; gallery shows our outputs.
REF_URL = ("https://images.squarespace-cdn.com/content/v1/"
           "5856f0bf46c3c4926dfaed81/1662758433649-W81UWLBP4CJ4V4EICVNQ/"
           "Cellar-ComedyNight-7.jpg?format=2500w")


def api(path, body=None, host="https://fal.run", timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        host + path, data=data,
        method="POST" if body is not None else "GET",
        headers={"Authorization": f"Key {KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def upload(local):
    import mimetypes
    boundary = "----cauldron123"
    ctype = mimetypes.guess_type(local.name)[0] or "image/jpeg"
    blob = (f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="file"; filename="{local.name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode() + local.read_bytes() \
        + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://rest.alpha.fal.ai/storage/upload", data=blob, method="POST",
        headers={"Authorization": f"Key {KEY}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())["url"]


def run_model(endpoint, payload):
    # Sync fal.run (queue path 405s from this box; sync completes ~1-2 min).
    out = api(f"/{endpoint}", payload, host="https://fal.run", timeout=600)
    return out


def main():
    global KEY
    import datetime
    if not KEY:
        print("REFUSING: FAL_API_KEY missing.", file=sys.stderr)
        return 2
    phase2 = "--angles" in sys.argv
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not phase2 and not REF.exists():
        print("REFUSING: ref missing.", file=sys.stderr)
        return 2
    ref_url = REF_URL
    print("using public ref URL (no upload needed).")
    spent_hint = 0.0
    jobs = ([(s, e, {"prompt": p, "image_url": u}, c) for s, e, p, u, c in ANGLE_JOBS]
            if phase2 else JOBS)
    for shot, endpoint, extra, est in jobs:
        payload = dict(extra)
        if phase2:
            ref = extra.get("image_url")
        else:
            ref = ref_url
            if "kontext" in endpoint:
                payload["image_url"] = ref
            else:
                payload["image_urls"] = [ref]
        try:
            out = run_model(endpoint, payload)
            imgs = (out.get("images") or out.get("data") or [])
            url = imgs[0]["url"] if imgs else None
            if not url:
                raise RuntimeError(str(out)[:200])
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=180) as r:
                img = r.read()
            ext = ".png" if ".png" in url else ".jpg"
            (OUT / f"{shot}{ext}").write_bytes(img)
            (OUT / f"{shot}.json").write_text(json.dumps({
                "shot": shot, "model": endpoint, "file": f"{shot}{ext}",
                "ref": ("own frame " + payload.get("image_url", "")
                        if phase2 else "user show photo (input only, never published)"),
                "prompt": payload.get("prompt", ""), "cost": f"~${est:.3f} (FAL, owner-approved)",
                "generated_at": now, "status": "draft-unreviewed",
                "anchor_eligible": False,
            }, indent=2) + "\n")
            spent_hint += est
            print(f"OK {shot} ({len(img)//1024}KB, ~${est:.3f})")
        except Exception as e:
            print(f"FAIL {shot}: {e}")
    print(f"done — estimated ~${spent_hint:.3f} (see FAL billing for exact).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
