#!/usr/bin/env python3
"""True 3D product mockups (runs INSIDE blender headless, Cycles CPU).

Usage:
  blender -b --python scripts/product_mockup.py -- \
    --product ornament --portrait /path/hero.png --outdir /tmp/prod3d \
    --size 2000 --samples 128
Products: ornament, keychain, brickmini, couple, croc, dice, pegs,
album, coaster. Real geometry, portrait-texture decals, studio light,
white 2000px stills.
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
    ap.add_argument("--product", required=True)
    ap.add_argument("--portrait", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--size", type=int, default=2000)
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--glb", default="")
    return ap.parse_args(argv)


def mat_tex(name, img_path):
    img = bpy.data.images.load(img_path)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def mat_flat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1.0)
    return m


def portrait_disc(r, img_path, loc, face="front"):
    bpy.ops.mesh.primitive_circle_add(radius=r, location=loc)
    o = bpy.context.object
    if face == "front":
        o.rotation_euler = (math.radians(90), 0, 0)
    o.data.materials.append(mat_tex("Portrait", img_path))
    return o


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True
    sc.cycles.device = "CPU"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 1.2
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.0
    # ground shadow catcher
    bpy.ops.mesh.primitive_plane_add(size=5, location=(0, 0, 0))
    ground = bpy.context.object
    ground.is_shadow_catcher = True
    # lights
    bpy.ops.object.light_add(type="AREA", location=(0.6, -0.8, 1.0))
    key = bpy.context.object
    key.data.energy = 60
    key.data.size = 0.6
    bpy.ops.object.light_add(type="AREA", location=(-0.7, -0.3, 0.6))
    fill = bpy.context.object
    fill.data.energy = 25
    fill.data.size = 0.8
    bpy.ops.object.light_add(type="AREA", location=(0, 0.8, 0.7))
    rim = bpy.context.object
    rim.data.energy = 40
    rim.data.size = 0.5

    gold = mat_flat("Gold", (0.79, 0.66, 0.42))
    white = mat_flat("White", (0.96, 0.96, 0.95))
    red = mat_flat("Red", (0.75, 0.15, 0.15))
    blue = mat_flat("Blue", (0.15, 0.3, 0.7))
    yellow = mat_flat("Yellow", (0.98, 0.8, 0.1))
    p = a.product
    H = 0.0  # product visual height for framing

    if p == "ornament":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(0, 0, 0.045))
        ball = bpy.context.object
        ball.data.materials.append(red)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.008, depth=0.012, location=(0, 0, 0.09))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.012, minor_radius=0.0025, location=(0, 0, 0.102))
        portrait_disc(0.028, a.portrait, (0, -0.038, 0.045))
        H = 0.11
    elif p == "keychain":
        bpy.ops.mesh.primitive_cube_add(size=0.06, location=(0, 0, 0.035))
        fob = bpy.context.object
        fob.data.materials.append(white)
        portrait_disc(0.022, a.portrait, (0, -0.0305, 0.035))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.014, minor_radius=0.0025, location=(0, 0, 0.085))
        H = 0.11
    elif p in ("brickmini", "couple"):
        if not a.glb:
            raise SystemExit("brick products need --glb")

        def import_scaled(dx):
            before = set(sc.objects)
            bpy.ops.import_scene.gltf(filepath=a.glb)
            new = [o for o in sc.objects if o not in before]
            meshes = [o for o in new if o.type == "MESH"]
            tall = max(o.dimensions.z for o in meshes)
            s = (0.06 if p == "brickmini" else 0.075) / tall
            for o in new:
                o.scale = (o.scale.x * s, o.scale.y * s, o.scale.z * s)
                o.location.x += dx
            bpy.context.view_layer.update()
            zmin = min((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
            for o in new:
                o.location.z -= zmin
            return new

        import_scaled(0.0)
        if p == "brickmini":
            bpy.ops.mesh.primitive_torus_add(major_radius=0.01, minor_radius=0.002, location=(0.035, 0, 0.075))
            H = 0.09
        else:
            import_scaled(-0.09)
            H = 0.085
    elif p == "croc":
        bpy.ops.mesh.primitive_cylinder_add(radius=0.014, depth=0.008, location=(0, 0, 0.02))
        charm = bpy.context.object
        charm.data.materials.append(yellow)
        portrait_disc(0.012, a.portrait, (0, 0, 0.0245))
        bpy.ops.mesh.primitive_cylinder_add(radius=0.0021, depth=0.014, location=(0, 0, 0.009))
        H = 0.035
    elif p == "dice":
        bpy.ops.mesh.primitive_cube_add(size=0.016, location=(0, 0, 0.008))
        die = bpy.context.object
        die.data.materials.append(white)
        portrait_disc(0.006, a.portrait, (0, -0.0081, 0.008))
        H = 0.02
    elif p == "pegs":
        cols = [red, white, blue]
        for i in range(3):
            x = (i - 1) * 0.03
            bpy.ops.mesh.primitive_cylinder_add(radius=0.004, depth=0.05,
                                                location=(x, 0, 0.025))
            peg = bpy.context.object
            peg.data.materials.append(cols[i])
            portrait_disc(0.0035, a.portrait, (x, 0, 0.051))
        H = 0.055
    elif p == "album":
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.071))
        case = bpy.context.object
        case.scale = (0.142, 0.01, 0.125)
        bpy.context.view_layer.update()
        case.data.materials.append(mat_flat("Black", (0.05, 0.05, 0.06)))
        portrait_disc(0.05, a.portrait, (0, -0.006, 0.071))
        H = 0.15
    elif p == "coaster":
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.005, location=(0, 0, 0.0025))
        co = bpy.context.object
        co.data.materials.append(mat_flat("Slate", (0.2, 0.22, 0.26)))
        portrait_disc(0.038, a.portrait, (0, 0, 0.0052))
        H = 0.008
    else:
        raise SystemExit("unknown product " + p)

    # frame it
    dist = max(0.1, H * 1.1)
    bpy.ops.object.camera_add(location=(dist * 0.35, -dist, H * 0.75),
                              rotation=(math.radians(72), 0, math.radians(10)))
    cam = bpy.context.object
    cam.data.lens = 40
    from mathutils import Vector
    focus_pt = Vector((0, 0, H * 0.42))
    cam.location = Vector((dist * 0.35, -dist, H * 0.75))
    cam.rotation_euler = (focus_pt - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.camera = cam
    sc.render.resolution_x = a.size
    sc.render.resolution_y = a.size
    sc.render.image_settings.file_format = "PNG"
    os.makedirs(a.outdir, exist_ok=True)
    sc.render.filepath = os.path.join(a.outdir, p + "_cycles.png")
    sc.render.fps = 24
    sc.frame_start = 1
    sc.frame_end = 1
    bpy.ops.render.render(write_still=True)
    print("MOCKUP DONE", p)


main()
