"""The newsroom's "shader hack": node groups authored with video-to-blender's nodekit (MIT) for the studio's hero
surfaces and its lens. Each is a documented group an artist can open (lint: inspect.check_groups("News ") = 0).

    News LED Panel      the video wall's LED face: the card image through a pixel grid (RGB subpixel stripes, dark
                        row gaps) that shows only close up (view distance), a black-level glow and a glossy coat
    News Brushed Metal  anisotropic brushed steel/brass: fine stretched streaks in colour, roughness and a bump
    News Lens           compositor finish: depth haze from the Mist pass (studio smoke catching the light), NK Soft
                        Glow on the LEDs and practicals, a chromatic fringe (Lens Distortion dispersion) and a soft
                        vignette. Film grain is added per frame in the 2D finish (newsroom_finish.py), seeded.

A true volumetric haze (a scattering volume filling the room) is available for hero stills (newsroom_studio.py
--haze volume); episodes use the Mist-pass haze, which costs nothing per frame.
"""
import bpy

from nodekit.graph import Graph, once
from nodekit.materials import material as new_material
from library.post import soft_glow
from library.materials import lin


def mixc(g, fac, a, b, blend="MIX"):
    return g.node("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": blend, "clamp_factor": True}).set(
        Factor=fac, A=a, B=b)["Result"]


@once
def led_panel():
    g = Graph("News LED Panel", kind="SHADER",
              description="An LED video-wall face: the card colour through a pixel grid of RGB subpixel stripes with "
                          "dark row gaps (only when the camera is close enough to resolve it), plus a black-level "
                          "glow; emission colour and strength for an emissive coat material")
    uv = g.input("UV", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="0..1 across the whole wall (UVMap)")
    col = g.input("Color", "COLOR", (0.5, 0.5, 0.5, 1.0), desc="The card / picture on the wall")
    px = g.input("Pixels X", "FLOAT", 480.0, min=8.0, max=8000.0, desc="LED pixels across the wall")
    py = g.input("Pixels Y", "FLOAT", 240.0, min=8.0, max=8000.0, desc="LED pixels down the wall")
    sub = g.input("Subpixel", "FLOAT", 0.55, min=0.0, max=1.0, subtype="FACTOR",
                  desc="How strongly the RGB stripe structure shows (0 = a plain screen)")
    bright = g.input("Brightness", "FLOAT", 1.2, min=0.0, max=100.0, desc="Emission strength")
    vis = g.input("Visible Within", "FLOAT", 4.5, min=0.1, max=100.0, subtype="DISTANCE",
                  desc="Camera distance under which the pixel grid shows")
    black = g.input("Black Level", "FLOAT", 0.012, min=0.0, max=1.0, subtype="FACTOR",
                    desc="Glow of a black pixel (LED walls are never fully black)")
    with g.frame("Pixel cell: fract(UV x pixels); subpixel stripe from the cell's x thirds, soft row gaps"):
        s = g.separate(uv)
        cx = g.math("FRACT", g.math("MULTIPLY", s["X"], px))
        cy = g.math("FRACT", g.math("MULTIPLY", s["Y"], py))
        third = g.math("FLOOR", g.math("MULTIPLY", cx, 3.0))
        r = g.math("COMPARE", third, 0.0, 0.5)
        gg = g.math("COMPARE", third, 1.0, 0.5)
        b = g.math("COMPARE", third, 2.0, 0.5)
        row = g.map_range(g.math("ABSOLUTE", g.math("SUBTRACT", cy, 0.5)), 0.32, 0.46, 1.0, 0.0, interp="SMOOTHSTEP")["Result"]
        mask = g.vmath("SCALE", g.combine(r, gg, b), scale=g.math("MULTIPLY", row, 3.0))["Vector"]
    with g.frame("Show the grid only close up (view distance under Visible Within): no moire in the wides"):
        dist = g.node("ShaderNodeCameraData")["View Distance"]
        near = g.map_range(dist, g.math("MULTIPLY", vis, 0.7), vis, 1.0, 0.0, interp="SMOOTHSTEP")["Result"]
        k = g.math("MULTIPLY", sub, near)
        grid = mixc(g, k, g.combine(1.0, 1.0, 1.0), mask)
        lit = mixc(g, 1.0, col, grid, "MULTIPLY")
        lit = mixc(g, 1.0, lit, g.combine(black, black, black), "ADD")
    g.output("Color", "COLOR", (0.0, 0.0, 0.0, 1.0), desc="Base colour (the LED face is near black)")
    g.output("Roughness", "FLOAT", 0.55, desc="Anti-glare front pane (a glossy pane mirrored the key light as a white blob)")
    g.output("Emission", "COLOR", lit, desc="Pixel light")
    g.output("Emission Strength", "FLOAT", bright, desc="Emission strength")
    return g.finish()


@once
def brushed_metal():
    g = Graph("News Brushed Metal", kind="SHADER",
              description="Brushed metal: long fine streaks along X (a noise stretched 1:60) modulate colour and "
                          "roughness and drive a faint bump; pair with Principled anisotropy for the streaked highlight")
    vec = g.input("Vector", "VECTOR", (0.0, 0.0, 0.0), hide_value=True, desc="Texture coordinate (object, metres)")
    col = g.input("Color", "COLOR", lin("#B8BCC4"), desc="Metal colour (steel, brass, gunmetal)")
    rough = g.input("Roughness", "FLOAT", 0.28, min=0.0, max=1.0, subtype="FACTOR", desc="Mean roughness")
    streak = g.input("Streaks", "FLOAT", 0.5, min=0.0, max=1.0, subtype="FACTOR", desc="How visible the brushing is")
    with g.frame("Streaks: noise squashed along the brushing direction"):
        s = g.separate(vec)
        p = g.combine(g.math("MULTIPLY", s["X"], 2.0), g.math("MULTIPLY", s["Y"], 120.0), g.math("MULTIPLY", s["Z"], 120.0))
        n = g.node("ShaderNodeTexNoise", Vector=p, Scale=4.0, Detail=6.0, Roughness=0.6)["Factor"]
        d = g.math("MULTIPLY", g.math("SUBTRACT", n, 0.5), streak)
        c = g.vmath("SCALE", col, scale=g.math("ADD", 1.0, g.math("MULTIPLY", d, 0.5)))["Vector"]
        r = g.math("ADD", rough, g.math("MULTIPLY", d, 0.25), clamp=True)
        bump = g.node("ShaderNodeBump", Strength=g.math("MULTIPLY", streak, 0.08), Distance=0.002, Height=n)["Normal"]
    g.output("Color", "COLOR", c, desc="Base colour")
    g.output("Roughness", "FLOAT", r, desc="Roughness")
    g.output("Normal", "VECTOR", bump, desc="Bump normal")
    g.output("Metallic", "FLOAT", 1.0, desc="Fully metallic")
    return g.finish()


def led_material(name, images, uv_px=(480, 240), strength=1.2, subpixel=0.55):
    """The LED wall slot: images (paths) mixed by an index chain (mix k selects image k+1) -> News LED Panel ->
    emissive Principled with a glossy coat. Returns (material, [mix factor sockets])."""
    m = new_material(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = led_panel()
    gn.inputs["Pixels X"].default_value, gn.inputs["Pixels Y"].default_value = uv_px
    gn.inputs["Brightness"].default_value = strength
    gn.inputs["Subpixel"].default_value = subpixel
    nt.links.new(uv.outputs["UV"], gn.inputs["UV"])
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for k in ("Color", "Roughness", "Emission", "Emission Strength"):
        nt.links.new(gn.outputs[k], pb.inputs[{"Color": "Base Color", "Emission": "Emission Color"}.get(k, k)])
    pb.inputs["Coat Weight"].default_value = 0.12
    pb.inputs["Coat Roughness"].default_value = 0.4
    nt.links.new(pb.outputs[0], out.inputs["Surface"])
    facs = []
    cur = None
    for path in images:
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = bpy.data.images.load(str(path), check_existing=True)
        tx.extension = "EXTEND"
        nt.links.new(uv.outputs["UV"], tx.inputs["Vector"])
        if cur is None:
            cur = tx.outputs["Color"]
            continue
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.label = f"card {len(facs) + 1}"
        nt.links.new(cur, mx.inputs["A"])
        nt.links.new(tx.outputs["Color"], mx.inputs["B"])
        mx.inputs["Factor"].default_value = 0.0
        facs.append(mx.inputs["Factor"])
        cur = mx.outputs["Result"]
    if cur is not None:
        nt.links.new(cur, gn.inputs["Color"])
    m["news_slot"] = 1
    return m, facs


def brushed_material(name, hexcol="#B8BCC4", rough=0.26, color_attr=None):
    m = new_material(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = brushed_metal()
    gn.inputs["Color"].default_value = lin(hexcol)
    gn.inputs["Roughness"].default_value = rough
    nt.links.new(tc.outputs["Object"], gn.inputs["Vector"])
    if color_attr:
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_type, at.attribute_name = "GEOMETRY", color_attr
        nt.links.new(at.outputs["Color"], gn.inputs["Color"])
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for k, tgt in (("Color", "Base Color"), ("Roughness", "Roughness"), ("Normal", "Normal"), ("Metallic", "Metallic")):
        nt.links.new(gn.outputs[k], pb.inputs[tgt])
    pb.inputs["Anisotropic"].default_value = 0.75
    tg = nt.nodes.new("ShaderNodeTangent")
    tg.direction_type = "RADIAL"
    tg.axis = "Z"
    nt.links.new(tg.outputs["Tangent"], pb.inputs["Tangent"])
    nt.links.new(pb.outputs[0], out.inputs["Surface"])
    return m


@once
def lens():
    g = Graph("News Lens", kind="COMPOSITOR",
              description="The studio camera's finish: haze by depth (Mist pass) tinted like smoke catching the "
                          "lights, NK Soft Glow on bright LEDs and lamps, a chromatic fringe toward the frame edges "
                          "(Lens Distortion dispersion) and a soft elliptical vignette")
    img = g.input("Image", "COLOR", (0.0, 0.0, 0.0, 1.0), desc="Rendered image (linear)")
    mist = g.input("Mist", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", desc="Mist pass (0 near .. 1 far)")
    haze_c = g.input("Haze Color", "COLOR", lin("#2A3550"), desc="Colour the haze glows with (the light mood)")
    haze = g.input("Haze", "FLOAT", 0.25, min=0.0, max=2.0, desc="Haze at full mist depth (added light)")
    glow = g.input("Glow", "FLOAT", 0.3, min=0.0, max=10.0, desc="Bloom strength")
    thresh = g.input("Glow Threshold", "FLOAT", 1.2, min=0.0, max=100.0, desc="Brightness that blooms")
    fringe = g.input("Fringe", "FLOAT", 0.012, min=0.0, max=1.0, desc="Chromatic dispersion at the edges")
    vig = g.input("Vignette", "FLOAT", 0.28, min=0.0, max=1.0, subtype="FACTOR", desc="Edge darkening")
    tint = g.input("Grade Tint", "COLOR", (1.0, 1.0, 1.0, 1.0), desc="The skin's colour grade (multiplied in)")
    tint_k = g.input("Grade Amount", "FLOAT", 0.0, min=0.0, max=1.0, subtype="FACTOR", desc="How much of the grade tint")
    sat = g.input("Saturation", "FLOAT", 1.0, min=0.0, max=2.0, desc="Grade saturation")
    with g.frame("Haze: add the haze colour by depth"):
        hz = mixc(g, g.math("MULTIPLY", mist, haze, clamp=True), (0.0, 0.0, 0.0, 1.0), haze_c)
        hazed = mixc(g, 1.0, img, hz, "ADD")
    with g.frame("Bloom, then the lens's chromatic fringe"):
        gl = g.group(soft_glow(), Image=hazed, Threshold=thresh, Strength=glow, Size=0.6, Tint=(1.0, 0.95, 0.9, 1.0))
        ld = g.node("CompositorNodeLensdist", Image=gl["Image"])
        if "Dispersion" in [sk.name for sk in ld.b.inputs]:
            g.connect(fringe, ld.i("Dispersion"))
    with g.frame("Vignette: elliptical falloff from the frame centre"):
        co = g.node("CompositorNodeImageCoordinates", Image=img)
        sp = g.separate(co["Normalized"])
        dx = g.math("MULTIPLY", g.math("SUBTRACT", sp["X"], 0.5), 1.25)
        dy = g.math("SUBTRACT", sp["Y"], 0.5)
        r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", dx, dx), g.math("MULTIPLY", dy, dy)))
        fall = g.map_range(r, 0.35, 0.85, 0.0, 1.0, interp="SMOOTHSTEP")["Result"]
        k = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", fall, vig))
        kc = g.node("CompositorNodeCombineColor", Red=k, Green=k, Blue=k, Alpha=1.0)["Image"]
        vg = mixc(g, 1.0, ld["Image"], kc, "MULTIPLY")
    with g.frame("Grade: the skin's tint and saturation"):
        tn = mixc(g, tint_k, vg, g.node("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": "MULTIPLY",
                                                                 "clamp_factor": True}).set(Factor=1.0, A=vg, B=tint)["Result"])
        hs = g.node("CompositorNodeHueSat", Image=tn)
        if "Saturation" in [sk.name for sk in hs.b.inputs]:
            g.connect(sat, hs.i("Saturation"))
        out = hs["Image"]
    g.output("Image", "COLOR", out, desc="Finished image")
    return g.finish()


def _lens_inputs(look, **over):
    from library.post import lin as plin
    d = {"Haze Color": plin(look.get("haze_color", "#2A3550")), "Haze": look.get("haze", 0.25),
         "Glow": look.get("glow", 0.3), "Glow Threshold": look.get("glow_threshold", 1.2),
         "Fringe": look.get("fringe", 0.012), "Vignette": look.get("vignette", 0.28),
         "Grade Tint": plin(look.get("grade_tint", "#FFFFFF")), "Grade Amount": look.get("grade_tint_amount", 0.0),
         "Saturation": look.get("saturation", 1.0)}
    d.update(over)
    return d


def post(sc, look, **over):
    """Compositor: render layers -> News Lens. Mist pass on (mist from 2 m over 14 m)."""
    vl = sc.view_layers[0]
    vl.use_pass_mist = True
    if sc.world is not None:
        sc.world.mist_settings.start, sc.world.mist_settings.depth = 2.0, 14.0
        sc.world.mist_settings.falloff = "QUADRATIC"
    g = Graph(f"News Post {sc.name}", kind="COMPOSITOR", description="Render layers through News Lens")
    with g.frame("Render layers -> News Lens"):
        rl = g.node("CompositorNodeRLayers")
        rl.b.scene = sc
        ln = g.group(lens(), Image=rl["Image"], Mist=rl["Mist"], **_lens_inputs(look, **over))
    g.output("Image", "COLOR", ln["Image"])
    sc.compositing_node_group = g.finish()


def post_over(sc, look, plate_path):
    """Plate shortcut compositor: the anchor (transparent film, studio as shadow catcher) laid over the studio plate
    (already hazed and bloomed), then the lens's fringe and vignette."""
    g = Graph(f"News Over {sc.name}", kind="COMPOSITOR", description="Anchor pass over the studio plate, then News Lens")
    with g.frame("Plate + anchor -> News Lens (no haze/glow: the plate carries them)"):
        im = g.node("CompositorNodeImage")
        im.b.image = bpy.data.images.load(plate_path, check_existing=True)
        im.b.image.reload()
        rl = g.node("CompositorNodeRLayers")
        rl.b.scene = sc
        ov = g.node("CompositorNodeAlphaOver", Background=im["Image"], Foreground=rl["Image"])
        ln = g.group(lens(), Image=ov["Image"], **_lens_inputs(look, Haze=0.0, Glow=0.0))
    g.output("Image", "COLOR", ln["Image"])
    sc.compositing_node_group = g.finish()
