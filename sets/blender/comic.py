"""The comic on the club stage: import a VRM/GLB standing at the mic mark, arms down (VRoid J_Aim sleeve fix), measure
the eye line, bind the expressive face (face_express.py) and light the comic with a motivated key and two rims.

Used by club_build.py (--comic, for camera-kit stills) and club_face.py (emotion close-ups, short test render).
"""
import math, pathlib

import bpy
from mathutils import Matrix, Vector

import face_express as FX

AXIS_X, AXIS_Y, AXIS_Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def pb_of(arm, *names):
    for n in names:
        if n in arm.pose.bones:
            return arm.pose.bones[n]
    return None


def rot_world(arm, pb, axis, angle):
    """Rotate a pose bone about a WORLD axis through its posed head (updates the view layer)."""
    if pb is None or not angle:
        return
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    h = mw @ pb.head
    R = Matrix.Translation(h) @ Matrix.Rotation(angle, 4, Vector(axis)) @ Matrix.Translation(-h)
    pb.matrix = mw.inverted() @ R @ mw @ pb.matrix
    bpy.context.view_layer.update()


def standing_pose(arm):
    """Arms down from T-pose with a slight elbow bend; VRoid sleeves hang off J_Aim_* bones (VRMC_node_constraint is
    dropped by the glTF importer) so they swing with the upper arm, else they stay out as 'wings'."""
    for side, s in (("L", 1.0), ("R", -1.0)):
        up = pb_of(arm, f"J_Bip_{side}_UpperArm")
        lo = pb_of(arm, f"J_Bip_{side}_LowerArm")
        aims = [p for p in (pb_of(arm, f"J_Aim_{side}_Shoulder"), pb_of(arm, f"J_Aim_{side}_TopsUpperArm")) if p]
        for b in [up] + aims:
            rot_world(arm, b, AXIS_Y, s * 1.36)          # comic faces -Y: about +Y brings the +X (left) arm down
            rot_world(arm, b, AXIS_X, -0.08)             # a touch forward
        rot_world(arm, lo, AXIS_X, -0.45)                # relaxed elbows, forearms a little forward
        rot_world(arm, lo, AXIS_Y, s * 0.12)


def import_comic(sc, path, at=(0.0, 0.0, 0.0)):
    """Import the VRM/GLB at the mic mark facing -Y. Returns dict(holder, arm, faces, eye, mouth)."""
    p = pathlib.Path(path).resolve()
    src = p
    if p.suffix.lower() == ".vrm":
        src = pathlib.Path("/tmp", p.stem + "_comic.glb")
        src.write_bytes(p.read_bytes())
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(src), import_shading="NORMALS")
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.name not in sc.collection.all_objects:
            sc.collection.objects.link(o)
        if o.type == "MESH" and o.name.lower().startswith("icosphere"):    # a stray helper in default-v1.vrm
            o.hide_render = o.hide_viewport = True
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    holder = bpy.data.objects.new("comic", None)
    sc.collection.objects.link(holder)
    holder.location = at
    for r in [o for o in new if o.parent is None]:
        r.parent = holder
    bpy.context.view_layer.update()
    if arm is not None:
        standing_pose(arm)
    faces = [o for o in new if o.type == "MESH" and o.data.shape_keys and not o.hide_render]
    eye = 1.45
    if arm is not None:
        eyes = [b for b in arm.pose.bones if "faceeye" in b.name.lower() or b.name.lower() in ("lefteye", "righteye")]
        if eyes:
            eye = sum((arm.matrix_world @ b.head).z for b in eyes) / len(eyes)
        else:
            hd = pb_of(arm, "J_Bip_C_Head", "Head", "head")
            if hd is not None:
                eye = (arm.matrix_world @ hd.head).z + 0.07
    return {"holder": holder, "arm": arm, "faces": faces, "eye": eye, "mouth": eye - 0.075, "objects": new}


def bind_face(comic, strict=False):
    b, chk = FX.bind_meshes(comic["faces"], comic["arm"])
    print("FACECHECK", chk)
    if strict and chk["level"] == "fail":
        raise SystemExit(f"FACECHECK fail: this mesh cannot express ({chk['missingCore']})")
    eye_base = {}
    gb = b.get("gaze_bones")
    if gb and comic["arm"] is not None:
        for n in (gb["left"], gb["right"]):
            pb = comic["arm"].pose.bones.get(n)
            if pb is not None:
                pb.rotation_mode = "QUATERNION"
                eye_base[n] = pb.rotation_quaternion.copy()
    comic["face"] = b
    comic["check"] = chk
    comic["eye_base"] = eye_base
    return b, chk


def comic_lights(sc, eye, look, spot_lamp):
    """Motivated light on the comic: a soft key from the follow spot's direction (the spot itself stays tight), a cool
    rim from upstage left and a warm one from upstage right, hitting hair and shoulders; a low frontal bounce."""
    from club_build import add_light, S
    head = Vector((0.0, 0.0, eye))
    lamp = Vector(spot_lamp)
    d = (lamp - head).normalized()
    add_light(sc, "Comic Key", "AREA", head + d * 2.2, look.get("comic_key", 16.0),
              S.srgb(look.get("key_color", "#FFF0DC")), tuple(head), size=0.9)
    add_light(sc, "Comic Rim L", "SPOT", (-1.3, 1.6, eye + 1.4), look.get("comic_rim", 90.0),
              S.srgb(look.get("rim_left", "#40D0FF")), (0.0, 0.0, eye - 0.15), size=0.12, spot_deg=28, blend=0.5)
    add_light(sc, "Comic Rim R", "SPOT", (1.4, 1.5, eye + 1.2), look.get("comic_rim", 90.0) * 0.8,
              S.srgb(look.get("rim_right", "#FF40C0")), (0.0, 0.0, eye - 0.2), size=0.12, spot_deg=28, blend=0.5)
    add_light(sc, "Comic Bounce", "AREA", (0.0, -1.4, 0.35), look.get("comic_bounce", 4.0),
              S.srgb("#FFE2C8"), (0.0, 0.0, eye - 0.3), size=1.2)
