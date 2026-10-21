# Delivery SDK → stage (characters repo handoff)

**Owner split:** audio + delivery = `prx0r/characters` (delivery SDK).
Face/lip-sync/stage = this repo. This doc is how their output lands here.
Questions → characters `docs/SDK-USAGE.md` + `docs/SPEC-FREAK-SDK.md`.

## What arrives: sealed-set.v1 bundles

Produced on the characters box by `delivery_engine.py --seal DIR`:

| file | who consumes it here |
|---|---|
| `set.wav` | timing authority (FT-03 analogue); AudioBus plays it |
| `timeline.json` | `plan/setAdapter.ts` → PerformancePlan beats + start/end ms |
| `mouth_cues.json` | energy envelope of set.wav → `MouthTrack` when-mouth-moves (deterministic, media clock) |
| `set_plan.json` | character_id, mesh, premise, `delivery.profile` (energy/pace/style), per-beat `performance` |

`loadSealedSet(url)` + `adaptSealedSet` already work — contract test
`packages/stage-runtime/tests/sealedSdkExport.test.ts` (fixture from a real
buddha render) guards the wire; regenerate the fixture whenever the
exporter's contract changes (characters will flag it in their HANDOVER).

## What the beats carry (vocabulary)

- `type`: setup | tag | punchline | closer (opener→setup)
- `performance.expression`: stage face vocabulary only
  (deadpan/smug/smile/annoyed/surprised/frown/disgusted) — the exporter
  maps mechanism + the character's own action face onto it; character wins.
- `performance.gesture`: `hold` = their freeze (`locomotion.freeze`),
  `shrug`/`point`/`wave` from character action triggers
  (`after_punchline`, `on_laugh`, `after_setup`).
- `pause_before_ms` / `pause_after_ms` are **delivery-authoritative**:
  pre-punch hold floor + post-punch resolution window (laugh-scaled).
  setAdapter already keys close-ups and freeze off these.
- `mouth_cues` are envelope-derived (honest label: derived, not
  forced-aligned). If a set later ships real `visemes.json` phonetics,
  MouthTrack prefers those — exporter will switch when we can emit them.

## What we don't produce (theirs)

Camera cues (setAdapter's director), face channels/ARKit (face/), body
gestures beyond the three verbs above, mesh files.

## Meshes

`characters/freaks/mesh-map.json` maps freak slugs → this repo's cast GLB
families (status confident/plausible/todo; todo → appearance fallback).
Their lifecycle/cast families are the source of truth — when new families
land (esp. human/deity), add the family GLB there and the SDK exports
`set_plan.mesh` automatically. Verified: no slug overlap with the 39 cast
specs yet (2026-10-21).

## Requesting a re-render

Bundles are cheap (free tier): characters side runs
`delivery_engine.py <txt> --comedian <slug> --out <name> --seal <dir>`.
Delivery timing/style changes are theirs; if a stage bug looks like
timing, check `timeline.json` first — if the ms are right, it's the stage.
