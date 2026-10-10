"""Audit fixes: single-clock compositor, pose map, honest scores, clean evidence."""
import io
import struct
import sys
import wave
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from tts_provider import AudioChunk, AudioCompositor
from comedy.evaluator import predict
import p0_learn
import rhubarb_cues


def _wav(ms, tone=True, sr=24000):
    n = int(sr * ms / 1000)
    frames = b"".join(struct.pack("<h", 3000 if (tone and (i // 240) % 2 == 0) else 0)
                      for i in range(n))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames)
    return buf.getvalue()


def test_spans_match_composed_waveform():
    comp = AudioCompositor()
    chunks = [AudioChunk(audio=_wav(1000), beat_id="b1", beat_type="setup",
                         pause_after_ms=500, pause_before_ms=200),
              AudioChunk(audio=_wav(800), beat_id="b2", beat_type="punchline",
                         pause_after_ms=300, pause_before_ms=0)]
    wav, spans = comp.compose_with_spans(chunks)
    with wave.open(io.BytesIO(wav)) as w:
        total = int(w.getnframes() / w.getframerate() * 1000)
    # last span end + its pause == total duration (single clock)
    last = spans[-1]
    assert last["end_ms"] + last["pause_after_ms"] == total
    # first span starts exactly after its pre-silence (trimmed speech)
    assert spans[0]["start_ms"] == 200
    assert spans[1]["start_ms"] > spans[0]["end_ms"]


def test_compose_deterministic():
    comp = AudioCompositor()
    mk = lambda: [AudioChunk(audio=_wav(500), beat_id="b1", beat_type="setup",
                             pause_after_ms=300, pause_before_ms=100)]
    w1, s1 = comp.compose_with_spans(mk())
    w2, s2 = comp.compose_with_spans(mk())
    assert w1 == w2 and s1 == s2


def test_rhubarb_pose_table_correct():
    m = rhubarb_cues.ANGLE
    assert m["A"] == 0.0 and m["X"] == 0.0  # closed lips / rest: shut
    assert m["D"] == -0.35 and m["C"] == -0.2  # wide > medium
    assert m["B"] == -0.08  # slight, not shut, not open


def test_evaluator_labels_prior_honestly():
    g = {"beats": [{"type": "setup"}, {"type": "punchline"}, {"type": "closer"}],
         "total_words": 120, "mechanism": "callback"}
    p = predict(g)
    assert p["calibration"] == "uncalibrated-structural-prior"
    assert p["structural_prior_score"] == p["predicted_laugh"]


def test_learn_excludes_rehearsal_and_splits_status():
    tl = [{"beat_id": "b1"}, {"beat_id": "b2"}]
    reacts = [{"set_id": "s", "viewer": "human-1", "kind": "POG", "beat_id": "b1",
               "playback_ms": 100, "origin": "audience"},
              {"set_id": "s", "viewer": "agent-9", "kind": "POG", "beat_id": "b1",
               "playback_ms": 100, "origin": "rehearsal"}]
    feeds = [{"set_id": "s", "viewer": "human-1", "comment": "ha"}]
    s = p0_learn.summarize("s", reacts, feeds, tl)
    assert s["presses"] == 1 and s["rehearsal_presses"] == 1
    assert s["eligible_views"] == 1 and s["pog_per_view"] == 1.0
    s2 = p0_learn.summarize("other", reacts, feeds, tl)
    assert s2["has_evidence"] is False and s2["presses"] == 0


def test_setplan_gate_refuses_draft(tmp_path):
    import json
    import types
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
    import build_set
    good = {"schema": "pog.setplan.v2", "status": "SCRIPT_APPROVED",
            "character_id": "pog.test", "approved_lines": ["a", "b", "c"],
            "voice": "en-US-AriaNeural"}
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(dict(good, status="DRAFT")))
    ns = types.SimpleNamespace(setplan=str(p), character="")
    refused = False
    try:
        build_set.load_source(ns)
    except SystemExit:
        refused = True
    assert refused
    p.write_text(json.dumps(good))
    src = build_set.load_source(ns)
    assert src["lines"] == ["a", "b", "c"] and src["character"] == "pog.test"
