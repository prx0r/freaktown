#!/usr/bin/env python3
"""Build AU prosody timeline for a take: set.wav -> aus.json.

Opt-in, additive: sits next to visemes.json (mouth) as the upper-face
track (brows/eyes/blink). The stage merges both on one clock; prosody
offsets stay small and additive under beat/reactor emotions.

Usage: python3 scripts/build_aus.py --take data/takes/kappa-kyle
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from backend.services.funnier.au_track import build_aus  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", required=True)
    a = ap.parse_args()
    wav_path = os.path.join(a.take, "set.wav")
    frames = build_aus(wav_path)
    dest = os.path.join(a.take, "aus.json")
    json.dump({"schema": "pog.au-prosody.v1", "frame_ms": 40,
               "frames": frames}, open(dest, "w"))
    accents = sum(1 for f in frames if f["accent"] >= 0.5)
    blinks = sum(f["phrase_end"] for f in frames)
    print(f"{a.take}: {len(frames)} AU frames, {accents} brow flashes, "
          f"{blinks} phrase blinks -> {dest}")


if __name__ == "__main__":
    main()
