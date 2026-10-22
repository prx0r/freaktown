# Hooking a new mesh into the face engine

How to prep a GLB so the stage's lip sync, blinks and expressions actually
move it. Read the checklist top to bottom, then run `face:check`. If
`face:check` says **OK**, the mesh will talk on stage.

```bash
npm run face:check -- static/avatars/<name>.glb
```

It runs the same binding the stage runs (`packages/stage-runtime/src/face/meshBinding.ts`),
so what it prints is what the stage drives.

Reference result: [`docs/media/buddha-face-mesh-binding.mp4`](media/buddha-face-mesh-binding.mp4)
(13 s, Buddha on the stand-up set, `COMIC_CLOSE`. The Meshy rig plus `face:rig` shapes:
the mouth follows the words, blinks, and the brows knit on the "annoyed" beat).

---

## How the engine picks a face (30 seconds)

| What's in the file | Mouth mode | What moves |
|---|---|---|
| ≥2 viseme morphs (`viseme_aa`, `viseme_O`, `Fcl_MTH_A`, …) | `viseme` | mouth shapes per sound |
| a `jawOpen` / `mouthOpen` morph | `morph` | mouth opens with the voice |
| a jaw bone (`Jaw`, `mixamorig:Jaw`, `CC_Base_JawRoot`) | `jaw` | the jaw bone rotates on X |
| nothing, but a skinned mesh with a `Head` bone | `morph` (procedural) | generated jaw/blink/brow/smile, plus a `[face]` warning |
| nothing at all | `none` | body sway only, plus a `[face] … NO mouth channel` warning |

Blink: `eyeBlinkLeft` + `eyeBlinkRight` (or one `blink`).
Expressions: ARKit names (`mouthSmileLeft/Right`, `browDownLeft/Right`,
`browInnerUp`, `eyeWideLeft/Right`, `mouthFrownLeft/Right`, …) drive
happy / angry / sad / surprised. Head nods and turns come from a `Head` bone.

---

## Checklist

### 1. Rig
- [ ] The mesh is **skinned** to a skeleton with a bone named `Head` (Meshy,
      Mixamo `mixamorig:Head`, AccuRIG/CC `CC_Base_Head`, and Rigify `head` all work).
- [ ] The whole head (face, ears, scalp) is weighted to `Head`, or to bones under it.
      A face weighted to `neck` won't nod, and the procedural fallback can't find it.
- [ ] Optional: a `Jaw` bone under `Head`, with the lower teeth, chin and lower lip
      weighted to it. Opening means rotating +X. That is the cheapest real mouth.

### 2. Face shapes (shape keys / blendshapes)
The best result is ARKit-named shape keys. Minimum set for a talking character:

- [ ] `jawOpen`: lower jaw and lower lip drop, the upper lip stays. **The lips have to
      part.** If the whole lower face slides down as one block, the mouth line just
      moves and nobody reads it as talking.
- [ ] `eyeBlinkLeft`, `eyeBlinkRight`: the lids close fully. With painted
      (texture) eyes, squash the eye area to a line rather than sliding it down.
- [ ] Nice to have: `mouthSmileLeft/Right`, `browInnerUp`, `browDownLeft/Right`,
      `mouthFunnel`, `mouthPucker`, `eyeWideLeft/Right`.
- [ ] Better lip sync: visemes `viseme_aa`, `viseme_E`, `viseme_I`, `viseme_O`, `viseme_U`
      (or VRoid `Fcl_MTH_A/I/U/E/O`). Two or more turns on `viseme` mode.

Names are matched case-insensitively, with separators and exporter prefixes
ignored, so `blendShape1.jawOpen`, `Jaw_Open`, `Mouth_Open` (CC4) and
`Eye_Blink_L` all work. If your tool uses another name, add it to
`MESH_FACE_ALIASES` in `src/face/meshBinding.ts` (one line, every mesh benefits)
rather than renaming in each file.

### 3. Orientation and scale
- [ ] The character **faces +Z** (glTF forward) and stands **+Y up**. Blender's glTF exporter
      does this when "+Y Up" is ticked (the default).
- [ ] Any real-world scale is fine. The stage normalises the height to 1.7 m.
- [ ] Feet at the origin is nice but not required (the stage re-centres).

### 4. Export (Blender → glTF 2.0 .glb)
- [ ] Format **glTF Binary (.glb)**.
- [ ] Mesh → **Apply Modifiers** ON. If a modifier blocks shape-key export, apply it
      to the base first. Blender won't export shape keys through unapplied
      modifiers.
- [ ] Data → **Shape Keys** ON (Animation → Shape Keys, depending on version). **Shape Key
      Normals** ON if you have them.
- [ ] Data → **Skinning** ON, and **Armature → Export Deformation Bones Only** is fine.
- [ ] Animation: leave it OFF unless you have a real `idle` clip. A one-frame rest
      pose clip (what Meshy exports) is ignored by the stage anyway.
- [ ] Draco/meshopt compression OFF for now (the loader isn't configured for it).
- [ ] Keep files under ~5 MB in git. Bigger bodies go to R2 (see `docs/BOUNDARIES.md`).

### 5. Verify
- [ ] `npm run face:check -- <file.glb>` prints `MOUTH  morph (jawOpen)` (or viseme/jaw),
      `BLINK  eyeBlinkLeft, eyeBlinkRight` and `verdict OK`.
- [ ] No `WARN … deltas are all zero` (a shape key exported with no change),
      no `NOT RENDERED` mesh carrying the morphs.
- [ ] On stage, `/stage/demo?debug=1` (or `window.__stage.telemetry().avatar`)
      shows `mouthMode` ≠ `none` and `faceRig: 'bytes'`. The browser console shows no
      `[face]` warning.
- [ ] Look at it: mouth parts on words, eyes close on blinks. The mic sits just
      below the mouth in `COMIC_MEDIUM`; check `COMIC_CLOSE` if a small mouth
      hides behind the grille.

---

## No time to sculpt? Generated shapes

For a rigged mesh with no face shapes (Meshy, Tripo, Rodin, Hunyuan…):

```bash
npm run face:rig -- in.glb static/avatars/<name>.glb        # bake jawOpen, blinks, brows, smile
npm run face:check -- static/avatars/<name>.glb
```

`face:rig` finds the head from the `Head` bone weights, finds the chin and nose
on the face's centre line, and builds:
`jawOpen` (lower face hinges like a mandible, lips part), `eyeBlinkLeft/Right`
(eyes squash to a slit), `browInnerUp`, `browDownLeft/Right`,
`mouthSmileLeft/Right`. If the mouth or eyes land in the wrong place, nudge the
landmarks:

| flag | default | moves |
|---|---|---|
| `--mouth=` | 0.38 | mouth line, as a fraction of nose-tip→chin below the nose |
| `--eyes=` | 0.45 | eye line, as a fraction of nose-tip→chin above the nose |
| `--spread=` | 0.26 | eye centres, as a fraction of head width from the middle |
| `--jaw=` | 0.26 | jaw rotation at full open (radians) |

The stage does the same thing at load for any such mesh it's given (with a
`[face]` console warning), so even an un-prepped mesh moves. Baking it means
the shapes ship with the file, show up in `face:check`, and can be fixed up in
Blender. Generated shapes are a fallback. Hand-made ARKit shapes always look
better, and lighting on squashed areas can show a faint crease, because normals
aren't morphed.

`scripts/inject_face_morphs.py` (the earlier stdlib version) is superseded by
`face:rig`. It slid the whole lower face instead of parting the lips.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Mouth never moves, `mouthMode: none` | no viseme/jawOpen/mouthOpen morph, no jaw bone | add `jawOpen` (step 2) or `npm run face:rig` |
| `face:check` OK but the lips don't part on stage | `jawOpen` moves the lips together (the whole lower face slides) | re-sculpt so the upper lip stays put, or re-bake with `face:rig --force` |
| Blink morph named `EyeClose` etc. isn't found | name not in the alias map | add it to `MESH_FACE_ALIASES.blinkBoth` / `blinkLeft` / `blinkRight` |
| Morph names right, nothing moves | shape keys exported with zero deltas, or on a hidden duplicate mesh | `face:check` flags both: re-export with modifiers applied |
| No nods | face weighted to `neck`, or no `Head` bone | weight the head to `Head` |
| Mouth hidden by the mic | small mouth, low on a big head (chibi) | check `COMIC_CLOSE`; mic fit is `DEFAULT_MIC_FIT` in `MicStand.ts` |

History: until `face-mesh-binding`, a GLB's `jawOpen` was zeroed every frame on
the feature branch, because the AU-prosody pass re-wrote all expression morphs
(`surprised` listed `jawOpen`) *after* the mouth. The mouth channel now owns
`jawOpen`, visemes and blink. Expression/prosody writes skip them, and
`meshFace.test.ts` pins it.
