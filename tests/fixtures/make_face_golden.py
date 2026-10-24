"""Regenerate tests/fixtures/face-expressive-golden.json from sets/blender/face_express.py (run after editing
packages/stage-runtime/src/face/expressive-map.json; both test suites then check the TS runtime against it)."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sets/blender"))
import face_express as F  # noqa: E402

STATES = {
    "talk_aa": {"visemes": {"aa": 1.0}, "speaking": True},
    "talk_oh_half": {"visemes": {"oh": 0.5}, "speaking": True},
    "jaw_only": {"open": 0.7},
    "happy_talk": {"visemes": {"ee": 0.8}, "emotions": {"happy": 1.0}, "speaking": True},
    "smirk_left": {"smirk": 0.8, "squint": 0.3},
    "smirk_right": {"smirk": -0.6},
    "the_look": {"browDown": 0.35, "squint": 0.3, "lookX": -0.2, "lookY": 0.05},
    "surprised": {"emotions": {"surprised": 1.0}},
    "sad": {"emotions": {"sad": 0.8}},
    "angry_flash": {"emotions": {"angry": 0.9}, "browUp": 0.4},
    "blink_left": {"blinkL": 1.0, "blinkR": 0.2},
    "dart": {"lookX": 0.9, "lookY": -0.3},
    "worried": {"browSad": 0.7, "speaking": True},
}
ARKIT = ["jawOpen", "mouthFunnel", "mouthPucker", "mouthStretchLeft", "mouthStretchRight", "eyeBlinkLeft", "eyeBlinkRight",
         "mouthSmileLeft", "mouthSmileRight", "cheekSquintLeft", "cheekSquintRight", "mouthFrownLeft", "mouthFrownRight",
         "browOuterUpLeft", "browOuterUpRight", "browInnerUp", "browDownLeft", "browDownRight", "eyeSquintLeft",
         "eyeSquintRight", "eyeWideLeft", "eyeWideRight", "eyeLookOutRight", "eyeLookInLeft", "eyeLookOutLeft",
         "eyeLookInRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight"]


def main():
    vroid, _ = F.glb_names(ROOT / "static/avatars/default-v1.vrm")
    meshes = {"vroid": {"names": vroid, "bones": ["J_Adj_L_FaceEye", "J_Adj_R_FaceEye"]},
              "arkit": {"names": ARKIT, "bones": []},
              "lantern": {"names": ["jawOpen", "mouthSmileLeft", "mouthSmileRight", "eyeBlinkLeft", "eyeBlinkRight"], "bones": []},
              "bare": {"names": ["Key 1"], "bones": []}}
    out = {"about": "Golden parity for expressive-map.json, written by tests/fixtures/make_face_golden.py "
                    "(sets/blender/face_express.py); packages/stage-runtime/tests/expressive.test.ts and "
                    "tests/contract/test_face_expressive.py must reproduce it exactly.",
           "states": STATES, "meshes": meshes, "channels": {}, "shapes": {}, "checks": {}}
    for k, s in STATES.items():
        out["channels"][k] = F.channels_from_state(s)
    for m, d in meshes.items():
        b = F.bind_rig(d["names"], d["bones"])
        out["checks"][m] = F.check_face(d["names"], d["bones"])
        out["shapes"][m] = {k: F.shapes_for(b, out["channels"][k]) for k in STATES}
    (ROOT / "tests/fixtures/face-expressive-golden.json").write_text(json.dumps(out, indent=1))
    print({m: out["checks"][m]["level"] for m in meshes})


if __name__ == "__main__":
    main()
