"""Expressive face parity + channel check (sets/blender/face_express.py vs the golden the TS runtime also checks)."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sets/blender"))
import face_express as F  # noqa: E402

GOLD = json.loads((ROOT / "tests/fixtures/face-expressive-golden.json").read_text())


def close(a, b):
    assert set(a) == set(b), (sorted(a), sorted(b))
    for k in a:
        assert abs(a[k] - b[k]) < 1e-6, (k, a[k], b[k])


def test_channels_match_golden():
    for k, s in GOLD["states"].items():
        close(F.channels_from_state(s), GOLD["channels"][k])


def test_shapes_and_checks_match_golden():
    for m, d in GOLD["meshes"].items():
        b = F.bind_rig(d["names"], d["bones"])
        assert F.check_face(d["names"], d["bones"]) == GOLD["checks"][m]
        for k in GOLD["states"]:
            close(F.shapes_for(b, GOLD["channels"][k]), GOLD["shapes"][m][k])


def test_vroid_mouth_gain_opens_past_one():
    # the old bake keyed Fcl_MTH_A at <= 0.85 and the mouth barely parted; the map drives it to 1.35
    b = F.bind_rig(GOLD["meshes"]["vroid"]["names"], GOLD["meshes"]["vroid"]["bones"])
    w = F.shapes_for(b, F.channels_from_state({"visemes": {"aa": 1.0}, "speaking": True}))
    assert w["Face_Blendshape.Fcl_MTH_A"] >= 1.3
    assert max(F.shapes_for(b, {"aa": 9.0}).values()) <= F.MAX_GAIN


def test_vroid_expresses_without_whole_face_presets():
    # expressions are composed from brow/eye/mouth parts, never Fcl_ALL_* (which close the eyes and open the mouth)
    b = F.bind_rig(GOLD["meshes"]["vroid"]["names"], GOLD["meshes"]["vroid"]["bones"])
    used = {n for t in b["bound"].values() for n, _ in t}
    assert not any("Fcl_ALL_" in n for n in used)
    assert {"smileL", "smileR", "browUp", "browDown", "squint", "blinkL", "blinkR"} <= set(b["bound"])
    assert b["gaze_bones"]["left"] == "J_Adj_L_FaceEye"


def test_check_levels():
    assert GOLD["checks"]["vroid"]["level"] == "ok"
    assert GOLD["checks"]["arkit"]["level"] == "ok"
    assert GOLD["checks"]["lantern"]["level"] == "fail" and GOLD["checks"]["lantern"]["missingCore"] == ["brow"]
    assert "no visemes" in GOLD["checks"]["lantern"]["warnings"]
    assert GOLD["checks"]["bare"]["missingCore"] == ["mouth", "blink", "smile", "brow"]


def test_house_avatar_file_passes():
    vrm = ROOT / "static/avatars/default-v1.vrm"
    names, nodes = F.glb_names(vrm)
    r = F.check_face(names, nodes)
    assert r["level"] == "ok", r
    assert r["generated"] == ["Fcl_MTH_Fun_L", "Fcl_MTH_Fun_R", "Fcl_MTH_Joy_L", "Fcl_MTH_Joy_R"]


def test_side_mask():
    assert F.side_mask(0.05, "L") == 1.0 and F.side_mask(-0.05, "L") == 0.0
    assert abs(F.side_mask(0.0, "R") - 0.5) < 1e-9
