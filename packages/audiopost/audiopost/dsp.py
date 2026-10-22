"""Small DSP toolkit: biquads, envelopes, seeded noise. numpy + scipy only."""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt, lfilter

SR = 48000


def rng(seed: int, *salt) -> np.random.Generator:
    """Deterministic generator per (seed, salt...). Same inputs, same noise, every run."""
    key = [int(seed)] + [sum(ord(c) * (i + 1) for i, c in enumerate(str(s))) for s in salt]
    return np.random.default_rng(np.random.SeedSequence(key))


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-12))


def undb(d):
    return 10 ** (np.asarray(d) / 20)


def lowpass(x, f, sr=SR, order=2, zero_phase=True):
    sos = butter(order, min(f, sr * 0.45), "low", fs=sr, output="sos")
    return sosfiltfilt(sos, x, axis=0) if zero_phase else sosfilt(sos, x, axis=0)


def highpass(x, f, sr=SR, order=2, zero_phase=True):
    sos = butter(order, f, "high", fs=sr, output="sos")
    return sosfiltfilt(sos, x, axis=0) if zero_phase else sosfilt(sos, x, axis=0)


def bandpass(x, f1, f2, sr=SR, order=2, zero_phase=True):
    sos = butter(order, [f1, min(f2, sr * 0.45)], "band", fs=sr, output="sos")
    return sosfiltfilt(sos, x, axis=0) if zero_phase else sosfilt(sos, x, axis=0)


def _biquad(kind, f0, gain_db, q, sr):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    if kind == "peak":
        b = [1 + alpha * A, -2 * c, 1 - alpha * A]
        a = [1 + alpha / A, -2 * c, 1 - alpha / A]
    elif kind == "lowshelf":
        s = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * c + s), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - s)]
        a = [(A + 1) + (A - 1) * c + s, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - s]
    elif kind == "highshelf":
        s = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * c + s), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - s)]
        a = [(A + 1) - (A - 1) * c + s, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - s]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return b, a


def eq(x, kind, f0, gain_db, q=0.707, sr=SR):
    b, a = _biquad(kind, f0, gain_db, q, sr)
    return lfilter(b, a, x, axis=0)


def envelope(x, sr=SR, win_ms=10.0):
    """RMS envelope sampled per block (block = win_ms). Returns (env, hop)."""
    hop = max(1, int(sr * win_ms / 1000))
    n = len(x) // hop
    if n == 0:
        return np.zeros(1), hop
    blk = x[: n * hop].reshape(n, hop)
    return np.sqrt((blk ** 2).mean(1) + 1e-20), hop


def smooth_ar(level, attack_blocks, release_blocks):
    """Attack/release one-pole smoothing over a block-rate control signal (python loop, block rate only)."""
    out = np.empty_like(level)
    a_at = np.exp(-1.0 / max(attack_blocks, 1e-3))
    a_re = np.exp(-1.0 / max(release_blocks, 1e-3))
    y = level[0] if len(level) else 0.0
    for i, v in enumerate(level):
        a = a_at if v > y else a_re
        y = a * y + (1 - a) * v
        out[i] = y
    return out


def blocks_to_samples(ctrl, hop, n):
    """Linear-interpolate a block-rate control curve to n samples."""
    if len(ctrl) == 0:
        return np.ones(n)
    xs = (np.arange(len(ctrl)) + 0.5) * hop
    return np.interp(np.arange(n), xs, ctrl)


def smooth_random_walk(n_blocks, r: np.random.Generator, corr_blocks: float, sigma: float = 1.0):
    """Ornstein-Uhlenbeck process (block rate): slow, bounded wandering around 0, unit-ish variance."""
    theta = 1.0 / max(corr_blocks, 1.0)
    x = np.zeros(n_blocks)
    noise = r.standard_normal(n_blocks) * sigma * np.sqrt(2 * theta)
    for i in range(1, n_blocks):
        x[i] = x[i - 1] * (1 - theta) + noise[i]
    # second smoothing pass so the curve has no corners
    k = max(3, int(corr_blocks / 4))
    win = np.hanning(2 * k + 1)
    win /= win.sum()
    return np.convolve(x, win, mode="same")


def pink(n, r: np.random.Generator):
    """Pink-ish noise via the Voss-McCartney-free FFT method (1/f power)."""
    w = r.standard_normal(n)
    W = np.fft.rfft(w)
    f = np.arange(len(W))
    f[0] = 1
    W = W / np.sqrt(f)
    y = np.fft.irfft(W, n)
    return y / (np.std(y) + 1e-12)


def fade(x, sr, fin_ms=5, fout_ms=5):
    n = len(x)
    a = min(n // 2, int(sr * fin_ms / 1000))
    b = min(n // 2, int(sr * fout_ms / 1000))
    y = x.copy()
    if a:
        y[:a] *= np.linspace(0, 1, a)[:, None] if y.ndim == 2 else np.linspace(0, 1, a)
    if b:
        y[-b:] *= np.linspace(1, 0, b)[:, None] if y.ndim == 2 else np.linspace(1, 0, b)
    return y


def add_at(dst, src, t_s, sr=SR, gain=1.0):
    """Mix src into dst at time t_s (clipped to bounds). Works for mono or stereo dst."""
    i = int(round(t_s * sr))
    if i >= len(dst) or i + len(src) <= 0:
        return dst
    s0 = max(0, -i)
    i = max(0, i)
    m = min(len(dst) - i, len(src) - s0)
    seg = src[s0 : s0 + m] * gain
    if dst.ndim == 2 and seg.ndim == 1:
        seg = seg[:, None]
    dst[i : i + m] += seg
    return dst
