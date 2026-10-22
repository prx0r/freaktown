"""Light procedural foley: paper shuffle, chair creak, mug clink. Seeded, synthesized, no samples."""
from __future__ import annotations

import numpy as np

from .dsp import SR, rng, bandpass, highpass, lowpass, fade


def paper(r: np.random.Generator, sr: int = SR) -> np.ndarray:
    """A page turn/shuffle: a slide (soft filtered noise) plus a cluster of crinkle grains."""
    d = r.uniform(0.7, 1.2)
    n = int(d * sr)
    x = np.zeros(n)
    slide = bandpass(r.standard_normal(n), 900, 6000, sr) * np.hanning(n) * 0.35
    x += slide
    for _ in range(int(r.integers(8, 18))):
        L = int(r.uniform(0.008, 0.035) * sr)
        i = int(r.uniform(0.05, 0.85) * n)
        if i + L >= n:
            continue
        g = highpass(r.standard_normal(L), r.uniform(1800, 3500), sr, order=1)
        g *= np.exp(-np.linspace(0, 6, L)) * r.uniform(0.4, 1.0)
        x[i : i + L] += g
    x = fade(x, sr, 20, 60)
    return x / (np.max(np.abs(x)) + 1e-9)


def creak(r: np.random.Generator, sr: int = SR) -> np.ndarray:
    """A chair creak: a stick-slip pulse train with a gliding rate through a wooden resonance."""
    d = r.uniform(0.35, 0.7)
    n = int(d * sr)
    t = np.arange(n) / sr
    rate = r.uniform(70, 140) * (1 + 0.6 * np.sin(np.pi * t / d))
    phase = np.cumsum(rate / sr)
    pulses = (np.diff(np.floor(phase), prepend=0) > 0).astype(float)
    pulses *= 1 + 0.3 * r.standard_normal(n)
    x = bandpass(pulses, 350, 1800, sr, order=2) + 0.5 * bandpass(pulses, 2200, 3200, sr, order=1)
    x *= np.sin(np.pi * t / d) ** 1.5
    x = fade(x, sr, 10, 40)
    return x / (np.max(np.abs(x)) + 1e-9)


def clink(r: np.random.Generator, sr: int = SR) -> np.ndarray:
    """A ceramic mug set down on the desk: inharmonic partials, fast decay, a soft thud under it."""
    d = 0.6
    n = int(d * sr)
    t = np.arange(n) / sr
    f0 = r.uniform(2400, 3200)
    x = np.zeros(n)
    for k, (ratio, amp, tau) in enumerate([(1.0, 1.0, 0.09), (1.58, 0.6, 0.06), (2.31, 0.35, 0.04), (3.7, 0.2, 0.025)]):
        x += amp * np.sin(2 * np.pi * f0 * ratio * t + r.uniform(0, 6.28)) * np.exp(-t / tau)
    thud = lowpass(r.standard_normal(n), 220, sr) * np.exp(-t / 0.02) * 3
    x = x + thud
    x = fade(x, sr, 1, 80)
    return x / (np.max(np.abs(x)) + 1e-9)


def plan_foley(story_starts: list[float], gaps: list[tuple[float, float]], seed: int, *,
               paper_prob: float = 0.85, creak_prob: float = 0.12, clink_max: int = 1, clink_prob: float = 0.35):
    """Decide what happens where. Paper at story transitions (inside the gap before the story),
    creaks rarely in other long gaps, at most clink_max mug clinks per episode."""
    r = rng(seed, "foley-plan")
    events = []
    for t in story_starts:
        if r.random() < paper_prob:
            prev = [a for a, b in gaps if abs(b - t) < 0.25]
            t0 = (prev[0] + r.uniform(0.05, 0.2)) if prev else t - r.uniform(1.05, 1.25)
            events.append({"kind": "paper", "t": max(0.0, t0)})
    clinks = 0
    for a, b in gaps:
        if b - a < 1.2:
            continue
        if any(abs(e["t"] - a) < 2.0 for e in events):
            continue
        u = r.random()
        if clinks < clink_max and u < clink_prob / max(1, len(gaps)) * 3:
            events.append({"kind": "clink", "t": a + 0.25})
            clinks += 1
        elif u < creak_prob:
            events.append({"kind": "creak", "t": a + r.uniform(0.15, 0.4)})
    return sorted(events, key=lambda e: e["t"])


def render_foley(n: int, events: list[dict], seed: int, sr: int = SR, *, levels_db: dict | None = None,
                 ref_peak: float = 1.0) -> np.ndarray:
    lv = {"paper": -30.0, "creak": -36.0, "clink": -33.0, **(levels_db or {})}
    gen = {"paper": paper, "creak": creak, "clink": clink}
    out = np.zeros((n, 2))
    for k, e in enumerate(events):
        r = rng(seed, "foley", k, e["kind"])
        x = gen[e["kind"]](r, sr) * ref_peak * 10 ** (lv[e["kind"]] / 20)
        pan = r.uniform(-0.3, 0.3)
        i = int(e["t"] * sr)
        m = min(len(x), n - i)
        if m <= 0 or i < 0:
            continue
        out[i : i + m, 0] += x[:m] * (1 - pan)
        out[i : i + m, 1] += x[:m] * (1 + pan)
    return out
