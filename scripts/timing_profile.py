#!/usr/bin/env python3
"""Voice timing profiler: measured delivery vs planned delivery.

Usage:
  python3 scripts/timing_profile.py --audio /tmp/pilot/set.wav \
    --timeline /tmp/pilot/timeline.json --out /tmp/pilot/timing.json

Stdlib only. Energy contour (40ms RMS), pause inventory, speech rate,
pre/post-punchline holds measured against the delivery plan.
"""
import argparse
import array
import json
import math
import wave


def load(path):
    with wave.open(path) as w:
        n, sr, sw, ch = w.getnframes(), w.getframerate(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(n)
    smp = array.array({1: "b", 2: "h"}[sw], raw)
    if ch == 2:
        smp = smp[0::2]
    peak = float(2 ** (8 * sw - 1))
    return [x / peak for x in smp], sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    smp, sr = load(a.audio)
    tl = json.load(open(a.timeline))
    win = max(1, int(sr * 0.04))
    frames = []
    for i in range(0, len(smp), win):
        seg = smp[i:i + win]
        rms = math.sqrt(sum(x * x for x in seg) / max(1, len(seg)))
        frames.append(20 * math.log10(rms + 1e-9))
    # pauses: runs below -38dB longer than 250ms
    pauses, run = [], None
    for i, db in enumerate(frames):
        t = i * 0.04
        if db < -38.0 and run is None:
            run = t
        elif db >= -38.0 and run is not None:
            if t - run >= 0.25:
                pauses.append({"start_ms": int(run * 1000), "dur_ms": int((t - run) * 1000)})
            run = None
    words = sum(len(t["text"].split()) for t in tl)
    dur_s = len(smp) / sr
    punch = next((t for t in tl if t["type"] == "punchline"), tl[-1])
    def overlaps(p, lo, hi, mind=400):
        return p["start_ms"] < hi and p["start_ms"] + p["dur_ms"] > lo and p["dur_ms"] >= mind
    pre = next((p for p in pauses
                if overlaps(p, punch["start_ms"] - 800, punch["start_ms"] + 200)), None)
    post = next((p for p in pauses
                 if overlaps(p, punch["end_ms"] - 200, punch["end_ms"] + 1500)), None)
    voiced = [db for db in frames if db >= -38.0]
    out = {
        "duration_s": round(dur_s, 1),
        "speech_rate_wps": round(words / dur_s, 2),
        "energy_db": {"mean_voiced": round(sum(voiced) / max(1, len(voiced)), 1),
                      "dynamic_range": round(max(frames) - min(frames), 1)},
        "pauses": pauses,
        "pre_punch_pause_ms": (pre["dur_ms"] if pre else 0),
        "pre_punch_planned_ms": punch.get("pause_before_ms", 0),
        "post_punch_hold_ms": (post["dur_ms"] if post else 0),
        "post_punch_planned_ms": punch.get("pause_after_ms", 0),
        "beat_count": len(tl),
    }
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


main()
