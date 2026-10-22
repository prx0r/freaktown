"""Original procedural music: a warm night jingle (pad + low bells, no kick) and a soft bed.

Everything is synthesized from a seed: no samples, no third-party audio, so the result is
ours to use. Key and voicing come from the preset.
"""
from __future__ import annotations

import numpy as np

from .dsp import SR, rng, lowpass, highpass, fade

A4 = 440.0
NOTE = {n: i for i, n in enumerate("C C# D D# E F F# G G# A A# B".split())}


def hz(name: str) -> float:
    n, o = name[:-1], int(name[-1])
    return A4 * 2 ** ((NOTE[n] + 12 * (o - 4) - 9) / 12)


def pad(freqs, dur, sr, r, *, detune=0.004, bright=1400.0, attack=1.2, release=1.6):
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = np.zeros((n, 2))
    for f in freqs:
        for ch in range(2):
            for d in (-detune, 0.0, detune):
                ph = r.uniform(0, 6.28)
                ff = f * (1 + d + (0.0015 if ch else -0.0015))
                # soft saw: a few harmonics with 1/k^1.6 rolloff
                s = sum(np.sin(2 * np.pi * ff * k * t + ph * k) / k ** 1.6 for k in range(1, 7))
                x[:, ch] += s
    x = lowpass(x, bright, sr, order=2)
    env = np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, (dur - t) / release))
    x *= env[:, None] ** 1.5
    return x / (np.max(np.abs(x)) + 1e-9)


def bell(f, dur, sr, r):
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    for ratio, amp, tau in ((1.0, 1.0, 1.6), (2.0, 0.35, 0.9), (2.76, 0.25, 0.6), (5.4, 0.08, 0.25)):
        x += amp * np.sin(2 * np.pi * f * ratio * t + r.uniform(0, 6.28)) * np.exp(-t / tau)
    x *= 1 - np.exp(-t / 0.004)
    return x / (np.max(np.abs(x)) + 1e-9)


def _space(x, sr, r, mix=0.25):
    """A soft generated reverb so the bells bloom (stereo, decorrelated decays)."""
    n = int(2.2 * sr)
    t = np.arange(n) / sr
    ir = r.standard_normal((n, 2)) * np.exp(-t / 0.55)[:, None]
    ir = lowpass(ir, 3500, sr, 1)
    ir /= np.sqrt((ir ** 2).sum(0)) + 1e-9
    from scipy.signal import fftconvolve
    wet = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)
    return x + mix * wet / (np.max(np.abs(wet)) + 1e-9) * np.max(np.abs(x))


def jingle(kind: str, seed: int, sr: int = SR, *, key: str = "D", dur: float | None = None) -> np.ndarray:
    """kind: open (≈5 s, rising) | sting (≈3.5 s) | close (≈5 s, falling, resolves)."""
    r = rng(seed, "jingle", kind)
    root = hz(f"{key}3")
    d = dur or {"open": 5.0, "sting": 3.5, "close": 5.0}[kind]
    maj = [1, 5 / 4, 3 / 2, 2, 5 / 2]
    chord = [root * m for m in (maj[:4] if kind != "close" else [1, 3 / 2, 2, 5 / 2])]
    x = pad(chord, d, sr, r, bright=1100 if kind == "close" else 1500, attack=0.9, release=min(2.0, d * 0.45)) * 0.55
    mel = {"open": [3, 4, 5, 7], "sting": [5, 3], "close": [7, 5, 4, 0]}[kind]
    scale = [0, 2, 4, 5, 7, 9, 11, 12]
    bell_root = root * 4
    step = (d * 0.55) / len(mel)
    for i, deg in enumerate(mel):
        semis = scale[deg % 8] + (12 if deg >= 8 else 0)
        b = bell(bell_root * 2 ** (semis / 12), min(2.4, d - i * step), sr, r) * 0.42
        i0 = int((0.35 + i * step) * sr)
        pan = (-0.25, 0.25)[i % 2]
        m = min(len(b), len(x) - i0)
        x[i0 : i0 + m, 0] += b[:m] * (1 - pan)
        x[i0 : i0 + m, 1] += b[:m] * (1 + pan)
    x = _space(x, sr, r, 0.35)
    x = highpass(x, 60, sr)
    x = fade(x, sr, 30, 600)
    return 0.8 * x / (np.max(np.abs(x)) + 1e-9)


def bed(duration_s: float, seed: int, sr: int = SR, *, key: str = "D", bar_s: float = 8.0) -> np.ndarray:
    """A slow, quiet bed: I–vi–IV–V pads, one chord per bar_s, crossfaded, very dark."""
    r = rng(seed, "bed")
    root = hz(f"{key}3")
    prog = [(0, [1, 5 / 4, 3 / 2]), (9, [1, 6 / 5, 3 / 2]), (5, [1, 5 / 4, 3 / 2]), (7, [1, 5 / 4, 3 / 2])]
    n = int(duration_s * sr)
    out = np.zeros((n + int(bar_s * sr) * 2, 2))
    k = 0
    t = 0.0
    while t < duration_s + bar_s:
        semi, ratios = prog[k % 4]
        f = root * 2 ** (semi / 12)
        if f > root * 1.5:
            f /= 2
        seg = pad([f * q for q in ratios] + [f / 2], bar_s * 1.5, sr, r, bright=700, attack=bar_s * 0.4, release=bar_s * 0.5)
        i0 = int(t * sr)
        m = min(len(seg), len(out) - i0)
        out[i0 : i0 + m] += seg[:m]
        t += bar_s
        k += 1
    out = out[:n]
    out = highpass(out, 70, sr)
    return 0.5 * out / (np.max(np.abs(out)) + 1e-9)
