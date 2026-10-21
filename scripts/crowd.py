#!/usr/bin/env python3
"""Crowd ambience bed for /perform rooms. System python OK (numpy + ffmpeg).

For each beat with predicted p_laugh >= chuckle threshold, overlays a real
CC0 laugh clip (characters' comedy-room SFX) starting ~150ms after the beat
(humans laugh AFTER the line), gain-scaled by p. Ends with an applause swell
scaled by the set's mean heat. Deterministic: round-robin clip pick, no RNG.

This is ambience, not sample-locked Foley: the room starts it with the set
at low volume. Silence where nothing is predicted. No model, no keys.
"""
import subprocess
from pathlib import Path

import numpy as np

SR = 24000
SFX = Path("/root/characters/apps/comedy-room/public/assets/sfx")
REACT_LAG_MS = 150

_clips: dict = {}


def _decode(path: Path) -> np.ndarray:
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, timeout=30)
    if p.returncode != 0 or not p.stdout:
        raise ValueError(f"ffmpeg failed on {path}")
    return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float64) / 32768.0


def clip(name: str) -> np.ndarray | None:
    if name not in _clips:
        try:
            _clips[name] = _decode(SFX / name)
        except Exception:
            _clips[name] = None
    return _clips[name]


def build_bed(beats: list, duration_ms: int,
              chuckle_p: float = 0.35) -> tuple:
    """Returns (wav_bytes_16bit_mono_24k, moments). moments lists what fired."""
    n = max(1, int(duration_ms * SR / 1000))
    bed = np.zeros(n, dtype=np.float64)
    moments = []
    li = 0
    for b in beats:
        p = float(b.get("p_laugh", 0))
        if p < chuckle_p:
            continue
        name = ["laugh_01.mp3", "laugh_02.mp3", "laugh_03.mp3"][li % 3]
        li += 1
        c = clip(name)
        if c is None:
            continue
        at = int((b["start"] + REACT_LAG_MS) * SR / 1000)
        if at >= n:
            continue
        take = min(len(c), n - at)
        bed[at:at + take] += c[:take] * (0.25 + 0.75 * min(1.0, p))
        moments.append({"t": b["start"], "p": p, "clip": name})
    mean_p = sum(float(b.get("p_laugh", 0)) for b in beats) / max(1, len(beats))
    ap = clip("clap_01.mp3")
    if ap is not None and duration_ms > 1000:
        at = max(0, n - len(ap) - int(0.5 * SR))
        take = min(len(ap), n - at)
        bed[at:at + take] += ap[:take] * (0.2 + 0.8 * min(1.0, mean_p * 2))
        moments.append({"t": duration_ms - 500, "p": round(mean_p, 3),
                        "clip": "clap_01.mp3"})
    peak = float(np.max(np.abs(bed))) if moments else 0.0
    if peak > 0:
        bed = bed / peak * 0.5
    return (bed * 32767).astype(np.int16).tobytes(), moments
