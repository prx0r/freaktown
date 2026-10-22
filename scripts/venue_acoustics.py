#!/usr/bin/env python3
"""Venue acoustics from first principles (Sabine + Eyring + axial modes).

For a venue JSON: builds surface areas from room dims, assigns standard
absorption coefficients (500-1000Hz octave, published tables), adds the
audience as absorbers, and reports:

  RT60 Sabine  = 0.161 * V / A            (diffuse field assumption)
  RT60 Eyring  = 0.161 * V / (-S * ln(1 - A/S))   (better for dead rooms)
  Schroeder fs = 2000 * sqrt(RT60 / V)    (below fs, modes rule, not reverb)
  Axial modes  = c/2 * nx/Lx ... below 200Hz (room boom notes)

Material coefficients (Sabine α, ~1kHz, standard tables):
  painted brick 0.03, concrete 0.04, wood floor/stage 0.10,
  heavy curtain 0.55, wood bar/door 0.10, glass 0.05,
  seated person 0.45 m² each, empty fabric chair 0.15, table 0.05.

Per-venue material overrides live in MATERIAL_MAP below, keyed by
surface. Honest limits printed with every run: Sabine overestimates dead
rooms (trust Eyring there); both assume diffuse field (fails below fs);
warmth/bed_db remain engineered mappings, NOT physics (labeled).

Usage: /usr/bin/python3 scripts/venue_acoustics.py [venue.json ...]
  --apply writes rt60 (Eyring, rounded) + warmth estimate back into the JSON.
"""
import json
import math
import sys
from pathlib import Path

C = 343.0  # m/s

ALPHA = {
    "brick-painted": 0.03, "concrete": 0.04, "wood": 0.10,
    "curtain": 0.55, "bar-wood": 0.10, "glass": 0.05,
    "person": 0.45, "chair-fabric": 0.15, "table": 0.05,
    "ceiling-black": 0.05, "door": 0.10,
}

# surface fractions per venue id: (material, fraction of surface class)
# walls include curtains/doors implicitly via blended alpha (documented).
VENUES = {
    "cauldron": {
        "floor": [("concrete", 0.7), ("wood", 0.3)],
        "ceiling": [("ceiling-black", 1.0)],
        "walls": [("brick-painted", 0.72), ("curtain", 0.18), ("bar-wood", 0.10)],
        "seats": {"person": 40, "chair-fabric": 0, "table": 6},
    },
    "medium": {
        "floor": [("wood", 0.6), ("concrete", 0.4)],
        "ceiling": [("ceiling-black", 1.0)],
        "walls": [("brick-painted", 0.7), ("curtain", 0.2), ("door", 0.1)],
        "seats": {"person": 150, "chair-fabric": 60, "table": 8},
    },
    "red-curtain": {
        "floor": [("wood", 0.5), ("concrete", 0.5)],
        "ceiling": [("ceiling-black", 1.0)],
        "walls": [("brick-painted", 0.55), ("curtain", 0.35), ("door", 0.1)],
        "seats": {"person": 400, "chair-fabric": 150, "table": 0},
    },
}


def analyze(vid, v):
    r = v["room"]
    w, d, h = r["w"], r["d"], r["h"]
    V = w * d * h
    S_floor, S_ceil = w * d, w * d
    S_walls = 2 * (w * h + d * h)
    S = S_floor + S_ceil + S_walls
    M = VENUES.get(vid)
    if M is None:
        raise ValueError(f"no material map for {vid} (add to VENUE map)")
    A = (sum(a * ALPHA[m] for m, a in [(m, f * S_floor) for m, f in M["floor"]])
         + sum(a * ALPHA[m] for m, a in [(m, f * S_ceil) for m, f in M["ceiling"]])
         + sum(a * ALPHA[m] for m, a in [(m, f * S_walls) for m, f in M["walls"]]))
    seats = M["seats"]
    A += seats.get("person", 0) * ALPHA["person"]
    A += seats.get("chair-fabric", 0) * ALPHA["chair-fabric"]
    A += seats.get("table", 0) * ALPHA["table"]
    a_bar = A / S
    rt_sabine = 0.161 * V / A
    rt_eyring = 0.161 * V / (-S * math.log(max(1e-6, 1 - a_bar)))
    fs = 2000 * math.sqrt(rt_eyring / V)
    modes = []
    for nx in range(1, 4):
        for ax, L in (("x", w), ("y", h), ("z", d)):
            f = C / 2 * nx / L
            if f < 200:
                modes.append((round(f, 1), f"{ax}{nx}"))
    modes.sort()
    # warmth: low-frequency persistence proxy = Eyring RT scaled by
    # volume (big rooms hold lows) — ENGINEERED mapping, labeled as such.
    warmth = round(min(1.0, 0.3 + rt_eyring / 4.0), 2)
    return {"volume_m3": round(V, 1), "surface_m2": round(S, 1),
            "absorption_m2": round(A, 1), "alpha_bar": round(a_bar, 3),
            "rt60_sabine": round(rt_sabine, 2),
            "rt60_eyring": round(rt_eyring, 2),
            "schroeder_hz": round(fs, 0),
            "axial_modes": modes[:8], "warmth_engineered": warmth}


def main():
    paths = sys.argv[1:]
    apply = "--apply" in paths
    paths = [p for p in paths if p != "--apply"]
    if not paths:
        paths = ["docs/venues/cauldron.json", "docs/venues/medium.json",
                 "docs/venues/red-curtain.json"]
    for p in paths:
        v = json.loads(Path(p).read_text())
        try:
            r = analyze(v["id"], v)
        except ValueError as e:
            print(f"{p}: {e}")
            continue
        print(f"== {v['id']} ==")
        for k, val in r.items():
            print(f"  {k}: {val}")
        print("  limits: Sabine overestimates dead rooms (trust Eyring); "
              "diffuse-field math fails below Schroeder fs; warmth is engineered.")
        if apply:
            v.setdefault("acoustics", {})["rt60"] = r["rt60_eyring"]
            v["acoustics"]["warmth"] = r["warmth_engineered"]
            v["acoustics"]["rt60_source"] = "eyring-1khz"
            Path(p).write_text(json.dumps(v, indent=2) + "\n")
            print(f"  applied rt60={r['rt60_eyring']} warmth={r['warmth_engineered']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
