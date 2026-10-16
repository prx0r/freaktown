#!/usr/bin/env python3
"""Brick figure listing renders (runs INSIDE blender headless).

Usage:
  blender -b --python scripts/render_brick.py -- \
    --glb /tmp/brick/brick-figure-XXX.glb --outdir /tmp/brickshots \
    --height_m 0.15 --size 1000
Renders front / three-quarter / back / top stills + 8-frame turntable.
Workbench MATCAP previs look, warm dark club backdrop.
"""
import argparse
import math
import os
import sys

import bpy


def parse():
    argv = sys.argv
    if "--" in argv:
        argv = sys.argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--height_m", type=float, default=0.15)
    ap.add_argument("--size", type=int, default=1000)
    return ap.parse_args(argv)


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=a.glb)
    roots = [o for o in bpy.context.scene.objects if o.parent is None]
    tall = max([o.dimensions.z for o in bpy.context.scene.objects if o.type == "MESH"] or [1.0])
    s = a.height_m / tall if tall > 0 else 1.0
    for o in roots:
        o.scale = (o.scale.x * s, o.scale.y * s, o.scale.z * s)
    bpy.context.view_layer.update()
    zmin = min((o.matrix_world @ v.co).z for o in bpy.context.scene.objects
               if o.type == "MESH" for v in o.data.vertices)
    for o in roots:
        o.location.z -= zmin
    bpy.context.view_layer.update()

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "MATCAP"
    sc.render.film_transparent = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.06, 0.04, 0.08, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, -0.001))
    bpy.ops.object.light_add(type="SUN", location=(4, -5, 8))

    h = a.height_m
    bpy.ops.object.empty_add(location=(0, 0, h * 0.55))
    focus = bpy.context.object
    bpy.ops.object.camera_add(location=(0, -h * 3.2, h * 0.75))
    cam = bpy.context.object
    cam.data.lens = 55
    t = cam.constraints.new("TRACK_TO")
    t.target = focus
    t.track_axis = "TRACK_NEGATIVE_Z"
    t.up_axis = "UP_Y"
    sc.camera = cam

    sc.render.resolution_x = a.size
    sc.render.resolution_y = a.size
    sc.render.image_settings.file_format = "PNG"
    os.makedirs(a.outdir, exist_ok=True)
    views = {"front": 0.0, "threequarter": 0.6, "side": 1.5708, "back": 3.1416}
    for name, ang in views.items():
        r = h * 3.2
        cam.location = (-math.sin(ang) * r, -math.cos(ang) * r, h * 0.75)
        sc.render.filepath = os.path.join(a.outdir, f"brick_{name}.png")
        bpy.ops.render.render(write_still=True)
    for i in range(8):
        ang = i / 8 * 2 * math.pi
        r = h * 3.2
        cam.location = (-math.sin(ang) * r, -math.cos(ang) * r, h * 0.75)
        sc.render.filepath = os.path.join(a.outdir, f"turn_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
    print("BRICK DONE", a.outdir)


main()
