#!/usr/bin/env python3
"""Build speakAudio visemes for a take: timeline.json -> visemes.json.

Opt-in, additive: existing take files untouched. The stage plays
visemes.json when present (MorphVisemePlayer, ARKit/Oculus blendshapes);
otherwise it keeps the old analyser/syllable behaviour.

Timelines with estimated spans can run past the real audio (known take
drift); frames are clamped to set.wav's measured duration and the drift
is reported — the mouth never moves in silence.

Usage: python3 scripts/build_visemes.py --take data/takes/kappa-kyle
"""
import argparse
import json
import os
import sys
import wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from backend.services.freaktown.viseme_text import build_take_visemes


def audio_ms(wav_path):
    with wave.open(wav_path, "rb") as w:
        return int(w.getnframes() / w.getframerate() * 1000)


def clamp(doc, limit_ms):
    """Drop frames starting past the audio; trim ones crossing the end.
    Returns (doc, dropped, trimmed_ms)."""
    vs, vt, vd = doc["visemes"], doc["vtimes"], doc["vdurations"]
    kept = [(v, t, d) for v, t, d in zip(vs, vt, vd) if t < limit_ms]
    dropped = len(vs) - len(kept)
    trimmed = 0
    out_v, out_t, out_d = [], [], []
    for v, t, d in kept:
        if t + d > limit_ms:
            trimmed += (t + d) - limit_ms
            d = max(20, limit_ms - t)
        out_v.append(v)
        out_t.append(t)
        out_d.append(d)
    doc = dict(doc, visemes=out_v, vtimes=out_t, vdurations=out_d)
    return doc, dropped, trimmed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", required=True)
    a = ap.parse_args()
    tl_path = os.path.join(a.take, "timeline.json")
    timeline = json.load(open(tl_path))
    doc = build_take_visemes(timeline)
    wav_path = os.path.join(a.take, "set.wav")
    drift_note = ""
    if os.path.exists(wav_path):
        limit = audio_ms(wav_path)
        doc, dropped, trimmed = clamp(doc, limit)
        if dropped or trimmed:
            drift_note = (f" [drift: timeline ran long, "
                          f"dropped {dropped}, trimmed {trimmed}ms "
                          f"to audio {limit}ms]")
    dest = os.path.join(a.take, "visemes.json")
    json.dump(doc, open(dest, "w"), indent=1)
    print(f"{a.take}: {len(doc['visemes'])} visemes "
          f"over {len(doc['words'])} words -> {dest}{drift_note}")


if __name__ == "__main__":
    main()
