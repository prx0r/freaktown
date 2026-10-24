"""Any VRM/GLB anchor at the newsroom desk: refuse a mesh that cannot express, seat it, measure it, bind its face.

    anchor = seat_anchor(sc, "static/avatars/default-v1.vrm", seat="anchor1", desk_h=0.8, strict=True)
    anchor["eye"], anchor["mouth"]      measured world heights after seating (the camera kit re-solves from these)
    anchor["face"], anchor["check"]     the expressive binding (face_express.bind_meshes) and its channel check

1. checkFace BEFORE import (face_express.glb_names + check_face, no Blender needed): a mesh with no mouth, blink,
   smile or brow channel is refused with a clear message (AnchorRefused, exit code 3) when strict.
2. Import (a .vrm is glTF with VRM extensions; Blender's importer reads the glTF part). Rig-agnostic bone lookup:
   VRoid J_Bip_*, VRM humanoid names, Mixamo/Meshy (Hips, LeftUpLeg, LeftArm, LeftForeArm ...).
3. Height: a mesh under 1.2 m or over 2.1 m tall is scaled to 1.65 m (a Meshy export can come in at any size).
4. Seat: thighs forward, shins down, then the WHOLE body is lifted/lowered so the eyes sit DESK_EYE m above the
   desk top (the newsroom eye-line) and the chair's seat follows the hips. Arms: a two-bone IK puts each wrist on
   the desk in front of the anchor (T-pose and A-pose rigs alike). Segments are measured joint to joint, never from
   bone tails (a glTF import guesses tails: a Meshy rig came in with 10 m ones). VRoid's J_Aim sleeve bones swing
   with the upper arm (Blender's importer drops VRMC_node_constraint: "sleeve wings" otherwise).
5. Measure: eye height = centroid of the vertices the blink shapes move; mouth = centroid of what the mouth-open
   shape moves (rig-agnostic, on the posed mesh); bone fallback (eye bones / head + 0.07).
6. Bind: face_express.bind_meshes generates one-sided smirk shapes, raises slider ranges, keys start at 0.
"""
import json, math, pathlib

import bpy
from mathutils import Matrix, Vector, Quaternion

import face_express as FX

DESK_EYE = 0.43          # eyes this far above the desk top: a broadcast anchor's seated eye-line
SEATS = {"anchor1": (0.75, 0.55), "anchor2": (-0.75, 0.55)}

ALIASES = {
    "hips": ["J_Bip_C_Hips", "hips", "Hips", "mixamorig:Hips", "pelvis"],
    "spine": ["J_Bip_C_Spine", "spine", "Spine", "mixamorig:Spine"],
    "chest": ["J_Bip_C_UpperChest", "J_Bip_C_Chest", "upperChest", "chest", "Spine02", "Spine2", "mixamorig:Spine2", "Spine01"],
    "neck": ["J_Bip_C_Neck", "neck", "Neck", "mixamorig:Neck"],
    "head": ["J_Bip_C_Head", "head", "Head", "mixamorig:Head"],
    "upperLeg.L": ["J_Bip_L_UpperLeg", "leftUpperLeg", "LeftUpLeg", "mixamorig:LeftUpLeg", "thigh.L", "thigh_l"],
    "lowerLeg.L": ["J_Bip_L_LowerLeg", "leftLowerLeg", "LeftLeg", "mixamorig:LeftLeg", "shin.L", "calf_l"],
    "foot.L": ["J_Bip_L_Foot", "leftFoot", "LeftFoot", "mixamorig:LeftFoot", "foot.L", "foot_l"],
    "upperLeg.R": ["J_Bip_R_UpperLeg", "rightUpperLeg", "RightUpLeg", "mixamorig:RightUpLeg", "thigh.R", "thigh_r"],
    "lowerLeg.R": ["J_Bip_R_LowerLeg", "rightLowerLeg", "RightLeg", "mixamorig:RightLeg", "shin.R", "calf_r"],
    "foot.R": ["J_Bip_R_Foot", "rightFoot", "RightFoot", "mixamorig:RightFoot", "foot.R", "foot_r"],
    "upperArm.L": ["J_Bip_L_UpperArm", "leftUpperArm", "LeftArm", "mixamorig:LeftArm", "upper_arm.L", "upperarm_l"],
    "lowerArm.L": ["J_Bip_L_LowerArm", "leftLowerArm", "LeftForeArm", "mixamorig:LeftForeArm", "forearm.L", "lowerarm_l"],
    "hand.L": ["J_Bip_L_Hand", "leftHand", "LeftHand", "mixamorig:LeftHand", "hand.L", "hand_l"],
    "upperArm.R": ["J_Bip_R_UpperArm", "rightUpperArm", "RightArm", "mixamorig:RightArm", "upper_arm.R", "upperarm_r"],
    "lowerArm.R": ["J_Bip_R_LowerArm", "rightLowerArm", "RightForeArm", "mixamorig:RightForeArm", "forearm.R", "lowerarm_r"],
    "hand.R": ["J_Bip_R_Hand", "rightHand", "RightHand", "mixamorig:RightHand", "hand.R", "hand_r"],
}


class AnchorRefused(SystemExit):
    pass


def bone(arm, key):
    if arm is None:
        return None
    for n in ALIASES.get(key, [key]):
        if n in arm.pose.bones:
            return arm.pose.bones[n]
    low = {b.name.lower().replace("mixamorig:", ""): b for b in arm.pose.bones}
    for n in ALIASES.get(key, [key]):
        b = low.get(n.lower().replace("mixamorig:", ""))
        if b is not None:
            return b
    return None


def _upd():
    bpy.context.view_layer.update()


def wpos(arm, pb, tail=False):
    _upd()
    return arm.matrix_world @ (pb.tail if tail else pb.head)


def rotate_world(arm, pb, q, pivot=None):
    """Rotate a pose bone by the world-space quaternion q about pivot (default: its own head)."""
    if pb is None:
        return
    _upd()
    mw = arm.matrix_world
    h = pivot if pivot is not None else mw @ pb.head
    R = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h)
    pb.matrix = mw.inverted() @ R @ mw @ pb.matrix
    _upd()


def aim(arm, pb, direction, carry=(), end=None):
    """Turn pb so its segment (head -> the next joint's head, else head -> tail) points along a world direction;
    carry= bones rotated by the same world rotation about pb's head (VRoid sleeve J_Aim bones)."""
    if pb is None:
        return Quaternion()
    cur = ((wpos(arm, end) if end is not None else wpos(arm, pb, True)) - wpos(arm, pb)).normalized()
    q = cur.rotation_difference(Vector(direction).normalized())
    piv = wpos(arm, pb)
    rotate_world(arm, pb, q)
    for c in carry:
        if c is not None:
            rotate_world(arm, c, q, piv)
    return q


def two_bone(s, l1, l2, target, pole):
    """Elbow position for a 2-bone chain from s to target with segment lengths l1, l2, bending toward pole."""
    s, target, pole = Vector(s), Vector(target), Vector(pole)
    d = target - s
    dist = max(1e-4, min(d.length, (l1 + l2) * 0.999))
    dn = d.normalized()
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    p = (pole - s)
    p = (p - dn * p.dot(dn)).normalized()
    return s + dn * a + p * h


def precheck(path, strict=True):
    names, nodes = FX.glb_names(path)
    chk = FX.check_face(names, nodes)
    print("FACECHECK-PRE", json.dumps({"file": str(path), **chk}))
    if strict and chk["level"] == "fail":
        raise AnchorRefused(f"ANCHOR REFUSED: {path} cannot express (no {', '.join(chk['missingCore'])} channel). "
                            f"Add face shapes (npm run face:rig -- in.glb out.glb bakes jaw/blink/brow/smile) and retry.")
    return chk


def import_mesh(sc, path):
    p = pathlib.Path(path).resolve()
    src = p
    if p.suffix.lower() == ".vrm":
        src = pathlib.Path("/tmp", p.stem + "_anchor.glb")
        src.write_bytes(p.read_bytes())
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(src), import_shading="NORMALS")
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.name not in sc.collection.all_objects:
            sc.collection.objects.link(o)
        if o.type == "MESH" and o.name.lower().startswith("icosphere"):     # stray helper in some exports
            o.hide_render = o.hide_viewport = True
    return new


def bbox_z(objs):
    zs = []
    _upd()
    for o in objs:
        if o.type == "MESH" and not o.hide_render:
            zs += [(o.matrix_world @ Vector(c)).z for c in o.bound_box]
    return (min(zs), max(zs)) if zs else (0.0, 1.6)


def shape_centroid(meshes, names, frac=0.5):
    """World centroid of the vertices the named shape keys move most (posed mesh, evaluated)."""
    pts = []
    for ob in meshes:
        kbs = ob.data.shape_keys.key_blocks
        hit = [n for n in names if n in kbs]
        if not hit:
            continue
        saved = {kb.name: kb.value for kb in kbs}
        for kb in kbs:
            kb.value = 0.0
        _upd()
        dg = bpy.context.evaluated_depsgraph_get()
        e0 = ob.evaluated_get(dg)
        m0 = e0.to_mesh()
        base = [ob.matrix_world @ v.co for v in m0.vertices]
        e0.to_mesh_clear()
        for n in hit:
            kbs[n].value = 1.0
        _upd()
        dg = bpy.context.evaluated_depsgraph_get()
        e1 = ob.evaluated_get(dg)
        m1 = e1.to_mesh()
        moved = [(ob.matrix_world @ v.co, (ob.matrix_world @ v.co - base[i]).length) for i, v in enumerate(m1.vertices)]
        e1.to_mesh_clear()
        for kb in kbs:
            kb.value = saved[kb.name]
        _upd()
        mx = max((d for _, d in moved), default=0.0)
        if mx > 1e-5:
            pts += [p for p, d in moved if d >= frac * mx]
    if not pts:
        return None
    return sum(pts, Vector()) / len(pts)



ANCHOR_EMIT = {"default": 0.18, "SKIN": 0.28, "EYE": 0.55, "FACE": 0.55}


def light_unlit(objs, emit=None):
    """VRoid/VRM materials import as glTF UNLIT: emission to camera rays, transparent to every other ray. Such an
    anchor ignores the studio's lights, casts no shadow and bounces nothing (flat, pasted-in, blown-out whites).
    Rebuild each unlit material as a lit Principled BSDF on the same texture plus a small share of the original
    emission (more on eyes and face lines so the anime read survives). NEWS_ANCHOR_UNLIT=1 keeps the import as is."""
    import os
    if os.environ.get("NEWS_ANCHOR_UNLIT") == "1":
        return 0
    emit = dict(ANCHOR_EMIT, **(emit or {}))
    done = set()
    for o in objs:
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if m is None or m.name in done or not m.use_nodes:
                continue
            nt = m.node_tree
            ems = [n for n in nt.nodes if n.type == "EMISSION"]
            if not ems or any(n.type == "BSDF_PRINCIPLED" for n in nt.nodes):
                continue
            em = ems[0]
            col = em.inputs["Color"]
            src = col.links[0].from_socket if col.is_linked else None
            out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
            if out is None:
                continue
            pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
            pb.inputs["Roughness"].default_value = 0.62
            pb.inputs["Specular IOR Level"].default_value = 0.25
            if src is not None:
                nt.links.new(src, pb.inputs["Base Color"])
            else:
                pb.inputs["Base Color"].default_value = col.default_value
            up = m.name.upper()
            k = next((v for key, v in emit.items() if key != "default" and key in up), emit["default"])
            em.inputs["Strength"].default_value = k
            add = nt.nodes.new("ShaderNodeAddShader")
            nt.links.new(pb.outputs[0], add.inputs[0])
            nt.links.new(em.outputs[0], add.inputs[1])
            nt.links.new(add.outputs[0], out.inputs["Surface"])
            done.add(m.name)
    print("ANCHOR-LIT", len(done), "unlit materials relit")
    return len(done)


def seat_anchor(sc, path, seat="anchor1", desk_h=0.8, strict=True, desk_eye=DESK_EYE):
    pre = precheck(path, strict)
    new = import_mesh(sc, path)
    # a GLB that ships a clip (Meshy: 'Armature|clip0|baselayer') would replay it on every frame change and undo the
    # seated pose (arms back in the rest T, floating over the desk): drop imported animation; the bake keys its own
    for o in new:
        o.animation_data_clear()
        sk = getattr(getattr(o, "data", None), "shape_keys", None)
        if sk is not None:
            sk.animation_data_clear()
    light_unlit(new)
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    sx, sy = SEATS[seat]
    holder = bpy.data.objects.new(f"anchor_{seat}", None)
    sc.collection.objects.link(holder)
    for r in [o for o in new if o.parent is None]:
        r.parent = holder
    _upd()
    z0, z1 = bbox_z(new)
    height = z1 - z0
    scale = 1.65 / height if (height < 1.2 or height > 2.1) else 1.0
    holder.scale = (scale, scale, scale)
    holder.location = (sx, sy, -z0 * scale)
    _upd()
    if arm is not None:
        pose_seated(arm)
    faces = [o for o in new if o.type == "MESH" and o.data.shape_keys and not o.hide_render]
    face, chk = FX.bind_meshes(faces, arm)
    print("FACECHECK", json.dumps(chk))
    if strict and chk["level"] == "fail":
        raise AnchorRefused(f"ANCHOR REFUSED: {path} cannot express after binding ({chk['missingCore']})")

    def measure():
        blink = [n for c in ("blinkL", "blinkR") for n, _ in face["bound"].get(c, [])]
        mouth_names = [n for n, _ in (face["bound"].get("open") or face["bound"].get("aa") or [])]
        e = shape_centroid(faces, blink)
        m = shape_centroid(faces, mouth_names)
        src = "shapes"
        if e is None:
            hd = bone(arm, "head")
            eyes = [b for b in arm.pose.bones if "faceeye" in b.name.lower() or b.name.lower() in ("lefteye", "righteye")] if arm else []
            e = (sum((wpos(arm, b) for b in eyes), Vector()) / len(eyes)) if eyes else \
                (wpos(arm, hd) + Vector((0, 0, 0.07)) if hd else Vector((sx, sy, 1.2)))
            src = "bones"
        if m is None:
            m = e - Vector((0, 0, 0.075))
        return e, m, src
    eye, mouth, src = measure()
    holder.location.z += (desk_h + desk_eye) - eye.z         # eyes on the newsroom eye-line; the seat follows
    _upd()
    if arm is not None:
        place_hands(arm, sx, desk_h)
    eye, mouth, src = measure()
    head_top = bbox_z(new)[1]
    hips = bone(arm, "hips")
    hip_z = wpos(arm, hips).z if hips is not None else eye.z - 0.6
    eye_base = {}
    gb = face.get("gaze_bones")
    if gb and arm is not None:
        for n in (gb["left"], gb["right"]):
            pb = arm.pose.bones.get(n)
            if pb is not None:
                pb.rotation_mode = "QUATERNION"
                eye_base[n] = pb.rotation_quaternion.copy()
    a = {"holder": holder, "arm": arm, "faces": faces, "face": face, "check": chk, "precheck": pre,
         "eye": eye.z, "mouth": mouth.z, "head_top": head_top, "eye_xyz": tuple(eye), "mouth_xyz": tuple(mouth), "measured_by": src,
         "height": height * scale, "scale": scale, "seat_h": max(0.4, min(0.8, hip_z - 0.08)), "eye_base": eye_base,
         "objects": new, "seat": seat, "path": str(path)}
    print("ANCHOR", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in a.items()
                                if k in ("eye", "mouth", "head_top", "height", "scale", "seat_h", "measured_by", "path")}))
    return a


def pose_seated(arm):
    """Thighs forward, shins down, arms hanging (rig-agnostic aims); the IK pass places the wrists later."""
    for side in ("L", "R"):
        ul, ll, ft = bone(arm, f"upperLeg.{side}"), bone(arm, f"lowerLeg.{side}"), bone(arm, f"foot.{side}")
        aim(arm, ul, (0.0, -1.0, -0.06), end=ll)
        aim(arm, ll, (0.0, -0.12, -1.0), end=ft)
    for side, s in (("L", 1.0), ("R", -1.0)):
        up, lo = bone(arm, f"upperArm.{side}"), bone(arm, f"lowerArm.{side}")
        carry = [arm.pose.bones.get(f"J_Aim_{side}_Shoulder"), arm.pose.bones.get(f"J_Aim_{side}_TopsUpperArm")]
        aim(arm, up, (0.12 * s, -0.25, -1.0), carry, end=lo)


def place_hands(arm, sx, desk_h):
    """Two-bone IK: each wrist on the desk top in front of the anchor, a little inside the shoulders, elbows out."""
    for side in ("L", "R"):
        up, lo, hand = bone(arm, f"upperArm.{side}"), bone(arm, f"lowerArm.{side}"), bone(arm, f"hand.{side}")
        if up is None or lo is None or hand is None:
            continue
        S, E, W = wpos(arm, up), wpos(arm, lo), wpos(arm, hand)
        l1, l2 = (E - S).length, (W - E).length
        tgt = Vector((S.x + (sx - S.x) * 0.3, S.y - min(0.42, (l1 + l2) * 0.78), desk_h + 0.045))
        if (tgt - S).length > (l1 + l2) * 0.97:
            tgt = S + (tgt - S).normalized() * (l1 + l2) * 0.97
        pole = S + Vector((1.0 if S.x > sx else -1.0, 0.4, -1.0))
        Eg = two_bone(S, l1, l2, tgt, pole)
        carry = [arm.pose.bones.get(f"J_Aim_{side}_Shoulder"), arm.pose.bones.get(f"J_Aim_{side}_TopsUpperArm")]
        aim(arm, up, Eg - S, carry, end=lo)
        aim(arm, lo, tgt - wpos(arm, lo), end=hand)
