# Blender stage sets (trial): the comedy club as one Geometry Nodes graph

This is a trial of building FUNNIER stage sets in **Blender 5.2** as procedural node graphs, using the
[video-to-blender](https://github.com/gokayfem/video-to-blender) skill (MIT): its **nodekit** graph builder and
its tested **NK** node-group library. The first set is the stand-up comedy club. The three.js procedural set
(`packages/stage-runtime/src/StageSet.ts`) is still the default; the Blender builds are opt-in variants.

```
sets/blender/club_build.py        the build script: one "Club Set" Geometry Nodes modifier + scene + export
sets/blender/presets/*.json       dive, late-night TV, basement open mic, theatre
sets/blender/ci_setup.sh          installs Blender 5.2.2 (SHA-256 checked) + video-to-blender at a pinned commit
.github/workflows/blender-sets.yml  CI: library check, Cycles stills, baked GLBs, a camera-move clip
apps/live/public/stage-sets/      the exported GLBs the web stage loads (club-<preset>.glb)
docs/media/blender-club/          renders and web-stage screenshots
```

## What the graph builds

One modifier group, **Club Set**, on an empty mesh object builds the whole room. A **Primary** panel holds the
macro controls; every part's own controls are forwarded in collapsed panels (`Room`, `Stage`, `Curtains`,
`Props`, `Neon`, `Spot`, `Audience`).

| Part group | What it makes | NK library groups used |
|---|---|---|
| Club Room | house floor, brick back wall, side/rear walls, ceiling, exit door + sign, exposed pipes | NK Rod; materials NK Stucco + `Club Brick Paint` (Brick Texture, soot, NK Stucco paint-over) |
| Club Stage | riser of chamfered planks (own grain each), black skirt, lip, side steps | NK Chamfer Box, NK Store Local Coords, NK Wood Grain |
| Club Curtains | side curtains (sine folds, gathered at the floor), optional back drape, scalloped valance | NK Felt |
| Club Props | mic stand (mic 0.11 m in front of the mouth, like FUNNIER's fitted mic), bar stool with a beer, set list | NK Rod, NK Profile Revolve, NK Ring |
| Club Neon | blank neon sign: dark board + two rounded neon tubes (the web stage draws the text) | NK Rounded Box |
| Club Spot | truss, lamp cans, a visible spotlight cone fading from lamp to floor | NK Rod |
| Club Audience | cafe tables Poisson-scattered with a clear aisle, chairs facing their table, bottles/pints/candles, seated silhouettes turned to the stage; or raked theatre rows | NK Scatter On Surface, NK Chamfer Box, NK Rounded Box, NK Profile Revolve, NK Glow Glass, NK Attribute Tint |

Haze is a compositor effect (NK Haze Over Sky on the Mist pass) plus NK Soft Glow, as the library recommends.
Lights and cameras are plain scene objects set up by the script from the same numbers the graph uses.

Primary controls: Room Width, Room Depth, Ceiling Height, Riser Height, Theatre Rows, Crowd, Clutter, Paint Cover,
Side Curtain Width, Neon Color, Seed.

Coordinates: metres, Z up, stage top at z = 0, performer at the origin facing -Y, back wall at y = 2.3. That is
the three.js stage's layout; glTF export turns Blender -Y into three.js +Z, so the GLB drops straight in.

## Install Blender 5.2

Blender 5.2+ is required (the nodekit API targets 5.2). Debian's apt only has 4.3.

**x86-64 Linux / CI (recommended)**

```bash
bash sets/blender/ci_setup.sh            # downloads blender-5.2.2-linux-x64, checks SHA-256, clones video-to-blender
export BLENDER=~/blender/blender-5.2.2-linux-x64/blender
export V2B_SKILL=~/video-to-blender/skills/procedural-blender-nodes
"$BLENDER" -b --version
```

macOS (arm64) and Windows have official 5.2 builds on https://download.blender.org/release/Blender5.2/.

**Linux arm64 (aarch64)**: there is no official linux-arm64 build of 5.2 (download.blender.org, the daily
builder, Flathub, Snap and PyPI `bpy` wheels are all x86-64 only for Linux, and conda-forge has no Blender).
Building from source does not fit in under an hour on a small box. What works is running the official x86-64
build under **qemu-user** (no root needed):

```bash
# qemu-user is a static binary; take it and an amd64 glibc + X11/GL runtime from Debian's pool
mkdir -p ~/emu && cd ~/emu
curl -sO http://deb.debian.org/debian/pool/main/q/qemu/qemu-user_10.0.2+ds-2+deb13u1~bpo12+1_arm64.deb
dpkg -x qemu-user_*.deb root          # then dpkg -x the amd64 debs: libc6 libstdc++6 libgcc-s1 zlib1g libx11-6
                                      # libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6
                                      # libgl1 libegl1 (and their dependencies)
ln -s usr/lib64 root/lib64            # so the x86-64 loader is found under -L
cat > ~/emu/blender <<'SH'
#!/bin/bash
E=$HOME/emu; B=$E/blender-5.2.2-linux-x64
exec $E/root/usr/bin/qemu-x86_64 -L $E/root -E LD_LIBRARY_PATH=$B/lib:$E/root/usr/lib/x86_64-linux-gnu $B/blender "$@"
SH
```

Under emulation `blender -b --version` takes about 1 s, `nodes_tools.py check` passes in about 45 s, and building
a preset plus a flat-colour GLB takes about 1 minute. Cycles works but is far too slow for real renders (a
320 x 240, 16-sample cube did not finish in 8 minutes), and EEVEE needs a GPU/EGL. So: iterate on the graph and
export locally under emulation, and let CI (x86-64) do the Cycles stills, the bakes and the clip.

## Build

```bash
# graph + scene only (prints vertex/face counts, node warnings and lint; must be zero)
"$BLENDER" -b --factory-startup --python sets/blender/club_build.py -- --skill "$V2B_SKILL" \
    --preset dive --out out/club_dive.blend

# stills: 1600 px Cycles, the house-wide view and the performer's eye view
... --render out/renders --views wide,eye --width 1600 --samples 96

# GLB for the web stage (albedo baked into JPEG textures; --bake 0 = flat colours, fast)
... --glb apps/live/public/stage-sets/club-dive.glb --bake 2048

# a camera move (PNG frames; encode with ffmpeg -framerate 24 -i tt_%04d.png)
... --turntable out/tt --frames 240 --tt-width 1280 --tt-samples 20

# validate the saved file the way a user meets it (warnings, eval time, camera clearance, lint)
"$BLENDER" -b out/club_dive.blend --python "$V2B_SKILL/scripts/validate.py" -- --prefix "Club "
```

In CI, push to the `sets-blender-club` branch (or run the **blender sets** workflow by hand) and download the
`club-<preset>` and `club-camera-move` artifacts. The camera move (240 frames, 10 s at 24 fps) renders as four
parallel jobs (`--chunk K/4`, one quarter of the frames each, persistent data so the BVH is built once per job)
and an encode job that joins the frames into the MP4.

## Add a preset

A preset is a flat JSON of modifier inputs by display name (colours as linear RGBA lists), plus an optional
`_look` block for the scene (light energies and colours, haze amount/colour/depth, ambient):

```json
{ "Room Width": 9.0, "Ceiling Height": 3.2, "Crowd": 0.4, "Neon Color": [0.1, 1.0, 0.3, 1.0], "Seed": 21,
  "_look": { "key": 800, "haze": 0.6, "haze_color": "#20282A" } }
```

Save it as `sets/blender/presets/NN-name.json`; `--preset name` finds it by substring. Presets should mostly
touch Primary controls; if one needs many detailed values, a macro control is missing. To ship it to the web
stage, export `apps/live/public/stage-sets/club-name.glb` and add the id to `CLUB_BLENDER_VARIANTS` in
`packages/stage-runtime/src/sets/definitions.ts`.

## Export and the web stage

`--glb` applies the modifier, splits the mesh by the `club_part` face attribute into named glTF nodes
(`club_wall`, `club_stage`, `club_audience`, `club_mic`, `club_beam`, `club_neon`, ...), swaps every procedural
material for a glTF-friendly Principled BSDF (baked albedo, or attribute/flat colours, emission for the neon,
candles and exit sign), and writes a Y-up GLB with JPEG textures. Keep each GLB under 15 MB: lower `--bake`,
the crowd, or the segment counts in the person/seat groups.

On the stand-up page the variants are opt-in: `/stage/<episode>?clubset=dive` (`late-night-tv`,
`basement-open-mic`, `theatre`). The runtime (`StageSet.loadVariant`) hides the procedural room (deck, wall,
curtains, stool, crowd), keeps the three.js lights, beam, haze and the mic fitted to the performer's mouth, hides
the GLB's own `club_mic` and `club_beam`, and moves the neon text onto the GLB's sign board. The GLB's house walls
(`club_house`, facing in) render front-side only, so a shallow room such as the basement never walls off the
WIDE_STAGE camera, which sits behind its rear wall. If the GLB fails to
load, the procedural room comes back. `runtime.setVariantStatus()` reports which one is showing.
`apps/live/e2e/club-variant-shots.mjs` takes desktop and mobile screenshots of each variant with the performer.

## Verdict

- **Blender for hero baked environments.** One node graph gives four believable rooms from a few macro
  controls, with real bounce light, Cycles stills for docs and marketing, and baked albedo in a GLB the web
  stage loads as-is. Builds need x86 Linux (no official arm64 Blender), so they run in CI, not on the dev box.
- **three.js for anything live-reactive.** The spot, beam, haze, mic fitted to the performer's mouth, neon text
  and camera cuts stay in the runtime, where they can follow the performance frame by frame. A baked GLB can't
  react, so the variant hides its own mic and beam and keeps the three.js ones.

## Credits

- [video-to-blender](https://github.com/gokayfem/video-to-blender) by gokayfem, MIT licence: nodekit, the NK
  node-group library (shapes, scatter, materials, post), its checker and validator, and the workflow (Primary
  macro panel, presets, validate). Used unmodified at commit `bfeca3ff77d1468f3f9c6a801342cb6286e3f6b1`, cloned at
  build time, not vendored.
- [Blender](https://www.blender.org/) 5.2.2 (GPL); the generated GLBs are output, not Blender code.

## Camera kit (sets/blender/club_cameras.py)

One kit for every preset and every show, derived from the room numbers and the comic's **measured** eye height:
`CAM_WIDE` (from the house, above that row's heads, lens fitted to the stage lip, capped at 8.5 m of stage so a
theatre doesn't shrink the comic to a speck), `CAM_MEDIUM` (waist-up), `CAM_CLOSE` (head and shoulders, 3/4 from
camera-right so the mic never crosses the lips), `CAM_XCU` (eyes and mouth, f/2), `CAM_OTS` (over the comic's right
shoulder onto the house), `CAM_PUSH_A/B` (the two ends of the slow push-in), `CAM_CROWD` (low from the stage lip,
aimed at the measured centroid of the seated people near the stage, so a sparse open mic still has faces in it),
`CAM_PERFORMER_EYE`, plus marks `MARK_EYE / MARK_MOUTH / MARK_CROWD / MARK_LIP`. Medium, close and push frame the
eyes exactly on the upper third (camera pitch solved for cameras above or below the eye line).

Shot grammar, `pick_shots(timeline)`: open wide; push in across a bit's setups; close-up on the look before a punch;
XCU into the hit word; crowd reverse (OTS, then CROWD) on a big laugh and back to the close-up for the reaction; tag
laughs stay on the comic; act-outs go medium; the last laugh of a closer pulls out wide; no shot shorter than 1.4 s.
Tests: `tests/contract/test_club_cameras.py` (eye line, wide inside the room and above the heads, stage-lip corners
in frame, the mic clear of the mouth in the close-up, the grammar).

`club_build.py --comic static/avatars/default-v1.vrm --views kit` renders every kit camera with the comic standing at
the mic (the mic is dropped to chin height, 0.13 m in front, so it never covers the mouth).

Look fixes in this round:
- **Beam near the camera:** the cone now fades in from the lens (first 5-35% of its length) and fades out within
  ~3.5 m of whatever camera looks at it (Camera Data view distance), on top of the earlier fade before the floor (no
  dome). OTS, crowd and performer-eye shots hide it.
- **Spill:** the key spot aims at the comic's chest with a body-sized cone and a soft 0.55 blend, instead of a deck-
  sized cone aimed at the floor that splashed the back wall and curtains; the comic gets a motivated soft key from the
  spot's direction, a cool and a warm rim from upstage and a low bounce (`comic.py`), and the spot is dimmed on the
  bright MToon albedo (`key_on_comic`).
- **Basement / theatre wide:** the wide is no longer a fixed 24 mm from y = -8.2 (inside the theatre rows, a fish-eye
  in the basement): it is solved per room (see above).
- OIDN denoising is explicit on CI; `CLUB_DENOISE=0` for local aarch64 previews (OIDN dies with SIGILL there).

## Expressive face proof (sets/blender/club_face.py)

See docs/FACE-EXPRESSIVE.md. CI renders ten emotion close-ups through the expressive channels (talk aa/oh, happy,
smirk, the look, surprised, sad, angry, eye dart, wink) and a ~7 s test performance with audio
(`sets/blender/perform/club-hark-punch`: the look, "Hark. You have arrived. Some time ago.", the laugh and the
reaction; Fish s2.1-pro-free voice, procedural crowd laugh, built by `sets/blender/club_clip.py`).
