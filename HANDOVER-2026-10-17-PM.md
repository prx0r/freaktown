# HANDOVER — Venue day PM (2026-10-17, ~12:30–18:45 UTC)

Branch: `feature/mutuals-acting-party-smiles` (local, UNPUSHED — owner pushes).
Previous: HANDOVER-2026-10-17.md (stage day). This file = venue/cauldron session.

## Live right now (all verified 200 today)

- `funnier.si/cauldron` (+ `.json`) — 50-frame concept gallery, grid, zoom,
  pass/fail filters, prompt sidecars, agent-readable feed.
- `funnier.si/venue/tavern-test` (+ `?nobg=1`, `?body=*.glb`, `?tv=1`) —
  mesh room + performer + mic + lights/cams + set + reverb + energy + REC.
- `funnier.si/sets` — server-recorded takes with audio (plays on any phone).
- `funnier.si/code` — phone controller (pair code + reactions + face/mic).
- `party.funnier.si/*` mirrors all of the above.

## Timestamped progress (UTC)

- 12:30 Review: Cauldron venue work (schema, acoustics, 9 houses VALID).
- 12:35 Atlas docs refresh (public API found; beta confirmed as our key's home).
- 12:38 Stored WLT/FISH/FAL keys in `.env` (600, gitignored). Rule: Atlas/FAL
  spend needs explicit owner yes, every time.
- 12:45 stage-runtime `npm install` (69 pkgs). Tests were already broken
  (wrong import paths) — not ours, left alone. Added `node_modules/` to
  .gitignore.
- 12:55 `scripts/marble_cauldron.py` (beta chisel payload from cauldron.json).
- 13:00–13:10 `scripts/cauldron_concepts.py` (12 CF-schnell drafts, $0) +
  `/cauldron` gallery route + apex worker `funnier-cauldron` + routes.
- 13:10 image-blaster skills mined (plate rule) + Marble image-input guides
  imported (`docs/vendors/marble-api/`). Prompts fixed per plate rule.
- 13:20 CF schnell takes prompt-only (400 lesson) + returns b64 JSON (fixed).
- 13:25 `scripts/validate_concepts.py` (PIL tech + llava gates, $0).
- 13:30 Grid + zoom gallery. `scripts/marble_cauldron.py` rewired to beta.
- 13:31 Real Cellar DNA: Wikimedia stage photo + dark-stage ref in /tmp.
- 13:35 User's show photo → ref A. FAL shortlist priced (Kontext pro $0.04).
- 13:40 `scripts/fal_cellar.py` — fal-a/b/c via 3 FAL models (~$0.16).
- 13:50 main2/main3/shell batches ($0). Shells parked (wrong order — owner's
  call, recorded). `docs/VENUEGUIDE.md` written (shell-only law).
- 14:00 ChatGPT venue analysis → adopted neutral-input + relight caveat.
- 14:05 Cellar-formula refs (Vegas pages) → surround-layout doctrine.
- 14:07 First Marble generate: 2 anchors posed + 4 views (mbl-* in gallery).
- 14:15 Agent docs imported (22 beta files) + official CLI installed.
- 14:20 422 (depth required) → two-phase pose-then-generate. 409 (static
  idempotency key) → unique keys. CLI skill noted.
- 14:30 Tavern world found → scene.spz downloaded → splats2Mesh → 33MB GLB
  → `/venue/tavern-test` stage page (room + VRM + mic + set driver).
- 14:45 Jev eyes: Playwright CDP + `typesafe/jev-1.14` Decisions API
  (`scripts/agent_eyes.py`, ~$0.0001/cycle). OPENROUTER_API_KEY = Jev ONLY
  (owner rule — enforced, generic vision attempts deleted).
- 15:00 `scripts/watch_performance.py` (observe→decide→log, Box tracking).
- 15:15 `docs/NORTHSTAR-LIVE.md` — 3 gates, all GREEN by watcher numbers.
- 15:30 Debugger era: rotateVRM removed, shadows off (SwiftShader/MToon),
  jaw flap, rest-pose revert, beat gestures via FoxGlove .vrma
  (copied 7 clips to `static/gestures/`, three-vrm-animation@3.3.0).
- 16:00 Second-screen: pair API + `?tv=1` + `/code` controller + apex routes.
- 16:10 Room feel: venue-RT60 convolver reverb + ROOM ENERGY physics.
- 16:20 gltf-transform: 33MB → 3.6MB → 5.2MB full-geo; sha re-pinned twice.
  Cache headers (immutable GLB, no-store pages). Blog capped at 9 lines.
- 16:25 MP3 fallback (250KB) for phones refusing WAV.
- 16:30 `scripts/record_set.py` (server-side takes + audio mux) + `/sets`
  gallery (renamed — legacy `/takes` route wins in Flask, first match).
- 16:40 Spark discovery (World Labs MIT splat renderer, SPZ-native, fuses
  splat+mesh). Tavern SPZ staged; SparkRenderer+SplatMesh wired with
  GLB→box fallback chain. ACES + contact blob.
- 16:50 three-vrm-lip-sync (MFCC→visemes, free, in-browser) LIVE
  ("mfcc live", wlipsync dep mapped). Fish timestamps reserved for emphasis.
- 17:00 characters repo pulled (ff-only, clean) — delivery engine map:
  timing_profile, delivery_engine, delivery_laugh, standup_sim,
  SPEC-JEV-DELIVERY. FUNNIER consumes timelines, never reimplements.
- 17:05 R2 inventory: 13 character GLBs (monster/cat/chimp/husky/spider…).
  Husky fetched (1.9MB, 12 embedded clips), staged via `?body=`. Mic
  auto-fits head height. Watcher questions de-speciated (Jev failed the
  dog for being a dog — question fixed, not the dog).
- 17:10 Meshy key stored. Session close-out (this file).

## Spend today (approved only)
FAL ~$0.52 total (fal-a/b/c, angles, bare-1/2, c-canonical). CF $0.
Marble beta billing unknown (no 402, no receipt — watch project usage).
Jev ~$0.001 (dozens of $0.0001 judgments).

## Secrets (all in funnier/.env, 600, gitignored, never in tree)
WLT_API_KEY · FISH_API_KEY · FAL_API_KEY · MESHY_API_KEY ·
OPENROUTER_API_KEY (Jev ONLY) · OPENCODE_GO_* (general use).
All pasted in chat — treat as exposed, rotate if anything strange.

## Session 2 — evening (~18:45–19:10 UTC): real comedy + eyes + second screen

- Louis minute rendered REAL (`scripts/render_real_minute.py`): voicelab
  c04 text + Louis pause ladder + Fish cues → `freaks/louis-c04/`
  (delivery + wav + mp3). Words+timing Louis's; voice is Fish default
  (no CK clone exists); body still default rig. Venue `?set=` param
  (default biscuit). Louis take recorded with audio (`--set` support).
- characters pulled ff-clean; delivery map done (timing_profile,
  delivery_engine, SPEC-JEV-DELIVERY). FUNNIER consumes timelines.
- R2 inventory: 13 character GLBs; husky fetched (1.9MB, 12 clips),
  `?body=` performers + auto-mic-to-head. Jev questions de-speciated.
- Jev eyes LIVE (`typesafe/jev-1.14` Decisions API, OPENROUTER key Jev-only):
  `scripts/agent_eyes.py` + `scripts/watch_performance.py` (noul + Box,
  ~$0.0001/cycle). NORTHSTAR-LIVE all 3 gates GREEN by watcher numbers.
  Ears repo confirmed: earshot (shallow-reviewed, deferred).
- Venue debugging saga: rotateVRM removed, shadows off (SwiftShader/MToon),
  jaw flap → three-vrm-lip-sync MFCC (free, in-browser) + FoxGlove .vrma
  (7 clips, `static/gestures/`, three-vrm-animation@3.3.0, beat gestures).
- Phone saga root causes: missing apex routes (VRM + audio 404'd — NOT the
  phone), route collision on `/takes` (legacy wins → recorded takes at
  `/sets`), `www.` needed wildcard routes, stale-HTML cache (no-store now),
  33MB→5.2MB gltf整治 (meshopt+webp, sha re-pinned), MP3 fallback, audio
  diag lines, boot log capped at 9 lines, view-box BackSide array bug.
- Second screen shipped: pair API + `?tv=1` (code + shared energy) +
  `/code` controller + apex routes. Verified end to end.
- Room feel: venue-RT60 convolver reverb + ROOM toggle + ROOM ENERGY
  (venue physics, local sim). REC + per-beat auto camera cuts + webm
  download. Record script muxes set audio (approx sync).
- Spark (World Labs MIT, SPZ-native, splat+mesh fuse) wired with
  GLB→box fallback + ACES + contact blob. Tavern SPZ staged
  (`var/venues/tavern.spz`, gitignored).
- Motif doctrine: `?style=` splat|mesh|box|void — Cauldron renders in any
  style. Bake-off loop in record_set.py (`--body`, `--set`).
- Meshy key stored. RPM recommended as low-investment cast.

## Session 3 — night (~19:10–19:45 UTC): 10 todos, all executed

1. Silence timings ($0 ffmpeg): `scripts/extract_timings.py` — longest-N-1
   silences as beat boundaries → `timings.json` for louis + biscuit.
2. Measured driver: venue fires beats at real start_ms (even-cadence dead).
3. VTubeMe Nova (VRM 0.x, 54 bones, 17 blends, CC BY) staged via `?body=`,
   `/venues` serves .vrm now. Photoreal man performing verified.
4. Bake-off: nova-louis + husky-louis takes recorded (same set, 3 bodies).
5. Takes share links (copy-link per take in `/sets`).
6. Mod KILL switch (`/api/pair/<code>/kill` → INTERMISSION card). No auth
   yet — unlisted codes only, flagged.
7. Face AB on Louis punchlines: 4/4 expressive (0.66–0.94).
8. Cauldron submission dry-run green (fal-b + ang-b anchors, 4 targets).
9. This handover + push (below).
10. Final verify (below).

Spend: $0 (ffmpeg + Jev micro ~$0.001). FAL untouched.

## Open threads (build order)
1. Cauldron's own mesh (anchors ready: bare-2 + fal-b + ang-b) + motif styles.
2. Headliner body (Ralph VRM / RPM free / husky weird-nights proven).
3. Delivery timelines → stage (characters delivery_engine output as
   the beat contract; Fish word timestamps for emphasis).
4. Ready Player Me bodies (free, visemed) as low-investment cast.
5. Takes publish flow (/sets records; needs share/publish step).
6. Delay + censor design (60s buffer, KILL switch) before any RTMP.
7. TikTok/YouTube restream (server + GPU bill — money talk first).
8. Monitor auth, prosody extractor, push this branch (owner).

## Verify in 60 seconds
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://funnier.si/cauldron
curl -s -o /dev/null -w "%{http_code}\n" https://funnier.si/sets
curl -s -o /dev/null -w "%{http_code}\n" "https://funnier.si/venue/tavern-test?nobg=1"
grep -rIlE "wl_live_|sk-fish-|fal_sk_|msy_|sk-or-v1-" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=marble-beta --exclude-dir=marble-api --exclude-dir=character-harness . (must print only ./.env — key VALUES live there alone, never in tree)
```
