#!/usr/bin/env python3
"""Per-beat laugh probability from the vendored delivery-aware model.

Reads a freaktown bundle (delivery + measured offsets + set.wav), builds
[pos, dur, pause_before, wps, energy_mean, energy_std, n_pauses, pause_total]
per beat, and scores with characters' delivery_aware_model.pkl (AUC 0.654,
leave-one-comedian-out).

Run ONLY under .venv-heat (numpy2 + sklearn 1.9.1 — the system python
cannot unpickle this model). Read-only on both repos. No network, no keys.

Usage: .venv-heat/bin/python scripts/heat_model.py <slug>
Prints JSON: {"ok": true, "model": ..., "beats": [{"id", "p"}]}.
"""
import json
import pickle
import sys
import wave
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FREAKS = BASE / "freaks"
MODEL = Path("/root/characters/audition/voicelab/delivery_aware_model.pkl")
MODEL_NAME = "delivery-aware-0.654"

import numpy as np  # noqa: E402  (venv: numpy2)


def load_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        n, sw, fr, nch = w.getnframes(), w.getsampwidth(), w.getframerate(), w.getnchannels()
        raw = w.readframes(n)
    if sw == 2:
        y = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sw == 4:
        y = np.frombuffer(raw, dtype=np.int32).astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if nch > 1:
        y = y.reshape(-1, nch).mean(axis=1)
    return y, fr


def rms_frames(y: np.ndarray, sr: int, win_ms: int = 50) -> np.ndarray:
    win = max(1, int(sr * win_ms / 1000))
    n = len(y) // win * win
    f = y[:n].reshape(-1, win)
    return np.sqrt((f ** 2).mean(axis=1))


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else ""
    bdir = FREAKS / slug
    try:
        delivery = json.loads((bdir / "delivery.json").read_text())
        offsets = json.loads((bdir / "offsets.json").read_text()).get("offsets", [])
        meta = json.loads((bdir / "meta.json").read_text())
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"bundle unreadable: {e}"}))
        return
    beats_in = delivery.get("beats", [])
    if not beats_in or not (bdir / "set.wav").exists():
        print(json.dumps({"ok": False, "error": "no beats or audio"}))
        return
    total_ms = int(float(meta.get("duration_s", 0)) * 1000) or None
    by_id = {o.get("id"): o for o in offsets}
    try:
        y, sr = load_wav(bdir / "set.wav")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"wav unreadable: {e}"}))
        return
    rms = rms_frames(y, sr)
    frame_ms = 50.0
    sig = float(np.percentile(rms, 95)) or 1.0
    thr = max(0.008, 0.15 * float(rms.mean()))

    with open(MODEL, "rb") as f:
        model = pickle.load(f)["model"]

    out = []
    prev_end = 0
    for b in beats_in:
        o = by_id.get(b.get("id"))
        if o is None:
            continue
        start, speech = int(o["start_ms"]), int(o["speech_ms"])
        dur = max(0.2, speech / 1000.0)
        pos = (start / total_ms) if total_ms else 0.0
        pause_before = max(0.0, (start - prev_end) / 1000.0)
        words = len(str(b.get("text", "")).split())
        wps = words / dur
        i0, i1 = int(start / frame_ms), int((start + speech) / frame_ms)
        seg = rms[i0:max(i0 + 1, min(i1, len(rms)))]
        energy_mean = float(seg.mean() / sig)
        energy_std = float(seg.std() / sig)
        silent = seg < thr
        runs, cur = 0, 0
        for v in silent:
            if v:
                cur += 1
            elif cur:
                if cur * frame_ms >= 150:
                    runs += 1
                cur = 0
        if cur and cur * frame_ms >= 150:
            runs += 1
        n_pauses = runs
        pause_total = round(runs * 0.25, 3)  # coarse: count x typical short pause
        x = np.array([[pos, dur, pause_before, wps,
                       energy_mean, energy_std, n_pauses, pause_total]])
        p = float(model.predict_proba(x)[0, 1])
        out.append({"id": b.get("id"), "p": round(p, 4)})
        prev_end = start + speech
    print(json.dumps({"ok": True, "model": MODEL_NAME, "beats": out}))


if __name__ == "__main__":
    main()
