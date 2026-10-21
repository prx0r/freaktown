#!/usr/bin/env python3
"""Render one expressive face frame headlessly (runs INSIDE blender).

Usage (runs INSIDE blender, not system python):
  ~/blender/blender -b --python scripts/render_face.py -- \\
      --glb /path/avatar.glb --out /tmp/faces/happy.png \\
      --weights '{"mouthSmileLeft": 1.0, "cheekSquintLeft": 0.6}' \\
      [--size 512] [--list-morphs]

Finds the head mesh (most morphs wins), applies shape-key weights by
name (unknown names skipped, never invented), frames a head closeup,
renders one Workbench/MATCAP frame. Exit 0 always on success.
"""
import argparse
import json
import math
import os
import sys

import bpy
import mathutils


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--weights", default="{}")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--list-morphs", action="store_true")
    ap.add_argument("--side", default="FRONT",
                    help="camera side: FRONT (+Y face check), BACK, TOP, BOTTOM")
    return ap.parse_args(argv)


def wipe():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                 bpy.data.materials, bpy.data.images):
        for x in list(coll):
            coll.remove(x)


def main():
    a = parse()
    wipe()
    bpy.ops.import_scene.gltf(filepath=a.glb)
    # head mesh: prefer *Head*, else most morphs + largest volume
    # (eyes/teeth carry the same 68 keys but are tiny).
    cands = []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        kb = ob.data.shape_keys.key_blocks if ob.data.shape_keys else []
        if len(kb) > 1:
            vol = (ob.dimensions.x * ob.dimensions.y *
                   ob.dimensions.z)
            cands.append((("head" in ob.name.lower()), len(kb), vol,
                          ob))
    if not cands:
        print("FACE-RENDER: no morph mesh found")
        return
    cands.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    best = cands[0][3]
    names = [k.name for k in best.data.shape_keys.key_blocks] \
        if best.data.shape_keys else []
    if a.list_morphs:
        print("FACE-MORPHS: " + json.dumps(names))
        return
    try:
        weights = json.loads(a.weights)
    except Exception:
        weights = {}
    applied, skipped = 0, []
    morph_meshes = [ob for ob in bpy.data.objects
                    if ob.type == "MESH" and ob.data.shape_keys]
    for ob in morph_meshes:
        for name, w in weights.items():
            kb = ob.data.shape_keys.key_blocks.get(str(name))
            if kb is None:
                if ob is best and str(name) not in skipped:
                    skipped.append(str(name))
                continue
            try:
                kb.value = max(0.0, min(1.0, float(w)))
                if ob is best:
                    applied += 1
            except Exception:
                if ob is best and str(name) not in skipped:
                    skipped.append(str(name))
    # frame the head: center of its bound box, camera on +Y looking back
    c = [0.0, 0.0, 0.0]
    for corner in best.bound_box:
        w = best.matrix_world @ mathutils.Vector(corner)
        c[0] += w.x / 8
        c[1] += w.y / 8
        c[2] += w.z / 8
    size = max(best.dimensions.x, best.dimensions.y,
               best.dimensions.z)
    dist = size * 4.5
    cam = bpy.data.cameras.new("FaceCam")
    cam.lens = 85
    cam.clip_start = 0.01
    co = bpy.data.objects.new("FaceCam", cam)
    bpy.context.scene.collection.objects.link(co)
    co.location = (c[0], c[1] - dist, c[2] + size * 0.05)
    if a.side == "BACK":
        co.location = (c[0], c[1] + dist, c[2] + size * 0.05)
    elif a.side == "TOP":
        co.location = (c[0], c[1], c[2] + dist)
    elif a.side == "BOTTOM":
        co.location = (c[0], c[1], c[2] - dist)
    d = mathutils.Vector((c[0] - co.location.x,
                            c[1] - co.location.y,
                            c[2] - co.location.z))
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = a.size
    sc.render.resolution_y = a.size
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.display.shading.light = "MATCAP"
    sc.render.filepath = a.out
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print(f"FACE-RENDER: applied={applied} skipped={skipped} -> {a.out}")


main()
