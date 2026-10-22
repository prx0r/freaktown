"""Prove the comic can express: emotion close-ups and a short (~5 s) performance in the club, driven ONLY through the
expressive channels (face_express.py / expressive-map.json — the same numbers the three.js stage writes).

    blender -b --factory-startup --python sets/blender/club_face.py -- --skill <video-to-blender>/skills/procedural-blender-nodes \
        [--preset late-night-tv] [--comic static/avatars/default-v1.vrm] [--strict] \
        [--stills out/face --width 960 --samples 48] \
        [--perform sets/blender/perform/club-hark-punch --frames out/perf --chunk 0/5 --width 960 --samples 24] [--keys out/keys.json]

--strict exits non-zero when the mesh fails the channel check (a core group missing: it cannot express).

The performance bake (per frame, from the club-clip timeline written by club_clip.py):
    mouth    the measured word under the playhead -> its vowel group -> viseme (aa ih ou ee oh); amplitude = the VO's
             own loudness (timeline env, per frame) x a syllable shape, so the jaw follows the real audio; VRoid
             visemes reach 1.35 through the map's gain (the old bake's 0.85 barely parted the lips)
    blinks   seeded 2.2-4.5 s cadence, none during the stare, one right after the punch lands
    gaze     eye darts across the house (3 points, 60 ms saccades) during setups; locked on the lens for the look
    acting   the look before the punch: brows down 0.35, squint 0.3, eyes + head to camera; the hit word: brow flash;
             after the line: smirk (one-sided smile, generated shape) + squint + head tilt and a small nod; the laugh:
             glance across the crowd
    camera   club_cameras.pick_shots on the same timeline (close on the look, XCU on the hit, crowd reverse on the
             laugh, close for the reaction)
"""
import argparse, json, math, pathlib, random, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import club_build as CB  # noqa: E402  (puts the video-to-blender skill on sys.path)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import club_cameras as CK  # noqa: E402
import comic as C  # noqa: E402
import face_express as FX  # noqa: E402

STILLS = [  # name, expressive state, head (yaw, pitch_down, tilt) radians, camera
    ("talk-aa", {"visemes": {"aa": 1.0}, "speaking": True, "browUp": 0.2}, (0.0, 0.0, 0.0), "CAM_CLOSE"),
    ("talk-oh", {"visemes": {"oh": 0.9}, "speaking": True}, (0.05, 0.0, 0.0), "CAM_CLOSE"),
    ("happy", {"emotions": {"happy": 1.0}}, (0.0, -0.03, 0.04), "CAM_CLOSE"),
    ("smirk", {"smirk": 0.9, "squint": 0.3}, (0.08, 0.0, 0.1), "CAM_CLOSE"),
    ("the-look", {"browDown": 0.45, "squint": 0.35, "lookX": -0.35, "lookY": 0.05}, (0.12, 0.03, 0.0), "CAM_XCU"),
    ("surprised", {"emotions": {"surprised": 1.0}, "open": 0.5}, (0.0, -0.05, 0.0), "CAM_CLOSE"),
    ("sad", {"emotions": {"sad": 0.9}}, (0.0, 0.1, -0.05), "CAM_CLOSE"),
    ("angry", {"emotions": {"angry": 1.0}}, (0.0, 0.06, 0.0), "CAM_CLOSE"),
    ("eye-dart", {"lookX": 0.9, "lookY": 0.15}, (-0.08, 0.0, 0.0), "CAM_XCU"),
    ("wink", {"blinkL": 1.0, "smirk": 0.7}, (0.0, 0.0, 0.08), "CAM_CLOSE"),
]


def setup(preset, comic_path, strict=False):
    pname, inputs, look = CB.load_preset(preset)
    sc = CB.S.reset()
    sc.name = "Club"
    ob, mod = CB.S.holder("Club", None, CB.build(), sc=sc)
    CB.inspect.set_modifier_inputs(mod, inputs)
    CB.lights(sc, mod, look)
    comic = C.import_comic(sc, comic_path)
    C.bind_face(comic, strict=strict)
    CB.inspect.set_modifier_inputs(mod, {"Mouth Height": comic["mouth"] - 0.07, "Mic Gap": 0.13})
    ks = bpy.data.objects.get("Key Spot")
    if ks is not None:
        ks.data.energy *= look.get("key_on_comic", 0.32)
    C.comic_lights(sc, comic["eye"], look, (0.45, -CB.value(mod, "Spot Throw"), CB.value(mod, "Ceiling Height") - 0.45))
    cams = CB.cameras(sc, mod, comic["eye"])
    CB.post(sc, look)
    return pname, sc, mod, look, comic, cams


class Head:
    """Head bone posed from its rest-at-mic matrix each frame (yaw about world Z, pitch about X, tilt about Y)."""

    def __init__(self, arm):
        self.arm = arm
        self.pb = C.pb_of(arm, "J_Bip_C_Head", "head", "Head") if arm else None
        self.chest = C.pb_of(arm, "J_Bip_C_UpperChest", "J_Bip_C_Chest") if arm else None
        bpy.context.view_layer.update()
        self.base = {p.name: p.matrix.copy() for p in (self.pb, self.chest) if p is not None}

    def pose(self, yaw, pitch_down, tilt, breath=0.0, frame=None):
        for p, rots in ((self.chest, [((1, 0, 0), breath)]), (self.pb, [((0, 0, 1), yaw), ((1, 0, 0), pitch_down), ((0, 1, 0), tilt)])):
            if p is None:
                continue
            bpy.context.view_layer.update()
            mw = self.arm.matrix_world
            p.matrix = self.base[p.name]
            bpy.context.view_layer.update()
            h = mw @ p.head
            R = Matrix.Identity(4)
            for ax, ang in rots:
                R = Matrix.Rotation(ang, 4, Vector(ax)) @ R
            p.matrix = mw.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ mw @ self.base[p.name]
            if frame is not None:
                p.rotation_mode = "QUATERNION"
                p.keyframe_insert("rotation_quaternion", frame=frame)


def use_camera(sc, cams, name, frame=None, prog=None):
    """Copy a kit camera onto the program camera (keyed when frame is given)."""
    src = cams[name]
    prog = prog or sc.camera
    prog.location = src.location.copy()
    prog.rotation_euler = src.rotation_euler.copy()
    prog.data.lens = src.data.lens
    prog.data.dof.use_dof = True
    prog.data.dof.focus_distance = src.data.dof.focus_distance
    prog.data.dof.aperture_fstop = src.data.dof.aperture_fstop
    if frame is not None:
        prog.keyframe_insert("location", frame=frame)
        prog.keyframe_insert("rotation_euler", frame=frame)
        prog.data.keyframe_insert("lens", frame=frame)
        prog.data.dof.keyframe_insert("focus_distance", frame=frame)
        prog.data.dof.keyframe_insert("aperture_fstop", frame=frame)


def program_camera(sc):
    cd = bpy.data.cameras.new("cam_program")
    cd.sensor_fit, cd.sensor_height = "VERTICAL", CK.SENSOR_H
    cd.clip_start = 0.05
    prog = bpy.data.objects.new("cam_program", cd)
    sc.collection.objects.link(prog)
    sc.camera = prog
    return prog


def render_stills(sc, mod, comic, cams, out, width, samples, pname, only=""):
    out = pathlib.Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    CB.render_setup(sc, width, round(width * 9 / 16 / 2) * 2, samples)
    head = Head(comic["arm"])
    prog = program_camera(sc)
    report = []
    for name, state, (yaw, pd, tilt), cam in STILLS:
        if only and name not in only.split(","):
            continue
        ch = FX.channels_from_state(state)
        w = FX.apply_channels(comic["faces"], comic["face"], ch, comic["arm"], eye_base=comic["eye_base"])
        head.pose(yaw, pd, tilt)
        use_camera(sc, cams, cam, prog=prog)
        CB.inspect.set_modifier_inputs(mod, {"Show Beam": False})
        sc.render.filepath = str(out / f"face_{pname}_{name}.png")
        bpy.ops.render.render(write_still=True, scene=sc.name)
        report.append({"still": name, "camera": cam, "channels": ch, "shapes": w})
        print("FACESTILL", name, json.dumps(w))
    (out / f"face_{pname}_stills.json").write_text(json.dumps({"check": comic["check"], "stills": report}, indent=1))


VOWEL_VIS = {"a": "aa", "e": "ee", "i": "ih", "o": "oh", "u": "ou", "y": "ih"}


def vowel_groups(word):
    import re
    v = re.findall(r"[aeiouy]+", word.lower())
    return v or ["a"]


def bake_perform(sc, mod, comic, cams, tl, fps, seed=5):
    """Key every channel per frame from the club-clip timeline. Returns the per-frame record."""
    n = int(round(tl["duration_ms"] / 1000 * fps))
    env = tl.get("env") or [0.0] * n
    lines, looks, laughs = tl["lines"], tl.get("looks", []), tl.get("laughs", [])
    cuts = CK.pick_shots(tl)
    prog = program_camera(sc)
    head = Head(comic["arm"])
    rng = random.Random(seed)
    stare = [(lk["t_ms"], lk["t_ms"] + lk["dur_ms"]) for lk in looks]
    blinks, t = [], 150.0
    while t < tl["duration_ms"]:
        if not any(a <= t <= b for a, b in stare):
            blinks.append(t)
        t += rng.uniform(2200, 4500)
    for ln in lines:
        if ln["role"] in ("punch", "callback", "closer"):
            blinks.append(ln["t_ms"] + ln["dur_ms"] + 180)        # the punch lands, then a blink
    darts = [-0.55, 0.25, 0.7, -0.1]
    rec, mouth = [], 0.0
    yaw = pitch = tilt = 0.0
    for f in range(n):
        frame, t = f + 1, f * 1000.0 / fps
        # camera
        cur = cuts[0]
        for c in cuts:
            if c["t_ms"] <= t:
                cur = c
        use_camera(sc, cams, cur["shot"], frame=frame, prog=prog)
        if cur.get("push"):
            a_, b_, ms = cur["push"]
            u = CK_smoother(min(1.0, (t - cur["t_ms"]) / ms))
            A, B = cams[a_], cams[b_]
            prog.location = A.location.lerp(B.location, u)
            prog.rotation_euler = A.rotation_euler.to_quaternion().slerp(B.rotation_euler.to_quaternion(), u).to_euler()
            prog.data.lens = A.data.lens + (B.data.lens - A.data.lens) * u
            prog.keyframe_insert("location", frame=frame)
            prog.keyframe_insert("rotation_euler", frame=frame)
            prog.data.keyframe_insert("lens", frame=frame)
        # mouth
        speaking, open_, vis = False, 0.0, None
        line = None
        for ln in lines:
            if ln["t_ms"] <= t < ln["t_ms"] + ln["dur_ms"]:
                line = ln
                for w in ln["words"]:
                    if w["start_ms"] <= t < w["end_ms"]:
                        vs = vowel_groups(w["word"])
                        local = (t - w["start_ms"]) / max(1, w["end_ms"] - w["start_ms"]) * len(vs)
                        syl = min(len(vs) - 1, int(local))
                        shape = 0.35 + 0.65 * math.sin(math.pi * min(1.0, local - math.floor(local)))
                        amp = min(1.0, (env[f] if f < len(env) else 0.0) * 1.3)
                        open_, vis, speaking = amp * shape, VOWEL_VIS.get(vs[syl][0], "aa"), True
        mouth = open_ if open_ > mouth else mouth + (open_ - mouth) * min(1.0, 18.0 / fps)
        state = {"speaking": speaking or mouth > 0.05}
        if vis or mouth > 0.02:
            state["visemes"] = {vis or "aa": mouth}
        # blink: 150 ms sine
        bl = max([math.sin(math.pi * (t - b) / 150.0) for b in blinks if b <= t < b + 150] or [0.0])
        state["blinkL"] = state["blinkR"] = bl
        # gaze + acting
        in_look = next((lk for lk in looks if lk["t_ms"] <= t < lk["t_ms"] + lk["dur_ms"]), None)
        cam_pos = prog.location
        to_cam = math.atan2(cam_pos.x, -cam_pos.y)
        want_yaw, want_pitch, want_tilt = 0.0, 0.0, 0.0
        if in_look or (line and line["role"] in ("punch", "callback")):
            # eyes + head on the lens; brows down and a squint for the look itself
            state["lookX"] = max(-1.0, min(1.0, math.degrees(to_cam) * 0.6 / 12.0))
            want_yaw = to_cam * 0.7
            if in_look:
                state["browDown"], state["squint"] = 0.35, 0.3
        else:
            k = int(t // 1300)
            state["lookX"] = darts[k % len(darts)]
            state["lookY"] = -0.15
            want_yaw = darts[k % len(darts)] * 0.18
        if line and line.get("hit_ms") and line["hit_ms"] - 80 <= t < line["hit_ms"] + 380:
            state["browUp"] = 0.45 * math.sin(math.pi * (t - line["hit_ms"] + 80) / 460)
        done = [ln for ln in lines if ln["role"] in ("punch", "callback", "closer") and t >= ln["t_ms"] + ln["dur_ms"]]
        if done:
            since = t - (done[-1]["t_ms"] + done[-1]["dur_ms"])
            r = min(1.0, since / 450.0)
            state["smirk"], state["squint"] = 0.8 * r, max(state.get("squint", 0), 0.3 * r)
            want_tilt = 0.09 * r
            want_pitch = 0.04 * math.sin(min(math.pi, since / 600.0 * math.pi))      # one small nod
            if any(lg["t_ms"] <= t for lg in laughs):
                state["lookX"] = math.sin(t / 700.0) * 0.6                            # glance across the laugh
        rate = min(1.0, 7.0 / fps)
        yaw += (want_yaw - yaw) * rate
        pitch += (want_pitch + 0.035 * mouth - pitch) * min(1.0, 12.0 / fps)
        tilt += (want_tilt - tilt) * rate
        ch = FX.channels_from_state(state)
        w = FX.apply_channels(comic["faces"], comic["face"], ch, comic["arm"], frame=frame, eye_base=comic["eye_base"])
        head.pose(yaw, pitch, tilt, breath=0.012 * math.sin(t / 1000.0 * 2 * math.pi / 4.2), frame=frame)
        rec.append({"f": frame, "t_ms": round(t), "shot": cur["shot"], "mouth": round(mouth, 3), "vis": vis,
                    "blink": round(bl, 2), "channels": ch})
    # camera cuts are hard cuts: constant interpolation on the program camera except inside pushes
    sc.frame_start, sc.frame_end = 1, n
    return rec, cuts


def CK_smoother(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="")
    ap.add_argument("--preset", default="late-night-tv")
    ap.add_argument("--comic", default=str(HERE.parent.parent / "static/avatars/default-v1.vrm"))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--stills", default="")
    ap.add_argument("--perform", default="")
    ap.add_argument("--frames", default="")
    ap.add_argument("--chunk", default="0/1")
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--keys", default="")
    ap.add_argument("--only", default="", help="comma list of still names")
    a = ap.parse_args(CB._ARGV)
    pname, sc, mod, look, comic, cams = setup(a.preset, a.comic, a.strict)
    if bpy.context.window:
        bpy.context.window.scene = sc
    if a.stills:
        render_stills(sc, mod, comic, cams, a.stills, a.width, a.samples, pname, a.only)
    if a.perform:
        tl = json.loads((pathlib.Path(a.perform) / "timeline.json").read_text())
        t0 = time.time()
        rec, cuts = bake_perform(sc, mod, comic, cams, tl, a.fps)
        print(f"BAKED {len(rec)} frames in {time.time() - t0:.1f}s; cuts {[(c['t_ms'], c['shot']) for c in cuts]}")
        if a.keys:
            pathlib.Path(a.keys).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(a.keys).write_text(json.dumps({"check": comic["check"], "cuts": cuts, "frames": rec}, indent=0))
        if a.frames:
            CB.inspect.set_modifier_inputs(mod, {"Show Beam": False})
            fd = pathlib.Path(a.frames).resolve()
            fd.mkdir(parents=True, exist_ok=True)
            CB.render_setup(sc, a.width, round(a.width * 9 / 16 / 2) * 2, a.samples)
            sc.render.use_persistent_data = True
            sc.render.fps = a.fps
            k, nch = (int(x) for x in a.chunk.split("/"))
            n = len(rec)
            per = math.ceil(n / nch)
            sc.frame_start, sc.frame_end = 1 + k * per, min(n, (k + 1) * per)
            sc.render.filepath = str(fd / "f_")
            times, last = [], [time.time()]

            def _post(scene, *_):
                now = time.time()
                times.append(now - last[0])
                print(f"FRAMETIME {scene.frame_current} {now - last[0]:.2f}s", flush=True)
                last[0] = now
            bpy.app.handlers.render_write.append(_post)
            t0 = time.time()
            last[0] = t0
            bpy.ops.render.render(animation=True, scene=sc.name)
            wall = time.time() - t0
            nf = sc.frame_end - sc.frame_start + 1
            stats = {"chunk": a.chunk, "frames": nf, "render_s": round(wall, 1), "s_per_frame": round(wall / max(1, nf), 2),
                     "first_frame_s": round(times[0], 1) if times else None, "width": a.width, "samples": a.samples}
            (fd / f"stats_{k}.json").write_text(json.dumps(stats))
            print("PERFSTATS", json.dumps(stats))


if __name__ == "__main__":
    main()
