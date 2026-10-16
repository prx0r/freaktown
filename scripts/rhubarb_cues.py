#!/usr/bin/env python3
"""Rhubarb phoneme lipsync for one P0 set: wav + lines -> mouth cues.

Reads <setdir>/set.wav + <setdir>/set_plan.json, runs the Rhubarb binary,
and writes <setdir>/mouth_cues_rhubarb.json as pog.mouth-cues.v1:
the ORIGINAL Rhubarb poses (A-H, X) with the source audio sha — never a
collapsed open/closed guess (FT-04). The jaw ANGLE per pose is a separate
render concern; we ship a first calibration here and the renderer reads it:

  A closed 0.0 | B slight -0.08 | C medium -0.2 | D wide -0.35
  E rounded -0.15 | F puckered -0.1 | G teeth-on-lip -0.1 | H tongue -0.12
  X rest 0.0 (pauses keep the rest mouth: no talking motion in silence)

Usage: python3 scripts/rhubarb_cues.py --setdir data/p0/dr-peel
Then render with: --mouth <setdir>/mouth_cues_rhubarb.json
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

ANGLE = {"A": 0.0, "B": -0.08, "C": -0.2, "D": -0.35, "E": -0.15,
         "F": -0.1, "G": -0.1, "H": -0.12, "X": 0.0}

RHUBARB = (os.environ.get("RHUBARB") or
           (glob.glob("/tmp/opencode/rhubarb/Rhubarb-Lip-Sync-*/rhubarb") + [""])[0])


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setdir", required=True)
    ap.add_argument("--rhubarb", default=RHUBARB)
    a = ap.parse_args()
    if not a.rhubarb or not os.path.exists(a.rhubarb):
        sys.exit("rhubarb binary not found (tried " + str(a.rhubarb) + ")")
    plan = json.load(open(os.path.join(a.setdir, "set_plan.json")))
    wav = os.path.join(a.setdir, "set.wav")
    dialog = os.path.join(a.setdir, ".rhubarb_dialog.txt")
    with open(dialog, "w") as f:
        for line in plan["lines"]:
            f.write("POG\t%s\n" % line.replace("\t", " "))
    out = os.path.join(a.setdir, ".rhubarb_raw.json")
    r = subprocess.run([a.rhubarb, "-f", "json", "-o", out, "--dialogFile", dialog, wav],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        sys.exit("rhubarb failed")
    raw = json.load(open(out))
    cues = [{"start_ms": int(c.get("start", 0) * 1000),
             "end_ms": int(c.get("end", 0) * 1000),
             "pose": c.get("value", "X"),
             "angle": ANGLE.get(c.get("value", "X"), 0.0)}
            for c in raw.get("mouthCues", [])]
    doc = {"schema": "pog.mouth-cues.v1", "source_audio_sha256": sha(wav),
           "angle_calibration": "v1-first-pass", "cues": cues}
    dest = os.path.join(a.setdir, "mouth_cues_rhubarb.json")
    json.dump(doc, open(dest, "w"), indent=1)
    print(f"{a.setdir}: {len(cues)} phoneme cues -> {dest}")


if __name__ == "__main__":
    main()
