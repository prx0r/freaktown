"""Loudness measurement (ffmpeg EBU R128, the same meter for every gate) and true-peak limiting."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .dsp import SR, envelope, smooth_ar, blocks_to_samples


def measure(path: str) -> dict:
    """Integrated LUFS, LRA and true peak (dBTP) of any file ffmpeg can decode (wav, aac in mp4...)."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0", "-af", "ebur128=peak=true:framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True)
    s = p.stderr
    tail = s[s.rfind("Summary:"):]
    def g(pat):
        m = re.search(pat, tail)
        return float(m.group(1)) if m else None
    return {"lufs_i": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"), "true_peak_dbtp": g(r"Peak:\s+(-?[\d.]+) dBFS")}


def measure_array(x: np.ndarray, sr: int = SR) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        sf.write(f.name, x, sr, subtype="FLOAT")
        return measure(f.name)


def true_peak_limit(x: np.ndarray, sr: int = SR, ceiling_dbtp: float = -1.5, release_ms: float = 80.0) -> np.ndarray:
    """4x-oversampled peak detector, look-ahead gain (zero-phase smoothing), never raises gain."""
    ceil = 10 ** (ceiling_dbtp / 20)
    up = resample_poly(x, 4, 1, axis=0)
    pk = np.abs(up).max(axis=1) if up.ndim == 2 else np.abs(up)
    pk = pk[: len(pk) // 4 * 4].reshape(-1, 4).max(1)
    pk = np.pad(pk, (0, len(x) - len(pk)), mode="edge") if len(pk) < len(x) else pk[: len(x)]
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    hop = 48
    nb = len(need) // hop + 1
    blk = np.ones(nb)
    for i in range(nb):
        seg = need[i * hop : (i + 1) * hop]
        if len(seg):
            blk[i] = seg.min()
    # look-ahead: take the min over a short window ahead, then smooth release
    la = 3
    blk = np.array([blk[i : i + la + 1].min() for i in range(nb)])
    red = 1 - blk
    red = smooth_ar(red, 0.01, release_ms / 1.0)
    red = np.maximum(red, 1 - blk)
    g = 1 - blocks_to_samples(red, hop, len(x))
    return x * (g[:, None] if x.ndim == 2 else g)


def master(x: np.ndarray, sr: int = SR, target_lufs: float = -14.0, ceiling_dbtp: float = -1.5, iters: int = 3):
    """Gain to target, limit true peaks, re-measure, repeat (limiting lowers loudness a hair)."""
    y = x.copy()
    hist = []
    for _ in range(iters):
        m = measure_array(y, sr)
        if m["lufs_i"] is None:
            break
        y = y * 10 ** ((target_lufs - m["lufs_i"]) / 20)
        y = true_peak_limit(y, sr, ceiling_dbtp)
        m2 = measure_array(y, sr)
        hist.append(m2)
        if abs(m2["lufs_i"] - target_lufs) <= 0.3 and m2["true_peak_dbtp"] <= ceiling_dbtp + 0.2:
            break
    return y, hist
