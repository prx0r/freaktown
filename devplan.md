# Freak Town Development Plan

> Two-track setup: Freaktown (experiments) → Killella (production runtime)
> Do not merge repos. Same versioned JSON formats only.

## Canonical Shared Contracts

```text
freaktown.bundle.v1    — character itself
freaktown.delivery.v1  — how text should be performed
freaktown.performance.v1 — sealed executable performance
freaktown.events.v1    — what actually happened
```

## Current Verdict

Backend architecture is surprisingly far along: event sourcing, Durable Objects, performance plans, motion language, TTS adapters, character bundles, delivery sequencing, sound generation, three judges.

**Main problem: integration.** No end-to-end production path exists.

## Execution Phases

### Phase A — Make the browser stage real
- Turn `apps/web` into the production frontend
- Install: vite, react, three, @pixiv/three-vrm, zod
- Build: /stage/:episodeId, /control/:episodeId, /live/:episodeId
- Stop developing frontend/index.html (legacy)

### Phase B — StageRuntime
- Refactor StageRenderer.ts into stage/ modules:
  - StageRuntime.ts, Scene.ts, Transport.ts, AudioBus.ts
  - ActorRuntime.ts, CameraDirector.ts, EventConsumer.ts, overlays/

### Phase C — Cameras
- 6 presets: WIDE_STAGE, COMIC_MEDIUM, COMIC_CLOSE, SIDE_STAGE, PANEL_WIDE, ELLA_CLOSE
- Keyboard control (1-6)
- Every cut generates camera.cut event

### Phase D — Actual Worker live room
- Wire EpisodeRoom into Wrangler
- Hibernation-safe WebSocket attachments
- Remove fake token validation

### Phase E — Remove duplicate realtime Python
- Mark backend/routes/audience.py WebSockets LEGACY
- FastAPI = HTTP control/generation API only

### Phase F — Remove D1 product duplication
- Worker owns live room state only
- Postgres owns durable domain/business/ML data

### Phase G — Immutable performance manifest
- All assets pre-generated before performance
- Show refuses to start unless performance.status == READY

### Phase H — Panel split
- Replace JudgePanel with: EllaEvaluator, EllaDecision, EllaDialogue, ChatGPTJudge, StreamAggregator
- No panel mean

### Phase I — Raw ML events
- Persist every audience/camera/judge/delivery event
- At show completion generate episode.json, events.ndjson, performances.json into R2

## Blockers to Fix First

### P0 — Stage not wired
- apps/web/package.json missing three, @pixiv/three-vrm, React, Vite
- frontend/index.html still says "Stage renders here"
- Production renderer unattached

### P0 — Two competing realtime architectures
- FastAPI WebSockets vs Cloudflare Durable Objects
- Pick: Cloudflare = canonical live runtime, FastAPI = control plane
- Delete/disable Python audience WebSocket once Worker path works

### P0 — EpisodeRoom not deployed
- Worker entrypoint doesn't export it
- wrangler.jsonc missing DO binding/export
- Fix (verified with `wrangler deploy --dry-run`): `durable_objects.bindings`
  + `migrations: [{ tag: "v1", new_classes: ["EpisodeRoom"] }]`
  (the declarative `exports` config is not accepted by wrangler.jsonc;
  migrations is the correct mechanism)
- Plus: `export { EpisodeRoom }`, `EPISODE_ROOM` in `Env`,
  `/live/:episodeId/{ws,state,command,stage-token}` routes proxying to
  `env.EPISODE_ROOM.getByName(episodeId)` ✅ DONE

### P0 — EpisodeRoom hibernation bugs
- In-memory Maps disappear on hibernation
- Use serializeAttachment() + getWebSockets()/tags
- Fix token.length > 10 fake auth
- Fix handlePuppeteerDialogue() missing await
- Fix first alarm not scheduled

### P0 — Two canonical databases
- Worker queries D1 for episodes/comedians/act_versions
- Postgres also has these
- Fix: Worker = live room state only, Postgres = everything else

### P0 — delivery.compose() audio format bug ✅ DONE
- Was concatenating provider MP3/WAV/OGG bytes as raw PCM. Now:
  provider audio → ffmpeg decode → canonical PCM16 mono 24kHz →
  exact silence insertion → valid WAV via stdlib wave.
- Verified: MP3 round-trip timing exact (3120ms = 1045+180+1045+850),
  silence-only path valid, empty score valid, HTTP route returns
  decodable WAV. ffmpeg binary required (raises loudly if missing).

## Performance Manifest Schema

```json
{
  "version": "freaktown.performance.v1",
  "performance_id": "...",
  "character_bundle_sha256": "...",
  "actor": { "slug": "...", "avatar_url": "...", "body_class": "humanoid-v1" },
  "audio": { "set_url": "...", "walkout_url": "...", "duration_ms": 59220 },
  "delivery": { "schema": "freaktown.delivery.v1", "sha256": "..." },
  "words": [],
  "motion": { "cues": [] }
}
```

## Live MVP

```
START SHOW → wide camera → walkout music → avatar enters
→ medium camera → 60s audio begins → lip sync
→ audience: HAHA/CLAP/CRICKETS → camera: 1-2-3-4
→ set ends → Ella evaluates → ChatGPT hallucinates → Stream locks
→ three score cards → Ella speaks → KEEP/CUT/GOLDEN TICKET
→ NEXT
```

## Deployment

```text
VPS: FastAPI + PostgreSQL + generation adapters
Cloudflare: Worker + EpisodeRoom DO + R2
Local: Chrome stage + OBS Browser Source (1920x1080, 60fps)
```

## Testing Requirements (Episode Zero blocking)

```
npm typecheck
frontend build
Python pytest
Worker DO tests
Playwright: stage loads, audio starts, transport moves, camera cuts, events recorded, reconnect works, score cards hidden before reveal
Audio: delivery composer produces valid WAV
Replay: given event log N, fresh StageRuntime renders same final state
Contracts: ShowPot compiles (verified vs real OZ) + Foundry invariant/
  fuzz tests required before ANY deploy:
  forge test --match-contract ShowPotInvariants covering:
  sum(contributions)==totalPot; shares sum to total; no claim before
  lock; no double claim/refund; only closer finalizes; refunds only
  pre-finalize to actual contributors
Payments: x402 402-then-settle flow against SDK models (no facilitator
  needed for 402/validation paths); facilitator verify/settle path
  requires FACILITATOR_URL + testnet funds in CI secrets
```

## Launchpad layer — WIRED (strategy.md, 2026-09-07)

Product framing adopted: Freak Town is an anonymous character launchpad.
The unit of virality is the Freak. Wired so far:

- `backend/services/clips/` — automatic content package per set
  (`freaktown.clips.v1`): full 16x9, TikTok-safe 9x16 (63-75s, set never
  cut), best-20s/40s peak-laugh windows, score-reveal, ella-roast,
  thumbnail anchor, SRT + JSON captions, ffmpeg cut-list. Verified exact.
- `backend/services/reputation/` — character records (W/L, best Ella /
  Stream / laugh share, regular rule v1: 3+ apps, 2+ KEEPs), pseudonymous
  creator codes (`creator_7F32`, sha256-opaque), leaderboard ranking,
  globally-numbered Golden Tickets.
- `backend/services/pot/` — THE POT as a pure fold over
  `pot.contribution` ShowEvents. No new tables; the log is the ledger.
  $0.00 is a valid state.
- `backend/routes/launchpad.py` — POST /v1/clips/plan (pure),
  GET /v1/characters/{slug}, GET /v1/leaderboard, GET /v1/creators/{code}
  (public viral surface), GET /v1/pot, POST /v1/pot/contribute (admin),
  POST /v1/tickets/issue (admin/Ella). Verified against real PG.
- EpisodeRoom: `tip.received` persisted show event (amount ≤ $500,
  140-char message). Payment capture belongs to FastAPI (fiat-first);
  the DO event is display + ML record.
- Python audience/stage WebSockets marked LEGACY (frozen, warn on
  connect). Removal gated on Worker deploy. Known defects documented
  in module docstrings, not fixed.

Still open from strategy.md: clip MP4 rendering job (ffmpeg cut-list
exists; needs the episode recording + runner), character social
distribution, Regular perks/revenue-share, creation challenges, IP
license terms (legal, before public submissions).

## devplan2 integration status (2026-09-08)

Product stack is now: Worker → EpisodeRoom → Stage/VRM → OBS → Rumble +
YouTube 4K60, Cloudflare Stream 1080p for freak.town/watch + VOD.
WebRTC/Realtime stays future (no recording/simulcast coexistence yet).

- R2 bucket ✅ standardized on freak-town-assets (media_store default,
  config, .env, wrangler binding) + drift-guard tests.
- Hyperdrive ⏳ binding + Env + accessor wired (placeholder id, same
  convention as D1/KV). Dashboard step required: create the Hyperdrive,
  put its id in wrangler.jsonc. D1 routes untouched until then —
  D1 holds edge-ephemeral only, no new business tables.
- EllaSense ✅ DO getSense() + GET /live/:ep/sense (~1Hz polling shape:
  phase/appearance/crowd/pot; set_time_ms null — only stage has clock).
- EllaReflex ✅ worker/ella/reflex.ts pure rules (spike/silence/$100
  tip/wtf/chatgpt-reveal → iris/stillness/flash/look) + 7 vitest.
- EllaLive ✅ session manager + FakeLiveTransport + provider_status
  (openai-realtime/gemini-live descriptors; no keys = honest not-ready).
  Voice routing decided: realtime custom voice OR text→Eleven Flash,
  edge-tts stays fallback.
- EllaJudge ✅ per-beat accumulator (rubric + laugh curve) with
  finalize; reactive banter structurally cannot touch it.
- Ella tools ✅ registry with implemented/planned split; command
  builders tested. ella.action contract both runtimes.
- OBS routing: 4K→YouTube+Rumble, 1080p→Stream (dashboard-created
  input; enable LL-HLS preferLowLatency). No code change — Stream
  inputs are provisioned, not committed.
- Redis: de-emphasized as show authority (DO owns live state);
  remains for queues/cache. No Redis pub/sub migration performed.
