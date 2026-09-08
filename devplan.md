# Freak Town Monorepo Consolidation

## Mission

Consolidate:

* `prx0r/freaktown`
* `prx0r/killella`

into **one canonical repository: `prx0r/freaktown`**.

Freak Town remains the product, brand, creator experience and schema authority.

Killella is treated as a donor of production infrastructure:

* FastAPI backend
* PostgreSQL persistence
* R2 media storage
* Cloudflare Worker
* Durable Object `EpisodeRoom`
* live event architecture
* StageRuntime
* Transport
* AudioBus
* LipSyncAdapter
* CameraDirector
* control/live audience surfaces
* Ella realtime infrastructure
* judge infrastructure
* production tests

Do NOT move Freak Town into Killella.

Do NOT leave two applications that can independently create/rehearse Freaks.

Do NOT create a nested `killella/` application inside Freak Town.

The desired architecture is:

```text
FREAK TOWN
│
├── CREATE
├── REHEARSE
├── WATCH / SHARE / RESPOND
├── PARTY
├── CHARACTER CAREERS
│
└── SUBMIT
        │
        ▼
PRODUCTION INFRASTRUCTURE
├── Postgres
├── R2
├── FastAPI
├── Cloudflare Worker
├── EpisodeRoom
├── Ella
├── Judges
└── StageRuntime
        │
        ▼
LIVE FREAK TOWN
```

---

# 0. Exact source snapshots

Migration must be based on these heads:

```text
FREAKTOWN_SOURCE
e8a6eabfd2718bf6462d10e7b89aa66d795cd68a

KILLELLA_SOURCE
863cdd37f73436f7ee5118b82340731eb868bf09
```

Tag both before changing anything.

In Freak Town:

```bash
git checkout main
git pull
git tag pre-killella-merge-e8a6eab
git push origin pre-killella-merge-e8a6eab
```

In Killella:

```bash
git checkout main
git pull
git tag frozen-before-freaktown-merge-863cdd3
git push origin frozen-before-freaktown-merge-863cdd3
```

Create migration branch in Freak Town:

```bash
git checkout -b merge/killella-infra
```

No work directly on `main`.

---

# 1. Preserve Killella history without polluting the tree

Add Killella as a Git remote:

```bash
git remote add killella https://github.com/prx0r/killella.git
git fetch killella
```

Record Killella's repository history as ancestry without importing its entire filesystem:

```bash
git merge \
  --allow-unrelated-histories \
  -s ours \
  killella/main \
  -m "chore: attach killella history as Freak Town infrastructure ancestry"
```

This creates a merge commit with:

```text
parent 1 = Freak Town
parent 2 = Killella
```

while preserving Freak Town's current tree.

Do NOT perform a normal unrelated-history merge.

Do NOT dump the whole Killella repository into the root.

For copying source, create a temporary worktree:

```bash
git worktree add ../killella-source killella/main
```

Use that tree only as the migration source.

At the end:

```bash
git worktree remove ../killella-source
```

---

# 2. Product ownership rule

This rule is absolute:

```text
Freak Town owns product behavior.
Infrastructure must conform to Freak Town.
```

Product surfaces owned by Freak Town:

```text
Studio
Create a Freak
portrait iteration
script generation
delivery editing
rehearsal
saved Freaks
watch page
sharing
reply/respond loop
canonical character URLs
lineage
party mode
mobile shell
character lore
Ella personality/content
```

Killella may never introduce another implementation of these.

Specifically DO NOT port:

```text
apps/web/src/green-room/
backend/routes/green_room.py
backend/services/green_room_compiler.py
```

Delete/ignore any Killella routes that attempt to make `/`, `/studio`, or `/green-room` the creator application.

There must be one Studio.

It is Freak Town Studio.

---

# 3. Target repository layout

Do not achieve this in one huge file move.

This is the target shape:

```text
freaktown/
│
├── app.py                         # temporary legacy Flask product shell
├── party.py                       # temporary party implementation
├── black_room.py
│
├── apps/
│   ├── live/
│   │   ├── src/
│   │   │   ├── control/
│   │   │   ├── live/
│   │   │   └── stage/
│   │   └── ...
│   │
│   └── ios/
│       └── ... Capacitor shell ...
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   ├── models/
│   ├── routes/
│   └── services/
│       ├── audio/
│       ├── avatars/
│       ├── delivery/
│       ├── ella/
│       ├── judge/
│       ├── clips/
│       ├── media/
│       ├── performances/
│       ├── tts/
│       └── events/
│
├── edge/
│   └── worker/
│       ├── index.ts
│       ├── episode-room.ts
│       ├── ella/
│       ├── auth/
│       └── api/
│
├── packages/
│   └── stage-runtime/
│       ├── StageRuntime.ts
│       ├── Transport.ts
│       ├── AudioBus.ts
│       ├── LipSync.ts
│       ├── CameraDirector.ts
│       └── EventConsumer.ts
│
├── contracts/
│   ├── delivery.v1.schema.json
│   ├── avatar.v1.schema.json
│   ├── character.v1.schema.json
│   ├── performance.v1.schema.json
│   ├── events.v1.schema.json
│   ├── lineage.v1.schema.json
│   └── fixtures/
│       └── golden-freak-v1/
│
├── alembic/
├── alembic.ini
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
│
├── scripts/
├── docs/
├── static/
└── freaks/                        # local development only
```

Eventually `app.py` should disappear.

Do NOT make removing it part of this first migration.

Use a strangler migration.

---

# 4. Import Killella backend first

Copy:

```text
killella/backend/
→
freaktown/backend/
```

but immediately remove creator-product duplication before the first commit.

Do NOT port active implementations of:

```text
backend/routes/green_room.py
backend/services/green_room_compiler.py
```

Review `dressing_room` carefully.

If it means creator-side character editing already covered by Freak Town:

```text
DROP
```

If it contains reusable pure capability/runtime logic:

```text
extract reusable pieces into backend/services/avatars/
```

Do not expose another Dressing Room UI/API.

---

# 5. Backend services: keep/drop matrix

## KEEP

From Killella:

```text
backend/db/
backend/models/

backend/services/audio/
backend/services/bodies.py
backend/services/clips/
backend/services/delivery/
backend/services/direction_parser.py
backend/services/ella/
backend/services/events.py
backend/services/freaktown/
backend/services/judge/
backend/services/media_store.py
backend/services/motions/
backend/services/tts/

backend/routes/audience.py
backend/routes/episodes.py
backend/routes/admin.py
backend/routes/intake.py
backend/routes/judge.py
backend/routes/shows.py
```

Also inspect and retain useful pieces of:

```text
launchpad
callbacks
chat_summary
sound
```

provided they are generic infrastructure rather than competing product APIs.

## DO NOT PORT INTO ACTIVE RUNTIME

For now:

```text
potchain
x402 UI
payments
crypto contracts
```

They are outside MVP.

Leave them available in the frozen Killella repository.

Do not drag them into Freak Town's dependency graph.

Likewise do not port miscellaneous experimental files simply because they exist.

---

# 6. Rename Killella concepts during import

There must be no live application concept named Killella after this migration.

Allowed:

```text
docs/migration/KILLELLA_IMPORT.md
git history
old commit messages
```

Not allowed:

```text
KillellaService
KILLELLA_API
killella_backend
"Killella" UI labels
```

Everything becomes Freak Town infrastructure.

---

# 7. Do NOT immediately rename every database table

Killella currently has useful mature database entities.

Do not combine:

```text
repo merge
+
database conceptual rename
+
frontend rewrite
```

in one migration.

Keep existing SQL table names initially where required for stability.

At Python/domain level introduce Freak Town vocabulary:

```text
Creator
Character
CharacterVersion
Performance
Episode
Appearance
ShowEvent
AudienceSession
JudgeRun
MediaAsset
```

Where legacy DB models are named:

```text
Comedian
ActVersion
Submission
```

use compatibility adapters temporarily.

Example:

```python
CharacterRecord = Comedian
PerformanceVersionRecord = ActVersion
```

Document this debt.

Do an Alembic domain rename only after migration parity is green.

---

# 8. Canonical contracts MUST move first

This is critical because previous regressions came from schema drift.

There is exactly one schema authority:

```text
/freaktown/contracts/
```

Nothing in:

```text
backend/
edge/
apps/live/
Studio
```

gets to define its own variation.

Canonical contracts:

```text
freaktown.character.v1
freaktown.avatar.v1
freaktown.delivery.v1
freaktown.performance.v1
freaktown.events.v1
freaktown.lineage.v1
```

Start by moving the existing Freak Town schemas into `contracts/`.

Fix `delivery.v1` before proceeding.

Canonical beat shape:

```json
{
  "id": "b2",
  "type": "punchline",
  "text": "Unfortunately my therapist is a printer.",
  "delivery": {
    "pace": 0.91,
    "energy": 0.7,
    "emphasis": 0.8,
    "expression": "deadpan"
  },
  "pause_before_ms": 0,
  "pause_after_ms": 950,
  "stage": "hold",
  "gesture": "still",
  "camera": "close",
  "sound": "none"
}
```

No parallel:

```text
speech{}
performance{}
```

representation under the same schema version.

If a new representation is ever needed:

```text
freaktown.delivery.v2
```

not silent mutation of v1.

---

# 9. Golden Freak contract fixture

Create immediately:

```text
contracts/fixtures/golden-freak-v1/
```

Contents:

```text
character.json
avatar.json
delivery.json
performance.json
offsets.json
set.wav
```

Make values deliberately non-default:

```text
pace        0.85
energy      0.71
emphasis    0.82
expression  annoyed
gesture     lean
camera      close
pause       937ms
```

Both Python and TypeScript must load the exact same files.

Tests must assert that every field survives:

```text
Freak Town Studio
→ save
→ contract fixture
→ backend intake
→ PerformanceManifest
→ StageRuntime
```

without mutation.

This fixture is the treaty between every subsystem.

---

# 10. Contract tooling

Use JSON Schema as language-neutral authority.

Python:

```text
jsonschema
Pydantic at HTTP boundaries
```

TypeScript:

```text
generated TS interfaces
or schema validation via Ajv
```

Do not manually maintain three structurally independent versions of every schema.

Add:

```bash
make contracts
```

or equivalent script.

CI must fail if generated contract bindings differ from checked-in output.

---

# 11. Import FastAPI as backend-of-record

Killella already has a proper FastAPI application.

Port it as:

```text
backend/main.py
```

Do NOT let it serve another competing frontend at `/`.

Remove Killella's:

```text
React SPA root ownership
SPA catch-all ownership
Green Room route ownership
```

FastAPI's responsibility becomes:

```text
/api/*
backend data
generation
persistence
intake
media metadata
judge APIs
show management
health
```

Product HTML remains Freak Town-owned during migration.

Target routes:

```text
/api/v1/characters/*
/api/v1/performances/*
/api/v1/episodes/*
/api/v1/judges/*
/api/v1/media/*
/api/v1/intake/*
```

Existing `/v1/*` routes may remain temporarily.

Do not rename every endpoint during migration.

Add compatibility redirects/aliases where necessary.

---

# 12. Strangler architecture during migration

For at least one migration phase run:

```text
freak.town
│
├── /                       existing Freak Town product
├── /studio                 existing Studio
├── /f/*                    share/watch/respond
├── /@*                     character/performance URLs
├── /party/*                party mode
│
├── /api/*                  FastAPI
│
├── /live/*                 production live app
├── /control/*              operator UI
│
└── /live-room/*            Cloudflare Worker / EpisodeRoom
```

Do not rewrite the successful viral flow just to make frameworks uniform.

Framework uniformity is not the goal.

Correct product behavior is.

---

# 13. Storage authority

Canonical durable state:

```text
Postgres = structured durable truth
R2       = immutable/media assets
DO       = active room/show realtime state
```

Specifically:

## PostgreSQL

Store:

```text
creator
character
character version
performance
lineage
episode
appearance
submission state
judge runs
Golden Tickets
reputation/career metadata
media metadata
```

## R2

Store:

```text
portrait.webp
avatar.glb / avatar.vrm
voice_reference.wav
set.wav
walkout.wav/mp3
performance manifests
clips
recordings
share cards
training exports
```

## Durable Object

Store active live state:

```text
sequence
phase
active performance
audience sessions
reactions
score locks
camera state
Ella reflex state
live event replay buffer
```

Durable Object is NOT the long-term database.

---

# 14. Filesystem Freak bundles remain useful

Do not delete:

```text
freaks/<slug>/
```

The bundle is an excellent portable artifact.

But change its role.

Local development:

```text
filesystem bundle = canonical local adapter
```

Production:

```text
Postgres metadata
+
R2 immutable bundle assets
```

Create an interface:

```python
class PerformanceRepository(Protocol):
    async def save(...)
    async def get(...)
    async def list(...)

class LocalPerformanceRepository(...)
class PostgresPerformanceRepository(...)
```

And:

```python
class MediaStore(Protocol):
    async def put(...)
    async def get(...)

class LocalMediaStore(...)
class R2MediaStore(...)
```

Product code must not directly know whether storage is local or R2.

---

# 15. Migrate current JSONL state later, not immediately

Current Freak Town has useful simple data:

```text
funnel.jsonl
reactions.jsonl
votes.jsonl
party_records.json
party_rooms.json
```

Do not delete them during the merge.

Introduce repository/event interfaces around them first.

Then migrate individually to Postgres/DO.

Preserve import scripts:

```text
scripts/import_funnel_jsonl.py
scripts/import_reactions_jsonl.py
scripts/import_party_records.py
```

Migration should be replayable and idempotent.

---

# 16. Party mode stays Freak Town-owned

Current Party mode already has a useful server-authoritative invariant:

```text
CONTROLLER
→ SERVER COMMAND
→ ROOM
→ PERSIST
→ BROADCAST
→ STAGE
```

Do not rewrite it into EpisodeRoom during this merge.

Later create a shared interface:

```text
RealtimeRoom
├── EpisodeRoom
└── PartyRoom
```

They have different semantics.

EpisodeRoom:

```text
live broadcast show
large audience
strict media clock
reactions
judges
```

PartyRoom:

```text
small invited group
private role state
turn-based games
secret information
```

Do not force one Durable Object class to become both immediately.

---

# 17. Port Cloudflare Worker

Move:

```text
killella/apps/web/worker/
```

to:

```text
freaktown/edge/worker/
```

Keep:

```text
episode-room.ts
episode-room.test.ts
index.ts
auth/
api/
ella/
```

Review `db/` before porting.

D1 must NOT become a second business database.

Rule:

```text
Postgres = business truth.
D1 = edge-local cache/ephemeral only, if retained at all.
```

Keep the R2 binding.

Keep Queues only where there are actual consumers.

Remove unused infrastructure bindings rather than preserving placeholders.

---

# 18. EpisodeRoom remains live authority

Keep its core invariant:

```text
receive command
→ validate
→ persist event
→ mutate room state
→ broadcast
```

Never:

```text
broadcast
→ persist later
```

Canonical live event key:

```text
episode_id
performance_id
seq
effective_at
created_at
type
payload
```

Reconnect protocol:

```text
client last_seq
→ room snapshot
→ replay events > last_seq
→ live stream
```

Every live consumer uses that.

---

# 19. Port StageRuntime as a PACKAGE, not a page

This is one of the most important changes.

Do NOT copy:

```text
apps/web/src/stage/
```

into another app-specific folder.

Extract it to:

```text
packages/stage-runtime/
```

Move:

```text
StageRuntime.ts
Transport.ts
AudioBus.ts
LipSync.ts
CameraDirector.ts
EventConsumer.ts
```

plus their tests.

StageRuntime must have NO dependency on:

```text
React
Green Room
ControlPage
LivePage
Freak Town Studio UI
```

It accepts data/events.

It renders.

That's all.

---

# 20. StageRuntime API

Target interface:

```ts
const runtime = new StageRuntime({
  container,
  mode: "rehearsal" | "watch" | "live",
});

await runtime.preload({
  avatar,
  audio,
  performance,
  wordTimings,
  walkout,
});

runtime.play();
runtime.pause();
runtime.resume();
runtime.seek(ms);
runtime.cutCamera("close");
runtime.dispose();
```

---

# 21. Fix StageRuntime's avatar assumption during import

Current Killella `preload()` requires an avatar URL before loading audio.

This caused the Killella rehearsal bug.

Fix it before Freak Town consumes the package.

Avatar is OPTIONAL.

Audio is the actual READY gate.

Target:

```ts
await runtime.preload({
    avatar: avatarSpecOrNull,
    portrait: portraitUrlOrNull,
    audio,
    performance
})
```

Loading:

```text
audio required
performance required

avatar optional
portrait optional
```

State:

```text
EMPTY
→ LOADING
→ READY
```

must succeed with:

```text
audio + portrait
```

even if 3D generation is pending.

The stage must degrade:

```text
rigged GLB
→ VRM
→ static portrait
→ generic silhouette
```

Never black screen.

---

# 22. Universal avatar runtime

Do not make VRM the only possible format anymore.

Support:

```text
VRM
rigged GLB
portrait
```

Canonical:

```json
{
  "version": "freaktown.avatar.v1",
  "format": "glb",
  "asset": "avatar.glb",
  "capabilities": {
    "humanoid": true,
    "skeleton": true,
    "visemes": ["jawOpen"],
    "blink": true,
    "expressions": ["happy", "angry"]
  }
}
```

or:

```json
{
  "version": "freaktown.avatar.v1",
  "format": "vrm",
  "asset": "avatar.vrm",
  "capabilities": {
    "humanoid": true,
    "visemes": ["aa", "ih", "ou", "ee", "oh"]
  }
}
```

Runtime adapters:

```text
AvatarRuntime
├── VrmAvatarAdapter
├── GlbAvatarAdapter
└── PortraitAvatarAdapter
```

---

# 23. One LipSyncAdapter

There is one lipsync subsystem for everything.

Input:

```text
WebAudio AnalyserNode
```

Outputs depending on capabilities:

```text
VRM visemes
ARKit morphs
jawOpen
body-only fallback
```

Audio source may be:

```text
set.wav
TTS
microphone
Ella realtime audio
LiveKit/WebRTC
Telnyx PCM
```

Mouth code does not care who generated the voice.

Invariant:

> Every mouth listens to the audio that is actually audible.

---

# 24. One AudioBus

Retain Killella's bus architecture:

```text
MASTER
├── VOICE
├── MUSIC
├── SFX
└── CROWD
```

Only ONE `AudioContext` per StageRuntime.

Only ONE `MediaElementSourceNode` per HTML media element/context.

Lipsync taps VOICE.

No page creates a second analyser/audio graph.

---

# 25. Use StageRuntime in three places

After extraction, migrate consumers in this order:

## First

Freak Town rehearsal.

```text
Studio
→ local PerformanceManifest
→ StageRuntime
```

No network/EventRoom required.

## Second

Shared `/f/*` pages.

```text
published PerformanceManifest
→ StageRuntime
```

Same rendering.

## Third

Live show.

```text
EpisodeRoom events
→ EventConsumer
→ StageRuntime
```

The renderer must not know which mode generated the event.

---

# 26. Import live/control app, not Killella product app

Create:

```text
apps/live/
```

Port only:

```text
control/
live audience page
stage page
store/
event executor
useful contracts adapters
```

Do NOT port:

```text
green-room/
creator shelf
creator editor
```

Routes:

```text
/live/:episodeId
/control/:episodeId
/stage/:episodeId
```

These belong to production.

---

# 27. Remove duplicate contract definitions from apps/live

Killella currently has browser/Worker contract definitions.

Change imports to:

```text
@freaktown/contracts
```

or generated output under root `contracts/`.

There must not be:

```text
apps/live/src/contracts/schemaA
edge/worker/contracts/schemaB
backend/contracts.py schemaC
```

with manually divergent definitions.

---

# 28. Intake remains a boundary even in one repo

Do NOT eliminate intake just because the repositories merged.

This interface is valuable.

Conceptually:

```text
Studio
    ↓
seal PerformanceBundle
    ↓
Intake
    ↓
validate
    ↓
persist
    ↓
queue for show
```

That means later:

```text
web Studio
iPhone
VR creator
external agent
CLI
```

can all submit the same artifact.

Keep an HTTP boundary:

```text
POST /api/v1/intake/bundle
```

or retain existing `/v1/intake/bundle` initially.

---

# 29. Intake rule

Intake never modifies creative content.

It may:

```text
validate
hash
store
index
assign IDs
reject
```

It may NOT:

```text
rewrite jokes
change pauses
change voice
change gestures
re-generate audio
replace avatar
```

The creator rehearsed a sealed performance.

Live performs exactly that artifact.

---

# 30. Performance immutability

Once marked:

```text
READY
```

produce:

```text
performance_id
sha256
manifest
```

Any edit creates:

```text
new performance version
```

Never mutate the sealed one.

This enables:

```text
reproducible live shows
replay
viral clips
ML evaluation
A/B comparison
auditing
```

---

# 31. Viral lineage comes from Freak Town

Current Freak Town now owns:

```text
relation
parent
root
depth
canonical character URLs
respond
send back
```

Do not replace that with Killella's older launchpad ideas.

Normalize it into:

```json
{
  "version": "freaktown.lineage.v1",
  "relation": "reply",
  "parent_performance_id": "perf_x",
  "root_performance_id": "perf_a",
  "depth": 3
}
```

Persist in Postgres during publication.

---

# 32. Ella separation

Port Killella's Ella architecture.

Keep these independent concepts:

```text
EllaSense
EllaReflex
EllaLive
EllaJudge
EllaDialogue
```

Do not replace Freak Town's:

```text
ella_bible.md
ella_scoring_rubric.md
Ella personality/content
```

with Killella prompts.

Freak Town owns Ella's character.

Infrastructure owns execution.

```text
Freak Town Ella definition
          ↓
Killella-derived Ella runtime
          ↓
EpisodeRoom
```

---

# 33. Keep EllaJudge isolated

Canonical scoring must never be contaminated by realtime banter.

```text
EllaJudge
     |
     | independent/frozen input
     ↓
score + verdict
```

Separate:

```text
EllaLive
→ jokes
→ interruption
→ hosting
```

No feedback loop from live dialogue into canonical score unless explicitly versioned as an experiment.

---

# 34. Remove Redis as show authority

If Killella code still assumes Redis for live show state:

```text
remove that responsibility.
```

Use:

```text
EpisodeRoom = live authority
Postgres    = durable structured truth
R2          = media
```

Redis may remain only for genuine caching/jobs if required.

Do not make correctness depend on it.

---

# 35. Dependency cleanup

Freak Town's current `requirements.txt` is no longer honest enough.

Replace dependency management with one real manifest.

Create:

```text
pyproject.toml
```

Core dependencies should include at least:

```text
fastapi
uvicorn
flask                   # temporary migration period
pydantic
pydantic-settings
sqlalchemy[asyncio]
asyncpg
alembic
httpx
edge-tts
openai
anthropic               # only if genuinely used
boto3
jsonschema
python-dotenv
python-multipart
```

Do NOT automatically import:

```text
x402
crypto packages
redis
```

unless code retained in the consolidated runtime actually requires them.

Add dev dependencies:

```text
pytest
pytest-asyncio
ruff
mypy
```

Use one lock strategy.

---

# 36. Node workspace

Create root:

```json
{
  "private": true,
  "workspaces": [
    "apps/live",
    "packages/*",
    "edge/worker"
  ]
}
```

Do not maintain unrelated duplicate copies of:

```text
three
@pixiv/three-vrm
zod
typescript
vitest
```

Pin compatible shared versions.

---

# 37. Do not rewrite Freak Town Studio to React yet

This is specifically forbidden in the consolidation PR.

Current Studio/watch/respond/party behavior is valuable and rapidly evolving.

First make infrastructure reusable.

Then migrate UI framework if there is an actual product reason.

A rewrite during a repo merge creates too many variables.

---

# 38. Break up `app.py` gradually

Current `app.py` is far too large.

But use extraction commits, not one rewrite.

Suggested sequence:

```text
app.py
│
├── routes/studio.py
├── routes/watch.py
├── routes/share.py
├── routes/respond.py
├── services/generation.py
├── services/portraits.py
├── services/walkouts.py
├── services/delivery.py
└── repositories/local.py
```

Do one subsystem per commit.

Behavior must be identical before/after extraction.

---

# 39. Party extraction later

Likewise:

```text
party.py
```

can eventually become:

```text
party/
├── room.py
├── persistence.py
├── modes/
│   ├── freaktionary.py
│   └── roast_relay.py
└── routes.py
```

Do not mix this refactor with the first infrastructure port.

---

# 40. Cloudflare configuration

Port Killella's Wrangler configuration but rename layout paths.

Target bindings:

```text
EPISODE_ROOM
R2
TTS_QUEUE        only if consumed
AI_QUEUE         only if consumed
KV               only if required
```

D1:

```text
remove if unused
```

or explicitly document:

```text
D1 MAY NOT store canonical:
characters
performances
episodes
scores
users
```

Postgres is canonical.

---

# 41. R2 bucket

Standardize one bucket name across everything.

Choose:

```text
freak-town
```

or:

```text
freak-town-assets
```

Pick ONE.

Search repository for every occurrence.

CI test:

```python
assert python_default_bucket == wrangler_bucket
```

Never allow the two-bucket regression again.

---

# 42. Asset layout in R2

Use deterministic keys:

```text
characters/<character_id>/<version>/portrait.webp
characters/<character_id>/<version>/avatar.glb
characters/<character_id>/<version>/avatar.json

performances/<performance_id>/delivery.json
performances/<performance_id>/set.wav
performances/<performance_id>/walkout.wav
performances/<performance_id>/manifest.json

clips/<performance_id>/<clip_id>.mp4

episodes/<episode_id>/events.jsonl
episodes/<episode_id>/manifest.json
```

Content hash assets where useful.

---

# 43. three.ws generation belongs to Freak Town creation infrastructure

Implement provider:

```text
backend/services/avatars/threews.py
```

Interface:

```python
class AvatarProvider:
    async def generate(...)
    async def check(...)
```

three.ws is one provider.

Studio does not know MCP details.

Flow:

```text
portrait
→ ThreeWsProvider
→ pending/ready
→ validate GLB
→ inspect skeleton/morphs
→ copy R2
→ avatar.json
```

Never make live stage fetch canonical assets from three.ws indefinitely.

---

# 44. Deployment topology after consolidation

```text
                    CLOUDFLARE
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
    edge Worker       static/CDN          R2
        │
    EpisodeRoom
        │
        │
        ▼
     FastAPI
        │
      Postgres
```

Product routes may remain on existing VPS/Flask temporarily.

Eventually:

```text
freak.town
```

is one coherent origin from the user's perspective.

Internal service boundaries remain invisible.

---

# 45. Development commands

Target root commands:

```bash
make dev
make test
make test-contracts
make test-python
make test-web
make test-worker
make test-e2e
make build
```

`make dev` should start:

```text
Flask legacy Studio temporarily
FastAPI
apps/live Vite
Wrangler local Worker
```

using known ports and clear output.

Eventually Flask disappears from this command.

---

# 46. Required CI pipeline

Every PR must run:

```bash
python -m pytest -q

cd apps/live
npm ci
npm run typecheck
npm run test
npm run build

cd ../../edge/worker
npm run typecheck
npm run test
wrangler deploy --dry-run

# contract/golden test
python scripts/validate_contracts.py

# end-to-end
npx playwright test
```

Also add:

```text
ruff check
```

and dependency sanity.

---

# 47. Migration tests before touching production

### Test A — current Studio

```text
CREATE A FREAK
→ portrait
→ minute
→ audio
→ avatar
→ rehearse
→ edit delivery
→ rehearse again
```

### Test B — viral loop

```text
publish
→ /f/<id>
→ watch
→ captions
→ react
→ YOUR TURN
→ respond
→ generated reply plays
→ send back
→ lineage correct
```

### Test C — party

```text
create room
→ join phones
→ seat tokens
→ start Freaktionary
→ hidden state not leaked
→ vote
→ results
→ restart process
→ persistent record survives
```

### Test D — intake

```text
Studio seals Golden Freak
→ intake
→ validates exact contract
→ Postgres
→ R2
→ manifest hash stable
```

### Test E — live

```text
create episode
→ queue Golden Freak
→ EpisodeRoom
→ preload
→ READY ACK
→ START
→ audio
→ lipsync
→ gesture
→ camera cut
→ audience reaction
→ score lock
→ reveal
→ verdict
→ END
```

### Test F — replay

```text
disconnect stage
→ reconnect last_seq
→ snapshot
→ replay
→ state identical
```

---

# 48. The ONE golden end-to-end acceptance test

This is the migration gate.

It must be automated.

```text
CREATE
    ↓
one Freak

WRITE
    ↓
one short 8-15s test set

DIRECT
    ↓
pace=.85
expression=annoyed
gesture=lean
pause=937ms

REHEARSE
    ↓
same StageRuntime

PUBLISH
    ↓
share link works

RESPOND
    ↓
lineage established

SUBMIT
    ↓
FastAPI intake

STORE
    ↓
Postgres + R2

QUEUE
    ↓
EpisodeRoom

PERFORM
    ↓
same audio
same timing
same avatar
same delivery

REACT
    ↓
audience event persisted

JUDGE
    ↓
Ella score locked

REPLAY
    ↓
same event sequence
```

If this test fails:

```text
MERGE IS NOT COMPLETE.
```

Passing unit tests alone does not count.

---

# 49. Commit sequence

Do not create one 40,000-line migration commit.

Use this sequence.

### Commit 1

```text
chore: attach killella history and document consolidation boundary
```

Only history + migration doc.

### Commit 2

```text
feat: establish canonical Freak Town contracts and golden fixture
```

No infrastructure.

### Commit 3

```text
feat: import production database and FastAPI foundation
```

No creator UI.

### Commit 4

```text
feat: import TTS media delivery and performance services
```

### Commit 5

```text
feat: import Cloudflare EpisodeRoom runtime
```

### Commit 6

```text
feat: extract shared StageRuntime package
```

### Commit 7

```text
feat: wire Freak Town rehearsal to shared StageRuntime
```

### Commit 8

```text
feat: wire published Freak viewer to shared StageRuntime
```

### Commit 9

```text
feat: port live stage control and audience surfaces
```

### Commit 10

```text
feat: connect Studio intake to Postgres and R2
```

### Commit 11

```text
test: golden Freak create-to-live convergence
```

### Commit 12

```text
docs: freeze killella and declare freaktown canonical
```

Every commit must independently build/test.

---

# 50. Rollback rule

At every stage:

```text
existing Freak Town user-facing route
```

must continue to work until its replacement has passed parity tests.

Never delete old behavior before replacement is verified.

Use feature flags:

```text
USE_NEW_STAGE_RUNTIME
USE_FASTAPI_INTAKE
USE_R2_PUBLISH
USE_EPISODE_ROOM
```

Default them off in the first migration commits.

Turn on one at a time.

Delete flags after stabilization.

---

# 51. Things specifically NOT to do

Do NOT:

```text
move Freak Town into Killella

rename Freak Town back to Killella anywhere

copy Killella Green Room

rewrite Studio in React during merge

maintain two delivery schemas

maintain two StageRuntime implementations

maintain two audio graphs

use D1 as a second business database

use Redis as live-show authority

force avatar presence before audio READY

require 3D generation before creating/rehearsing

make intake rewrite creative artifacts

bring x402/crypto into MVP consolidation

delete current party mode

delete viral reply lineage

switch URL structures during the merge

perform a database rename simultaneously with repo migration
```

---

# 52. Documentation to add

Create:

```text
docs/ARCHITECTURE.md
docs/BOUNDARIES.md
docs/LIVE_RUNTIME.md
docs/CONTRACTS.md
docs/DEPLOYMENT.md
docs/migration/KILLELLA_IMPORT.md
```

`BOUNDARIES.md` should begin:

```text
Freak Town Studio creates performances.

Contracts describe performances.

FastAPI stores and indexes performances.

EpisodeRoom coordinates live performances.

StageRuntime renders performances.

Ella observes and acts on live events.

No subsystem may recreate another subsystem's responsibility.
```

---

# 53. Final repo ownership model

After migration:

```text
prx0r/freaktown
```

is the ONLY active development repository.

Change Killella README to:

```text
# Archived

This repository was consolidated into prx0r/freaktown.

Final imported source:
863cdd37f73436f7ee5118b82340731eb868bf09

Do not add new production code here.
```

Do not delete Killella.

Its history is useful.

But no feature gets implemented there again.

---

# 54. Final architecture invariant

The entire product should reduce to:

```text
                    FREAK TOWN

CREATE / RESPOND / PARTY / HUMAN / AI
                    │
                    ▼
              CHARACTER PACK
                    │
                    ▼
             PERFORMANCE
                    │
              sealed + hashed
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   REHEARSAL                   LIVE
        │                       │
        │                  EpisodeRoom
        │                       │
        └───────────┬───────────┘
                    ▼
               StageRuntime
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
        audio     avatar    camera
          │         │
          └────┬────┘
               ▼
         human reactions
               │
               ▼
              Ella
               │
               ▼
        event + career graph
```

The same Freak.

The same performance.

The same renderer.

The same contracts.

Different contexts.

That is the merged system.

---

# Appendix: dependency honesty

Freak Town's current `requirements.txt` only declares `openai` and `edge-tts`,
despite the current app using Flask and the merged system needing
substantially more infrastructure; Killella's dependency manifest is much
closer to reality. Fix as part of early consolidation (see §35).

# Appendix: architectural split

Above everything else, protect this split:

```text
Freak Town = product + contracts.
Imported infrastructure = execution.
```
