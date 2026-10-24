"""Bake a directed newsroom episode onto the anchor and render a chunk of it (Blender 5.2, Cycles CPU).

    blender -b --factory-startup --python sets/blender/newsroom_episode.py -- --skill <video-to-blender>/skills/procedural-blender-nodes \
        --episode <dir from newsroom_show.py> [--anchor <vrm/glb>] [--skin <id>] \
        [--frames out/frames --chunk 3/20 --width 1280 --samples 16 --plate-samples 32 --mode plates|full] [--keys out/keys.json]

The episode directory (newsroom_show.py writes it) holds programme.json (the programme clock: reads with measured
words, wall-card schedule, lower thirds, moods, stings), env.json (VO loudness per frame), cards/ (wall cards + desk
band for the show) and master.wav. Everything below is computed per frame, identically in every chunk:

    director  newsroom_cameras.direct on this anchor's re-solved kit: intro crane, wall shot on each tee, medium at
              each story start, close on emphasis, inserts / push / dolly across long reads, sign-off close and the
              pull-out, the outro crane (cuts snapped into word gaps, 30-degree rule, hold minimums)
    wall      the scheduled card, swapped to the show's ambient art whenever the camera frames the wall partially
              (newsroom_cameras.wall_mode: the headline is never cropped by a push-in or a close-up)
    mouth     the measured word under the playhead -> vowel group -> viseme; amplitude = the VO's own loudness
              (sqrt curve + noise gate) x a syllable shape; through the expressive map (VRoid aa at 1.35)
    face      the read's mood (expressive emotions, eased), a brow flash on emphasis words, a settle smile/smirk when
              a read ends, blinks (seeded 2.2-5 s cadence + one on each cut), eye darts to the lens on cuts
    head      turns to the addressed lens (eyes lead, head follows ~300 ms), a speech nod, slow sway, breath

Render modes: --mode full renders every frame whole. --mode plates (the shortcut) renders, for every LOCKED shot,
the empty studio once per (shot, wall card) as a plate, then only the anchor for each frame: the studio becomes a
shadow catcher (it still lights, occludes and receives the anchor's shadows), the render is cropped to the anchor's
projected bounds, and the compositor lays the anchor over the plate before the lens finish. Moving shots render
whole. stats_<k>.json records both kinds of frame separately so the saving is measured, not assumed.
"""
import argparse, json, math, pathlib, random, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import newsroom_studio as NS  # noqa: E402
import newsroom_build as NB  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import face_express as FX  # noqa: E402
import newsroom_cameras as CK  # noqa: E402
import newsroom_looks as LK  # noqa: E402

ADDRESSED = {"CAM_MEDIUM", "CAM_CLOSE", "CAM_XCU", "CAM_PUSH_A", "CAM_PUSH_B", "CAM_TWO"}
VOWEL_VIS = {"a": "aa", "e": "ee", "i": "ih", "o": "oh", "u": "ou", "y": "ih"}


def loud_to_open(e):
    """VO loudness (0..~1.1) -> jaw amplitude: square root with a noise gate (linear left syllables at a third)."""
    return 0.0 if e < 0.03 else min(1.0, 1.15 * math.sqrt(e))


def vowel_groups(word):
    v = re.findall(r"[aeiouy]+", word.lower())
    return v or ["a"]


def bake(ctx, prog, env, fps, seed=7):
    sc, an = ctx["sc"], ctx["anchor"]
    spec, st = ctx["spec"], ctx["studio"]
    subject = NB.SEATS["anchor1"]
    cuts = CK.direct(prog, spec, subject)
    n = int(round(prog["duration_ms"] / 1000 * fps))
    prog_cam = NS.program_camera(sc)
    head = NS.Head(an["arm"])
    rng = random.Random(seed)
    lines = prog["lines"]
    words = [w for ln in lines for w in ln["words"]]
    cut_ts = [c["t_ms"] for c in cuts]
    blinks, t = [], rng.uniform(600, 1800)
    while t < prog["duration_ms"]:
        blinks.append(t)
        t += rng.uniform(2200, 5000)
    blinks += [c + 90 for c in cut_ts[1:]]
    blinks.sort()
    emph = [w for w in words if CK.is_emphasis(w["word"])]
    ends = [ln["end_ms"] for ln in lines]
    rec = []
    mouth = 0.0
    yaw = pitch = 0.0
    eye_x = eye_y = 0.0
    last_shot = None
    since_cut = 0.0
    for f in range(n):
        frame, t = f + 1, f * 1000.0 / fps
        pose, cur = CK.pose_at(cuts, spec, t)
        shot, moving = CK.shot_name_at(cuts, t)
        NS.set_pose(prog_cam, pose, frame)
        # wall: the scheduled card, ambient whenever the frame would crop a headline
        card = "title"
        for c in prog["cards"]:
            if c["t_ms"] <= t:
                card = c["card"]
        mode = CK.wall_mode(pose, st)
        shown = card if (mode == "headline" or card == "ambient") else "ambient"
        NS.show_card(ctx, shown if shown in ctx["card_names"] else "ambient", frame)
        # mouth from measured words x VO loudness
        state = {}
        open_, vis, speaking, line = 0.0, None, False, None
        for ln in lines:
            if ln["start_ms"] <= t < ln["end_ms"] + 120:
                line = ln
                for w in ln["words"]:
                    if w["start_ms"] <= t < w["end_ms"]:
                        vs = vowel_groups(w["word"])
                        local = (t - w["start_ms"]) / max(1, w["end_ms"] - w["start_ms"]) * len(vs)
                        syl = min(len(vs) - 1, int(local))
                        shape = 0.35 + 0.65 * math.sin(math.pi * min(1.0, local - math.floor(local)))
                        e = env[f] if f < len(env) else 0.0
                        open_, vis, speaking = loud_to_open(e) * shape, VOWEL_VIS.get(vs[syl][0], "aa"), True
                        break
        mouth = open_ if open_ > mouth else mouth + (open_ - mouth) * min(1.0, 18.0 / fps)
        state["speaking"] = speaking or mouth > 0.05
        if vis or mouth > 0.02:
            state["visemes"] = {vis or "aa": mouth}
        # mood (eased 400 ms) and the settle smile after each read
        emos = {}
        for m in prog.get("moods", []):
            if m["t_ms"] - 300 <= t < m["t_ms"] + m["dur_ms"] + 600:
                r = min(1.0, (t - m["t_ms"] + 300) / 400.0, (m["t_ms"] + m["dur_ms"] + 600 - t) / 400.0)
                emos[m["emotion"]] = max(emos.get(m["emotion"], 0.0), m["intensity"] * max(0.0, r))
        if emos:
            state["emotions"] = emos
        done = [e for e in ends if e <= t < e + 1600]
        if done and not speaking:
            r = min(1.0, (t - done[-1]) / 350.0) * min(1.0, (done[-1] + 1600 - t) / 400.0)
            k = ends.index(done[-1])
            state["smirk"] = (0.55 if k % 2 == 0 else -0.45) * r
            state["squint"] = 0.22 * r
        # brow flash on emphasis words, a lift at the start of each tee
        bu = 0.0
        for w in emph:
            if w["start_ms"] - 120 <= t < w["start_ms"] + 380:
                bu = max(bu, 0.5 * math.sin(math.pi * (t - w["start_ms"] + 120) / 500.0))
        for ln in lines:
            if ln["kind"] == "tee" and ln["start_ms"] <= t < ln["start_ms"] + 700:
                bu = max(bu, 0.35 * math.sin(math.pi * (t - ln["start_ms"]) / 700.0))
        if bu > 0:
            state["browUp"] = bu
        bl = max([math.sin(math.pi * (t - b) / 150.0) for b in blinks if b <= t < b + 150] or [0.0])
        state["blinkL"] = state["blinkR"] = bl
        # gaze: the addressed lens (the live single, else the main medium); eyes lead, the head follows
        if shot != last_shot:
            since_cut = 0.0
            last_shot = shot
        since_cut += 1000.0 / fps
        addr = pose if shot in ADDRESSED else spec["CAM_MEDIUM"]
        wy, wp = NS.face_cam(ctx, addr)
        if line is None and t < prog["intro_ms"]:
            wy, wp = 0.0, 0.05
        e_rate = 1.0 if since_cut > 60 else 0.5
        gx = max(-1.0, min(1.0, (wy - yaw) / math.radians(16)))
        eye_x += (gx - eye_x) * e_rate
        state["lookX"] = eye_x
        rate = min(1.0, (1000.0 / fps) / 300.0)
        yaw += (wy - yaw) * rate
        ts = t / 1000.0
        nod = 0.035 * mouth + 0.01 * math.sin(ts * 1.3)
        pitch += (wp + nod - pitch) * min(1.0, 12.0 / fps)
        tilt = 0.02 * math.sin(ts * 0.45 + 0.7) + (0.05 * state.get("smirk", 0.0))
        ch = FX.channels_from_state(state)
        FX.apply_channels(an["faces"], an["face"], ch, an["arm"], frame=frame, eye_base=an["eye_base"])
        head.pose(yaw, pitch, tilt, breath=0.01 * math.sin(ts * 2 * math.pi / 4.2), frame=frame)
        rec.append({"f": frame, "t_ms": round(t), "shot": shot, "moving": moving, "cut": cur["t_ms"], "card": card,
                    "wall": shown, "mouth": round(mouth, 3), "vis": vis, "blink": round(bl, 2),
                    "channels": ch, "pose": {"pos": [round(x, 4) for x in pose["pos"]], "tgt": [round(x, 4) for x in pose["tgt"]],
                                             "lens": round(pose["lens"], 3)}})
    sc.frame_start, sc.frame_end = 1, n
    return rec, cuts


def anchor_bounds(ctx, pose, pad=0.12):
    """Render border (xmin, xmax, ymin, ymax in 0..1) around the anchor's projected bounds (+ the desk area its
    shadow falls on), or None when it is out of frame."""
    pts = []
    for o in ctx["anchor"]["objects"]:
        if o.type == "MESH" and not o.hide_render:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    a = ctx["anchor"]
    ex, ey, ez = a["eye_xyz"]
    pts += [Vector((ex + dx, ey - 0.55, ctx["studio"]["desk_h"])) for dx in (-0.6, 0.6)]
    pr = [CK.project(pose["pos"], pose["tgt"], pose["lens"], tuple(p)) for p in pts]
    pr = [p for p in pr if p is not None]
    if not pr:
        return None
    xs = [(p[0] + 1) / 2 for p in pr]
    ys = [(p[1] + 1) / 2 for p in pr]
    x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
    if x1 < 0 or x0 > 1 or y1 < 0 or y0 > 1:
        return None
    return max(0.0, x0), min(1.0, x1), max(0.0, y0), min(1.0, y1)


def render(ctx, rec, cuts, fd, k, nch, width, samples, plate_samples, mode, only=None):
    sc = ctx["sc"]
    fd = pathlib.Path(fd).resolve()
    fd.mkdir(parents=True, exist_ok=True)
    H = round(width * 9 / 16 / 2) * 2
    NB.render_setup(sc, width, H, samples)
    sc.render.use_persistent_data = True
    n = len(rec)
    per = math.ceil(n / nch)
    f0, f1 = 1 + k * per, min(n, (k + 1) * per)
    look = ctx["look"]
    stud_objs = [ctx["ob"]]
    anchor_objs = [o for o in ctx["anchor"]["objects"] if o.type == "MESH" and not o.hide_render]
    stats = {"chunk": f"{k}/{nch}", "frames": 0, "width": width, "height": H, "samples": samples, "mode": mode,
             "full_frames": 0, "full_s": 0.0, "anchor_frames": 0, "anchor_s": 0.0, "plates": 0, "plate_s": 0.0,
             "plate_samples": plate_samples, "first_frame_s": None}
    LK.post(sc, look)
    plates = {}
    t_all = time.time()
    for f in (only or range(f0, f1 + 1)):
        r = rec[f - 1]
        locked = mode == "plates" and not r["moving"] and r["shot"] != "CAM_CRANE_A"
        sc.frame_set(f)
        t0 = time.time()
        if not locked:
            sc.render.film_transparent = False
            sc.render.use_border = False
            for o in stud_objs:
                o.is_shadow_catcher = False
            LK.post(sc, look)
            sc.cycles.samples = samples
            sc.render.filepath = str(fd / f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True, scene=sc.name)
            dt = time.time() - t0
            stats["full_frames"] += 1
            stats["full_s"] += dt
        else:
            key = (r["shot"], r["wall"], r["cut"])
            if key not in plates:
                tp = time.time()
                for o in anchor_objs:
                    o.hide_render = True
                sc.render.film_transparent = False
                sc.render.use_border = False
                for o in stud_objs:
                    o.is_shadow_catcher = False
                LK.post(sc, dict(look, vignette=0.0, fringe=0.0))
                sc.cycles.samples = plate_samples
                pth = fd / f"plate_{len(plates):02d}_{r['shot']}_{r['wall']}.exr"
                sc.render.image_settings.file_format = "OPEN_EXR"
                sc.render.image_settings.color_depth = "16"
                sc.render.filepath = str(pth)
                bpy.ops.render.render(write_still=True, scene=sc.name)
                sc.render.image_settings.file_format = "PNG"
                sc.render.image_settings.color_depth = "8"
                for o in anchor_objs:
                    o.hide_render = False
                plates[key] = pth
                stats["plates"] += 1
                stats["plate_s"] += time.time() - tp
                print(f"PLATE {pth.name} {time.time() - tp:.1f}s", flush=True)
                t0 = time.time()
            # the anchor alone over the plate: studio = shadow catcher, transparent film, border on the anchor
            sc.render.film_transparent = True
            for o in stud_objs:
                o.is_shadow_catcher = True
            b = anchor_bounds(ctx, r["pose"])
            if b is None:
                b = (0.0, 0.01, 0.0, 0.01)
            sc.render.use_border, sc.render.use_crop_to_border = True, False
            sc.render.border_min_x, sc.render.border_max_x, sc.render.border_min_y, sc.render.border_max_y = b
            LK.post_over(sc, look, str(plates[key]))
            sc.cycles.samples = samples
            sc.render.filepath = str(fd / f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True, scene=sc.name)
            dt = time.time() - t0
            stats["anchor_frames"] += 1
            stats["anchor_s"] += dt
        stats["frames"] += 1
        if stats["first_frame_s"] is None:
            stats["first_frame_s"] = round(dt, 1)
        print(f"FRAMETIME {f} {dt:.2f}s {'anchor' if locked else 'full'} {r['shot']}", flush=True)
    wall = time.time() - t_all
    stats["render_s"] = round(wall, 1)
    stats["s_per_frame"] = round(wall / max(1, stats["frames"]), 2)
    for kk in ("full_s", "anchor_s", "plate_s"):
        stats[kk] = round(stats[kk], 1)
    stats["full_s_per_frame"] = round(stats["full_s"] / stats["full_frames"], 2) if stats["full_frames"] else None
    stats["anchor_s_per_frame"] = round(stats["anchor_s"] / stats["anchor_frames"], 2) if stats["anchor_frames"] else None
    stats["fps"] = sc.render.fps
    (fd / f"stats_{k}.json").write_text(json.dumps(stats, indent=1))
    print("PERFSTATS", json.dumps(stats), flush=True)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="")
    ap.add_argument("--episode", required=True)
    ap.add_argument("--skin", default="")
    ap.add_argument("--anchor", default="")
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--frames", default="")
    ap.add_argument("--chunk", default="0/1")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--plate-samples", type=int, default=32)
    ap.add_argument("--mode", default="plates", choices=["plates", "full"])
    ap.add_argument("--keys", default="")
    ap.add_argument("--only-frames", default="", help="comma list of frames to render (local checks)")
    a = ap.parse_args(NB._ARGV)
    ep = pathlib.Path(a.episode).resolve()
    prog = json.loads((ep / "programme.json").read_text())
    env = json.loads((ep / "env.json").read_text())["env"] if (ep / "env.json").exists() else []
    meta = json.loads((ep / "episode.json").read_text()) if (ep / "episode.json").exists() else {}
    skin = a.skin or meta.get("skin", "goodnight")
    anchor = a.anchor or meta.get("anchor") or str(HERE.parent.parent / "static/avatars/default-v1.vrm")
    if not pathlib.Path(anchor).is_absolute():
        anchor = str((HERE.parent.parent / anchor).resolve())
    ts = time.time()
    ctx = NS.setup(skin, ep / "cards", anchor, strict=True)
    ctx["sc"].render.fps = a.fps
    rec, cuts = bake(ctx, prog, env, a.fps)
    print(f"BAKED {len(rec)} frames in {time.time() - ts:.1f}s; {len(cuts)} cuts", flush=True)
    print("CUTS", json.dumps([(c["t_ms"], c["shot"], c["move"][1] if c.get("move") else None) for c in cuts]))
    if a.keys:
        pathlib.Path(a.keys).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.keys).write_text(json.dumps({"fps": a.fps, "skin": skin, "anchor": {k: ctx["anchor"][k] for k in
                                                    ("eye", "mouth", "height", "seat_h", "measured_by", "path")},
                                                    "check": ctx["anchor"]["check"], "cuts": cuts,
                                                    "spec": {k: {kk: list(vv) if isinstance(vv, tuple) else vv for kk, vv in v.items()}
                                                             for k, v in ctx["spec"].items()},
                                                    "frames": rec}, indent=0))
    if bpy.context.window:
        bpy.context.window.scene = ctx["sc"]
    if a.frames:
        k, nch = (int(x) for x in a.chunk.split("/"))
        fl = [int(x) for x in a.only_frames.split(",")] if a.only_frames else None
        render(ctx, rec, cuts, a.frames, k, nch, a.width, a.samples, a.plate_samples, a.mode, fl)


if __name__ == "__main__":
    main()
