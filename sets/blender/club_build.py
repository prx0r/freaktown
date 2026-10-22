"""FUNNIER comedy-club stage set as ONE procedural Geometry Nodes graph (Blender 5.2+).

Built with nodekit + the NK node-group library from video-to-blender (MIT, github.com/gokayfem/video-to-blender).

    blender -b --factory-startup --python sets/blender/club_build.py -- \
        --skill <video-to-blender>/skills/procedural-blender-nodes \
        --preset dive --out out/club_dive.blend \
        [--render out/renders --views wide,eye --width 1600 --samples 64] \
        [--glb out/club-dive.glb [--bake 1024]] [--turntable out/tt --frames 240 --tt-width 1280]

One modifier group, "Club Set", builds the whole room on an empty mesh object. Its parts are groups an artist can
open and read:

    Club Room       house floor, brick back wall (Club Brick: Brick Texture + NK Stucco paint), side/rear walls,
                    ceiling, exit door + sign, optional exposed pipes
    Club Stage      the riser (NK Chamfer Box planks, NK Store Local Coords so every plank has its own grain),
                    black skirt, lip trim and side steps
    Club Curtains   side curtains, optional back drape and a scalloped valance (sine-folded grids, NK Felt)
    Club Props      mic stand (NK Rod, NK Profile Revolve, mic aimed 0.11 m in front of the performer's mouth),
                    bar stool (NK Ring foot rail) with a bottle on it, a set list taped to the floor
    Club Neon       blank neon sign: dark board + two fillet-rounded neon tubes (the text is drawn by the stage)
    Club Spot       lighting truss, lamp cans and a visible spotlight cone (additive, fades along its length)
    Club Audience   cafe tables scattered Poisson-spaced (NK Scatter On Surface), chairs round each table facing
                    it, bottles/glasses/candles (NK Glow Glass), seated audience silhouettes - or raked theatre rows

Coordinates: metres, Z up. Stage top is z = 0, the performer stands at the origin facing -Y (the audience), the
back wall sits at y = Back Wall Y (2.3, matching the three.js stage). glTF export turns -Y into three.js +Z.

Every face carries an INT attribute club_part; the exporter splits the realized mesh by it into named nodes
(club_wall, club_mic, ...) so the web stage can hide parts it draws itself (the fitted mic, the beam).
"""
import argparse, json, math, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent


def _skill_path(argv):
    for i, a in enumerate(argv):
        if a == "--skill" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--skill="):
            return a.split("=", 1)[1]
    return os.environ.get("V2B_SKILL", "")


_ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
_SKILL = _skill_path(_ARGV)
if not _SKILL or not pathlib.Path(_SKILL, "nodekit").is_dir():
    raise SystemExit("club_build: pass --skill <video-to-blender>/skills/procedural-blender-nodes (or $V2B_SKILL)")
sys.path.insert(0, _SKILL)

import bpy  # noqa: E402
from nodekit import inspect  # noqa: E402
from nodekit import scene as S  # noqa: E402
from nodekit.graph import Graph, once  # noqa: E402
from nodekit.materials import material as new_material  # noqa: E402
from library.shapes import chamfer_box, rod, ring, profile_revolve, rounded_box  # noqa: E402
from library.scatter import scatter_on_surface  # noqa: E402
from library.materials import (make_material, attribute_tint, stucco, wood_grain, felt, glow_glass,  # noqa: E402
                               store_local_coords, lin)
from library.post import haze_over_sky, soft_glow  # noqa: E402

NAME = "Club Set"
TAU = 2.0 * math.pi
PARTS = {  # club_part id -> glTF node name
    1: "club_floor", 2: "club_wall", 3: "club_house", 4: "club_stage", 5: "club_curtains", 6: "club_stool",
    7: "club_mic", 8: "club_neon", 9: "club_beam", 10: "club_truss", 11: "club_tables", 12: "club_chairs",
    13: "club_bottles", 14: "club_audience", 15: "club_candles", 16: "club_exit", 17: "club_pipes",
    18: "club_seats", 19: "club_setlist", 20: "club_neon_board",
}


# ---- node idioms (python helpers, not groups) ------------------------------------------------------------------
def store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def attr(g, name, dtype="FLOAT"):
    return g.node("GeometryNodeInputNamedAttribute", props={"data_type": dtype}, Name=name)["Attribute"]


def rand(g, lo, hi, seed, k, ident=None, dtype="FLOAT"):
    n = g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi,
               Seed=g.math("ADD", seed, float(k)))
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n["Value"]


def chance(g, p, seed, k, ident=None):
    n = g.node("FunctionNodeRandomValue", props={"data_type": "BOOLEAN"}, Probability=p,
               Seed=g.math("ADD", seed, float(k)))
    if ident is not None:
        g.connect(ident, n.i("ID"))
    return n["Value"]


def switch(g, typ, cond, false=None, true=None):
    n = g.node("GeometryNodeSwitch", props={"input_type": typ}, Switch=cond)
    g.connect(false, n.i("False"))
    g.connect(true, n.i("True"))
    return n["Output"]


def join(g, *geos):
    j = g.node("GeometryNodeJoinGeometry")
    for x in reversed(geos):
        g.connect(x, j.i("Geometry"))
    return j["Geometry"]


def xform(g, geo, t=None, r=None, s=None):
    n = g.node("GeometryNodeTransform", Geometry=geo)
    if t is not None:
        g.connect(t, n.i("Translation"))
    if r is not None:
        g.connect(r, n.i("Rotation"))
    if s is not None:
        g.connect(s, n.i("Scale"))
    return n["Geometry"]


def setmat(g, geo, mat):
    return g.node("GeometryNodeSetMaterial", Geometry=geo, Material=mat)["Geometry"]


def smooth(g, geo):
    return g.node("GeometryNodeSetShadeSmooth", Mesh=geo)["Mesh"]


def part(g, geo, pid):
    """Tag every face of geo with club_part = pid (the exporter splits by it)."""
    return store(g, geo, "club_part", pid, "INT", "FACE")


def box(g, size, center=(0.0, 0.0, 0.0)):
    m = g.node("GeometryNodeMeshCube", Size=size)["Mesh"]
    return xform(g, m, t=center)


def cyl(g, radius, depth, verts=16, fill="NGON"):
    return g.node("GeometryNodeMeshCylinder", props={"fill_type": fill}, Vertices=verts, Radius=radius,
                  Depth=depth)["Mesh"]


def M(g, x, *ops):
    """Chain of math ops: M(g, x, ("MULTIPLY", 2), ("ADD", 1))."""
    for op, v in ops:
        x = g.math(op, x, v)
    return x


def position(g):
    return g.node("GeometryNodeInputPosition")["Position"]


def wall_grid(g, sx, sy, nx=2, ny=2):
    return g.node("GeometryNodeMeshGrid", **{"Size X": sx, "Size Y": sy, "Vertices X": nx, "Vertices Y": ny})["Mesh"]


# ---- materials ------------------------------------------------------------------------------------------------
@once
def brick_paint():
    """Shader group: running-bond brick (Blender Brick Texture) with soot at the base, partly painted over with
    NK Stucco (club_paint = how much paint, club_tint = brick colour)."""
    g = Graph("Club Brick Paint", kind="SHADER",
              description="Running-bond brick from Blender's Brick Texture, varied per brick, sooted toward the "
                          "floor, then painted over with NK Stucco where noise is below Paint Cover (club_paint)")
    vec = g.input("Vector", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="Texture coordinate in metres")
    brick_c = g.input("Brick Color", "COLOR", lin("#7A3B2A"), desc="Average brick colour (club_tint)")
    mortar_c = g.input("Mortar Color", "COLOR", lin("#6E625A"), desc="Mortar colour")
    paint_c = g.input("Paint Color", "COLOR", lin("#2B2B33"), desc="Paint rolled over the bricks")
    cover = g.input("Paint Cover", "FLOAT", 0.15, min=0.0, max=1.0, subtype="FACTOR",
                    desc="0 bare brick, 1 fully painted (club_paint)")
    with g.frame("Bricks: 0.22 x 0.075 m running bond in the wall plane (X along, Z up)"):
        sep = g.separate(vec)
        uv = g.combine(sep["X"], sep["Z"], sep["Y"])
        dark = g.node("ShaderNodeMixRGB", props={"blend_type": "MULTIPLY"}, Fac=1.0, Color1=brick_c,
                      Color2=(0.62, 0.55, 0.52, 1.0))["Color"]
        br = g.node("ShaderNodeTexBrick", Vector=uv, Color1=brick_c, Color2=dark, Mortar=mortar_c, Scale=1.0,
                    **{"Mortar Size": 0.011, "Mortar Smooth": 0.25, "Bias": 0.0, "Brick Width": 0.225,
                       "Row Height": 0.075})
        br.b.offset, br.b.squash = 0.5, 1.0
        fine = g.node("ShaderNodeTexNoise", Vector=g.vmath("SCALE", uv, scale=30.0)["Vector"], Scale=1.0,
                      Detail=3.0)["Factor"]
        col = g.vmath("SCALE", br["Color"], scale=g.math("ADD", 0.82, g.math("MULTIPLY", fine, 0.36)))["Vector"]
    with g.frame("Soot: darker toward the floor and in blotches"):
        soot_n = g.node("ShaderNodeTexNoise", Vector=uv, Scale=0.8, Detail=4.0)["Factor"]
        low = g.map_range(sep["Z"], -0.6, 1.4, 0.55, 0.0, interp="SMOOTHSTEP")
        soot = g.math("ADD", low, g.map_range(soot_n, 0.55, 0.8, 0.0, 0.3), clamp=True)
        col = g.mix(soot, col, (0.03, 0.025, 0.02, 1.0), data_type="RGBA")["Result"]
    with g.frame("Paint: NK Stucco where large noise is below Paint Cover; mortar lines show through paint"):
        st = g.group(stucco(), Vector=vec, Color=paint_c, **{"Grime": 0.4, "Base Height": -0.6, "Grime Height": 1.2})
        pn = g.node("ShaderNodeTexNoise", Vector=uv, Scale=0.35, Detail=5.0, Roughness=0.65)["Factor"]
        paint = g.map_range(g.math("SUBTRACT", pn, g.math("SUBTRACT", g.math("MULTIPLY", cover, 1.3), 0.15)),
                            -0.04, 0.04, 1.0, 0.0)
        paint = g.math("MULTIPLY", paint, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", br["Factor"], 0.35)))
        col = g.mix(paint, col, st["Color"], data_type="RGBA")["Result"]
        rough = g.mix(paint, 0.93, 0.7)["Result"]
        bump = g.node("ShaderNodeBump", Strength=0.6, Distance=0.01,
                      Height=g.math("ADD", g.math("SUBTRACT", 1.0, br["Factor"]), g.math("MULTIPLY", fine, 0.15)))
    g.output("Color", "COLOR", col, desc="Wall colour")
    g.output("Roughness", "FLOAT", rough, desc="Roughness (paint is smoother)")
    g.output("Normal", "VECTOR", bump["Normal"], desc="Bricks proud of the mortar")
    return g.finish()


@once
def people_paint():
    g = Graph("Club People Paint", kind="SHADER",
              description="Audience silhouettes: clothes from nk_color (NK Attribute Tint), skin where club_skin = 1")
    skin = g.input("Skin", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", desc="1 on heads and hands (club_skin)")
    tone = g.input("Skin Tone", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR",
                   desc="0 dark to 1 light skin (club_tone, random per person)")
    with g.frame("Clothes from nk_color; skin between two tones by club_tone"):
        tint = g.group(attribute_tint(), **{"Base Color": lin("#2A2A30"), "Value Variation": 0.3, "Roughness": 0.85})
        sk = g.mix(tone, lin("#4A2C1E"), lin("#D9A88A"), data_type="RGBA")["Result"]
        col = g.mix(skin, tint["Color"], sk, data_type="RGBA")["Result"]
        rough = g.mix(skin, tint["Roughness"], 0.5)["Result"]
    g.output("Color", "COLOR", col, desc="Colour")
    g.output("Roughness", "FLOAT", rough, desc="Roughness")
    return g.finish()


def emissive(name, color_attr=None, color=(1, 1, 1, 1), strength=8.0):
    """Emission material; colour from a FLOAT_COLOR attribute when given."""
    m = new_material(name)
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    em.inputs["Color"].default_value = color
    if color_attr:
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_type, a.attribute_name = "GEOMETRY", color_attr
        nt.links.new(a.outputs["Color"], em.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m["club_emit"] = strength
    return m


def beam_material():
    """Additive light cone: transparent + emission that fades from the lamp (club_beam_t 0) to the floor (1) and
    toward the silhouette (layer weight), so the cone reads as lit haze."""
    m = new_material("Club Beam")
    nt = m.node_tree
    a = nt.nodes.new("ShaderNodeAttribute"); a.attribute_type, a.attribute_name = "GEOMETRY", "club_beam_t"
    col = nt.nodes.new("ShaderNodeAttribute"); col.attribute_type, col.attribute_name = "GEOMETRY", "club_beam_color"
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.45
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    # fade to nothing well before the floor end: the cone runs through the raised deck, and a lit lower end read
    # as a grey haze "dome" round the spot pool; smoothstep so there is no visible cut-off ring
    fade = nt.nodes.new("ShaderNodeMapRange"); fade.interpolation_type = "SMOOTHSTEP"
    fade.inputs["From Max"].default_value = 0.8
    fade.inputs["To Min"].default_value = 1.0
    fade.inputs["To Max"].default_value = 0.0
    nt.links.new(a.outputs["Factor"], fade.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    nt.links.new(inv.outputs[0], mul.inputs[0]); nt.links.new(fade.outputs[0], mul.inputs[1])
    st = nt.nodes.new("ShaderNodeAttribute"); st.attribute_type, st.attribute_name = "GEOMETRY", "club_beam_strength"
    mul2 = nt.nodes.new("ShaderNodeMath"); mul2.operation = "MULTIPLY"
    nt.links.new(mul.outputs[0], mul2.inputs[0]); nt.links.new(st.outputs["Factor"], mul2.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col.outputs["Color"], em.inputs["Color"]); nt.links.new(mul2.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
    m["club_beam"] = 1
    return m


def glass_material():
    m = new_material("Club Bottle Glass")
    nt = m.node_tree
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    a = nt.nodes.new("ShaderNodeAttribute"); a.attribute_type, a.attribute_name = "GEOMETRY", "nk_color"
    nt.links.new(a.outputs["Color"], pb.inputs["Base Color"])
    pb.inputs["Roughness"].default_value = 0.08
    pb.inputs["Transmission Weight"].default_value = 0.85
    pb.inputs["IOR"].default_value = 1.45
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(pb.outputs[0], out.inputs["Surface"])
    return m


def flat_material(name, hexcol, rough=0.8, metal=0.0):
    m = new_material(name)
    nt = m.node_tree
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pb.inputs["Base Color"].default_value = lin(hexcol)
    pb.inputs["Roughness"].default_value = rough
    pb.inputs["Metallic"].default_value = metal
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(pb.outputs[0], out.inputs["Surface"])
    return m


def materials():
    return {
        "brick": make_material("Club Brick", brick_paint(), **{"Brick Color": "attr:club_tint",
                                                                "Paint Color": "attr:club_paint_color",
                                                                "Paint Cover": "attr:club_paint"}),
        "house": make_material("Club House Wall", stucco, Color="attr:club_house_color",
                               **{"Grime": 0.5, "Base Height": 0.0, "Grime Height": 1.0}),
        "floor": make_material("Club Floor", stucco, Color="attr:club_floor_color",
                               **{"Grime": 0.8, "Mottle": 0.6, "Roughness": 0.55}),
        "stage": make_material("Club Stage Boards", wood_grain, **{"Light Color": lin("#5A3A22"),
                                                                    "Dark Color": lin("#2A160C"),
                                                                    "Piece Shift": 3.0, "Roughness": 0.45}),
        "black": flat_material("Club Matte Black", "#0E0D10", 0.9),
        "metal": flat_material("Club Metal", "#2A2A2E", 0.32, 1.0),
        "chrome": flat_material("Club Chrome", "#C8C8CC", 0.18, 1.0),
        "curtain": make_material("Club Velvet", felt, Color="attr:club_curtain_color",
                                 **{"Sheen": 0.9, "Mottle": 0.12}),
        "neon": emissive("Club Neon", "club_neon_color", strength=14.0),
        "board": flat_material("Club Sign Board", "#121016", 0.6),
        "beam": beam_material(),
        "table": make_material("Club Table Wood", wood_grain, **{"Light Color": lin("#3B2416"),
                                                                  "Dark Color": lin("#1C0F08"),
                                                                  "Piece Shift": 2.0, "Roughness": 0.35}),
        "chair": make_material("Club Chair", attribute_tint, **{"Base Color": lin("#2C1A12"),
                                                               "Value Variation": 0.25, "Roughness": 0.6}),
        "glass": glass_material(),
        "people": make_material("Club People", people_paint(), Skin="attr:club_skin", **{"Skin Tone": "attr:club_tone"}),
        "candle": make_material("Club Candle", glow_glass, **{"Strength": 6.0, "Glass Color": lin("#5A1A10"),
                                                              "Core Color": lin("#FF9A3C")}),
        "exit": emissive("Club Exit", color=lin("#21FF6A"), strength=10.0),
        "seat": make_material("Club Seat Velvet", felt, Color="attr:club_seat_color", **{"Sheen": 0.8}),
        "paper": flat_material("Club Set List", "#E9E6DC", 0.9),
        "pipe": flat_material("Club Pipe", "#4A4640", 0.5, 0.7),
    }


# ---- Club Room ----------------------------------------------------------------------------------------------------
@once
def room(mats):
    g = Graph("Club Room", description="The room: house floor at the foot of the riser, the brick back wall behind "
                                       "the stage, side and rear walls, ceiling, a door with a glowing exit sign, "
                                       "and optional exposed pipes. Wall colours ride on attributes the materials "
                                       "read (club_tint, club_paint, club_house_color, club_floor_color)")
    W = g.input("Room Width", "FLOAT", 10.0, min=4.0, max=40.0, subtype="DISTANCE", desc="Wall to wall")
    D = g.input("Room Depth", "FLOAT", 11.0, min=4.0, max=60.0, subtype="DISTANCE",
                desc="Back wall to rear wall (the house runs from the stage toward -Y)")
    H = g.input("Ceiling Height", "FLOAT", 3.8, min=2.0, max=20.0, subtype="DISTANCE",
                desc="Ceiling height above the stage top")
    R = g.input("Riser Height", "FLOAT", 0.3, min=0.0, max=2.0, subtype="DISTANCE",
                desc="Stage top above the house floor")
    wy = g.input("Back Wall Y", "FLOAT", 2.3, min=0.5, max=10.0, subtype="DISTANCE",
                 desc="Back wall distance behind the performer (2.3 matches the web stage)")
    brick_c = g.input("Brick Color", "COLOR", lin("#7A3B2A"), desc="Average brick colour")
    paint_c = g.input("Paint Color", "COLOR", lin("#24232B"), desc="Paint rolled over parts of the brick")
    cover = g.input("Paint Cover", "FLOAT", 0.15, min=0.0, max=1.0, subtype="FACTOR",
                    desc="0 bare brick, 1 painted wall")
    house_c = g.input("House Color", "COLOR", lin("#1A1418"), desc="Side and rear walls, ceiling")
    floor_c = g.input("Floor Color", "COLOR", lin("#16120F"), desc="House floor (sticky concrete)")
    pipes = g.input("Pipes", "INT", 0, min=0, max=12, desc="Exposed pipes along the ceiling (basements)")
    with g.frame("Back wall: a plane behind the stage from the house floor to the ceiling, facing the audience"):
        hh = g.math("ADD", H, R)
        bw = xform(g, wall_grid(g, W, hh, 2, 2), t=g.combine(0.0, wy, g.math("SUBTRACT", g.math("MULTIPLY", hh, 0.5), R)),
                   r=(math.pi / 2, 0.0, 0.0))
        bw = store(g, bw, "club_tint", brick_c, "FLOAT_COLOR", "FACE")
        bw = store(g, bw, "club_paint_color", paint_c, "FLOAT_COLOR", "FACE")
        bw = store(g, bw, "club_paint", cover, "FLOAT", "FACE")
        bw = part(g, setmat(g, bw, mats["brick"]), 2)
    with g.frame("House floor: from the rear wall to the back wall at the foot of the riser"):
        rear = g.math("SUBTRACT", wy, D)
        fl = xform(g, wall_grid(g, W, D), t=g.combine(0.0, g.math("SUBTRACT", wy, g.math("MULTIPLY", D, 0.5)),
                                                       g.math("MULTIPLY", R, -1.0)))
        fl = store(g, fl, "club_floor_color", floor_c, "FLOAT_COLOR", "FACE")
        fl = part(g, setmat(g, fl, mats["floor"]), 1)
    with g.frame("Side walls, rear wall and ceiling, all facing in (house colour)"):
        cz = g.math("SUBTRACT", g.math("MULTIPLY", hh, 0.5), R)
        cy = g.math("SUBTRACT", wy, g.math("MULTIPLY", D, 0.5))
        halfw = g.math("MULTIPLY", W, 0.5)
        left = xform(g, wall_grid(g, D, hh), t=g.combine(g.math("MULTIPLY", halfw, -1.0), cy, cz),
                     r=(math.pi / 2, 0.0, -math.pi / 2))
        right = xform(g, wall_grid(g, D, hh), t=g.combine(halfw, cy, cz), r=(math.pi / 2, 0.0, math.pi / 2))
        rw = xform(g, wall_grid(g, W, hh), t=g.combine(0.0, rear, cz), r=(math.pi / 2, 0.0, math.pi))
        ceil = xform(g, wall_grid(g, W, D), t=g.combine(0.0, cy, H), r=(math.pi, 0.0, 0.0))
        house = join(g, left, right, rw, ceil)
        house = store(g, house, "club_house_color", house_c, "FLOAT_COLOR", "FACE")
        house = part(g, setmat(g, house, mats["house"]), 3)
    with g.frame("Exit: a dark door in the rear wall's corner and a green sign above it"):
        dx = g.math("SUBTRACT", halfw, 1.1)
        door = box(g, (0.95, 0.06, 2.05), g.combine(dx, g.math("ADD", rear, 0.03), g.math("SUBTRACT", 1.025, R)))
        door = part(g, setmat(g, door, mats["black"]), 3)
        sign = box(g, (0.36, 0.06, 0.14), g.combine(dx, g.math("ADD", rear, 0.05), g.math("SUBTRACT", 2.3, R)))
        sign = part(g, setmat(g, sign, mats["exit"]), 16)
    with g.frame("Pipes: rods along the ceiling, spread across the room"):
        pts = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=pipes,
                     **{"Start Location": g.combine(g.math("MULTIPLY", halfw, -0.8), 0.0, 0.0),
                        "Offset": g.combine(g.math("MULTIPLY", halfw, 0.8), 0.0, 0.0)})["Mesh"]
        pts = g.node("GeometryNodeMeshToPoints", Mesh=pts)["Points"]
        pipe = g.group(rod(), Start=g.combine(0.0, rear, 0.0), End=g.combine(0.0, wy, 0.0), Radius=0.05,
                       Resolution=10)["Mesh"]
        idx = g.node("GeometryNodeInputIndex")["Index"]
        drop = g.math("SUBTRACT", H, g.math("ADD", 0.12, rand(g, 0.0, 0.25, 0, 71, idx)))
        ps = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=pipe,
                    Scale=g.combine(rand(g, 0.6, 1.5, 0, 72, idx), 1.0, rand(g, 0.6, 1.5, 0, 72, idx)))["Instances"]
        # world space: in local space the drop was multiplied by each pipe's thickness scale (pipes hung at head height)
        ps = g.node("GeometryNodeTranslateInstances", Instances=ps, Translation=g.combine(0.0, 0.0, drop),
                    **{"Local Space": False})["Instances"]
        ps = g.node("GeometryNodeRealizeInstances", Geometry=ps)["Geometry"]
        ps = part(g, setmat(g, smooth(g, ps), mats["pipe"]), 17)
    g.output("Geometry", "GEOMETRY", join(g, bw, fl, house, door, sign, ps), desc="The room")
    return g.finish()


# ---- Club Stage ---------------------------------------------------------------------------------------------------
@once
def stage(mats):
    g = Graph("Club Stage", description="The riser: a deck of chamfered planks across the stage (each with its own "
                                        "grain via NK Store Local Coords), a black skirt down to the house floor, a "
                                        "lip trim along the front edge and a flight of steps at stage right")
    SW = g.input("Stage Width", "FLOAT", 6.0, min=1.5, max=30.0, subtype="DISTANCE", desc="Across the stage")
    SD = g.input("Stage Depth", "FLOAT", 3.4, min=1.0, max=20.0, subtype="DISTANCE",
                 desc="From the back wall to the front edge")
    R = g.input("Riser Height", "FLOAT", 0.3, min=0.0, max=2.0, subtype="DISTANCE", desc="Stage top above the floor")
    wy = g.input("Back Wall Y", "FLOAT", 2.3, min=0.5, max=10.0, subtype="DISTANCE", desc="Back wall position")
    pw = g.input("Plank Width", "FLOAT", 0.14, min=0.05, max=0.6, subtype="DISTANCE", desc="Deck board width")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    cy = g.math("SUBTRACT", wy, g.math("MULTIPLY", SD, 0.5))
    with g.frame("Deck: one chamfered plank per Plank Width across the stage, top at z = 0"):
        n = g.math("CEIL", g.math("DIVIDE", SW, pw))
        line = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=n,
                      **{"Start Location": g.combine(g.math("MULTIPLY", g.math("SUBTRACT", SW, pw), -0.5), cy, -0.02),
                         "Offset": g.combine(g.math("MULTIPLY", g.math("SUBTRACT", SW, pw), 0.5), cy, -0.02)})
        pts = g.node("GeometryNodeMeshToPoints", Mesh=line["Mesh"])["Points"]
        plank = g.group(chamfer_box(), Size=g.combine(g.math("SUBTRACT", pw, 0.004), SD, 0.04), Chamfer=0.004)["Mesh"]
        plank = g.group(store_local_coords(), Geometry=plank, **{"Grain Axis": 1})["Geometry"]
        idx = g.node("GeometryNodeInputIndex")["Index"]
        deck = g.node("GeometryNodeInstanceOnPoints", Points=pts, Instance=plank)["Instances"]
        deck = store(g, deck, "nk_rand", rand(g, 0.0, 1.0, seed, 3, idx), "FLOAT", "INSTANCE")
        deck = g.node("GeometryNodeRealizeInstances", Geometry=deck)["Geometry"]
        deck = part(g, setmat(g, deck, mats["stage"]), 4)
    with g.frame("Skirt and lip: matte black box under the deck, a thin trim on the front edge"):
        skh = g.math("MAXIMUM", g.math("SUBTRACT", R, 0.04), 0.001)
        skirt = box(g, g.combine(SW, SD, skh), g.combine(0.0, cy, g.math("SUBTRACT", -0.04, g.math("MULTIPLY", skh, 0.5))))
        front = g.math("SUBTRACT", wy, SD)
        lip = box(g, g.combine(g.math("ADD", SW, 0.02), 0.05, 0.05), g.combine(0.0, front, -0.02))
        sk = part(g, setmat(g, join(g, skirt, lip), mats["black"]), 4)
    with g.frame("Steps: one 0.18 m step per rise, beside stage right"):
        steps = g.math("FLOOR", g.math("DIVIDE", R, 0.18))
        sx = g.math("ADD", g.math("MULTIPLY", SW, 0.5), 0.35)
        sline = g.node("GeometryNodeMeshLine", props={"mode": "OFFSET"}, Count=steps,
                       **{"Start Location": g.combine(sx, g.math("ADD", front, 0.25), g.math("MULTIPLY", R, -1.0)),
                          "Offset": (0.0, 0.0, 0.0)})["Mesh"]
        spts = g.node("GeometryNodeMeshToPoints", Mesh=sline)["Points"]
        k = g.node("GeometryNodeInputIndex")["Index"]
        rise = g.math("DIVIDE", R, g.math("MAXIMUM", g.math("ADD", steps, 1.0), 1.0))
        hk = g.math("MULTIPLY", rise, g.math("ADD", k, 1.0))
        spts = g.node("GeometryNodeSetPosition", Geometry=spts,
                      Offset=g.combine(0.0, g.math("MULTIPLY", g.math("SUBTRACT", steps, k), -0.28),
                                       g.math("MULTIPLY", hk, 0.5)))["Geometry"]
        step = g.node("GeometryNodeMeshCube", Size=(0.7, 0.3, 1.0))["Mesh"]
        st = g.node("GeometryNodeInstanceOnPoints", Points=spts, Instance=step, Scale=g.combine(1.0, 1.0, hk))["Instances"]
        st = g.node("GeometryNodeRealizeInstances", Geometry=st)["Geometry"]
        st = part(g, setmat(g, st, mats["black"]), 4)
    g.output("Geometry", "GEOMETRY", join(g, deck, sk, st), desc="The riser")
    return g.finish()


# ---- Club Curtains -------------------------------------------------------------------------------------------------
def folded(g, width, height, folds, depth, nx=64, taper=0.0):
    """A vertical curtain panel in the XZ plane (bottom at z = 0, centred on x = 0), folded in Y by a sine of x.
    taper > 0 gathers the folds tighter toward the bottom (a tied-back swag)."""
    grid = wall_grid(g, width, height, nx, 8)
    p = g.separate(position(g))
    u = g.math("DIVIDE", p["X"], width)
    v = g.math("ADD", g.math("DIVIDE", p["Y"], height), 0.5)          # 0 bottom .. 1 top
    wave = g.math("SINE", g.math("MULTIPLY", u, g.math("MULTIPLY", folds, TAU)))
    noise = g.node("ShaderNodeTexNoise", Vector=position(g), Scale=1.3, Detail=2.0)["Factor"]
    amp = g.math("MULTIPLY", depth, g.math("ADD", 0.75, g.math("MULTIPLY", noise, 0.5)))
    squeeze = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", taper, g.math("SUBTRACT", 1.0, v)))
    grid = g.node("GeometryNodeSetPosition", Geometry=grid,
                  Position=g.combine(g.math("MULTIPLY", p["X"], squeeze), g.math("MULTIPLY", wave, amp),
                                     g.math("MULTIPLY", v, height)))["Geometry"]
    return smooth(g, grid)


@once
def curtains(mats):
    g = Graph("Club Curtains", description="Velvet: two side curtains framing the stage (sine folds, gathered "
                                           "toward the floor), an optional full back drape over the brick and an "
                                           "optional scalloped valance across the top of the stage opening")
    SW = g.input("Stage Width", "FLOAT", 6.0, min=1.5, max=30.0, subtype="DISTANCE", desc="Across the stage")
    SD = g.input("Stage Depth", "FLOAT", 3.4, min=1.0, max=20.0, subtype="DISTANCE", desc="Deck depth")
    H = g.input("Ceiling Height", "FLOAT", 3.8, min=2.0, max=20.0, subtype="DISTANCE", desc="Ceiling above stage")
    wy = g.input("Back Wall Y", "FLOAT", 2.3, min=0.5, max=10.0, subtype="DISTANCE", desc="Back wall position")
    cw = g.input("Side Curtain Width", "FLOAT", 1.6, min=0.0, max=10.0, subtype="DISTANCE",
                 desc="Width of each side curtain (0 = none)")
    folds = g.input("Folds Per Metre", "FLOAT", 3.0, min=0.5, max=10.0, desc="Fold frequency")
    depth = g.input("Fold Depth", "FLOAT", 0.1, min=0.0, max=0.5, subtype="DISTANCE", desc="Fold amplitude")
    drape = g.input("Back Drape", "BOOL", False, desc="Hang a full drape over the back wall")
    valance = g.input("Valance", "BOOL", False, desc="Scalloped pelmet across the top of the stage")
    col = g.input("Curtain Color", "COLOR", lin("#5E0B16"), desc="Velvet colour")
    with g.frame("Side curtains: one each side, near the back wall, angled toward the audience"):
        has = g.math("GREATER_THAN", cw, 0.01)
        cwc = g.math("MAXIMUM", cw, 0.05)
        panel = folded(g, cwc, g.math("SUBTRACT", H, 0.05), g.math("MULTIPLY", folds, cwc), depth, 64, 0.35)
        x = g.math("ADD", g.math("MULTIPLY", SW, 0.5), g.math("MULTIPLY", cwc, -0.3))
        y = g.math("SUBTRACT", wy, g.math("MINIMUM", 0.7, g.math("MULTIPLY", SD, 0.25)))
        lc = xform(g, panel, t=g.combine(g.math("MULTIPLY", x, -1.0), y, 0.0), r=(0.0, 0.0, -0.35))
        rc = xform(g, panel, t=g.combine(x, y, 0.0), r=(0.0, 0.0, 0.35))
        sides = switch(g, "GEOMETRY", has, None, join(g, lc, rc))
    with g.frame("Back drape: a full-width folded curtain just in front of the back wall"):
        bd = folded(g, g.math("ADD", SW, 1.0), g.math("SUBTRACT", H, 0.05), g.math("MULTIPLY", folds, g.math("ADD", SW, 1.0)),
                    g.math("MULTIPLY", depth, 0.6), 160, 0.0)
        bd = xform(g, bd, t=g.combine(0.0, g.math("SUBTRACT", wy, 0.12), 0.0))
        bd = switch(g, "GEOMETRY", drape, None, bd)
    with g.frame("Valance: a short folded strip across the opening with a scalloped hem"):
        vw = g.math("ADD", SW, 1.2)
        vg = wall_grid(g, vw, 0.9, 120, 6)
        p = g.separate(position(g))
        v = g.math("ADD", g.math("DIVIDE", p["Y"], 0.9), 0.5)
        sc = g.math("ABSOLUTE", g.math("SINE", g.math("MULTIPLY", p["X"], 2.2)))
        hem = g.math("MULTIPLY", g.math("SUBTRACT", 1.0, v), g.math("MULTIPLY", sc, 0.25))
        vg = g.node("GeometryNodeSetPosition", Geometry=vg,
                    Position=g.combine(p["X"], g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", p["X"], 9.0)), 0.05),
                                       g.math("SUBTRACT", g.math("MULTIPLY", v, 0.9), hem)))["Geometry"]
        vg = xform(g, smooth(g, vg), t=g.combine(0.0, g.math("ADD", g.math("SUBTRACT", wy, SD), 0.15),
                                                  g.math("SUBTRACT", H, 0.95)))
        vg = switch(g, "GEOMETRY", valance, None, vg)
    with g.frame("Velvet material and colour"):
        allc = join(g, sides, bd, vg)
        allc = store(g, allc, "club_curtain_color", col, "FLOAT_COLOR", "FACE")
        allc = part(g, setmat(g, allc, mats["curtain"]), 5)
    g.output("Geometry", "GEOMETRY", allc, desc="Curtains")
    return g.finish()


# ---- Club Props ------------------------------------------------------------------------------------------------------
@once
def bottle_shape(mats):
    g = Graph("Club Bottle", description="A beer bottle (NK Profile Revolve, 0.23 m) in tinted glass (nk_color)")
    with g.frame("Revolved profile: body, shoulder, neck"):
        b = g.group(profile_revolve(), Height=0.23, Segments=12, Rings=3,
                    **{"Radius Bottom": 0.031, "Radius Lower": 0.032, "Radius Middle": 0.03,
                       "Radius Upper": 0.012, "Radius Top": 0.011})["Mesh"]
        b = setmat(g, smooth(g, b), mats["glass"])
    g.output("Mesh", "GEOMETRY", b, desc="Bottle")
    return g.finish()


@once
def glass_shape(mats):
    g = Graph("Club Pint", description="A pint glass (hollow NK Profile Revolve, 0.15 m) in clear glass")
    with g.frame("Hollow tapered vessel"):
        b = g.group(profile_revolve(), Height=0.15, Segments=12, Rings=2, **{"Radius Bottom": 0.03,
                    "Radius Lower": 0.032, "Radius Middle": 0.034, "Radius Upper": 0.037, "Radius Top": 0.04,
                    "Wall Thickness": 0.003})["Mesh"]
        b = setmat(g, smooth(g, b), mats["glass"])
    g.output("Mesh", "GEOMETRY", b, desc="Pint glass")
    return g.finish()


@once
def props(mats):
    g = Graph("Club Props", description="What stands on the stage: a mic stand whose mic sits Mic Gap in front of "
                                        "the performer's mouth, a bar stool with a beer on it, and a set list "
                                        "taped to the boards")
    mouth_h = g.input("Mouth Height", "FLOAT", 1.5, min=0.8, max=2.2, subtype="DISTANCE",
                      desc="Performer's mouth above the stage (1.5 for a 1.7 m body)")
    gap = g.input("Mic Gap", "FLOAT", 0.11, min=0.02, max=0.5, subtype="DISTANCE",
                  desc="Mic head distance in front of the mouth (FUNNIER uses 0.11 m)")
    stool_on = g.input("Stool", "BOOL", True, desc="Show the bar stool")
    stool_x = g.input("Stool X", "FLOAT", -1.3, min=-10.0, max=10.0, subtype="DISTANCE", desc="Stool position across")
    stool_y = g.input("Stool Y", "FLOAT", 0.9, min=-5.0, max=5.0, subtype="DISTANCE",
                      desc="Stool position (+ is upstage, toward the back wall)")
    with g.frame("Mic: grille 0.11 m in front of the mouth, body angled down toward the clip"):
        mouth = g.combine(0.0, -0.1, mouth_h)
        head = g.vmath("ADD", mouth, g.combine(0.0, g.math("MULTIPLY", gap, -1.0), -0.02))["Vector"]
        axis = g.vmath("NORMALIZE", (0.0, 0.55, 0.45))["Vector"]
        clip = g.vmath("SUBTRACT", head, g.vmath("SCALE", axis, scale=0.2)["Vector"])["Vector"]
        body = g.group(profile_revolve(), Height=0.17, Segments=12, Rings=2, **{"Radius Bottom": 0.011,
                       "Radius Lower": 0.013, "Radius Middle": 0.016, "Radius Upper": 0.019, "Radius Top": 0.021})["Mesh"]
        grille = xform(g, g.node("GeometryNodeMeshUVSphere", Segments=14, Rings=8, Radius=0.027)["Mesh"],
                       t=(0.0, 0.0, 0.19))
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=axis)["Rotation"]
        mic = xform(g, join(g, setmat(g, smooth(g, body), mats["metal"]), setmat(g, smooth(g, grille), mats["chrome"])),
                    t=clip, r=rot)
    with g.frame("Stand: round base, pole up to the clip"):
        cs = g.separate(clip)
        base_c = g.combine(cs["X"], cs["Y"], 0.0)
        base = g.group(profile_revolve(), Height=0.03, Segments=20, Rings=1, **{"Radius Bottom": 0.15,
                       "Radius Lower": 0.15, "Radius Middle": 0.13, "Radius Upper": 0.06, "Radius Top": 0.03})["Mesh"]
        base = xform(g, base, t=base_c)
        pole = g.group(rod(), Start=base_c, End=clip, Radius=0.011, Resolution=10)["Mesh"]
        stand = setmat(g, smooth(g, join(g, base, pole)), mats["metal"])
        micstand = part(g, join(g, stand, mic), 7)
    with g.frame("Stool: seat, three splayed legs, a foot ring, a beer on top"):
        seat = xform(g, cyl(g, 0.19, 0.05, 20), t=(0.0, 0.0, 0.75))
        legs = []
        for i in range(3):
            a = i * TAU / 3
            legs.append(g.group(rod(), Start=(0.12 * math.cos(a), 0.12 * math.sin(a), 0.74),
                                End=(0.2 * math.cos(a), 0.2 * math.sin(a), 0.0), Radius=0.012, Resolution=8)["Mesh"])
        rim = xform(g, g.group(ring(), Radius=0.165, **{"Tube Width": 0.02, "Tube Height": 0.02,
                                                       "Resolution": 24, "Tube Resolution": 6})["Mesh"], t=(0.0, 0.0, 0.28))
        st = join(g, setmat(g, seat, mats["black"]), setmat(g, smooth(g, join(g, *legs, rim)), mats["chrome"]))
        beer = store(g, g.group(bottle_shape(mats))["Mesh"], "nk_color", lin("#5A3008"), "FLOAT_COLOR", "POINT")
        beer = xform(g, beer, t=(0.07, 0.02, 0.775))
        st = xform(g, join(g, part(g, st, 6), part(g, beer, 13)), t=g.combine(stool_x, stool_y, 0.0))
        st = switch(g, "GEOMETRY", stool_on, None, st)
    with g.frame("Set list: a sheet of paper taped to the boards beside the mic"):
        sl = xform(g, wall_grid(g, 0.21, 0.297), t=(0.42, -0.55, 0.003), r=(0.0, 0.0, 0.3))
        sl = part(g, setmat(g, sl, mats["paper"]), 19)
    g.output("Geometry", "GEOMETRY", join(g, micstand, st, sl), desc="Stage props")
    return g.finish()


# ---- Club Neon --------------------------------------------------------------------------------------------------------
@once
def neon(mats):
    g = Graph("Club Neon", description="A blank neon sign on the back wall: a dark board with two concentric "
                                       "rounded-rectangle neon tubes; the web stage draws its own text on it")
    wy = g.input("Back Wall Y", "FLOAT", 2.3, min=0.5, max=10.0, subtype="DISTANCE", desc="Back wall position")
    H = g.input("Ceiling Height", "FLOAT", 3.8, min=2.0, max=20.0, subtype="DISTANCE", desc="Ceiling above stage")
    w = g.input("Sign Width", "FLOAT", 4.0, min=0.5, max=12.0, subtype="DISTANCE", desc="Tube width")
    h = g.input("Sign Height", "FLOAT", 1.0, min=0.2, max=4.0, subtype="DISTANCE", desc="Tube height")
    z = g.input("Sign Height Above Stage", "FLOAT", 3.25, min=0.5, max=15.0, subtype="DISTANCE",
                desc="Centre height (clamped below the ceiling)")
    col = g.input("Neon Color", "COLOR", lin("#FF2FA0"), desc="Tube colour")
    drape = g.input("Back Drape", "BOOL", False, desc="A drape hangs on the back wall: mount the sign in front of it")
    with g.frame("Placement: centred on the back wall (in front of a drape), kept 0.35 m under the ceiling"):
        zc = g.math("MINIMUM", z, g.math("SUBTRACT", g.math("SUBTRACT", H, g.math("MULTIPLY", h, 0.5)), 0.35))
        off = g.math("ADD", 0.06, g.math("MULTIPLY", drape, 0.3))
        centre = g.combine(0.0, g.math("SUBTRACT", wy, off), zc)
    with g.frame("Tubes: rounded rectangles swept by a 15 mm circle"):
        def tube(ww, hh, rr):
            q = g.node("GeometryNodeCurvePrimitiveQuadrilateral", Width=ww, Height=hh)["Curve"]
            q = g.node("GeometryNodeFilletCurve", Curve=q, Radius=rr, Mode="Poly", Count=6)["Curve"]
            prof = g.node("GeometryNodeCurvePrimitiveCircle", Resolution=8, Radius=0.015)["Curve"]
            return g.node("GeometryNodeCurveToMesh", Curve=q, **{"Profile Curve": prof})["Mesh"]
        outer = tube(w, h, 0.16)
        inner = tube(g.math("SUBTRACT", w, 0.16), g.math("SUBTRACT", h, 0.16), 0.1)
        tubes = xform(g, join(g, outer, inner), t=centre, r=(math.pi / 2, 0.0, 0.0))
        tubes = store(g, tubes, "club_neon_color", col, "FLOAT_COLOR", "POINT")
        tubes = part(g, setmat(g, smooth(g, tubes), mats["neon"]), 8)
    with g.frame("Board: a dark rounded slab behind the tubes"):
        bs = g.combine(g.math("ADD", w, 0.3), 0.05, g.math("ADD", h, 0.3))
        board = g.group(rounded_box(), Size=bs, Radius=0.02, Segments=2)["Mesh"]
        board = xform(g, board, t=g.vmath("ADD", centre, (0.0, 0.035, 0.0))["Vector"])
        board = part(g, setmat(g, board, mats["board"]), 20)
    g.output("Geometry", "GEOMETRY", join(g, tubes, board), desc="Neon sign")
    return g.finish()


# ---- Club Spot ----------------------------------------------------------------------------------------------------------
@once
def spot(mats):
    g = Graph("Club Spot", description="Lighting: a truss bar under the ceiling over the house, a key lamp can "
                                       "aimed at the performer with a visible cone (fading from lamp to floor), "
                                       "and two coloured side cans. The scene's spot light uses the same numbers")
    W = g.input("Room Width", "FLOAT", 10.0, min=4.0, max=40.0, subtype="DISTANCE", desc="Wall to wall")
    H = g.input("Ceiling Height", "FLOAT", 3.8, min=2.0, max=20.0, subtype="DISTANCE", desc="Ceiling above stage")
    throw = g.input("Spot Throw", "FLOAT", 4.6, min=1.0, max=30.0, subtype="DISTANCE",
                    desc="How far in front of the performer the key lamp hangs")
    radius = g.input("Spot Radius", "FLOAT", 0.85, min=0.2, max=4.0, subtype="DISTANCE",
                     desc="Radius of the pool of light on the stage")
    strength = g.input("Beam Strength", "FLOAT", 0.35, min=0.0, max=5.0, desc="Brightness of the visible cone")
    col = g.input("Beam Color", "COLOR", (1.0, 0.92, 0.8, 1.0), desc="Cone colour")
    show = g.input("Show Beam", "BOOL", True, desc="Draw the visible cone (off for the performer's-eye view, "
                                                   "which sits inside it)")
    with g.frame("Lamp position: under the ceiling, Spot Throw in front, aimed at the floor behind the performer"):
        lamp = g.combine(0.45, g.math("MULTIPLY", throw, -1.0), g.math("SUBTRACT", H, 0.45))
        target = (0.0, 0.15, 0.0)
        d = g.vmath("SUBTRACT", target, lamp)["Vector"]
        L = g.vmath("LENGTH", d)["Value"]
        dirn = g.vmath("NORMALIZE", d)["Vector"]
        rot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=dirn)["Rotation"]
    with g.frame("Cone: open cone from the lens to the floor pool; club_beam_t is 0 at the lamp, 1 at the floor"):
        cone = g.node("GeometryNodeMeshCone", props={"fill_type": "NONE"}, Vertices=40, **{"Side Segments": 6,
                      "Radius Top": radius, "Radius Bottom": 0.09, "Depth": L})["Mesh"]
        # the Cone primitive spans z = 0 (Radius Bottom, the lens) .. Depth (Radius Top, the floor pool)
        t = g.math("DIVIDE", g.separate(position(g))["Z"], L, clamp=True)
        cone = store(g, cone, "club_beam_t", t, "FLOAT", "POINT")
        cone = xform(g, cone, t=lamp, r=rot)
        cone = store(g, cone, "club_beam_color", col, "FLOAT_COLOR", "POINT")
        cone = store(g, cone, "club_beam_strength", strength, "FLOAT", "POINT")
        cone = part(g, setmat(g, cone, mats["beam"]), 9)
        cone = switch(g, "GEOMETRY", show, None, cone)
    with g.frame("Hardware: truss across the room, the key can and two coloured side cans"):
        ls = g.separate(lamp)
        ty = ls["Y"]
        tz = g.math("ADD", ls["Z"], 0.25)
        hw = g.math("MULTIPLY", W, 0.5)
        bar = g.group(rod(), Start=g.combine(g.math("MULTIPLY", hw, -1.0), ty, tz), End=g.combine(hw, ty, tz),
                      Radius=0.025, Resolution=8)["Mesh"]
        bar2 = g.group(rod(), Start=g.combine(g.math("MULTIPLY", hw, -1.0), g.math("ADD", ty, 0.25), tz),
                       End=g.combine(hw, g.math("ADD", ty, 0.25), tz), Radius=0.025, Resolution=8)["Mesh"]
        can = xform(g, cyl(g, 0.12, 0.34, 16), t=(0.0, 0.0, -0.17))
        key = xform(g, can, t=lamp, r=rot)
        cans = [key]
        for sx in (-1.0, 1.0):
            sp = g.combine(sx * 1.8, g.math("ADD", ty, 0.25), g.math("SUBTRACT", tz, 0.2))
            sd = g.vmath("NORMALIZE", g.vmath("SUBTRACT", (0.0, 0.0, 1.2), sp)["Vector"])["Vector"]
            sr = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=sd)["Rotation"]
            cans.append(xform(g, can, t=sp, r=sr))
        hwgeo = part(g, setmat(g, smooth(g, join(g, bar, bar2, *cans)), mats["black"]), 10)
    g.output("Geometry", "GEOMETRY", join(g, cone, hwgeo), desc="Truss, cans and the visible cone")
    return g.finish()


# ---- Club Audience ------------------------------------------------------------------------------------------------------
@once
def chair_shape(mats):
    g = Graph("Club Chair", description="A bistro chair facing +X (backrest at -X): seat, four legs, back panel")
    with g.frame("Seat, legs and back from NK Chamfer Box and NK Rod"):
        seat = xform(g, g.group(chamfer_box(), Size=(0.4, 0.4, 0.04), Chamfer=0.008)["Mesh"], t=(0.0, 0.0, 0.46))
        legs = [g.group(rod(), Start=(sx * 0.17, sy * 0.17, 0.45), End=(sx * 0.19, sy * 0.19, 0.0), Radius=0.014,
                        Resolution=6)["Mesh"] for sx in (-1, 1) for sy in (-1, 1)]
        back = xform(g, g.group(chamfer_box(), Size=(0.03, 0.38, 0.32), Chamfer=0.006)["Mesh"], t=(-0.2, 0.0, 0.74),
                     r=(0.0, -0.12, 0.0))
        ch = setmat(g, join(g, seat, back, *legs), mats["chair"])
    g.output("Mesh", "GEOMETRY", ch, desc="Chair")
    return g.finish()


@once
def person_shape(mats):
    g = Graph("Club Person", description="A seated audience silhouette facing +X: hips on the seat, torso, "
                                         "shoulders, head (club_skin = 1) and forearms resting forward")
    with g.frame("Body (clothes) from NK Rounded Box; head and hands are skin"):
        rb = rounded_box()
        hips = xform(g, g.group(rb, Size=(0.36, 0.36, 0.14), Radius=0.06, Segments=1)["Mesh"], t=(0.02, 0.0, 0.55))
        thighs = xform(g, g.group(rb, Size=(0.34, 0.32, 0.12), Radius=0.05, Segments=1)["Mesh"], t=(0.2, 0.0, 0.52))
        shins = xform(g, g.group(rb, Size=(0.1, 0.3, 0.46), Radius=0.04, Segments=1)["Mesh"], t=(0.36, 0.0, 0.25))
        torso = xform(g, g.group(rb, Size=(0.22, 0.38, 0.5), Radius=0.09, Segments=2)["Mesh"], t=(-0.02, 0.0, 0.85),
                      r=(0.0, 0.08, 0.0))
        arms = xform(g, g.group(rb, Size=(0.3, 0.46, 0.08), Radius=0.035, Segments=1)["Mesh"], t=(0.16, 0.0, 0.76))
        clothes = store(g, join(g, hips, thighs, shins, torso, arms), "club_skin", 0.0, "FLOAT", "POINT")
        head = xform(g, g.node("GeometryNodeMeshUVSphere", Segments=12, Rings=7, Radius=0.1)["Mesh"],
                     t=(0.0, 0.0, 1.24), s=(1.0, 0.9, 1.18))
        neck = xform(g, cyl(g, 0.05, 0.1, 10), t=(0.0, 0.0, 1.12))
        skin = store(g, join(g, head, neck), "club_skin", 1.0, "FLOAT", "POINT")
        person = setmat(g, smooth(g, join(g, clothes, skin)), mats["people"])
    g.output("Mesh", "GEOMETRY", person, desc="Person")
    return g.finish()


@once
def theatre_seat_shape(mats):
    g = Graph("Club Theatre Seat", description="A theatre seat facing +X: cushion, tall back, armrests (velvet)")
    with g.frame("Cushion, back and arms from NK Rounded Box"):
        rb = rounded_box()
        cushion = xform(g, g.group(rb, Size=(0.46, 0.5, 0.1), Radius=0.04, Segments=1)["Mesh"], t=(0.02, 0.0, 0.45))
        back = xform(g, g.group(rb, Size=(0.1, 0.5, 0.62), Radius=0.04, Segments=1)["Mesh"], t=(-0.22, 0.0, 0.78),
                     r=(0.0, -0.15, 0.0))
        arms = [xform(g, g.group(rb, Size=(0.46, 0.06, 0.62), Radius=0.025, Segments=1)["Mesh"],
                      t=(0.0, s * 0.28, 0.31)) for s in (-1, 1)]
        seat = setmat(g, join(g, cushion, back, *arms), mats["seat"])
    g.output("Mesh", "GEOMETRY", seat, desc="Theatre seat")
    return g.finish()


@once
def audience(mats):
    sc = scatter_on_surface()
    g = Graph("Club Audience", description="The house: cafe tables scattered Poisson-spaced over the floor in front "
                                           "of the stage (NK Scatter On Surface), up to four chairs round each table "
                                           "facing it, bottles, pints and candles on the tables and seated people on "
                                           "some chairs, turned toward the stage. Or, with Theatre Rows on, raked rows "
                                           "of velvet seats")
    W = g.input("Room Width", "FLOAT", 10.0, min=4.0, max=40.0, subtype="DISTANCE", desc="Wall to wall")
    D = g.input("Room Depth", "FLOAT", 11.0, min=4.0, max=60.0, subtype="DISTANCE", desc="Back wall to rear wall")
    R = g.input("Riser Height", "FLOAT", 0.3, min=0.0, max=2.0, subtype="DISTANCE", desc="Stage top above the floor")
    SD = g.input("Stage Depth", "FLOAT", 3.4, min=1.0, max=20.0, subtype="DISTANCE", desc="Deck depth")
    wy = g.input("Back Wall Y", "FLOAT", 2.3, min=0.5, max=10.0, subtype="DISTANCE", desc="Back wall position")
    rows = g.input("Theatre Rows", "BOOL", False, desc="Raked rows of theatre seats instead of cafe tables")
    crowd = g.input("Crowd", "FLOAT", 0.6, min=0.0, max=1.0, subtype="FACTOR", desc="Share of seats taken")
    clutter = g.input("Clutter", "FLOAT", 1.0, min=0.0, max=3.0,
                      desc="Scales table density and the chance of drinks on them")
    aisle = g.input("Aisle Width", "FLOAT", 1.3, min=0.0, max=6.0, subtype="DISTANCE",
                    desc="Clear centre aisle through the tables (the web stage's wide camera looks down it)")
    spacing = g.input("Table Spacing", "FLOAT", 1.55, min=0.8, max=5.0, subtype="DISTANCE",
                      desc="Minimum distance between table centres")
    chair_p = g.input("Chair Chance", "FLOAT", 0.8, min=0.0, max=1.0, subtype="FACTOR",
                      desc="Chance each of the four places at a table has a chair")
    candle_p = g.input("Candle Chance", "FLOAT", 0.7, min=0.0, max=1.0, subtype="FACTOR", desc="Candles on tables")
    row_pitch = g.input("Row Pitch", "FLOAT", 0.95, min=0.6, max=2.0, subtype="DISTANCE", desc="Row to row")
    rake = g.input("Rake", "FLOAT", 0.18, min=0.0, max=0.8, subtype="DISTANCE", desc="Rise per row")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    front = g.math("SUBTRACT", wy, SD)
    floor_z = g.math("MULTIPLY", R, -1.0)
    rear = g.math("SUBTRACT", wy, D)
    with g.frame("House area: floor patch from 1.2 m in front of the stage to 1.2 m from the rear wall"):
        aw = g.math("SUBTRACT", W, 1.6)
        ad = g.math("MAXIMUM", g.math("SUBTRACT", g.math("SUBTRACT", front, rear), 2.4), 0.5)
        ay = g.math("SUBTRACT", front, g.math("ADD", 1.2, g.math("MULTIPLY", ad, 0.5)))
        area = xform(g, wall_grid(g, aw, ad, 8, 8), t=g.combine(0.0, ay, floor_z))
    with g.frame("Tables: NK Scatter On Surface, Poisson-spaced by Table Spacing, density by Clutter, none in the aisle"):
        tbl = join(g,
                   xform(g, cyl(g, 0.32, 0.03, 18), t=(0.0, 0.0, 0.73)),
                   g.group(rod(), Start=(0.0, 0.0, 0.0), End=(0.0, 0.0, 0.72), Radius=0.03, Resolution=8)["Mesh"],
                   xform(g, cyl(g, 0.2, 0.02, 14), t=(0.0, 0.0, 0.01)))
        tbl = setmat(g, tbl, mats["table"])
        tbl = g.group(store_local_coords(), Geometry=tbl, **{"Grain Axis": 0})["Geometry"]
        dens = g.math("MULTIPLY", g.math("DIVIDE", 1.0, g.math("MULTIPLY", spacing, spacing)), g.math("MULTIPLY", clutter, 1.4))
        scat = g.group(sc, Surface=area, Instance=tbl, Density=dens, Seed=seed, Align=0.0,
                       **{"Min Distance": spacing})
        in_aisle = g.math("LESS_THAN", g.math("ABSOLUTE", g.separate(position(g))["X"]),
                          g.math("ADD", g.math("MULTIPLY", aisle, 0.5), 0.8))
        tables = g.node("GeometryNodeDeleteGeometry", props={"domain": "INSTANCE"}, Geometry=scat["Instances"],
                        Selection=in_aisle)["Geometry"]
        in_aisle2 = g.math("LESS_THAN", g.math("ABSOLUTE", g.separate(position(g))["X"]),
                           g.math("ADD", g.math("MULTIPLY", aisle, 0.5), 0.8))
        tpts = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=scat["Points"],
                      Selection=in_aisle2)["Geometry"]
        tidx = g.node("GeometryNodeInputIndex")["Index"]
        tpts = store(g, tpts, "club_tpos", position(g), "FLOAT_VECTOR", "POINT")
        tpts = store(g, tpts, "club_tid", tidx, "INT", "POINT")
        tables = part(g, g.node("GeometryNodeRealizeInstances", Geometry=tables)["Geometry"], 11)
    with g.frame("Places: four points round each table at a random turn; drop each by Chair Chance"):
        ring4 = g.node("GeometryNodeMeshToPoints", Mesh=g.node("GeometryNodeMeshCircle", Vertices=4, Radius=0.55)["Mesh"])["Points"]
        yaw = rand(g, 0.0, TAU, seed, 11, tidx)
        places = g.node("GeometryNodeInstanceOnPoints", Points=tpts, Instance=ring4, Rotation=g.combine(0.0, 0.0, yaw))["Instances"]
        places = g.node("GeometryNodeRealizeInstances", Geometry=places)["Geometry"]
        pidx = g.node("GeometryNodeInputIndex")["Index"]
        keep = chance(g, chair_p, seed, 12, pidx)
        places = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=places,
                        Selection=g.node("FunctionNodeBooleanMath", props={"operation": "NOT"}, Boolean=keep))["Geometry"]
    with g.frame("Chairs: one per place, turned to face its table"):
        to_t = g.vmath("SUBTRACT", attr(g, "club_tpos", "FLOAT_VECTOR"), position(g))["Vector"]
        ts = g.separate(to_t)
        cyaw = g.math("ARCTAN2", ts["Y"], ts["X"])
        chairs = g.node("GeometryNodeInstanceOnPoints", Points=places, Instance=g.group(chair_shape(mats))["Mesh"],
                        Rotation=g.combine(0.0, 0.0, g.math("ADD", cyaw, rand(g, -0.3, 0.3, seed, 13, pidx))))["Instances"]
        chairs = store(g, chairs, "nk_rand", rand(g, 0.0, 1.0, seed, 14, pidx), "FLOAT", "INSTANCE")
        chairs = part(g, g.node("GeometryNodeRealizeInstances", Geometry=chairs)["Geometry"], 12)
    with g.frame("People: Crowd share of the chairs, seated and turned toward the stage (+Y)"):
        sit = chance(g, crowd, seed, 15, pidx)
        hue = rand(g, 0.0, 1.0, seed, 16, pidx)
        cloth = g.node("FunctionNodeCombineColor", props={"mode": "HSV"}, Red=hue, Green=rand(g, 0.2, 0.7, seed, 17, pidx),
                       Blue=rand(g, 0.05, 0.35, seed, 18, pidx))["Color"]
        pyaw = g.mix(0.65, cyaw, math.pi / 2)["Result"]
        ppl = g.node("GeometryNodeInstanceOnPoints", Points=places, Selection=sit,
                     Instance=g.group(person_shape(mats))["Mesh"],
                     Rotation=g.combine(0.0, 0.0, g.math("ADD", pyaw, rand(g, -0.35, 0.35, seed, 19, pidx))),
                     Scale=rand(g, 0.92, 1.08, seed, 20, pidx))["Instances"]
        ppl = store(g, ppl, "nk_color", cloth, "FLOAT_COLOR", "INSTANCE")
        ppl = store(g, ppl, "club_tone", rand(g, 0.0, 1.0, seed, 21, pidx), "FLOAT", "INSTANCE")
        ppl = part(g, g.node("GeometryNodeRealizeInstances", Geometry=ppl)["Geometry"], 14)
    with g.frame("Drinks: up to three per table (bottle or pint, tinted), Clutter scales the chance"):
        ring3 = g.node("GeometryNodeMeshToPoints", Mesh=g.node("GeometryNodeMeshCircle", Vertices=3, Radius=0.17)["Mesh"])["Points"]
        dp = g.node("GeometryNodeInstanceOnPoints", Points=tpts, Instance=ring3,
                    Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 22, tidx)))["Instances"]
        dp = g.node("GeometryNodeRealizeInstances", Geometry=dp)["Geometry"]
        didx = g.node("GeometryNodeInputIndex")["Index"]
        dkeep = chance(g, g.math("MULTIPLY", clutter, 0.45, clamp=False), seed, 23, didx)
        dp = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=dp,
                    Selection=g.node("FunctionNodeBooleanMath", props={"operation": "NOT"}, Boolean=dkeep))["Geometry"]
        dp = g.node("GeometryNodeSetPosition", Geometry=dp, Offset=(0.0, 0.0, 0.745))["Geometry"]
        kinds = g.node("GeometryNodeGeometryToInstance")
        g.connect(g.group(glass_shape(mats))["Mesh"], kinds.i("Geometry"))
        g.connect(g.group(bottle_shape(mats))["Mesh"], kinds.i("Geometry"))
        tint = g.node("GeometryNodeIndexSwitch", props={"data_type": "RGBA"})
        tint.b.index_switch_items.new()
        g.connect(g.math("FLOOR", rand(g, 0.0, 2.99, seed, 24, didx)), tint.i("Index"))
        for k, hx in enumerate(("#3E6B1E", "#5A3008", "#D8D2C0")):
            g.connect(lin(hx), tint.i(str(k)))
        drinks = g.node("GeometryNodeInstanceOnPoints", Points=dp, Instance=kinds["Instances"],
                        **{"Pick Instance": True, "Instance Index": g.math("FLOOR", rand(g, 0.0, 1.99, seed, 25, didx))},
                        Rotation=g.combine(0.0, 0.0, rand(g, 0.0, TAU, seed, 26, didx)))["Instances"]
        drinks = store(g, drinks, "nk_color", tint["Output"], "FLOAT_COLOR", "INSTANCE")
        drinks = part(g, g.node("GeometryNodeRealizeInstances", Geometry=drinks)["Geometry"], 13)
    with g.frame("Candles: a glowing jar (NK Glow Glass) in the middle of some tables"):
        jar = g.group(profile_revolve(), Height=0.09, Segments=10, Rings=1, **{"Radius Bottom": 0.035,
                      "Radius Lower": 0.04, "Radius Middle": 0.042, "Radius Upper": 0.04, "Radius Top": 0.036})["Mesh"]
        jar = setmat(g, smooth(g, jar), mats["candle"])
        cpts = g.node("GeometryNodeSetPosition", Geometry=tpts, Offset=(0.0, 0.0, 0.745))["Geometry"]
        candles = g.node("GeometryNodeInstanceOnPoints", Points=cpts, Selection=chance(g, candle_p, seed, 27, tidx),
                         Instance=jar)["Instances"]
        candles = part(g, g.node("GeometryNodeRealizeInstances", Geometry=candles)["Geometry"], 15)
        cafe = join(g, tables, chairs, ppl, drinks, candles)
    with g.frame("Theatre rows: a grid of seats over the house, each row Rake higher, Crowd share occupied"):
        pitch = 0.56
        nseat = g.math("FLOOR", g.math("DIVIDE", g.math("SUBTRACT", W, 2.4), pitch))
        nrow = g.math("MAXIMUM", g.math("FLOOR", g.math("DIVIDE", ad, row_pitch)), 1.0)
        grid = g.node("GeometryNodeMeshGrid", **{"Size X": g.math("MULTIPLY", g.math("SUBTRACT", nseat, 1.0), pitch),
                                                  "Size Y": g.math("MULTIPLY", g.math("SUBTRACT", nrow, 1.0), row_pitch),
                                                  "Vertices X": nseat, "Vertices Y": nrow})["Mesh"]
        rp = g.node("GeometryNodeMeshToPoints", Mesh=grid)["Points"]
        ry = g.separate(position(g))["Y"]
        rowk = g.math("ROUND", g.math("DIVIDE", g.math("SUBTRACT", g.math("MULTIPLY", g.math("SUBTRACT", nrow, 1.0),
                                                                                   g.math("MULTIPLY", row_pitch, 0.5)), ry), row_pitch))
        row_aisle = g.math("LESS_THAN", g.math("ABSOLUTE", g.separate(position(g))["X"]), g.math("MULTIPLY", aisle, 0.5))
        rp = g.node("GeometryNodeDeleteGeometry", props={"domain": "POINT"}, Geometry=rp, Selection=row_aisle)["Geometry"]
        rp = g.node("GeometryNodeSetPosition", Geometry=rp,
                    Offset=g.combine(0.0, g.math("SUBTRACT", front, g.math("ADD", 1.6, g.math("MULTIPLY", g.math("SUBTRACT", nrow, 1.0),
                                                                                                   g.math("MULTIPLY", row_pitch, 0.5)))),
                                     g.math("ADD", floor_z, g.math("MULTIPLY", rowk, rake))))["Geometry"]
        ridx = g.node("GeometryNodeInputIndex")["Index"]
        seats = g.node("GeometryNodeInstanceOnPoints", Points=rp, Instance=g.group(theatre_seat_shape(mats))["Mesh"],
                       Rotation=(0.0, 0.0, math.pi / 2))["Instances"]
        seats = store(g, seats, "club_seat_color", lin("#6B0F1E"), "FLOAT_COLOR", "INSTANCE")
        seats = part(g, g.node("GeometryNodeRealizeInstances", Geometry=seats)["Geometry"], 18)
        rsit = chance(g, crowd, seed, 31, ridx)
        rhue = rand(g, 0.0, 1.0, seed, 32, ridx)
        rcloth = g.node("FunctionNodeCombineColor", props={"mode": "HSV"}, Red=rhue, Green=rand(g, 0.2, 0.7, seed, 33, ridx),
                        Blue=rand(g, 0.05, 0.35, seed, 34, ridx))["Color"]
        rppl = g.node("GeometryNodeInstanceOnPoints", Points=rp, Selection=rsit, Instance=g.group(person_shape(mats))["Mesh"],
                      Rotation=g.combine(0.0, 0.0, g.math("ADD", math.pi / 2, rand(g, -0.2, 0.2, seed, 35, ridx))),
                      Scale=rand(g, 0.92, 1.08, seed, 36, ridx))["Instances"]
        rppl = store(g, rppl, "nk_color", rcloth, "FLOAT_COLOR", "INSTANCE")
        rppl = store(g, rppl, "club_tone", rand(g, 0.0, 1.0, seed, 37, ridx), "FLOAT", "INSTANCE")
        rppl = part(g, g.node("GeometryNodeRealizeInstances", Geometry=rppl)["Geometry"], 14)
        rowgeo = join(g, seats, rppl)
    g.output("Geometry", "GEOMETRY", switch(g, "GEOMETRY", rows, cafe, rowgeo), desc="The house")
    return g.finish()


# ---- Club Set (the modifier) ------------------------------------------------------------------------------------------
PRIMARY = [
    # name, type, default, min, max, subtype, description
    ("Room Width", "FLOAT", 10.0, 4.0, 40.0, "DISTANCE", "Wall to wall: small dive 8-10, theatre 18+"),
    ("Room Depth", "FLOAT", 11.0, 4.0, 60.0, "DISTANCE", "Back wall to rear wall: how deep the house runs"),
    ("Ceiling Height", "FLOAT", 3.8, 2.0, 20.0, "DISTANCE", "Ceiling above the stage top (basement ~2.6)"),
    ("Riser Height", "FLOAT", 0.3, 0.0, 2.0, "DISTANCE", "Stage top above the house floor"),
    ("Theatre Rows", "BOOL", False, None, None, None, "Raked rows of seats instead of cafe tables"),
    ("Crowd", "FLOAT", 0.6, 0.0, 1.0, "FACTOR", "Share of seats taken (open mic: 0.2)"),
    ("Clutter", "FLOAT", 1.0, 0.0, 3.0, None, "More tables and more drinks on them"),
    ("Paint Cover", "FLOAT", 0.15, 0.0, 1.0, "FACTOR", "0 bare brick, 1 a painted wall"),
    ("Side Curtain Width", "FLOAT", 1.6, 0.0, 10.0, "DISTANCE", "Velvet each side of the stage (0 = none)"),
    ("Neon Color", "COLOR", lin("#FF2FA0"), None, None, None, "Colour of the neon sign"),
    ("Seed", "INT", 0, 0, 100000, None, "Changes every random choice (tables, crowd, drinks)"),
]


def build():
    mats = materials()
    parts = [("Room", room(mats)), ("Stage", stage(mats)), ("Curtains", curtains(mats)), ("Props", props(mats)),
             ("Neon", neon(mats)), ("Spot", spot(mats)), ("Audience", audience(mats))]
    g = Graph(NAME, modifier=True,
              description="A FUNNIER comedy-club stage set from a few controls: room, riser, brick wall, curtains, "
                          "mic stand and stool, a blank neon sign, a spotlight cone, and a house of cafe tables or "
                          "theatre rows with a seated crowd. Every face carries club_part for export")
    ui = {}
    for name, stype, dv, lo, hi, sub, desc in PRIMARY:
        kw = {}
        if lo is not None:
            kw.update(min=lo, max=hi)
        if sub:
            kw["subtype"] = sub
        ui[name] = g.input(name, stype, dv, panel="Primary", desc=desc, **kw)
    sockmap = {"NodeSocketFloat": "FLOAT", "NodeSocketInt": "INT", "NodeSocketBool": "BOOL",
               "NodeSocketColor": "COLOR", "NodeSocketVector": "VECTOR"}
    for label, tree in parts:
        for it in tree.interface.items_tree:
            if it.item_type != "SOCKET" or it.in_out != "INPUT" or it.name in ui:
                continue
            dv = it.default_value
            dv = tuple(dv) if hasattr(dv, "__len__") else dv
            kw = {k: getattr(it, a) for k, a in (("min", "min_value"), ("max", "max_value")) if hasattr(it, a)}
            if getattr(it, "subtype", "NONE") != "NONE":
                kw["subtype"] = it.subtype
            ui[it.name] = g.input(it.name, sockmap[it.socket_type], dv, panel=label, desc=it.description, **kw)
    for label, _ in parts:
        if label in g._panels:
            g._panels[label].default_closed = True
    outs = []
    with g.frame("Parts: every part reads the shared controls by name (one Seed, one Room Width, ...)"):
        for label, tree in parts:
            n = g.group(tree, label=label)
            for s in n.b.inputs:
                if s.enabled and s.name in ui:
                    g.connect(ui[s.name], s)
            outs.append(n["Geometry"])
    with g.frame("Join the parts (each already realized and tagged with club_part)"):
        geo = join(g, *outs)
    g.output("Geometry", "GEOMETRY", geo)
    return g.finish()


# ---- scene: lights, cameras, compositor ----------------------------------------------------------------------------------
def load_preset(name):
    p = pathlib.Path(name)
    if not p.exists():
        hits = sorted((HERE / "presets").glob(f"*{name}*.json"))
        if not hits:
            raise SystemExit(f"no preset {name!r} in {HERE / 'presets'}")
        p = hits[0]
    data = json.loads(p.read_text())
    inputs = {k: (tuple(v) if isinstance(v, list) else v) for k, v in data.items() if not k.startswith("_")}
    look = data.get("_look", {})
    return p.stem, inputs, look


def value(mod, name):
    return inspect.get_modifier_inputs(mod)[name]


def add_light(sc, name, kind, loc, energy, color, target=None, size=None, spot_deg=None, blend=0.3):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color[:3]
    if size is not None and hasattr(ld, "shadow_soft_size"):
        ld.shadow_soft_size = size
    if kind == "AREA" and size is not None:
        ld.size = size
    if kind == "SPOT":
        ld.spot_size = math.radians(spot_deg or 30)
        ld.spot_blend = blend
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    sc.collection.objects.link(ob)
    if target is not None:
        from mathutils import Vector
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def lights(sc, mod, look):
    """Scene lights that match the graph: key spot at the lamp can, rims, neon spill, house glow, candles."""
    H, throw, rad = value(mod, "Ceiling Height"), value(mod, "Spot Throw"), value(mod, "Spot Radius")
    W, D, wy, R = value(mod, "Room Width"), value(mod, "Room Depth"), value(mod, "Back Wall Y"), value(mod, "Riser Height")
    neon_c = value(mod, "Neon Color")
    lamp = (0.45, -throw, H - 0.45)
    tgt = (0.0, 0.15, 0.0)
    dist = math.dist(lamp, tgt)
    cone = 2 * math.degrees(math.atan2(rad * 1.1, dist))
    add_light(sc, "Key Spot", "SPOT", lamp, look.get("key", 900.0) * (dist / 6.6) ** 2,
              S.srgb(look.get("key_color", "#FFF0DC")), tgt, size=0.08, spot_deg=cone, blend=0.25)
    for sx, c in ((-1, look.get("rim_left", "#40D0FF")), (1, look.get("rim_right", "#FF40C0"))):
        add_light(sc, f"Rim {sx}", "SPOT", (sx * 3.0, wy - 0.7, min(H - 0.3, 4.2)), look.get("rim", 160.0), S.srgb(c),
                  (0.0, 0.0, 1.3), size=0.2, spot_deg=50, blend=0.6)
    add_light(sc, "Neon Spill", "AREA", (0.0, wy - 0.6, min(3.25, H - 0.9)), look.get("neon", 60.0), neon_c,
              (0.0, wy, min(3.25, H - 0.9)), size=3.0)
    add_light(sc, "Wall Wash", "AREA", (0.0, wy - 1.2, H - 0.1), look.get("wash", 80.0),
              S.srgb(look.get("wash_color", "#FFA080")), (0.0, wy, 1.0), size=4.0)
    add_light(sc, "House Glow", "AREA", (0.0, wy - D * 0.6, H - 0.05), look.get("house", 120.0),
              S.srgb(look.get("house_color", "#FFB070")), (0.0, wy - D * 0.6, -R), size=max(3.0, W * 0.6))
    w = bpy.data.worlds.new("Club World")
    w.color = (0.0, 0.0, 0.0)
    nt = w.node_tree
    nt.nodes["Background"].inputs["Color"].default_value = (*S.srgb(look.get("ambient", "#120C18")), 1.0)
    nt.nodes["Background"].inputs["Strength"].default_value = look.get("ambient_strength", 0.6)
    sc.world = w


def cameras(sc, mod):
    wy, D, R = value(mod, "Back Wall Y"), value(mod, "Room Depth"), value(mod, "Riser Height")
    H = value(mod, "Ceiling Height")
    back = wy - D
    wide_y = max(back + 0.6, -8.2)
    rows = value(mod, "Theatre Rows")
    wide = S.camera("Wide", lens=24.0, loc=(0.25, wide_y, min(1.85 + (1.0 if rows else 0.0), H - 0.9)),
                    target=(0.0, 0.0, 1.1))
    eye = S.camera("Performer Eye", lens=20.0, loc=(0.0, 0.05, 1.62), target=(0.0, back, 0.7 - R))
    return {"wide": wide[0], "eye": eye[0]}


def post(sc, look):
    sc.render.film_transparent = False
    sc.view_layers[0].use_pass_mist = True
    ms = sc.world.mist_settings
    ms.start, ms.depth, ms.falloff = look.get("haze_start", 1.5), look.get("haze_depth", 14.0), "LINEAR"
    g = Graph(f"Club Post {sc.name}", kind="COMPOSITOR",
              description="Stage haze by the Mist pass (NK Haze Over Sky with a dark sky), then NK Soft Glow on the "
                          "neon, candles and the spot")
    with g.frame("Render layers, haze, glow"):
        rl = g.node("CompositorNodeRLayers")
        rl.b.scene = sc
        hz = g.group(haze_over_sky(), Image=rl["Image"], Mist=rl["Mist"],
                     **{"Haze Color": lin(look.get("haze_color", "#2A2230")), "Haze Amount": look.get("haze", 0.5),
                        "Sky Top": lin("#000000"), "Sky Horizon": lin("#05030A"), "Horizon": 0.5, "Top": 0.9})
        gl = g.group(soft_glow(), Image=hz["Image"], Threshold=look.get("glow_threshold", 1.2),
                     Strength=look.get("glow", 0.35), Size=0.7, Tint=(1.0, 0.9, 0.95, 1.0))
    g.output("Image", "COLOR", gl["Image"])
    sc.compositing_node_group = g.finish()


def render_setup(sc, width, height, samples):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 16
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"


# ---- export ----------------------------------------------------------------------------------------------------------
BAKE_PARTS = {1: 1024, 2: 2048, 3: 1024, 4: 1024, 5: 1024, 11: 512, 12: 512}
EMISSIVE_PARTS = {8, 9, 15, 16}


def split_parts(src, sc):
    """Apply the modifier to a mesh copy and split it by club_part into one named object per part.

    Fast path: encode club_part as the material index, separate by material (C code), then restore each
    piece's original materials from a stored index, so baking still sees the real shaders."""
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    ev = src.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    mats = list(me.materials)
    n = len(me.polygons)
    orig = np.zeros(n, dtype=np.int32)
    me.polygons.foreach_get("material_index", orig)
    pa = me.attributes.get("club_part")
    parts = np.zeros(n, dtype=np.int32)
    if pa is not None:
        pa.data.foreach_get("value", parts)
    keep = me.attributes.new("club_orig_mat", "INT", "FACE")
    keep.data.foreach_set("value", orig)
    uniq = sorted(set(parts.tolist()))
    me.materials.clear()
    for pid in uniq:
        me.materials.append(bpy.data.materials.get(f"__part_{pid}") or bpy.data.materials.new(f"__part_{pid}"))
    lut = np.zeros(max(uniq) + 1, dtype=np.int32)
    for i, pid in enumerate(uniq):
        lut[pid] = i
    me.polygons.foreach_set("material_index", lut[parts])
    whole = bpy.data.objects.new("club_whole", me)
    sc.collection.objects.link(whole)
    for o in sc.objects:
        o.select_set(False)
    whole.select_set(True)
    bpy.context.view_layer.objects.active = whole
    with bpy.context.temp_override(active_object=whole, object=whole, selected_objects=[whole],
                                   selected_editable_objects=[whole]):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
    objs = {}
    for ob in [o for o in sc.objects if o.type == "MESH" and o.name.startswith("club_whole")]:
        m2 = ob.data
        if not len(m2.polygons):
            continue
        slot = m2.materials[m2.polygons[0].material_index].name
        pid = int(slot.split("_")[-1])
        k = len(m2.polygons)
        idx = np.zeros(k, dtype=np.int32)
        m2.attributes["club_orig_mat"].data.foreach_get("value", idx)
        m2.materials.clear()
        for mat in mats:
            m2.materials.append(mat)
        m2.polygons.foreach_set("material_index", idx)
        m2.update()
        name = PARTS.get(pid, f"club_part_{pid}")
        ob.name = name
        m2.name = name
        objs[pid] = ob
    return objs


def principled(name, color=(0.5, 0.5, 0.5, 1), rough=0.7, metal=0.0, emit=None, emit_strength=0.0, image=None,
               alpha=1.0):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    pb = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    pb.inputs["Base Color"].default_value = color
    pb.inputs["Roughness"].default_value = rough
    pb.inputs["Metallic"].default_value = metal
    if image is not None:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = image
        nt.links.new(tx.outputs["Color"], pb.inputs["Base Color"])
    if emit is not None:
        pb.inputs["Emission Color"].default_value = emit
        pb.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1.0:
        pb.inputs["Alpha"].default_value = alpha
    return m


def mean_attr_color(ob, name, fallback):
    a = ob.data.color_attributes.get(name) or ob.data.attributes.get(name)
    if not a or not len(a.data):
        return fallback
    n = len(a.data)
    acc = [0.0, 0.0, 0.0]
    for d in a.data:
        c = d.color
        for i in range(3):
            acc[i] += c[i]
    return (acc[0] / n, acc[1] / n, acc[2] / n, 1.0)


def bake_part(sc, ob, size, workdir):
    """Smart-UV the part and bake its diffuse colour (albedo only) into a JPEG-ready image."""
    bpy.context.view_layer.objects.active = ob
    for o in sc.objects:
        o.select_set(False)
    ob.select_set(True)
    ob.data.uv_layers.new(name="BakeUV")
    ob.data.uv_layers.active = ob.data.uv_layers["BakeUV"]
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
        bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(f"{ob.name}_albedo", size, size)
    for mat in ob.data.materials:
        if mat is None or mat.node_tree is None:
            continue
        nt = mat.node_tree
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        nt.nodes.active = tx
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    sc.render.bake.margin = 4
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.bake(type="DIFFUSE")
    path = pathlib.Path(workdir, f"{ob.name}.png")
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    return img


def vertex_colors(objs):
    """Crowd parts carry their colour per vertex instead of a texture (a baked atlas of 100k faces is mush):
    people = clothes (nk_color) or skin (club_skin, club_tone), bottles = nk_color, seats = club_seat_color."""
    import numpy as np

    def read(me, name, comps):
        a = me.attributes.get(name)
        n = len(me.vertices)
        if a is None or a.domain != "POINT":
            return None
        buf = np.zeros(n * comps, dtype=np.float32)
        a.data.foreach_get("color" if comps == 4 else "value", buf)
        return buf.reshape(n, comps) if comps > 1 else buf

    lo, hi = np.array(lin("#4A2C1E")[:3]), np.array(lin("#D9A88A")[:3])
    for pid, ob in objs.items():
        me = ob.data
        n = len(me.vertices)
        if pid == 14:
            cloth, skin, tone = read(me, "nk_color", 4), read(me, "club_skin", 1), read(me, "club_tone", 1)
            if cloth is None:
                continue
            skin = np.zeros(n) if skin is None else skin
            tone = np.full(n, 0.5) if tone is None else tone
            sk = lo[None, :] * (1 - tone[:, None]) + hi[None, :] * tone[:, None]
            rgb = cloth[:, :3] * (1 - skin[:, None]) + sk * skin[:, None]
        elif pid in (13, 18):
            c = read(me, "nk_color" if pid == 13 else "club_seat_color", 4)
            if c is None:
                continue
            rgb = c[:, :3]
        else:
            continue
        col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        col.data.foreach_set("color", np.concatenate([rgb, np.ones((n, 1))], axis=1).astype(np.float32).ravel())
        me.color_attributes.active_color = col
        me["club_vcol"] = 1


CROWD_PARTS = (14, 18, 12, 13)        # audience, theatre seats, chairs, bottles: the bulk of a big house


def decimate_crowd(objs, budget):
    """Keep the GLB light: if the set has more faces than budget, collapse-decimate the crowd parts (never the
    room, stage, props or sign) by one shared ratio, at least 0.2."""
    total = sum(len(o.data.polygons) for o in objs.values())
    heavy = [objs[p] for p in CROWD_PARTS if p in objs]
    hf = sum(len(o.data.polygons) for o in heavy)
    if total <= budget or not hf:
        return 1.0
    ratio = max(0.2, (budget - (total - hf)) / hf)
    for ob in heavy:
        md = ob.modifiers.new("Decimate", "DECIMATE")
        md.ratio = ratio
        with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.object.modifier_apply(modifier=md.name)
    print(f"DECIMATE crowd parts to {ratio:.2f} ({total} faces > budget {budget})")
    return ratio


def export_glb(sc, holder, path, bake=0, workdir="/tmp", budget=60000):
    """Realize + split by club_part, swap every material for a glTF-friendly Principled (baked albedo where
    baking is on, attribute or flat colour otherwise, emission for neon/candles/exit), export GLB (Y up)."""
    objs = split_parts(holder, sc)
    holder.hide_render = True
    holder.hide_set(True)
    vertex_colors(objs)
    decimate_crowd(objs, budget)
    neon_c = value(holder.modifiers[0], "Neon Color")
    flat = {2: lin("#5A2C22"), 1: lin("#16120F"), 3: lin("#1A1418"), 4: lin("#2E1C10"), 5: lin("#5E0B16"),
            6: lin("#202024"), 7: lin("#2A2A2E"), 10: lin("#0E0D10"), 11: lin("#2A1810"), 12: lin("#2C1A12"),
            13: lin("#3E6B1E"), 14: lin("#2A2A30"), 17: lin("#4A4640"), 18: lin("#6B0F1E"), 19: lin("#E9E6DC"),
            20: lin("#121016")}
    attr_col = {2: "club_tint", 1: "club_floor_color", 3: "club_house_color", 5: "club_curtain_color",
                14: "nk_color", 13: "nk_color", 18: "club_seat_color"}
    for pid, ob in objs.items():
        me = ob.data
        img = None
        if bake and pid in BAKE_PARTS and len(me.polygons):
            img = bake_part(sc, ob, min(BAKE_PARTS[pid], bake), workdir)
        if pid == 8:
            mat = principled("club_neon_mat", color=(0, 0, 0, 1), emit=(*neon_c[:3], 1.0), emit_strength=6.0)
        elif pid == 9:
            mat = principled("club_beam_mat", color=(1, 0.95, 0.85, 1), emit=(1, 0.95, 0.85, 1), emit_strength=0.5,
                             alpha=0.12)
            mat.surface_render_method = "BLENDED" if hasattr(mat, "surface_render_method") else None
        elif pid == 15:
            mat = principled("club_candle_mat", color=lin("#5A1A10"), emit=lin("#FF9A3C"), emit_strength=3.0)
        elif pid == 16:
            mat = principled("club_exit_mat", color=(0, 0, 0, 1), emit=lin("#21FF6A"), emit_strength=4.0)
        elif img is not None:
            mat = principled(f"{ob.name}_mat", rough=0.75, image=img)
        elif me.get("club_vcol"):
            mat = principled(f"{ob.name}_mat", color=(1, 1, 1, 1), rough=0.3 if pid == 13 else 0.8)
            ca = mat.node_tree.nodes.new("ShaderNodeVertexColor")
            ca.layer_name = "Col"
            mat.node_tree.links.new(ca.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        else:
            c = mean_attr_color(ob, attr_col[pid], flat.get(pid)) if pid in attr_col else flat.get(pid, lin("#555555"))
            metal = 1.0 if pid in (6, 7) else 0.0
            mat = principled(f"{ob.name}_mat", color=c, rough=0.35 if metal else 0.75, metal=metal)
        me.materials.clear()
        me.materials.append(mat)
        for poly in me.polygons:
            poly.material_index = 0
        if not bake:
            for uv in list(me.uv_layers):
                me.uv_layers.remove(uv)
    # only the crowd's "Col" may reach glTF as COLOR_0 (three.js multiplies any COLOR_0 into the albedo)
    for ob in objs.values():
        me = ob.data
        for ca in [c for c in me.color_attributes if c.name != "Col"]:
            me.color_attributes.remove(ca)
        for at in [a for a in me.attributes if a.data_type in {"FLOAT_COLOR", "BYTE_COLOR"} and a.name != "Col"]:
            me.attributes.remove(at)
    # an empty at the key lamp, so the web stage can hang its own spot and cone where this room's lamp is
    mod = holder.modifiers[0]
    lamp = bpy.data.objects.new("club_key_lamp", None)
    lamp.location = (0.45, -value(mod, "Spot Throw"), value(mod, "Ceiling Height") - 0.45)
    sc.collection.objects.link(lamp)
    names = {ob.name for ob in objs.values()} | {lamp.name}
    for o in sc.objects:
        o.select_set(o.name in names)
    kw = dict(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
              export_image_format="JPEG", export_jpeg_quality=82, export_attributes=False, export_cameras=False,
              export_lights=False, export_extras=False, export_materials="EXPORT")
    try:
        bpy.ops.export_scene.gltf(**kw, export_vertex_color="MATERIAL")
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)
    return {PARTS.get(pid, pid): len(ob.data.polygons) for pid, ob in objs.items()}


# ---- main --------------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="")
    ap.add_argument("--preset", default="dive")
    ap.add_argument("--out", default="")
    ap.add_argument("--render", default="", help="directory for stills")
    ap.add_argument("--views", default="wide,eye")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--glb", default="")
    ap.add_argument("--bake", type=int, default=0, help="bake albedo textures up to this size (0 = flat colours)")
    ap.add_argument("--face-budget", type=int, default=60000, help="decimate the crowd above this many faces")
    ap.add_argument("--turntable", default="", help="directory for a camera-move frame sequence")
    ap.add_argument("--frames", type=int, default=240)
    ap.add_argument("--tt-width", type=int, default=1280)
    ap.add_argument("--tt-samples", type=int, default=24)
    ap.add_argument("--chunk", default="0/1", help="K/N: render the K-th of N frame ranges of the camera move")
    ap.add_argument("--dump", default="", help="write the graph dump JSON here")
    a = ap.parse_args(_ARGV)

    pname, inputs, look = load_preset(a.preset)
    sc = S.reset()
    sc.name = "Club"
    group = build()
    ob, mod = S.holder("Club", None, group, sc=sc)
    inspect.set_modifier_inputs(mod, inputs)
    sc.frame_set(1)
    st = inspect.evaluated_stats(ob, sc)
    warn = [w.message for w in mod.node_warnings]
    lint = inspect.check_groups("Club ") + inspect.check_groups("NK ")
    print(f"PRESET {pname}: verts {st['verts']} faces {st['faces']} warnings {warn}")
    print("LINT", len(lint))
    for p in lint:
        print("  ", p)
    if a.dump:
        inspect.dump_groups(a.dump, prefix="Club ")
    lights(sc, mod, look)
    cams = cameras(sc, mod)
    post(sc, look)
    if a.out:
        out = pathlib.Path(a.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
        print("SAVED", out)
    if a.render:
        rd = pathlib.Path(a.render).resolve()
        rd.mkdir(parents=True, exist_ok=True)
        render_setup(sc, a.width, round(a.width * 9 / 16 / 2) * 2, a.samples)
        if bpy.context.window:
            bpy.context.window.scene = sc
        for v in a.views.split(","):
            inspect.set_modifier_inputs(mod, {"Show Beam": v != "eye"})
            sc.camera = cams[v]
            sc.render.filepath = str(rd / f"club_{pname}_{v}.png")
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print("RENDERED", sc.render.filepath)
        inspect.set_modifier_inputs(mod, {"Show Beam": True})
    if a.turntable:
        # a slow push-in that sweeps across the house: keyframed once, rendered as an animation with persistent
        # data (one BVH build); --chunk K/N renders the K-th of N equal frame ranges (CI renders them in parallel)
        td = pathlib.Path(a.turntable).resolve()
        td.mkdir(parents=True, exist_ok=True)
        render_setup(sc, a.tt_width, round(a.tt_width * 9 / 16 / 2) * 2, a.tt_samples)
        sc.render.use_persistent_data = True
        cam = cams["wide"]
        cam.constraints.clear()
        H = value(mod, "Ceiling Height")
        back = value(mod, "Back Wall Y") - value(mod, "Room Depth")
        from mathutils import Vector
        n = a.frames
        for f in range(n):
            u = f / max(n - 1, 1)
            e = 0.5 - 0.5 * math.cos(math.pi * u)                         # ease in/out
            ang = math.radians(-38 + 76 * e)                              # sweep across the house
            r = 6.4 - 2.6 * e                                             # and push in
            loc = Vector((r * math.sin(ang), max(back + 0.6, -r * math.cos(ang)), min(H - 0.6, 2.1 - 0.5 * e)))
            tgt = Vector((0.0, 0.0, 1.15 + 0.15 * e))
            cam.location = loc
            cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
            cam.keyframe_insert("location", frame=f + 1)
            cam.keyframe_insert("rotation_euler", frame=f + 1)
        k, nch = (int(x) for x in a.chunk.split("/"))
        per = math.ceil(n / nch)
        sc.frame_start, sc.frame_end = 1 + k * per, min(n, (k + 1) * per)
        sc.camera = cam
        sc.render.filepath = str(td / "tt_")
        if bpy.context.window:
            bpy.context.window.scene = sc
        bpy.ops.render.render(animation=True, scene=sc.name)
        print("TURNTABLE", td, sc.frame_start, sc.frame_end)
    if a.glb:
        p = pathlib.Path(a.glb).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        bake_dir = p.parent / f"{p.stem}_bake"
        bake_dir.mkdir(exist_ok=True)
        counts = export_glb(sc, ob, p, bake=a.bake, workdir=str(bake_dir), budget=a.face_budget)
        print("GLB", p, p.stat().st_size, json.dumps(counts))


main()
