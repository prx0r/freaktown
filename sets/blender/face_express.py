"""Expressive face for the Blender bake: the Python mirror of packages/stage-runtime/src/face/expressive.ts.

Both read packages/stage-runtime/src/face/expressive-map.json, so a channel weight drives the same shapes with the same
gains in the three.js stage and in a Cycles render (golden parity: tests/fixtures/face-expressive-golden.json, checked
by tests/contract/test_face_expressive.py and packages/stage-runtime/tests/expressive.test.ts).

Pure functions (no bpy): norm_name, bind_rig, check_face, channels_from_state, shapes_for, side_mask.
Blender helpers (bpy imported lazily): bind_meshes (generates the one-sided shapes, raises slider_max to max_gain),
apply_channels (sets + optionally keys shape values and eye bones).

    python3 sets/blender/face_express.py check static/avatars/default-v1.vrm      # the channel check on a GLB/VRM
"""
import json, math, pathlib, struct, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "packages/stage-runtime/src/face/expressive-map.json"
MAP = json.loads(MAP_PATH.read_text())
CHANNELS = list(MAP["channels"])
MAX_GAIN = MAP["max_gain"]
VIS = ("aa", "ih", "ou", "ee", "oh")


def norm_name(name):
    s = name.strip()
    cut = max(s.rfind("."), s.rfind("|"), s.rfind(":"))
    if 0 <= cut < len(s) - 1:
        s = s[cut + 1:]
    i = s.lower().find("fcl_")         # VRoid beta exports: "M_F00_000_00_Fcl_MTH_A" -> "Fcl_MTH_A"
    if i > 0:
        s = s[i:]
    return "".join(ch for ch in s.lower() if ch.isascii() and ch.isalnum())


def bind_rig(names, bones=(), force=None):
    """{rig, bound: channel -> [[name, w]], generate: [[new, src, side, gain]], gaze_bones, gaze_morphs}"""
    have = {}
    for n in names:
        have.setdefault(norm_name(n), n)
    bone_set = {norm_name(b) for b in bones}
    best, best_score = {"rig": None, "bound": {}, "generate": [], "gaze_bones": None, "gaze_morphs": {}}, -1
    for rid in ([force] if force else list(MAP["rigs"])):
        spec = MAP["rigs"][rid]
        hits = sum(1 for d in spec["detect"] if norm_name(d) in have)
        gen, virtual = [], dict(have)
        for nm, g in spec.get("generate", {}).items():
            src = have.get(norm_name(g["from"]))
            if src and norm_name(nm) not in have:
                gen.append([nm, src, g["side"], g["gain"]])
                virtual[norm_name(nm)] = nm
        bound = {}
        for ch, targets in spec["shapes"].items():
            t = [[virtual[norm_name(n)], w] for n, w in targets if norm_name(n) in virtual]
            if t:
                bound[ch] = t
        gm = {}
        for d, targets in spec.get("gaze_morphs", {}).items():
            t = [[have[norm_name(n)], w] for n, w in targets if norm_name(n) in have]
            if t:
                gm[d] = t
        gb = spec.get("gaze_bones")
        gb = gb if gb and norm_name(gb["left"]) in bone_set and norm_name(gb["right"]) in bone_set else None
        score = hits * 100 + len(bound)
        if hits >= min(2, len(spec["detect"])) and score > best_score:
            best_score = score
            best = {"rig": rid, "bound": bound, "generate": gen, "gaze_bones": gb, "gaze_morphs": gm}
    return best


def check_face(names, bones=(), gaze_by_head=False):
    b = bind_rig(names, bones)
    has = lambda c: c in b["bound"]
    groups = {"mouth": any(has(c) for c in ("open",) + VIS), "blink": has("blinkL") or has("blinkR"),
              "smile": has("smileL") or has("smileR"), "brow": has("browUp") or has("browDown") or has("browSad")}
    missing = [g for g in MAP["check"]["core"] if not groups[g]]
    same = has("smileL") and has("smileR") and b["bound"]["smileL"] == b["bound"]["smileR"]
    distinct = {json.dumps(sorted(n for n, _ in b["bound"][c])) for c in VIS if has(c)}
    ext = {"visemes": all(has(c) for c in VIS) and len(distinct) >= 3, "smileSides": has("smileL") and has("smileR") and not same,
           "frown": has("frown"), "browSad": has("browSad"), "squint": has("squint"), "eyeWide": has("eyeWide"),
           "gaze": bool(b["gaze_bones"]) or len(b["gaze_morphs"]) >= 2 or gaze_by_head}
    warnings = [f"no {k}" for k in MAP["check"]["extended"] if not ext[k]]
    return {"rig": b["rig"], "level": "fail" if missing else "warn" if warnings else "ok",
            "channels": list(b["bound"]), "missingCore": missing, "warnings": warnings,
            "generated": [g[0] for g in b["generate"]]}


def apply_overrides(b, face=None, names=()):
    """A cast file's per-character face overrides on a binding (sets/blender/news_cast/<id>.json "face"):
    "shapes": {channel: [[shape, w], ...]} replaces a channel's targets (names matched like bind_rig: only shapes the
    mesh has; pass names= every shape key name), then "gains": {channel: k} scales every target weight of that channel. Returns a new binding."""
    if not face:
        return b
    out = dict(b, bound={c: [list(t) for t in ts] for c, ts in b["bound"].items()})
    avail = {norm_name(n): n for ts in b["bound"].values() for n, _ in ts}
    for n in names:
        avail.setdefault(norm_name(n), n)
    for c, targets in (face.get("shapes") or {}).items():
        t = [[avail[norm_name(n)], float(w)] for n, w in targets if norm_name(n) in avail]
        if t:
            out["bound"][c] = t
    for c, k in (face.get("gains") or {}).items():
        if c in out["bound"]:
            out["bound"][c] = [[n, _r6(w * float(k))] for n, w in out["bound"][c]]
    return out


def _c01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _r6(x):
    return math.floor(x * 1e6 + 0.5) / 1e6      # == JS Math.round(x * 1e6) / 1e6


def channels_from_state(s):
    ch = {}

    def put(k, v):
        if v > 0:
            ch[k] = max(ch.get(k, 0.0), v)
    vis = s.get("visemes") or {}
    if any((vis.get(k) or 0) > 0 for k in VIS):
        for k in VIS:
            put(k, _c01(vis.get(k) or 0))
    else:
        put("open", _c01(s.get("open") or 0))
    emos = s.get("emotions") or {}
    for emo, mix in MAP["emotions"].items():
        e = _c01(emos.get(emo) or 0)
        if e > 0:
            for k, w in mix.items():
                put(k, e * w)
    for k in ("blinkL", "blinkR", "browUp", "browDown", "browSad", "squint"):
        put(k, _c01(s.get(k) or 0))
    sm = s.get("smirk") or 0
    if sm > 0:
        put("smileL", _c01(sm))
    if sm < 0:
        put("smileR", _c01(-sm))
    if s.get("speaking"):
        for k, f in MAP["speech"]["while_speaking"].items():
            if k in ch and k != "open":
                ch[k] *= f
    if ch.get("browUp") and ch.get("browDown"):
        if ch["browUp"] >= ch["browDown"]:
            ch["browDown"] *= 0.5
        else:
            ch["browUp"] *= 0.5
    if s.get("lookX"):
        ch["lookX"] = max(-1.0, min(1.0, s["lookX"]))
    if s.get("lookY"):
        ch["lookY"] = max(-1.0, min(1.0, s["lookY"]))
    return {k: _r6(ch[k]) for k in sorted(ch)}


def shapes_for(b, ch):
    out = {}
    for c, v in ch.items():
        if c in ("lookX", "lookY"):
            continue
        for n, w in b["bound"].get(c, []):
            out[n] = out.get(n, 0.0) + v * w
    gm = b.get("gaze_morphs", {})

    def g(d, v):
        for n, w in gm.get(d, []):
            out[n] = out.get(n, 0.0) + v * w
    lx, ly = ch.get("lookX", 0), ch.get("lookY", 0)
    if lx > 0: g("left", lx)
    if lx < 0: g("right", -lx)
    if ly > 0: g("up", ly)
    if ly < 0: g("down", -ly)
    return {k: _r6(max(0.0, min(MAX_GAIN, v))) for k, v in out.items()}


def side_mask(x, side, width=0.012):
    u = _c01(0.5 + (x if side == "L" else -x) / width)
    return u * u * (3 - 2 * u)


# ---- GLB / VRM inspection without Blender --------------------------------------------------------------------------
def glb_names(path):
    """(morph target names, node names) from a .glb/.vrm (glTF binary): extras.targetNames per mesh, VRM0/1 blend
    shape names are not needed (the raw morph names carry Fcl_* for VRoid)."""
    b = pathlib.Path(path).read_bytes()
    if b[:4] != b"glTF":
        raise SystemExit(f"{path}: not a glTF binary")
    n = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + n])
    names = []
    for m in j.get("meshes", []):
        tn = (m.get("extras") or {}).get("targetNames") or []
        if not tn:
            for p in m.get("primitives", []):
                tn = (p.get("extras") or {}).get("targetNames") or tn
        names += tn
    return names, [nd.get("name", "") for nd in j.get("nodes", [])]


# ---- Blender -------------------------------------------------------------------------------------------------------
def bind_meshes(meshes, arm=None, force=None, generate=True):
    """Bind Blender meshes with shape keys: generate the rig's one-sided shapes (same soft mask as the runtime), raise
    slider_max so gains up to max_gain work, and return (binding, check)."""
    names = [kb.name for ob in meshes for kb in ob.data.shape_keys.key_blocks]
    bones = [pb.name for pb in arm.pose.bones] if arm is not None else []
    b = bind_rig(names, bones, force)
    if generate:
        for nm, src, side, gain in b["generate"]:
            for ob in meshes:
                kbs = ob.data.shape_keys.key_blocks
                if src not in kbs or nm in kbs:
                    continue
                basis = ob.data.shape_keys.reference_key
                s = kbs[src]
                new = ob.shape_key_add(name=nm, from_mix=False)
                new.value = 0.0         # Blender 5.x adds a key at value 1.0: a generated smile would sit on the face
                for i, (bv, sv) in enumerate(zip(basis.data, s.data)):
                    m = side_mask(bv.co.x, side) * gain
                    new.data[i].co = bv.co + (sv.co - bv.co) * m
    names = [kb.name for ob in meshes for kb in ob.data.shape_keys.key_blocks]
    for ob in meshes:
        for kb in ob.data.shape_keys.key_blocks:
            kb.slider_max = max(kb.slider_max, MAX_GAIN)
    b = bind_rig(names, bones, force)
    return b, check_face(names, bones)


def apply_channels(meshes, b, ch, arm=None, frame=None, eye_base=None):
    """Write channel weights to shape keys (every bound shape, so nothing sticks) and aim the eye bones; key them
    at `frame` when given. eye_base: {bone name: rest quaternion} captured once."""
    from mathutils import Euler
    w = shapes_for(b, ch)
    allnames = {n for t in b["bound"].values() for n, _ in t}
    for ob in meshes:
        kbs = ob.data.shape_keys.key_blocks
        for n in allnames:
            if n in kbs:
                kbs[n].value = w.get(n, 0.0)
                if frame is not None:
                    kbs[n].keyframe_insert("value", frame=frame)
    gb = b.get("gaze_bones")
    if arm is not None and gb:
        yaw = math.radians(gb["yaw_deg"]) * ch.get("lookX", 0.0)
        pitch = math.radians(gb["pitch_deg"]) * ch.get("lookY", 0.0)
        for name in (gb["left"], gb["right"]):
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            pb.rotation_mode = "QUATERNION"
            base = (eye_base or {}).get(name)
            # bone-local axes of a VRoid eye after glTF import: Y along the bone (up), Z toward the face front
            q = Euler((-pitch, 0.0, yaw), "XYZ").to_quaternion()
            pb.rotation_quaternion = (base @ q) if base is not None else q
            if frame is not None:
                pb.keyframe_insert("rotation_quaternion", frame=frame)
    return w


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        rc = 0
        for p in sys.argv[2:]:
            names, nodes = glb_names(p)
            r = check_face(names, nodes)
            print(json.dumps({"file": p, **r}))
            rc |= r["level"] == "fail"
        sys.exit(rc)
    print(__doc__)
