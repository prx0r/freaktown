"""The master newsroom studio, dressed by a SKIN, with any anchor seated: stills of every camera, emotion close-ups.

    blender -b --factory-startup --python sets/blender/newsroom_studio.py -- --skill <video-to-blender>/skills/procedural-blender-nodes \
        --skin goodnight --cards out/cards/goodnight --anchor static/avatars/default-v1.vrm [--strict] \
        [--stills out/stills --views kit --width 1280 --samples 64] [--emotions out/emo] [--haze volume] [--out x.blend]

The master (newsroom_build.py: one Geometry Nodes graph + the News LED Panel / Brushed Metal / Lens groups) is
neutral; a skin (news_skins/<skin>.json, a "studio filter") switches everything a show owns: the decor preset it
starts from and its overrides (palette, trim, backdrop, add-in props), the light mood, the compositor grade, the
wall/desk graphics, title cards, lower thirds and the music variant. Skins are pure data: drop in a JSON (+ assets)
and `--skin <name>` works with no code edits. The anchor swaps independently (`--anchor`): any VRM/GLB that passes
checkFace (newsroom_anchor.py); the camera kit re-solves from its measured eye and mouth height.

--views kit        every camera in the kit (newsroom_cameras.shots), named <skin>__<anchor>__<CAM>.png
--emotions DIR     the anchor's expressive range on CAM_CLOSE / CAM_XCU, driven ONLY through the shared expressive map
                   (face_express.py <-> packages/stage-runtime/src/face/expressive-map.json): no whole-face presets
"""
import argparse, json, math, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import newsroom_build as NB  # noqa: E402  (puts the video-to-blender skill on sys.path)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import face_express as FX  # noqa: E402
import newsroom_anchor as NA  # noqa: E402
import newsroom_cameras as CK  # noqa: E402

SKINS = HERE / "news_skins"
EMOTIONS = [  # name, expressive state, head (yaw, pitch_down, tilt), camera
    ("neutral-read", {"visemes": {"ee": 0.5}, "speaking": True}, (0.0, 0.0, 0.0), "CAM_CLOSE"),
    ("talk-aa", {"visemes": {"aa": 1.0}, "speaking": True, "browUp": 0.2}, (0.0, 0.0, 0.0), "CAM_CLOSE"),
    ("talk-oh", {"visemes": {"oh": 0.9}, "speaking": True}, (0.04, 0.0, 0.0), "CAM_CLOSE"),
    ("warm", {"emotions": {"happy": 0.55}}, (0.0, -0.02, 0.03), "CAM_CLOSE"),
    ("happy", {"emotions": {"happy": 1.0}}, (0.0, -0.03, 0.04), "CAM_CLOSE"),
    ("smirk", {"smirk": 0.9, "squint": 0.3}, (0.06, 0.0, 0.08), "CAM_CLOSE"),
    ("brow-flash", {"browUp": 1.0, "visemes": {"aa": 0.4}, "speaking": True}, (0.0, -0.03, 0.0), "CAM_XCU"),
    ("concerned", {"emotions": {"sad": 0.7}, "browSad": 0.85}, (0.0, 0.06, -0.04), "CAM_CLOSE"),
    ("serious", {"browDown": 0.8, "squint": 0.15}, (0.0, 0.03, 0.0), "CAM_XCU"),
    ("surprised", {"emotions": {"surprised": 1.0}, "open": 0.4}, (0.0, -0.05, 0.0), "CAM_CLOSE"),
    ("eye-dart", {"lookX": 0.85, "lookY": 0.1}, (-0.06, 0.0, 0.0), "CAM_XCU"),
    ("wink", {"blinkL": 1.0, "smirk": 0.7}, (0.0, 0.0, 0.07), "CAM_CLOSE"),
]


def load_skin(name):
    p = pathlib.Path(name)
    if not p.exists():
        p = SKINS / f"{name}.json"
    if not p.exists():
        raise SystemExit(f"no skin {name!r}: available {sorted(x.stem for x in SKINS.glob('*.json'))}")
    return json.loads(p.read_text())


def card_list(cards_dir):
    """Wall card images in mix-chain order: title, ambient, signoff, story0..N."""
    d = pathlib.Path(cards_dir).resolve()
    meta = json.loads((d / "cards.json").read_text())
    names = ["title", "ambient", "signoff"] + sorted([k for k in meta if k.startswith("story")], key=lambda k: int(k[5:]))
    return names, [str(d / pathlib.Path(meta[n]).name) for n in names], str(d / "brand.png")


def setup(skin_name, cards_dir, anchor_path, strict=True, haze="mist", coanchor=None):
    skin = load_skin(skin_name)
    pname, inputs, look = NB.load_preset(skin["base"])
    inputs.update({k: (tuple(v) if isinstance(v, list) else v) for k, v in skin.get("studio", {}).items()})
    look = dict(look, **skin.get("look", {}))
    names, cards, brand = card_list(cards_dir)
    sc = NB.S.reset()
    sc.name = "Newsroom"
    mats = NB.materials(None, brand, wall_cards=cards, wall_px=tuple(look.get("wall_px", (480, 240))))
    group = NB.build(mats)
    ob, mod = NB.S.holder("Newsroom", None, group, sc=sc)
    NB.inspect.set_modifier_inputs(mod, inputs)
    if coanchor:
        NB.inspect.set_modifier_inputs(mod, {"Second Seat": True})
    sc.frame_set(1)
    st = NB.inspect.evaluated_stats(ob, sc)
    lint = NB.inspect.check_groups("News ") + NB.inspect.check_groups("NK ")
    print(f"STUDIO skin {skin['id']} (decor {pname}): verts {st['verts']} faces {st['faces']} warnings "
          f"{[w.message for w in mod.node_warnings]} LINT {len(lint)}")
    for p in lint:
        print("  LINT", p)
    desk_h = NB.value(mod, "Desk Height")
    an = NA.seat_anchor(sc, anchor_path, "anchor1", desk_h, strict)
    NB.inspect.set_modifier_inputs(mod, {"Seat Height": an["seat_h"]})
    co = NA.seat_anchor(sc, coanchor, "anchor2", desk_h, strict) if coanchor else None
    NB.lights(sc, mod, look, an["eye"])
    cams, spec, studio = NB.cameras(sc, mod, an["eye"], an["mouth"], "anchor1", coanchor=bool(co),
                                       head_top=an["head_top"])
    sm = bpy.data.materials["news_wall_screen"]
    mixes = [n for n in sm.node_tree.nodes if n.bl_idname == "ShaderNodeMix"]
    mixes.sort(key=lambda n: int(n.label.split()[-1]) if n.label.startswith("card") else 0)
    for n in sm.node_tree.nodes:
        if n.bl_idname == "ShaderNodeGroup" and n.node_tree and n.node_tree.name == "News LED Panel":
            n.inputs["Brightness"].default_value = look.get("wall_brightness", 1.2)
    NB.post(sc, look)
    if haze == "volume":
        NB.volume_haze(sc, mod, look.get("volume_density", 0.01), look.get("haze_color", "#FFFFFF"))
    return {"sc": sc, "ob": ob, "mod": mod, "look": look, "skin": skin, "anchor": an, "coanchor": co, "cams": cams,
            "spec": spec, "studio": studio, "card_names": names, "wall_mix": [m.inputs["Factor"] for m in mixes]}


def show_card(ctx, name, frame=None):
    """Put card `name` on the wall: mix k selects image k+1 of title, ambient, signoff, story0.. (k+1 == idx on)."""
    idx = ctx["card_names"].index(name)
    for k, f in enumerate(ctx["wall_mix"]):
        f.default_value = 1.0 if (k + 1 == idx) else 0.0
        if frame is not None:
            f.keyframe_insert("default_value", frame=frame)


class Head:
    """Head/neck/chest posed from their seated rest each frame: yaw about world Z, pitch about X, tilt about Y."""

    def __init__(self, arm):
        self.arm = arm
        self.pbs = {k: NA.bone(arm, k) for k in ("chest", "neck", "head")} if arm else {}
        bpy.context.view_layer.update()
        self.base = {k: p.matrix.copy() for k, p in self.pbs.items() if p is not None}
        for p in self.pbs.values():
            if p is not None:
                p.rotation_mode = "QUATERNION"

    def pose(self, yaw, pitch_down, tilt, breath=0.0, frame=None):
        # pose matrices are absolute (armature space): the head carries the whole turn, the neck its share
        share = {"chest": (0.0, breath, 0.0), "neck": (yaw * 0.35, pitch_down * 0.35, tilt * 0.3), "head": (yaw, pitch_down, tilt)}
        for k in ("chest", "neck", "head"):
            p = self.pbs.get(k)
            if p is None:
                continue
            y, pd, tl = share[k]
            bpy.context.view_layer.update()
            mw = self.arm.matrix_world
            p.matrix = self.base[k]
            bpy.context.view_layer.update()
            h = mw @ p.head
            R = Matrix.Rotation(y, 4, Vector((0, 0, 1))) @ Matrix.Rotation(pd, 4, Vector((1, 0, 0))) @ Matrix.Rotation(tl, 4, Vector((0, 1, 0)))
            p.matrix = mw.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ mw @ self.base[k]
            if frame is not None:
                p.keyframe_insert("rotation_quaternion", frame=frame)


def program_camera(sc):
    cd = bpy.data.cameras.new("cam_program")
    cd.sensor_fit, cd.sensor_height = "VERTICAL", CK.SENSOR_H
    cd.clip_start, cd.clip_end = 0.05, 200.0
    cd.dof.use_dof = True
    prog = bpy.data.objects.new("cam_program", cd)
    sc.collection.objects.link(prog)
    sc.camera = prog
    return prog


def set_pose(prog, pose, frame=None):
    prog.location = pose["pos"]
    prog.rotation_euler = (Vector(pose["tgt"]) - Vector(pose["pos"])).to_track_quat("-Z", "Y").to_euler()
    prog.data.lens = pose["lens"]
    prog.data.dof.focus_distance = (Vector(pose["focus"]) - Vector(pose["pos"])).length
    prog.data.dof.aperture_fstop = pose["fstop"]
    if frame is not None:
        prog.keyframe_insert("location", frame=frame)
        prog.keyframe_insert("rotation_euler", frame=frame)
        prog.data.keyframe_insert("lens", frame=frame)
        prog.data.dof.keyframe_insert("focus_distance", frame=frame)
        prog.data.dof.keyframe_insert("aperture_fstop", frame=frame)


def face_cam(ctx, pose):
    """Head yaw/pitch that turns the anchor toward a camera (the anchor addresses the lens on every cut)."""
    e = Vector(ctx["anchor"]["eye_xyz"])
    d = Vector(pose["pos"]) - e
    yaw = max(-0.6, min(0.6, math.atan2(d.x, -d.y)))
    pitch = max(-0.35, min(0.35, math.atan2(d.z, math.hypot(d.x, d.y))))
    return yaw * 0.85, -pitch * 0.7


def stills(ctx, out, views, width, samples, tag, head_to_cam=True):
    sc = ctx["sc"]
    out = pathlib.Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    NB.render_setup(sc, width, round(width * 9 / 16 / 2) * 2, samples)
    prog = program_camera(sc)
    head = Head(ctx["anchor"]["arm"])
    names = list(ctx["spec"]) if views in ("kit", "all") else views.split(",")
    rows = []
    for v in names:
        pose = ctx["spec"][v]
        set_pose(prog, pose)
        mode = CK.wall_mode(pose, ctx["studio"])
        story = next((n for n in ctx["card_names"] if n.startswith("story")), "title")
        show_card(ctx, story if mode == "headline" else "ambient")
        y, p = face_cam(ctx, pose if v not in ("CAM_SCREEN", "CAM_WALL", "CAM_CRANE_A", "CAM_WIDE", "CAM_DESK34") else ctx["spec"]["CAM_MEDIUM"]) \
            if head_to_cam else (0.0, 0.0)
        head.pose(y, p, 0.0)
        ch = FX.channels_from_state({"emotions": {"happy": 0.35}})
        FX.apply_channels(ctx["anchor"]["faces"], ctx["anchor"]["face"], ch, ctx["anchor"]["arm"], eye_base=ctx["anchor"]["eye_base"])
        f = out / f"{tag}__{v}.png"
        sc.render.filepath = str(f)
        bpy.ops.render.render(write_still=True, scene=sc.name)
        rows.append({"view": v, "file": f.name, "wall": mode, "lens": round(pose["lens"], 1),
                     "pos": [round(x, 3) for x in pose["pos"]], "tgt": [round(x, 3) for x in pose["tgt"]]})
        print("RENDERED", f, flush=True)
    (out / f"{tag}__views.json").write_text(json.dumps({"anchor": {k: ctx["anchor"][k] for k in ("eye", "mouth", "height", "seat_h", "measured_by", "path")},
                                                        "check": ctx["anchor"]["check"], "views": rows}, indent=1))


def emotions(ctx, out, width, samples, tag, only=""):
    sc = ctx["sc"]
    out = pathlib.Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    NB.render_setup(sc, width, round(width * 9 / 16 / 2) * 2, samples)
    prog = program_camera(sc)
    head = Head(ctx["anchor"]["arm"])
    show_card(ctx, "ambient")
    rep = []
    for name, state, (yaw, pd, tilt), cam in EMOTIONS:
        if only and name not in only.split(","):
            continue
        pose = ctx["spec"][cam]
        set_pose(prog, pose)
        y0, p0 = face_cam(ctx, pose)
        head.pose(y0 + yaw, p0 + pd, tilt)
        ch = FX.channels_from_state(state)
        w = FX.apply_channels(ctx["anchor"]["faces"], ctx["anchor"]["face"], ch, ctx["anchor"]["arm"], eye_base=ctx["anchor"]["eye_base"])
        f = out / f"{tag}__emo_{name}.png"
        sc.render.filepath = str(f)
        bpy.ops.render.render(write_still=True, scene=sc.name)
        rep.append({"still": name, "camera": cam, "channels": ch, "shapes": w})
        print("EMOTION", name, json.dumps(w), flush=True)
    (out / f"{tag}__emotions.json").write_text(json.dumps({"check": ctx["anchor"]["check"], "stills": rep}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="")
    ap.add_argument("--skin", default="goodnight")
    ap.add_argument("--cards", required=True, help="card directory from newsroom_gfx.py cards")
    ap.add_argument("--anchor", default=str(HERE.parent.parent / "static/avatars/default-v1.vrm"))
    ap.add_argument("--coanchor", default="")
    ap.add_argument("--strict", action="store_true", help="refuse an anchor that fails checkFace")
    ap.add_argument("--haze", default="mist", choices=["mist", "volume"])
    ap.add_argument("--stills", default="")
    ap.add_argument("--views", default="kit")
    ap.add_argument("--emotions", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args(NB._ARGV)
    try:
        ctx = setup(a.skin, a.cards, a.anchor, a.strict, a.haze, a.coanchor or None)
    except NA.AnchorRefused as e:
        print(str(e), flush=True)
        sys.exit(3)
    if bpy.context.window:
        bpy.context.window.scene = ctx["sc"]
    tag = a.tag or f"{ctx['skin']['id']}__{pathlib.Path(a.anchor).stem}"
    if a.out:
        bpy.ops.wm.save_as_mainfile(filepath=str(pathlib.Path(a.out).resolve()), compress=True)
    if a.stills:
        stills(ctx, a.stills, a.views, a.width, a.samples, tag)
    if a.emotions:
        emotions(ctx, a.emotions, a.width, a.samples, tag, a.only)


if __name__ == "__main__":
    main()
