# VENUEGUIDE — the law for making venues (CANONICAL, 2026-10-17)

Read this BEFORE creating any venue, prompting any image, or spending a
single credit. If it conflicts with any older doc, this wins.

## The one rule

**The venue GLB is the bare-bones shell. Everything else is a layer we add
after.** Adding is easier than removing. Anything baked into the mesh is
frozen forever; anything layered stays changeable, animatable, removable.

## What MAY be baked (shell only)

Floor, walls, ceiling, stage deck, bar block, curtain rails (rails — not
fabric), door/window HOLES with nothing in them (a basement has no windows;
cut no holes at all). Bare geometry, neutrally lit, no mood.

## What is BANNED from the bake (never in the GLB, never in shell prompts)

1. People. Obviously. No audience, no faces, no silhouettes.
2. Windows and daylight. It's a cellar. There are none.
3. LIGHT. No spotlight, no haze cone, no cans, no practicals, no glow of
   any kind. The shell ships FLAT — lighting is 100% our live rig on top.
   A baked highlight is a lie the light rig can never un-tell.
4. Furniture and gear. No mic stand, no stools, no tables, no chairs.
5. Fabric and dressing. No curtains (rails only), no posters, no photos,
   no frames, no candles, no strings, no ashtrays.
6. Marks and text. No chalk sigil, no EXIT sign, no LIVE sign, no logos,
   no legible anything. All marks arrive as decal layers.
7. Sky, sun, weather. See rule 2.

## The layer stack (build in this order, each replaceable alone)

0. SHELL — baked GLB (this guide). Bare, flat, dumb.
1. PROPS — procedural/GLB meshes we own (mic stand, tables, chairs,
   curtain fabric, bar detail). Registry: docs/VENUE-PROPS.md.
2. DRESSING — decals we own (photos on walls, posters, chalk sigil,
   handbills). Swappable per night, per act.
3. LIGHT — live rig only (house cans, follow-spot, washes, haze).
   Spec per venue: `light_rig` in the venue JSON. Nothing baked.
4. MOTION — animated layer (EXIT flicker, LIVE sign buzz, curtain sway,
   haze drift). Anything that moves or blinks lives here, never in mesh.

## Why (so nobody "helpfully" re-bakes)

Marble and image models LOVE dressing rooms: candles, strings, glowing
runes, volumetric god-rays baked into geometry. Every one of those is a
frozen decision that fights the live show. The Cauldron feels magical
because of what we ADD (sigil decal + haze + spot), not what we bake.

## Input lighting for reconstruction (not the final look)

Shoot the shell input SOFT, NEUTRAL (~5000K), MODERATELY BRIGHT: readable
brick texture, visible corners, no hard shadows, no colored light, no
pitch-black areas. Darkness destroys the albedo detail the splat needs.
The nightclub darkness is the LIVE grade on top, never the input. Input
bright ≠ final bright.

## Relight caveat (test before committing)

Gaussian splats bake appearance — Three.js lights will NOT make splat
brick respond like PBR materials. If the walls look painted-on under the
live rig, fall back to the textured-mesh export for reactive surfaces
(mesh takes real lights; splat doesn't). Our darkness helps: a near-dark
grade hides the relight gap. Test splat-under-rig first; mesh is plan B.

## One baked exception

A permanently distinctive architectural feature (e.g. a crooked brick
arch around the stage) MAY bake into Marble — character that benefits
from being environment. Everything else stays layered.

## Gate checklist (every shell frame must answer YES to all)

- [ ] No people, no faces, no silhouettes?
- [ ] No windows, no daylight, no sky?
- [ ] Soft neutral ~5000K input light, no glow, no haze, no hard shadows?
- [ ] Deck and floor hold NOTHING?
- [ ] No fabric, no furniture, no gear?
- [ ] No marks, text, signs, or logos?
- [ ] Floor, walls, ceiling, deck all visible (spatial context for Atlas)?

## One shell, many layouts (the venue is a room, not a set)

The Comedy Cellar formula: small intimate room, dark low ceiling, tables
gathered AROUND a small stage — surround, not cinema rows. One permanent
shell plays every format: standup rows one night, poker table the next,
mafia circle after. Layouts are prop-layer presets (furniture arrangements
in the venue JSON), never separate rooms. Build the shell once; redress it
per game.

## Enforcement

`scripts/marble_cauldron.py --live` refuses without `--yes-i-read-the-guide`
AND prints this checklist. Concept batches are gate-checked by
`scripts/validate_concepts.py` (shell frames fail on mic/furniture/people/
windows). Venue JSONs carry `glb.sha256` pinned to shell-only meshes.
