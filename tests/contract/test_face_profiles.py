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
        assert happy == {"smile_left": 0.5, "smile_right": 0.5}


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
