#!/usr/bin/env python3
"""Face profiles: detection, POG_FACE_V1 mapping honesty, app wiring."""

import json
import struct

import face_profiles as fp


def _glb_with_targets(names):
    raw = json.dumps({"asset": {"version": "2.0"}, "meshes": [{
        "primitives": [{"targets": [{} for _ in names]}],
        "extras": {"targetNames": list(names)}}]}).encode()
    while len(raw) % 4:
        raw += b" "
    return (struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(raw))
            + struct.pack("<II", len(raw), 0x4E4F534A) + raw)


class TestDetect:
    def test_empty_is_none(self):
        assert fp.detect_face_profile([]) == "NONE"
        assert fp.detect_face_profile(None) == "NONE"
        assert fp.detect_face_profile("garbage") == "NONE"

    def test_jaw_only(self):
        assert fp.detect_face_profile(["jawOpen"]) == "JAW"

    def test_arkit52(self):
        assert fp.detect_face_profile(sorted(fp.ARKIT_52)) == "ARKIT_52"

    def test_visemes15(self):
        assert fp.detect_face_profile(sorted(fp.OCULUS_15)) == "VISEMES15"

    def test_metaperson_shape(self):
        names = sorted(fp.ARKIT_52) + sorted(fp.OCULUS_15)
        assert fp.detect_face_profile(names) == "METAPERSON_MOBILE51"

    def test_unknown_is_custom_not_mislabeled(self):
        p = fp.detect_face_profile(["wiggle0", "wobble1"])
        assert p == "CUSTOM"


class TestPogFace:
    def test_never_invents_morphs(self):
        names = ["jawOpen", "eyeBlinkLeft", "mouthSmileLeft"]
        m = fp.to_pog_face(names)
        assert set(m["intents"].values()) <= set(names)
        assert "jaw_open" in m["intents"] and "blink_left" in m["intents"]
        assert "frown_right" in m["unmapped"]

    def test_basic_body_maps_jaw(self):
        m = fp.to_pog_face(["jawOpen"])
        assert m["profile"] == "JAW"
        assert m["intents"]["jaw_open"] == "jawOpen"

    def test_expression_unknown_is_empty(self):
        assert fp.map_expression("schmorp", 1.0) == []
        happy = dict(fp.map_expression("happy", 0.5))
        assert happy == {"smile_left": 0.5, "smile_right": 0.5,
                         "cheek_squint_left": 0.3,
                         "cheek_squint_right": 0.3}

    def test_full_face_recipes(self):
        sad = dict(fp.map_expression("sad", 1.0))
        assert sad["brow_inner_up"] == 0.9
        assert sad["frown_left"] == 0.8
        angry = dict(fp.map_expression("angry", 1.0))
        assert angry["brow_down_left"] == 1.0
        assert angry["eye_squint_right"] == 0.5
        assert fp.map_expression("moonwalk", 1.0) == []
        morphs = dict(fp.expression_morphs("surprised", 1.0))
        assert morphs["jawOpen"] == 0.8
        assert morphs["eyeWideLeft"] == 0.9
        assert morphs["browOuterUpRight"] == 0.7
        assert fp.expression_morphs("moonwalk") == []

    def test_new_intents_resolve(self):
        names = ["browDownLeft", "browInnerUp", "eyeWideLeft",
                 "noseSneerRight", "cheekPuff"]
        m = fp.to_pog_face(names)
        assert m["intents"]["brow_down_left"] == "browDownLeft"
        assert m["intents"]["brow_inner_up"] == "browInnerUp"
        assert m["intents"]["eye_wide_left"] == "eyeWideLeft"
        assert m["intents"]["nose_sneer_right"] == "noseSneerRight"
        assert m["intents"]["cheek_puff"] == "cheekPuff"


class TestVRM:
    VRM = "static/avatars/default-v1.vrm"

    def test_vrm_sniffs_expressive(self):
        from app import _sniff_glb
        blob = open(self.VRM, "rb").read()
        caps = _sniff_glb(blob)
        assert caps["rigged"] and caps["lipsync"] is True
        assert caps["lipsync_profile"] == "viseme"
        assert len(caps["vrm_expressions"]) >= 10

    def test_vrm_profile_and_intents(self):
        from app import _sniff_glb
        blob = open(self.VRM, "rb").read()
        caps = _sniff_glb(blob)
        m = fp.to_pog_face(caps["all_morph_names"], "vrm")
        assert m["profile"] == "VRM"
        for intent in ("viseme_aa", "blink_left", "smile_left"):
            assert intent in m["intents"], intent
        # every mapped value must exist in the file
        assert set(m["intents"].values()) <= set(caps["all_morph_names"])


class TestSniffWiring:
    def test_sniff_reports_profile(self):
        from app import _sniff_glb
        caps = _sniff_glb(_glb_with_targets(
            ["jawOpen", "mouthSmileLeft", "mouthFunnel", "mouthPucker",
             "eyeBlinkLeft"]))
        assert caps["face_profile"] in ("CUSTOM", "JAW", "OCULUS")
        assert "jawOpen" in caps["all_morph_names"]

    def test_sniff_arkit_full(self):
        from app import _sniff_glb
        caps = _sniff_glb(_glb_with_targets(sorted(fp.ARKIT_52)))
        assert caps["face_profile"] == "ARKIT_52"
        assert caps["lipsync_profile"] == "viseme"


class TestBasicManifest:
    SLUG = "test-face-basic-001"

    @classmethod
    def _mk_bundle(cls):
        import os
        import shutil
        d = f"freaks/{cls.SLUG}"
        os.makedirs(d, exist_ok=True)
        json.dump({"name": "Face Test", "species": "pigeon",
                   "vibe": "proud", "voice": "en-US-GuyNeural",
                   "premise": "test pigeon"},
                  open(f"{d}/character.json", "w"))
        json.dump({"character": {"name": "Face Test"}, "duration_s": 5},
                  open(f"{d}/meta.json", "w"))
        fx = "contracts/fixtures/golden-freak-v1"
        for f in ("delivery.json", "offsets.json", "set.wav"):
            shutil.copy(f"{fx}/{f}", f"{d}/{f}")

    def test_basic_body_carries_face_profile(self):
        from app import app
        self._mk_bundle()
        c = app.test_client()
        d = c.post("/api/avatar/basic",
                   json={"slug": self.SLUG}).get_json()
        assert d["ok"] and d["status"] == "done"
        man = json.load(open(f"freaks/{self.SLUG}/avatar.json"))
        assert man["face_profile"]["profile"] == "JAW"
        assert "jaw_open" in man["face_profile"]["pog_face_v1"]

    def test_preload_exposes_face(self):
        from app import app
        self._mk_bundle()
        c = app.test_client()
        c.post("/api/avatar/basic", json={"slug": self.SLUG})
        d = c.get(f"/api/preload/{self.SLUG}").get_json()
        assert d["ok"] and d["avatarUrl"]
        assert d["face_profile"]["profile"] == "JAW"
        assert "jaw_open" in d["face_profile"]["pog_face_v1"]


class TestFacsCalibration:
    """Recipes follow the FACS canonical table (AUBlendNet ICCV'25 T2):
    Happy 6+12, Sad 1+4+15, Surprise 1+2+5+27, Fear 1+2+4+5+7+20+26,
    Anger 4+5+7+9+23, Disgust 9+5+16, Contempt 4+14+64."""

    def test_sad_has_au4(self):
        sad = dict(fp.map_expression("sad", 1.0))
        assert sad["brow_inner_up"] == 0.9   # AU1
        assert sad["brow_down_left"] == 0.5  # AU4
        assert sad["frown_left"] == 0.8      # AU15

    def test_fear_has_stretch(self):
        fear = dict(fp.map_expression("fear", 1.0)) if False else None
        afraid = dict(fp.map_expression("afraid", 1.0))
        assert afraid["mouth_stretch_left"] == 0.6   # AU20
        assert afraid["eye_wide_left"] == 1.0        # AU5
        assert afraid["brow_down_right"] == 0.4      # AU4

    def test_disgust_is_nose_not_frown(self):
        d = dict(fp.map_expression("disgust", 1.0))
        assert d["nose_sneer_left"] == 0.9            # AU9
        assert d["mouth_lower_down_left"] == 0.7      # AU16
        assert "frown_left" not in d

    def test_anger_has_press_and_nose(self):
        a = dict(fp.map_expression("angry", 1.0))
        assert a["mouth_press_left"] == 0.7           # AU23
        assert a["nose_sneer_right"] == 0.5           # AU9

    def test_contempt_exists(self):
        c = dict(fp.map_expression("contempt", 1.0))
        assert c["smile_left"] == 0.8
        assert c["brow_down_left"] == 0.5

    def test_new_intents_resolve(self):
        m = fp.to_pog_face(["mouthStretchLeft", "mouthPressRight",
                            "mouthLowerDownLeft"])
        assert m["intents"]["mouth_stretch_left"] == "mouthStretchLeft"
        assert m["intents"]["mouth_press_right"] == "mouthPressRight"
        assert m["intents"]["mouth_lower_down_left"] == \
            "mouthLowerDownLeft"
