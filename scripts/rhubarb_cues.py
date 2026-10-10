#!/usr/bin/env python3
"""Rhubarb phoneme lipsync for one P0 set: wav + lines -> mouth cues.

Reads <setdir>/set.wav + <setdir>/set_plan.json, runs the Rhubarb binary
(expected at /tmp/opencode/rhubarb/Rhubarb-Lip-Sync-*/rhubarb or --rhubarb),
maps mouth shapes to jaw open/close intervals, writes
<setdir>/mouth_cues_rhubarb.json in the same {start_ms,end_ms,shape} format
scripts/render_set.py --mouth already consumes. No code change downstream:
pass the rhubarb file as --mouth on the next render of a jawed set.

Open shapes (jaw drops): A C D E G. Closed: B F X (M/B/P, F/V, idle).
"""
import argparse
import glob
import json
import os
import subprocess
import sys

OPEN = set("ACDEG")

RHUBARB = (os.environ.get("RHUBARB") or
           (glob.glob("/tmp/opencode/rhubarb/Rhubarb-Lip-Sync-*/rhubarb") + [""])[0])


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
        for i, line in enumerate(plan["lines"]):
            f.write("POG\t%s\n" % line.replace("\t", " "))
    out = os.path.join(a.setdir, ".rhubarb_raw.json")
    r = subprocess.run([a.rhubarb, "-f", "json", "-o", out, "--dialogFile", dialog, wav],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        sys.exit("rhubarb failed")
    raw = json.load(open(out))
    cues = raw.get("mouthCues", [])
    intervals, cur = [], None
    for c in cues:
        v = c.get("value", "X")
        s, e = int(c.get("start", 0) * 1000), int(c.get("end", 0) * 1000)
        if v in OPEN:
            if cur is None:
                cur = [s, e]
            else:
                cur[1] = e
        else:
            if cur is not None and e - cur[0] >= 60:
                intervals.append({"start_ms": cur[0], "end_ms": cur[1], "shape": "open"})
                cur = None
    if cur is not None and cur[1] - cur[0] >= 60:
        intervals.append({"start_ms": cur[0], "end_ms": cur[1], "shape": "open"})
    dest = os.path.join(a.setdir, "mouth_cues_rhubarb.json")
    json.dump(intervals, open(dest, "w"), indent=1)
    print(f"{a.setdir}: {len(cues)} phoneme cues -> {len(intervals)} jaw-open intervals -> {dest}")


if __name__ == "__main__":
    main()
