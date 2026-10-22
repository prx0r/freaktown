#!/usr/bin/env python3
"""Cellar-DNA transforms: real Comedy Cellar photo -> Cauldron ($0 neurons).

Reference: /tmp/cellar-ref.jpg (Wikimedia CC BY-SA, input ONLY — never
published; gallery shows our outputs). Model: runway SD1.5-inpainting
img2img (image_b64 + strength + seed). Outputs are DRESSED previews
(mic/tables preserved); validator marks them accordingly.

  source /root/.r2-env && /usr/bin/python3 scripts/cellar_dna.py
"""
import base64
import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "concepts"
MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
REF = Path("/tmp/cellar-ref.jpg")

TAKES = [
    ("dna-a", 0.55, 11, "same intimate brick comedy club, but matte-black painted brick instead of red wash, smudged chalk cauldron outline on the wall where the sign was, no text, no logos, grungier, worn wood, dim warm lamps, empty, no people"),
    ("dna-b", 0.7, 22, "dark dingy underground comedy cellar, near-black brick, small stage with mic, round tables close around it, low black ceiling, faint green exit glow at the rear, moody, empty, no people"),
    ("dna-c", 0.45, 33, "same cozy brick comedy room, keep the warm lamps and wood, blacken the brick, replace the wall sign with a hand-drawn chalk mark, remove all text, intimate basement club, empty, no people"),
]


def run(ref_b64, prompt, strength, seed, token, acct):
    body = json.dumps({"prompt": prompt, "image_b64": ref_b64,
                       "strength": strength, "seed": seed,
                       "width": 1024, "height": 768,
                       "num_steps": 20}).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODEL}",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    if "json" in r.headers.get("Content-Type", ""):
        raise RuntimeError(data[:200].decode(errors="replace"))
    return data


def main():
    token = os.environ.get("CF_API_TOKEN", "")
    acct = os.environ.get("CF_ACCOUNT_ID", "")
    if not token or not acct or not REF.exists():
        print("REFUSING: creds or /tmp/cellar-ref.jpg missing.", file=sys.stderr)
        return 2
    ref_b64 = base64.b64encode(REF.read_bytes()).decode()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for shot, strength, seed, prompt in TAKES:
        try:
            img = run(ref_b64, prompt, strength, seed, token, acct)
            (OUT / f"{shot}.png").write_bytes(img)
            (OUT / f"{shot}.json").write_text(json.dumps({
                "shot": shot, "model": MODEL, "seed": seed,
                "strength": strength, "ref": "wikimedia Comedy Cellar stage (CC BY-SA, input only)",
                "prompt": prompt, "cost": "$0 (CF neurons)",
                "generated_at": now, "status": "draft-unreviewed",
                "anchor_eligible": False,
            }, indent=2) + "\n")
            print(f"OK {shot} ({len(img)//1024}KB, strength {strength})")
        except Exception as e:
            print(f"FAIL {shot}: {e}")
    print("done — $0 spent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
