#!/usr/bin/env python3
"""Validate a venue JSON against freaktown.venue.v1 + registry + physics.

Usage: /usr/bin/python3 scripts/validate_venue.py <venue.json>
Checks: schema shape/types/ranges, size-class bounds, marks inside room,
props in registry, light temps, camera counts, crowd capacity math,
budgets. Exit 0 = shippable. No deps, stdlib only.
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((BASE / "docs" / "VENUE-SCHEMA.json").read_text())

SIZE_BOUNDS = {
    "S": {"room": (12, 9, 4.0), "capacity": 60, "parses": 3, "glb_mb": 30},
    "M": {"room": (20, 16, 6), "capacity": 250, "parses": 5, "glb_mb": 80},
    "L": {"room": (40, 30, 12), "capacity": 2000, "parses": 8, "glb_mb": 200},
}


def load_registry():
    reg = {}
    p = BASE / "docs" / "VENUE-PROPS.md"
    if not p.exists():
        return reg
    cur = None
    for line in p.read_text().splitlines():
        if line.startswith("### "):
            cur = line[4:].strip().split()[0]
            reg[cur] = True
    return reg


def err(out, msg):
    out.append(msg)


def main():
    v = json.loads(Path(sys.argv[1]).read_text())
    bad = []
    for k in SCHEMA["required"]:
        if k not in v:
            err(bad, f"missing: {k}")
    if bad:
        print("INVALID\n" + "\n".join(f"  - {m}" for m in bad))
        return 1
    size = v.get("size")
    if size not in SIZE_BOUNDS:
        err(bad, f"size must be S/M/L, got {size!r}")
        bounds = SIZE_BOUNDS["S"]
    else:
        bounds = SIZE_BOUNDS[size]
    r = v.get("room", {})
    for ax, key, lim in (("w", "w", bounds["room"][0]), ("d", "d", bounds["room"][1]),
                         ("h", "h", bounds["room"][2])):
        if not isinstance(r.get(key), (int, float)) or not (0 < r[key] <= lim):
            err(bad, f"room.{key} must be 0..{lim} for size {size}")
    for m in v.get("marks", []):
        x, y, z = m.get("pos", [None] * 3)
        if not all(isinstance(c, (int, float)) for c in (x, y, z)):
            err(bad, f"mark {m.get('id')}: bad pos")
        elif not (-r.get("w", 0) / 2 <= x <= r.get("w", 0) / 2 and
                  0 <= y <= r.get("h", 99) and -r.get("d", 0) <= z <= r.get("d", 0)):
            err(bad, f"mark {m.get('id')}: outside room")
    reg = load_registry()
    for pr in v.get("props", []):
        if pr.get("id") not in reg:
            err(bad, f"prop {pr.get('id')!r} not in registry")
        if pr.get("pack", "base") not in ("base", "band", "judging", "custom"):
            err(bad, f"prop {pr.get('id')}: bad pack")
    rig = v.get("light_rig", {})
    for name in ("house", "spot"):
        li = rig.get(name, {})
        if not (1800 <= li.get("temp_k", 0) <= 8000):
            err(bad, f"light {name}: temp_k 1800..8000")
        if not (0 <= li.get("level", -1) <= 1):
            err(bad, f"light {name}: level 0..1")
    for w in rig.get("washes", [])[:5]:
        if not (1800 <= w.get("temp_k", 0) <= 8000):
            err(bad, "wash: temp_k 1800..8000")
    cams = v.get("cameras", [])
    if not (1 <= len(cams) <= 8):
        err(bad, "cameras: 1..8")
    crowd = v.get("crowd", {})
    zoned = sum(z.get("count", 0) for z in crowd.get("zones", []))
    if crowd.get("capacity", 0) > bounds["capacity"]:
        err(bad, f"capacity {crowd.get('capacity')} exceeds size {size}")
    if zoned != crowd.get("capacity"):
        err(bad, f"zones sum {zoned} != capacity {crowd.get('capacity')}")
    b = v.get("budgets", {})
    if b.get("glb_mb", 0) > bounds["glb_mb"] or b.get("glb_mb", 0) < 1:
        err(bad, f"glb_mb within 1..{bounds['glb_mb']} for size {size}")
    if b.get("parses", 0) > bounds["parses"] or b.get("parses", 0) < 1:
        err(bad, f"parses within 1..{bounds['parses']} for size {size}")
    if not v.get("glb", {}).get("sha256"):
        err(bad, "glb.sha256 required (hash-pin, never latest)")
    ac = v.get("acoustics", {})
    if not (0.2 <= ac.get("rt60", 0) <= 3.0):
        err(bad, "acoustics.rt60 0.2..3.0")
    if not (0 <= ac.get("warmth", -1) <= 1):
        err(bad, "acoustics.warmth 0..1")
    if not (-24 <= ac.get("bed_db", -99) <= 0):
        err(bad, "acoustics.bed_db -24..0")
    ph = v.get("physics", {})
    if not (0.5 <= ph.get("decay", 0) <= 0.99):
        err(bad, "physics.decay 0.5..0.99")
    if not (0.02 <= ph.get("laugh_gain", 0) <= 0.5):
        err(bad, "physics.laugh_gain 0.02..0.5")
    if not (0 <= ph.get("resist_start", -1) <= 1):
        err(bad, "physics.resist_start 0..1")
    if bad:
        print("INVALID\n" + "\n".join(f"  - {m}" for m in bad))
        return 1
    print(f"VALID venue {v.get('id')} ({size}): "
          f"{len(v.get('marks', []))} marks, {len(v.get('props', []))} props, "
          f"{crowd.get('capacity')} seats, {len(cams)} cameras")
    return 0


if __name__ == "__main__":
    sys.exit(main())
