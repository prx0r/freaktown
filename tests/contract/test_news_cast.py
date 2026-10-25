"""Contract tests for the newsroom cast (sets/blender/news_cast/*.json) and the multi-character show (no Blender)."""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sets/blender"))
import face_express as FX  # noqa: E402
import news_cast as NC  # noqa: E402
import newsroom_cameras as CK  # noqa: E402
import newsroom_programme as P  # noqa: E402

EP = ROOT / "sets/blender/episodes/cast-proof"


def test_every_cast_member_loads_and_can_express():
    ids = NC.ids()
    assert {"house", "vivi", "fumiriya", "theo", "seed"} <= set(ids)
    for cid in ids:
        c, chk = NC.check(cid)
        assert pathlib.Path(c["model_path"]).exists(), cid
        assert chk["level"] != "fail", (cid, chk)
        for k in ("name", "licence", "source", "voice"):
            assert c.get(k), (cid, k)
        assert re.fullmatch(r"[0-9a-f]{32}", c["voice"]["id"]), cid
        for ch in list((c.get("face") or {}).get("gains", {})) + list((c.get("face") or {}).get("shapes", {})):
            assert ch in FX.CHANNELS, (cid, ch)


def test_cast_voices_are_distinct():
    voices = [NC.load(c)["voice"]["id"] for c in NC.ids()]
    assert len(set(voices)) == len(voices)


def test_resolve_id_path_and_plain_model():
    p, c = NC.resolve("vivi")
    assert p.endswith("static/avatars/cast/vivi.vrm") and c["id"] == "vivi"
    p2, c2 = NC.resolve("static/avatars/cast/vivi.vrm")      # a model path a cast file names gets that cast entry
    assert c2["id"] == "vivi" and p2 == p
    p3, c3 = NC.resolve("static/avatars/buddha.glb")
    assert c3["id"] == "buddha" and c3["face"] == {}


def test_vroid_beta_morph_prefix_normalises():
    assert FX.norm_name("Face.M_F00_000_00_Fcl_MTH_A") == FX.norm_name("Fcl_MTH_A") == "fclmtha"
    assert FX.norm_name("jawOpen") == "jawopen"


def test_beta_vrm_primitive_target_names_are_hoisted():
    raw = (ROOT / "static/avatars/cast/vivi.vrm").read_bytes()
    fixed = NC.hoist_target_names(raw)
    assert fixed is not raw
    import struct
    n = struct.unpack("<I", fixed[12:16])[0]
    assert struct.unpack("<I", fixed[8:12])[0] == len(fixed)
    j = json.loads(fixed[20:20 + n])
    face = next(m for m in j["meshes"] if any((p.get("extras") or {}).get("targetNames") for p in m["primitives"]))
    assert "Fcl_MTH_A" in " ".join(face["extras"]["targetNames"])
    house = (ROOT / "static/avatars/default-v1.vrm").read_bytes()
    assert NC.hoist_target_names(house) is house               # VRM 1.0 exports already carry mesh-level names


def test_vrm_versions():
    assert NC.vrm_version(ROOT / "static/avatars/default-v1.vrm") == 1
    assert NC.vrm_version(ROOT / "static/avatars/cast/vivi.vrm") == 0     # faces -Z: seat_anchor turns it 180 degrees
    assert NC.vrm_version(ROOT / "static/avatars/buddha.glb") is None


def test_face_overrides_scale_and_replace():
    names, nodes = FX.glb_names(ROOT / "static/avatars/cast/vivi.vrm")
    b = FX.bind_rig(names, nodes)
    o = FX.apply_overrides(b, {"gains": {"grin": 1.25}, "shapes": {"squint": [["Fcl_EYE_Joy", 0.5]]}}, names)
    assert o["bound"]["grin"][0][1] == round(b["bound"]["grin"][0][1] * 1.25, 6)
    assert o["bound"]["squint"] == [[next(n for n in names if n.endswith("Fcl_EYE_Joy")), 0.5]]
    assert b["bound"]["grin"] != o["bound"]["grin"]           # the binding itself is untouched


def test_new_map_emotions_drive_channels():
    ch = FX.channels_from_state({"emotions": {"serious": 1.0}})
    assert ch["browDown"] > 0.5 and "smileL" not in ch
    ch = FX.channels_from_state({"emotions": {"concerned": 1.0}})
    assert ch["browSad"] > 0.5 and ch["frown"] > 0.3


def test_intro_shows_ambient_wall_then_title():
    rds = [{"id": "a#1", "kind": "open", "story": None, "text": "Hello there."}]
    prog = P.layout(rds, {"a#1": 1500}, {"a#1": [{"word": "Hello", "start_ms": 0, "end_ms": 400}]}, {"stories": []},
                    {"brand": {}}, 6000, 3000)
    assert prog["cards"][0] == {"t_ms": 0, "card": "ambient"}
    assert any(c["card"] == "title" and c["t_ms"] >= 0.8 * 6000 for c in prog["cards"])
    prog2 = P.layout(rds, {"a#1": 1500}, {"a#1": []}, {"stories": []}, {"brand": {}}, 0, 0, lead_ms=350)
    assert prog2["lines"][0]["start_ms"] == 350


def test_intro_title_date_and_tagline_never_overlap():
    import newsroom_gfx as G
    for sk in ("goodnight", "galactic", "night-wire"):
        skin = G.load_skin(sk)
        ov = G.Overlay(skin, {"intro_ms": 4500, "outro_ms": 4000, "duration_ms": 40000, "date": "25 October 2026",
                              "lowers": []}, 1280, 720)
        ov.frame(0.7 * 4500)
        bx = list(ov.intro_boxes.values())
        for i in range(len(bx)):
            for j in range(i + 1, len(bx)):
                a, b = bx[i], bx[j]
                assert a[3] <= b[1] or b[3] <= a[1], (sk, ov.intro_boxes)      # stacked, no vertical overlap


def test_director_opens_on_the_segment_shot():
    prog = {"duration_ms": 8000, "intro_ms": 0, "outro_ms": 0, "open_shot": "CAM_DESK34",
            "lines": [{"id": "x", "kind": "body", "start_ms": 350, "end_ms": 7400,
                       "words": [{"word": w, "start_ms": 350 + i * 400, "end_ms": 350 + i * 400 + 330} for i, w in
                                 enumerate("closer to home the river is rising again crews are working through the night".split())]}]}
    skin = json.loads((ROOT / "sets/blender/news_skins/night-wire.json").read_text())
    pre = {p.stem.split("-", 1)[-1]: json.loads(p.read_text()) for p in (ROOT / "sets/blender/newsroom_presets").glob("*.json")}
    st = CK.studio_numbers(dict({k: v for k, v in pre[skin["base"]].items() if not k.startswith("_")}, **skin.get("studio", {})))
    kit, _ = CK.shots(st, 1.23)
    cuts = CK.direct(prog, kit, CK.SEATS["anchor1"])
    assert cuts[0]["shot"] == "CAM_DESK34"


def test_cast_proof_episode_is_consistent():
    meta = json.loads((EP / "cast_episode.json").read_text())
    script = json.loads((EP / "script.json").read_text())
    assert len(meta["segments"]) == len(script["segments"]) >= 4
    assert len({s["skin"] for s in meta["segments"]}) == 3
    assert len({s["cast"] for s in meta["segments"]}) == len(meta["segments"])
    assert 30.0 <= meta["duration_ms"] / 1000 <= 46.0
    assert meta["tts_model"] == "s2.1-pro-free"
    assert abs(meta["loudness"]["lufs_i"] + 14.0) <= 0.6 and meta["loudness"]["true_peak_dbfs"] <= -1.0
    f0 = 0
    for s, sc in zip(meta["segments"], script["segments"]):
        sd = EP / s["dir"]
        prog = json.loads((sd / "programme.json").read_text())
        env = json.loads((sd / "env.json").read_text())["env"]
        ep = json.loads((sd / "episode.json").read_text())
        assert s["frame0"] == f0 and len(env) == s["frames"] == ep["frames"]
        assert ep["anchor"] == sc["cast"] and ep["skin"] == sc["skin"]
        assert ep["tts"]["model"] == "s2.1-pro-free" and ep["tts"]["voice"] == NC.load(sc["cast"])["voice"]["id"]
        want = [ln["emotion"][0] for ln in sc["lines"] if ln.get("emotion")]
        assert [m["emotion"] for m in prog["moods"]] == want
        assert len(prog["gestures"]) == sum(len(ln.get("gestures", [])) for ln in sc["lines"])
        assert (sd / "cards" / "cards.json").exists()
        f0 += s["frames"]
    assert f0 == meta["frames"]
