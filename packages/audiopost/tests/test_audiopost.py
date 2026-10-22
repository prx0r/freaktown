"""audiopost tests: deterministic per seed, no time shift, loudness/true-peak targets, ducking, presets load.
Run: python -m pytest packages/audiopost/tests  (or python packages/audiopost/tests/test_audiopost.py)"""
import json
import os
import sys
import tempfile

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from audiopost import process, room, mic  # noqa: E402
from audiopost.master import measure  # noqa: E402

SR = 48000


def fake_voice(seconds=14.0, seed=0):
    """Syllable-rate modulated harmonic buzz with pauses: enough like speech for the chain."""
    r = np.random.default_rng(seed)
    t = np.arange(int(seconds * SR)) / SR
    f0 = 120 + 15 * np.sin(2 * np.pi * 0.3 * t)
    ph = np.cumsum(2 * np.pi * f0 / SR)
    x = sum(np.sin(k * ph) / k for k in range(1, 12))
    syl = (np.sin(2 * np.pi * 4.2 * t) > 0).astype(float)
    x = x * syl * 0.15 + 0.01 * r.standard_normal(len(t)) * syl
    lines = [(1.0, 5.5), (6.6, 10.4), (11.6, 13.6)]
    m = np.zeros_like(t)
    for a, b in lines:
        m[int(a * SR):int(b * SR)] = 1
    return x * m, lines


def plan_for(lines, dur):
    return {"duration_s": dur, "lines": [{"start": a, "end": b, "words": [{"word": "word.", "start": b - 0.4, "end": b}]} for a, b in lines],
            "story_starts": [lines[1][0]], "stings": [{"t": 0.0, "kind": "open", "dur": 1.0}], "music": {"bed_from": 0.5, "bed_to": dur - 0.2}}


def run(seed, d):
    x, lines = fake_voice()
    vo = os.path.join(d, "vo.wav")
    sf.write(vo, x, SR)
    rep = process.run(vo, plan_for(lines, len(x) / SR), "goodnight-studio", seed, os.path.join(d, f"o{seed}"))
    return rep, os.path.join(d, f"o{seed}", "master.wav"), vo


def test_deterministic_and_seeded():
    with tempfile.TemporaryDirectory() as d:
        r1, m1, _ = run(5, d)
        a = open(m1, "rb").read()
        r1b, m1b, _ = run(5, d)
        assert open(m1b, "rb").read() == a, "same seed must give identical bytes"
        r2, m2, _ = run(6, d)
        assert open(m2, "rb").read() != a, "a different seed must change the take"


def test_master_targets_and_mix():
    with tempfile.TemporaryDirectory() as d:
        rep, m, _ = run(3, d)
        L = measure(m)
        assert abs(L["lufs_i"] + 14.0) <= 0.5, L
        assert L["true_peak_dbtp"] <= -1.0, L
        assert rep["mix"]["duck_depth_db"] >= 6.0, rep["mix"]
        assert sf.info(m).channels == 2


def test_room_has_no_delay():
    ir = room.studio_ir(1)
    assert ir.shape[1] == 2 and abs(ir[0, 0] - 1.0) < 1e-9
    x = np.zeros(SR)
    x[1000] = 1.0
    y = room.apply_room(x, ir)
    assert int(np.argmax(np.abs(y[:, 0]))) == 1000


def test_mic_drift_bounded():
    a, ev = mic.drift_curve(SR * 20, 9, sentence_ends=[2.0, 5.0, 9.0, 14.0], turn_prob=1.0)
    assert 0 <= a.min() and a.max() <= 1.0 and len(ev) == 4
    x = np.random.default_rng(0).standard_normal(SR * 20) * 0.1
    y = mic.apply_mic(x, a, dip_db=3.0)
    assert np.sqrt(np.mean(y ** 2)) <= np.sqrt(np.mean(x ** 2)) * 1.001


def test_presets_load():
    pd = os.path.join(os.path.dirname(HERE), "presets")
    for f in os.listdir(pd):
        p = process.load_preset(os.path.join(pd, f))
        for k in ("room", "mic_drift", "breaths", "chain", "foley", "music", "mix", "master"):
            assert k in p, (f, k)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
