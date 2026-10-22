"""The post chain, end to end: dry VO + a timing plan -> stems + mix + master + a report.

plan (JSON, all times in seconds on the VO clock):
  {"duration_s": 245.0,
   "lines": [{"start": 5.1, "end": 12.3, "words": [{"word": "Good", "start": 5.1, "end": 5.3}, ...]}],
   "story_starts": [31.0, 74.2, ...],          # paper shuffles land in the gap before these
   "stings": [{"t": 0.0, "kind": "open", "dur": 5.0}, ...],   # jingle cues (open|sting|close)
   "music": {"bed_from": 5.0, "bed_to": 240.0}}  # optional bed span
Nothing moves in time: every stage is zero-phase or has its direct path at sample 0.
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from . import breaths, chain, foley, mic, music, room
from .dsp import SR, rng, pink, lowpass, highpass, envelope, smooth_ar, blocks_to_samples, db, undb
from .master import master, measure_array

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(os.path.dirname(HERE), "presets")


def load_preset(name_or_path: str) -> dict:
    p = name_or_path if name_or_path.endswith(".json") else os.path.join(PRESETS, f"{name_or_path}.json")
    return json.load(open(p))


def read_mono(path: str, sr: int = SR) -> np.ndarray:
    x, s = sf.read(path, dtype="float64", always_2d=True)
    x = x.mean(1)
    if s != sr:
        g = np.gcd(s, sr)
        x = resample_poly(x, sr // g, s // g)
    return x


def speech_mask(n: int, lines: list[dict], sr: int = SR, pad_s: float = 0.05) -> np.ndarray:
    m = np.zeros(n, bool)
    for ln in lines:
        a, b = int(max(0, ln["start"] - pad_s) * sr), int(min(n / sr, ln["end"] + pad_s) * sr)
        m[a:b] = True
    return m


def rms_db(x: np.ndarray, mask: np.ndarray | None = None) -> float:
    if x.ndim == 2:
        x = x.mean(1)
    if mask is not None:
        x = x[mask[: len(x)]]
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)) if len(x) else -120.0


def voice_post(vo: np.ndarray, plan: dict, P: dict, seed: int, sr: int = SR) -> tuple[np.ndarray, dict]:
    """Mono dry VO -> stereo 'in the room' VO (+ breaths). Returns (stereo, report)."""
    rep = {}
    words = [w for ln in plan["lines"] for w in ln.get("words", [])]
    ends = [w["end"] for w in words if str(w["word"]).rstrip("\"'”’)").endswith((".", "!", "?"))]
    x = vo.copy()
    if P["plosive"]["enabled"]:
        x, hits = mic.plosives(x, words, seed, sr, **{k: v for k, v in P["plosive"].items() if k != "enabled"})
        rep["plosive_events"] = hits
    if P["mic_drift"]["enabled"]:
        q = P["mic_drift"]
        a, ev = mic.drift_curve(len(x), seed, sr, corr_s=q["corr_s"], depth=q["depth"], sentence_ends=ends,
                                turn_prob=q["turn_prob"], turn_amount=q["turn_amount"])
        x = mic.apply_mic(x, a, sr, dip_db=q["dip_db"], hf_split=q["hf_split_hz"], hf_loss_db=q["hf_loss_db"],
                          prox_split=q["prox_split_hz"], prox_loss_db=q["prox_loss_db"])
        rep["mic_drift"] = {"turn_aways": [[round(t, 2), round(d, 2), round(m, 2)] for t, d, m in ev],
                            "level_dip_db_p95": round(float(np.percentile(q["dip_db"] * a, 95)), 2),
                            "level_dip_db_max": round(float(q["dip_db"] * a.max()), 2)}
    peak = np.max(np.abs(vo)) + 1e-9
    if P["breaths"]["enabled"]:
        q = P["breaths"]
        b, placed = breaths.place_breaths(len(x), plan["lines"], seed, sr, min_gap_s=q["min_gap_s"], prob=q["prob"],
                                          level_db=q["level_db"], vo_peak=peak)
        x = x + b
        rep["breaths"] = placed
    if P["chain"]["enabled"]:
        x, crep = chain.broadcast(x, sr, P["chain"].get("params"))
        rep["chain"] = crep
    if P["room"]["enabled"]:
        q = P["room"]
        ir = room.studio_ir(seed, sr, size_m=q["size_m"], rt60_s=q["rt60_s"], early_count=q["early_count"],
                            early_db=q["early_db"], tail_db=q["tail_db"], damping_hz=q["damping_hz"])
        y = room.apply_room(x, ir, wet=q.get("wet", 1.0))
    else:
        y = np.stack([x, x], 1)
    return y, rep


def build_music(n: int, plan: dict, P: dict, seed: int, sr: int = SR):
    """Jingles at their cues + a bed between them. Returns (jingles_stereo, bed_stereo)."""
    q = P["music"]
    jin = np.zeros((n, 2))
    bed = np.zeros((n, 2))
    if not q["enabled"]:
        return jin, bed
    for st in plan.get("stings", []):
        j = music.jingle(st["kind"], seed, sr, key=q["key"], dur=st.get("dur"))
        i = int(st["t"] * sr)
        m = min(len(j), n - i)
        if m > 0:
            jin[i : i + m] += j[:m] * undb(q["jingle_db"])
    span = plan.get("music") or {}
    a = span.get("bed_from", 0.0)
    b = span.get("bed_to", n / sr)
    if q["bed_db"] > -90 and b > a:
        bd = music.bed(b - a + 2, seed, sr, key=q["key"], bar_s=q["bar_s"])
        i = int(a * sr)
        m = min(len(bd), n - i)
        seg = bd[:m]
        fi, fo = int(q["bed_fade_in_s"] * sr), int(q["bed_fade_out_s"] * sr)
        env = np.ones(m)
        env[: min(fi, m)] = np.linspace(0, 1, min(fi, m))
        end_i = min(m, int((b - a) * sr))
        env[end_i:] = 0
        k = min(fo, end_i)
        env[end_i - k : end_i] *= np.linspace(1, 0, k)
        bed[i : i + m] += seg * env[:, None]
    return jin, bed


def duck_curve(vo_mono: np.ndarray, sr: int, duck_db: float, attack_ms: float, release_ms: float, thresh_db: float = -45.0):
    env, hop = envelope(vo_mono, sr, 10.0)
    on = (db(env) > thresh_db).astype(float)
    sm = smooth_ar(on, attack_ms / 10.0, release_ms / 10.0)
    return undb(-duck_db * blocks_to_samples(sm, hop, len(vo_mono)))


def run(vo_path: str, plan: dict, preset: dict | str, seed: int, out_dir: str, sr: int = SR, write_stems: bool = True) -> dict:
    P = load_preset(preset) if isinstance(preset, str) else preset
    os.makedirs(out_dir, exist_ok=True)
    vo = read_mono(vo_path, sr)
    n = max(len(vo), int(plan.get("duration_s", 0) * sr))
    vo = np.pad(vo, (0, n - len(vo)))
    report = {"seed": seed, "preset": P.get("id"), "sr": sr, "duration_s": round(n / sr, 3)}

    v, vrep = voice_post(vo, plan, P, seed, sr)
    report["voice"] = vrep
    mask = speech_mask(n, plan["lines"], sr)
    # level the post VO so its speech RMS sits at the preset's reference (headroom for the mix)
    v *= undb(P["mix"]["vo_rms_db"] - rms_db(v, mask))

    jin, bed = build_music(n, plan, P, seed, sr)
    ref = P["mix"]["vo_rms_db"]
    if np.any(bed):
        active = np.abs(bed).sum(1) > 1e-4 * np.abs(bed).max()
        bed *= undb(ref - P["mix"]["vo_over_bed_db"] + P["mix"]["duck_db"] - rms_db(bed, active))
        g = duck_curve(v.mean(1), sr, P["mix"]["duck_db"], P["mix"]["duck_attack_ms"], P["mix"]["duck_release_ms"])
        bed *= g[:, None]
    else:
        g = np.ones(n)
    if np.any(jin):
        jin *= undb(ref + P["music"]["jingle_rel_db"] - rms_db(jin, np.abs(jin).sum(1) > 1e-6))

    tone = np.zeros((n, 2))
    if P["room_tone"]["enabled"]:
        r = rng(seed, "roomtone")
        t = np.stack([pink(n, r), pink(n, r)], 1)
        t = lowpass(highpass(t, 40, sr), P["room_tone"]["lowpass_hz"], sr)
        hum = np.sin(2 * np.pi * P["room_tone"]["hum_hz"] * np.arange(n) / sr) * undb(P["room_tone"]["hum_rel_db"])
        t = t / (np.sqrt((t ** 2).mean()) + 1e-12) + hum[:, None]
        tone = t * undb(ref + P["room_tone"]["level_rel_db"])

    fol = np.zeros((n, 2))
    fol_events = []
    if P["foley"]["enabled"]:
        q = P["foley"]
        lines = plan["lines"]
        gaps = [(lines[i]["end"], lines[i + 1]["start"]) for i in range(len(lines) - 1)]
        fol_events = foley.plan_foley(plan.get("story_starts", []), gaps, seed, paper_prob=q["paper_prob"],
                                      creak_prob=q["creak_prob"], clink_max=q["clink_max"], clink_prob=q["clink_prob"])
        vo_peak = np.percentile(np.abs(v[mask]), 99.5) if mask.any() else 0.1
        fol = foley.render_foley(n, fol_events, seed, sr, levels_db=q["levels_db"], ref_peak=vo_peak)
    report["foley"] = fol_events

    mix = v + bed + jin + tone + fol
    # metrics on the pre-master mix (master is a static gain + limiter, so the ratios hold)
    speech = mask & (np.abs(bed).sum(1) > 0)
    rest = (~speech_mask(n, plan["lines"], sr, pad_s=0.15)) & (np.abs(bed).sum(1) > 0)
    gdb = db(g)
    report["mix"] = {
        "vo_over_bed_db": round(rms_db(v, speech) - rms_db(bed, speech), 2) if speech.any() else None,
        "duck_depth_db": round(float(np.percentile(gdb[rest], 95) - np.median(gdb[speech])), 2) if speech.any() and rest.any() else None,
        "duck_target_db": P["mix"]["duck_db"],
        "room_tone_rel_db": P["room_tone"]["level_rel_db"] if P["room_tone"]["enabled"] else None,
    }
    mastered, hist = master(mix, sr, P["master"]["target_lufs"], P["master"]["ceiling_dbtp"])
    report["master"] = hist[-1] if hist else None
    sf.write(os.path.join(out_dir, "master.wav"), mastered, sr, subtype="PCM_24")
    gain = float(np.max(np.abs(mastered)) / (np.max(np.abs(mix)) + 1e-12))
    if write_stems:
        for name, s in (("vo_post", v), ("bed", bed), ("jingles", jin), ("roomtone", tone), ("foley", fol)):
            sf.write(os.path.join(out_dir, f"stem_{name}.wav"), s.astype(np.float32), sr, subtype="FLOAT")
    report["master_gain_approx"] = round(gain, 4)
    report["sha256_master"] = hashlib.sha256(open(os.path.join(out_dir, "master.wav"), "rb").read()).hexdigest()
    json.dump(report, open(os.path.join(out_dir, "post_report.json"), "w"), indent=1)
    return report


def dry_master(vo_path: str, out_path: str, sr: int = SR, target_lufs: float = -14.0, ceiling: float = -1.5) -> dict:
    """The A side of an A/B: the same VO with no post at all, only loudness-matched."""
    vo = read_mono(vo_path, sr)
    y, hist = master(np.stack([vo, vo], 1), sr, target_lufs, ceiling)
    sf.write(out_path, y, sr, subtype="PCM_24")
    return hist[-1] if hist else {}
