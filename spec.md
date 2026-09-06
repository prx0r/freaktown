# KILLELLA — Canonical Backend Specification

The concept is technically very buildable. After reviewing the repo and checking the current APIs, I would **replace most of `backend-spec.md` rather than implement it literally**.

The repo currently has the right *product decomposition* but the wrong *runtime decomposition*. Your existing spec assumes FastAPI centrally controls voice, avatars, OBS, chat, scoring, state, and payments.  In reality, Killella should be a **durable event-driven show engine**, while a browser-based stage renderer does the audiovisual work.

The biggest external correction is three.ws. It really does provide browser-native `<agent-3d>`, avatar speech/lipsync, emotions, gestures, `playClip()`, and related APIs, so it fits this project unusually well. ([GitHub][1]) But your spec says it is Apache-2.0 and instructs you to clone/self-host it; the current upstream `LICENSE` says **proprietary, all rights reserved**. Do not build Killella around redistributing/self-hosting their code until that licensing position is resolved. ([GitHub][2])

Here is the backend architecture I would actually build.

---

## 1. Architectural principle

Killella is not primarily an API application.

It is a **live show runtime**.

The backend's job is to decide:

> **What happens next, when it happens, what data caused it, and whether it already happened.**

The browser stage's job is to execute:

> **What gets rendered, spoken, animated, captioned, and heard.**

Therefore:

```text
                         KILLELLA

 Audience phones
       │
       │ reactions/chat
       ▼
┌─────────────────────────────────────┐
│            FASTAPI API              │
│ auth / admin / audience / entries   │
│ WebSockets / snapshots / commands   │
└─────────────┬─────────────┬─────────┘
              │             │
        ┌─────▼─────┐ ┌────▼─────┐
        │ PostgreSQL│ │   Redis   │
        │ truth     │ │ realtime  │
        └─────▲─────┘ └────▲─────┘
              │             │
              └──────┬──────┘
                     │
              ┌──────▼───────┐
              │  SHOW RUNNER │
              │ deterministic│
              │ state machine│
              └──────┬───────┘
                     │ ordered ShowEvents
                     ▼
              ┌──────────────┐
              │ STAGE CLIENT │
              │ browser/3D   │
              │ three.ws     │
              │ audio        │
              │ captions     │
              │ animation    │
              └──────┬───────┘
                     │
             OBS Browser Source
                     │
                     ▼
                    OBS
                     │ RTMP
                     ▼
               Rumble Studio
```

Separate asynchronous workers generate:

```text
LLM → scripts
LLM → judge outputs
ElevenLabs → audio
compiler → PerformancePlan
                         ↓
                    Cloudflare R2
```

This separation is the key architectural change.

---

## 2. Canonical stack

| Concern        | Technology                                                 |
| -------------- | ---------------------------------------------------------- |
| API            | FastAPI                                                    |
| Validation     | Pydantic v2                                                |
| Database       | PostgreSQL from day one                                    |
| ORM            | SQLAlchemy 2 async                                         |
| Migrations     | Alembic                                                    |
| Realtime       | WebSockets                                                 |
| Realtime bus   | Redis Streams + Pub/Sub                                    |
| Job queue      | ARQ/Dramatiq using Redis                                   |
| Media          | Cloudflare R2                                              |
| LLMs           | provider abstraction for OpenAI/Anthropic/etc.             |
| TTS            | ElevenLabs                                                 |
| 3D             | three.ws hosted/pinned runtime, subject to licensing       |
| Streaming      | OBS Browser Source → Rumble Studio                         |
| OBS automation | obs-websocket 5.x through local bridge                     |
| Analytics      | PostgreSQL initially; ClickHouse only if scale requires it |
| Crypto         | separate optional Solana/Anchor service after MVP          |

Do **not** use SQLite first.

Your Compose setup already provisions PostgreSQL, while `.env.example` still defaults to SQLite.

You need transactions, row locks, unique constraints, JSONB, concurrency control, and a durable event log immediately. There is no meaningful simplification gained from SQLite here.

---

## 3. Runtime services

### A. API service

FastAPI handles:

* audience sessions
* contestant registration
* episode CRUD
* admin/control commands
* score queries
* current-show snapshots
* WebSocket authentication
* signed R2 upload/download URLs

It does **not** execute the show loop.

### B. Show Runner

One active Show Runner owns each live episode.

It is the actual heart of Killella.

```text
Episode
   ↓
acquire episode leadership
   ↓
load persistent state
   ↓
emit ordered event
   ↓
wait for completion/ack/deadline
   ↓
commit transition
   ↓
emit next event
```

Only one runner may control an episode.

Use either:

```text
PostgreSQL advisory lock
```

or a renewable Redis lease backed by database ownership.

Postgres is preferable for the first version.

If the process dies, another runner reconstructs state from the database and resumes.

---

## 4. Two state machines, not one

The current:

```text
REGISTRATION → LOCKED → LIVE → JUDGING → COMPLETED
```

is far too coarse.

Use two levels.

### Episode lifecycle

```text
DRAFT
OPEN
LOCKED
PREPARING
READY
LIVE
COMPLETED
CANCELLED
FAILED
```

### Live show phase

```text
PRE_SHOW
INTRO
LINEUP
CONTESTANT_ENTER
SET_ACTIVE
POST_SET
JUDGING
ROAST
TRANSITION
ELIMINATION
FINALE
WINNER
OUTRO
ENDED
```

The episode lifecycle describes the business object.

The show phase describes what's physically happening on screen.

---

## 5. Event sourcing

Everything that affects the stage becomes a `ShowEvent`.

Example:

```json
{
  "v": 1,
  "event_id": "01K...",
  "episode_id": "ep_...",
  "seq": 184,
  "type": "stage.speak",
  "created_at": "2026-09-06T06:15:21.321Z",
  "effective_at": "2026-09-06T06:15:21.700Z",
  "actor": "ella",
  "payload": {
    "utterance_id": "utt_...",
    "audio_asset_id": "asset_...",
    "text": "That was technically a joke.",
    "emotion": "contempt",
    "gesture": "dismissive_wave"
  }
}
```

Every event has a monotonically increasing `seq`.

The stage stores `last_seq`.

If its WebSocket disconnects:

```text
reconnect
→ send last_seq
→ server sends current snapshot
→ replay seq > last_seq
→ continue
```

Never rely on ephemeral WebSocket messages as truth.

This single feature will eliminate an enormous category of live-show bugs.

---

## 6. Stage protocol

There should be one primary stage socket:

```text
WS /v1/ws/episodes/{episode_id}/stage
```

Not separate connections for stage, score, etc.

Multiplex typed events.

Core event vocabulary:

```text
show.snapshot

stage.avatar.enter
stage.avatar.exit
stage.avatar.look_at
stage.avatar.gesture
stage.avatar.emote
stage.speak
stage.caption
stage.music
stage.sfx

timer.start
timer.pause
timer.finish

score.update
score.reveal

crowd.update

show.phase
show.pause
show.resume
show.end
```

And acknowledgements:

```text
stage.ready
stage.event_started
stage.event_finished
stage.error
```

three.ws already exposes browser lifecycle events and imperative avatar methods such as gesture/clip playback. ([GitHub][3])

Therefore the backend sends:

```text
gesture = "wave"
```

and the stage calls:

```text
avatar.playClip("wave")
```

The backend should never know anything about Three.js render loops.

---

## 7. PerformancePlan

Do not ask an LLM, TTS system and animation system to improvise simultaneously during every contestant set.

Compile each performance beforehand.

```json
{
  "performance_id": "perf_123",
  "duration_ms": 59420,
  "audio_asset": "r2://...",
  "script": "...",
  "segments": [
    {
      "start_ms": 0,
      "end_ms": 8500,
      "text": "...",
      "emotion": "confident"
    }
  ],
  "cues": [
    {
      "at_ms": 1400,
      "type": "gesture",
      "value": "open_hand"
    },
    {
      "at_ms": 6100,
      "type": "gesture",
      "value": "shrug"
    }
  ]
}
```

The Stage Client loads the plan and audio before the contestant walks out.

Then the entire performance is synchronized against one browser clock.

This makes the stream dramatically more reliable.

---

## 8. Audio architecture

The current spec has the backend synthesize PCM and route it through a virtual audio cable into OBS.

Remove that completely.

OBS Browser Source can render ordinary web content including audio. ([OBS Studio][4])

So:

```text
ElevenLabs
    ↓
audio data
    ↓
stage browser
    ↓
Web Audio
    ├── speaker output
    ├── three.ws lipsync analyser
    └── OBS Browser Source audio
```

One clock controls:

* speech
* lipsync
* animation
* captions
* timer
* camera
* sound effects

No virtual cable.

No cross-process audio sync.

---

## 9. Two TTS modes

### Contestant sets

Pre-generate them.

Use ElevenLabs HTTP streaming or normal generation and store the final asset in R2.

### Live Ella/judge reactions

Use ElevenLabs WebSocket TTS.

Current ElevenLabs documentation specifically recommends `eleven_flash_v2_5` for latency-sensitive applications, and its TTS WebSocket accepts incremental text and can return alignment information. ([ElevenLabs][5])

Pipeline:

```text
LLM streaming text
       ↓
sentence chunker
       ↓
ElevenLabs TTS WebSocket
       ↓
audio chunks
       ↓
Stage Client
```

Don't send individual tokens into TTS.

Buffer into natural phrase/sentence boundaries.

three.ws can derive lip movement from the actual audio signal, so you don't need ElevenLabs timings to drive the face; timings remain useful for captions/analytics. ([GitHub][6])

---

## 10. Media storage

R2 should contain:

```text
episodes/{episode}/
  performances/{performance}/
      script.json
      performance-plan.json
      audio.opus
      metadata.json

  judges/{judge_run}/
      response.json
      audio.opus

avatars/
voices/
recordings/
exports/
```

The database stores asset metadata, not blobs.

Use immutable content hashes.

---

## 11. Comedy generation provenance

Every generated item must be reproducible/auditable.

Store:

```text
provider
model
prompt_version
system_prompt_hash
input_hash
temperature
seed where available
response
token_usage
latency_ms
cost_usd
created_at
parent_generation_id
```

This becomes extremely valuable later.

You won't merely have:

> "This joke scored 81."

You'll have:

> "Prompt v17 + persona v8 + model X + absurdist escalation + this delivery profile produced this audience curve."

That is your eventual comedy-learning dataset.

---

## 12. Judge engine

Judges should emit structured results.

```json
{
  "overall": 7.4,
  "dimensions": {
    "originality": 8.1,
    "structure": 6.9,
    "persona": 8.8,
    "delivery": 6.3
  },
  "reasoning_summary": "...",
  "roast": "...",
  "confidence": 0.77
}
```

Store each judge independently.

Do not have one call generate:

```text
score + roast + both judges + voice
```

as the present pseudocode suggests.

Separate:

```text
JudgeEvaluation
       ↓
ShowDecision
       ↓
DialogueGeneration
       ↓
SpeechGeneration
```

That makes each component testable.

---

## 13. Crowd scoring

The current model cannot survive real users.

It scores total clicks rather than audience-normalized response and contains an ordering bug because new events are `LPUSH`ed before elapsed time is calculated as if events were chronological.

Do not initially invent a magical 0–100 comedy score.

Record objective primitives.

Every 500 ms or 1 second:

```text
active_viewers
unique_laughers
laugh_events
laugher_share
claps
boos
```

Then derive:

```text
mean_laugher_share
peak_3s_laugher_share
reaction_coverage
median_reaction_delay
largest_laugh_cluster
silence_duration
```

Example:

```text
25 viewers
10 unique people laugh in second 17
→ laugh_share = 0.40
```

That is meaningful.

"38 button presses" is not.

After you have real episodes, learn/calibrate the conversion from those measurements to a presentation-friendly `crowd_score`.

---

## 14. Audience anti-spam

Create an anonymous signed `audience_session_id`.

Every event carries:

```text
session_id
performance_id
client_seq
client_timestamp
```

Server adds:

```text
server_timestamp
connection_id
```

Rules:

```text
maximum reaction frequency per session
deduplicate client_seq
clamp/reject impossible timestamps
one active audience connection per session where practical
IP/session rate limits
ignore reactions outside SET_ACTIVE
```

Never trust client-provided `intensity`.

If intensity matters, derive it from a defined interaction such as press duration.

---

## 15. Crowd data pipeline

Do not `LRANGE` every historical reaction every time someone clicks.

Instead:

```text
WebSocket
    ↓
Redis Stream
    ↓
CrowdAggregator
    ↓
in-memory 250ms/1s window
    ↓
Redis current counters
    ↓
broadcast live aggregate
    ↓
periodically persist aggregates to Postgres
```

Optional raw event archive:

```text
R2 NDJSON / Parquet
```

This allows thousands of reactions without O(n) score recalculation per click.

---

## 16. PostgreSQL schema

Core tables:

### `episodes`

```text
id
title
status
current_phase
version
registration_opens_at
registration_closes_at
scheduled_at
started_at
ended_at
winner_entry_id
created_at
```

### `contestants`

```text
id
owner_id
name
persona_json
avatar_ref
voice_ref
agent_endpoint
created_at
```

### `entries`

```text
id
episode_id
contestant_id
status
draw_position
created_at
```

### `performances`

```text
id
entry_id
script
script_version
performance_plan_json
audio_asset_id
duration_ms
status
started_at
finished_at
```

### `show_events`

```text
id
episode_id
seq
type
actor
payload_json
effective_at
created_at

UNIQUE(episode_id, seq)
```

### `audience_sessions`

```text
id
episode_id
user_id nullable
connected_at
last_seen_at
```

### `crowd_buckets`

```text
episode_id
performance_id
bucket_start
active_viewers
unique_laughers
laugh_events
claps
boos
```

### `judge_runs`

```text
id
performance_id
judge
provider
model
prompt_version
input_hash
output_json
latency_ms
cost_usd
created_at
```

### `scores`

```text
performance_id
crowd_score
judge_scores_json
final_score
formula_version
```

### `media_assets`

```text
id
kind
storage_key
content_type
bytes
sha256
duration_ms
metadata_json
```

### `generation_runs`

```text
id
kind
provider
model
prompt_version
input_json
output_json
usage_json
cost_usd
parent_id
created_at
```

---

## 17. REST API

Use `/v1`.

### Public

```text
GET  /v1/episodes/live
GET  /v1/episodes/{id}
GET  /v1/episodes/{id}/snapshot
GET  /v1/episodes/{id}/leaderboard

POST /v1/audience/session
```

### Contestants

```text
POST /v1/contestants
GET  /v1/contestants/{id}

POST /v1/episodes/{id}/entries
GET  /v1/entries/{id}
```

### Admin

```text
POST /v1/admin/episodes
POST /v1/admin/episodes/{id}/lock
POST /v1/admin/episodes/{id}/prepare
POST /v1/admin/episodes/{id}/start

POST /v1/admin/episodes/{id}/pause
POST /v1/admin/episodes/{id}/resume
POST /v1/admin/episodes/{id}/skip
POST /v1/admin/episodes/{id}/end
```

All command endpoints require:

```text
Idempotency-Key
```

and return the resulting state version.

---

## 18. WebSockets

Three sockets are enough.

```text
/v1/ws/episodes/{id}/audience
/v1/ws/episodes/{id}/stage
/v1/ws/episodes/{id}/control
```

### Audience

Incoming:

```text
reaction
chat.message
vote
ping
```

Outgoing:

```text
snapshot
phase
timer
crowd.aggregate
score
chat.message
```

### Stage

Outgoing:

```text
all canonical ShowEvents
```

Incoming:

```text
ready
ack
playback.started
playback.finished
error
heartbeat
```

### Control

Used by the admin console and optional OBS bridge.

---

## 19. Rumble

Rumble must be an **adapter**, never a dependency of the core show.

`cocorum` is an unofficial wrapper around Rumble's Live Stream API beta. Its more direct/internal chat functionality is explicitly experimental. ([GitHub][7])

Use:

```python
class ChatSource(Protocol):
    async def messages(self) -> AsyncIterator[ExternalChatMessage]:
        ...
```

Implement:

```text
NativeChatSource
RumbleChatSource
TwitchChatSource
YouTubeChatSource
```

Everything becomes:

```json
{
  "source": "rumble",
  "external_id": "...",
  "display_name": "...",
  "text": "...",
  "created_at": "..."
}
```

Rumble Studio itself can already multistream and provides aggregated chat for the broadcaster, so Killella doesn't need to solve cross-platform chat before the first show. ([Rumble Studio][8])

Native Killella audience interaction should remain canonical.

---

## 20. OBS

For MVP:

```text
OBS manually started
+
one Killella Stage Browser Source
```

That's enough.

For full automation, install a tiny local process on the OBS machine:

```text
killella-obs-bridge
```

It connects outbound to:

```text
wss://api.killella/.../control
```

and locally to:

```text
ws://127.0.0.1:4455
```

OBS WebSocket 5.x uses port 4455 by default and exposes RPC control for scenes, streaming, recording and sources. ([GitHub][9])

Backend:

```text
show.start_stream
```

Bridge:

```text
StartStream
```

No inbound ports on the streaming machine.

---

## 21. three.ws integration

For Killella, use three.ws as a **renderer**, not as the show brain.

Stage owns three avatar instances:

```text
Ella
Chat
Current contestant
```

The stage drives them imperatively.

Example conceptual mapping:

```text
stage.avatar.gesture("ella", "dismissive")
                ↓
ella.playClip("dismissive")
```

```text
stage.avatar.look_at("ella", "contestant")
                ↓
avatar.lookAt(...)
```

```text
stage.speak(...)
                ↓
Web Audio playback
                ↓
avatar lipsync analyser
```

three.ws documentation confirms its browser-based runtime exposes avatar manipulation and speech/lipsync hooks. ([GitHub][10])

**Production warning:** pin an exact three.ws bundle rather than using `latest`; its own security docs recommend version pinning/SRI. ([GitHub][11])

And resolve the upstream license before depending on self-hosting or redistribution. The current LICENSE is proprietary. ([GitHub][2])

---

## 22. Crypto boundary

Do not make Solana a dependency of getting Episode 1 online.

Define:

```python
class PrizeProvider:
    create_pool(...)
    enter(...)
    refund(...)
    finalize(...)
    claim(...)
```

Start with:

```text
NoopPrizeProvider
```

Then:

```text
SolanaPrizeProvider
```

Anchor currently supports token accounts/ATAs, `token_interface`, PDA-controlled token accounts and PDA-signed token transfers, which are the correct building blocks for a USDC escrow implementation. ([Anchor Lang][12])

USDC's Solana mint remains:

```text
EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

as documented by Anchor. ([Anchor Lang][13])

Keep wagering/self-staking mechanics outside the initial backend. First prove that people actually watch and laugh.

---

## 23. Repository structure

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── episodes.py
│   │   ├── contestants.py
│   │   ├── audience.py
│   │   └── admin.py
│   │
│   ├── realtime/
│   │   ├── audience.py
│   │   ├── stage.py
│   │   ├── control.py
│   │   └── protocol.py
│   │
│   ├── domain/
│   │   ├── episode.py
│   │   ├── show.py
│   │   ├── performance.py
│   │   ├── scoring.py
│   │   └── events.py
│   │
│   ├── services/
│   │   ├── show_runner.py
│   │   ├── crowd_aggregator.py
│   │   ├── performance_compiler.py
│   │   ├── judge_engine.py
│   │   └── media_service.py
│   │
│   ├── adapters/
│   │   ├── llm/
│   │   ├── tts/
│   │   ├── rumble/
│   │   ├── storage/
│   │   └── prizes/
│   │
│   ├── workers/
│   │   ├── material.py
│   │   ├── tts.py
│   │   └── judging.py
│   │
│   └── db/
│       ├── models.py
│       ├── session.py
│       └── migrations/
│
stage/
├── src/
│   ├── runtime.ts
│   ├── protocol.ts
│   ├── avatars.ts
│   ├── audio.ts
│   ├── timeline.ts
│   ├── captions.ts
│   └── reconnect.ts
│
audience/
│
obs-bridge/
│
contracts/          # later
│
tests/
├── unit/
├── integration/
├── protocol/
└── replay/
```

---

## 24. Replayability requirement

Every completed episode should be replayable without an LLM, ElevenLabs or Rumble connection.

Given:

```text
database snapshot
+
ShowEvent log
+
R2 assets
```

you should be able to run:

```bash
killella replay ep_123
```

and see essentially the same episode.

This gives you:

* deterministic tests
* debugging
* highlight generation
* offline scoring experiments
* model comparisons
* training data
* automated regression testing

It is one of the highest-leverage properties Killella can have.

---

## 25. First vertical slice

Do **not** begin by implementing contestant registration, crypto, cross-platform chat or seasons.

Build exactly this:

```text
1 Ella avatar
1 contestant avatar
1 generated 60-second set
1 prerecorded ElevenLabs audio asset
1 PerformancePlan
1 browser stage
1 FastAPI Show Runner
1 stage WebSocket
1 laugh button
1 crowd aggregator
1 Ella judge call
1 live Ella TTS response
1 OBS Browser Source
```

Flow:

```text
POST /episode
      ↓
prepare contestant
      ↓
compile PerformancePlan
      ↓
stage connects
      ↓
START
      ↓
contestant enters
      ↓
audio + lipsync + gestures
      ↓
audience laughs
      ↓
set ends
      ↓
crowd metrics frozen
      ↓
Ella evaluation
      ↓
Ella roast generated
      ↓
ElevenLabs streaming
      ↓
Ella speaks
      ↓
score displayed
      ↓
episode ends
```

Once that complete path works, adding 10 contestants is mostly orchestration.

---

## 26. Immediate repository fixes

Before implementing features:

```text
1. Change project Python requirement to >=3.12.
2. Delete SQLite from the design.
3. Add async PostgreSQL + Alembic.
4. Replace wildcard CORS.
5. Replace ws:// frontend construction with ws:/wss: awareness.
6. Add authenticated audience/stage WebSocket sessions.
7. Implement ShowEvent schema + show_events table.
8. Implement durable Show Runner.
9. Implement stage reconnect/snapshot/replay.
10. Implement Redis crowd ingestion.
11. Replace current crowd-score algorithm.
12. Add R2 media abstraction.
13. Build PerformancePlan compiler.
14. Build stage client.
15. Integrate ElevenLabs.
16. Only then add Rumble.
17. Keep Solana behind a provider interface.
```

The current frontend opens `ws://${location.host}/ws/crowd/test`, despite that endpoint not existing in the current FastAPI application; it will also be wrong under an HTTPS deployment because it needs `wss://`.

The present FastAPI app exposes only `/` and `/health`, confirming that essentially all of the implementation remains available to structure correctly rather than migrate later.

The key simplification is this:

**Killella backend = conductor. Stage browser = orchestra. OBS = camera.**

And I would explicitly **not add LiveKit yet**. LiveKit is excellent when you need WebRTC audio/video participants or genuinely live conversational agents; its current architecture is designed around that. ([LiveKit Docs][14]) Killella's first version is predominantly one-way generated media plus tiny audience reaction events, so WebSockets + browser audio are much simpler.

The other major unlock is the `PerformancePlan`. Once every comedian becomes a reusable, timed artifact containing script + voice + cues + metadata, you can generate episodes ahead of time, rerun them, A/B models, swap judges, automatically make clips, and eventually train on the exact relationship between **generation configuration → delivery → audience laughter curve**. That is substantially more valuable than the current "FastAPI calls LLM then sends some audio to OBS" design.

---

## References

[1]: https://github.com/nirholas/three.ws/blob/main/docs/introduction.md
[2]: https://github.com/nirholas/three.ws/blob/main/LICENSE
[3]: https://github.com/nirholas/three.ws/blob/main/specs/EMBED_SPEC.md
[4]: https://obsproject.com/kb/browser-source
[5]: https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input
[6]: https://github.com/nirholas/three.ws/blob/main/docs/tutorials/voice-and-lipsync.md
[7]: https://github.com/thelabcat/cocorum
[8]: https://studio.rumble.com/
[9]: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
[10]: https://github.com/nirholas/three.ws/blob/main/docs/tutorials/character-library-to-embed.md
[11]: https://github.com/nirholas/three.ws/blob/main/docs/security.md
[12]: https://www.anchor-lang.com/docs/tokens/basics/create-token-account
[13]: https://www.anchor-lang.com/docs/tokens/basics/create-mint
[14]: https://docs.livekit.io/agents/
