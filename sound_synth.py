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

# Melody mode: vibe → scale (semitone offsets). Paranoid gets the
# tritone-heavy locrian-ish set. Unknown vibes fall back to major pent.
VIBE_SCALES = {
    "paranoid":     [0, 1, 3, 5, 6, 8, 10],
    "menacing":     [0, 1, 5, 7, 8],
    "mysterious":   [0, 2, 3, 7, 8],
    "melancholic":  [0, 3, 5, 7, 10],
    "chaotic":      [0, 1, 4, 6, 7, 10],
    "absurd":       [0, 2, 3, 6, 9],
    "sleazy":       [0, 3, 5, 6, 10],
    "chill":        [0, 2, 5, 7, 9],
    "confident":    [0, 2, 4, 7, 9],
    "heroic":       [0, 2, 4, 7, 9],
    "triumphant":   [0, 4, 5, 7, 11],
    "dark":         [0, 2, 3, 7, 8],
    "spooky":       [0, 1, 6, 7, 8],
    "playful":      [0, 2, 5, 7, 9],
    "romantic":     [0, 2, 4, 9, 11],
    "epic":         [0, 2, 4, 7, 11],
}
DEFAULT_SCALE = [0, 2, 4, 7, 9]

SCALE_NAMES = {
    "paranoid": "tritone-heavy Locrian-ish", "menacing": "Phrygian-ish",
    "mysterious": "enigmatic", "melancholic": "minor pentatonic",
    "chaotic": "chromatic-leaning", "absurd": "whole-tone-leaning",
    "sleazy": "minor blues-ish", "chill": "major pentatonic",
    "confident": "major pentatonic", "heroic": "major pentatonic",
    "triumphant": "lydian-leaning", "dark": "aeolian-leaning",
    "spooky": "Locrian-leaning", "playful": "major pentatonic",
    "romantic": "major-leaning", "epic": "lydian-major",
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
              "F#", "G", "G#", "A", "A#", "B"]


def _motif(rng, scale):
    """Seeded 1-bar motif: stepwise markov walk over scale degrees + the
    euclidean placement mask. THE single source of truth — renderer and
    describer both consume this, so agents read the notes actually played."""
    deg = rng.randrange(len(scale))
    motif = []
    for _ in range(8):
        motif.append(deg)
        step = rng.choices([-2, -1, -1, 0, 1, 1, 2, -4, 4],
                           weights=[8, 18, 18, 10, 18, 18, 8, 1, 1])[0]
        deg = max(0, min(11, deg + step))
    return motif, _euclidean(5, 8)


def _degree_name(degree: int, scale: list, root_shift: int) -> str:
    semi = scale[degree % len(scale)] + 12 * (degree // len(scale))
    midi = 45 + root_shift + semi  # root 110Hz concert pitch naming
    return f"{NOTE_NAMES[midi % 12]}{(midi // 12) - 1}"


def describe(recipe: dict, seed: int = 0) -> dict:
    """Agent-readable score: key, scale, motif notes, sections, arc.
    Deterministic — same (recipe, seed) describes the exact tune rendered.
    Pattern mode describes the riff engine instead of a motif."""
    genre = (recipe or {}).get("genre", "funk")
    g = GENRES.get(genre, GENRES["funk"])
    mood = (recipe or {}).get("mood", "confident")
    energy = (recipe or {}).get("energy", "high")
    mode = (recipe or {}).get("mode", "pattern")
    duration = min(11, max(2, float((recipe or {}).get("duration", 8))))
    root_shift = MOOD_ROOT.get(mood, 0)
    out = {"mode": mode, "bpm": g["bpm"], "drums": g["drums"],
           "duration_s": duration, "energy": energy, "mood": mood}
    if mode != "melody":
        out.update({"kind": "riff-groove",
                    "bass_pattern": [x + root_shift for x in g["bass"]],
                    "text": (f"{g['bpm']} BPM {genre} groove in a loop, "
                             f"bass riff {g['bass']}, {energy} energy.")})
        return out
    scale = VIBE_SCALES.get(mood, DEFAULT_SCALE)
    rng = random.Random(
        f"{genre}|{mood}|{energy}|{(recipe or {}).get('shape', 'hit')}|melody|{seed}")
    motif, mask = _motif(rng, scale)
    notes = [_degree_name(d, scale, root_shift) for d in motif]
    sounded = [n for n, on in zip(notes, mask) if on]
    n_bars = max(1, int(duration / ((60.0 / g["bpm"]) * 4)))
    roles = ["repeat", "repeat", "lift", "resolve"]
    sections = [roles[i % 4] for i in range(n_bars)]
    bass_root = _degree_name(motif[0], scale, root_shift)
    out.update({
        "kind": "seeded-tune",
        "scale": SCALE_NAMES.get(mood, "major pentatonic"),
        "scale_degrees": scale,
        "motif": notes,
        "motif_sounded": sounded,
        "bass_root": bass_root,
        "sections": sections,
        "text": (f"{g['bpm']} BPM {SCALE_NAMES.get(mood, 'major pentatonic')} tune "
                 f"in {mood} mood. Motif: {' '.join(sounded)}. "
                 f"Bass sits on {bass_root}. "
                 f"It repeats, lifts, then resolves home. {energy} energy, {duration:g}s."),
    })
    return out


def music_event(recipe: dict, seed: int = 0, participant: str = "") -> dict:
    """FreakEvent-shaped music.started payload: agents observe this."""
    d = describe(recipe, seed)
    return {"type": "music.started", "payload": {**d, "participant": participant}}


def _euclidean(pulses: int, steps: int) -> list[bool]:
    """Bjorklund-style rhythm mask, downbeat always sounds."""
    if pulses >= steps:
        return [True] * steps
    mask = [False] * steps
    bucket = 0
    for i in range(steps):
        bucket += pulses
        if bucket >= steps:
            bucket -= steps
            mask[i] = True
    mask[0] = True
    return mask


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
    """Walkout WAV. recipe: {genre, mood, energy, shape, duration, mode}.
    mode "pattern" (default): riff/groove engine. mode "melody": seeded
    vibe-arranged tune — markov motif, repeat/lift/resolve phrasing,
    euclidean rhythm, bass on motif roots. Same drums, same render path.
    Deterministic per (recipe, seed) in both modes."""
    genre = recipe.get("genre", "funk") if isinstance(recipe, dict) else "funk"
    g = GENRES.get(genre, GENRES["funk"])
    mood = recipe.get("mood", "confident") if isinstance(recipe, dict) else "confident"
    energy = recipe.get("energy", "high") if isinstance(recipe, dict) else "high"
    shape = recipe.get("shape", "hit") if isinstance(recipe, dict) else "hit"
    mode = recipe.get("mode", "pattern") if isinstance(recipe, dict) else "pattern"
    duration = min(11, max(2, float(recipe.get("duration", 8)))) if isinstance(recipe, dict) else 8

    rng = random.Random(
        f"{genre}|{mood}|{energy}|{shape}|{seed}"
        + (f"|{mode}" if mode == "melody" else ""))
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

    if mode == "melody":
        _render_melody(samples, g, mood, root_shift, beat, duration, env, rng)
    else:
        _render_pattern(samples, g, root_shift, beat, duration, env, rng)

    _render_drums(samples, g["drums"], beat, duration, env, rng)
    return _finish(samples, gain, duration)


def _render_pattern(samples, g, root_shift, beat, duration, env, rng):
    """Original riff engine: bass pattern + lead stabs on 1 and 3."""
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


def _render_melody(samples, g, mood, root_shift, beat, duration, env, rng):
    """Seeded tune: markov 1-bar motif, repeat/lift/resolve phrasing,
    euclidean placement, bass on motif roots."""
    scale = VIBE_SCALES.get(mood, DEFAULT_SCALE)

    # 1-bar motif + placement mask from the single source of truth
    motif, mask = _motif(rng, scale)
    slot = beat / 2
    n_bars = max(1, int(duration / (beat * 4)))

    for bar in range(n_bars):
        role = bar % 4  # 0 repeat, 1 repeat, 2 lift, 3 resolve
        lift = 3 if role == 2 else 0
        for s in range(8):
            if not mask[s]:
                continue
            d = motif[s] + lift
            if role == 3 and s == 7:
                d = 0  # resolve home on the last hit
            semi = scale[d % len(scale)] + 12 * (d // len(scale))
            semi += root_shift + 12
            tt0 = bar * beat * 4 + s * slot
            if tt0 >= duration:
                break
            f = _freq(semi)
            ndur = min(slot * 0.92, duration - tt0)
            for i in range(int(SR * ndur)):
                tt = tt0 + i / SR
                decay = max(0.0, 1 - i / (SR * max(ndur, 1e-6)))
                samples[int(tt * SR)] += _osc("sine", f, tt) * 0.5 * decay * env(tt)
        # bass follows the motif root: quarter-note roots, genre wave
        root_semi = scale[motif[0] % len(scale)] + root_shift
        rf = _freq(root_semi)
        for q in range(4):
            tt0 = bar * beat * 4 + q * beat
            if tt0 >= duration:
                break
            bdur = min(beat * 0.85, duration - tt0)
            for i in range(int(SR * bdur)):
                tt = tt0 + i / SR
                decay = max(0.0, 1 - i / (SR * max(bdur, 1e-6)))
                samples[int(tt * SR)] += _osc(g["wave"], rf, tt) * 0.35 * decay * env(tt)


def _render_drums(samples, kit, beat, duration, env, rng):
    """drums: kick on quarters, hats on 8ths, snare on 2&4 (varies by kit)"""
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


def _finish(samples, gain, duration) -> bytes:
    """normalize + hard ending + WAV encode. Shared by both modes."""
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
