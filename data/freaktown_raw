I reviewed the latest push, including commit `ce039813e59bae855fbaf27480d7b00cc6f17658`, the new `spec2.md`, `comedian-act-appearance.md`, and the current backend implementation.

The **product direction is now substantially better than the implementation**. `Comedian → ActVersion → Appearance` is the right core abstraction, and the newest character UX is much stronger than the original “register an AI agent” concept.

There are several blockers I would fix before adding another feature:

* **Current `main` does not boot:** `backend/main.py` imports `admin`, `audience`, and `stage`, but those route modules do not exist.
* **Authentication/ownership is effectively absent.** `creator_id` is accepted from the client, anyone can create a new ActVersion for someone else's comedian, and episode administration is unauthenticated.
* **The random queue cannot implement the product.** Entry count is capped at `max_contestants`, and `/draw` then selects every eligible entrant. You cannot have 10,000 people in “The Line” competing for four slots with the existing schema.
* **Act immutability is only nominal.** The current hash is truncated and covers only a subset of the Act fields, rather than a canonical serialization of the complete immutable Act.
* **Event sequencing will collide.** Draw hardcodes `seq=0`, start hardcodes `seq=1`, despite `(episode_id, seq)` being unique.
* **The documentation conflicts.** README still describes an “AI comedy competition”, three.ws, Solana prize pool, etc., while the new docs correctly describe a stage for human-written, assisted and autonomous characters.
* **A ~79 MB research MP3 is back in Git**, despite the previous R2 cleanup. `.gitignore` only excludes dataset JSON.
* There are currently **no CI statuses on the latest commit**, no Playwright suite, and no migrations/tests visible despite Alembic and pytest being dependencies.

For the final stack, I would now make a larger call: because the production implementation is still extremely young, **move the live application/runtime to TypeScript on Cloudflare and keep Python only for offline research/evaluation tools**. React + Vite + a Worker is now an officially supported Cloudflare full-stack path, with the Vite plugin running locally in `workerd` close to production. ([Cloudflare Docs][1]) Durable Objects are specifically designed to coordinate thousands of WebSocket clients, and Cloudflare recommends their hibernating WebSocket API and SQLite-backed transactional storage. ([Cloudflare Docs][2])

For assets, R2 remains ideal because Internet egress is currently free. ([Cloudflare Docs][3]) For the stage, React Three Fiber + Three.js + MIT-licensed `@pixiv/three-vrm` gives us a clean open stack, with curated GLBs for dogs/objects/non-humanoids. ([GitHub][4]) For voice, ElevenLabs supports live WebSocket TTS and returns character alignment alongside streamed audio. ([ElevenLabs][5])

Here is the build brief I would hand directly to the coding agent.

# KILLELLA CANONICAL BUILD BRIEF

## 0. Mandate

Rebuild Killella around this product definition:

> **Killella is a live stage where anyone can create a comedian.**

A comedian may be written by a human, assisted by AI, fully AI-generated, puppeteered live by a human, controlled by Killella AI, or eventually controlled by an external agent.

Do not expose this complexity during normal submission.

The normal entrant journey must feel like:

```text
I had a funny idea
→ I chose what it looks like
→ I wrote/got help writing its minute
→ I heard it perform
→ I entered it into The Line
```

Optimize every engineering decision in this exact order:

1. Entrant accessibility
2. Security
3. Runtime speed

Do not optimize for theoretical decentralization, maximum agent configurability, crypto-native users, or infrastructure cleverness ahead of those three priorities.

---

# 1. Stop and stabilize the repository first

Before implementing new features:

### 1.1 Make one specification canonical

Create:

```text
docs/
  PRODUCT.md
  ARCHITECTURE.md
  DOMAIN.md
  PROTOCOL.md
  SECURITY.md
  TESTING.md
  PAYMENTS.md
  ARCHIVE/
```

`PRODUCT.md` absorbs the final conclusions from:

* `spec2.md`
* `comedian-act-appearance.md`

`ARCHITECTURE.md` supersedes:

* `backend-spec.md`
* `killella-stack.md`
* `streaming-and-crypto.md`

Move obsolete docs into `docs/ARCHIVE/`.

Update README so a coding agent cannot accidentally implement the old architecture.

There must be exactly one sentence defining the product:

> **A live stage where anyone can create a comedian.**

Not “AI comedy competition”.

### 1.2 Remove research media from source control

Remove all large audio/video/corpus assets from application Git.

Add:

```gitignore
data/audio/
data/video/
data/raw/
data/research/
*.mp3
*.wav
*.mp4
```

Put research data in a separate **private R2 research bucket**.

Keep only manifests in Git:

```json
{
  "id": "...",
  "storage_key": "...",
  "sha256": "...",
  "source": "...",
  "license_status": "...",
  "purpose": "research"
}
```

Application production assets and private research assets must use separate R2 buckets.

### 1.3 Make broken-head commits impossible

No commit may merge if:

```bash
pnpm typecheck
pnpm lint
pnpm test
pnpm test:e2e:smoke
```

does not pass.

The current situation where `main.py` imports nonexistent modules must never recur.

---

# 2. Final production stack

Use a TypeScript-first monorepo.

```text
killella/
├── apps/
│   └── web/
│       ├── src/
│       │   ├── creator/
│       │   ├── watch/
│       │   ├── stage/
│       │   ├── comedian/
│       │   └── admin/
│       ├── worker/
│       │   ├── api/
│       │   ├── auth/
│       │   ├── queues/
│       │   └── index.ts
│       └── wrangler.jsonc
│
├── packages/
│   ├── domain/
│   ├── protocol/
│   ├── db/
│   ├── stage/
│   ├── ai/
│   ├── voice/
│   ├── auth/
│   ├── payments/
│   └── observability/
│
├── research/
│   └── python/
│
├── tests/
│   ├── e2e/
│   ├── fixtures/
│   ├── load/
│   └── replay/
│
└── docs/
```

### Technology

Frontend:

```text
React
TypeScript
Vite
React Router
Zod
Zustand
```

Platform:

```text
Cloudflare Workers
Cloudflare Durable Objects
Cloudflare Queues
Cloudflare R2
Cloudflare Turnstile
```

API:

```text
Hono
Zod schemas shared with client
```

Long-term DB:

```text
PostgreSQL
Neon or equivalent managed Postgres
Cloudflare Hyperdrive
Drizzle ORM
Drizzle Kit migrations
```

Realtime:

```text
one SQLite-backed Durable Object per live Episode
WebSocket Hibernation API
```

Stage:

```text
Three.js
React Three Fiber
@pixiv/three-vrm for humanoids
curated GLB body adapters for non-humanoids
Web Audio API
```

AI:

```text
provider interface
OpenAI
Anthropic
others later
```

Voice:

```text
ElevenLabs production
provider abstraction
```

Authentication:

```text
Privy
email
Google/social
passkeys
wallet linking
```

Payments:

```text
Stripe Connect for normal users
Privy + Solana + USDC as optional crypto rail
```

Streaming:

```text
OBS Browser Source
→ YouTube/Rumble/etc.
```

Testing:

```text
Vitest
Cloudflare Workers Vitest pool
Playwright
@axe-core/playwright
```

Do not run Redis in the final application. Durable Objects handle live coordination; Queues handle async delivery.

Do not put FastAPI in the live request path.

Existing Python research/evaluation code can remain under `research/python/`.

---

# 3. Core domain model

Replace:

```text
EpisodeContestant
```

doing five different jobs with an explicit lifecycle.

Canonical graph:

```text
User
  ↓ owns
Comedian
  ↓ has
ActVersion
  ↓ entered as
Submission
  ↓ selected into
Appearance
  ↓ produces
ShowEvent[]
```

## User

```text
id
privy_user_id UNIQUE
handle UNIQUE
display_name
created_at
```

Never trust a `creator_id` received from the browser.

Resolve identity exclusively from the verified authentication token.

---

# 4. Comedian

Persistent public character identity.

```text
id UUID
owner_user_id FK
name
slug UNIQUE
premise
body_family_id
status
created_at
```

`name` is **not globally unique**.

Two people should be able to create characters with the same display name.

Slug can resolve collisions.

Comedian persists indefinitely.

---

# 5. ActVersion

An Act is a frozen incarnation of that comedian.

```text
id
comedian_id
revision
parent_act_version_id
created_by_user_id

manifest JSONB
content_sha256 CHAR(64)

created_at
sealed_at
```

The manifest includes everything that affects the appearance:

```json
{
  "schemaVersion": 1,

  "character": {
    "name": "...",
    "deal": "...",
    "facts": []
  },

  "body": {
    "family": "dog",
    "variant": "german-shepherd",
    "outfit": "police-vest"
  },

  "voice": {
    "voiceId": "..."
  },

  "minute": {
    "text": "...",
    "authorship": "human",
    "assistance": []
  },

  "interview": {
    "controller": "killella_ai",
    "facts": []
  }
}
```

## Immutability

Use deterministic canonical JSON.

Hash the **entire manifest**:

```text
SHA-256(canonical_manifest)
```

Store all 64 hex characters.

Never hash only the minute.

Never trust a browser-provided hash.

After `sealed_at`:

```text
UPDATE ActVersion
```

must be forbidden at the domain layer and database layer.

Changing anything creates:

```text
ActVersion revision N+1
```

Use a transaction/row lock when allocating revisions so simultaneous submissions cannot both create revision 4.

---

# 6. Submission

This represents joining The Line.

```text
id
episode_id
comedian_id
act_version_id
submitted_by_user_id

qualification_status
moderation_status
technical_status

submitted_at
eligible_at
rejected_at
rejection_reason
```

Possible lifecycle:

```text
draft
→ submitted
→ validating
→ eligible

or

→ rejected
```

## Critical distinction

An episode may have:

```text
10,000 eligible submissions
```

and:

```text
5 appearance slots
```

Do not cap submissions using `max_contestants`.

---

# 7. Appearance

Only created when a Submission is actually selected.

```text
id
episode_id
submission_id
draw_position
selected_at

performance_plan_id

performance_started_at
performance_ended_at

result_json
```

An Appearance freezes the exact ActVersion selected.

Even if its creator creates Act v8 five seconds afterward, Appearance still points to v7.

---

# 8. Entrant UX — this is the highest priority

## Anonymous first

A visitor should be able to explore Killella before creating an account.

CTA:

# PUT SOMEONE ON STAGE

Only request login when they start saving/submitting.

Normal login:

```text
Continue with Google
Continue with email
Continue with passkey
```

Do not mention crypto.

Do not ask for KYC.

Do not ask for payment.

Do not ask for an API key.

---

# 9. Creator flow

The entire ordinary flow is:

## Step 1

# WHO'S GOING ON STAGE?

Visual body cards:

```text
Human
Dog
Robot
Creature
Object
Animal
Mystery
```

Cards must have semantic text labels.

WebGL must NOT load on this screen.

Use optimized static previews.

---

## Step 2

# WHAT'S THEIR NAME?

Normal text input.

Autosave.

---

## Step 3

# WHAT'S THEIR DEAL?

One large field.

Example placeholder:

> A police sniffer dog born without a sense of smell who thinks all the other dogs are flirting with him.

Target is one funny idea, not a system prompt.

---

## Step 4

# GIVE THEM A MINUTE

Three equal options:

```text
WRITE IT MYSELF
HELP ME WRITE IT
WRITE IT FOR ME
```

No authorship mode is treated as more legitimate.

### Write myself

Plain editor.

### Help me

AI operates as writing assistant.

Never silently replace the writer's copy.

Offer explicit suggestions.

### Write it for me

Generate from character premise.

Creator can edit output.

Track final provenance.

---

# 10. Minute editor

Show:

```text
0:47 / ~1:00
```

Word count is only an estimate.

Actual synthesized audio duration is authoritative.

Buttons:

```text
PLAY PREVIEW
REGENERATE VOICE
SAVE
SUBMIT
```

The creation experience should still be useful even if the character is never drawn.

---

# 11. Voice selection

Start with a curated licensed catalog.

Do not support arbitrary voice cloning at launch.

Give:

```text
6–12 excellent voices
+ Surprise me
```

Samples should already exist in R2 so voice selection is instant.

---

# 12. Interview mode

Ask:

# WHEN ELLA TALKS TO THEM, WHO ANSWERS?

Default:

```text
● Bring my character to life
```

Secondary:

```text
○ I'll answer live
```

Advanced:

```text
○ External agent
```

External agent mode stays **feature-flagged OFF** for public users initially.

The first launch supports:

```text
Killella AI
Human puppeteer
```

That gives nearly all the creative space without accepting arbitrary server URLs.

---

# 13. Preview

Only now load the 3D engine.

Creator sees:

```text
their body
their voice
their minute
basic gestures
captions
```

If WebGL fails:

```text
2D character preview
+
audio
+
captions
```

must still work.

Creator submission must never require WebGL.

---

# 14. Final submission

Use Turnstile on final submission.

Flow:

```text
Create/finalize ActVersion
→ seal canonical manifest
→ create Submission
→ run validation
→ ELIGIBLE
```

Result:

```text
NO-NOSE NOLAN IS IN THE LINE

Act #3
Status: Eligible

Next show:
Friday 8 PM
```

No wallet.

No stake.

No entry fee.

---

# 15. Authentication and authorization

Every server mutation has explicit capabilities.

## Public

May:

```text
view public comedian
view current show
connect anonymous audience session
send rate-limited laugh event
```

## Authenticated creator

May:

```text
create comedian
create ActVersion for OWN comedian
submit OWN ActVersion
manage OWN live puppeteer session
```

Cannot supply owner ID manually.

## Admin

May:

```text
create episode
freeze eligible pool
run draw
start/pause/end show
issue stage commands
approve sponsor creative
```

## Stage client

Gets a short-lived machine token.

May:

```text
read stage events
ack playback
report playback status
```

Cannot perform admin mutations.

## Human puppeteer

Token scoped to:

```text
one Appearance
one episode
one response channel
short expiry
```

Cannot modify the character or issue stage/admin events.

---

# 16. Durable Object live architecture

Create:

```text
EpisodeRoom:{episode_id}
```

One per live show.

The EpisodeRoom owns:

```text
current phase
active Appearance
ordered event sequence
timers
connected stage clients
connected audience clients
crowd aggregation window
human puppeteer connection
```

Use SQLite-backed Durable Object storage.

Persist important live state before broadcasting it.

Tables inside DO:

```text
state
events
command_idempotency
crowd_windows
```

Every ShowEvent receives:

```text
eventId
episodeId
seq
schemaVersion
type
actor
payload
effectiveAt
createdAt
correlationId
```

`seq` is allocated exclusively inside EpisodeRoom.

Never hardcode sequence values.

---

# 17. Command model

Clients send commands.

Commands are not events.

Example:

```json
{
  "commandId": "uuid",
  "type": "show.start",
  "expectedVersion": 18,
  "payload": {}
}
```

EpisodeRoom:

```text
authenticate
→ authorize
→ check idempotency
→ validate transition
→ mutate durable state
→ append event
→ broadcast event
```

Repeating the same `commandId` must not create another event.

---

# 18. WebSocket security

All production sockets use:

```text
wss://
```

Enforce exact Origin allowlist.

Authenticate on connection or immediately after connection.

Maximum application frame:

```text
16 KB
```

unless a specific protocol message has a documented larger limit.

Implement:

```text
per-session rate limits
per-IP coarse limits
client sequence numbers
duplicate suppression
heartbeat
expiry
backpressure
connection caps
```

Never send API credentials through WebSockets.

Never log auth tokens.

Audience cannot emit arbitrary event types.

Their protocol is an explicit allowlist.

---

# 19. Crowd reactions

Normal audience message:

```json
{
  "type": "reaction",
  "reaction": "laugh",
  "appearanceId": "...",
  "clientSeq": 83
}
```

Do not trust:

```text
intensity
score
timestamp
comedianId
```

from the client.

EpisodeRoom adds authoritative time and active Appearance.

Per session:

```text
cap laugh frequency
dedupe clientSeq
ignore out-of-phase events
```

Aggregate locally every ~250 ms for display.

Persist 1-second buckets:

```text
active viewers
unique laughers
laugh events
laugher share
```

Do not persist every button mash into PostgreSQL.

Main visible metric:

```text
share of active audience laughing
```

not total clicks.

---

# 20. Random draw protocol

The Line must be legitimately random and replayable.

Do not use `random.shuffle()`.

Implement versioned deterministic draw protocol.

### Freeze

At draw cutoff:

1. Load all eligible Submission IDs.
2. Sort them deterministically.
3. Hash the complete eligible set.
4. Generate 32 random bytes using CSPRNG.
5. Publish `SHA256(seed)` as the seed commitment.

### Draw

Reveal seed.

Derive deterministic random bytes from:

```text
SHA256(seed || counter)
```

Use deterministic Fisher–Yates or reservoir sampling.

Select:

```text
randomSlots = maxAppearances - residentSlots
```

Store:

```json
{
  "algorithm": "KILLELLA_DRAW_V1",
  "eligibleSetHash": "...",
  "seedCommitment": "...",
  "seed": "...",
  "selectedSubmissionIds": []
}
```

Anyone can replay the draw afterward.

No blockchain is necessary for this.

---

# 21. Show stage

OBS does not get a special renderer.

Use the exact same Stage application.

URLs:

```text
/show/{episodeId}
```

Audience mode.

```text
/stage/{episodeId}?mode=obs
```

OBS mode.

Both consume canonical ShowEvents.

The OBS client removes interaction UI and renders broadcast framing.

---

# 22. Body architecture

Define:

```ts
interface BodyAdapter {
  load(): Promise<void>
  enter(): void
  exit(): void
  idle(): void
  speak(audio: AudioSource): void
  gesture(name: Gesture): void
  emote(name: Emotion): void
  lookAt(target: StageTarget): void
}
```

Initial adapters:

```text
HumanoidVRMAdapter
DogGLBAdapter
RobotGLBAdapter
ObjectGLBAdapter
```

Characters select a body definition.

They do not supply code.

Body catalog entry:

```json
{
  "id": "dog.german-shepherd.v1",
  "family": "dog",
  "asset": "...",
  "supportedGestures": [],
  "supportedEmotions": [],
  "mouthMode": "jaw"
}
```

No arbitrary GLB uploads in MVP.

---

# 23. PerformancePlan

Prepared minutes are compiled before showtime.

```json
{
  "appearanceId": "...",
  "durationMs": 59120,
  "audioAssetId": "...",

  "segments": [],
  "cues": [
    {
      "atMs": 2400,
      "type": "gesture",
      "value": "shrug"
    }
  ]
}
```

Stage preloads:

```text
model
textures
audio
captions
animation clips
```

before entrance.

Prepared minutes must not depend on a live TTS call.

---

# 24. Voice

## Prepared minute

Generate once.

Store:

```text
audio
character/word timings
provider metadata
voice ID
content hash
```

in R2/DB.

Cache key should depend on:

```text
text
voice
voice settings
provider model
```

Identical preview requests should not regenerate audio.

## Live Ella/interview

Use ElevenLabs streaming TTS.

Pipeline:

```text
LLM streaming
→ natural phrase chunker
→ ElevenLabs streaming TTS
→ stage Web Audio
→ mouth animation
→ captions
```

Do not send tokens individually to TTS.

Set timeouts.

If TTS fails:

```text
show captions
use fallback voice if configured
continue show
```

Never freeze the episode indefinitely.

---

# 25. Ella interview engine

Do not implement Ella as one giant prompt.

Maintain structured state:

```text
facts
open threads
contradictions
callbacks
audience signals
comedic targets
turn count
```

Every turn outputs a structured decision:

```json
{
  "action": "PROBE",
  "target": "fake medieval identity",
  "utterance": "...",
  "shouldEnd": false
}
```

Allowed actions:

```text
GROUND
PROBE
CALLBACK
CHALLENGE
LIVE_TEST
CHANGE_TOPIC
END
```

Separate:

```text
conversation reasoning state
from
spoken dialogue
```

Store summaries/provenance necessary for replay/debugging, not hidden model chain-of-thought.

---

# 26. Live tests

Start with only four:

```text
TEN_WORDS
AUDIENCE_WORD
REWRITE
ROAST_CREATOR
```

Do not implement model swapping, context surgery, temperature theater, memory deletion, etc. until the basic interview is reliably entertaining.

Every Live Test is a typed protocol event.

---

# 27. Creator reveal

The creator is a first-class public identity.

Character card:

```text
NO-NOSE NOLAN
created by @alice
```

The Act may optionally reveal provenance after the performance:

```text
Minute:
Human-written

Interview:
Killella AI
```

Or:

```text
Minute:
AI-generated

Creator:
@alice
```

Never imply that avatar type determines authorship.

---

# 28. Payments — architect now, activate later

Submission never depends on payment infrastructure.

Define:

```ts
interface TipRail {
  prepareTip(...)
  confirmTip(...)
  refundTip(...)
}
```

Implement later:

```text
StripeTipRail
SolanaUSDCTipRail
```

## Crypto

Privy handles normal authentication and optional embedded/external wallet.

Normal user should never see:

```text
seed phrase
RPC
gas
ATA
mint
```

For a crypto tip:

```text
creator share
+
Killella platform share
```

can be transferred directly in one transaction.

Killella should not custody the creator portion.

Target:

```text
95% creator
5% Killella
```

for crypto.

## Card

Use Stripe Connect.

Do not hardcode “5% of gross” before processor economics are modelled.

Application should store configurable fee policy by payment rail.

Do not require Stripe onboarding when someone creates a comedian.

Creator sees:

```text
ENABLE TIPS
```

when they actually want to monetize.

---

# 29. Tip events

A confirmed tip may become a ShowEvent:

```json
{
  "type": "tip.confirmed",
  "appearanceId": "...",
  "amountDisplay": "$10",
  "senderDisplay": "@bob",
  "message": "..."
}
```

Only emit after payment provider confirmation.

Never trust a browser “payment succeeded” message.

Moderate tip messages before public rendering.

Money must not influence official selection or audience score.

---

# 30. Sponsors

Do not build an auction yet.

Build a basic sponsor domain:

```text
SponsorCampaign
SponsorCreative
SponsorPlacement
```

Supported placements:

```text
OPENING_READ
TRANSITION
SPONSORED_CHALLENGE
CHARACTER_SPONSOR
```

Advertiser inputs are structured:

```text
brand
approved claims
required phrase
CTA
destination URL
logo
optional video asset
```

No advertiser-supplied JS.

No advertiser-supplied HTML.

Ella sponsor copy is generated beforehand, approved/frozen, then read during show.

Include sponsor events in replay protocol:

```text
sponsor.read
sponsor.overlay.show
sponsor.overlay.hide
```

---

# 31. PostgreSQL

Postgres is long-term application truth for:

```text
users
comedians
act_versions
submissions
appearances
episodes
creator profiles
media
generations
payments
sponsors
post-show analytics
```

Durable Object storage is authoritative for the live room while it is running.

Replicate live events asynchronously to long-term storage.

At show completion create an immutable episode archive.

---

# 32. Queue consumers

Use Cloudflare Queues for:

```text
TTS generation
AI minute generation
moderation
performance compilation
event replication
post-show reports
clip jobs later
```

Every job:

```text
has unique job ID
is idempotent
supports retry
records failure
```

Configure a Dead Letter Queue.

The user must see:

```text
Preview generation failed — Retry
```

rather than an endless spinner.

---

# 33. Security baseline

Before public launch:

* strict CSP
* HSTS
* no wildcard CORS
* same-origin APIs where possible
* Turnstile on abuse-prone submission operations
* request body limits
* schema validation on every boundary
* normalized Unicode inputs
* output escaping
* rate limits
* authorization on every mutation
* secret scanning
* dependency scanning
* audit log for admin operations
* short-lived privileged tokens
* no arbitrary remote URLs fetched by application servers
* no user-controlled HTML/JS
* no arbitrary 3D uploads
* no public voice cloning
* no client-generated ownership IDs

External agents later require a dedicated egress gateway with SSRF protection.

---

# 34. Accessibility baseline

The entire creator flow must work:

```text
without WebGL
with keyboard only
with screen reader
with reduced motion
with captions
```

Use semantic HTML before visual components.

Every avatar card has visible text.

Audio has:

```text
play
pause
caption/transcript
```

Never communicate state only through color.

Creator screens must not load the 3D engine until Preview.

Watch page modes:

```text
FULL 3D
REDUCED 3D
VIDEO/STREAM
TRANSCRIPT
```

Respect:

```css
prefers-reduced-motion
```

---

# 35. E2E TEST PLAN

These tests define “done”.

## A — repository boot

CI must prove:

```text
build succeeds
Worker starts
database migrations apply from empty DB
all route modules import
health endpoint returns 200
```

This prevents the current broken-head situation.

---

## B — entrant golden path

Playwright:

```text
anonymous homepage
→ Put Someone On Stage
→ sign in using test auth
→ choose Dog
→ enter No-Nose Nolan
→ enter premise
→ Write Myself
→ enter minute
→ choose voice
→ preview
→ audio job completes
→ preview plays
→ choose Killella AI interview
→ submit
→ Turnstile test success
→ immutable ActVersion created
→ Submission created
→ qualification passes
→ status reads Eligible
```

Assert DB records.

Assert the creator ID came from authentication, not the browser request.

---

## C — AI-assisted path

```text
create Robot
→ Help Me Write It
→ mocked LLM returns suggestions
→ creator accepts one
→ final provenance = assisted
→ preview
→ submit
```

---

## D — human puppeteer path

```text
creator chooses I'll Answer Live
→ submission eligible
→ selected
→ short-lived puppeteer token issued
→ creator can submit dialogue for own Appearance
→ second user cannot
```

---

## E — authorization

Test:

```text
User B cannot create an ActVersion for User A's comedian.
User B cannot submit User A's Act.
Normal user cannot create/start/end episodes.
Client-supplied creatorId is ignored/rejected.
Expired privileged token fails.
Wrong puppeteer Appearance token fails.
```

---

## F — Act immutability

Tests:

```text
same canonical manifest → identical hash

changing:
voice
body
minute
authorship
facts
interview controller
outfit

→ changes hash
```

Sealed Act cannot be updated.

Concurrent requests for new revisions produce:

```text
v7
v8
```

not two `v7`s.

---

## G — queue scalability

Seed:

```text
10,000 eligible submissions
```

Episode:

```text
5 slots
1 resident
```

Assert:

```text
10,000 remain eligible
4 random selected
1 resident selected
exactly 5 Appearances
no duplicates
```

---

## H — draw verification

Given:

```text
same frozen eligible IDs
same revealed seed
same algorithm version
```

two independent implementations must produce identical selected IDs.

Verify seed commitment.

Verify eligible-set hash.

Add deterministic fixtures to repository.

---

## I — episode state machine

Test valid transitions.

Reject invalid:

```text
OPEN → LIVE
COMPLETED → LIVE
CANCELLED → START
```

unless explicitly supported.

Repeated command with same `commandId` does not duplicate transition/event.

---

## J — event sequence concurrency

Send multiple commands concurrently.

Assert:

```text
seq 101
seq 102
seq 103
...
```

No duplicates.

No gaps caused by successful committed events.

---

## K — WebSocket reconnect

Stage receives through:

```text
seq 300
```

Disconnect.

Events 301–320 occur.

Reconnect with:

```text
lastSeq = 300
```

Stage receives snapshot/replay and ends at canonical state 320.

---

## L — mid-show audience join

Viewer opens page 24 seconds into set.

Assert immediately receives:

```text
active comedian
active Act
current phase
timer state
crowd state
```

without waiting for another event.

---

## M — crowd anti-spam

Simulate:

```text
100 legitimate viewers
1 malicious viewer
```

Malicious viewer sends 5,000 laugh events.

Assert their contribution is capped.

100 unique users laughing once must outweigh one user hammering button 5,000 times.

---

## N — crowd latency

Staging performance target:

```text
reaction → visible aggregate
p95 < 250 ms same-region
p95 < 500 ms broadly
```

Measure rather than merely assert function execution time.

---

## O — TTS preview

Normal CI uses stub TTS.

Assert:

```text
request created
cache key generated
audio stored
timings stored
duration calculated
status completes
```

Repeated identical preview should hit cache.

Nightly/provider contract test hits ElevenLabs with a short controlled sample.

---

## P — TTS failure

Simulate:

```text
timeout
429
500
invalid audio
```

UI must:

```text
stop loading
show useful failure
allow retry
```

Live show must fall back rather than freeze.

---

## Q — body tests

For every body family:

```text
load
idle
enter
speak
gesture
exit
```

Use deterministic screenshot regression where practical.

Test:

```text
Human VRM
Dog GLB
Robot GLB
Object GLB
```

---

## R — no-WebGL test

Force WebGL unavailable.

Creator can still:

```text
create
write
hear preview
submit
```

Viewer gets fallback experience.

---

## S — accessibility

Use `@axe-core/playwright` on:

```text
homepage
all creator screens
minute editor
preview
submission status
watch page
comedian page
tip modal
```

Also manually/automatically test complete keyboard-only submission.

Automated axe passing is not enough; maintain manual accessibility checklist.

---

## T — mobile

Playwright/mobile runs:

```text
iPhone-sized viewport
Android-sized viewport
slow connection
touch input
```

Creator form must not jump/reflow when 3D dependencies are absent.

---

## U — sponsor security

Sponsor creative attempting:

```html
<script>...</script>
```

must never execute.

Sponsor links are validated.

Only structured fields render.

---

## V — payment tests

Stripe test mode:

```text
tip initiated
payment provider confirms
destination receives correct amount
platform fee recorded
webhook duplicate received twice
ledger remains single transaction
refund updates state
```

Browser redirect/success state is not payment truth.

Crypto tests later:

```text
correct USDC mint
correct creator destination
correct platform destination
correct split
no arbitrary destination substitution
```

---

## W — replay

Record an Episode fixture.

Delete all live state.

Replay only from:

```text
ShowEvents
snapshots
R2 assets
```

Assert same:

```text
phase sequence
appearance sequence
captions
performance timing
Ella dialogue
draw result
final result
```

Replay must not call live LLM/TTS.

---

## X — failure/chaos

Inject:

```text
LLM timeout
TTS timeout
R2 failure
Postgres delay
Queue consumer retry
Durable Object restart
stage disconnect
audience reconnect
```

The show may degrade.

It may not become permanently stuck.

---

## Y — load tests

Staging scenarios:

```text
1,000 WebSockets
5,000 WebSockets
10,000 WebSockets
```

Bursty laughs during punchline windows.

Measure:

```text
CPU
DO duration
message latency
dropped connections
backpressure
memory
queue lag
```

Do not assume the theoretical Durable Object socket limit equals acceptable Killella production capacity.

---

# 36. CI

Every pull request:

```text
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm test:workers
pnpm db:migrate:test
pnpm test:e2e:smoke
pnpm test:a11y
dependency review
CodeQL
secret scan
```

Required.

On `main`:

```text
full Playwright Chromium
Firefox
WebKit
visual regression
replay suite
small load test
```

Nightly:

```text
real ElevenLabs contract
real AI-provider contract
staging load test
DAST/security scan
```

Use Cloudflare's official Turnstile testing keys in E2E only.

Never deploy those keys to production.

---

# 37. Episode Zero acceptance test

The MVP is not complete until this single scenario works automatically.

Create:

```text
Creator Alice
→ No-Nose Nolan
→ Dog
→ human-written minute

Creator Bob
→ Corporate Robot
→ Robot
→ AI-assisted minute
```

Seed another:

```text
100 fake eligible submissions
```

Create Episode Zero.

Assign:

```text
1 resident
4 random slots
```

Freeze line.

Publish draw seed commitment.

Reveal seed.

Verify draw.

Open:

```text
OBS stage client
100 simulated audience clients
```

Selected comedian enters.

Stage preloads assets.

60-second minute plays.

Avatar moves/lip-syncs.

Captions remain synchronized.

Audience laughs.

Crowd display updates.

Set ends.

Ella interview begins.

Character answers.

Ella runs a live test.

Audience reacts.

Author/model provenance is revealed according to settings.

Audience votes:

```text
SEE THEM AGAIN?
```

Appearance completes.

Next comedian enters.

Episode ends.

Event log is archived.

Creator receives post-show report.

Replay reconstructs the episode without AI/TTS network calls.

That is the MVP.

---

# 38. Explicitly DO NOT BUILD yet

Until Episode Zero above passes:

```text
crypto staking
entry fees
smart-contract escrow
NFTs
golden-ticket tokens
self-serve advertiser auction
arbitrary user GLB uploads
public voice cloning
arbitrary external agent URLs
cross-platform chat aggregation
complex judge scoring
season tokenomics
Bittensor integration
model marketplace
```

Keep interfaces where appropriate.

Do not implement them.

---

# 39. Performance targets

Creator:

```text
No WebGL before preview.
Normal creator UI LCP target <2.5s on typical mobile.
Autosave must be nonblocking.
```

Submission:

```text
No wallet required.
No payment required.
No KYC required.
No technical configuration required.
```

Realtime:

```text
ShowEvent broadcast p95 <200ms target.
Audience reaction aggregate p95 <250ms same-region target.
Reconnect + authoritative snapshot <1s target.
```

Stage:

```text
60 FPS desktop target.
30 FPS supported-mobile floor.
automatic fallback below capability threshold.
```

Voice:

```text
Prepared minutes fully cached before appearance.
Live Ella speech first-audio target roughly 1–1.5s, measured in production.
```

Reliability:

```text
0 committed ShowEvent loss in reconnect tests.
0 duplicate transitions from repeated command IDs.
100% deterministic draw replay.
100% deterministic completed-show event replay.
```

---

# 40. Primary product metric

Engineering must expose analytics for:

```text
landing
→ creator started
→ account created
→ character created
→ minute completed
→ preview played
→ submission made
→ eligible
```

The key early number is:

> **What percentage of people with a funny character idea successfully get that character into The Line?**

Target ordinary nontechnical users.

Secondary creator loop:

```text
Appearance
→ creator views report
→ creates next ActVersion
→ resubmits
```

The technology exists to make impossible characters perform.

The moat begins when those characters accumulate identity, history, audience, creators, earnings, relationships with Ella and immutable canonical appearances.

Protect that data model above everything else.

A few stack choices deserve emphasis. Cloudflare's current guidance makes React + Vite + Workers a stable, first-party route; Durable Objects' hibernation API is specifically recommended for WebSocket servers, and new Durable Objects are recommended to use transactional SQLite storage. ([Cloudflare Docs][1]) Hyperdrive can sit in front of managed PostgreSQL and officially documents Drizzle as a lightweight type-safe option. ([Cloudflare Docs][6])

The testing choice is also straightforward: Playwright officially supports axe-based accessibility assertions, while Cloudflare provides dedicated Turnstile test credentials specifically so Playwright-style E2E flows do not become flaky CAPTCHA tests. ([Playwright][7])

The largest architectural shift I would make from the current push is therefore: **preserve the new domain/product thinking, but don't invest further in the current FastAPI/Redis live runtime. Move the actual product to one TypeScript/Cloudflare system now, while there is almost nothing expensive to migrate.** That yields the simplest entrant experience, the narrowest security boundary, and the fastest realtime architecture in that priority order.

[1]: https://developers.cloudflare.com/workers/framework-guides/web-apps/react/ "https://developers.cloudflare.com/workers/framework-guides/web-apps/react/"
[2]: https://developers.cloudflare.com/durable-objects/best-practices/websockets/ "https://developers.cloudflare.com/durable-objects/best-practices/websockets/"
[3]: https://developers.cloudflare.com/r2/pricing/ "https://developers.cloudflare.com/r2/pricing/"
[4]: https://github.com/pmndrs/react-three-fiber/blob/master/docs/getting-started/introduction.mdx "https://github.com/pmndrs/react-three-fiber/blob/master/docs/getting-started/introduction.mdx"
[5]: https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts "https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts"
[6]: https://developers.cloudflare.com/hyperdrive/ "https://developers.cloudflare.com/hyperdrive/"
[7]: https://playwright.dev/docs/accessibility-testing "https://playwright.dev/docs/accessibility-testing"
