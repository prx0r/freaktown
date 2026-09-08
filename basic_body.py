#!/usr/bin/env python3
"""FREAK BASIC — guaranteed $0 instant offline bodies. No provider, no queue.

One parametric blocky humanoid, species presets for proportions/colors/
accessories, deterministic per (species, name, seed). Emits a RIGGED GLB
with a real skeleton + a jawOpen morph target, pre-normalized (feet at
y=0, ~1.6 units tall, faces +Z). The stage bobs it procedurally and drives
jawOpen from the analyser — known rig, known motion, known lipsync.

Pure stdlib. If this file runs, bodies exist. That is the whole point.
"""

import hashlib
import math
import random
import struct

# joint order = skin joint indices
JOINTS = ["hips", "spine", "head",
          "shL", "elL", "shR", "elR",
          "hipL", "kneeL", "hipR", "kneeR"]

# relative translations (parent -> joint), bind pose
LOCAL_T = {
    "hips": (0.0, 0.95, 0.0),
    "spine": (0.0, 0.15, 0.0),
    "head": (0.0, 0.22, 0.0),
    "shL": (-0.27, 0.08, 0.0), "elL": (-0.05, -0.26, 0.0),
    "shR": (0.27, 0.08, 0.0), "elR": (0.05, -0.26, 0.0),
    "hipL": (-0.11, -0.06, 0.0), "kneeL": (0.0, -0.42, 0.0),
    "hipR": (0.11, -0.06, 0.0), "kneeR": (0.0, -0.42, 0.0),
}
PARENT = {"spine": "hips", "head": "spine",
          "shL": "hips", "elL": "shL", "shR": "hips", "elR": "shR",
          "hipL": "hips", "kneeL": "hipL", "hipR": "hips", "kneeR": "hipL"}

SPECIES = {
    "human":   {"head": 1.0, "body": 1.0, "leggy": 1.0,
                "palette": [(0.85, 0.62, 0.45), (0.20, 0.25, 0.65), (0.12, 0.12, 0.14)],
                "hat": 0.25, "glasses": 0.2},
    "goblin":  {"head": 1.35, "body": 0.8, "leggy": 0.8,
                "palette": [(0.35, 0.65, 0.30), (0.45, 0.30, 0.15), (0.10, 0.10, 0.10)],
                "hat": 0.4, "glasses": 0.1},
    "robot":   {"head": 0.9, "body": 1.1, "leggy": 1.0,
                "palette": [(0.55, 0.58, 0.62), (0.90, 0.30, 0.15), (0.05, 0.08, 0.12)],
                "hat": 0.0, "glasses": 0.5},
    "dog":     {"head": 1.15, "body": 0.9, "leggy": 0.75,
                "palette": [(0.60, 0.42, 0.25), (0.85, 0.80, 0.70), (0.08, 0.06, 0.05)],
                "hat": 0.2, "glasses": 0.1},
    "bird":    {"head": 1.25, "body": 0.75, "leggy": 1.15,
                "palette": [(0.55, 0.55, 0.60), (0.95, 0.75, 0.20), (0.10, 0.10, 0.12)],
                "hat": 0.5, "glasses": 0.15},
    "blob":    {"head": 1.5, "body": 1.2, "leggy": 0.5,
                "palette": [(0.45, 0.75, 0.85), (0.95, 0.45, 0.65), (0.08, 0.08, 0.10)],
                "hat": 0.15, "glasses": 0.3},
    "object":  {"head": 1.0, "body": 1.0, "leggy": 0.9,
                "palette": [(0.70, 0.70, 0.72), (0.15, 0.55, 0.85), (0.10, 0.10, 0.10)],
                "hat": 0.1, "glasses": 0.35},
    "monster": {"head": 1.2, "body": 1.15, "leggy": 0.9,
                "palette": [(0.50, 0.25, 0.65), (0.20, 0.70, 0.30), (0.05, 0.05, 0.05)],
                "hat": 0.3, "glasses": 0.05},
}

SPECIES_KEYS = {"dog": "dog", "pup": "dog", "hound": "dog",
                "bird": "bird", "pigeon": "bird", "crow": "bird",
                "parrot": "bird", "moth": "bird",
                "robot": "robot", "droid": "robot", "toaster": "object",
                "roomba": "object", "lamp": "object", "cone": "object",
                "goblin": "goblin", "orc": "goblin", "monster": "monster",
                "blob": "blob", "slime": "blob", "ghost": "blob"}


def species_key(species: str, premise: str = "") -> str:
    text = f"{species} {premise}".lower()
    for k, v in SPECIES_KEYS.items():
        if k in text:
            return v
    return "human"


def _world(joint: str) -> tuple:
    x, y, z = 0.0, 0.0, 0.0
    chain = []
    j = joint
    while j:
        chain.append(j)
        j = PARENT.get(j)
    for j in reversed(chain):
        tx, ty, tz = LOCAL_T[j]
        x += tx
        y += ty
        z += tz
    return (x, y, z)


def _box(center, size):
    cx, cy, cz = center
    sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
    return [(cx + dx, cy + dy, cz + dz)
            for dx in (-sx, sx) for dy in (-sy, sy) for dz in (-sz, sz)]


def _box_indices(base):
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 2, 6, 4),
             (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6)]
    idx = []
    for a, b, c, d in quads:
        idx += [base + a, base + b, base + c, base + a, base + c, base + d]
    return idx


def build(species: str = "human", name: str = "", seed: int = 0) -> tuple[bytes, dict]:
    """Returns (glb_bytes, caps). caps matches _sniff_glb shape + profile."""
    rng = random.Random(hashlib.sha256(
        f"{species}|{name}|{seed}".encode()).hexdigest())
    key = species_key(species, name)
    spec = SPECIES[key]
    skin, accent, dark = spec["palette"]
    hs, bs = spec["head"], spec["body"]

    hx, hy, hz = _world("head")
    head_c = (hx, hy + 0.13 * hs, hz)
    head_s = (0.30 * hs, 0.32 * hs, 0.28 * hs)

    parts = []  # (verts, joint, material, jaw_flags)
    # torso
    parts.append((_box((0, 1.02, 0), (0.42 * bs, 0.48 * bs, 0.24 * bs)),
                  "spine", 0, [False] * 8))
    # head (jaw = bottom 4 verts: dy<0)
    hv = _box(head_c, head_s)
    jaw = [v[1] < head_c[1] for v in hv]
    parts.append((hv, "head", 0, jaw))
    # eyes
    ex = 0.075 * hs
    for sx in (-1, 1):
        parts.append((_box((sx * ex, head_c[1] + 0.03, head_c[2] + head_s[2] / 2 + 0.005),
                           (0.05, 0.06, 0.02)), "head", 2, [False] * 8))
    # arms
    for side, sh, el in (("L", "shL", "elL"), ("R", "shR", "elR")):
        sx, sy, sz = _world(sh)
        parts.append((_box((sx, sy - 0.14, sz), (0.11, 0.30, 0.11)), sh, 1, [False] * 8))
        fx, fy, fz = _world(el)
        parts.append((_box((fx, fy - 0.13, fz), (0.09, 0.28, 0.09)), el, 1, [False] * 8))
    # legs
    for side, hip, knee in (("L", "hipL", "kneeL"), ("R", "hipR", "kneeR")):
        tx, ty, tz = _world(hip)
        parts.append((_box((tx, ty - 0.20, tz), (0.14, 0.42, 0.14)), hip, 1, [False] * 8))
        kx, ky, kz = _world(knee)
        parts.append((_box((kx, (ky + 0.0) / 2, kz), (0.12, ky, 0.12)), knee, 1, [False] * 8))
    # hat?
    if rng.random() < spec["hat"]:
        hy_top = head_c[1] + head_s[1] / 2
        parts.append((_box((head_c[0], hy_top + 0.02, head_c[2]), (0.34 * hs, 0.04, 0.34 * hs)),
                      "head", 1, [False] * 8))
        parts.append((_box((head_c[0], hy_top + 0.10, head_c[2]), (0.20 * hs, 0.14, 0.20 * hs)),
                      "head", 1, [False] * 8))
    # glasses?
    if rng.random() < spec["glasses"]:
        parts.append((_box((head_c[0], head_c[1] + 0.03, head_c[2] + head_s[2] / 2 + 0.01),
                           (0.24 * hs, 0.03, 0.02)), "head", 2, [False] * 8))

    mats = [skin, accent, dark]
    # assemble buffers: per material mesh
    meshes = []
    bin_blobs = []
    accessors = []
    buffer_views = []

    def add_blob(data: bytes):
        off = sum(len(b) for b in bin_blobs)
        pad = (-len(data)) % 4
        bin_blobs.append(data + b"\x00" * pad)
        return off, len(data)

    def add_view(off, ln):
        buffer_views.append({"buffer": 0, "byteOffset": off, "byteLength": ln})
        return len(buffer_views) - 1

    def add_acc(view, comp, count, typ, mn=None, mx=None):
        a = {"bufferView": view, "componentType": comp, "count": count, "type": typ}
        if mn is not None:
            a["min"] = list(mn)
            a["max"] = list(mx)
        accessors.append(a)
        return len(accessors) - 1

    joint_idx = {j: i for i, j in enumerate(JOINTS)}
    world = {j: _world(j) for j in JOINTS}
    ibm = []
    for j in JOINTS:
        x, y, z = world[j]
        ibm += [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -x, -y, -z, 1]
    off, ln = add_blob(struct.pack(f"<{len(ibm)}f", *ibm))
    ibm_acc = add_acc(add_view(off, ln), 5126, len(JOINTS), "MAT4")

    for mi, mat in enumerate(mats):
        verts, joints, jawflags, indices = [], [], [], []
        for (vv, joint, m2, jf) in parts:
            if m2 != mi:
                continue
            base = len(verts)
            verts.extend(vv)
            joints.extend([joint] * len(vv))
            jawflags.extend(jf)
            indices.extend(_box_indices(base))
        if not verts:
            continue
        flat = [c for v in verts for c in v]
        mn = [min(flat[0::3]), min(flat[1::3]), min(flat[2::3])]
        mx = [max(flat[0::3]), max(flat[1::3]), max(flat[2::3])]
        nrm = []
        cx, cy, cz = sum(flat[0::3]) / len(verts), sum(flat[1::3]) / len(verts), sum(flat[2::3]) / len(verts)
        for v in verts:
            dx, dy, dz = v[0] - cx, v[1] - cy, v[2] - cz
            l = math.sqrt(dx * dx + dy * dy + dz * dz) or 1
            nrm += [dx / l, dy / l, dz / l]
        jarr = [joint_idx[j] for j in joints]
        warr = [1.0, 0.0, 0.0, 0.0] * len(verts)
        o1, l1 = add_blob(struct.pack(f"<{len(flat)}f", *flat))
        o2, l2 = add_blob(struct.pack(f"<{len(nrm)}f", *nrm))
        o3, l3 = add_blob(struct.pack(f"<{len(jarr)*4}B", *[x for j in jarr for x in (j, 0, 0, 0)]))
        o4, l4 = add_blob(struct.pack(f"<{len(warr)}f", *warr))
        o5, l5 = add_blob(struct.pack(f"<{len(indices)}H", *indices))
        prim = {
            "attributes": {
                "POSITION": add_acc(add_view(o1, l1), 5126, len(verts), "VEC3", mn, mx),
                "NORMAL": add_acc(add_view(o2, l2), 5126, len(verts), "VEC3"),
                "JOINTS_0": add_acc(add_view(o3, l3), 5121, len(verts), "VEC4"),
                "WEIGHTS_0": add_acc(add_view(o4, l4), 5126, len(verts), "VEC4"),
            },
            "indices": add_acc(add_view(o5, l5), 5123, len(indices), "SCALAR"),
            "material": mi,
        }
        targets = None
        if any(jawflags):
            disp = []
            for v, jf in zip(verts, jawflags):
                disp += [(0.0, -0.07, 0.01) if jf else (0.0, 0.0, 0.0)]
            flat_d = [c for v in disp for c in v]
            od, ld = add_blob(struct.pack(f"<{len(flat_d)}f", *flat_d))
            prim["targets"] = [{"POSITION": add_acc(add_view(od, ld), 5126, len(verts), "VEC3")}]
            targets = ["jawOpen"]
        mesh = {"primitives": [prim], "name": f"basic_{mi}"}
        if targets:
            mesh["extras"] = {"targetNames": targets}
        meshes.append(mesh)

    # nodes: meshes + joints
    nodes = []
    mesh_nodes = []
    for mi in range(len(meshes)):
        mesh_nodes.append(len(nodes))
        nodes.append({"mesh": mi, "skin": 0, "name": f"part_{mi}"})
    jnode = {}
    for j in JOINTS:
        jnode[j] = len(nodes)
        nd = {"name": j, "translation": list(LOCAL_T[j])}
        ch = [jnode[c] for c in JOINTS if PARENT.get(c) == j and c in jnode]
        if ch:
            nd["children"] = ch
        nodes.append(nd)
    roots = mesh_nodes + [jnode["hips"]]
    doc = {
        "asset": {"version": "2.0", "generator": "freak-basic-v1"},
        "scenes": [{"nodes": roots}],
        "nodes": nodes,
        "meshes": meshes,
        "skins": [{"joints": [jnode[j] for j in JOINTS],
                   "skeleton": jnode["hips"],
                   "inverseBindMatrices": ibm_acc}],
        "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [r, g, b, 1.0],
                                                "metallicFactor": 0.1,
                                                "roughnessFactor": 0.85},
                       "name": f"mat_{i}"} for i, (r, g, b) in enumerate(mats)],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": sum(len(b) for b in bin_blobs)}],
    }
    js = json_dumps(doc).encode()
    while len(js) % 4:
        js += b" "
    blob = b"".join(bin_blobs)
    total = 12 + 8 + len(js) + 8 + len(blob)
    out = struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(blob), 0x004E4942) + blob
    caps = {"rigged": True, "has_skin": True, "joint_count": len(JOINTS),
            "humanoid_skin": True, "has_morph_targets": True,
            "facial_morphs": 1, "lipsync": True, "morph_names": ["jawOpen"],
            "profile": "basic", "species_key": key}
    return bytes(out), caps


def json_dumps(d) -> str:
    import json as _j
    return _j.dumps(d, separators=(",", ":"))


if __name__ == "__main__":
    import sys
    blob, caps = build(sys.argv[1] if len(sys.argv) > 1 else "pigeon",
                       sys.argv[2] if len(sys.argv) > 2 else "Test")
    open("basic_test.glb", "wb").write(blob)
    print(f"wrote basic_test.glb ({len(blob)} bytes) {caps}")
