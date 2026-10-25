"""Newsroom camera kit + director (sets/blender/newsroom_cameras.py): pure maths, no Blender."""
import json, math, pathlib, sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sets/blender"))
import newsroom_cameras as K  # noqa: E402
import newsroom_programme as P  # noqa: E402

SKINS = sorted((ROOT / "sets/blender/news_skins").glob("*.json"))
PRESETS = {p.stem.split("-", 1)[-1]: json.loads(p.read_text()) for p in (ROOT / "sets/blender/newsroom_presets").glob("*.json")}
PROOF = ROOT / "sets/blender/episodes/goodnight-2026-10-22-proof/programme.json"
SEAT = K.SEATS["anchor1"]
SINGLES = ["CAM_MEDIUM", "CAM_CLOSE", "CAM_PUSH_A", "CAM_PUSH_B"]


def studio(skin_path):
    skin = json.loads(skin_path.read_text())
    inputs = {k: v for k, v in PRESETS[skin["base"]].items() if not k.startswith("_")}
    inputs.update(skin.get("studio", {}))
    return K.studio_numbers(inputs)


@pytest.mark.parametrize("skin", SKINS, ids=[s.stem for s in SKINS])
@pytest.mark.parametrize("eye", [1.12, 1.23, 1.4])
def test_eyes_on_the_upper_third(skin, eye):
    kit, _ = K.shots(studio(skin), eye)
    for name in SINGLES:
        s = kit[name]
        x, y = K.project(s["pos"], s["tgt"], s["lens"], (SEAT[0], SEAT[1], eye))
        assert abs(y - 1 / 3) < 0.02, (name, y)
        assert abs(x) < 0.25, (name, x)


@pytest.mark.parametrize("skin", SKINS, ids=[s.stem for s in SKINS])
def test_wall_shots_frame_the_whole_headline_and_screen_hides_the_anchor(skin):
    st = studio(skin)
    for eye, top in ((1.23, 1.4), (1.23, 1.62)):
        kit, _ = K.shots(st, eye, head_top=top)
        for c in K.wall_corners(st):
            assert K.in_frame(kit["CAM_WALL"]["pos"], kit["CAM_WALL"]["tgt"], kit["CAM_WALL"]["lens"], c, margin=0.9)
            assert K.in_frame(kit["CAM_SCREEN"]["pos"], kit["CAM_SCREEN"]["tgt"], kit["CAM_SCREEN"]["lens"], c, margin=0.95)
        s = kit["CAM_SCREEN"]
        assert not any(K.in_frame(s["pos"], s["tgt"], s["lens"], q) for q in K.anchor_points(SEAT, eye, None, top))
        assert K.wall_mode(kit["CAM_WALL"], st) == "headline"


@pytest.mark.parametrize("skin", SKINS, ids=[s.stem for s in SKINS])
def test_cameras_stay_inside_the_room(skin):
    st = studio(skin)
    kit, _ = K.shots(st, 1.23)
    for name, s in kit.items():
        assert s["pos"][2] < st["H"] - 0.2, name
        assert abs(s["pos"][0]) < st["W"] / 2 - 0.3, name
        assert 10.0 <= s["lens"] <= 150.0, (name, s["lens"])


def test_kit_re_solves_for_a_taller_anchor():
    st = studio(SKINS[0])
    a, _ = K.shots(st, 1.2)
    b, _ = K.shots(st, 1.45)
    assert b["CAM_CLOSE"]["pos"][2] > a["CAM_CLOSE"]["pos"][2] + 0.2
    assert b["CAM_CLOSE"]["tgt"][2] > a["CAM_CLOSE"]["tgt"][2] + 0.2


def test_medium_close_xcu_cuts_obey_the_30_degree_rule():
    kit, _ = K.shots(studio(SKINS[0]), 1.23)
    for a, b in (("CAM_MEDIUM", "CAM_CLOSE"), ("CAM_CLOSE", "CAM_XCU"), ("CAM_MEDIUM", "CAM_XCU"), ("CAM_WALL", "CAM_MEDIUM")):
        assert K.legal_cut(a, b, kit, SEAT), (a, b)
    assert not K.legal_cut("CAM_MEDIUM", "CAM_PUSH_A", kit, SEAT)     # same framing: a jump cut


def test_push_in_never_shows_a_cropped_headline():
    st = studio(SKINS[0])
    kit, _ = K.shots(st, 1.23)
    modes = []
    for i in range(41):
        pose = K.ease_move(kit["CAM_PUSH_A"], kit["CAM_PUSH_B"], i / 40)
        m = K.wall_mode(pose, st)
        modes.append(m)
        if m == "headline":       # headline only when the whole wall is framed or none of it
            c = [K.in_frame(pose["pos"], pose["tgt"], pose["lens"], p) for p in K.wall_corners(st)]
            assert all(c) or not any(c)
    assert "ambient" in modes


def _programme():
    if not PROOF.exists():
        pytest.skip("proof episode not built")
    return json.loads(PROOF.read_text())


def test_director_grammar_on_the_proof_episode():
    prog = _programme()
    kit, _ = K.shots(studio(SKINS[0]), 1.23)
    cuts = K.direct(prog, kit, SEAT)
    assert cuts[0]["shot"] == "CAM_CRANE_A" and cuts[0]["move"][1] == "CAM_WIDE"           # intro crane
    tees = [ln for ln in prog["lines"] if ln["kind"] == "tee"]
    for ln in tees:                                                                       # wall shot on each tee
        assert any(c["shot"] == "CAM_WALL" and abs(c["t_ms"] - ln["start_ms"]) < 900 for c in cuts), ln["id"]
    for ln in prog["lines"]:
        if ln["kind"] == "body":                                                          # story starts medium
            assert any(c["shot"] == "CAM_MEDIUM" and abs(c["t_ms"] - ln["start_ms"]) < 900 for c in cuts), ln["id"]
    assert any(c["why"].startswith("emphasis") for c in cuts)                             # punch-in on a number
    assert any(c["move"] and c["move"][1] == "CAM_WIDE" and c["why"].startswith("the last word") for c in cuts)
    assert cuts[-1]["move"] and cuts[-1]["move"][1] == "CAM_CRANE_A"                      # outro crane


def test_director_rules_hold():
    prog = _programme()
    kit, _ = K.shots(studio(SKINS[0]), 1.23)
    cuts = K.direct(prog, kit, SEAT)
    words = [w for ln in prog["lines"] for w in ln["words"]]
    for a, b in zip(cuts, cuts[1:]):
        hold = b["t_ms"] - a["t_ms"]
        assert hold >= K.MIN_HOLD_MS or b["why"].startswith(("the last word", "outro")), (a, b)
        if a.get("move"):
            assert b["t_ms"] >= a["t_ms"] + a["move"][2] or b["why"].startswith(("the last word", "outro"))
        on_air = a["move"][1] if a.get("move") else a["shot"]
        first = b["move"][0] if b.get("move") else b["shot"]
        if K._alias(first) != K._alias(on_air):
            assert K.legal_cut(K._alias(on_air), K._alias(first), kit, SEAT), (a, b)
        for w in words:                                                                   # never mid-word
            assert not (w["start_ms"] < b["t_ms"] < w["end_ms"] - 1), (b, w)


def test_reads_and_layout_from_a_tagged_text_script(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("# Test News\n[open] Hello there.\n[open] Here we go.\n## Big story | Somewhere\n[tee] First: Big story. "
                 "From Somewhere.\n[body] It happened on 3 May.\n[close] Goodnight.\n")
    s = P.load_script(p)
    r = P.reads(s)
    assert [x["kind"] for x in r] == ["open", "tee", "body", "close"]
    assert r[0]["text"] == "Hello there. Here we go."
    assert s["stories"][0] == {"title": "Big story", "source": "Somewhere"}
    words = {x["id"]: [{"word": w, "start_ms": 300 * i, "end_ms": 300 * i + 250} for i, w in enumerate(x["text"].split())] for x in r}
    prog = P.layout(r, {x["id"]: 2000 for x in r}, words, s, {"brand": {"title": "Test News"}})
    assert prog["lines"][0]["start_ms"] == 6000
    assert any(c["card"] == "story0" for c in prog["cards"])
    assert prog["stings"][0]["kind"] == "open"


def test_tee_titles_come_from_the_engine_script_shape():
    m = P.TEE.match("Second: Earth from Space: West Antarctica. From the European Space Agency.")
    assert m.group(1) == "Earth from Space: West Antarctica" and m.group(2) == "the European Space Agency"
