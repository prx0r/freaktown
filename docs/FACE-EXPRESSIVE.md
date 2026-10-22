# Expressive faces: audit + the engine guarantee

One channel set for every mesh, driven with the same numbers in the three.js stage and in the Blender bake, and a
check that says up front whether a mesh can express at all.

- Map: `packages/stage-runtime/src/face/expressive-map.json`
- Runtime: `packages/stage-runtime/src/face/expressive.ts` (`checkFace`, `channelsFromState`, `shapesFor`,
  `ExpressiveFace`), wired into `FaceChannel.apply` → `GlbAvatar.setExpressive` / `VrmAvatar.setExpressive`
- Bake: `sets/blender/face_express.py` (Python mirror) used by `sets/blender/club_face.py` and `comic.py`
- Parity: `tests/fixtures/face-expressive-golden.json` (written by the Python mirror), checked by
  `packages/stage-runtime/tests/expressive.test.ts` and `tests/contract/test_face_expressive.py`

## 1. Audit: what the runtime drove before this change

| Layer | What it actually drives |
|---|---|
| `VrmAvatar` | VRM presets only, through `expressionManager`: visemes `aa ih ou ee oh` (when ≥ 2 exist), `blink` (both eyes; `blinkLeft/Right` never written), emotions `happy angry sad surprised relaxed`. `setBlendshapes` (ARKit) writes only VRM *custom* expressions named like ARKit: `default-v1.vrm` has none, so for the house avatar the ARKit path is a no-op. Gaze: `vrm.lookAt.target`. |
| VRoid presets | `happy/angry/sad/surprised/relaxed` bind to `Fcl_ALL_*` whole-face shapes: they also close the eyes and move the mouth, so an emotion fights the visemes and the blink. There is no brow-only, squint, smirk or per-eye channel. |
| `GlbAvatar` | Alias binding of morphs: visemes, `open` (or a jaw bone, 0.35 rad), blink, emotions, AU prosody (brow flash, eye). `setBlendshapes` writes raw ARKit names present in the bytes. |
| `BasicAvatar` | Procedural face, a few ARKit names by construction. |
| `FaceChannel` | base (Performer emotions + blink + plan/text mouth) + affect hold (A/V/P → emotions) + live ARKit stream (overrides mouth/blink while fresh). `faceToArkit` re-expresses a plan face for ARKit-only GLBs. |
| ARKit-52 | Vocabulary + `arkitToFace` / `faceToArkit` maps exist; on VRMs nothing consumes them. |
| Timeline (sketch compiler) | `dialogue.line` (+ measured words) and a `face.expression` with the line's emotion at intensity 0.6 for the whole line; `react`/`gesture` items → `face.smug`, `face.annoyed`, `gesture.*`; `gaze.look` (scripted looks, idle glances, nods). |
| Delivery (characters MCP) | `warm / deliberate / deadpan / manic`, `pause_ms`, `hold_ms`, emphasis (the hit word, uppercased in the sketch). Only timing and TTS use them: the hit word is not a face cue, and deadpan punches carry `emotion: neutral`, so the face goes flat exactly on the punch. |
| Blender newsroom bake (PR #12) | Visemes keyed at `sin × 0.85` (mean ≈ 0.54), affect drives `Fcl_ALL_*` × 0.45 while speaking, one random blink cadence, head nod/sway. No brows, squint, smirk or eye darts. |

**Weak VRoid lip-sync, root cause.** The shape-key slider range is the normal 0..1 and the binding works
(`Face_Blendshape.Fcl_MTH_A` normalises to `fclmtha`). The problem is that `Fcl_MTH_A` at 1.0 is a small opening on
this model (measured with renders), `Fcl_MTH_I/E/U` barely part the lips at all, and the bake peaked at 0.85.
Fix: the map drives `aa → Fcl_MTH_A × 1.35`, gives I/E/U/O some A for jaw, and raises `slider_max` to 1.5 (Blender)
— three.js influences above 1 extrapolate the same way.

## 2. The channels

`open, aa, ih, ou, ee, oh, blinkL, blinkR, smileL, smileR, frown, browUp, browDown, browSad, squint, eyeWide, lookX,
lookY`. Emotions mix into channels (`happy` = both smiles 0.8 + squint 0.35 + a little brow), and expressions are
composed from brow / eye / mouth parts, never VRoid's `Fcl_ALL_*`. While speaking, smiles and frowns are scaled down so
they don't fight the lips; brows and eyes keep full range. A missing one-sided smile is **generated** from the
symmetric one with the same soft side mask in both engines (`Fcl_MTH_Fun_L/R` on VRoid), so smirks work on the house
avatar.

Rigs in the map: `vroid` (Fcl_*), `arkit` (ARKit-52 + eyeLook* gaze morphs), `oculus` (viseme_*), `vrm` (presets, the
fallback). Gaze uses eye bones when the rig has them (`J_Adj_L/R_FaceEye`, ±12° yaw / ±8° pitch).

## 3. The check

`checkFace(names, bones)` / `python3 sets/blender/face_express.py check <file.glb|vrm>`:

- **fail** when a core group has no shape at all: mouth, blink, smile, brow. The mesh cannot express.
  `club_face.py --strict` exits non-zero; the stage gets `driver.faceCheck` to log or refuse.
- **warn** for each missing extended capability: 5 distinct visemes (not all the same jaw), one-sided smiles, frown,
  sad brow, squint, wide eyes, gaze.

| Mesh | Result |
|---|---|
| `static/avatars/default-v1.vrm` (VRoid) | ok: all 16 shape channels + eye-bone gaze (smirk shapes generated) |
| a full ARKit-52 head | ok |
| `agent.hark-lantern.glb` (5 morphs, no skeleton; characters MCP branch) | **fail**: no brow; warns no visemes, frown, sad brow, squint, wide eyes, gaze |
| a mesh with no recognisable shapes | fail: mouth, blink, smile, brow |

Fix for a failing mesh: add the missing shapes with the face:rig generator (PR #10, `face-mesh-binding`), or use a
VRM with full expressions.

## 4. How the Blender bake acts a beat (club_face.py)

- mouth: the measured word under the playhead → its vowel group → viseme; amplitude is the VO's own loudness per frame
  (timeline `env`) × a syllable shape, so the jaw follows the real audio
- blinks: seeded 2.2–4.5 s, none during the stare, one right after the punch lands
- gaze: darts across the house during setups; eyes and head on the lens for the look and the punch
- the look before the punch: brows down 0.35, squint 0.3; the hit word: brow flash; after the line: smirk + squint +
  head tilt and a small nod; during the laugh: a glance across the crowd

## Not covered here

- `meshBinding.ts` / `face:check` / `face:rig` from PR #10 live on `face-mesh-binding` (merged into
  `feature/mutuals-acting-party-smiles`), not on this branch. `expressive.ts` uses the same name normalisation; folding
  the two alias tables into one is a follow-up.
- Upper-body gestures (shrug, open hands, the desk-bell hand on "Hark.") are not keyed yet: the head, chest breath and
  face are.
- The sketch compiler does not yet emit `look-before-punch`, hit-word or post-laugh reaction cues; `club_face.py`
  derives them from the clip timeline (looks, `hit_ms`, laughs).
