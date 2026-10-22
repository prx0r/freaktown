"""Club camera kit + shot grammar (sets/blender/club_cameras.py), no Blender needed."""
import json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sets/blender"))
import club_cameras as CK  # noqa: E402

DEFAULTS = {"Room Width": 10.0, "Room Depth": 11.0, "Ceiling Height": 3.8, "Riser Height": 0.3, "Stage Width": 6.0,
            "Stage Depth": 3.4, "Back Wall Y": 2.3, "Theatre Rows": False, "Rake": 0.18, "Row Pitch": 0.95}
PRESETS = sorted((ROOT / "sets/blender/presets").glob("*.json"))
EYE = 1.449           # default-v1.vrm measured standing eye height


def room(p):
    d = json.loads(p.read_text())
    return {k: d.get(k, v) for k, v in DEFAULTS.items()}


def project(cam, pt):
    """NDC (x, y) of a world point in a pinhole camera looking from pos at tgt (vertical fit, 16:9)."""
    px, py, pz = cam["pos"]
    f = [cam["tgt"][i] - cam["pos"][i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in f)); f = [c / n for c in f]
    r = [f[1], -f[0], 0.0]; rn = math.hypot(r[0], r[1]); r = [r[0] / rn, r[1] / rn, 0.0]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    d = [pt[0] - px, pt[1] - py, pt[2] - pz]
    z = sum(a * b for a, b in zip(d, f))
    half_h = (CK.SENSOR_H / 2) / cam["lens"]
    y = sum(a * b for a, b in zip(d, u)) / z / half_h
    x = sum(a * b for a, b in zip(d, r)) / z / (half_h * 16 / 9)
    return x, y


def test_every_preset_gets_the_full_kit():
    names = {"CAM_WIDE", "CAM_MEDIUM", "CAM_CLOSE", "CAM_XCU", "CAM_OTS", "CAM_PUSH_A", "CAM_PUSH_B", "CAM_CROWD"}
    for p in PRESETS:
        shots, marks = CK.shots(room(p), EYE)
        assert set(shots) == names, p.name
        assert {"MARK_EYE", "MARK_MOUTH", "MARK_CROWD", "MARK_LIP"} <= set(marks)


def test_eye_line_on_the_upper_third():
    for p in PRESETS:
        shots, _ = CK.shots(room(p), EYE)
        for name in ("CAM_MEDIUM", "CAM_CLOSE", "CAM_PUSH_B"):
            x, y = project(shots[name], (0.0, 0.0, EYE))
            assert abs(y - 1 / 3) < 0.05, (p.name, name, y)          # NDC +1/3 = one third down from the top
            assert abs(x) < 0.25, (p.name, name, x)
        x, y = project(shots["CAM_XCU"], (0.0, 0.0, EYE))
        assert 0.15 < y < 0.4


def test_wide_is_inside_the_room_and_frames_the_stage():
    for p in PRESETS:
        r = room(p)
        w = CK.shots(r, EYE)[0]["CAM_WIDE"]
        back = r["Back Wall Y"] - r["Room Depth"]
        front = r["Back Wall Y"] - r["Stage Depth"]
        assert back + 0.5 < w["pos"][1] < front - 1.0, p.name
        assert w["pos"][2] < r["Ceiling Height"] - 0.3, p.name
        assert w["pos"][2] > CK._floor_z(r, w["pos"][1]) + 1.6, p.name       # above the heads at that row
        for x in (-min(r["Stage Width"], 8.5) / 2 * 0.95, min(r["Stage Width"], 8.5) / 2 * 0.95):
            nx, ny = project(w, (x, front, 0.0))
            assert abs(nx) <= 1.0 and abs(ny) <= 1.0, (p.name, nx, ny)          # stage lip corners in frame
        nx, ny = project(w, (0.0, 0.0, EYE))
        assert abs(nx) < 0.3 and abs(ny) < 0.6


def test_ots_looks_out_from_behind_the_comic():
    for p in PRESETS:
        s = CK.shots(room(p), EYE)[0]
        assert s["CAM_OTS"]["pos"][1] > 0.3 and s["CAM_OTS"]["tgt"][1] < -2
        assert s["CAM_CROWD"]["tgt"][1] < s["CAM_CROWD"]["pos"][1]


def test_close_clears_the_mic():
    # the mic head sits 0.13 m in front of the mouth and 0.07 m below it: in CAM_CLOSE it must project below the mouth
    for p in PRESETS:
        s = CK.shots(room(p), EYE)[0]
        mouth = (0.0, -0.08, EYE - 0.075)
        mic = (0.0, -0.1 - 0.13, EYE - 0.075 - 0.07 - 0.02)
        _, my = project(s["CAM_CLOSE"], mouth)
        mx, iy = project(s["CAM_CLOSE"], mic)
        assert iy < my - 0.08, (p.name, iy, my)


def test_shot_grammar_on_the_punch_clip():
    tl = json.loads((ROOT / "sets/blender/perform/club-hark-punch/timeline.json").read_text())
    cuts = CK.pick_shots(tl)
    shots = [c["shot"] for c in cuts]
    assert shots == ["CAM_CLOSE", "CAM_XCU", "CAM_OTS", "CAM_CLOSE"]
    assert all(b["t_ms"] - a["t_ms"] >= CK.MIN_SHOT_MS for a, b in zip(cuts, cuts[1:]))
    hit = tl["lines"][0]["hit_ms"]
    assert cuts[1]["t_ms"] < hit                                   # in on the punch before the hit word
    assert cuts[2]["t_ms"] >= tl["laughs"][0]["t_ms"]               # crowd reverse on the laugh


def test_shot_grammar_rules_on_a_synthetic_set():
    L = lambda i, role, t, d, hit=None: {"id": f"l{i}", "role": role, "t_ms": t, "dur_ms": d, "hit_ms": hit, "words": []}
    tl = {"lines": [L(1, "opener", 500, 3000), L(2, "setup", 4000, 3000), L(3, "setup", 7200, 3000),
                    L(4, "punch", 12000, 1800, 13000), L(5, "tag", 16500, 2500), L(6, "act-out", 20000, 1800),
                    L(7, "tag", 23000, 2500)],
          "looks": [{"t_ms": 11000, "dur_ms": 1300, "at": "camera", "line": "l4"}],
          "laughs": [{"t_ms": 14000, "dur_ms": 1900, "size": 1.0, "after": "l4"},
                     {"t_ms": 25800, "dur_ms": 1300, "size": 0.6, "after": "l7"}]}
    cuts = CK.pick_shots(tl)
    by = [(c["shot"], c["why"].split(":")[0]) for c in cuts]
    assert by[0] == ("CAM_WIDE", "open")
    assert ("CAM_PUSH_A", "build") in by and next(c for c in cuts if c["shot"] == "CAM_PUSH_A")["push"][1] == "CAM_PUSH_B"
    assert ("CAM_CLOSE", "look") in by and ("CAM_XCU", "punch") in by and ("CAM_OTS", "laugh") in by
    assert ("CAM_MEDIUM", "act-out") in by
    assert by[-1] == ("CAM_WIDE", "last laugh")
