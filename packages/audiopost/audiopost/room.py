"""Small-studio acoustics: a generated impulse response (direct + early reflections + short tail).

The IR's direct path sits at sample 0, so convolution adds colour and air but no delay:
word timings measured on the dry voice stay valid on the processed voice.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import oaconvolve as fftconvolve

from .dsp import SR, rng, lowpass, highpass


def studio_ir(seed: int, sr: int = SR, *, size_m: float = 4.0, rt60_s: float = 0.28,
              early_count: int = 9, early_db: float = -14.0, tail_db: float = -24.0,
              damping_hz: float = 5200.0, stereo_spread: float = 0.35) -> np.ndarray:
    """Return a (n, 2) IR. size_m sets the reflection window; rt60_s the tail; *_db the levels vs direct."""
    r = rng(seed, "room-ir")
    n = int(sr * max(rt60_s * 1.6, 0.12))
    ir = np.zeros((n, 2))
    ir[0, :] = 1.0
    c = 343.0
    # early reflections: desk, side walls, ceiling, glass; 2.5 ms .. size/c*2 window
    t_max = max(0.012, 2.2 * size_m / c)
    times = np.sort(r.uniform(0.0025, t_max, early_count))
    for k, t in enumerate(times):
        lvl = 10 ** ((early_db - 6.0 * np.log2(1 + t / 0.004)) / 20) * r.uniform(0.6, 1.0)
        pol = 1.0 if r.random() > 0.25 else -1.0
        pan = r.uniform(-stereo_spread, stereo_spread)
        i = int(t * sr)
        ir[i, 0] += pol * lvl * (1 - pan)
        ir[i, 1] += pol * lvl * (1 + pan)
    # diffuse tail: decorrelated noise with exponential decay, starts after the early window
    t = np.arange(n) / sr
    decay = np.exp(-6.91 * t / rt60_s)
    onset = np.clip((t - t_max * 0.6) / (t_max * 0.6 + 1e-9), 0, 1)
    tail = r.standard_normal((n, 2)) * (decay * onset)[:, None]
    tail = lowpass(tail, damping_hz, sr, order=1)
    tail = highpass(tail, 180.0, sr, order=1)
    e_tail = np.sqrt((tail ** 2).sum(0).mean()) + 1e-12
    ir[1:] += tail[1:] / e_tail * 10 ** (tail_db / 20)
    return ir


def apply_room(x: np.ndarray, ir: np.ndarray, wet: float = 1.0) -> np.ndarray:
    """Mono x -> stereo. Direct path unchanged in time; wet scales reflections + tail."""
    ir = ir.copy()
    d = ir[0].copy()
    ir[0] = 0
    out = np.empty((len(x), 2))
    for ch in range(2):
        out[:, ch] = d[ch] * x + wet * fftconvolve(x, ir[:, ch])[: len(x)]
    return out
