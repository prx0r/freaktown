# Avatar options — ownable 3D characters that can speak (research import 2026-09-11)

The market is better than "three.ws or bust." Strongest current candidates for
**ownable/downloadable 3D characters that can actually speak**:

| Option | Own/download asset? | Body rig | Facial rig / mouth | Output | Best use |
|---|---|---|---|---|---|
| **Avatar SDK / MetaPerson** | Yes | Yes | Yes — facial blendshapes + visemes | GLB / glTF / FBX | Best proven selfie → talking avatar pipeline |
| **Threedium / Julian NXT** | Yes | Yes | **52 ARKit blendshapes** | GLB / FBX / USDZ / VRM | Very interesting all-in-one modern pipeline |
| **Neural4D** | Yes, claims export | Yes | **Visemes generated for lip-sync** | game/VRChat formats | New 2026 entrant worth testing |
| **Meshy** | Yes | Yes | weaker/less explicit facial story | GLB / FBX / OBJ | Great for stylized characters, less convincing for expressive faces |
| **three.ws** | Yes | Yes | depends on its exact facial-rig output | GLB / VRM | Still attractive for agent-native workflow |
| **Polywink** | You provide/own model | n/a | **excellent facial rigging** | rigged model | Best "upgrade any mesh into a proper face" layer |

## Avatar SDK (biggest correction)

Their current API explicitly says: one photo → **rigged, game-ready full-body
avatar with facial blendshapes**, downloadable as GLB/glTF/FBX. Export API can
embed both a roughly ARKit-style mobile blendshape set and **15 visemes**
directly into the GLB. Almost exactly the asset contract Freaktown needs.
(https://avatarsdk.com/avatar-api/) Consumer generator advertises the
**first avatar free to create and export** — immediately testable without
enterprise API access. (https://avatarsdk.com/ai-avatar-generator/)

## Threedium / Julian NXT (sleeper candidate)

Docs claim: **image/text → humanoid mesh → automatic skeleton → facial rig
with 52 ARKit blendshapes → GLB/FBX/USDZ/VRM export.** Basically the desired
Freak Pack body spec in one pipeline. If output quality holds, possibly a
better canonical-asset generator than three.ws because **ARKit 52 gives a
standardized expressive face**, not merely "rigged humanoid."
(https://threedium.io/create/3d-models/avatars/vrm) Test before committing.

## Neural4D (bake-off candidate)

Very recent, explicitly targeting: text/image → fully rigged humanoid →
VRChat topology → generated visemes. **Visemes are the mouth shapes speech
needs.** Claims automated skeletal hierarchy, skin weights, facial lip-sync
shapes. (https://www.neural4d.com/features/ai-avatar-generator) Don't trust
marketing without inspecting exports, but belongs in the benchmark.

## Meshy (better than expected)

Now advertises: text/image → textured 3D character → **auto-rig** → hundreds
of animation presets → downloadable GLB/FBX. Very useful for Freaktown
characters that don't need to resemble a real person.
(https://www.meshy.ai/use-cases/3d-avatar) Weakness remains the face —
humanoid skeletons are easy now; **a standardized expressive facial rig is
the valuable part**.

## Architecture change: define the canonical asset as a digital actor

Do **not** define the canonical Freak Pack as merely `model.glb`. Define it as:

```text
character/
  body.glb
  avatar.vrm          # optional standardized avatar representation
  portrait.webp
  manifest.json

  rig.json
    skeleton: humanoid
    facial_standard: arkit52 | viseme15 | vrm
    visemes: [...]
    expressions: [...]
```

Canonical assets must pass:

```text
✓ downloadable
✓ no vendor runtime required
✓ humanoid skeleton
✓ skinned mesh
✓ mouth movement
✓ blinking
✓ eye movement
✓ expression morphs
✓ audio → lip sync possible
✓ GLB or VRM
```

## Mouth movement is solved once you have the asset

No need for the avatar-generation vendor to perform speech. TalkingHead
(met4citizen/TalkingHead, MIT, 1.5k stars, 272 commits) takes a GLB with a
Mixamo-compatible body rig + **ARKit + Oculus viseme blendshapes** and performs
realtime lip sync in Three.js. Consumes word timestamps (ElevenLabs) or viseme
IDs (Azure) directly. Live demo in-browser; EdgeSpeaker.com runs the whole
stack (TalkingHead + Kokoro TTS + whisper + WebLLM) with zero APIs.

```text
LLM → TTS → audio + viseme/blendshape timings → owned GLB → Three.js → talking freak
```

Zero avatar vendor at runtime. Key design insight: **bitHuman isn't the avatar
system — merely an optional renderer.**

```text
OWNED CHARACTER (GLB / VRM)
  ├── browser → Three.js + TalkingHead
  ├── Unreal / Unity / VRChat / Blender
  ├── livestream
  └── cinematic vendor
```

## VRM as first-class canonical standard

Consider **VRM 1.0 as Freak Pack canonical**, GLB as lower-level interchange.
VRM adds: humanoid bone mapping, expressions, gaze, lip-sync semantics, spring
bones/hair, avatar metadata, licensing. Realistic avatars are valid VRM (not
anime-only); scan workflows already use VRM with realistic facial blendshapes.

## Fallback: separate generation from facial rigging (Polywink)

If the best-looking generator gives poor facial controls, Polywink generates
52-ish / FACS-style facial sets, MetaHuman-compatible rigs, iPhone-mocap faces
(up to 236 blendshapes) onto your own model:

```text
Meshy / Hunyuan3D / Trellis / custom generator → textured mesh → auto body rig
→ Polywink-style facial rigging → canonical VRM
```

Removes dependence on any single avatar generator.

## Bake-off plan: five lanes, same 5 references

Lanes: Avatar SDK / MetaPerson · Threedium Julian NXT · three.ws · Neural4D ·
Meshy + facial-rig postprocess. References: photoreal human · grotesque
Freaktown human · stylized humanoid · animal-ish humanoid · genuinely weird
character. Auto-score: identity similarity, topology, texture, skeleton
validity, ARKit morph count, viseme count, blink, jawOpen, mouthSmile, phoneme
test, Mixamo compat, Three.js load, VRM conversion, file size, generation
time, cost. Winner becomes `avatar_generator_primary`. Gold standard:
**52 ARKit morphs + humanoid skeleton + downloadable GLB/VRM** — smile, sneer,
blink, look, yell, talk, dance forever from a file you own.
