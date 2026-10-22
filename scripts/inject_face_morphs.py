#!/usr/bin/env python3
"""inject_face_morphs.py — add jawOpen + blink morph targets to a rigged GLB.

SUPERSEDED by `npm run face:rig -- in.glb out.glb` (packages/stage-runtime/cli/face-rig.ts,
same generator the stage runs at load). This version translates the whole lower
face down (the lip line slides instead of parting) and names the blink `blink`.
Kept for reference; see docs/MESH-FACE-HOOKUP.md.

The stage's GlbAvatar is ONE facial engine for every body: it sniffs
morphTargetDictionary for names it knows (jawOpen/visemes/blink/emotions)
and drives them from the audio envelope and face channel. Meshy (and most
generators) emit geometry + a rig but ZERO morphs — so the engine has
nothing to grab and the mouth stays mute ("mouth: none", never a fake mouth).

This script makes any rigged GLB engine-compatible:
  - jawOpen : chin/lower-face verts (Head-bone-weighted) push down on the
              audio envelope -> the set actually talks
  - blink   : eyelid-weighted verts push down on the blink timer

Pure stdlib (struct + json): reads the glTF JSON chunk + BIN chunk, picks
vertices by Head-bone weight (JOINTS_0/WEIGHTS_0 — no transform math needed;
deltas live in POSITION space like every other morph target), appends the
delta accessors, and rewrites mesh.targets + extras.targetNames.

Usage:
  python3 inject_face_morphs.py in.glb out.glb [--no-blink]

Verified on the Meshy buddha rig: 24 joints, no morphs in -> jawOpen+blink
out; the stage reports mouthMode 'morph' and the mouth follows the set.wav
envelope.
"""
from __future__ import annotations

import json
import struct
import sys


def read_glb(path: str):
    d = open(path, "rb").read()
    magic, ver, total = struct.unpack("<4sII", d[:12])
    assert magic == b"glTF" and ver == 2, f"not a glTF2 binary: {magic!r}"
    off, js, binchunk = 12, None, None
    while off < len(d):
        clen, ctype = struct.unpack("<I4s", d[off:off + 8])
        body = d[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(body)
        elif ctype == b"BIN\x00":
            binchunk = bytearray(body)
        off += 8 + clen + ((4 - clen % 4) % 4)
    return js, binchunk


def write_glb(path: str, js: dict, binchunk: bytes) -> None:
    jb = json.dumps(js, separators=(",", ":")).encode()
    jb += b" " * ((4 - len(jb) % 4) % 4)
    bb = binchunk + b"\x00" * ((4 - len(binchunk) % 4) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(jb) + 8 + len(bb)))
        f.write(struct.pack("<I4s", len(jb), b"JSON") + jb)
        f.write(struct.pack("<I4s", len(bb), b"BIN\x00") + bb)


def accessor_bytes(js: dict, binchunk: bytes, idx: int):
    acc = js["accessors"][idx]
    bv = js["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    count = acc["count"]
    csz = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}[acc["componentType"]]
    stride = bv.get("byteStride") or ncomp * csz
    out = []
    for i in range(count):
        s = start + i * stride
        out.append(struct.unpack_from("<" + "f" * ncomp if acc["componentType"] == 5126
                                     else "B" * ncomp if acc["componentType"] == 5121
                                     else "H" * ncomp, binchunk, s))
    return acc, out


def append_accessor(js: dict, binchunk: bytearray, data: list, comp: int, ncomp: int, typ: str) -> int:
    """Append a tightly-packed float32 (or ubyte/ushort) accessor; returns its index."""
    fmt = {5126: "f", 5121: "B", 5123: "H"}[comp]
    raw = b"".join(struct.pack("<" + fmt * ncomp, *row) for row in data)
    while len(binchunk) % 4:
        binchunk += b"\x00"
    bvi = len(js.get("bufferViews", []))
    js.setdefault("bufferViews", []).append({
        "buffer": 0, "byteOffset": len(binchunk), "byteLength": len(raw),
    })
    binchunk += raw
    ai = len(js["accessors"])
    js["accessors"].append({
        "bufferView": bvi, "componentType": comp, "count": len(data), "type": typ,
    })
    if comp == 5126:  # POSITION/targets need min/max
        mins = [min(r[i] for r in data) for i in range(ncomp)]
        maxs = [max(r[i] for r in data) for i in range(ncomp)]
        js["accessors"][ai]["min"] = mins
        js["accessors"][ai]["max"] = maxs
    return ai


def inject(path_in: str, path_out: str, with_blink: bool = True) -> dict:
    js, binchunk = read_glb(path_in)
    assert js.get("meshes"), "no meshes"
    prim = js["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    for need in ("POSITION", "JOINTS_0", "WEIGHTS_0"):
        assert need in attrs, f"missing {need} — rig the mesh first"
    assert js.get("skins"), "no skin"

    head_idx = None
    skin = js["skins"][0]
    for j in skin["joints"]:
        n = js["nodes"][j]
        if re_search_head(n.get("name", "")):
            head_idx = skin["joints"].index(j)
            break
    assert head_idx is not None, "no Head bone in the skin"

    _, pos = accessor_bytes(js, binchunk, attrs["POSITION"])
    _, joints = accessor_bytes(js, binchunk, attrs["JOINTS_0"])
    acc_w, weights_raw = accessor_bytes(js, binchunk, attrs["WEIGHTS_0"])
    # WEIGHTS_0 may be normalized ubyte/ushort (value/255 or /65535)
    wmax = {5121: 255.0, 5123: 65535.0, 5126: 1.0}[acc_w["componentType"]]
    weights = [tuple(v / wmax for v in row) for row in weights_raw]
    n = len(pos)
    assert n == len(joints) == len(weights), "count mismatch"

    # head vertices: any meaningful weight on the Head joint
    hv = [i for i in range(n)
          if any(joints[i][k] == head_idx and weights[i][k] > 0.35 for k in range(4))]
    assert len(hv) > 100, f"head-weighted verts: {len(hv)} — bad rig weighting"
    xs = [pos[i][0] for i in hv]; ys = [pos[i][1] for i in hv]; zs = [pos[i][2] for i in hv]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    w, h, dp = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)

    # glTF forward = +Z. Mouth: front + lower-middle of the head cloud.
    mouth = (cx, cy - 0.28 * h, cz + 0.38 * dp)
    # Eyes: front + upper third, two x-clusters around ±0.22w of centre
    eyeL = (cx - 0.20 * w, cy + 0.20 * h, cz + 0.42 * dp)
    eyeR = (cx + 0.20 * w, cy + 0.20 * h, cz + 0.42 * dp)
    r_jaw, r_eye = 0.30 * max(w, dp), 0.16 * max(w, dp)

    def fall(p, c, r):
        d2 = sum((p[i] - c[i]) ** 2 for i in range(3))
        return max(0.0, 1.0 - d2 / (r * r))

    jaw_delta = [(0.0, 0.0, 0.0)] * n
    eye_ids = set()
    scale = -0.10 * h  # chin drops ~10% of head height fully flared
    for i in hv:
        p = pos[i]
        fj = fall(p, mouth, r_jaw)
        if fj > 0:
            jaw_delta[i] = (0.0, scale * fj, 0.0)
        fe = max(fall(p, eyeL, r_eye), fall(p, eyeR, r_eye))
        if fe > 0.35:
            eye_ids.add(i)
    moved_jaw = sum(1 for d in jaw_delta if d != (0.0, 0.0, 0.0))
    assert moved_jaw > 50, f"jaw region too small ({moved_jaw} verts)"

    targets = [{"POSITION": append_accessor(js, binchunk, jaw_delta, 5126, 3, "VEC3")}]
    names = ["jawOpen"]
    if with_blink and eye_ids:
        blink_delta = [(0.0, 0.0, 0.0)] * n
        bscale = -0.22 * h * 0.45  # lids close ~45% of their travel
        for i in eye_ids:
            p = pos[i]
            f = fall(p, eyeL, r_eye * 1.4) if abs(p[0] - eyeL[0]) < abs(p[0] - eyeR[0]) else fall(p, eyeR, r_eye * 1.4)
            blink_delta[i] = (0.0, bscale * f, 0.0)
        targets.append({"POSITION": append_accessor(js, binchunk, blink_delta, 5126, 3, "VEC3")})
        names.append("blink")

    prim["targets"] = targets
    js["meshes"][0]["extras"] = {**(js["meshes"][0].get("extras") or {}), "targetNames": names}
    # BIN chunk grew; existing bufferView offsets are untouched (append-only)
    write_glb(path_out, js, bytes(binchunk))
    return {"head_verts": len(hv), "jaw_verts": moved_jaw, "blink_verts": len(eye_ids),
            "targets": names, "head_bbox": [round(v, 2) for v in (w, h, dp)]}


def re_search_head(name: str) -> bool:
    import re
    return bool(re.search(r"head$|head_|:head|^head", name, re.I))


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    with_blink = "--no-blink" not in sys.argv
    print(json.dumps(inject(src, dst, with_blink), indent=1))
