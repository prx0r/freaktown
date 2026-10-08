# docs/ — freaktown docs map

Read in order: `BOUNDARIES.md` → `TRIAL_STAGE1_PLAN.md` → `CHARACTER_PACK.md`
→ then the relevant deep-dive below.

## Architecture and boundaries

| File | What it is |
|---|---|
| BOUNDARIES.md | What lives where: pogtown vs freaktown, old vs new, three rooms, hard rules |
| ARCHITECTURE.md | Live system map: Flask strangler, backend, edge, stage-runtime, contracts |
| AGENT-ONBOARDING.md | Quick-start for coding agents joining the project |

## Avatar and bodies

| File | What it is |
|---|---|
| NORTHSTAR.md | Avatar doctrine: what a freak is, body rules, VRM, face, rig |
| CHARACTER_PACK.md | Character pack schema (how a freak's identity is described) |
| avataroptions.md | Renderer research: three.ws, bitHuman, Atlas, rigging options |
| BLENDER-FACTORY.md | Headless Blender pipeline: inspect, decimate, render, export |
| VOICE-BANK.md | Voice bank structure, voice profiles, qwen render pipeline |

## Vendors and providers

| File | What it is |
|---|---|
| vendors/atlas.md | Atlas API: mesh, rig, endpoints, credit holds, failure log |
| vendors/bithuman.md | bitHuman integration notes (3.ws bodies) |
| vendors/runway.md | Runway integration notes |

## Audio and TTS

| File | What it is |
|---|---|
| HANDOFF_STABLE_AUDIO.md | Stable Audio handoff: walkout music, sting generation |
| JUDGE_VOICES.md | Judge voice design: Ella, panel voices, delivery styles |

## Delivery and hardening

| File | What it is |
|---|---|
| PRELAUNCH-HARDENING.md | Production security and reliability checklist |
| TRIAL_STAGE1_PLAN.md | What's live, what's not, what's next on the trial site |

## Session history

| File | What it is |
|---|---|
| HANDOVER.md | Session close 2026-09-11 (historical, base state) |
| HANDOVER-2026-09-12.md | Latest session: avatar flow, short URLs, revoice, takes, Blender |
| migration/ | Alembic database migrations |
