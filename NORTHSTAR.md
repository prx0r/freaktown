# NORTHSTAR — canonical avatar doctrine (set 2026-09-11)

> **A Freak owns its appearance. Renderers borrow it.**

## Decision

**MetaPerson / Avatar SDK as the primary canonical-avatar generator** for
human/humanoid Freaks. Keep the current **three.ws path as fallback and as
the weird-character lane**. Keep **bitHuman/Runway strictly as optional
renderers**. Bring-your-own GLB/VRM stays first-class forever (`/api/avatar/upload`).
BASIC procedural body stays as the guaranteed instant fallback.

## Why MetaPerson fits this codebase

The Freaktown avatar path is already:

```text
portrait → generator → avatar.glb → sniff actual capabilities → avatar.json → Freak Pack → renderers
```

sniffing for `rigged, humanoid_skin, facial_morphs, lipsync, morph_names`
with explicit ARKit-mouth and Oculus-viseme recognition. MetaPerson exports
almost exactly what that code looks for: downloadable GLB/glTF/FBX, skeleton,
facial/body blendshapes, configurable embedded sets — their own sample exports
`mobile_51` + `visemes_15`. 2026 release notes: viseme export added March,
missing-viseme bug fixed April, lip-sync updated. Their LiveSpeak animates the
same exported GLB from raw audio locally in the browser (ElevenLabs + raw
audio supported). Documented Unreal workflow: download GLB, load as skeletal
mesh at runtime — aligns with PogWorld.

Caveat: proper REST API is Enterprise-only; lower tiers use iframe/JS creator
with exports on Pro/Enterprise. Do NOT rewrite around their REST API yet.
First avatar free to create and export — testable now.

## Why not three.ws primary

History contains both "Forge makes STATIC meshes (no rig, no mouth morphs)"
and a higher rung assuming forge → auto-rig → ARKit-52, compensated by
sniffing the returned GLB instead of trusting provider claims. Excellent
defensive architecture — and evidence three.ws is not identity-foundation
material today. Keep it as the creative/weird lane (Meshy alongside later).

## Why bitHuman is not the avatar system

bitHuman would violate the Pogtown doctrine ("Freak Pack is portable
identity"; "Unreal is a renderer, never the rules authority"). Rented
`.imx` identity ≠ owned asset. bitHuman is a premium realtime renderer
(Essence closeups, Expression live); Runway is the highlight renderer
(best laugh, trailers — never full sets).

## Tier table (runtime cost → canonical?)

| Tier | Use | Cost | Canonical? |
|---|---|---|---|
| BASIC | instant fallback | ~0 | no |
| GLB MetaPerson | normal show/game/web | ~0 | **YES** |
| GLB three.ws | weird/generated freaks | ~0 | yes, when quality passes |
| bitHuman Essence | host/interview closeups | paid | no |
| bitHuman Expression | premium live closeup | paid | no |
| Runway | viral/cinematic clip | expensive | no |
| Unreal | PogWorld/show | GPU | consumes canonical |

## Two creation lanes (Freaktown is weird; MetaPerson is human)

- `HUMANOID`: photo → MetaPerson → skeleton + face.
- `FREAK`: portrait/prompt → three.ws / Meshy / future generators →
  auto-rig → facial rig if possible.
- Both end in `freak.character/v1`. Provider-neutral manifest is why this works.

## Canonical asset shape (target)

```json
{
  "appearance": {
    "canonical": { "format": "glb", "uri": "r2://freaks/gregor/avatar.glb", "sha256": "..." },
    "derivatives": { "vrm": "r2://freaks/gregor/avatar.vrm" }
  },
  "rig": { "skeleton": "humanoid", "face": "mobile_51", "visemes": "visemes_15" }
}
```

GLB primary (neutral base: Three.js, Blender, Unity, Unreal ingestion,
post-processing); VRM as derived interoperability representation (humanoid
semantics), not mandatory canonical.

## Face profiles (build this — the moat)

Sniffer must understand explicit profiles and normalize to one vocabulary:

```text
FACE_PROFILE_NONE | ARKIT_52 | METAPERSON_MOBILE51 | VISEMES15 | OCULUS | VRM | CUSTOM
→ POG_FACE_V1: jaw_open, blink_left/right, smile/frown left/right,
   viseme_sil/aa/ee/ih/oh/ou, …
```

Games/agents emit semantic intents (`{expression: smirk, intensity: 0.74}`),
never `morphTarget37`. Every renderer maps intent → local morphs. Same event
drives Three.js, MetaPerson, bitHuman, Unreal MetaHuman, VRM, future.

## Provider interface (build this)

```text
AvatarProvider: generate() → poll() → download() → inspect()
providers/metaperson.py → providers/threews.py → providers/upload.py → BASIC
Selection: MetaPerson if configured → three.ws forge → three.ws mesh → BASIC.
SAVE FREAK → instant BASIC body → playable immediately → async generation → hot-swap canonical.
```

## Bake-off (before committing architecture)

Lanes: Avatar SDK · Threedium Julian NXT · three.ws · Neural4D · Meshy+postprocess.
Same 5 references (photoreal, grotesque, stylized, animal-ish, weird).
Auto-score: identity, topology, texture, skeleton, ARKit count, viseme count,
blink/jawOpen/smile, phoneme test, Mixamo compat, Three.js load, VRM conversion,
size, time, cost. Winner = `avatar_generator_primary`. Gold standard: 52 ARKit
morphs (or mobile_51+visemes_15 equivalent) + humanoid skeleton + downloadable GLB/VRM.

## Sources

- Avatar SDK export/visemes: https://api.avatarsdk.com/ ; release notes: https://docs.metaperson.avatarsdk.com/business-integration/release_notes/desktop/
- LiveSpeak: https://docs.metaperson.avatarsdk.com/livespeak/integration/
- Unreal sample: https://docs.metaperson.avatarsdk.com/business-integration/ue/github_sample/
- REST (Enterprise): https://docs.metaperson.avatarsdk.com/rest_api/
- TalkingHead (proves the render side): https://github.com/met4citizen/TalkingHead
- Prior research: `docs/avataroptions.md`, `docs/vendors/`
