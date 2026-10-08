#!/usr/bin/env python3
"""Blender factory v1: inspect → transform → prove. One headless call.

Usage (runs INSIDE blender, not system python):
  ~/blender/blender -b --python scripts/blender_factory.py -- \
      --in /tmp/badger-30k.glb --out /tmp/factory/badger \
      [--decimate 0.5] [--views 4] [--export out.glb]

Pattern borrowed from @three-ws/blender-mcp (one process per call,
payload via args, JSON report on stdout tail) without its node runtime:
our box already has Blender 4.2 + system python, nothing to install.

Report: objects, meshes, tris, verts, armatures + bone names, actions,
materials, bounds, metres-tall. Exit 0 always on success; inspection
never fails a static mesh — it just reports bones=[].
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
        argv = argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", default="/tmp/factory/out")
    ap.add_argument("--decimate", type=float, default=0.0)
    ap.add_argument("--views", type=int, default=4)
    ap.add_argument("--export", default="")
    return ap.parse_args(argv)


def wipe():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                 bpy.data.materials, bpy.data.images):
        for x in list(coll):
            coll.remove(x)


def tris_of(ob):
    try:
        deps = bpy.context.evaluated_depsgraph_get()
        m = ob.evaluated_get(deps).to_mesh()
        n = len(m.loop_triangles)
        ob.evaluated_get(deps).to_mesh_clear()
        return n
    except Exception:
        return 0


def main():
    a = parse()
    os.makedirs(a.out, exist_ok=True)
    wipe()
    bpy.ops.import_scene.gltf(filepath=a.inp)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    tris0 = sum(tris_of(o) for o in meshes)
    verts0 = sum(len(o.data.vertices) for o in meshes)

    if a.decimate and 0.0 < a.decimate < 1.0:
        for o in meshes:
            mod = o.modifiers.new("FactoryDecimate", "DECIMATE")
            mod.ratio = a.decimate
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=mod.name)

    tris1 = sum(tris_of(o) for o in meshes)
    bones = sorted({b.name for ar in arms for b in ar.data.bones})
    mats = sorted({m.name for o in meshes for m in o.data.materials if m})
    bounds = [list(map(float, o.bound_box[0])) + [0, 0, 0]
              for o in meshes[:1]]
    tall = 0.0
    for o in meshes:
        ws = [o.matrix_world @ v.co for v in o.data.vertices] or None
        if ws:
            tall = max(tall, max(v.z for v in ws) - min(v.z for v in ws))

    previews = []
    if a.views > 0:
        scene = bpy.context.scene
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.resolution_x = 512
        scene.render.resolution_y = 512
        scene.render.film_transparent = True
        scene.render.filepath = os.path.join(a.out, "view.png")
        scene.render.image_settings.file_format = "PNG"
        cam_data = bpy.data.cameras.new("FactoryCam")
        cam = bpy.data.objects.new("FactoryCam", cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
        sun = bpy.data.objects.new("FactorySun",
                                   bpy.data.lights.new("FactorySun", "SUN"))
        scene.collection.objects.link(sun)
        r = max(tall, 0.5) * 1.4
        for i in range(a.views):
            ang = 2 * math.pi * i / a.views
            cam.location = (r * math.sin(ang), -r * math.cos(ang), tall * 0.6)
            d = cam.location.copy()
            d.length = 0.0
            cam.rotation_euler = (math.radians(70), 0, ang)
            scene.render.filepath = os.path.join(a.out, f"view{i}.png")
            bpy.ops.render.render(write_still=True)
            previews.append(f"view{i}.png")

    exp = ""
    if a.export:
        bpy.ops.export_scene.gltf(filepath=a.export, export_format="GLB")
        exp = a.export

    print("FACTORY-REPORT:" + json.dumps({
        "meshes": len(meshes), "tris_before": tris0, "verts": verts0,
        "tris_after": tris1, "armatures": len(arms), "bones": bones[:40],
        "bone_count": len(bones), "actions": [x.name for x in bpy.data.actions],
        "materials": mats[:20], "metres_tall": round(tall, 3),
        "previews": previews, "export": exp,
    }))


main()
