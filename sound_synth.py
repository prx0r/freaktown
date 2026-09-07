#!/usr/bin/env python3
"""Procedural walkout synth — 8-second character stings, no GPU, no API.

Genre + mood + energy + shape in, WAV out. Deterministic per (recipe, seed).
Good enough for comedy walk-ons; a model backend can replace it later
without changing the recipe format (see walkout.json in freak bundles).
"""

import hashlib
import math
import random
import struct
import wave
from io import BytesIO
from pathlib import Path

SR = 24000

GENRES = {
    "funk":       {"bpm": 118, "bass": [0, 0, 7, 0, 10, 0, 7, 5], "wave": "square",
                   "drums": "funk", "lead": [12, 15, 12, 10]},
    "rock":       {"bpm": 138, "bass": [0, 0, 0, 0, 5, 0, 3, 0], "wave": "saw",
                   "drums": "rock", "lead": [0, 0, 12, 0]},
    "electronic": {"bpm": 128, "bass": [0, 0, 0, 0, 0, 0, 0, 7], "wave": "saw",
                   "drums": "four", "lead": [12, 12, 15, 19]},
    "jazz":       {"bpm": 108, "bass": [0, 4, 7, 4, 0, 4, 7, 9], "wave": "sine",
                   "drums": "brush", "lead": [7, 9, 12, 9]},
    "orchestral": {"bpm": 100, "bass": [0, 0, 7, 0, 5, 0, 7, 12], "wave": "sine",
                   "drums": "timpani", "lead": [12, 16, 19, 24]},
    "comedy":     {"bpm": 100, "bass": [0, 7, 0, 7, 0, 7, 5, 7], "wave": "square",
                   "drums": "oompah", "lead": [12, 0, 12, 0]},
    "hip-hop":    {"bpm": 92, "bass": [0, 0, 0, 7, 0, 0, 5, 3], "wave": "sine",
                   "drums": "boom", "lead": [0, 3, 5, 3]},
    "disco":      {"bpm": 120, "bass": [0, 0, 7, 0, 0, 0, 7, 10], "wave": "square",
                   "drums": "four", "lead": [12, 14, 12, 10]},
}

MOOD_ROOT = {
    "heroic": 0, "confident": 2, "absurd": 6, "menacing": -4,
    "chill": -7, "chaotic": 1, "sleazy": -2, "mysterious": -5,
    "triumphant": 5, "melancholic": -9,
}

ENERGY_GAIN = {"low": 0.35, "medium": 0.55, "high": 0.75, "unhinged": 0.9}


def _freq(semitones: int, root: float = 110.0) -> float:
    return root * (2 ** (semitones / 12))


def _osc(wave_type: str, freq: float, t: float) -> float:
    ph = 2 * math.pi * freq * t
    if wave_type == "sine":
        return math.sin(ph)
    if wave_type == "square":
        return 0.6 if math.sin(ph) > 0 else -0.6
    # saw
    return 2 * ((freq * t) % 1) - 1


def generate(recipe: dict, seed: int = 0) -> bytes:
    """Generate an 8s walkout WAV. recipe: {genre, mood, energy, shape, duration}."""
    genre = recipe.get("genre", "funk") if isinstance(recipe, dict) else "funk"
    g = GENRES.get(genre, GENRES["funk"])
    mood = recipe.get("mood", "confident") if isinstance(recipe, dict) else "confident"
    energy = recipe.get("energy", "high") if isinstance(recipe, dict) else "high"
    shape = recipe.get("shape", "hit") if isinstance(recipe, dict) else "hit"
    duration = min(11, max(2, float(recipe.get("duration", 8)))) if isinstance(recipe, dict) else 8

    rng = random.Random(f"{genre}|{mood}|{energy}|{shape}|{seed}")
    gain = ENERGY_GAIN.get(energy, 0.6)
    root_shift = MOOD_ROOT.get(mood, 0)
    beat = 60.0 / g["bpm"]
    n = int(SR * duration)
    samples = [0.0] * n

    # shape envelope
    def env(t: float) -> float:
        x = t / duration
        if shape == "hit":
            return 1.0 if x < 0.7 else max(0.0, 1 - (x - 0.7) / 0.3)
        if shape == "build":
            return min(1.0, 0.25 + x)
        if shape == "fanfare":
            return 1.0 if x < 0.5 else (0.4 if x < 0.6 else 1.0 if x < 0.85 else max(0.0, 1 - (x - 0.85) / 0.15))
        if shape == "weird":
            return 0.8 + 0.2 * math.sin(40 * x)
        return 0.9  # groove: steady

    # bass line (8th notes cycling the pattern)
    step = beat / 2
    idx = 0
    t = 0.0
    while t < duration:
        semi = g["bass"][idx % len(g["bass"])] + root_shift
        f = _freq(semi)
        dur = min(step * 0.9, duration - t)
        for i in range(int(SR * dur)):
            tt = t + i / SR
            samples[int(tt * SR)] += _osc(g["wave"], f, tt) * 0.45 * env(tt)
        t += step
        idx += 1

    # lead stabs on beats 1 and 3
    for bar in range(int(duration / (beat * 4)) + 1):
        for b in (0, 2):
            tt0 = bar * beat * 4 + b * beat
            if tt0 >= duration:
                break
            semi = rng.choice(g["lead"]) + root_shift + 12
            f = _freq(semi)
            for i in range(int(SR * 0.28)):
                tt = tt0 + i / SR
                if tt >= duration:
                    break
                decay = max(0.0, 1 - i / (SR * 0.28))
                samples[int(tt * SR)] += _osc("square", f, tt) * 0.22 * decay * env(tt)

    # drums: kick on quarters, hats on 8ths, snare on 2&4 (varies by kit)
    kit = g["drums"]
    t = 0.0
    eighth = 0
    while t < duration:
        is_quarter = eighth % 2 == 0
        beat_pos = (eighth // 2) % 4
        # kick
        if is_quarter and kit in ("rock", "four", "disco", "boom", "funk"):
            for i in range(int(SR * 0.12)):
                tt = t + i / SR
                if tt >= duration:
                    break
                decay = max(0.0, 1 - i / (SR * 0.12))
                samples[int(tt * SR)] += math.sin(2 * math.pi * 55 * tt) * 0.7 * decay * env(tt)
        # snare on 2 & 4
        if beat_pos in (1, 3) and kit in ("rock", "funk", "disco"):
            for i in range(int(SR * 0.09)):
                tt = t + i / SR
                if tt >= duration:
                    break
                decay = max(0.0, 1 - i / (SR * 0.09))
                samples[int(tt * SR)] += rng.uniform(-1, 1) * 0.35 * decay * env(tt)
        # hats
        for i in range(int(SR * 0.03)):
            tt = t + i / SR
            if tt >= duration:
                break
            decay = max(0.0, 1 - i / (SR * 0.03))
            samples[int(tt * SR)] += rng.uniform(-1, 1) * 0.12 * decay
        t += beat / 2
        eighth += 1

    # normalize + hard ending
    peak = max(1e-6, max(abs(s) for s in samples))
    out = [int(max(-1, min(1, s / peak * gain)) * 32767) for s in samples]
    fade = int(SR * 0.05)
    for i in range(fade):
        out[-(i + 1)] = int(out[-(i + 1)] * i / fade)

    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack(f"<{len(out)}h", *out))
    return buf.getvalue()


def recipe_id(recipe: dict, seed: int = 0) -> str:
    canon = json_dumps_sorted({**recipe, "seed": seed})
    return hashlib.sha256(canon.encode()).hexdigest()[:12]


def json_dumps_sorted(d: dict) -> str:
    import json as _j
    return _j.dumps(d, sort_keys=True)


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("walkout_test.wav")
    out.write_bytes(generate({"genre": "funk", "mood": "absurd", "energy": "high",
                              "shape": "hit", "duration": 8}))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
