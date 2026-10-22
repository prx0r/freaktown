"""Gentle broadcast voice chain: HPF -> EQ -> de-esser -> compressor. Zero added latency."""
from __future__ import annotations

import numpy as np

from .dsp import SR, highpass, bandpass, eq, envelope, smooth_ar, blocks_to_samples, db, undb


def deess(x: np.ndarray, sr: int = SR, *, f1: float = 5500, f2: float = 9500, threshold_db: float = -30.0,
          max_red_db: float = 6.0, ratio: float = 4.0) -> tuple[np.ndarray, float]:
    """Split-band de-esser: only the sibilant band is turned down, only when it is hot."""
    band = bandpass(x, f1, f2, sr, order=2)
    env, hop = envelope(band, sr, 2.0)
    lvl = db(env)
    over = np.maximum(0.0, lvl - threshold_db)
    red = np.minimum(max_red_db, over * (1 - 1 / ratio))
    red = smooth_ar(red, 0.5, 15)
    g = undb(-blocks_to_samples(red, hop, len(x)))
    return x - band + band * g, float(red.max() if len(red) else 0)


def compress(x: np.ndarray, sr: int = SR, *, threshold_db: float = -24.0, ratio: float = 2.5,
             attack_ms: float = 12.0, release_ms: float = 160.0, knee_db: float = 6.0, makeup_db: float = 0.0):
    env, hop = envelope(x, sr, 1.0)
    lvl = db(env)
    # soft knee
    over = lvl - threshold_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    gr = smooth_ar(gr, attack_ms, release_ms)
    g = undb(makeup_db - blocks_to_samples(gr, hop, len(x)))
    return x * g, float(np.percentile(gr, 95) if len(gr) else 0)


def broadcast(x: np.ndarray, sr: int = SR, p: dict | None = None) -> tuple[np.ndarray, dict]:
    p = {"hpf_hz": 75, "mud_db": -1.5, "mud_hz": 320, "presence_db": 1.5, "presence_hz": 3200,
         "air_db": 1.0, "air_hz": 10000, "deess": {}, "comp": {}, **(p or {})}
    y = highpass(x, p["hpf_hz"], sr, order=2)
    y = eq(y, "peak", p["mud_hz"], p["mud_db"], 1.0, sr)
    y = eq(y, "peak", p["presence_hz"], p["presence_db"], 0.9, sr)
    y = eq(y, "highshelf", p["air_hz"], p["air_db"], 0.7, sr)
    y, ds = deess(y, sr, **p["deess"])
    y, gr = compress(y, sr, **p["comp"])
    return y, {"deess_max_db": round(ds, 2), "comp_gr_p95_db": round(gr, 2)}
