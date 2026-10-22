"""Off-axis mic drift: the speaker's head moves while they read.

A slow seeded random walk (plus occasional bigger turn-aways at sentence ends) gives an
off-axis amount a(t) in [0, 1]. It maps to: level dips (dip_db at a=1), HF rolloff (the
>hf_split band loses up to hf_loss_db) and reduced proximity bass (<prox_split loses up to
prox_loss_db). Bands are split with zero-phase filters, so nothing shifts in time.
"""
from __future__ import annotations

import numpy as np

from .dsp import SR, rng, lowpass, highpass, smooth_random_walk, blocks_to_samples, undb


def drift_curve(n: int, seed: int, sr: int = SR, *, corr_s: float = 3.5, depth: float = 0.45,
                sentence_ends: list[float] | None = None, turn_prob: float = 0.22,
                turn_amount: float = 0.9, turn_s: tuple[float, float] = (0.6, 1.4)) -> np.ndarray:
    hop = sr // 100
    nb = n // hop + 1
    r = rng(seed, "mic-drift")
    w = smooth_random_walk(nb, r, corr_blocks=corr_s * 100)
    w = (w - w.min()) / (np.ptp(w) + 1e-9)
    a = depth * w
    events = []
    for t in sentence_ends or []:
        if r.random() < turn_prob:
            dur = r.uniform(*turn_s)
            amt = turn_amount * r.uniform(0.6, 1.0)
            events.append((t, dur, amt))
            b0 = int((t - 0.25) * 100)
            L = int(dur * 100)
            if b0 + L <= 0 or b0 >= nb:
                continue
            k = np.arange(L)
            shape = np.sin(np.pi * k / max(L - 1, 1)) ** 2   # turn away, come back
            lo, hi = max(0, b0), min(nb, b0 + L)
            a[lo:hi] = np.maximum(a[lo:hi], amt * shape[lo - b0 : hi - b0])
    a = np.clip(a, 0, 1)
    return blocks_to_samples(a, hop, n), events


def apply_mic(x: np.ndarray, a: np.ndarray, sr: int = SR, *, dip_db: float = 2.5,
              hf_split: float = 4200.0, hf_loss_db: float = 6.0,
              prox_split: float = 220.0, prox_loss_db: float = 4.0) -> np.ndarray:
    low = lowpass(x, prox_split, sr, order=2)
    high = highpass(x, hf_split, sr, order=2)
    mid = x - low - high
    g = undb(-dip_db * a)
    gl = undb(-prox_loss_db * a)
    gh = undb(-hf_loss_db * a)
    return g * (mid + low * gl + high * gh)


def plosives(x: np.ndarray, words: list[dict], seed: int, sr: int = SR, *, prob: float = 0.18,
             level_db: float = -24.0, lean_prob: float = 0.08, lean_db: float = 2.5) -> tuple[np.ndarray, list]:
    """Proximity moments: soft low 'pop' under some p/b onsets, and short lean-ins (bass up a touch)."""
    r = rng(seed, "plosive")
    y = x.copy()
    hits = []
    peak = np.max(np.abs(x)) + 1e-9
    for w in words:
        word = str(w.get("word", "")).lower().lstrip("\"'“‘(")
        t = float(w["start"])
        if word[:1] in ("p", "b") and r.random() < prob:
            L = int(0.045 * sr)
            k = np.arange(L) / sr
            f = r.uniform(55, 95)
            pop = np.sin(2 * np.pi * f * k) * np.exp(-k / 0.012)
            i = int(t * sr)
            if 0 <= i < len(y) - L:
                y[i : i + L] += pop * peak * 10 ** (level_db / 20)
                hits.append(("pop", round(t, 3)))
        elif r.random() < lean_prob / 10:
            i0, i1 = int(t * sr), int((t + r.uniform(0.8, 1.6)) * sr)
            i1 = min(i1, len(y))
            if i1 - i0 > sr // 4:
                seg = y[i0:i1]
                lo = lowpass(seg, 180, sr)
                env = np.sin(np.linspace(0, np.pi, i1 - i0))
                y[i0:i1] = seg + lo * (10 ** (lean_db / 20) - 1) * env
                hits.append(("lean", round(t, 3)))
    return y, hits
