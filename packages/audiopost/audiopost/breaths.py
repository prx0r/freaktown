"""Synthetic breaths placed in alignment gaps (before a line starts)."""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

from .dsp import SR, rng, bandpass, fade


def breath(r: np.random.Generator, sr: int = SR, dur_s: float | None = None) -> np.ndarray:
    """An inhale: band-limited noise through two moving formants, swell then quick stop."""
    d = dur_s or r.uniform(0.28, 0.48)
    n = int(d * sr)
    noise = r.standard_normal(n)
    a = bandpass(noise, 350, 2600, sr, order=2)
    b = bandpass(noise, 1400, 5200, sr, order=1) * 0.35
    x = a + b
    t = np.linspace(0, 1, n)
    env = (t ** 0.8) * np.exp(-((t - 0.72) ** 2) / 0.08)
    env /= env.max() + 1e-9
    x = x * env
    x = fade(x, sr, 15, 25)
    return x / (np.max(np.abs(x)) + 1e-9)


def place_breaths(n: int, lines: list[dict], seed: int, sr: int = SR, *, min_gap_s: float = 0.55,
                  prob: float = 0.8, level_db: float = -30.0, lead_s: float = 0.07, vo_peak: float = 1.0):
    """For each line start with >= min_gap_s silence before it, maybe place a breath ending lead_s before the onset."""
    r = rng(seed, "breaths")
    out = np.zeros(n)
    placed = []
    prev_end = 0.0
    for i, ln in enumerate(lines):
        s = float(ln["start"])
        gap = s - prev_end
        if gap >= min_gap_s and (i == 0 or r.random() < prob):
            b = breath(r, sr, min(gap - 0.12, r.uniform(0.28, 0.46)))
            t0 = s - lead_s - len(b) / sr
            if t0 > prev_end + 0.05:
                lvl = level_db + r.uniform(-3, 2)
                i0 = int(t0 * sr)
                m = min(len(b), n - i0)
                if m > 0 and i0 >= 0:
                    out[i0 : i0 + m] += b[:m] * vo_peak * 10 ** (lvl / 20)
                    placed.append(round(t0, 3))
        prev_end = float(ln["end"])
    return out, placed
