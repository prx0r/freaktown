"""News skins are pure data: every skin JSON is complete, points at a real decor preset, and paints its cards."""
import json, pathlib, sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sets/blender"))
SKINS = sorted((ROOT / "sets/blender/news_skins").glob("*.json"))
PRESETS = {p.stem.split("-", 1)[-1] for p in (ROOT / "sets/blender/newsroom_presets").glob("*.json")}
NEED_BRAND = ["title", "tagline", "anchor_name", "desk_text", "card_style", "palette", "fonts", "signoff"]
NEED_PAL = ["paper", "paper2", "ink", "muted", "accent", "accent2", "lower_bg", "lower_ink", "desk_bg", "desk_ink"]


def test_at_least_the_showcase_skins():
    names = {s.stem for s in SKINS}
    assert {"goodnight", "galactic"} <= names and len(names) >= 3


@pytest.mark.parametrize("p", SKINS, ids=[s.stem for s in SKINS])
def test_skin_is_complete(p):
    s = json.loads(p.read_text())
    assert s["id"] == p.stem
    assert s["base"] in PRESETS
    for k in NEED_BRAND:
        assert k in s["brand"], k
    for k in NEED_PAL:
        assert s["brand"]["palette"][k].startswith("#"), k
    assert s["music"]["style"] in ("bells", "pulse", "stabs")
    for k, v in s["brand"]["fonts"].items():
        assert (ROOT / "sets/blender/newsroom_fonts" / v).exists() or (p.parent / v).exists(), v


@pytest.mark.parametrize("p", SKINS, ids=[s.stem for s in SKINS])
def test_skin_paints_its_cards(p, tmp_path):
    pytest.importorskip("PIL")
    import newsroom_gfx as G
    out = G.write_cards(G.load_skin(p.stem), tmp_path, sample=True)
    assert {"title", "ambient", "signoff", "story0", "brand"} <= set(out)
    ov = G.Overlay(G.load_skin(p.stem), {"intro_ms": 6000, "outro_ms": 5000, "duration_ms": 30000, "date": "1 May",
                                         "lowers": [{"t_ms": 8000, "dur_ms": 4000, "title": "A", "sub": "B"}]}, 640, 360)
    for t in (500, 3000, 9000, 27000):
        assert ov.frame(t).size == (640, 360)


def test_a_new_skin_needs_no_code(tmp_path, monkeypatch):
    """Drop in a JSON with an unknown card style: the generic painter draws it."""
    pytest.importorskip("PIL")
    import newsroom_gfx as G
    s = json.loads((ROOT / "sets/blender/news_skins/goodnight.json").read_text())
    s["id"], s["brand"]["card_style"] = "morning", "brand-new-style"
    out = G.write_cards(s, tmp_path, sample=True)
    assert (tmp_path / out["story0"]).exists()
