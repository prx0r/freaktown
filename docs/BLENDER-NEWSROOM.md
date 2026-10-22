# Blender newsroom

A procedural Blender studio for the newsroom show (three looks), baked to GLBs the web stage can load, plus a
Blender **performance bake**: a stretch of a real Goodnight timeline replayed on the anchor in Blender and rendered
with Cycles. Everything heavy runs in GitHub Actions on Blender 5.2.2 (x86 Linux); Blender has no official
linux-arm64 build, so nothing here needs Blender locally.

## Pieces

| File | What it does |
| --- | --- |
| `sets/blender/newsroom_build.py` | One Geometry Nodes modifier ("News Set") builds the studio: room, backdrop, desk, video wall, practicals, furniture. Seats the default VRM anchor, sets camera marks (wide / medium / close / wall 3/4), renders Cycles stills, exports a GLB with baked albedo. |
| `sets/blender/newsroom_presets/*.json` | The three looks: `late-night` (blue LED wall), `goodnight` (wood, bookshelves, night windows, moon), `breaking` (red accents). |
| `sets/blender/newsroom_cards/<preset>/` | Wall and desk-band cards for the stills, painted with the web stage's own `paintWallCard` (`newsroom_cards.mjs`). |
| `sets/blender/newsroom_perform.py` | Bakes a compiled newsroom timeline into keyframes (mouth visemes from measured words, blinks, affect, head turn, camera cues with the web stage's easing, which wall card is up) and renders a chunk of it. |
| `sets/blender/perform/goodnight-2026-10-22/` | The clip: timeline cut to 15.44–25.44 s of the 2026-10-22 Goodnight episode, its wall cards, desk brand and programme audio. |
| `.github/workflows/blender-newsroom.yml` | `check` (library lint), `preset` × 3 (stills + GLB + .blend validation), `perform` × 8 (one eighth of the clip each), `encode` (MP4 with audio + throughput summary). |
| `apps/live/public/stage-sets/newsroom-*.glb` | The CI-baked GLBs. Opt in on the web stage with `?newsset=late-night|goodnight|breaking`; the wall screen and desk band stay blank material slots so the stage paints headlines on them. |

## Running it

Push to `newsroom-blender` (paths filter: `sets/blender/newsroom*`, presets, perform, cards, the workflow) or
dispatch the workflow by hand: `samples` (stills, default 96), `clip_samples` (clip, default 16), `clip` (directory
under `sets/blender/perform`). Every ref update starts a full run (~25–35 min wall clock), so batch commits and push
once.

Artefacts: `newsroom-<preset>` (renders/, GLB, graph dump, logs), `perform-frames-<k>` (PNG frames, per-chunk
stats, keys.json), `newsroom-performance` (MP4 + `throughput.json`).

## Things that bit us (fixed)

- **Black clip frames.** Camera marks were read from `matrix_world` of cameras created in the same run, which has no
  evaluated matrix until a depsgraph update: every mark sat at the origin looking at the floor. Marks now come from
  `location` / `rotation_euler`.
- **Magenta wall and desk band in the stills.** Card images were loaded from CWD-relative paths; `save_as_mainfile`
  remapped them to `/sets/...` before the render, so Cycles reported missing images. Paths are made absolute.
- **T-pose sleeve "wings".** VRoid sleeves and shoulder skin hang off `J_Aim_*_TopsUpperArm` / `J_Aim_*_Shoulder`,
  which aim at the forearm through `VRMC_node_constraint`. three-vrm evaluates that; Blender's glTF import drops it,
  so the sleeves stayed horizontal while the arms went down. The seated pose now swings those bones with the arm.
- **Encode found no frames.** `download-artifact` with `merge-multiple` keeps paths below the common root (`out/`),
  so frames land in `dl/frames/`, not `dl/`.
- **Clipped wall title at ~217.5 s (web stage, `packages/newsroom/src/compile.ts`).** The close card used to come
  back at the start of the eased pull-out while the camera still framed the cropped wall. It now stays ambient until
  60 % of the move, mirroring the push-in swap.

## Throughput (measured)

1280×720, 16 spp Cycles CPU, standard 4-vCPU `ubuntu-24.04` runner, 25 fps:

Two full runs, 16 chunks of ~32 frames (runs 39725231781 and 39727047882):

| Runner CPU (GitHub's pick) | chunks | steady s/frame |
| --- | --- | --- |
| AMD EPYC 9V45 | 4 | 14.8–16.0 (≈15.4) |
| Intel Xeon 8573C | 1 | 22.3 |
| AMD EPYC 9V74 | 1 | 24.2 |
| Intel Xeon 8370C | 2 | 26.4–26.6 |
| AMD EPYC 7763 | 8 | 31.1–33.7 (≈32.3) |
| **All chunks, runner-seconds / frames** | 16 | **26.2** (6,632 s + 6,483 s for 2 × 250 frames) |

First frame of each chunk adds ~5–6 s (BVH build); the timeline bake itself is 1.4–3.1 s per chunk. Ten seconds of
clip took ~18 min wall clock on 8 runners (slowest chunk 1,061 s).

The runner CPU matters more than the shot: chunks 0–4 are all the same wall 3/4 shot, yet chunks on AMD EPYC
9V45 ran ~15 s/frame and chunks on EPYC 7763 / Xeon 8370C ran 26–33 s/frame. GitHub picks the machine; plan on the
mean.

## Full episode estimate

The 2026-10-22 episode is 224.9 s = 5,623 frames at 25 fps.

| Option | s/frame | Render time, 5,623 frames | Cost |
| --- | --- | --- | --- |
| GitHub 4-vCPU runners, measured mean | 26.2 | 40.9 runner-hours (24–50 h depending on CPU draw); ~2.1 h wall on 20 parallel jobs | free (standard runners, public repo); $29.50 at the $0.012/min 4-core larger-runner rate |
| RTX 4090 (RunPod $0.34–0.89/h), est. 100–175× | 0.15–0.26 | 14–25 min | $0.08–0.36 + pod time |
| A10 (~$0.24/h), est. 25–40× | 0.66–1.05 | 61–98 min | $0.25–0.39 + pod time |

GPU figures are estimates, not measurements: the assumed speed-ups (RTX 4090 ~100–175×, A10 ~25–40× a 4-vCPU
runner) are applied to the measured mean s/frame. They leave out per-chunk overhead (Blender start, scene build
and keyframe bake ≈ 20–40 s per chunk, first-frame BVH build) and pod start-up/upload time. No GPU was rented to
check them.

## Known gaps

- The `medium` still crops the top of the wall headline, and the empty second chair hides part of the wall footer.
  It isn't used by the clip; adjust `cam_medium` in `cameras()` if it starts being used.
- Close-ups sit the anchor low with a lot of desk in frame; the web stage's framing tests don't cover Blender.
- Only the default VRM is exercised; other avatars may need their own constraint bones swung (see sleeves above).
- Lip-sync reads weak: `Fcl_MTH_*` are keyed to 0.85 on open vowels (keys.json) but in the close-up the mouth
  barely parts. Either raise the viseme gain for VRoid faces or check the shape keys' slider range. Not checked frame
  by frame against the audio.
- During the clip's push-in (~8.4 s) the wall headline is clipped at the top of frame. The web stage swaps the wall
  to ambient part-way through a push-in; the Blender wall-card keys don't yet.
- On free runners a full episode needs more than the 8 chunks used here: with the 150 min job timeout and the slow
  CPUs, plan on 24–32 chunks.
