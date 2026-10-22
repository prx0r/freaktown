#!/usr/bin/env python3
"""Face-voice-react: pose bridge, envelopes, reaction policy, VAD gate."""

import struct

from backend.services.funnier.face_voice import (
    DELIVERY_TO_FACE,
    REACTIONS,
    ReactionPolicy,
    expression_envelope,
    mouth_cues_to_face_frames,
)
from backend.services.funnier.omni_reactor import (
    _transcript_to_event,
    classify_room,
    frame_rms,
)

MORPHS = ["jawOpen", "viseme_PP", "viseme_aa", "viseme_E", "viseme_O",
          "viseme_U", "viseme_DD", "viseme_FF", "viseme_kk",
          "viseme_sil", "eyeBlinkLeft", "mouthSmileLeft"]


def _doc(*poses):
    cues = [{"start_ms": i * 100, "end_ms": i * 100 + 90, "pose": p,
             "angle": -0.2} for i, p in enumerate(poses)]
    return {"schema": "pog.mouth-cues.v1", "cues": cues}


class TestPoseBridge:
    def test_all_poses_map(self):
        out = mouth_cues_to_face_frames(
            _doc("A", "B", "C", "D", "E", "F", "G", "H", "X"), MORPHS)
        assert len(out["frames"]) == 9
        assert out["unmapped_visemes"] == []
        assert out["jaw_fallbacks"] == 0
        by_pose = {f["pose"]: f["intent"] for f in out["frames"]}
        assert by_pose["A"] == "viseme_PP"
        assert by_pose["D"] == "viseme_aa"
        assert by_pose["X"] == "viseme_sil"

    def test_missing_viseme_falls_back_to_jaw(self):
        bare = ["jawOpen"]
        out = mouth_cues_to_face_frames(_doc("D", "X"), bare)
        assert len(out["frames"]) == 2
        assert all(f["morph"] == "jawOpen" for f in out["frames"])
        assert out["jaw_fallbacks"] == 2  # aa + sil both missing

    def test_no_mouth_at_all(self):
        out = mouth_cues_to_face_frames(_doc("D"), ["eyeBlinkLeft"])
        assert out["frames"] == []
        assert "viseme_aa" in out["unmapped_visemes"]

    def test_bad_input_never_raises(self):
        assert mouth_cues_to_face_frames(None, MORPHS)["frames"] == []
        assert mouth_cues_to_face_frames({}, None)["frames"] == []
        assert mouth_cues_to_face_frames(
            {"cues": ["junk", 42, None]}, MORPHS)["frames"] == []

    def test_sorted(self):
        doc = _doc("D", "A")
        doc["cues"].reverse()
        out = mouth_cues_to_face_frames(doc, MORPHS)
        assert [f["pose"] for f in out["frames"]] == ["D", "A"]


class TestEnvelope:
    def test_ramp_shape(self):
        keys = expression_envelope(1000, 2000)
        assert keys[0] == (1000, 0.0)
        assert keys[-1] == (2300, 0.0)
        assert max(w for _, w in keys) == 1.0

    def test_zero_span(self):
        assert expression_envelope(5, 5) == [(5, 0.0)]

    def test_bad_input(self):
        assert expression_envelope("x", None) == []


class TestDeliveryMap:
    def test_five_words_covered(self):
        for w in ("deadpan", "excited", "whisper", "shout", "normal"):
            assert w in DELIVERY_TO_FACE

    def test_reactions_use_existing_verbs(self):
        for key, r in REACTIONS.items():
            assert r["expression"] in (
                "smirk", "smile", "annoyed", "surprised"), key
            if r["gesture"] is not None:
                assert r["gesture"][0] in ("lean",), key
            if r["gaze"] is not None:
                assert r["gaze"].startswith("gaze."), key


class TestPolicy:
    def test_pog_burst(self):
        p = ReactionPolicy()
        assert p.decide(0, pog_pressed=True) == "room_laugh"
        assert p.decide(500, pog_pressed=True) == "room_laugh"
        assert p.decide(900, pog_pressed=True) == "pog_burst"

    def test_burst_window_prunes(self):
        p = ReactionPolicy()
        p.decide(0, pog_pressed=True)
        assert p.decide(5000, pog_pressed=True) == "room_laugh"

    def test_applause(self):
        p = ReactionPolicy()
        assert p.decide(0, crowd={"level": 0.8, "sustained": True}) \
            == "applause"

    def test_heckle(self):
        p = ReactionPolicy()
        assert p.decide(0, crowd={"level": 0.9, "speech": True}) == "heckle"

    def test_silence_after_punch_fires_once(self):
        p = ReactionPolicy()
        p.mark_punch(0)
        r = p.decide(3000, crowd={"level": 0.05}, beat_kind="punchline")
        assert r == "silence_after_punch"
        r2 = p.decide(6000, crowd={"level": 0.05}, beat_kind="punchline")
        assert r2 is None

    def test_quiet_returns_none(self):
        assert ReactionPolicy().decide(0) is None

    def test_never_raises(self):
        p = ReactionPolicy()
        assert p.decide("junk", crowd="junk") is None


class TestVad:
    def _pcm(self, amp, n=1600):
        return struct.pack("<%dh" % n, *([int(amp)] * n))

    def test_rms_scales(self):
        assert frame_rms(self._pcm(1000)) > frame_rms(self._pcm(100))
        assert frame_rms(b"") == 0.0

    def test_silence(self):
        low = [frame_rms(self._pcm(50))] * 40
        c = classify_room(low)
        assert c is not None and c["level"] == 0.0

    def test_shout(self):
        hot = [frame_rms(self._pcm(6000))] * 10
        c = classify_room(hot, speech_hint=True)
        assert c is not None and c["speech"] is True

    def test_applause_shape(self):
        mid = [frame_rms(self._pcm(1500))] * 40
        c = classify_room(mid)
        assert c is not None and c["sustained"] is True

    def test_empty(self):
        assert classify_room([]) is None
        assert classify_room(None) is None


class TestTranscript:
    def test_valid(self):
        assert _transcript_to_event('{"event": "heckle", "tag": null}') \
            == "heckle"

    def test_unknown_event(self):
        assert _transcript_to_event('{"event": "moonwalk"}') is None

    def test_garbage(self):
        assert _transcript_to_event("not json") is None
        assert _transcript_to_event("") is None
        assert _transcript_to_event(None) is None


class TestOmniHttp:
    def test_wav_roundtrip(self):
        import struct
        import wave
        from backend.services.funnier.omni_http import (
            _to_event,
            pcm_to_wav_bytes,
        )
        pcm = struct.pack("<4h", 0, 1000, -1000, 32767)
        wav = pcm_to_wav_bytes(pcm, rate=16000)
        assert wav[:4] == b"RIFF"
        with wave.open(__import__("io").BytesIO(wav), "rb") as w:
            assert w.getframerate() == 16000
            assert w.getnchannels() == 1
            assert w.readframes(4) == pcm

    def test_to_event(self):
        from backend.services.funnier.omni_http import _to_event
        assert _to_event('{"event": "heckle", "tag": null}') == "heckle"
        assert _to_event('{"event": "moonwalk"}') is None
        assert _to_event("not json") is None
        assert _to_event("") is None


class TestResolveExpression:
    def test_event_default(self):
        from backend.services.funnier.face_voice import (
            resolve_expression,
        )
        assert resolve_expression("pog_burst") == ("smile", 1.0)
        assert resolve_expression("heckle") == ("annoyed", 0.8)

    def test_omni_emotion_override(self):
        from backend.services.funnier.face_voice import (
            resolve_expression,
        )
        assert resolve_expression("applause", emotion="grin") == (
            "grin", 1.0)
        assert resolve_expression("room_laugh", emotion="afraid",
                                  intensity=0.4) == ("afraid", 0.4)

    def test_unknown_everything_deadpans(self):
        from backend.services.funnier.face_voice import (
            resolve_expression,
        )
        assert resolve_expression("moonwalk", emotion="moonwalk") == (
            "deadpan", 1.0)
        assert resolve_expression() == ("deadpan", 1.0)

    def test_reaction_dict_parsing(self):
        from backend.services.funnier.omni_reactor import (
            _transcript_to_reaction,
        )
        r = _transcript_to_reaction(
            '{"event": "heckle", "emotion": "angry", "intensity": 0.8,'
            ' "tag": "tough room"}')
        assert r == {"event": "heckle", "emotion": "angry",
                     "intensity": 0.8, "tag": "tough room"}
        r = _transcript_to_reaction("garbage")
        assert r == {"event": None, "emotion": None, "intensity": None,
                     "tag": None}
        # legacy event-only shape still parses
        r = _transcript_to_reaction('{"event": "applause"}')
        assert r["event"] == "applause" and r["emotion"] is None


class TestStageKind:
    def test_mapping(self):
        from backend.services.funnier.face_voice import to_stage_kind
        assert to_stage_kind("room_laugh") == "laugh"
        assert to_stage_kind("pog_burst") == "laugh"
        assert to_stage_kind("applause") == "clap"
        assert to_stage_kind("heckle") == "boo"
        assert to_stage_kind("silence_after_punch") == "crickets"
        assert to_stage_kind("moonwalk") is None
        assert to_stage_kind(None) is None
