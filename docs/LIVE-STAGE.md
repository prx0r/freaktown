# Live stage — three.js stage + control + room (2026-10-22)

A character performs a sealed set **live in the browser**: real cameras,
WebAudio clock, plan-driven mouth, body and face, crowd reactions. Blender
stays for offline sealed renders (`scripts/render_set.py`); this is the
realtime lane. Extending it: [`LIVE-STAGE-EXTENDING.md`](LIVE-STAGE-EXTENDING.md).

**Sets (2026-10-22):** besides the comedy club there are a news studio, a podcast and a
poker table (`set.load {setId}`; Set panel in /control; human poker seat at
`/play/:ep/seat/4`). See LIVE-STAGE-EXTENDING.md §8 "Adding a set".

**Faces (2026-10-22, live-face):** one face layer for VRM/GLB/BASIC — ARKit-52 blendshapes,
Oculus→VRM visemes, harness emotion vocabulary, affect servo, `face.expression /
face.blendshapes / face.affect` events, measured `words.json` + `acting.json` for sealed sets.
See LIVE-STAGE-EXTENDING.md §10.

```text
 /control ──command()──►  LiveTransport  ──► room (persist → broadcast) ──► /stage
 (operator)              ├─ LocalTransport  (BroadcastChannel + localStorage, LocalRoom)
                         └─ EpisodeRoomTransport (edge/worker EpisodeRoom DO, websocket + POST)
                                                                   │
                                     StageEventExecutor ◄──────────┘ events only
                                            │
          StageRuntime: Transport (WebAudio clock) · AvatarDriver (VRM → GLB → BASIC)
          · MouthTrack · Performer · CameraDirector · StageSet · SfxSynth
```

## Pieces

| Where | What |
|---|---|
| `packages/contracts` (`@freaktown/contracts`) | wire types (`ShowEventV1`, cameras, `PerformancePlan`, `WordTiming`, `MotionCue`, `CameraCue`), `validateCameraCut`, **`applyEpisodeEvent`** — the one state reducer used by both the DO and LocalRoom |
| `packages/stage-runtime` | the renderer + executor + transports + set adapter (README there) |
| `apps/live` | Vite + React: `/control/:ep`, `/stage/:ep`, `/live/:ep` (audience), `/`; demo sets in `public/sets/` |
| `edge/worker` | EpisodeRoom DO (unchanged semantics; now calls the shared reducer); ws forwarding fixed; `LIVE_DEV_OPEN` for local dev |

### Invariants kept

- **Control never touches the stage.** Every button is `transport.command()`
  → room persists → broadcasts → `StageEventExecutor` acts. Plan camera cues
  live *inside* the preloaded plan, so replaying the log reproduces every cut.
- **One clock.** The set wav on the WebAudio `Transport`; cues, mouth, cameras
  and captions all read `transport.currentTimeMs`.
- **Channels don't clear each other.** mouth = `MouthTrack` (or analyser),
  face = `face.*` cues, blink = own timer, body = idle + gestures.
- **Never a fake mouth.** GLBs report `mouthMode: none` when the bytes have no
  morphs/jaw; they get body bob only.
- **Replay-safe.** Events execute serially in seq order; a late stage replays the
  log, catches up on a running set (`playFrom(elapsed)`), and never re-ACKs a
  `performance.ready` already in the log.

## What performs

| Character (demo set) | Body | Mouth | Face | Body motion |
|---|---|---|---|---|
| Captain Ata Ashcroft (`sets/captain-ata-ashcroft`) | VRM `static/avatars/default-v1.vrm` (pixiv VRM1 sample; meta licence `vrm.dev/licenses/1.0`) | **yes** — VRM visemes `aa ih ou ee oh` from word vowels, gated by the wav envelope | VRM `happy/angry/sad/surprised/relaxed` + `blink` | humanoid bones: breath, sway, nods, talking hands, gestures, lean |
| The Algorithm (`sets/the-algorithm`) | BASIC procedural (robot variant) | **yes** — jaw + mouth shape (ours by construction) | brows + mouth width | same Performer, primitive rig |
| any `assets/character-meshes` GLB | GLB (sniffed) | only if it has visemes / `jawOpen`·`mouthOpen` morphs / a jaw bone | ARKit-ish morphs if present | bones if found, else whole-body puppet bob |

The 13 character-mesh GLBs are **not in git** (R2 only; `scripts/fetch_r2_media.py --meshes`
→ `data/character-meshes/`, served by the dev server at `/meshes/<file>`). None were
available in this sandbox, so no GLB mouth was verified. Pick "avatar" in /control or
put `avatar_url: "meshes/<file>.glb"` in `public/sets/index.json`.

Demo sets were generated with `scripts/build_set.py --character pog.<id>` (edge-TTS, $0);
`set.wav` re-encoded to 64 kbps mono `set.mp3` (~0.5 MB each).

## Cameras

Presets live in `CameraDirector.ts` (names from the contract). The set adapter
schedules: `WIDE_STAGE` open → `COMIC_MEDIUM` on the set-up → `SIDE_STAGE` /
`COMIC_MEDIUM` alternating on escalations → `COMIC_CLOSE` on the **last sentence of
each punchline** (close-ups punchline-only, per P0) → `WIDE_STAGE` for the laugh/out.
Min 1.2 s between cuts. Operator cuts (`camera.cut`, keys 1–4 in /control) override
at any time. Portrait screens widen the lens automatically. Also available:
`PANEL_WIDE`, `ELLA_CLOSE`, `CHATGPT_CLOSE`, `STREAM_CLOSE`.

## Run locally

```bash
npm install                      # repo root (npm workspaces)
npm run dev                      # http://localhost:5173/control/demo + /stage/demo
npm test                         # vitest: contracts/runtime/adapter/transports/edge (79)
npm run build                    # typecheck + apps/live/dist (static)
```

Open `/control/demo` and `/stage/demo` in two tabs of the same browser (local
transport = same origin). Press **Start show**. Stage flags: `?debug=1`
(telemetry), `?captions=0`, `?quality=low` (half-res, no shadows),
`?cpuskin=1` (CPU skinning for GPUs without vertex texture fetch),
`?capture=1` (frame-stepped capture), `?transport=room&token=…`.
Mobile Safari: first tap unlocks audio ("TAP TO ENABLE AUDIO").

### Against the EpisodeRoom (Cloudflare, local only)

```bash
npm run build
cd edge && npm ci && cp .dev.vars.example .dev.vars     # LIVE_DEV_OPEN=1, dev secret
npx wrangler dev --config wrangler.jsonc --assets ../apps/live/dist --local --port 8787
# http://127.0.0.1:8787/control/demo?transport=room → "Mint stage link" → open it
ROOM_URL=http://127.0.0.1:8787 npm run test:e2e -- e2e/room.spec.ts
```

`LIVE_DEV_OPEN=1` lets `/command` and `/stage-token` skip admin auth **only when set
in `.dev.vars`**; unset (prod) → normal Privy/API-key auth. Stage tokens are still
HMAC-verified by the DO (a forged token is rejected — covered by the room test).

### e2e (Playwright, headless)

```bash
npm run build && cd apps/live
CHROMIUM_PATH=/usr/bin/chromium NO_PROXY=127.0.0.1 npx playwright test
node e2e/capture.mjs captain-ata-ashcroft 33000 43000 25 /tmp/frames 1280x720 cpuskin=1
ffmpeg -framerate 25 -i /tmp/frames/f_%05d.jpg -ss 33 -t 10 -i public/sets/captain-ata-ashcroft/set.mp3 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest stage_demo.mp4
```

linux-arm64 has no Playwright-managed Chrome: install `chromium` and set
`CHROMIUM_PATH`. SwiftShader (software GL) **loses the WebGL context on three's
bone/morph textures**, so headless runs use `?cpuskin=1&quality=low`; real GPUs
don't need either. Hidden tabs throttle rAF — the tests `bringToFront()` the stage.

## Deploy (owner — nothing was deployed)

Build output is static (`apps/live/dist`, ~13 MB incl. the 10.7 MB VRM).

**A. Flask box at `funnier.si/perform/live`** (local transport works with zero
backend; for multi-device shows point it at the worker room):

```bash
LIVE_BASE=/perform/live/ npm run build          # optional: VITE_LIVE_TRANSPORT=room VITE_LIVE_ROOM_ORIGIN=https://<worker-host>
rsync -a apps/live/dist/ box:/srv/freaktown/live/
```

Caddy (reload with `caddy reload`, never systemctl):

```caddy
handle_path /perform/live/* {
    root * /srv/freaktown/live
    try_files {path} /index.html
    file_server
}
```

The `funnier-web` / `freaktown-perform` worker must pass `/perform/live/*` through
to the box (it already proxies `/perform`); make sure the funnier skin rewrite
skips this path (it is a SPA, not a Flask page).

**B. Cloudflare Worker assets** (`edge/wrangler.jsonc` serves `edge/dist` with SPA
fallback, same origin as the EpisodeRoom → `?transport=room` just works):

```bash
npm run build && rm -rf edge/dist && cp -r apps/live/dist edge/dist
cd edge && npx wrangler secret put STAGE_TOKEN_SECRET && npx wrangler deploy
```

Note: `wrangler.jsonc` has an `"env": { "PRIVY_APP_ID": … }` block that wrangler
reads as *environment names*, not vars — move those to `"vars"`/secrets before
relying on them in prod. `LIVE_DEV_OPEN` must never be set in prod.

## What's left

- **Box `/api/perform` integration**: the catalog is static (`public/sets/index.json`).
  Next: a box endpoint listing sealed sets (`data/p0/*`, takes) with `set_url`/`audio_url`,
  and control fetching it instead; `performance.preload` already accepts any `set_url`.
- **Real word timings**: the adapter now prefers a measured `words.json` (live-face);
  still to do: capture edge-TTS `WordBoundary` events in `build_set.py` to write it. Rhubarb `mouth_cues_rhubarb.json` could map to visemes too.
- **GLB cast**: fetch the meshes, sniff (`face_profiles`), add `BODY_CATALOG` entries,
  verify licences; confirm which actually have morphs/jaw.
- **Auto-director from the crowd**: cut to WIDE on `crowd.update` laugh spikes
  (needs the DO to broadcast aggregates to the stage role, today audience-only).
- **Catch-up ignores pauses** taken before a late stage joined.
- `/stage-ws` (`ThreeWsStagePage`) is parked: its `<agent-3d>` component wasn't carried
  over from killella; excluded from the build.
- Sound bank: `SfxSynth` is a procedural stand-in for real crowd samples.
- Bundle is one 1 MB chunk (three + vrm); split if load time matters.
