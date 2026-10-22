# @funnier/stage-runtime

Extracted from Killella `apps/web/src/stage/` (see `docs/migration/KILLELLA_IMPORT.md`).
It accepts data/events. It renders. No React, no Green Room, no pages.
Architecture, run and deploy notes: `docs/LIVE-STAGE.md`; extending it:
`docs/LIVE-STAGE-EXTENDING.md`.

## Layout

| Path | What |
|---|---|
| `src/StageRuntime.ts` | the one renderer: scene, transport clock, avatar, performer, cameras, telemetry, capture |
| `src/StageEventExecutor.ts` | room events → runtime calls (serial queue, replay-safe ACKs) |
| `src/EventConsumer.ts` | inbound event pipe over any `LiveTransport`, feeds an injected `RoomStore` |
| `src/live/` | `LiveTransport` interface, `EpisodeRoomTransport` (DO websocket + POST), `LocalTransport` + `LocalRoom` (BroadcastChannel + localStorage) |
| `src/plan/setAdapter.ts` | `scripts/build_set.py` outputs → `PerformancePlan` (words, cues, camera cues) |
| `src/avatars/` | `AvatarDriver` + `VrmAvatar` / `GlbAvatar` (sniffed) / `BasicAvatar`, `CpuDeformer` |
| `src/performance/` | `MouthTrack` (plan visemes on the media clock), `Performer` (body/face/blink) |
| `src/StageSet.ts`, `src/SfxSynth.ts` | the club room; procedural crowd sounds |
| `src/Transport.ts`, `src/AudioBus.ts`, `src/CameraDirector.ts`, `src/LipSync.ts` | carried over (clock, mix bus, presets, analyser lipsync) |

## Coupling debt — paid (2026-10-22)

1. ~~`StageRuntime` imports `useShowStore`~~ → constructor-injected
   `ClockSink { setCurrentTime(ms) }` (`src/ports.ts`).
2. ~~`EventConsumer` binds `useShowStore`~~ → injected `RoomStore`
   (`applyEvent/setEpisode/setPhase/setCrowd`); apps/live passes
   `showRoomStore`, tests use `createMemoryRoomStore()`.
3. ~~`../contracts/show` + app store types~~ → `@funnier/contracts`
   (`packages/contracts`), the one place; edge re-exports it.

`StageRenderer.ts` (a second, older renderer) was removed: one renderer.

Do NOT add new imports from app code into this package.
The dependency arrow points one way: apps → stage-runtime → contracts.
