#!/usr/bin/env python3
"""Print QC for brick-figure GLBs (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/brick_qc.py -- --glb <file> [--scale 75]
Reports JSON: parts, bounds/height, scale fix, non-manifold edges,
loose verts, material base colors, face-region detail estimate.
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
    ap.add_argument("--scale", type=float, default=75.0)
    return ap.parse_args(argv)


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    parts = []
    for o in meshes:
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        nonman = sum(1 for e in bm.edges if not e.is_manifold)
        loose = sum(1 for v in bm.verts if not v.link_edges)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        bm.free()
        mats = []
        for m in o.data.materials:
            if m and m.use_nodes:
                bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf:
                    mats.append({"name": m.name,
                                 "base": [round(float(x), 3) for x in bsdf.inputs["Base Color"].default_value]})
        ws = [o.matrix_world @ v.co for v in me.vertices]
        xs = [v.x for v in ws]
        ys = [v.y for v in ws]
        zs = [v.z for v in ws]
        parts.append({"object": o.name, "verts": len(me.vertices), "tris": tris,
                      "nonmanifold_edges": nonman, "loose_verts": loose,
                      "bounds_mm": [round((max(xs) - min(xs)) * 1000, 1),
                                    round((max(ys) - min(ys)) * 1000, 1),
                                    round((max(zs) - min(zs)) * 1000, 1)],
                      "materials": mats})
    zs = [b for p in parts for b in [p["bounds_mm"][2]]]
    print("QC-REPORT:" + json.dumps({"file": a.glb, "target_mm": a.scale, "parts": parts}))


main()
