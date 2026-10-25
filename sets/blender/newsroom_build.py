"""FUNNIER / Goodnight News newsroom set as ONE procedural Geometry Nodes graph (Blender 5.2+).

Built with nodekit + the NK node-group library from video-to-blender (MIT, github.com/gokayfem/video-to-blender),
the same way as the comedy club (sets/blender/club_build.py).

    blender -b --factory-startup --python sets/blender/newsroom_build.py -- \
        --skill <video-to-blender>/skills/procedural-blender-nodes \
        --preset late-night --out out/newsroom_late-night.blend \
        [--anchor static/avatars/default-v1.vrm] [--wall-card card.png] [--brand-card brand.png] \
        [--render out/renders --views wide,medium,close --width 1600 --samples 96] \
        [--glb out/newsroom-late-night.glb [--bake 1024]]

One modifier group, "News Set", builds the studio on an empty mesh object. Its parts are groups an artist can open:

    News Room        floor (polished resin, seams), riser disc with an LED edge, ceiling, side flats with glow strips
    News Backdrop    the depth behind the wall: a slatted back wall, OR glass panes with mullions and a night
                     skyline of lit windows far behind (bokeh), OR two windows onto a moonlit sky flanking the wall
    News Desk        curved anchor desk (arc swept profiles): front panel, top, kick plinth, a blank brand band
                     (material slot news_desk_brand, UVs 0..1) and an LED lip
    News Wall        the video wall: LED tiles (or one framed screen) that together carry ONE blank material slot
                     news_wall_screen with UVs 0..1 across the whole wall, so the web stage paints headlines on it
    News Practicals  lighting grid (truss + cans), pendant globes, desk lamp and side table lamps with glowing shades
    News Furniture   anchor chairs (one part per seat, so the web can hide an empty seat), papers, mug, monitor,
                     bookshelves, potted plants

Coordinates: metres, Z up, floor at z = 0. The anchors sit at (+-0.75, 0.55) facing -Y, the desk arc is centred on
(0, 1.75) with its front 2.0 m out, the wall centre is at (0, 2.7, 2.05): exactly the three.js news-studio layout
(packages/stage-runtime/src/sets/definitions.ts) after glTF's -Y -> +Z, so the GLB drops straight in.

Every face carries an INT attribute news_part; the exporter splits the realized mesh by it into named nodes.
Camera marks (cam_wide, cam_medium, cam_close, cam_wall) are exported as glTF cameras.
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
    raise SystemExit("newsroom_build: pass --skill <video-to-blender>/skills/procedural-blender-nodes (or $V2B_SKILL)")
sys.path.insert(0, _SKILL)
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from nodekit import inspect  # noqa: E402
from nodekit import scene as S  # noqa: E402
from nodekit.graph import Graph, once  # noqa: E402
from nodekit.materials import material as new_material  # noqa: E402
from library.shapes import chamfer_box, rod, profile_revolve, rounded_box  # noqa: E402
from library.materials import make_material, stucco, wood_grain, felt, glow_glass, attribute_tint, lin  # noqa: E402
from library.post import soft_glow  # noqa: E402
import newsroom_looks as LK  # noqa: E402
import newsroom_cameras as CK  # noqa: E402

NAME = "News Set"
TAU = 2.0 * math.pi
PARTS = {  # news_part id -> glTF node name
    1: "news_floor", 2: "news_riser", 3: "news_backwall", 4: "news_flats", 5: "news_desk", 6: "news_desk_top",
    7: "news_desk_brand", 8: "news_wall_frame", 9: "news_wall_screen", 10: "news_glow", 11: "news_grid",
    12: "news_practicals", 13: "news_lampglow", 14: "news_skyline", 15: "news_glass", 16: "news_chair_anchor1",
    17: "news_chair_anchor2", 18: "news_props", 19: "news_shelves", 20: "news_plants", 21: "news_sky",
    22: "news_ceiling", 23: "news_books", 24: "news_desk_trim", 25: "news_globe", 26: "news_laptop",
    27: "news_pillars",
}
SEATS = {"anchor1": (0.75, 0.55), "anchor2": (-0.75, 0.55)}   # Blender XY of the three.js seats


# ---- node idioms (python helpers, not groups) ------------------------------------------------------------------
def store(g, geo, name, value, dtype="FLOAT", domain="POINT"):
    return g.node("GeometryNodeStoreNamedAttribute", props={"data_type": dtype, "domain": domain},
                  Geometry=geo, Name=name, Value=value)["Geometry"]


def rand(g, lo, hi, seed, k, ident=None, dtype="FLOAT"):
    n = g.node("FunctionNodeRandomValue", props={"data_type": dtype}, Min=lo, Max=hi,
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
    """Tag every face of geo with news_part = pid (the exporter splits by it)."""
    return store(g, geo, "news_part", pid, "INT", "FACE")


def box(g, size, center=(0.0, 0.0, 0.0)):
    m = g.node("GeometryNodeMeshCube", Size=size)["Mesh"]
    return xform(g, m, t=center)


def position(g):
    return g.node("GeometryNodeInputPosition")["Position"]


def grid(g, sx, sy, nx=2, ny=2):
    return g.node("GeometryNodeMeshGrid", **{"Size X": sx, "Size Y": sy, "Vertices X": nx, "Vertices Y": ny})["Mesh"]


def arc_sweep(g, radius, span, width, height, res=48):
    """A curved slab: an arc of `radius` (centred on -Y, `span` radians wide) swept with a width x height
    rectangle (width radial, height along Z), caps filled. Centred on the origin in Z."""
    arc = g.node("GeometryNodeCurveArc", Resolution=res, Radius=radius,
                 **{"Start Angle": g.math("SUBTRACT", -math.pi / 2, g.math("MULTIPLY", span, 0.5)),
                    "Sweep Angle": span})["Curve"]
    prof = g.node("GeometryNodeCurvePrimitiveQuadrilateral", Width=width, Height=height)["Curve"]
    return g.node("GeometryNodeCurveToMesh", Curve=arc, **{"Profile Curve": prof, "Fill Caps": True})["Mesh"]


def planar_uv(g, geo, x0, width, z0, height):
    """UVMap from world X/Z: u = (x - x0) / width, v = (z - z0) / height (a front-facing planar projection)."""
    p = g.separate(position(g))
    u = g.math("DIVIDE", g.math("SUBTRACT", p["X"], x0), width)
    v = g.math("DIVIDE", g.math("SUBTRACT", p["Z"], z0), height)
    return store(g, geo, "UVMap", g.combine(u, v, 0.0), "FLOAT2", "CORNER")


def realize(g, geo):
    return g.node("GeometryNodeRealizeInstances", Geometry=geo)["Geometry"]


def line_points(g, count, start, end):
    m = g.node("GeometryNodeMeshLine", props={"mode": "END_POINTS"}, Count=count,
               **{"Start Location": start, "Offset": end})["Mesh"]
    return g.node("GeometryNodeMeshToPoints", Mesh=m)["Points"]


# ---- materials ------------------------------------------------------------------------------------------------
@once
def floor_paint():
    g = Graph("News Floor Paint", kind="SHADER",
              description="Polished studio floor: large resin tiles (Brick Texture, square) with faint seams, a "
                          "slow cloudy mottle and roughness that rises in the seams (news_floor_color, news_gloss)")
    vec = g.input("Vector", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="Texture coordinate in metres")
    col = g.input("Color", "COLOR", lin("#101218"), desc="Floor colour (news_floor_color)")
    gloss = g.input("Gloss", "FLOAT", 0.7, min=0.0, max=1.0, subtype="FACTOR", desc="0 matte, 1 mirror-like")
    tile = g.input("Tile Size", "FLOAT", 1.2, min=0.1, max=10.0, subtype="DISTANCE", desc="Square tile size")
    with g.frame("Tiles: square Brick Texture in the floor plane, seams 6 mm"):
        sep = g.separate(vec)
        uv = g.combine(g.math("DIVIDE", sep["X"], tile), g.math("DIVIDE", sep["Y"], tile), 0.0)
        br = g.node("ShaderNodeTexBrick", Vector=uv, Color1=(1.0, 1.0, 1.0, 1.0), Color2=(0.86, 0.86, 0.86, 1.0),
                    Mortar=(0.0, 0.0, 0.0, 1.0), Scale=1.0,
                    **{"Mortar Size": g.math("DIVIDE", 0.006, tile), "Brick Width": 1.0, "Row Height": 1.0})
        br.b.offset, br.b.squash = 0.0, 1.0
    with g.frame("Mottle: cloudy resin, darker seams; roughness from gloss, rougher in seams and blotches"):
        n = g.node("ShaderNodeTexNoise", Vector=vec, Scale=0.6, Detail=4.0)["Factor"]
        shade = g.math("MULTIPLY", g.map_range(n, 0.3, 0.7, 0.8, 1.15), g.math("ADD", 0.55, g.math("MULTIPLY", br["Color"], 0.45)))
        out = g.vmath("SCALE", col, scale=shade)["Vector"]
        base_r = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gloss, 0.92))
        rough = g.math("ADD", base_r, g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", 1.0, br["Fac"]), 0.35),
                                              g.map_range(n, 0.5, 0.8, 0.0, 0.08)), clamp=True)
    g.output("Color", "COLOR", out, desc="Floor colour")
    g.output("Roughness", "FLOAT", rough, desc="Roughness")
    return g.finish()


@once
def lacquer():
    g = Graph("News Lacquer", kind="SHADER",
              description="Desk and furniture finish: glossy lacquer in news_color, or (by news_wood) NK Wood Grain "
                          "tinted toward the same colour, for the cosy studio's walnut desk")
    vec = g.input("Vector", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="Texture coordinate")
    col = g.input("Color", "COLOR", lin("#E8ECF2"), desc="Lacquer colour (news_color)")
    wood = g.input("Wood", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", desc="0 lacquer, 1 wood (news_wood)")
    gloss = g.input("Gloss", "FLOAT", 0.7, min=0.0, max=1.0, subtype="FACTOR", desc="Gloss (news_gloss)")
    with g.frame("Wood grain (NK Wood Grain) tinted by the colour; mixed with flat lacquer by Wood"):
        wg = g.group(wood_grain(), Vector=vec, **{"Light Color": lin("#6B4528"), "Dark Color": lin("#2E1A0E"),
                                                  "Ring Scale": 24.0, "Roughness": 0.4})
        tinted = g.node("ShaderNodeMixRGB", props={"blend_type": "MULTIPLY"}, Fac=0.5, Color1=wg["Color"],
                        Color2=col)["Color"]
        c = g.mix(wood, col, tinted, data_type="RGBA")["Result"]
        r = g.mix(wood, g.math("SUBTRACT", 1.0, g.math("MULTIPLY", gloss, 0.9)), wg["Roughness"])["Result"]
    g.output("Color", "COLOR", c, desc="Colour")
    g.output("Roughness", "FLOAT", r, desc="Roughness")
    return g.finish()


@once
def skyline_paint():
    g = Graph("News Skyline Paint", kind="SHADER",
              description="Night city: dark building faces with a grid of windows, a random share lit warm or cool "
                          "(Brick Texture per-window colour variation), dimmer toward the top. Emission only, so it "
                          "goes to soft bokeh behind a shallow depth of field")
    vec = g.input("Vector", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="Object coordinate in metres")
    lit = g.input("Lit Color", "COLOR", lin("#FFC98A"), desc="Window light colour (news_glow_color)")
    density = g.input("Density", "FLOAT", 0.45, min=0.0, max=1.0, subtype="FACTOR", desc="Share of windows lit")
    strength = g.input("Strength", "FLOAT", 3.0, min=0.0, max=100.0, desc="Window brightness")
    with g.frame("Windows: 1.6 x 1.1 m cells in the facade plane (X along, Z up)"):
        sep = g.separate(vec)
        uv = g.combine(g.math("ADD", sep["X"], sep["Y"]), sep["Z"], 0.0)
        br = g.node("ShaderNodeTexBrick", Vector=uv, Color1=(0.0, 0.0, 0.0, 1.0), Color2=(1.0, 1.0, 1.0, 1.0),
                    Mortar=(0.0, 0.0, 0.0, 1.0), Scale=1.0,
                    **{"Mortar Size": 0.22, "Brick Width": 1.6, "Row Height": 1.1,
                       "Bias": g.math("SUBTRACT", g.math("MULTIPLY", density, 2.0), 1.0)})
        br.b.offset, br.b.squash = 0.0, 1.0
        on = g.math("GREATER_THAN", g.separate(br["Color"])["X"], 0.5)
        on = g.math("MULTIPLY", on, br["Fac"])
    with g.frame("Emission: lit windows, a cool share, fading with height"):
        cool = g.math("GREATER_THAN", g.node("ShaderNodeTexNoise", Vector=g.vmath("SCALE", uv, scale=0.4)["Vector"],
                                               Scale=3.0)["Factor"], 0.58)
        lc = g.mix(cool, lit, lin("#9CC4FF"), data_type="RGBA")["Result"]
        fade = g.map_range(sep["Z"], 2.0, 30.0, 1.0, 0.35)
        st = g.math("MULTIPLY", g.math("MULTIPLY", on, strength), fade)
    g.output("Color", "COLOR", (0.006, 0.007, 0.01, 1.0), desc="Facade colour")
    g.output("Roughness", "FLOAT", 0.8, desc="Roughness")
    g.output("Emission", "COLOR", lc, desc="Window light")
    g.output("Emission Strength", "FLOAT", st, desc="Window strength")
    return g.finish()


@once
def sky_paint():
    g = Graph("News Night Sky", kind="SHADER",
              description="Night sky for the window wall: a vertical gradient (news_sky_top -> horizon) with "
                          "sparse stars (thresholded Voronoi) and a soft moon disc")
    vec = g.input("Vector", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="Object coordinate in metres")
    top = g.input("Top Color", "COLOR", lin("#0B1430"), desc="Sky colour at the top")
    hor = g.input("Horizon Color", "COLOR", lin("#2A2850"), desc="Sky colour at the horizon")
    moon = g.input("Moon", "VECTOR", (3.6, 0.0, 2.6), subtype="TRANSLATION", desc="Moon centre on the sky plane (X, -, Z)")
    with g.frame("Gradient by height, stars from Voronoi distance"):
        sep = g.separate(vec)
        grad = g.mix(g.map_range(sep["Z"], 0.5, 4.5, 0.0, 1.0), hor, top, data_type="RGBA")["Result"]
        vo = g.node("ShaderNodeTexVoronoi", Vector=g.combine(sep["X"], sep["Z"], 0.0), Scale=9.0)
        star = g.map_range(vo["Distance"], 0.0, 0.035, 6.0, 0.0)
    with g.frame("Moon: smooth disc of radius 0.28 m"):
        d = g.vmath("DISTANCE", g.combine(sep["X"], 0.0, sep["Z"]), g.vmath("MULTIPLY", moon, (1.0, 0.0, 1.0))["Vector"])["Value"]
        mo = g.map_range(d, 0.26, 0.3, 1.0, 0.0, interp="SMOOTHSTEP")
        halo = g.map_range(d, 0.3, 1.2, 0.25, 0.0, interp="SMOOTHSTEP")
        strength = g.math("ADD", g.math("ADD", g.math("MULTIPLY", mo, 12.0), halo), g.math("ADD", star, 1.0))
        em = g.mix(g.math("MAXIMUM", mo, g.math("MINIMUM", star, 1.0)), grad, lin("#FFF4D8"), data_type="RGBA")["Result"]
    g.output("Color", "COLOR", (0.0, 0.0, 0.0, 1.0), desc="Base colour (black: the sky is all emission)")
    g.output("Emission", "COLOR", em, desc="Sky light")
    g.output("Emission Strength", "FLOAT", strength, desc="Sky strength")
    return g.finish()


def emissive(name, color_attr=None, color=(1, 1, 1, 1), strength=8.0, strength_attr=None):
    """Emission material; colour from a FLOAT_COLOR attribute and strength from a FLOAT attribute when given."""
    m = new_material(name)
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    em.inputs["Color"].default_value = color
    if color_attr:
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_type, a.attribute_name = "GEOMETRY", color_attr
        nt.links.new(a.outputs["Color"], em.inputs["Color"])
    if strength_attr:
        s = nt.nodes.new("ShaderNodeAttribute")
        s.attribute_type, s.attribute_name = "GEOMETRY", strength_attr
        nt.links.new(s.outputs["Factor"], em.inputs["Strength"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m["news_emit"] = strength
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


def glass_material():
    m = new_material("News Glass")
    nt = m.node_tree
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pb.inputs["Base Color"].default_value = lin("#B8D4E8")
    pb.inputs["Roughness"].default_value = 0.04
    pb.inputs["Transmission Weight"].default_value = 1.0
    pb.inputs["IOR"].default_value = 1.2
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(pb.outputs[0], out.inputs["Surface"])
    return m


def screen_material(name, image_path=None, tint=(0.05, 0.06, 0.09, 1.0), strength=1.4):
    """The blank slot the web stage paints (news_wall_screen / news_desk_brand). In Blender renders it shows
    --wall-card / --brand-card when given (emission, UVMap), else a dim vertical gradient so stills aren't black."""
    m = new_material(name)
    nt = m.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    if image_path and pathlib.Path(image_path).exists():
        tx = nt.nodes.new("ShaderNodeTexImage")
        # absolute: a CWD-relative path is remapped to "/sets/..." when the .blend is saved (cards rendered missing-pink)
        tx.image = bpy.data.images.load(str(pathlib.Path(image_path).resolve()))
        tx.extension = "EXTEND"
        nt.links.new(uv.outputs["UV"], tx.inputs["Vector"])
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
    else:
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeMix")
        ramp.data_type = "RGBA"
        ramp.inputs["A"].default_value = tint
        ramp.inputs["B"].default_value = tuple(min(1.0, c * 3.0) for c in tint[:3]) + (1.0,)
        nt.links.new(sep.outputs["Y"], ramp.inputs["Factor"])
        nt.links.new(ramp.outputs["Result"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    m["news_slot"] = 1
    return m


def materials(wall_card=None, brand_card=None, wall_cards=None, wall_px=(480, 240)):
    """Studio materials. wall_cards: card PNGs for the LED wall (News LED Panel); the first is up unless a bake
    keys the mix factors (newsroom_studio.show_card)."""
    cards = list(wall_cards or ([wall_card] if wall_card else []))
    if cards:
        screen, _ = LK.led_material("news_wall_screen", [pathlib.Path(c).resolve() for c in cards], wall_px)
    else:
        screen = screen_material("news_wall_screen", None)
    return {
        "floor": make_material("News Floor", floor_paint(), Color="attr:news_floor_color", Gloss="attr:news_gloss"),
        "panel": make_material("News Panel", stucco, Color="attr:news_color",
                               **{"Grime": 0.05, "Mottle": 0.08, "Roughness": 0.7, "Bump": 0.03}),
        "lacquer": make_material("News Lacquer", lacquer(), Color="attr:news_color", Wood="attr:news_wood",
                                 Gloss="attr:news_gloss"),
        "black": flat_material("News Matte Black", "#0B0B0E", 0.85),
        "metal": flat_material("News Metal", "#30323A", 0.3, 1.0),
        "brushed": LK.brushed_material("News Brushed Steel", "#9DA3AD", 0.3),
        "trim": LK.brushed_material("News Desk Trim", "#B8BCC4", 0.24, color_attr="news_trim_color"),
        "globe": make_material("News Globe", attribute_tint, **{"Base Color": lin("#2D5C8A"), "Value Variation": 0.25,
                                                                "Hue Variation": 0.05, "Roughness": 0.35}),
        "glow": emissive("News Glow", "news_glow_color", strength=6.0, strength_attr="news_glow_strength"),
        "screen": screen,
        "brand": screen_material("news_desk_brand", brand_card, tint=(0.12, 0.08, 0.03, 1.0), strength=1.2),
        "glass": glass_material(),
        "skyline": make_material("News Skyline", skyline_paint(), **{"Lit Color": "attr:news_glow_color",
                                                                     "Density": "attr:news_density"}),
        "sky": make_material("News Sky", sky_paint(), **{"Top Color": "attr:news_sky_top",
                                                         "Horizon Color": "attr:news_sky_horizon"}),
        "shade": make_material("News Lamp Shade", glow_glass, **{"Strength": 4.0, "Glass Color": lin("#E8D2B0"),
                                                                 "Core Color": lin("#FFD9A0"), "Rim Color": lin("#E09A50"),
                                                                 "Flicker": 0.0}),
        "fabric": make_material("News Chair Fabric", felt, Color="attr:news_color", **{"Sheen": 0.5, "Mottle": 0.1}),
        "paper": flat_material("News Paper", "#EDE9E0", 0.9),
        "ceramic": flat_material("News Mug", "#D8D2C8", 0.25),
        "books": make_material("News Book Spines", attribute_tint, **{"Base Color": lin("#5A3A2A"),
                                                                     "Value Variation": 0.35, "Hue Variation": 0.08,
                                                                     "Roughness": 0.7}),
        "leaf": flat_material("News Leaf", "#1F4A22", 0.6),
        "pot": flat_material("News Pot", "#B0654A", 0.7),
    }


# ---- News Room ----------------------------------------------------------------------------------------------------
@once
def room(mats):
    g = Graph("News Room", description="The studio shell: a polished floor, a raised elliptical riser under the desk "
                                       "with a glowing edge, a dark ceiling, and two angled side flats with vertical "
                                       "glow strips framing the wall")
    W = g.input("Room Width", "FLOAT", 12.0, min=6.0, max=40.0, subtype="DISTANCE", desc="Side to side")
    D = g.input("Room Depth", "FLOAT", 14.0, min=6.0, max=60.0, subtype="DISTANCE",
                desc="Floor depth, from the back wall toward the cameras (-Y)")
    H = g.input("Ceiling Height", "FLOAT", 4.6, min=2.6, max=20.0, subtype="DISTANCE", desc="Ceiling height")
    by = g.input("Back Wall Y", "FLOAT", 4.2, min=2.9, max=20.0, subtype="DISTANCE", desc="Back wall position (+Y)")
    floor_c = g.input("Floor Color", "COLOR", lin("#0E1016"), desc="Floor colour")
    gloss = g.input("Floor Gloss", "FLOAT", 0.75, min=0.0, max=1.0, subtype="FACTOR", desc="0 matte carpet, 1 mirror")
    riser_c = g.input("Riser Color", "COLOR", lin("#1A2236"), desc="Riser top colour")
    glow_c = g.input("Glow Color", "COLOR", lin("#3C8CFF"), desc="LED colour (riser edge, strips)")
    glow_s = g.input("Glow Strength", "FLOAT", 6.0, min=0.0, max=100.0, desc="LED brightness")
    flat_c = g.input("Flat Color", "COLOR", lin("#141C2E"), desc="Side flat colour")
    flats = g.input("Side Flats", "BOOL", True, desc="Angled flats either side of the wall")
    with g.frame("Floor: one plane under everything, colour and gloss on attributes"):
        fl = xform(g, grid(g, W, D, 2, 2), t=g.combine(0.0, g.math("SUBTRACT", by, g.math("MULTIPLY", D, 0.5)), 0.0))
        fl = store(g, fl, "news_floor_color", floor_c, "FLOAT_COLOR", "FACE")
        fl = store(g, fl, "news_gloss", gloss, "FLOAT", "FACE")
        fl = part(g, setmat(g, fl, mats["floor"]), 1)
    with g.frame("Riser: an ellipse 2.7 x 1.5 m, 6 cm high, under the desk, with an LED band round its edge"):
        rs = g.node("GeometryNodeMeshCylinder", props={"fill_type": "NGON"}, Vertices=64, Radius=1.0, Depth=0.06)["Mesh"]
        rs = xform(g, rs, t=(0.0, 0.85, 0.03), s=(2.7, 1.5, 1.0))
        rs = store(g, rs, "news_color", riser_c, "FLOAT_COLOR", "FACE")
        rs = store(g, rs, "news_wood", 0.0, "FLOAT", "FACE")
        rs = store(g, rs, "news_gloss", 0.55, "FLOAT", "FACE")
        rs = part(g, setmat(g, rs, mats["lacquer"]), 2)
        band = g.node("GeometryNodeMeshCylinder", props={"fill_type": "NONE"}, Vertices=64, Radius=1.0, Depth=0.018)["Mesh"]
        band = xform(g, band, t=(0.0, 0.85, 0.035), s=(2.71, 1.51, 1.0))
    with g.frame("Side flats: tall panels angled 20 degrees toward the desk, a glow strip on each inner edge"):
        flat = box(g, (1.5, 0.12, 3.6), (0.0, 0.0, 1.8))
        strip = box(g, (0.05, 0.14, 3.3), (-0.62, -0.01, 1.8))
        fls, sts = [], []
        for sx in (-1.0, 1.0):
            rot = (0.0, 0.0, sx * 0.35)
            pos = (sx * 3.7, 2.35, 0.0)
            fls.append(xform(g, flat, t=pos, r=rot))
            sts.append(xform(g, xform(g, strip, s=(sx * -1.0, 1.0, 1.0)), t=pos, r=rot))
        fgeo = store(g, join(g, *fls), "news_color", flat_c, "FLOAT_COLOR", "FACE")
        fgeo = part(g, setmat(g, fgeo, mats["panel"]), 4)
        fgeo = switch(g, "GEOMETRY", flats, None, fgeo)
        sgeo = switch(g, "GEOMETRY", flats, None, join(g, *sts))
    with g.frame("LEDs: riser band + flat strips share the glow material (news_glow_color, news_glow_strength)"):
        leds = join(g, band, sgeo)
        leds = store(g, leds, "news_glow_color", glow_c, "FLOAT_COLOR", "POINT")
        leds = store(g, leds, "news_glow_strength", glow_s, "FLOAT", "POINT")
        leds = part(g, setmat(g, leds, mats["glow"]), 10)
    with g.frame("Ceiling: a dark plane at Ceiling Height, facing down"):
        ce = xform(g, grid(g, W, D, 2, 2), t=g.combine(0.0, g.math("SUBTRACT", by, g.math("MULTIPLY", D, 0.5)), H),
                   r=(math.pi, 0.0, 0.0))
        ce = part(g, setmat(g, ce, mats["black"]), 22)
    g.output("Geometry", "GEOMETRY", join(g, fl, rs, fgeo, leds, ce), desc="The studio shell")
    return g.finish()


# ---- News Backdrop --------------------------------------------------------------------------------------------------
@once
def backdrop(mats):
    g = Graph("News Backdrop", description="Depth behind the video wall, one of three looks: a solid back wall with "
                                           "vertical glow slats (late-night desk), glass panes on mullions with a "
                                           "night skyline of lit windows far behind (breaking-news glass studio), or "
                                           "a warm wall with two windows onto a moonlit sky flanking the video wall "
                                           "and bookshelves outside them (cosy goodnight studio)")
    W = g.input("Room Width", "FLOAT", 12.0, min=6.0, max=40.0, subtype="DISTANCE", desc="Side to side")
    H = g.input("Ceiling Height", "FLOAT", 4.6, min=2.6, max=20.0, subtype="DISTANCE", desc="Ceiling height")
    by = g.input("Back Wall Y", "FLOAT", 4.2, min=2.9, max=20.0, subtype="DISTANCE", desc="Back wall position (+Y)")
    wall_c = g.input("Back Color", "COLOR", lin("#0E1424"), desc="Back wall colour")
    glow_c = g.input("Glow Color", "COLOR", lin("#3C8CFF"), desc="Slat / window light colour")
    glow_s = g.input("Glow Strength", "FLOAT", 6.0, min=0.0, max=100.0, desc="Slat brightness")
    slats = g.input("Slats", "INT", 9, min=0, max=60, desc="Vertical glow slats on the solid back wall")
    glass = g.input("Glass Wall", "BOOL", False, desc="Glass panes + skyline instead of a solid wall")
    window = g.input("Window Wall", "BOOL", False, desc="Two windows onto a night sky (ignored with Glass Wall)")
    sky_d = g.input("Skyline Density", "FLOAT", 0.45, min=0.0, max=1.0, subtype="FACTOR", desc="Share of city windows lit")
    sky_top = g.input("Sky Top", "COLOR", lin("#0B1430"), desc="Night sky colour at the top")
    sky_h = g.input("Sky Horizon", "COLOR", lin("#2A2850"), desc="Night sky colour at the horizon")
    shelves = g.input("Bookshelves", "BOOL", False, desc="Bookshelves outside the windows")
    woff = g.input("Window Offset", "FLOAT", 3.2, min=0.0, max=20.0, subtype="DISTANCE",
                   desc="Window centres at +-this X (they flank the video wall, so it never hides them)")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    win_w, win_h, win_z = 1.4, 2.0, 1.8
    with g.frame("Solid wall: a grid 0.1 m fine; with Window Wall the faces inside both windows are deleted"):
        nx = g.math("CEIL", g.math("MULTIPLY", W, 10.0))
        nz = g.math("CEIL", g.math("MULTIPLY", H, 10.0))
        wl = grid(g, W, H, g.math("ADD", nx, 1.0), g.math("ADD", nz, 1.0))
        wl = xform(g, wl, t=g.combine(0.0, by, g.math("MULTIPLY", H, 0.5)), r=(math.pi / 2, 0.0, 0.0))
        p = g.separate(position(g))
        inside = g.math("MULTIPLY", g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", g.math("ABSOLUTE", p["X"]), woff)), win_w / 2),
                        g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", p["Z"], win_z)), win_h / 2))
        cut = g.math("MULTIPLY", inside, window)
        wl = g.node("GeometryNodeDeleteGeometry", props={"domain": "FACE"}, Geometry=wl, Selection=cut)["Geometry"]
        wl = store(g, wl, "news_color", wall_c, "FLOAT_COLOR", "FACE")
        wl = part(g, setmat(g, wl, mats["panel"]), 3)
    with g.frame("Slats: Slats vertical glow bars across the wall, 4 cm in front of it (skipped behind the window)"):
        sp = line_points(g, slats, g.combine(g.math("MULTIPLY", W, -0.42), g.math("SUBTRACT", by, 0.04), 0.0),
                         g.combine(g.math("MULTIPLY", W, 0.42), g.math("SUBTRACT", by, 0.04), 0.0))
        bar = box(g, g.combine(0.06, 0.03, g.math("SUBTRACT", H, 0.6)), g.combine(0.0, 0.0, g.math("MULTIPLY", H, 0.5)))
        sl = realize(g, g.node("GeometryNodeInstanceOnPoints", Points=sp, Instance=bar)["Instances"])
        sl = store(g, sl, "news_glow_color", glow_c, "FLOAT_COLOR", "POINT")
        sl = store(g, sl, "news_glow_strength", g.math("MULTIPLY", glow_s, 0.6), "FLOAT", "POINT")
        sl = part(g, setmat(g, sl, mats["glow"]), 10)
        sl = switch(g, "GEOMETRY", window, sl, None)
    with g.frame("Windows: wooden frame round each hole, a cross mullion and a sill; the night sky 3 m behind"):
        fw = 0.09
        frame_parts = [box(g, (win_w + 2 * fw, 0.14, fw), (0.0, 0.0, win_h / 2 + fw / 2)),
                       box(g, (win_w + 2 * fw, 0.14, fw), (0.0, 0.0, -win_h / 2 - fw / 2)),
                       box(g, (fw, 0.14, win_h), (win_w / 2 + fw / 2, 0.0, 0.0)),
                       box(g, (fw, 0.14, win_h), (-win_w / 2 - fw / 2, 0.0, 0.0)),
                       box(g, (0.05, 0.08, win_h), (0.0, 0.0, 0.0)),
                       box(g, (win_w, 0.08, 0.05), (0.0, 0.0, 0.25)),
                       box(g, (win_w + 0.5, 0.32, 0.06), (0.0, -0.12, -win_h / 2 - fw - 0.03))]
        one = join(g, *frame_parts)
        wf = join(g, xform(g, one, t=g.combine(g.math("MULTIPLY", woff, -1.0), by, win_z)), xform(g, one, t=g.combine(woff, by, win_z)))
        wf = store(g, wf, "news_color", lin("#2A1E18"), "FLOAT_COLOR", "FACE")
        wf = store(g, wf, "news_wood", 1.0, "FLOAT", "FACE")
        wf = store(g, wf, "news_gloss", 0.4, "FLOAT", "FACE")
        wf = part(g, setmat(g, wf, mats["lacquer"]), 3)
        sky = xform(g, grid(g, g.math("ADD", W, 6.0), win_h + 3.0, 2, 2), t=g.combine(0.0, g.math("ADD", by, 3.0), win_z),
                    r=(math.pi / 2, 0.0, 0.0))
        sky = store(g, sky, "news_sky_top", sky_top, "FLOAT_COLOR", "FACE")
        sky = store(g, sky, "news_sky_horizon", sky_h, "FLOAT_COLOR", "FACE")
        sky = part(g, setmat(g, sky, mats["sky"]), 21)
        win = switch(g, "GEOMETRY", window, None, join(g, wf, sky))
    with g.frame("Bookshelves: a tall unit either side of the window, shelves of books (random height, colour)"):
        unit_w, unit_h = 1.3, 2.6
        carcass = join(g, box(g, (unit_w, 0.34, 0.04), (0.0, 0.0, unit_h)), box(g, (0.04, 0.34, unit_h), (-unit_w / 2, 0.0, unit_h / 2)),
                       box(g, (0.04, 0.34, unit_h), (unit_w / 2, 0.0, unit_h / 2)), box(g, (unit_w, 0.02, unit_h), (0.0, 0.16, unit_h / 2)),
                       *[box(g, (unit_w, 0.32, 0.03), (0.0, 0.0, 0.08 + k * 0.62)) for k in range(5)])
        bpts = g.node("GeometryNodeMeshGrid", **{"Size X": unit_w - 0.12, "Size Y": 0.62 * 3, "Vertices X": 26,
                                                 "Vertices Y": 4})["Mesh"]
        bpts = xform(g, bpts, t=(0.0, 0.0, 0.1 + 0.93), r=(math.pi / 2, 0.0, 0.0))
        bpts = g.node("GeometryNodeMeshToPoints", Mesh=bpts)["Points"]
        bidx = g.node("GeometryNodeInputIndex")["Index"]
        keep = g.math("GREATER_THAN", rand(g, 0.0, 1.0, seed, 41, bidx), 0.18)
        bh = rand(g, 0.18, 0.3, seed, 42, bidx)
        book = box(g, (0.042, 0.22, 1.0), (0.0, 0.0, 0.5))
        bk = g.node("GeometryNodeInstanceOnPoints", Points=bpts, Selection=keep, Instance=book,
                    Rotation=g.combine(0.0, rand(g, -0.05, 0.05, seed, 43, bidx), 0.0),
                    Scale=g.combine(1.0, 1.0, bh))["Instances"]
        hue = rand(g, 0.0, 1.0, seed, 44, bidx)
        bcol = g.node("FunctionNodeCombineColor", props={"mode": "HSV"}, Red=hue, Green=rand(g, 0.3, 0.7, seed, 45, bidx),
                      Blue=rand(g, 0.12, 0.45, seed, 46, bidx))["Color"]
        bk = store(g, bk, "nk_color", bcol, "FLOAT_COLOR", "INSTANCE")
        bk = realize(g, bk)
        shelves_geo = []
        for sx in (-1.0, 1.0):
            t = g.combine(g.math("MULTIPLY", g.math("ADD", woff, 1.55), sx), g.math("SUBTRACT", by, 0.18), 0.0)
            shelves_geo.append((xform(g, carcass, t=t), xform(g, bk, t=t)))
        car = join(g, *[c for c, _ in shelves_geo])
        car = store(g, car, "news_color", lin("#3A2618"), "FLOAT_COLOR", "FACE")
        car = store(g, car, "news_wood", 1.0, "FLOAT", "FACE")
        car = store(g, car, "news_gloss", 0.3, "FLOAT", "FACE")
        car = part(g, setmat(g, car, mats["lacquer"]), 19)
        books = part(g, setmat(g, join(g, *[b for _, b in shelves_geo]), mats["books"]), 23)
        sh = switch(g, "GEOMETRY", shelves, None, join(g, car, books))
    solid = join(g, wl, sl, win, sh)
    with g.frame("Glass wall: panes on a 1.5 m mullion grid at the back wall line, a skyline of towers 9-16 m behind"):
        panes = xform(g, grid(g, W, H, 2, 2), t=g.combine(0.0, by, g.math("MULTIPLY", H, 0.5)), r=(math.pi / 2, 0.0, 0.0))
        panes = part(g, setmat(g, panes, mats["glass"]), 15)
        mp = line_points(g, g.math("ADD", g.math("CEIL", g.math("DIVIDE", W, 1.5)), 1.0),
                         g.combine(g.math("MULTIPLY", W, -0.5), by, 0.0), g.combine(g.math("MULTIPLY", W, 0.5), by, 0.0))
        mull = g.group(rod(), Start=(0.0, 0.0, 0.0), End=g.combine(0.0, 0.0, H), Radius=0.035, Resolution=8)["Mesh"]
        mu = realize(g, g.node("GeometryNodeInstanceOnPoints", Points=mp, Instance=mull)["Instances"])
        rail = join(g, g.group(rod(), Start=g.combine(g.math("MULTIPLY", W, -0.5), by, 0.9), End=g.combine(g.math("MULTIPLY", W, 0.5), by, 0.9),
                               Radius=0.03, Resolution=8)["Mesh"],
                    g.group(rod(), Start=g.combine(g.math("MULTIPLY", W, -0.5), by, g.math("SUBTRACT", H, 0.05)),
                            End=g.combine(g.math("MULTIPLY", W, 0.5), by, g.math("SUBTRACT", H, 0.05)), Radius=0.05, Resolution=8)["Mesh"])
        mu = part(g, setmat(g, smooth(g, join(g, mu, rail)), mats["metal"]), 15)
        tp = line_points(g, 22, g.combine(-26.0, g.math("ADD", by, 12.0), 0.0), g.combine(26.0, g.math("ADD", by, 12.0), 0.0))
        tidx = g.node("GeometryNodeInputIndex")["Index"]
        tower = box(g, (1.0, 1.0, 1.0), (0.0, 0.0, 0.5))
        tw = g.node("GeometryNodeInstanceOnPoints", Points=tp, Instance=tower,
                    Scale=g.combine(rand(g, 3.0, 6.0, seed, 51, tidx), rand(g, 3.0, 6.0, seed, 52, tidx),
                                    rand(g, 8.0, 34.0, seed, 53, tidx)))["Instances"]
        tw = g.node("GeometryNodeTranslateInstances", Instances=tw,
                    Translation=g.combine(rand(g, -1.0, 1.0, seed, 54, tidx), rand(g, -3.0, 4.0, seed, 55, tidx), -4.0))["Instances"]
        tw = realize(g, tw)
        tw = store(g, tw, "news_glow_color", glow_c, "FLOAT_COLOR", "FACE")
        tw = store(g, tw, "news_density", sky_d, "FLOAT", "FACE")
        tw = part(g, setmat(g, tw, mats["skyline"]), 14)
        ground = xform(g, grid(g, 80.0, 30.0, 2, 2), t=g.combine(0.0, g.math("ADD", by, 14.0), -4.0))
        ground = part(g, setmat(g, ground, mats["black"]), 14)
        glassy = join(g, panes, mu, tw, ground)
    g.output("Geometry", "GEOMETRY", switch(g, "GEOMETRY", glass, solid, glassy), desc="Back wall or glass + skyline")
    return g.finish()


# ---- News Desk -------------------------------------------------------------------------------------------------------
@once
def desk(mats):
    g = Graph("News Desk", description="The anchor desk: arcs around (0, Desk Centre Y) swept with rectangles: a "
                                       "front panel, an overhanging top, a recessed kick plinth, a blank brand band "
                                       "(news_desk_brand, UVs 0..1 left to right, bottom to top) and an LED lip "
                                       "under the top's front edge")
    cy = g.input("Desk Centre Y", "FLOAT", 1.75, min=0.0, max=10.0, subtype="DISTANCE",
                 desc="Centre of the desk arc (1.75 = three.js desk)")
    R = g.input("Desk Radius", "FLOAT", 2.0, min=0.8, max=10.0, subtype="DISTANCE", desc="Radius of the front panel")
    span = g.input("Desk Span", "FLOAT", 1.24, min=0.2, max=3.0, subtype="ANGLE", desc="Arc of the desk")
    top_h = g.input("Desk Height", "FLOAT", 0.8, min=0.5, max=1.2, subtype="DISTANCE", desc="Height of the top")
    body_c = g.input("Desk Color", "COLOR", lin("#1A3C8C"), desc="Front panel colour")
    top_c = g.input("Desk Top Color", "COLOR", lin("#E9EEF7"), desc="Top colour")
    wood = g.input("Desk Wood", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", desc="0 lacquer, 1 walnut")
    gloss = g.input("Desk Gloss", "FLOAT", 0.75, min=0.0, max=1.0, subtype="FACTOR", desc="Lacquer gloss")
    brand_h = g.input("Brand Height", "FLOAT", 0.24, min=0.0, max=0.7, subtype="DISTANCE", desc="Height of the brand band")
    glow_c = g.input("Glow Color", "COLOR", lin("#3C8CFF"), desc="LED colour")
    glow_s = g.input("Glow Strength", "FLOAT", 6.0, min=0.0, max=100.0, desc="LED brightness")
    trim_c = g.input("Trim Color", "COLOR", lin("#B8BCC4"), desc="Brushed metal edge (steel, brass, gunmetal)")
    with g.frame("Front panel and kick plinth"):
        ph = g.math("SUBTRACT", top_h, 0.1)
        panel = xform(g, arc_sweep(g, R, span, 0.06, ph), t=g.combine(0.0, cy, g.math("ADD", 0.08, g.math("MULTIPLY", ph, 0.5))))
        kick = xform(g, arc_sweep(g, g.math("SUBTRACT", R, 0.08), span, 0.06, 0.1), t=g.combine(0.0, cy, 0.05))
        body = store(g, panel, "news_color", body_c, "FLOAT_COLOR", "FACE")
        body = store(g, body, "news_wood", wood, "FLOAT", "FACE")
        body = store(g, body, "news_gloss", gloss, "FLOAT", "FACE")
        body = part(g, setmat(g, body, mats["lacquer"]), 5)
        kick = part(g, setmat(g, kick, mats["black"]), 5)
    with g.frame("Top: 0.62 m deep, overhanging the panel by 6 cm, 5 cm thick"):
        top = xform(g, arc_sweep(g, g.math("SUBTRACT", R, 0.25), g.math("ADD", span, 0.06), 0.68, 0.05),
                    t=g.combine(0.0, cy, g.math("SUBTRACT", top_h, 0.025)))
        top = store(g, top, "news_color", top_c, "FLOAT_COLOR", "FACE")
        top = store(g, top, "news_wood", wood, "FLOAT", "FACE")
        top = store(g, top, "news_gloss", g.math("ADD", gloss, 0.1), "FLOAT", "FACE")
        top = part(g, setmat(g, smooth(g, top), mats["lacquer"]), 6)
    with g.frame("Brand band: a thin arc 4 mm proud of the panel, planar UVs across its width"):
        zb = g.math("ADD", 0.08, g.math("MULTIPLY", g.math("SUBTRACT", ph, brand_h), 0.55))
        band = xform(g, arc_sweep(g, g.math("ADD", R, 0.034), g.math("MULTIPLY", span, 0.8), 0.008, brand_h, 64),
                     t=g.combine(0.0, cy, g.math("ADD", zb, g.math("MULTIPLY", brand_h, 0.5))))
        half = g.math("MULTIPLY", g.math("ADD", R, 0.034), g.math("SINE", g.math("MULTIPLY", span, 0.4)))
        band = planar_uv(g, band, g.math("MULTIPLY", half, -1.0), g.math("MULTIPLY", half, 2.0), zb, brand_h)
        band = part(g, setmat(g, band, mats["brand"]), 7)
    with g.frame("LED lip under the top's front edge"):
        lip = xform(g, arc_sweep(g, g.math("ADD", R, 0.06), span, 0.012, 0.012), t=g.combine(0.0, cy, g.math("SUBTRACT", top_h, 0.06)))
        lip = store(g, lip, "news_glow_color", glow_c, "FLOAT_COLOR", "POINT")
        lip = store(g, lip, "news_glow_strength", glow_s, "FLOAT", "POINT")
        lip = part(g, setmat(g, lip, mats["glow"]), 10)
    with g.frame("Trim: a brushed-metal band on the top's front edge (News Brushed Metal, anisotropic)"):
        trim = xform(g, arc_sweep(g, g.math("ADD", R, 0.096), g.math("ADD", span, 0.06), 0.012, 0.056),
                     t=g.combine(0.0, cy, g.math("SUBTRACT", top_h, 0.025)))
        trim = store(g, trim, "news_trim_color", trim_c, "FLOAT_COLOR", "FACE")
        trim = part(g, setmat(g, smooth(g, trim), mats["trim"]), 24)
    g.output("Geometry", "GEOMETRY", join(g, body, kick, top, band, lip, trim), desc="The desk")
    return g.finish()


# ---- News Wall ----------------------------------------------------------------------------------------------------------
@once
def video_wall(mats):
    g = Graph("News Wall", description="The video wall: Tiles X x Tiles Y LED cabinets (Split Edges + Scale Elements "
                                       "leaves a hairline gap between cabinets) on a dark bezel. Every cabinet carries "
                                       "the ONE blank slot news_wall_screen with UVs running 0..1 across the whole "
                                       "wall, so the web stage draws a single headline card over all of them")
    wy = g.input("Wall Y", "FLOAT", 2.7, min=1.5, max=10.0, subtype="DISTANCE", desc="Wall plane (+Y)")
    ww = g.input("Wall Width", "FLOAT", 5.2, min=1.0, max=20.0, subtype="DISTANCE", desc="Screen width")
    wh = g.input("Wall Height", "FLOAT", 2.6, min=0.5, max=10.0, subtype="DISTANCE", desc="Screen height")
    wz = g.input("Wall Centre Height", "FLOAT", 2.05, min=0.5, max=10.0, subtype="DISTANCE", desc="Screen centre height")
    tx = g.input("Tiles X", "INT", 4, min=1, max=24, desc="Cabinets across (1 = one framed screen)")
    ty = g.input("Tiles Y", "INT", 2, min=1, max=12, desc="Cabinets down")
    gap = g.input("Tile Gap", "FLOAT", 0.003, min=0.0, max=0.1, subtype="DISTANCE", desc="Gap between cabinets")
    bezel = g.input("Bezel", "FLOAT", 0.1, min=0.0, max=1.0, subtype="DISTANCE", desc="Frame width round the screen")
    frame_c = g.input("Frame Color", "COLOR", lin("#05070C"), desc="Bezel colour")
    with g.frame("Cabinets: grid -> split edges -> shrink each face by the gap -> stand up facing -Y"):
        sc = grid(g, ww, wh, g.math("ADD", tx, 1.0), g.math("ADD", ty, 1.0))
        sc = g.node("GeometryNodeSplitEdges", Mesh=sc)["Mesh"]
        cell = g.math("DIVIDE", ww, tx)
        k = g.math("SUBTRACT", 1.0, g.math("DIVIDE", gap, cell), clamp=True)
        sc = g.node("GeometryNodeScaleElements", props={"domain": "FACE"}, Geometry=sc, Scale=k)["Geometry"]
        sc = xform(g, sc, t=g.combine(0.0, g.math("SUBTRACT", wy, 0.012), wz), r=(math.pi / 2, 0.0, 0.0))
        z0 = g.math("SUBTRACT", wz, g.math("MULTIPLY", wh, 0.5))
        sc = planar_uv(g, sc, g.math("MULTIPLY", ww, -0.5), ww, z0, wh)
        sc = part(g, setmat(g, sc, mats["screen"]), 9)
    with g.frame("Bezel: a rounded slab behind the cabinets, Bezel wider all round"):
        bs = g.combine(g.math("ADD", ww, g.math("MULTIPLY", bezel, 2.0)), 0.1, g.math("ADD", wh, g.math("MULTIPLY", bezel, 2.0)))
        bz = g.group(rounded_box(), Size=bs, Radius=0.02, Segments=2)["Mesh"]
        bz = xform(g, bz, t=g.combine(0.0, g.math("ADD", wy, 0.04), wz))
        bz = store(g, bz, "news_color", frame_c, "FLOAT_COLOR", "FACE")
        bz = store(g, bz, "news_wood", 0.0, "FLOAT", "FACE")
        bz = store(g, bz, "news_gloss", 0.5, "FLOAT", "FACE")
        bz = part(g, setmat(g, bz, mats["lacquer"]), 8)
    g.output("Geometry", "GEOMETRY", join(g, sc, bz), desc="Video wall")
    return g.finish()


# ---- News Practicals -------------------------------------------------------------------------------------------------
@once
def lamp_shape(mats):
    g = Graph("News Table Lamp", description="A table lamp at the origin: turned base (NK Profile Revolve), stem "
                                             "(NK Rod) and a drum shade of glowing glass (NK Glow Glass)")
    h = g.input("Height", "FLOAT", 0.55, min=0.2, max=2.0, subtype="DISTANCE", desc="Overall height")
    with g.frame("Base, stem, shade"):
        base = g.group(profile_revolve(), Height=0.06, **{"Radius Bottom": 0.09, "Radius Lower": 0.085, "Radius Middle": 0.06,
                                                         "Radius Upper": 0.04, "Radius Top": 0.02, "Segments": 24})["Mesh"]
        stem = g.group(rod(), Start=(0.0, 0.0, 0.05), End=g.combine(0.0, 0.0, g.math("MULTIPLY", h, 0.72)), Radius=0.012,
                       Resolution=8)["Mesh"]
        hard = part(g, setmat(g, smooth(g, join(g, base, stem)), mats["brushed"]), 12)
        shade = g.node("GeometryNodeMeshCone", props={"fill_type": "NONE"}, Vertices=32,
                       **{"Radius Top": 0.11, "Radius Bottom": 0.16, "Depth": g.math("MULTIPLY", h, 0.36)})["Mesh"]
        shade = xform(g, shade, t=g.combine(0.0, 0.0, g.math("MULTIPLY", h, 0.8)))
        shade = part(g, setmat(g, smooth(g, shade), mats["shade"]), 13)
    g.output("Mesh", "GEOMETRY", join(g, hard, shade), desc="Lamp")
    return g.finish()


@once
def practicals(mats):
    g = Graph("News Practicals", description="Lights you can see: a lighting grid of two truss bars under the ceiling "
                                             "with Grid Cans fresnel cans aimed at the desk, Pendants glass globes over "
                                             "the desk, an optional desk lamp at the empty end of the desk and table "
                                             "lamps on side tables")
    W = g.input("Room Width", "FLOAT", 12.0, min=6.0, max=40.0, subtype="DISTANCE", desc="Side to side")
    H = g.input("Ceiling Height", "FLOAT", 4.6, min=2.6, max=20.0, subtype="DISTANCE", desc="Ceiling height")
    cans = g.input("Grid Cans", "INT", 8, min=0, max=40, desc="Fresnel cans on the grid")
    pend = g.input("Pendants", "INT", 0, min=0, max=9, desc="Glass globe pendants over the desk")
    deskl = g.input("Desk Lamp", "BOOL", False, desc="A lamp on the desk (left end)")
    sidel = g.input("Side Lamps", "BOOL", False, desc="Side tables with lamps either side of the desk")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    with g.frame("Grid: two truss bars across the room 0.3 m under the ceiling, cans hanging from the front bar"):
        tz = g.math("SUBTRACT", H, 0.3)
        hw = g.math("MULTIPLY", W, 0.45)
        bars = [g.group(rod(), Start=g.combine(g.math("MULTIPLY", hw, -1.0), y, tz), End=g.combine(hw, y, tz), Radius=0.025,
                        Resolution=8)["Mesh"] for y in (-1.6, -1.2, 2.2)]
        cp = line_points(g, cans, g.combine(g.math("MULTIPLY", hw, -0.8), -1.4, tz), g.combine(g.math("MULTIPLY", hw, 0.8), -1.4, tz))
        can = join(g, g.node("GeometryNodeMeshCylinder", props={"fill_type": "NGON"}, Vertices=16, Radius=0.11, Depth=0.3)["Mesh"],
                   xform(g, box(g, (0.03, 0.26, 0.03), (0.0, 0.0, 0.0)), t=(0.0, 0.0, 0.2)))
        can = xform(g, can, t=(0.0, 0.0, -0.22))
        cidx = g.node("GeometryNodeInputIndex")["Index"]
        cpos = g.node("GeometryNodeInputPosition")["Position"]
        aim = g.vmath("NORMALIZE", g.vmath("SUBTRACT", g.combine(0.0, 0.8, 1.0), cpos)["Vector"])["Vector"]
        crot = g.node("FunctionNodeAlignRotationToVector", props={"axis": "Z"}, Vector=g.vmath("SCALE", aim, scale=-1.0)["Vector"])["Rotation"]
        cs = realize(g, g.node("GeometryNodeInstanceOnPoints", Points=cp, Instance=can, Rotation=crot,
                               Scale=rand(g, 0.9, 1.1, seed, 61, cidx))["Instances"])
        gridgeo = part(g, setmat(g, smooth(g, join(g, *bars, cs)), mats["black"]), 11)
    with g.frame("Pendants: glass globes on thin cords over the desk"):
        pp = line_points(g, pend, (-1.6, 0.9, 0.0), (1.6, 0.9, 0.0))
        globe = g.node("GeometryNodeMeshUVSphere", Segments=24, Rings=12, Radius=0.13)["Mesh"]
        globe = part(g, setmat(g, smooth(g, xform(g, globe, t=g.combine(0.0, 0.0, 2.55))), mats["shade"]), 13)
        cord = g.group(rod(), Start=(0.0, 0.0, 2.68), End=g.combine(0.0, 0.0, H), Radius=0.004, Resolution=5)["Mesh"]
        cord = part(g, setmat(g, cord, mats["black"]), 12)
        pg = realize(g, g.node("GeometryNodeInstanceOnPoints", Points=pp, Instance=join(g, globe, cord))["Instances"])
    with g.frame("Lamps: one on the desk's free end, two on side tables"):
        lamp = g.group(lamp_shape(mats))["Mesh"]
        dl = switch(g, "GEOMETRY", deskl, None, xform(g, lamp, t=(-1.0, 0.25, 0.8), s=(0.85, 0.85, 0.85)))
        table = join(g, g.group(chamfer_box(), Size=(0.5, 0.5, 0.04), Chamfer=0.006)["Mesh"],
                     g.group(rod(), Start=(0.0, 0.0, -0.02), End=(0.0, 0.0, -0.6), Radius=0.03, Resolution=8)["Mesh"],
                     xform(g, g.node("GeometryNodeMeshCylinder", props={"fill_type": "NGON"}, Vertices=24, Radius=0.2,
                                     Depth=0.03)["Mesh"], t=(0.0, 0.0, -0.6)))
        table = part(g, setmat(g, xform(g, table, t=(0.0, 0.0, 0.62)), mats["brushed"]), 12)
        side = join(g, table, xform(g, lamp, t=(0.0, 0.0, 0.64)))
        sl = switch(g, "GEOMETRY", sidel, None, join(g, xform(g, side, t=(-2.75, 1.7, 0.0)), xform(g, side, t=(2.75, 1.7, 0.0))))
    g.output("Geometry", "GEOMETRY", join(g, gridgeo, pg, dl, sl), desc="Practical lights")
    return g.finish()


# ---- News Furniture --------------------------------------------------------------------------------------------------
@once
def chair_shape(mats):
    g = Graph("News Anchor Chair", description="An anchor's swivel chair facing -Y at the origin: padded seat and tall "
                                               "back (NK Rounded Box, fabric), gas column and a five-star base")
    col = g.input("Color", "COLOR", lin("#1A1A20"), desc="Upholstery colour")
    sh = g.input("Seat Height", "FLOAT", 0.5, min=0.3, max=0.9, subtype="DISTANCE",
                 desc="Seat cushion height (the anchor's measured hips set it)")
    with g.frame("Seat + back (fabric), column + star base (metal)"):
        seat = xform(g, g.group(rounded_box(), Size=(0.52, 0.5, 0.09), Radius=0.03, Segments=2)["Mesh"], t=g.combine(0.0, 0.0, sh))
        back = xform(g, g.group(rounded_box(), Size=(0.48, 0.07, 0.46), Radius=0.035, Segments=2)["Mesh"],
                     t=g.combine(0.0, 0.29, g.math("ADD", sh, 0.3)), r=(-0.12, 0.0, 0.0))
        up = store(g, join(g, seat, back), "news_color", col, "FLOAT_COLOR", "FACE")
        up = setmat(g, up, mats["fabric"])
        colm = g.group(rod(), Start=(0.0, 0.0, 0.08), End=g.combine(0.0, 0.0, g.math("SUBTRACT", sh, 0.04)), Radius=0.025,
                       Resolution=10)["Mesh"]
        legs = [g.group(rod(), Start=(0.0, 0.0, 0.08), End=(0.3 * math.cos(a), 0.3 * math.sin(a), 0.04), Radius=0.018,
                        Resolution=6)["Mesh"] for a in [k * TAU / 5 for k in range(5)]]
        metal = setmat(g, smooth(g, join(g, colm, *legs)), mats["metal"])
    g.output("Mesh", "GEOMETRY", join(g, up, metal), desc="Chair")
    return g.finish()


@once
def furniture(mats):
    g = Graph("News Furniture", description="Anchor chairs at the seats (one part each, so the web stage can hide an "
                                            "empty seat), papers in front of each anchor and a mug on the desk, and "
                                            "potted plants either side of the riser")
    cy = g.input("Desk Centre Y", "FLOAT", 1.75, min=0.0, max=10.0, subtype="DISTANCE", desc="Desk arc centre")
    top_h = g.input("Desk Height", "FLOAT", 0.8, min=0.5, max=1.2, subtype="DISTANCE", desc="Desk top height")
    chair_c = g.input("Chair Color", "COLOR", lin("#1A1A20"), desc="Upholstery")
    plants = g.input("Plants", "BOOL", False, desc="Potted plants either side")
    seed = g.input("Seed", "INT", 0, min=0, max=100000, desc="Random seed")
    seat_h = g.input("Seat Height", "FLOAT", 0.5, min=0.3, max=0.9, subtype="DISTANCE",
                     desc="Seat cushion height (the anchor's measured hips set it)")
    second = g.input("Second Seat", "BOOL", True, desc="The co-anchor's chair and papers (off for a solo show)")
    with g.frame("Chairs: one per seat, a little behind the seat point; the second only with a co-anchor"):
        ch = g.group(chair_shape(mats), Color=chair_c, **{"Seat Height": seat_h})["Mesh"]
        c1 = part(g, xform(g, ch, t=(SEATS["anchor1"][0], SEATS["anchor1"][1] + 0.05, 0.0)), 16)
        c2 = switch(g, "GEOMETRY", second, None, part(g, xform(g, ch, t=(SEATS["anchor2"][0], SEATS["anchor2"][1] + 0.05, 0.0)), 17))
    with g.frame("Desk props: papers before each anchor and a mug (no monitor: it read as clutter in the 3/4 shot)"):
        z = g.math("ADD", top_h, 0.003)
        props = []
        for sx, (x, y) in ((1.0, SEATS["anchor1"]), (-1.0, SEATS["anchor2"])):
            pp = part(g, setmat(g, xform(g, box(g, (0.21, 0.29, 0.004), (0.0, 0.0, 0.0)), t=g.combine(x - 0.08 * sx, y - 0.42, z),
                                         r=(0.0, 0.0, 0.08 * sx)), mats["paper"]), 18)
            props.append(pp if sx > 0 else switch(g, "GEOMETRY", second, None, pp))
        mug = g.group(profile_revolve(), Height=0.1, **{"Radius Bottom": 0.038, "Radius Lower": 0.04, "Radius Middle": 0.041,
                                                        "Radius Upper": 0.042, "Radius Top": 0.043, "Wall Thickness": 0.004,
                                                        "Segments": 24})["Mesh"]
        props.append(part(g, setmat(g, smooth(g, xform(g, mug, t=g.combine(1.12, -0.05, top_h))), mats["ceramic"]), 18))
    with g.frame("Plants: terracotta pot (NK Profile Revolve) and a leafy crown of scaled spheres, either side"):
        pot = g.group(profile_revolve(), Height=0.42, **{"Radius Bottom": 0.16, "Radius Lower": 0.18, "Radius Middle": 0.2,
                                                        "Radius Upper": 0.22, "Radius Top": 0.23, "Segments": 24})["Mesh"]
        pot = part(g, setmat(g, smooth(g, pot), mats["pot"]), 20)
        lp = g.node("GeometryNodeDistributePointsOnFaces", props={"distribute_method": "RANDOM"},
                    Mesh=g.node("GeometryNodeMeshUVSphere", Segments=12, Rings=8, Radius=0.3)["Mesh"],
                    Density=90.0, Seed=seed)["Points"]
        leaf = g.node("GeometryNodeMeshUVSphere", Segments=8, Rings=5, Radius=0.09)["Mesh"]
        lidx = g.node("GeometryNodeInputIndex")["Index"]
        crown = g.node("GeometryNodeInstanceOnPoints", Points=lp, Instance=leaf,
                       Rotation=g.combine(rand(g, 0.0, TAU, seed, 71, lidx), rand(g, 0.0, TAU, seed, 72, lidx), 0.0),
                       Scale=g.combine(1.0, 0.35, rand(g, 0.6, 1.2, seed, 73, lidx)))["Instances"]
        crown = part(g, setmat(g, smooth(g, realize(g, xform(g, crown, t=(0.0, 0.0, 0.85), s=(1.0, 1.0, 1.4)))), mats["leaf"]), 20)
        plant = join(g, pot, crown)
        pl = switch(g, "GEOMETRY", plants, None, join(g, xform(g, plant, t=(-3.3, 0.9, 0.0)), xform(g, plant, t=(3.3, 0.9, 0.0))))
    g.output("Geometry", "GEOMETRY", join(g, c1, c2, *props, pl), desc="Chairs, desk props, plants")
    return g.finish()



# ---- News Props (show add-ins) ---------------------------------------------------------------------------------------
@once
def addins(mats):
    g = Graph("News Props", description="Show add-ins a theme switches on: a desk globe on a brushed stand at the "
                                        "empty end of the desk, a laptop beside the anchor, and two glowing LED "
                                        "pillars framing the video wall")
    top_h = g.input("Desk Height", "FLOAT", 0.8, min=0.5, max=1.2, subtype="DISTANCE", desc="Desk top height")
    ww = g.input("Wall Width", "FLOAT", 5.2, min=1.0, max=20.0, subtype="DISTANCE", desc="Screen width")
    wy = g.input("Wall Y", "FLOAT", 2.7, min=1.5, max=10.0, subtype="DISTANCE", desc="Wall plane (+Y)")
    H = g.input("Ceiling Height", "FLOAT", 4.6, min=2.6, max=20.0, subtype="DISTANCE", desc="Ceiling height")
    glow_c = g.input("Glow Color", "COLOR", lin("#3C8CFF"), desc="LED colour")
    glow_s = g.input("Glow Strength", "FLOAT", 6.0, min=0.0, max=100.0, desc="LED brightness")
    globe_on = g.input("Globe", "BOOL", False, desc="A desk globe at the far end of the desk")
    laptop_on = g.input("Laptop", "BOOL", False, desc="A laptop on the desk beside the anchor")
    pillars_on = g.input("LED Pillars", "BOOL", False, desc="Glowing pillars either side of the wall")
    with g.frame("Globe: a sphere on a tilted axis, a brushed meridian and turned base"):
        ball = g.node("GeometryNodeMeshUVSphere", Segments=32, Rings=16, Radius=0.15)["Mesh"]
        ball = part(g, setmat(g, smooth(g, xform(g, ball, t=(0.0, 0.0, 0.27), r=(0.0, 0.41, 0.0))), mats["globe"]), 25)
        stand = join(g, g.group(profile_revolve(), Height=0.05, **{"Radius Bottom": 0.09, "Radius Lower": 0.085,
                                                                  "Radius Middle": 0.06, "Radius Upper": 0.03,
                                                                  "Radius Top": 0.015, "Segments": 24})["Mesh"],
                     g.group(rod(), Start=(0.0, 0.0, 0.04), End=(0.0, 0.0, 0.12), Radius=0.012, Resolution=8)["Mesh"],
                     xform(g, g.node("GeometryNodeCurveToMesh",
                                     Curve=g.node("GeometryNodeCurveArc", Resolution=32, Radius=0.17,
                                                  **{"Sweep Angle": math.pi})["Curve"],
                                     **{"Profile Curve": g.node("GeometryNodeCurvePrimitiveCircle", Resolution=6,
                                                                Radius=0.006)["Curve"]})["Mesh"],
                           t=(0.0, 0.0, 0.27), r=(math.pi / 2, 0.41, 0.0)))
        stand = part(g, setmat(g, smooth(g, stand), mats["trim"]), 25)
        globe = switch(g, "GEOMETRY", globe_on, None, xform(g, join(g, ball, stand), t=g.combine(-0.95, 0.2, top_h)))
    with g.frame("Laptop: base and an open lid in brushed aluminium"):
        base = g.group(chamfer_box(), Size=(0.32, 0.22, 0.014), Chamfer=0.004)["Mesh"]
        lid = xform(g, g.group(chamfer_box(), Size=(0.32, 0.008, 0.21), Chamfer=0.003)["Mesh"], t=(0.0, 0.11, 0.1),
                    r=(-0.32, 0.0, 0.0))
        lap = part(g, setmat(g, join(g, base, lid), mats["brushed"]), 26)
        laptop = switch(g, "GEOMETRY", laptop_on, None, xform(g, lap, t=g.combine(1.33, -0.02, g.math("ADD", top_h, 0.008)),
                                                            r=(0.0, 0.0, 0.5)))
    with g.frame("Pillars: tall glowing columns either side of the wall"):
        ph = g.math("SUBTRACT", H, 0.4)
        col = g.node("GeometryNodeMeshCube", Size=g.combine(0.16, 0.16, ph))["Mesh"]
        col = xform(g, col, t=g.combine(0.0, 0.0, g.math("MULTIPLY", ph, 0.5)))
        col = store(g, col, "news_glow_color", glow_c, "FLOAT_COLOR", "POINT")
        col = store(g, col, "news_glow_strength", g.math("MULTIPLY", glow_s, 0.5), "FLOAT", "POINT")
        col = part(g, setmat(g, col, mats["glow"]), 27)
        px = g.math("ADD", g.math("MULTIPLY", ww, 0.5), 0.75)
        py = g.math("SUBTRACT", wy, 0.2)
        pil = join(g, xform(g, col, t=g.combine(px, py, 0.0)), xform(g, col, t=g.combine(g.math("MULTIPLY", px, -1.0), py, 0.0)))
        pillars = switch(g, "GEOMETRY", pillars_on, None, pil)
    g.output("Geometry", "GEOMETRY", join(g, globe, laptop, pillars), desc="Show add-ins")
    return g.finish()

# ---- News Set (the modifier) ------------------------------------------------------------------------------------------
PRIMARY = [
    # name, type, default, min, max, subtype, description
    ("Room Width", "FLOAT", 12.0, 6.0, 40.0, "DISTANCE", "Side to side"),
    ("Ceiling Height", "FLOAT", 4.6, 2.6, 20.0, "DISTANCE", "Ceiling height (cosy ~3.2)"),
    ("Back Wall Y", "FLOAT", 4.2, 2.9, 20.0, "DISTANCE", "How far behind the wall the backdrop sits (depth for bokeh)"),
    ("Glass Wall", "BOOL", False, None, None, None, "Glass panes and a night skyline behind the wall"),
    ("Window Wall", "BOOL", False, None, None, None, "Two windows onto a moonlit sky either side of the wall"),
    ("Glow Color", "COLOR", lin("#3C8CFF"), None, None, None, "LED accent colour"),
    ("Glow Strength", "FLOAT", 6.0, 0.0, 100.0, None, "LED brightness"),
    ("Desk Wood", "FLOAT", 0.0, 0.0, 1.0, "FACTOR", "0 glossy lacquer desk, 1 walnut"),
    ("Tiles X", "INT", 4, 1, 24, None, "Video wall cabinets across (1 = one framed screen)"),
    ("Seed", "INT", 0, 0, 100000, None, "Changes every random choice"),
]


def build(mats):
    parts = [("Room", room(mats)), ("Backdrop", backdrop(mats)), ("Desk", desk(mats)), ("Wall", video_wall(mats)),
             ("Practicals", practicals(mats)), ("Furniture", furniture(mats)), ("Props", addins(mats))]
    g = Graph(NAME, modifier=True,
              description="A FUNNIER / Goodnight News studio from a few controls: floor and riser, side flats, a "
                          "backdrop (slats, glass + skyline, or window + bookshelves), a curved anchor desk with a blank "
                          "brand band, a video wall carrying one blank screen slot, practical lights and the anchors' "
                          "chairs. Every face carries news_part for export")
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
    with g.frame("Parts: every part reads the shared controls by name (one Seed, one Glow Color, ...)"):
        for label, tree in parts:
            n = g.group(tree, label=label)
            for s in n.b.inputs:
                if s.enabled and s.name in ui:
                    g.connect(ui[s.name], s)
            outs.append(n["Geometry"])
    with g.frame("Join the parts (each tagged with news_part)"):
        geo = join(g, *outs)
    g.output("Geometry", "GEOMETRY", geo)
    return g.finish()


# ---- scene: presets, lights, cameras, compositor -----------------------------------------------------------------------
def load_preset(name):
    p = pathlib.Path(name)
    if not p.exists():
        hits = sorted((HERE / "newsroom_presets").glob(f"*{name}*.json"))
        if not hits:
            raise SystemExit(f"no preset {name!r} in {HERE / 'newsroom_presets'}")
        p = hits[0]
    data = json.loads(p.read_text())
    inputs = {k: (tuple(v) if isinstance(v, list) else v) for k, v in data.items() if not k.startswith("_")}
    look = data.get("_look", {})
    return p.stem.split("-", 1)[-1], inputs, look


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
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


EYE_Z = 1.23   # default seated eye height (newsroom_anchor seats every anchor with its eyes DESK_EYE above the desk)


def lights(sc, mod, look, eye=EYE_Z, seat="anchor1"):
    """A broadcast three-point rig on the anchor's MEASURED eye-line, plus the studio's washes and practicals.

        Key     soft box 40 deg camera-right, ~1 m above the eyes (the modelling light)
        Fill    big soft box camera-left, at eye height (look.fill sets the contrast ratio)
        Back    hard spot from behind and above: the rim on hair and shoulders that cuts the anchor off the wall
        Kicker  small soft box behind camera-right, skimming the cheek and hair (look.kicker)
        Desk    overhead wash on the desk; Back Wash on the wall/backdrop; Practicals inside the lamp shades
    """
    by, H = value(mod, "Back Wall Y"), value(mod, "Ceiling Height")
    ax, ay = SEATS[seat]
    head = (ax, ay, eye + 0.02)
    sh = (ax, ay, eye - 0.25)
    col = lambda k, d: S.srgb(look.get(k, d))
    add_light(sc, "Key", "AREA", (ax + 1.55, ay - 2.25, eye + 1.05), look.get("key", 220.0), col("key_color", "#FFF1DE"),
              head, size=1.1)
    add_light(sc, "Fill", "AREA", (ax - 2.3, ay - 2.0, eye + 0.25), look.get("fill", 70.0), col("fill_color", "#CFE0FF"),
              head, size=2.0)
    add_light(sc, "Back", "SPOT", (ax - 0.55, ay + 1.45, min(H - 0.3, eye + 1.75)), look.get("rim", 260.0),
              col("rim_color", "#8FB8FF"), sh, size=0.15, spot_deg=42, blend=0.55)
    add_light(sc, "Kicker", "AREA", (ax + 1.25, ay + 1.0, eye + 0.6), look.get("kicker", look.get("rim", 260.0) * 0.18),
              col("kicker_color", look.get("rim_color", "#8FB8FF")), head, size=0.5)
    add_light(sc, "Desk Wash", "AREA", (0.0, -2.2, min(H - 0.2, 3.0)), look.get("desk", 120.0), col("desk_color", "#FFFFFF"),
              (0.0, 0.0, 0.6), size=3.0)
    add_light(sc, "Back Wash", "AREA", (0.0, by - 1.4, H - 0.3), look.get("wash", 90.0), col("wash_color", "#6FA0FF"),
              (0.0, by, 1.2), size=5.0)
    for k, (x, y, z) in enumerate(look.get("practicals", [])):
        add_light(sc, f"Practical {k}", "POINT", (x, y, z), look.get("practical", 25.0), col("practical_color", "#FFC88A"),
                  size=0.08)
    w = bpy.data.worlds.new("News World")
    nt = w.node_tree
    nt.nodes["Background"].inputs["Color"].default_value = (*S.srgb(look.get("ambient", "#0A0C14")), 1.0)
    nt.nodes["Background"].inputs["Strength"].default_value = look.get("ambient_strength", 0.5)
    sc.world = w


def volume_haze(sc, mod, density=0.012, color="#FFFFFF"):
    """A real scattering volume filling the studio (hero stills; it costs several times the render time, so
    episodes use the Mist-pass haze in News Lens instead)."""
    import bmesh
    W, H, by = value(mod, "Room Width"), value(mod, "Ceiling Height"), value(mod, "Back Wall Y")
    me = bpy.data.meshes.new("news_haze")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("news_haze", me)
    ob.scale = (W * 0.98, by + 9.0, H * 0.98)
    ob.location = (0.0, (by - 9.0) / 2, H / 2)
    sc.collection.objects.link(ob)
    m = bpy.data.materials.new("News Haze Volume")
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vs = nt.nodes.new("ShaderNodeVolumeScatter")
    vs.inputs["Density"].default_value = density
    vs.inputs["Anisotropy"].default_value = 0.45
    vs.inputs["Color"].default_value = (*S.srgb(color), 1.0)
    nt.links.new(vs.outputs[0], out.inputs["Volume"])
    me.materials.append(m)
    ob.visible_shadow = False
    return ob


def make_camera(sc, name, s):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "VERTICAL"
    cd.sensor_height = CK.SENSOR_H
    cd.lens = s["lens"]
    cd.clip_start, cd.clip_end = 0.05, 200.0
    ob = bpy.data.objects.new(name, cd)
    # location/rotation, never matrix_world, on objects made this run (black frames otherwise)
    ob.location = s["pos"]
    ob.rotation_euler = (Vector(s["tgt"]) - Vector(s["pos"])).to_track_quat("-Z", "Y").to_euler()
    cd.dof.use_dof = True
    cd.dof.focus_distance = (Vector(s["focus"]) - Vector(s["pos"])).length
    cd.dof.aperture_fstop = s["fstop"]
    sc.collection.objects.link(ob)
    ob["news_shot"] = {"tgt": list(s["tgt"]), "focus": list(s["focus"])}
    return ob


def cameras(sc, mod, eye=EYE_Z, mouth=None, seat="anchor1", coanchor=False, head_top=None):
    """The camera kit (newsroom_cameras.shots) as named Blender cameras, solved from this studio's numbers and the
    anchor's measured eye/mouth height. Returns ({name: camera}, {name: spec}, studio numbers)."""
    st = CK.studio_numbers(inspect.get_modifier_inputs(mod))
    spec, marks = CK.shots(st, eye, mouth, seat, coanchor, head_top)
    cams = {name: make_camera(sc, name, s) for name, s in spec.items()}
    for name, p in marks.items():
        e = bpy.data.objects.new(name, None)
        e.empty_display_type, e.empty_display_size = "SPHERE", 0.05
        e.location = p
        sc.collection.objects.link(e)
    return cams, spec, st


def post(sc, look):
    LK.post(sc, look)


def render_setup(sc, width, height, samples):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    # OIDN dies with SIGILL on the aarch64 sandbox: NEWS_DENOISE=0 for local previews; CI (x86) keeps it
    sc.cycles.use_denoising = os.environ.get("NEWS_DENOISE", "1") != "0"
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 12
    sc.cycles.transmission_bounces = 8
    sc.cycles.volume_bounces = 1
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = "PNG"


# ---- export ----------------------------------------------------------------------------------------------------------
BAKE_PARTS = {1: 1024, 3: 1024, 4: 512, 5: 512, 6: 1024, 2: 512, 19: 512}
EMISSIVE = {10: "news_glow_color", 13: None, 14: "news_glow_color", 21: None}


def split_parts(src, sc):
    """Apply the modifier to a mesh copy and split it by news_part into one named object per part
    (part id -> material index, separate by material, restore the original materials)."""
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    ev = src.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    mats = list(me.materials)
    n = len(me.polygons)
    orig = np.zeros(n, dtype=np.int32)
    me.polygons.foreach_get("material_index", orig)
    pa = me.attributes.get("news_part")
    parts = np.zeros(n, dtype=np.int32)
    if pa is not None:
        pa.data.foreach_get("value", parts)
    keep = me.attributes.new("news_orig_mat", "INT", "FACE")
    keep.data.foreach_set("value", orig)
    uniq = sorted(set(parts.tolist()))
    me.materials.clear()
    for pid in uniq:
        me.materials.append(bpy.data.materials.get(f"__part_{pid}") or bpy.data.materials.new(f"__part_{pid}"))
    lut = np.zeros(max(uniq) + 1, dtype=np.int32)
    for i, pid in enumerate(uniq):
        lut[pid] = i
    me.polygons.foreach_set("material_index", lut[parts])
    whole = bpy.data.objects.new("news_whole", me)
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
    for ob in [o for o in sc.objects if o.type == "MESH" and o.name.startswith("news_whole")]:
        m2 = ob.data
        if not len(m2.polygons):
            continue
        slot = m2.materials[m2.polygons[0].material_index].name
        pid = int(slot.split("_")[-1])
        k = len(m2.polygons)
        idx = np.zeros(k, dtype=np.int32)
        m2.attributes["news_orig_mat"].data.foreach_get("value", idx)
        m2.materials.clear()
        for mat in mats:
            m2.materials.append(mat)
        m2.polygons.foreach_set("material_index", idx)
        m2.update()
        name = PARTS.get(pid, f"news_part_{pid}")
        ob.name = name
        m2.name = name
        objs[pid] = ob
    return objs


def principled(name, color=(0.5, 0.5, 0.5, 1), rough=0.7, metal=0.0, emit=None, emit_strength=0.0, image=None,
               alpha=1.0, transmission=0.0):
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
    if transmission:
        pb.inputs["Transmission Weight"].default_value = transmission
    return m


def mean_attr(ob, name, fallback):
    import numpy as np
    a = ob.data.attributes.get(name)
    if a is None or not len(a.data):
        return fallback
    comps = 4 if a.data_type in {"FLOAT_COLOR", "BYTE_COLOR"} else 1
    buf = np.zeros(len(a.data) * comps, dtype=np.float32)
    a.data.foreach_get("color" if comps == 4 else "value", buf)
    if comps == 4:
        c = buf.reshape(-1, 4).mean(axis=0)
        return (float(c[0]), float(c[1]), float(c[2]), 1.0)
    return float(buf.mean())


def bake_part(sc, ob, size, workdir, kind="DIFFUSE"):
    """Smart-UV the part (as BakeUV, keeping any UVMap) and bake its diffuse colour (or, kind="EMIT", its
    emission: the skyline's lit windows, the night sky) into an image."""
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
        tx = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tx.image = img
        mat.node_tree.nodes.active = tx
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    sc.render.bake.margin = 4
    with bpy.context.temp_override(active_object=ob, object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.bake(type=kind)
    path = pathlib.Path(workdir, f"{ob.name}.png")
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    # keep only the bake UVs (the first UV set is what glTF's TEXCOORD_0 and three.js read)
    for uv in [u for u in ob.data.uv_layers if u.name != "BakeUV"]:
        ob.data.uv_layers.remove(uv)
    return img


def book_colors(objs):
    """Books carry their colour per vertex (nk_color) as glTF COLOR_0, instead of a texture."""
    import numpy as np
    ob = objs.get(23)
    if ob is None:
        return
    me = ob.data
    a = me.attributes.get("nk_color")
    if a is None or a.domain != "POINT":
        return
    n = len(me.vertices)
    buf = np.zeros(n * 4, dtype=np.float32)
    a.data.foreach_get("color", buf)
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    col.data.foreach_set("color", buf)
    me.color_attributes.active_color = col
    me["news_vcol"] = 1


def export_glb(sc, holder, path, bake=0, workdir="/tmp", cams=None):
    """Realize + split by news_part, swap every material for a glTF-friendly Principled, keep the two blank slots
    (news_wall_screen, news_desk_brand) as named materials with UVMap, export a Y-up GLB with the camera marks."""
    mod = holder.modifiers[0]
    objs = split_parts(holder, sc)
    holder.hide_render = True
    holder.hide_set(True)
    book_colors(objs)
    flat = {1: lin("#101218"), 2: lin("#1A2236"), 3: lin("#0E1424"), 4: lin("#141C2E"), 5: lin("#1A3C8C"),
            6: lin("#E9EEF7"), 8: lin("#05070C"), 11: lin("#0B0B0E"), 12: lin("#9DA3AD"), 16: lin("#1A1A20"),
            17: lin("#1A1A20"), 18: lin("#30323A"), 19: lin("#3A2618"), 20: lin("#2A5A2A"), 22: lin("#0B0B0E")}
    for pid, ob in objs.items():
        me = ob.data
        img = None
        if pid == 9:
            mat = principled("news_wall_screen", color=(0.02, 0.025, 0.04, 1), rough=0.4, emit=(0.02, 0.025, 0.04, 1),
                             emit_strength=1.0)
        elif pid == 7:
            mat = principled("news_desk_brand", color=(0.06, 0.04, 0.02, 1), rough=0.4,
                             emit=tuple(value(mod, "Glow Color")[:3]) + (1.0,), emit_strength=0.3)
        elif pid in (14, 21) and bake:
            img = bake_part(sc, ob, 1024, workdir, kind="EMIT")
            mat = principled(f"{ob.name}_mat", color=(0, 0, 0, 1), rough=0.8, emit=(1, 1, 1, 1), emit_strength=1.0)
            tx = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tx.image = img
            mat.node_tree.links.new(tx.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"])
        elif pid in (10, 14):
            c = mean_attr(ob, "news_glow_color", lin("#3C8CFF"))
            mat = principled(f"{ob.name}_mat", color=(0, 0, 0, 1), emit=c,
                             emit_strength=2.0 if pid == 10 else 0.6, rough=0.5)
        elif pid == 13:
            mat = principled("news_lampglow_mat", color=lin("#E8D2B0"), emit=lin("#FFD9A0"), emit_strength=2.5)
        elif pid == 21:
            mat = principled("news_sky_mat", color=(0, 0, 0, 1), emit=mean_attr(ob, "news_sky_top", lin("#0B1430")),
                             emit_strength=1.0)
        elif pid == 15:
            mat = principled("news_glass_mat", color=lin("#B8D4E8"), rough=0.05, alpha=0.18)
            mat.surface_render_method = "BLENDED" if hasattr(mat, "surface_render_method") else None
        elif pid == 23:
            mat = principled("news_books_mat", color=(1, 1, 1, 1), rough=0.7)
            ca = mat.node_tree.nodes.new("ShaderNodeVertexColor")
            ca.layer_name = "Col"
            mat.node_tree.links.new(ca.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        else:
            if bake and pid in BAKE_PARTS and len(me.polygons):
                img = bake_part(sc, ob, min(BAKE_PARTS[pid], bake), workdir)
            if img is not None:
                mat = principled(f"{ob.name}_mat", rough=0.35 if pid in (1, 6) else 0.7, image=img)
            else:
                c = mean_attr(ob, "news_color", flat.get(pid, lin("#555555")))
                if pid == 1:
                    c = mean_attr(ob, "news_floor_color", flat[1])
                metal = 1.0 if pid in (11, 12, 18) else 0.0
                mat = principled(f"{ob.name}_mat", color=c, rough=0.3 if pid in (1, 6) or metal else 0.7, metal=metal)
        me.materials.clear()
        me.materials.append(mat)
        for poly in me.polygons:
            poly.material_index = 0
        if pid not in (7, 9) and img is None:
            for uv in list(me.uv_layers):
                me.uv_layers.remove(uv)
    for ob in objs.values():   # only the books' "Col" may reach glTF as COLOR_0
        me = ob.data
        for ca in [c for c in me.color_attributes if c.name != "Col"]:
            me.color_attributes.remove(ca)
        for at in [a for a in me.attributes if a.data_type in {"FLOAT_COLOR", "BYTE_COLOR"} and a.name != "Col"]:
            me.attributes.remove(at)
    names = {ob.name for ob in objs.values()} | {c.name for c in (cams or {}).values()}
    for o in sc.objects:
        o.select_set(o.name in names)
    kw = dict(filepath=str(path), export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
              export_image_format="JPEG", export_jpeg_quality=82, export_attributes=False, export_cameras=True,
              export_lights=False, export_extras=False, export_materials="EXPORT")
    try:
        bpy.ops.export_scene.gltf(**kw, export_vertex_color="MATERIAL")
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)
    return {PARTS.get(pid, pid): len(ob.data.polygons) for pid, ob in objs.items()}


# ---- main --------------------------------------------------------------------------------------------------------------
def setup(preset, wall_card=None, brand_card=None):
    """Reset the file, build the graph on a holder, apply the preset. Returns (scene, holder, modifier, look, name)."""
    pname, inputs, look = load_preset(preset)
    sc = S.reset()
    sc.name = "Newsroom"
    mats = materials(wall_card, brand_card)
    group = build(mats)
    ob, mod = S.holder("Newsroom", None, group, sc=sc)
    inspect.set_modifier_inputs(mod, inputs)
    sc.frame_set(1)
    return sc, ob, mod, look, pname


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default="")
    ap.add_argument("--preset", default="late-night")
    ap.add_argument("--out", default="")
    ap.add_argument("--anchor", default="", help="VRM/GLB avatar to seat at anchor1 (stills only; not exported)")
    ap.add_argument("--wall-card", default="", help="PNG painted on news_wall_screen in renders")
    ap.add_argument("--brand-card", default="", help="PNG painted on news_desk_brand in renders")
    ap.add_argument("--render", default="", help="directory for stills")
    ap.add_argument("--views", default="wide,medium,close")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--glb", default="")
    ap.add_argument("--bake", type=int, default=0, help="bake albedo textures up to this size (0 = flat colours)")
    ap.add_argument("--dump", default="", help="write the graph dump JSON here")
    a = ap.parse_args(_ARGV)

    sc, ob, mod, look, pname = setup(a.preset, a.wall_card or None, a.brand_card or None)
    st = inspect.evaluated_stats(ob, sc)
    warn = [w.message for w in mod.node_warnings]
    lint = inspect.check_groups("News ") + inspect.check_groups("NK ")
    print(f"PRESET {pname}: verts {st['verts']} faces {st['faces']} warnings {warn}")
    print("LINT", len(lint))
    for p in lint:
        print("  ", p)
    if a.dump:
        inspect.dump_groups(a.dump, prefix="News ")
    eye = EYE_Z
    if a.anchor and (a.render or a.out):
        import newsroom_anchor as NA
        an = NA.seat_anchor(sc, a.anchor, desk_h=value(mod, "Desk Height"), strict=False)
        inspect.set_modifier_inputs(mod, {"Seat Height": an["seat_h"]})
        eye = an["eye"]
    lights(sc, mod, look, eye)
    cams, _, _ = cameras(sc, mod, eye)
    cams = {"wide": cams["CAM_WIDE"], "medium": cams["CAM_MEDIUM"], "close": cams["CAM_CLOSE"], "wall": cams["CAM_WALL"]}
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
            sc.camera = cams[v]
            sc.render.filepath = str(rd / f"newsroom_{pname}_{v}.png")
            bpy.ops.render.render(write_still=True, scene=sc.name)
            print("RENDERED", sc.render.filepath)
    if a.glb:
        if a.anchor:
            for o in [o for o in sc.objects if o.name.startswith("anchor_")]:
                for c in o.children_recursive:
                    c.hide_render = True
        p = pathlib.Path(a.glb).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        bake_dir = p.parent / f"{p.stem}_bake"
        bake_dir.mkdir(exist_ok=True)
        counts = export_glb(sc, ob, p, bake=a.bake, workdir=str(bake_dir), cams=cams)
        print("GLB", p, p.stat().st_size, json.dumps(counts))


if __name__ == "__main__":
    main()
