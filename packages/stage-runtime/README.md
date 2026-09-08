# @freaktown/stage-runtime

Extracted from Killella `apps/web/src/stage/` (see `docs/migration/KILLELLA_IMPORT.md`).
It accepts data/events. It renders. No React, no Green Room, no pages.

## Known coupling debt (tracked, not hidden)

1. `src/StageRuntime.ts:20,384` imports `useShowStore` from
   `../store/showStore` (zustand) for one call: `setCurrentTime()`.
   Fix: constructor-inject a minimal `ClockSink { setCurrentTime(ms) }`.
2. `src/EventConsumer.ts:14,35` binds `private store = useShowStore`
   (reads/writes events/phase). Fix: inject a `RoomStore` interface;
   `EpisodeRoom` and `PartyRoom` each provide one.
3. `src/*` imports `../contracts/show` and `../store/showStore` types
   (`MotionCue`, `WordTiming`, `PerformancePlan`, `ShowEvent`).
   Fix: import from `@freaktown/contracts` once the TS workspace exists
   (§27); canonical JSON Schemas already live in `/contracts/`.

Do NOT add new imports from app code into this package.
The dependency arrow points one way: apps → stage-runtime.
