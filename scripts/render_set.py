#!/usr/bin/env python3
"""Render a character set in Blender (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/render_set.py -- \
    --glb data/character-meshes/quaternius_cc0-husky-1095.glb \
    --audio /tmp/pilot/set.wav --timeline /tmp/pilot/timeline.json \
    --outdir /tmp/pilot/frames --width 360 --height 640 --fps 24

Reads the delivery timeline, stages a Workbench club scene, drives the
puppet from its own GLB actions plus procedural emphasis, cuts cameras
per beat, and renders a PNG sequence (muxed later with ffmpeg).
"""
import argparse
import json
import math
import os
import sys

import bpy


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = argv.index("--") + 1
        argv = sys.argv[argv:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--width", type=int, default=360)
    ap.add_argument("--height", type=int, default=640)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--height_m", type=float, default=1.1)
    ap.add_argument("--mouth", default="", help="mouth_cues.json for jaw drive (optional)")
    ap.add_argument("--from-frame", type=int, default=1, help="resume: skip segments ending before this frame")
    return ap.parse_args(argv)


def ms_to_frame(ms, fps):
    return 1 + int(ms / 1000.0 * fps)


def set_stepped():
    """PogMotion stepped sampler: CONSTANT interpolation on every fcurve
    (12Hz-placed keys hold; camera/scene untouched)."""
    for act in bpy.data.actions:
        bags = []
        try:
            bags.append(act.fcurves)
        except AttributeError:
            pass
        try:
            for layer in act.layers:
                for strip in layer.strips:
                    try:
                        bags.append(strip.channelbag.fcurves)
                    except AttributeError:
                        pass
        except AttributeError:
            pass
        for fcs in bags:
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def main():
    a = parse()
    fps = a.fps
    timeline = json.load(open(a.timeline))
    total_ms = max(t["end_ms"] + t["pause_after_ms"] for t in timeline)
    end_frame = ms_to_frame(total_ms, fps) + 12

    # --- wipe + import -----------------------------------------------------
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    roots = [o for o in bpy.context.scene.objects if o.parent is None]
    perf = max(roots, key=lambda o: (o.type == "MESH", (o.dimensions.z if hasattr(o, "dimensions") else 0)))
    # normalize height
    dims = [o.dimensions.z for o in bpy.context.scene.objects if o.type == "MESH"]
    tall = max(dims) if dims else 1.0
    s = a.height_m / tall if tall > 0 else 1.0
    for o in roots:
        o.scale = (o.scale.x * s, o.scale.y * s, o.scale.z * s)
    bpy.context.view_layer.update()
    # ground the performer: lowest point to z=0
    zmin = min((o.matrix_world @ v.co).z for o in bpy.context.scene.objects
               if o.type == "MESH" for v in o.data.vertices)
    for o in roots:
        o.location.z -= zmin
    bpy.context.view_layer.update()
    cx = sum(o.location.x for o in roots) / max(1, len(roots))

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = a.width
    sc.render.resolution_y = a.height
    sc.render.film_transparent = False
    sc.display.shading.light = "MATCAP"
    world = sc.world
    if world is None:
        world = bpy.data.worlds.new("World")
        sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.03, 0.06, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0

    # --- club: floor, backdrop, lights, mic --------------------------------
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.01))
    floor = bpy.context.object
    fmat = bpy.data.materials.new("Floor")
    fmat.diffuse_color = (0.08, 0.05, 0.09, 1.0)
    floor.data.materials.append(fmat)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 8, 5), rotation=(math.radians(90), 0, 0))
    bpy.ops.object.light_add(type="SPOT", location=(0, -3, 5))
    key = bpy.context.object
    key.data.energy = 2500
    key.data.color = (1.0, 0.85, 0.7)
    key.data.spot_size = 0.7
    track = key.constraints.new("TRACK_TO")
    track.target = perf
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.ops.object.light_add(type="AREA", location=(3, -4, 3))
    fill = bpy.context.object
    fill.data.energy = 500
    fill.data.color = (0.5, 0.65, 1.0)
    bpy.ops.object.light_add(type="POINT", location=(0, -2.5, 1.2))
    front = bpy.context.object
    front.data.energy = 300
    front.data.color = (1.0, 0.9, 0.8)
    bpy.ops.object.light_add(type="SPOT", location=(0, 4, 4))
    rim = bpy.context.object
    rim.data.energy = 400
    rim.data.color = (1.0, 0.4, 0.3)
    # mic: stand + head
    bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=1.4, location=(0.45, -0.55, 0.7))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=(0.45, -0.55, 1.45))

    # --- cameras: wide / medium / close ------------------------------------
    h = a.height_m
    cams = {}

    def add_cam(name, loc, rot):
        bpy.ops.object.camera_add(location=loc, rotation=rot)
        c = bpy.context.object
        c.name = name
        c.data.lens = 50
        cams[name] = c
        return c

    add_cam("CAM_WIDE", (0, -4.2, 1.3), (math.radians(78), 0, 0))
    add_cam("CAM_MEDIUM", (0.3, -2.4, 1.05), (math.radians(82), 0, 0))
    add_cam("CAM_CLOSE", (-0.25, -1.3, 1.15), (math.radians(84), 0, 0))
    for c in cams.values():
        t = c.constraints.new("TRACK_TO")
        t.target = perf
        t.track_axis = "TRACK_NEGATIVE_Z"
        t.up_axis = "UP_Y"

    # --- puppet motion ------------------------------------------------------
    # PogMotion v1: NLA clips where present; procedural stepped layer for
    # emphasis; jaw driven from mouth cues where a jaw bone exists;
    # whole-body fallback (bob/lean/slide) for armature-less meshes.
    arm = next((o for o in sc.objects if o.type == "ARMATURE"), None)
    actions = {act.name: act for act in bpy.data.actions}
    idle = (actions.get("Idle_2") or actions.get("Idle") or actions.get("Anim_GiraffeIdle")
            or actions.get("Spider_Idle") or actions.get("Pixabay_International_Cat"))
    walk = actions.get("Walk") or actions.get("Anim_GiraffeWalkForward") or actions.get("Spider_Walk")
    movers = [arm] if arm else roots
    # entrance: slide in from stage left over first 3s
    for m in movers:
        m.location.x = -2.4
        m.keyframe_insert("location", frame=1)
        m.location.x = 0.0
        m.keyframe_insert("location", frame=3 * fps)
    if arm and idle:
        ad = arm.animation_data_create()
        ad.action = None
        tr = ad.nla_tracks.new()
        tr.name = "base"
        ilen = max(1, int(idle.frame_range.y - idle.frame_range.x))
        reps = max(1, math.ceil(end_frame / ilen) + 1)
        st = tr.strips.new("idle", 1, idle)
        st.repeat = reps
        st.blend_type = "COMBINE"
        # punchline emphasis: head dip + recover on each punchline/tag
        pbones = arm.pose.bones
        head = (pbones.get("Head") or pbones.get("Head_M") or pbones.get("Neck3")
                or pbones.get("Neck_3") or pbones.get("Neck1"))
        # sparse speech-coupled emphasis: 2 small nods per beat on the 12Hz
        # grid (no constant bobbing; energy scales amplitude)
        for t in timeline:
            if head and t["dur_ms"] > 1200:
                f0 = ms_to_frame(t["start_ms"], fps)
                amp = 0.06 + 0.06 * float(t.get("energy", 0.9) or 0.9)
                for k, frac in ((0.3, -1.0), (0.55, 0.6)):
                    f = f0 + int(t["dur_ms"] / 1000.0 * fps * frac // 2 * 2)
                    head.rotation_mode = "XYZ"
                    head.rotation_euler = (amp, 0, 0)
                    head.keyframe_insert("rotation_euler", frame=f)
                    head.rotation_euler = (0.0, 0, 0)
                    head.keyframe_insert("rotation_euler", frame=f + 4)
        for t in timeline:
            if t["type"] in ("punchline", "tag"):
                f0 = ms_to_frame(t["start_ms"], fps)
                if head:
                    head.rotation_mode = "XYZ"
                    for df, ang in ((0, 0.0), (6, -0.28), (14, 0.12), (22, 0.0)):
                        head.rotation_euler = (ang, 0, 0)
                        head.keyframe_insert("rotation_euler", frame=f0 + df)
                # hop: root z bump
                arm.location.z = 0.0
                arm.keyframe_insert("location", frame=f0 + 4)
                arm.location.z = 0.12
                arm.keyframe_insert("location", frame=f0 + 10)
                arm.location.z = 0.0
                arm.keyframe_insert("location", frame=f0 + 18)
        # jaw drive from mouth cues (replacement-morph-simple flap ladder:
        # real bone where present, nothing faked where absent)
        jaw = None
        for cand in ("Jaw_M", "Wolf_Head_JawSHJnt", "Mouth", "Jaw"):
            if cand in pbones:
                jaw = pbones[cand]
                break
        if jaw and getattr(a, "mouth", ""):
            try:
                cues = json.load(open(a.mouth))
            except Exception:
                cues = []
            jaw.rotation_mode = "XYZ"
            for c in cues:
                f0 = ms_to_frame(c["start_ms"], fps)
                f1 = ms_to_frame(c["end_ms"], fps)
                jaw.rotation_euler = (0.0, 0, 0)
                jaw.keyframe_insert("rotation_euler", frame=max(1, f0 - 1))
                jaw.rotation_euler = (-0.35, 0, 0)
                jaw.keyframe_insert("rotation_euler", frame=f0 + 1)
                jaw.rotation_euler = (0.0, 0, 0)
                jaw.keyframe_insert("rotation_euler", frame=f1)
    else:
        # static-mesh fallback: whole-body acting on roots (stepped later)
        for t in timeline:
            f0 = ms_to_frame(t["start_ms"], fps)
            for m in movers:
                if t["type"] in ("punchline", "tag"):
                    m.rotation_euler = (0.06, 0, 0.04)
                    m.keyframe_insert("rotation_euler", frame=f0 + 6)
                    m.rotation_euler = (0.0, 0, 0)
                    m.keyframe_insert("rotation_euler", frame=f0 + 20)
                elif t["dur_ms"] > 1200:
                    f = f0 + int(t["dur_ms"] / 1000.0 * fps * 0.4 // 2 * 2)
                    m.rotation_euler = (0.03, 0, 0)
                    m.keyframe_insert("rotation_euler", frame=f)
                    m.rotation_euler = (0.0, 0, 0)
                    m.keyframe_insert("rotation_euler", frame=f + 4)

    # --- camera cuts per beat (frame handler: robust headless) ------------------
    order = {"CAM_MEDIUM": 0}

    def pick_cam(beat, i):
        t = beat["type"]
        if t == "setup":
            return "CAM_MEDIUM"
        if t == "punchline":
            return "CAM_CLOSE"
        if t == "closer":
            return "CAM_WIDE"
        order["CAM_MEDIUM"] += 1
        return "CAM_MEDIUM" if order["CAM_MEDIUM"] % 2 else "CAM_CLOSE"

    cuts = []  # (start_frame, cam_obj)
    sc.camera = cams["CAM_WIDE"]
    # PogDirector mechanism language (comedy/mechanism-direction.json):
    # beat type resolves to a mechanism entry; its acting list is logged
    # per segment for traceability. Camera stays type-resolved (v1).
    dpath = os.path.join(os.path.dirname(__file__), "..", "comedy", "mechanism-direction.json")
    try:
        direction = json.load(open(os.path.normpath(dpath)))
    except Exception:
        direction = {}
    TYPE2MECH = {"setup": "incongruity_misdirection", "escalation": "escalation",
                 "misdirect": "incongruity_misdirection", "punchline": "escalation",
                 "tag": "callback", "callback": "callback", "closer": "callback"}
    segments = []  # (start_frame, end_frame, cam_obj): exact tiling
    for i, t in enumerate(timeline):
        f = ms_to_frame(t["start_ms"], fps)
        cam = cams[pick_cam(t, i)]
        sc.timeline_markers.new("b%s_%s" % (t["beat_id"], cam.name), frame=f)
        cuts.append((f, cam.name))
        f1 = ms_to_frame(timeline[i + 1]["start_ms"], fps) - 1 if i + 1 < len(timeline) else end_frame
        segments.append((f, f1, cam))
    cuts.sort()
    json.dump([{"frame": f0, "camera": c.name,
                "beat_id": timeline[i]["beat_id"], "beat_type": timeline[i]["type"],
                "mechanism": TYPE2MECH.get(timeline[i]["type"], "escalation"),
                "acting": direction.get(TYPE2MECH.get(timeline[i]["type"], "escalation"), {}).get("acting", [])}
               for i, (f0, _, c) in enumerate(segments)],
              open(os.path.join(os.path.dirname(a.timeline), "cuts.json"), "w"), indent=1)

    # --- render PNG sequence: one pass per camera segment (deterministic) ----
    set_stepped()  # stepped puppet channels; camera/scene untouched
    sc.render.fps = fps
    os.makedirs(a.outdir, exist_ok=True)
    sc.render.filepath = os.path.join(a.outdir, "f###.png")
    sc.render.image_settings.file_format = "PNG"
    for f0, f1, cam in segments:
        if f1 < a.from_frame:
            continue
        sc.camera = cam
        sc.frame_start = max(f0, a.from_frame)
        sc.frame_end = f1
        bpy.ops.render.render(animation=True)
    print("RENDER DONE frames=%d fps=%d segs=%d" % (end_frame, fps, len(segments)))


main()
