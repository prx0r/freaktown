# Freak Town peer review — web MVP

## What was good in the original repo

- The product loop was already correctly reduced to performer → minute → audience reaction.
- The existing `comedians.py` character dictionaries are a good low-overhead content source.
- `edge-tts` is a sensible prototype voice layer with caching.
- The original page already had keyboard reactions and a playback-oriented UI.

## Problems blocking useful data

1. Reaction timestamps used server wall-clock time (`time.time()`), not position inside the set.
2. Reactions were stored in one global list rather than scoped to a performance/session.
3. Laugh/clap counters were not reset per set in the browser.
4. There was no explicit set start/completion lifecycle and no canonical JSON record.
5. The word timer advanced independently from `audio.currentTime`, so pause/resume could drift.
6. The avatar was an emoji placeholder rather than the intended 3D character.
7. The synchronous single-thread HTTP server could stall other requests during TTS generation.
8. No persistence or tests existed for the audience-event contract.

## MVP changes

- `freaktown.set.v1` canonical completed-set JSON.
- UUID per performance session.
- Raw event stream with set-relative timestamps.
- Stable `audience_member_id` field now, even for one local viewer.
- Derived counts, rates/minute, first/last reaction, 5-second bins and reaction coverage.
- JSON persisted automatically under `web/data/sessions/` and downloadable in the UI.
- three.ws `<agent-3d>` GLB avatar on a simple stage.
- Playback-clock-driven transcript and reaction timestamping.
- Browser speech fallback if `edge-tts` is unavailable.
- `ThreadingHTTPServer` and session lock for the first step toward multi-viewer use.
- Unit tests plus an HTTP smoke flow.

## Keep the next version modular

Do not add a database, auth, rooms, livestreaming, scoring models, interviews, or multiplayer yet. The next useful modules are independent append-only additions:

- `reaction_type` registry: boo, wow, cringe, etc.
- exact transcript segment/punchline timestamps
- avatar/animation configuration per character
- multiple audience-member ingestion into the same `session_id`
- post-set host/judge feedback as another event stream
- append-only persistence (SQLite/Postgres) only when more than one process needs the data

The core invariant should remain: every observable thing is an event tied to `session_id` + `set_time_seconds`.
