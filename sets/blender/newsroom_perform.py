"""Bake a Goodnight / newsroom performance timeline into Blender keyframes and render it in the Blender newsroom.

    blender -b --factory-startup --python sets/blender/newsroom_perform.py -- \
        --skill <video-to-blender>/skills/procedural-blender-nodes \
        --clip sets/blender/perform/goodnight-2026-10-22 \
        [--preset goodnight] [--anchor static/avatars/default-v1.vrm] [--fps 25] \
        [--frames out/frames --chunk 0/4 --width 1280 --samples 16] [--keys out/keys.json] [--out out/perform.blend]

A clip directory holds what the web stage used for that stretch of the show:

    timeline.json   the compiled newsroom timeline (events in t_ms), already cut to the clip window
                    (clip.json says where it starts in the episode)
    cards.json      wall cards active in the window (painted by sets/blender/newsroom_cards.mjs with the web stage's
                    own paintWallCard) + card_<k>.png, and brand.png for the desk band
    vo.m4a          the programme audio for the window (muxed by CI after the frames are encoded)

What gets keyed, per frame, with the same maths as the web stage (packages/stage-runtime/src/sets):

    mouth      dialogue.line words -> wordsMouth (one open/close per vowel group inside each measured word span),
               attack instant / release 18/s like SetStage.renderFrame, the vowel picks the viseme
               (aa ih ou ee oh); shapes found through the face:rig alias table (PR #10 meshBinding: jawOpen, ARKit,
               VRoid Fcl_MTH_*, Oculus viseme_*), else a jaw/head bone fallback
    blinks     eyeBlinkLeft/Right (or Fcl_EYE_Close_L/R): seeded 1.8-5.0 s cadence, 150 ms sine (Performer)
    affect     face.expression emotion x intensity -> the happy/relaxed/sad/... channel, eased in and out
    head       neck 0.4 / head 0.6 of a small speech nod + slow sway, turned toward the camera (speakers address it)
    camera     set.camera cues -> the set's camera marks (wide / anchor close / wall 3/4 / medium), move_ms eased with
               smootherstep (the look leads the dolly), then the slow creep toward the target
    wall       overlay.headline -> which card is on news_wall_screen (constant keys on a mix-shader chain)
"""
import argparse, json, math, pathlib, random, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import newsroom_build as NB  # noqa: E402  (also puts the video-to-blender skill on sys.path)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

_ARGV = NB._ARGV

# ---- face channel aliases (a Python mirror of packages/stage-runtime/src/face/meshBinding.ts) ------------------------
def norm(name):
    s = name.strip()
    cut = max(s.rfind("."), s.rfind("|"), s.rfind(":"))
    if 0 <= cut < len(s) - 1:
        s = s[cut + 1:]
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _n(*names):
    return [norm(x) for x in names]


ALIASES = {
    "open": _n("jawOpen", "mouthOpen", "jaw_open", "Mouth_Open", "JawDown", "mouth_wide", "A_Open", "CC_Base_JawOpen", "MTH_OPEN"),
    "aa": _n("viseme_aa", "v_aa", "aa", "A", "mouth_a", "Fcl_MTH_A", "MTH_A", "Viseme_AA"),
    "ih": _n("viseme_I", "viseme_ih", "v_ih", "ih", "I", "mouth_i", "Fcl_MTH_I", "MTH_I", "Viseme_IH"),
    "ou": _n("viseme_U", "viseme_ou", "v_ou", "ou", "U", "mouth_u", "Fcl_MTH_U", "MTH_U", "Viseme_OU"),
    "ee": _n("viseme_E", "viseme_ee", "v_e", "v_ee", "ee", "E", "mouth_e", "Fcl_MTH_E", "MTH_E", "Viseme_EE"),
    "oh": _n("viseme_O", "viseme_oh", "v_oh", "oh", "O", "mouth_o", "Fcl_MTH_O", "MTH_O", "Viseme_OH"),
    "blinkLeft": _n("eyeBlinkLeft", "eyeBlink_L", "Eye_Blink_L", "blinkLeft", "blink_L", "Fcl_EYE_Close_L", "EyeBlink_L", "eye_close_l"),
    "blinkRight": _n("eyeBlinkRight", "eyeBlink_R", "Eye_Blink_R", "blinkRight", "blink_R", "Fcl_EYE_Close_R", "EyeBlink_R", "eye_close_r"),
    "blink": _n("blink", "eyesClosed", "Eyes_Closed", "eyeClose", "Fcl_EYE_Close"),
    "happy": _n("mouthSmileLeft", "mouthSmileRight", "happy", "smile", "Mouth_Smile", "Fcl_ALL_Joy", "joy"),
    "relaxed": _n("relaxed", "fun", "Fcl_ALL_Fun"),
    "sad": _n("mouthFrownLeft", "mouthFrownRight", "sad", "sorrow", "Fcl_ALL_Sorrow"),
    "angry": _n("browDownLeft", "browDownRight", "angry", "Fcl_ALL_Angry"),
    "surprised": _n("browInnerUp", "eyeWideLeft", "eyeWideRight", "surprised", "Fcl_ALL_Surprised"),
}
VISEMES = ("aa", "ih", "ou", "ee", "oh")
VOWEL_VIS = {"a": "aa", "e": "ee", "i": "ih", "o": "oh", "u": "ou", "y": "ih"}
# timeline emotion words -> face channel (emotionToFaceAction, packages/stage-runtime/src/face/vocab.ts, coarse)
EMOTION = {"warm": ("happy", 0.45), "happy": ("happy", 1.0), "joy": ("happy", 1.0), "amused": ("happy", 0.8),
           "calm": ("relaxed", 0.6), "relaxed": ("relaxed", 1.0), "gentle": ("relaxed", 0.7), "sad": ("sad", 1.0),
           "sombre": ("sad", 0.6), "concerned": ("sad", 0.5), "angry": ("angry", 1.0), "surprised": ("surprised", 1.0),
           "excited": ("surprised", 0.5)}


def bind(face_meshes):
    """channel -> [(mesh, shape key name)] through the aliases (first alias hit per mesh)."""
    out = {}
    for ob in face_meshes:
        keys = ob.data.shape_keys.key_blocks
        by = {}
        for kb in keys:
            by.setdefault(norm(kb.name), []).append(kb.name)
        for ch, al in ALIASES.items():
            for a in al:
                if a in by:
                    out.setdefault(ch, []).extend((ob, k) for k in by[a])
                    break
    return out


# ---- mouth (wordsMouth + SetStage smoothing) ------------------------------------------------------------------------------
def vowels(word):
    import re
    v = re.findall(r"[aeiouy]+", word.lower())
    return v or ["a"]


def words_mouth(words, t):
    """packages/stage-runtime/src/sets/textMouth.ts wordsMouth: (open, viseme) at t ms into the line."""
    if not words or t < words[0]["start_ms"] or t >= words[-1]["end_ms"]:
        return 0.0, None
    lo = 0
    for i, w in enumerate(words):
        if w["start_ms"] <= t:
            lo = i
    w = words[lo]
    if t >= w["end_ms"]:
        return 0.0, None
    vs = vowels(w["word"])
    local = (t - w["start_ms"]) / max(1, w["end_ms"] - w["start_ms"]) * len(vs)
    syl = min(len(vs) - 1, int(local))
    phase = local - math.floor(local)
    return math.sin(math.pi * min(1.0, phase)) * 0.85, VOWEL_VIS.get(vs[syl][0], "aa")


def text_mouth(text, dur, t):
    words = text.split()
    if not words or t < 0 or t >= dur:
        return 0.0, None
    groups = [max(1, len(vowels(w)) if any(c in "aeiouy" for c in w.lower()) else 1) for w in words]
    total = sum(groups)
    pos = t / (dur * 0.92) * total
    acc = 0
    for i, w in enumerate(words):
        if pos < acc + groups[i]:
            local = pos - acc
            syl = int(local)
            vs = vowels(w)
            v = vs[min(syl, len(vs) - 1)][0]
            return math.sin(math.pi * (local - syl)) * (0.8 if i == len(words) - 1 else 1.0) * 0.85, VOWEL_VIS.get(v, "aa")
        acc += groups[i]
    return 0.0, None


# ---- camera (SetStage.currentPose with the newsroom's marks) -------------------------------------------------------------
def smootherstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def lead(u, k=1.6):
    """The look leads the dolly: the target finishes its move at 1/k of the move (matches SetStage)."""
    return smootherstep(min(1.0, u * k))


CUE_MARK = {"wide": "wide", "anchor1-single": "close", "close:anchor1": "close", "wall-ots": "wall",
            "two-shot": "medium", "screen": "wall", "anchor1-medium": "medium"}


def mark_pose(cam):
    """(position, target, fov_deg) of a camera mark: target 1 m along its view axis."""
    m = cam.matrix_world
    pos = m.translation.copy()
    fwd = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
    return pos, pos + fwd * (cam.data.dof.focus_distance or 3.0), math.degrees(cam.data.angle_y)


# ---- the bake ---------------------------------------------------------------------------------------------------------
def load_clip(d):
    d = pathlib.Path(d)
    tl = json.loads((d / "timeline.json").read_text())
    clip = json.loads((d / "clip.json").read_text()) if (d / "clip.json").exists() else {"from_ms": 0}
    cards = json.loads((d / "cards.json").read_text()) if (d / "cards.json").exists() else []
    return d, tl, clip, cards


def wall_card_material(mat, d, cards, fps):
    """news_wall_screen in the render: a chain of Mix Shaders over one emission per card, factors keyed constant."""
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    shaders = []
    for c in cards:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = bpy.data.images.load(str(d / c["file"]))
        tx.extension = "EXTEND"
        nt.links.new(uv.outputs["UV"], tx.inputs["Vector"])
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = 1.15
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
        shaders.append(em)
    if not shaders:
        return
    cur = shaders[0].outputs[0]
    for k, c in enumerate(cards[1:], start=1):
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(cur, mix.inputs[1])
        nt.links.new(shaders[k].outputs[0], mix.inputs[2])
        f = mix.inputs["Fac"]
        on = 1 + round(c["t_ms"] / 1000 * fps)
        f.default_value = 0.0
        f.keyframe_insert("default_value", frame=1)
        f.default_value = 1.0
        f.keyframe_insert("default_value", frame=on)
        cur = mix.outputs[0]
    nt.links.new(cur, out.inputs["Surface"])
    if nt.animation_data and nt.animation_data.action:
        for fc in _fcurves(nt.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def _fcurves(action):
    """F-curves of an action (Blender 5 layered actions keep them in channelbags)."""
    if hasattr(action, "fcurves") and action.fcurves is not None:
        try:
            return list(action.fcurves)
        except TypeError:
            pass
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out.extend(bag.fcurves)
    return out


def bake(sc, tl, clip, cams, arm, binding, fps, seed=7):
    """Compute every channel per frame from the timeline and insert keyframes. Returns the per-frame record."""
    from_ms = 0.0
    dur = float(clip.get("duration_ms", tl.get("duration_ms", 10000)))
    n = int(round(dur / 1000 * fps))
    ev = sorted(tl["events"], key=lambda e: e["t_ms"])
    lines = [e for e in ev if e["type"] == "dialogue.line"]
    exprs = [e for e in ev if e["type"] == "face.expression"]
    cuts = [e for e in ev if e["type"] == "set.camera"]
    marks = {k: mark_pose(c) for k, c in cams.items()}

    # program camera: keyed every frame
    cd = bpy.data.cameras.new("cam_program")
    cd.sensor_fit = "VERTICAL"
    prog = bpy.data.objects.new("cam_program", cd)
    sc.collection.objects.link(prog)
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = cams["close"].data.dof.aperture_fstop
    head_pt = Vector((NB.SEATS["anchor1"][0], NB.SEATS["anchor1"][1], NB.EYE_Z))

    # blink schedule (seeded, like the Performer's idle blinks)
    rng = random.Random(seed)
    blinks, t = [], rng.uniform(0.6, 2.0) * 1000
    while t < dur:
        blinks.append(t)
        t += 1800 + rng.random() * 3200          # Performer: next blink 1.8-5.0 s after the last

    # base pose of the head bones (seated pose already applied), so each frame starts from it
    neck = NB._pb(arm, "J_Bip_C_Neck", "neck", "Neck") if arm else None
    head = NB._pb(arm, "J_Bip_C_Head", "head", "Head") if arm else None
    chest = NB._pb(arm, "J_Bip_C_UpperChest", "J_Bip_C_Chest", "chest") if arm else None
    base = {pb.name: pb.matrix.copy() for pb in (neck, head, chest) if pb is not None}
    for pb in (neck, head, chest):
        if pb is not None:
            pb.rotation_mode = "QUATERNION"

    def rotate_from_base(pb, axis_angles):
        if pb is None:
            return
        bpy.context.view_layer.update()
        mw = arm.matrix_world
        h = mw @ pb.head
        R = Matrix.Identity(4)
        for ax, ang in axis_angles:
            R = Matrix.Rotation(ang, 4, Vector(ax)) @ R
        pb.matrix = mw.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ mw @ base[pb.name]

    shot = None          # current cue state
    mouth, last_vis = 0.0, "aa"
    yaw = pitch = 0.0
    rec = []
    for f in range(n):
        t = from_ms + f * 1000.0 / fps
        frame = f + 1
        dt = 1.0 / fps
        # -- camera
        for c in cuts:
            if shot is not None and c is shot["ev"]:
                continue
            if c["t_ms"] <= t and (shot is None or c["t_ms"] >= shot["ev"]["t_ms"]):
                p = c["payload"]
                mk = CUE_MARK.get(p["cue"], "wide")
                prev = shot["pose"] if shot else None
                shot = {"ev": c, "mark": mk, "from": prev, "move": float(p.get("move_ms", 0) or 0),
                        "creep": float(p.get("creep", 0) or 0), "creep_ms": float(p.get("creep_ms", 12000) or 12000),
                        "pose": None}
        pos, tgt, fov = marks[shot["mark"]] if shot else marks["wide"]
        pos, tgt = pos.copy(), tgt.copy()
        t0 = shot["ev"]["t_ms"] if shot else 0.0
        if shot and shot["creep"] > 0:
            u = max(0.0, min(1.0, (t - t0 - shot["move"]) / max(1000.0, shot["creep_ms"])))
            k = min(0.3, shot["creep"]) * (0.5 - 0.5 * math.cos(math.pi * u))
            pos = pos + (tgt - pos) * k
        if shot and shot["move"] > 0 and shot["from"] is not None:
            u = (t - t0) / shot["move"]
            e, el = smootherstep(u), lead(u)
            fp, ft, ff = shot["from"]
            pos = fp.lerp(pos, e)
            tgt = ft.lerp(tgt, el)
            fov = ff + (fov - ff) * e
        if shot is not None and (shot["move"] <= 0 or t - t0 >= shot["move"]) and shot["from"] is not None:
            pass
        cur_pose = (pos.copy(), tgt.copy(), fov)
        if shot is not None and (shot["pose"] is None or True):
            shot["pose"] = cur_pose
        prog.location = pos
        prog.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler()
        cd.angle_y = math.radians(fov)
        cd.dof.focus_distance = (head_pt - pos).length
        prog.keyframe_insert("location", frame=frame)
        prog.keyframe_insert("rotation_euler", frame=frame)
        cd.keyframe_insert("lens", frame=frame)
        cd.dof.keyframe_insert("focus_distance", frame=frame)

        # -- mouth
        open_, vis = 0.0, None
        speaking = False
        for ln in lines:
            p = ln["payload"]
            lt = t - ln["t_ms"]
            if 0 <= lt < float(p.get("duration_ms", 0)):
                speaking = True
                open_, vis = words_mouth(p["words"], lt) if p.get("words") else text_mouth(p["text"], float(p["duration_ms"]), lt)
                break
        mouth = open_ if open_ > mouth else mouth + (open_ - mouth) * min(1.0, dt * 18)
        if vis:
            last_vis = vis
        # -- blink: sin over 150 ms (Performer.update); at 25 fps at least one frame lands above 0.9
        bl = 0.0
        for b in blinks:
            if b <= t < b + 150:
                bl = math.sin(math.pi * (t - b) / 150.0)
        # -- affect
        aff = {}
        for e in exprs:
            p = e["payload"]
            d = float(p.get("duration_ms", 2000))
            if e["t_ms"] <= t < e["t_ms"] + d:
                ch, k = EMOTION.get(p.get("emotion", ""), ("happy", 0.5))
                ramp = min(1.0, (t - e["t_ms"]) / 400.0, (e["t_ms"] + d - t) / 400.0)
                aff[ch] = max(aff.get(ch, 0.0), float(p.get("intensity", 0.9)) * k * ramp)
        # -- keys
        weights = {v: 0.0 for v in VISEMES}
        if "aa" in binding or "ih" in binding:
            weights[last_vis] = mouth
        weights["open"] = mouth * 0.6 if "open" in binding and not any(v in binding for v in VISEMES) else 0.0
        weights["blinkLeft"] = weights["blinkRight"] = bl
        weights["blink"] = bl if not ("blinkLeft" in binding or "blinkRight" in binding) else 0.0
        for ch in ("happy", "relaxed", "sad", "angry", "surprised"):
            # VRoid's whole-face presets also close the eyes and open the mouth: keep affect light while speaking
            weights[ch] = aff.get(ch, 0.0) * (0.45 if speaking else 0.7)
        for ch, targets in binding.items():
            w = max(0.0, min(1.0, weights.get(ch, 0.0)))
            for ob, kname in targets:
                kb = ob.data.shape_keys.key_blocks[kname]
                kb.value = w
                kb.keyframe_insert("value", frame=frame)
        # -- head: address the camera, nod with speech, slow sway, breath
        if arm is not None and head is not None:
            me = Vector((NB.SEATS["anchor1"][0], NB.SEATS["anchor1"][1], NB.EYE_Z))
            dvec = pos - me
            want_yaw = max(-0.75, min(0.75, math.atan2(dvec.x, -dvec.y))) * 0.8
            want_pitch = max(-0.45, min(0.5, math.atan2(dvec.z, math.hypot(dvec.x, dvec.y)))) * 0.6
            rate = min(1.0, dt * 7)
            yaw += (want_yaw - yaw) * rate
            pitch += (want_pitch - pitch) * rate
            ts = t / 1000.0
            nod = 0.05 * mouth + 0.012 * math.sin(ts * 1.3)
            sway = 0.025 * math.sin(ts * 0.45 + 0.7)
            # three.js head pitch +x looks down; Blender world: about +X tips the face (-Y) down too
            neck_aa = [((0, 0, 1), yaw * 0.4), ((1, 0, 0), -(pitch * 0.4) + nod * 0.4)]
            # pose matrices are absolute (armature space): the head carries the whole turn, the neck its 0.4 share
            head_aa = [((0, 0, 1), yaw), ((1, 0, 0), -pitch + nod), ((0, 1, 0), sway)]
            rotate_from_base(chest, [((1, 0, 0), 0.01 * math.sin(ts * 2 * math.pi / 4.2))])
            rotate_from_base(neck, neck_aa)
            rotate_from_base(head, head_aa)
            for pb in (chest, neck, head):
                if pb is not None:
                    pb.keyframe_insert("rotation_quaternion", frame=frame)
        rec.append({"f": frame, "t_ms": round(t), "cam": shot["mark"] if shot else "wide", "mouth": round(mouth, 3),
                    "vis": last_vis if mouth > 0.01 else None, "blink": round(bl, 2),
                    "affect": {k: round(v, 2) for k, v in aff.items()}})
    sc.camera = prog
    sc.frame_start, sc.frame_end = 1, n
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="")
    ap.add_argument("--clip", required=True, help="clip directory (timeline.json, cards.json + PNGs, clip.json)")
    ap.add_argument("--preset", default="goodnight")
    ap.add_argument("--anchor", default=str(HERE.parent.parent / "static/avatars/default-v1.vrm"))
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--frames", default="", help="render PNG frames here")
    ap.add_argument("--chunk", default="0/1", help="K/N: render the K-th of N frame ranges")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--keys", default="", help="write the per-frame channel record (JSON) here")
    ap.add_argument("--out", default="", help="save the baked .blend here")
    a = ap.parse_args(_ARGV)

    t_start = time.time()
    d, tl, clip, cards = load_clip(a.clip)
    brand = d / "brand.png"
    sc, ob, mod, look, pname = NB.setup(a.preset, None, str(brand) if brand.exists() else None)
    sc.render.fps = a.fps
    holder, arm, faces, eye = NB.import_anchor(sc, a.anchor)
    NB.EYE_Z = eye
    NB.lights(sc, mod, look, eye)
    cams = NB.cameras(sc, mod, eye, look.get("fstop", 2.8))
    NB.post(sc, look)
    wall_card_material(bpy.data.materials["news_wall_screen"], d, cards, a.fps)
    binding = bind(faces)
    print("BIND", {k: [kn for _, kn in v] for k, v in binding.items()})
    rec = bake(sc, tl, clip, cams, arm, binding, a.fps)
    t_bake = time.time() - t_start
    print(f"BAKED {len(rec)} frames at {a.fps} fps in {t_bake:.1f}s (preset {pname}, eye {eye:.3f} m)")
    if a.keys:
        pathlib.Path(a.keys).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.keys).write_text(json.dumps({"fps": a.fps, "preset": pname, "clip": clip, "bind": {k: [kn for _, kn in v] for k, v in binding.items()},
                                                    "frames": rec}, indent=0))
    if a.out:
        bpy.ops.wm.save_as_mainfile(filepath=str(pathlib.Path(a.out).resolve()), compress=True)
    if a.frames:
        fd = pathlib.Path(a.frames).resolve()
        fd.mkdir(parents=True, exist_ok=True)
        NB.render_setup(sc, a.width, round(a.width * 9 / 16 / 2) * 2, a.samples)
        sc.render.use_persistent_data = True
        k, nch = (int(x) for x in a.chunk.split("/"))
        n = len(rec)
        per = math.ceil(n / nch)
        sc.frame_start, sc.frame_end = 1 + k * per, min(n, (k + 1) * per)
        sc.render.filepath = str(fd / "f_")
        times = []
        last = [time.time()]

        def _post(scene, *_):
            now = time.time()
            times.append(now - last[0])
            print(f"FRAMETIME {scene.frame_current} {now - last[0]:.2f}s", flush=True)
            last[0] = now

        bpy.app.handlers.render_write.append(_post)
        if bpy.context.window:
            bpy.context.window.scene = sc
        t0 = time.time()
        last[0] = t0
        bpy.ops.render.render(animation=True, scene=sc.name)
        wall = time.time() - t0
        nf = sc.frame_end - sc.frame_start + 1
        stats = {"chunk": a.chunk, "frames": nf, "render_s": round(wall, 1), "bake_s": round(t_bake, 1),
                 "s_per_frame": round(wall / max(1, nf), 2), "frames_per_min": round(nf / max(1e-6, wall / 60), 2),
                 "first_frame_s": round(times[0], 1) if times else None,
                 "steady_s_per_frame": round(sum(times[1:]) / max(1, len(times) - 1), 2) if len(times) > 1 else None,
                 "width": a.width, "height": round(a.width * 9 / 16 / 2) * 2, "samples": a.samples, "fps": a.fps}
        (fd / f"stats_{k}.json").write_text(json.dumps(stats, indent=1))
        print("PERFSTATS", json.dumps(stats))


if __name__ == "__main__":
    main()
