#!/usr/bin/env python3
"""Repair brick GLB -> print-ready STL (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/repair_brick.py -- \
    --glb in.glb --out out.stl --height_mm 75
Steps: join parts, weld doubles, recalc normals, fill small holes,
re-check manifold, normalize to height, export STL. Reports residuals.
Conservative: no boolean union (slicers union intersecting shells).
"""
import argparse
import json
import sys

import bmesh
import bpy


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = sys.argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--height_mm", type=float, default=75.0)
    return ap.parse_args(argv)


def audit(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    n = len(bm.verts)
    bm.free()
    return n, nm, loose


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    ctx = bpy.context
    meshes = [o for o in ctx.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    ctx.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    fig = ctx.view_layer.objects.active
    # weld + normals + fill
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.fill_holes(sides=8)
    bpy.ops.object.mode_set(mode="OBJECT")
    # normalize height
    bpy.context.view_layer.update()
    ws = [fig.matrix_world @ v.co for v in fig.data.vertices]
    h = max(v.z for v in ws) - min(v.z for v in ws)
    s = (a.height_mm / 1000.0) / h if h > 0 else 1.0
    fig.scale = (fig.scale.x * s, fig.scale.y * s, fig.scale.z * s)
    bpy.context.view_layer.update()
    ws = [fig.matrix_world @ v.co for v in fig.data.vertices]
    fig.location.z -= min(v.z for v in ws)
    n, nm, loose = audit(fig.data)
    ws = [fig.matrix_world @ v.co for v in fig.data.vertices]
    bounds = [round((max(v[i] for v in ws) - min(v.z if False else v[i] for v in ws)) * 1000, 1)
              for i in range(3)]
    bpy.ops.wm.stl_export(filepath=a.out, export_selected_objects=True)
    print("REPAIR-REPORT:" + json.dumps({"verts": n, "nonmanifold": nm, "loose": loose,
                                         "bounds_mm": bounds, "out": a.out}))


main()
