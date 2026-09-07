# Ella as a First-Class Realtime Subsystem + Production Stack

## What Killella is actually using now

Current head is `bd12f46`, and it has a genuine split architecture:

```text
                    FREAK TOWN / KILLELLA

                         CLOUDFLARE
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
     Worker/Hono       Durable Object            R2
     API + website     EpisodeRoom           media/assets
        │                    │                    │
        │             live show state             │
        │             WebSockets                  │
        │             events/reactions             │
        │                                         │
        └────────────────┐       ┌────────────────┘
                         ▼       ▼
                         VPS / PYTHON
                         FastAPI
                         Postgres
                         Redis
                         AI/TTS/generation
                         ML pipelines
```

The latest Worker config has **D1, R2, Durable Objects, Queues and KV** wired.

And R2 isn't aspirational anymore: `MediaStore` actually uploads sealed set audio, performance manifests, timings and plans through the S3-compatible R2 API.

The Python side is still FastAPI + Postgres + Redis on the VPS.

### One config bug to fix

There is a naming mismatch:

```text
Worker R2 bucket:
freak-town-assets
```

while Python defaults to:

```text
R2_BUCKET=freak-town
```

Unless production env overrides it, those are literally two different buckets.

Standardize immediately on:

```text
freak-town-assets
```

or whatever canonical name you choose.

---

# Are we using Cloudflare Stream?

**No, not currently.**

There is no Stream live input/API integration in the current production config.

And I now think we should use it — but **not as the foundation of everything**.

Cloudflare Stream is excellent for:

```text
video ingest
adaptive encoding
website playback
live recording
VOD
simulcast
```

It accepts RTMPS/SRT from OBS and can automatically turn a live broadcast into a recording. ([Cloudflare Docs][1])

It can also restream one input to up to **50 destinations**. ([Cloudflare Docs][2])

Pricing is very reasonable:

```text
$5 / 1,000 stored minutes
$1 / 1,000 delivered viewer-minutes
encoding + ingress free
```

([Cloudflare Docs][3])

But there is an important limitation:

**normal Cloudflare Stream delivery currently tops out at 1080p.** ([Cloudflare Docs][4])

So don't put our 4K master exclusively through Stream.

---

# My production stack

I'd make this canonical.

```text
                       freak.town
                           │
                    CLOUDFLARE WORKER
                  auth / HTTP / routing
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
     EpisodeRoom       PostgreSQL            R2
   Durable Object      via Hyperdrive       assets
          │                │                 │
          │                │                 │
     LIVE EVENTS       durable truth      WAV/VRM/MP4
     reactions         users/shows        manifests
     score locks       characters         ML exports
     camera cuts       results
          │
          ▼
      Stage Runtime
      Three.js/VRM
          │
          ▼
          OBS
          │
    ┌─────┼──────────────┐
    ▼     ▼              ▼
 Rumble YouTube    Cloudflare Stream
 4K60    4K60           1080p
                         │
                         ▼
                    freak.town/watch
```

## Remove D1 as a second source of truth

The Worker currently has D1 while Python has Postgres.

I wouldn't maintain:

```text
D1 users/shows
+
Postgres users/shows
```

Use Postgres as canonical.

Cloudflare now explicitly recommends **Hyperdrive** for Workers talking to external Postgres. It maintains pooled connections close to the database and eliminates repeated TCP/TLS/auth round trips. ([Cloudflare Docs][5])

So:

```text
Worker
   ↓
Hyperdrive
   ↓
Postgres
```

Then D1 can disappear or be restricted to genuinely edge-local ephemeral data.

That makes the architecture far easier to reason about.

---

# R2 is absolutely the right choice

Keep it.

R2 has:

* S3 compatibility
* strong consistency
* no Internet egress fee
* 10GB/month free tier
* currently $0.015/GB-month standard storage

([Cloudflare Docs][6])

Use it for:

```text
avatars/
voice refs/
sets/
walkouts/
performance manifests/
event logs/
vertical clips/
4K masters if desired
training data/
judge runs/
reaction datasets/
```

Not as a database.

---

# EpisodeRoom is exactly right

This may actually be the strongest infrastructure decision in Killella.

One:

```text
EpisodeRoom Durable Object
```

per show.

It owns:

```text
event sequence
show phase
active performer
audience connections
reaction ingestion
score locks
camera commands
POT events
Ella events
```

Cloudflare specifically positions Durable Objects + hibernating WebSockets for multiplayer/chat/realtime coordinated state, with thousands of clients per object and up to 32,768 accepted WebSockets as a platform limit. ([Cloudflare Docs][7])

So **don't replace this with Redis pub/sub**.

Redis becomes much less important.

---

# Cloudflare Stream vs Realtime

There's a really interesting new option.

Cloudflare now has **Stream Live WebRTC** using WHIP/WHEP with **sub-second playback to thousands of viewers**. ([Cloudflare Docs][8])

That is extraordinarily relevant to Freak Town because voting/reactions suck if the audience is 8 seconds behind.

However, as of September 8, 2026, the WebRTC mode has a significant limitation:

> WHIP/WHEP streams currently cannot simultaneously use recording, HLS playback or RTMP/SRT simulcasting. ([Cloudflare Docs][8])

So don't bet the whole show on it yet.

### For now

Do:

```text
OBS
├── 4K → YouTube
├── 4K → Rumble
└── 1080p → Cloudflare Stream
```

Cloudflare Stream handles:

```text
freak.town viewer
automatic recording
VOD archive
```

and enable its LL-HLS option. Cloudflare exposes `preferLowLatency` specifically for this. ([Cloudflare Docs][9])

### Later

For the hardcore interactive Freak Town audience:

```text
Stage
  ↓
WebRTC
  ↓
Cloudflare Realtime / Stream WebRTC
  ↓
<1 sec audience
```

Cloudflare Realtime SFU is explicitly designed for interactive broadcasts and AI/media pipelines, using WebRTC globally. ([Cloudflare Docs][10])

Even better: the first **1,000GB/month of Realtime SFU egress is currently free**, then $0.05/GB. ([Cloudflare Docs][11])

So there is a credible future path to a truly live interactive show.

---

# Now Ella. This is the bigger architectural issue.

Yes.

**Ella absolutely should not be a normal stateless REST call.**

Something like:

```text
set finishes
↓
POST transcript to model
↓
wait
↓
get text
↓
call edge-tts
↓
wait
↓
play WAV
```

will make her feel dead.

You're thinking of a **Realtime / Live model API**, rather than a normal inference endpoint.

And there are now very good ones.

---

# The key realization: Ella actually needs TWO brains

Do not use the same pipeline for:

```text
"jesus christ"
```

and:

```text
8.7 / KEEP / Golden Ticket / detailed judgment
```

Those have radically different latency/intelligence requirements.

Build:

```text
                    ELLA
                      │
          ┌───────────┴────────────┐
          ▼                        ▼
      ELLA LIVE                 ELLA JUDGE
    <1 sec reactions          deeper evaluation
    interruptions             canonical scoring
    banter                    theme relevance
    hosting                   KEEP/CUT
    micro reactions           Golden Ticket
```

## Ella Live

Persistent session.

It watches the show **while it happens**.

## Ella Judge

Separate model evaluation.

It produces the authoritative result.

This means she can be hilariously reactive without corrupting the scientific judge.

---

# Ella doesn't even need to transcribe the comedian

This is a huge advantage.

We already know:

```text
the exact script
the exact WAV
every beat
every pause
set_time_ms
delivery.json
```

Therefore while Martin Lämp performs:

```text
t=0s
Ella receives setup text

t=7.2s
next beat

t=12.4s
punchline

t=12.9s
HAHA spike +480%

t=18.1s
next punchline bombs

t=23s
someone donates $100
```

Ella isn't trying to understand noisy stage audio.

She receives perfect structured perception.

That makes her **faster and smarter than a human host**.

---

# Build an `EllaSense` stream

EpisodeRoom should continuously send her compact context updates:

```json
{
  "performance": "martin-lamp-004",
  "set_time_ms": 18420,

  "beat": {
    "type": "punchline",
    "text": "..."
  },

  "audience": {
    "laugh_500ms": 93,
    "laugh_5s": 281,
    "groan_5s": 4,
    "reaction_velocity": 3.8
  },

  "stream": {
    "sentiment": 0.82,
    "top_comment": "THE LAMP LINE"
  },

  "pot": {
    "delta": 100
  }
}
```

Not 1,000 raw reaction events.

Cloudflare actually recommends batching high-frequency Durable Object messages every roughly **50–100ms** or by message count to reduce overhead. ([Cloudflare Docs][7])

Perfect for this.

---

# Ella needs three latency tiers

This is the architecture I'd build.

## Tier 0 — Reflex

Target:

```text
0–100ms
```

No LLM.

Examples:

```text
iris widens
looks at ChatGPT
desk flashes
small laugh
"oh."
"Jesus."
```

These are deterministic reactions to:

```text
massive laugh
total silence
$100 donation
WTF spike
ChatGPT score reveal
```

Have maybe 50 tiny pre-generated Ella sounds.

That makes her appear *instantly alive*.

---

# Tier 1 — Live intelligence

Target:

```text
~300–800ms perceived response
```

Persistent realtime model.

Two excellent candidates exist right now.

## Option A — OpenAI GPT-Realtime-2.1

The Realtime API is built for low-latency audio over WebRTC/WebSockets and supports:

* native speech-to-speech
* server VAD
* semantic VAD
* interruption
* tool calls
* streaming audio
* custom voices for eligible accounts

([OpenAI Platform][12])

It explicitly supports cancelling an ongoing response and clearing its output audio buffer. ([OpenAI Platform][13])

That's extremely useful:

```text
Ella:
"And what I liked about—"

STREAM:
+$500 DONATION

Ella stops.

"...well, apparently someone liked it more."
```

That interruption is the difference between an AI voice and a **character who is present**.

---

# Option B — Gemini 3.1 Flash Live

Also extremely compelling.

Google describes `gemini-3.1-flash-live-preview` as its low-latency audio-to-audio model specifically for realtime dialogue. ([Google AI for Developers][14])

Its Live API has:

```text
persistent WebSocket
audio input
text input
video/images
native audio output
function calling
interruptions
```

and Google recommends tiny **20–40ms audio chunks** for lowest latency. ([Google AI for Developers][15])

This should absolutely be benchmarked against OpenAI.

---

# But Ella's voice matters

You currently like:

```text
Edge TTS → Aria
```

That's fine for prototype.

But Edge TTS is not what I'd trust for the final host's live production voice.

For production there are three possibilities.

### 1. OpenAI Realtime custom Ella voice

Current Realtime supports:

```json
"voice": {"id": "voice_123"}
```

and OpenAI has a custom-voice creation API for eligible customers. ([OpenAI Platform][12])

That would be architecturally beautiful:

```text
Ella brain + Ella voice
inside one realtime model
```

Lowest plumbing complexity.

### 2. Fast text brain → ElevenLabs Flash

If we want total control over the voice:

```text
realtime text model
       ↓ tokens
Eleven Flash websocket
       ↓
Ella audio
```

Eleven's Flash models are around **75ms model inference**, and their WebSocket TTS is explicitly intended for streamed LLM output. ([ElevenLabs][16])

They now route API TTS across US/Netherlands/Singapore automatically as well. ([ElevenLabs][17])

That's probably the best provider-independent architecture.

### 3. Edge TTS

Keep it as:

```text
free/dev
pre-generated lines
fallback
```

not the production-critical realtime host.

---

# Tier 2 — Ella Judge

This can take:

```text
1–3 seconds
```

because television gives us cover.

Set ends:

```text
applause
camera goes panel wide
ChatGPT animation
Stream score calculating
```

while Ella's real judge model finishes.

And we can cheat even further.

## Score WHILE the set is happening

Don't wait until second 60.

At each beat:

```text
EllaJudgeAccumulator.update(...)
```

By the time the closer hits, the model already knows:

```text
material quality
delivery
laugh curve
theme fit
originality
performer history
```

Final call is basically:

```text
closer result + finalize
```

not:

```text
read entire minute from scratch
```

That could make Ella's verdict almost instant.

---

# The really good architecture

```text
                       EPISODE ROOM
                            │
                canonical show events
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
           ELLA SENSE               ML ARCHIVE
                │
      normalized live context
                │
       ┌────────┼──────────┐
       │        │          │
       ▼        ▼          ▼
    REFLEX    LIVE       JUDGE
    rules     session     model
    <100ms    <1 sec      deeper
       │        │          │
       │        ▼          │
       │    Ella Voice     │
       │        │          │
       └────────┼──────────┘
                ▼
            ELLA ACTION
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
     speak    gesture    verdict
       │        │         │
       ▼        ▼         ▼
                EpisodeRoom
                     │
                  Stage
```

Every Ella decision becomes an event too:

```json
{
  "type": "ella.action",
  "set_time_ms": 42188,
  "trigger": "audience_laugh_spike",
  "action": "look_at_chatgpt",
  "latency_ms": 37,
  "source": "reflex-v1"
}
```

That itself becomes training data.

---

# Ella can become genuinely frighteningly alive

Because she owns the stage, give her tools:

```text
cut_camera()
play_sting()
dim_lights()
spotlight(character)
look_at(chatgpt)
show_comment()
show_replay()
interrupt_chatgpt()
award_ticket()
end_set()
next_character()
```

Then her realtime model can literally operate the theatre.

So if a comedian says:

> “Ella couldn't organize a piss-up in a brewery.”

She can immediately:

```text
lights OFF
```

pause.

lights ON.

> “Continue.”

That's the mythology becoming mechanically real.

---

# I would make the infrastructure change like this

**Keep:**

```text
Cloudflare Worker
EpisodeRoom Durable Object
R2
Postgres
Three.js/VRM
OBS
Privy/x402
```

**Add:**

```text
Hyperdrive → make Postgres accessible cleanly from Workers
Cloudflare Stream → own-site broadcast/VOD
EllaSense
EllaReflex
EllaLive persistent session
EllaDialogue (implemented through agent-3d dialogue system)
EllaJudge accumulator
```

**Eventually add:**

```text
Cloudflare Realtime/WebRTC
```

for the ultra-low-latency interactive audience.

**Remove/de-emphasize:**

```text
D1 as duplicate business DB
Redis as realtime show authority
stateless Ella calls
```

The important shift is that **Ella becomes another live participant connected to EpisodeRoom**, just like Stage and Audience—not a backend function invoked after something happens.

That's the architecture that makes the central Ella orb idea actually true: **EpisodeRoom is her nervous system, the stage is her body, and the realtime model is her voice.**

[1]: https://developers.cloudflare.com/stream/stream-live/?utm_source=chatgpt.com "Stream live video · Cloudflare Stream docs"
[2]: https://developers.cloudflare.com/stream/stream-live/simulcasting/?utm_source=chatgpt.com "Stream live video · Cloudflare Stream docs"
[3]: https://developers.cloudflare.com/stream/pricing/?utm_source=chatgpt.com "Pricing · Cloudflare Stream docs"
[4]: https://developers.cloudflare.com/stream/?utm_source=chatgpt.com "Overview · Cloudflare Stream docs"
[5]: https://developers.cloudflare.com/hyperdrive/get-started/?utm_source=chatgpt.com "Getting started · Cloudflare Hyperdrive docs"
[6]: https://developers.cloudflare.com/r2/pricing/?utm_source=chatgpt.com "Pricing · Cloudflare R2 docs"
[7]: https://developers.cloudflare.com/durable-objects/best-practices/websockets/?utm_source=chatgpt.com "Use WebSockets · Cloudflare Durable Objects docs"
[8]: https://developers.cloudflare.com/stream/webrtc-beta/?utm_source=chatgpt.com "Ultra-low Latency with WebRTC · Cloudflare Stream docs"
[9]: https://developers.cloudflare.com/stream/stream-live/start-stream-live/?utm_source=chatgpt.com "Start a live stream · Cloudflare Stream docs"
[10]: https://developers.cloudflare.com/realtime/sfu/?utm_source=chatgpt.com "Overview · Cloudflare Realtime SFU docs"
[11]: https://developers.cloudflare.com/realtime/sfu/pricing/?utm_source=chatgpt.com "Pricing · Cloudflare Realtime SFU pricing"
[12]: https://platform.openai.com/docs/api-reference/realtime?lang=javascript&utm_source=chatgpt.com "Realtime | OpenAI API Reference"
[13]: https://platform.openai.com/docs/api-reference/realtime-client-events/conversation/item/create?utm_source=chatgpt.com "Client events | OpenAI Platform"
[14]: https://ai.google.dev/gemini-api/docs/models?authuser=002&utm_source=chatgpt.com "Models  |  Gemini API  |  Google AI for Developers"
[15]: https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk?utm_source=chatgpt.com "Get started with Gemini Live API using the Google GenAI SDK"
[16]: https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization?utm_source=chatgpt.com "Latency optimization | ElevenLabs Documentation"
[17]: https://elevenlabs.io/blog/text-to-speech-api-up-to-40-faster-globally?utm_source=chatgpt.com "Text to Speech API - Up To 40% Faster Globally"
