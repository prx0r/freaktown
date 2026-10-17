# STATUS — freaktown honest state (2026-10-16)

Read this first. Everything else is detail. This file is the anti-mess:
vision, what's done, what's not, what's theatre, what's next.

## Vision (one paragraph)

Freaktown is the comedy party stage: friends on phones play fast joke games
(freeze-night, quip, roast, draw-guess) while a theory-driven comedy engine
(pregates → director → delivery, callback economy, vote weights, affect
servo) makes the funny legible and re-playable. Improv canon
(`/root/improv/docs/`) is the design authority; `party.py` is the playable
slice; the lab is the instrument bench. Win = a room of humans laughs,
bots fill seats, every point traces to a rule you can read.

## What's DONE (verified against code, not claims)

- Party MVP live on-box: `party.py` freeze-night 7 rounds (prompt / ritual /
  wheel / last-lash), 11 quip decks (normal/inverted/liar + truth flags),
  5 ballot types, callback ×1.5 once per event, wheel re-spin, Last-Lash
  spread-3 triple pool, host lock/start/advance/bots/deck API, phone
  controller + stage views. Commit `4cfe7c3`.
- Bots for freeze-night (`_fz_bots_act`) + quip (`_qc_bots_act`): solo and
  all-bot nights complete, score, archive, crown. Proven by
  `test_solo_night.py` + `test_allbots.py`.
- Tech lab: `lab.py` `/party/lab` + 5 rigs + `POST /party/prop/validate`
  (closed op vocab). Proven by `test_tech_lab.py`.
- Canon written: `PARTY-FORMATS.md` (M1–M12, formats #1–#34), `ENGINES.md`
  (E1–E12), `MVP-FREEZE-NIGHT-V1.md` in `/root/improv/docs/`.
- Service healthy: systemd `freaktown.service` active, `:8090` listening,
  on-box `/play` 200, public `https://party.funnier.si/play` 200.
- Controller fix (2026-10-16): callback textarea + I-CAUGHT-THAT button wired
  to the pre-existing server API (`kind=entry+callback`, `kind=caught`).
- STONE FACE (2026-10-16): new mode `stone-face` (canon M1 / #7). Phones
  confess one funny-true info, room assembles a set weaving every confession,
  set plays line by line, I-CRACKED button knocks you out of the survivor
  pool, survivors +3. Bots confess + crack. Proven by `test_stone_face.py`
  (33 checks). HONEST LIMITS: set is template-assembled ($0, no LLM call);
  cracks are self-reported taps; `smile_detected` accepted for the future E1
  webcam referee but nothing produces it yet.

## What's NOT done (open threads, no owner needed for code ones)

1. Bots for roast-relay + freaktionary (no driver; solo impossible there).
2. Host pacing: open/reveal buttons, reject UI (API exists, no button),
   wheel-spin button (auto today), roast-target input (API accepts, stage
   can't send), timer-extend, family filter, moderation.
3. Callback anti-spam: 2nd invoke should pay half, pure repeat zero. Code
   returns 1.0 for repeats — no half, no judge tap.
4. Vote economy: affect-servo weights computed but never applied; no
   People's Champ second electorate, no cheer/boo, no heckler doubles,
   no JINX, no speed-weighted buzzer.
5. Game-pack loader: `party.py` never reads
   `game-packs/freeze-night-v1.freak-game.json`. Drift: min 3 vs 4, phases
   don't match (no SCENE/UNFREEZE/HALFTIME/FINAL/CROWNING), performers
   all-players vs 3/2, 8-seg wheel vs canon 12, 90/60s vs 600/300s.
6. Comedy wiring: `comedy/` (belief/corpus/director/evaluator/gates/rhythms)
   has zero imports in `party.py`. No pregates, no vetoes, no priors.
7. Missing canon: M3 COURT, M4 DUB-OFF, M5 KING-OF-HILL,
   M6 LAST-JESTER, M8 MAFIA, M10 HEADBANDZ, M11 SOUNDTRACK, M12 JOKERS
   (M1 STONE-FACE shipped 2026-10-16 — template set, self-report cracks);
   formats #7 smile, #8 ppt-karaoke, #9 two-headed, #11 genre-swap, #15 body
   relay, #20–#26 music, #27–#34 voice; E4 music absent; E8 secret-role absent.
8. Voice: freeze-night has no TTS call; only roast-relay uses edge-tts.
   Canon demands Fish `s2.1-pro-free` everywhere — mismatch unresolved.
9. Ritual is SAY-IT only (canon: ACT-IT/SAY-IT/BE-IT), victim is rotation
   (canon: shuffled assign), dub has no clip library, nonsense has no rater.
10. Game truth boundary: docs say pogtown owns it; `party.py` reimplements
    it. Unresolved — treat as product-UX-for-now, flag before scaling.

## What's THEATRE (looks done, isn't — verify before citing)

- "Comedy engine drives the game" — false. `grep comedy party.py` = nothing.
- "Game-pack driven" — false. Pack exists, loader doesn't.
- "Affect/smile/props integrated" — false. Lab-only; tallies are raw counts.
- "www.funnier.si/party live (200 verified)" — stale. Currently 404s;
  live public URL is `https://party.funnier.si/play`.
- "`test_jev_images` 9 / `test_affect_parity` 3" — files not in tree.
- "46/47 contract, 1 env fail" — stale counts; suites changed, interpreters
  changed (venv → system python). Run current commands before quoting.
- "Latest handover 09-12" (AGENTS.md + docs/README said this) — false;
  10-16 is latest. Fixed in AGENTS.md 2026-10-16.
- "Main frozen / staged-clean" — false since 09-12; `trial/avatar-flow`
  merged (`352c3e7`, +16k), party MVP committed (`4cfe7c3`).

## Needs HUMAN (do not attempt autonomously)

Secrets/keys: rotate chat-pasted CF token + R2 pair + Atlas `atk` + HF token
+ GH PAT (deploy key); vault `member` grant; Kaggle `HF_TOKEN` attach to both
kernels; HF gated accepts (Qwen3-TTS CustomVoice/Base, stable-audio-open);
`WLT_API_KEY`; LiveKit Cloud + Qwen/DashScope; three.ws/MetaPerson accounts.
Money ($0 rule): Tripo C02 $0.55 + C03 $0.50, SkinTokens 24GB GPU, GPU box
(~300MB, NOT on this box — disk pressure), hero Cycles 1/night max,
Jev-images ~$0.0001/call + OpenRouter model CONFIRM. Publish/laugh: never
push (owner pushes), retire v1 only after human confirms v3s, sealed stays
sealed / drafts stay drafts until human laughs, `human_laughter` null until
≥1 eligible view, playtests (dad mirrored? old-phone chug? badger framing?),
`www` pointer sign-off, `chatgpt-right` rename, `pog.pet` DNS, `~/qp` purpose.
Ops: `caddy reload` only (unit sandbox broken), UFW 22+80+8090, kill by exact
PID never pattern-kill.

## High-value NEXT (autonomous order)

1. Roast + freaktionary bots (unblocks solo testing everywhere).
2. Host pacing buttons (open/reveal/reject/spin/target/timer).
3. Callback anti-spam + vote-weight application (scoring honesty).
4. Game-pack loader + drift fix (single source of truth).
5. Comedy pregate wiring (first real engine-in-loop point).
6. One new text-only deck (genre-swap or try-not-to-smile — cheap proof
   the canon→deck pipeline flows).

## Harness integration (2026-10-16, feature branch)

Branch `feature/mutuals-acting-party-smiles` (local, unpushed): applied
`freaktown-harness-integration.zip` from R2 `stallshark` via its installer
(anchors `--check` passed first). Adds: `harness_beats` acting overlay on
sealed manifests (`mutuals-beats/v1`, delivery.v1 untouched), embedded-clip
gesture playback in `StageRuntime.ts`, host-token `/party/<code>/harness`
relay + acting caption, opt-in smile Boolean (`smiling:true`, 3s cooldown,
never scored/logged), free `/party/acting/preview`. Proven: 5+4 unit OK,
190 sim checks + contract 47/47 green, `git diff --check` clean. Honest
limits (from its README): no 3D party avatar yet, gestures need clips in
the GLB, smile accuracy unguaranteed, no paid calls in installer/preview.
R2 creds used memory-only + shredded; the fresh `icy-snow` token was pasted
in chat — delete it there once done.

Implemented end-to-end 2026-10-17 (same branch): `freaktown-party`
extension installed at `character-harness/extensions/freaktown-party`
(operator adds 2 lines to their character yaml AFTER director + sets
`FREAKTOWN_PARTY_ENDPOINT`/`HOST_TOKEN` in the clone's gitignored `.env`;
foxglove left pristine so upstream `npm test` stays 132/132). Proven
without Kaigen: `npm run typecheck` clean, checker grades the extension
(check-clean with env, explicit fill-in error without), relay POSTs
sentence+beats non-blocking (proof script `/tmp/prove_party_ext.mjs`).
Python live: `/party/acting/preview` deterministic (span resolves to
measured `start_ms`, misalignment rejected), `/party/<code>/harness`
host-authed + vocab-enforced, smile boolean-only + 3s cooldown + never
scored/leave-view. Service restarted: box `/play` 200, preview live,
public `party.funnier.si/play` 200. Deliberately NOT done: separate R2
motion loading, 3D party avatar layer, streamed-audio shared clock
(patch's stated limits). No-Kaigen rule: Kaigen is ONLY the native
player binary — everything else (director, rig prepare, relay, stage)
runs on Node/Python + your Three.js renderer.

## OpenCode Go + mimo-v2.5 (2026-10-17)

`.env` (600, gitignored) holds `OPENCODE_GO_API_KEY` + model pin
`mimo-v2.5`. Verified live: models list contains mimo-v2.5; chat works at
`https://opencode.ai/inference/go/openai/v1/chat/completions` with
`x-opencode-session` + own UA (without the session header Go refuses with
`MissingSessionID` — that error means routing, not a bad key). Director
proof: mimo staged "The humans were the resources." → neutral setup +
deadpan/push-in punchline → preview compiled to `face.deadpan` cues +
`COMIC_CLOSE` on measured offsets. Key was pasted in chat — rotate at
opencode.ai if anything looks off. RESOLVED 2026-10-17: the `Go subscription required` errors were this box's
persistent shell shadowing `.env` with a platform key (wrong account) plus
a stale base URL — the owner's key + inference endpoint work (mimo live,
3/4 semantic tests green; the 1 miss is mimo over-confident on an ambiguous
line, a calibration quirk). Lesson: repo `.env` now overrides inherited env
in our scripts; never trust the ambient shell for keys. To point a harness character at it:
`model: {base_url: https://opencode.ai/inference/go/openai/v1/chat/completions,
api_key_env: OPENCODE_GO_API_KEY, model: mimo-v2.5}` in its director.yaml
(not applied to vendored foxglove — operator change, keeps `npm test` green).

## Theatre audit — party x harness (all executed, 2026-10-17)

- preview compiles beats→cues on measured offsets: REAL (live, incl.
  mimo-staged beats; misalignment rejected).
- harness relay → stage clients: REAL (`character.act` in `?once=1`
  events; bad token 403, bad vocab 400, lobby-room 409).
- smile boolean → room event, cooldown, never scored/never in view:
  REAL (accepted, double-tap 429, non-boolean 400).
- controller smile toggle + referee script served: REAL (on `/play`).
- gesture clip playback in StageRuntime: CODE-WIRED, visually UNPROVEN
  (needs a prepared VRM with baked clips + a browser; no such asset yet).
- `neutral` beat → `face.deadpan` action: DELIBERATE (deadpan IS the
  neutral comedy face; stage renders it as `neutral` expression).
- SSE `curl -N` "missing" relay: TEST-ERROR (stream is snapshot+replay,
  clients resume via last_seq — `?once=1` proves delivery).

## Recent upstream implemented (2026-10-17, characters ce2f209+)

- REAL laugh heat: `/api/perform/<slug>/heat` serves characters'
  `delivery_aware_model.pkl` (AUC 0.654 LOO) via `.venv-heat` sidecar
  (numpy2/sklearn — system python can't unpickle it). 17/21 bundles score
  from measured offsets + set.wav energy; rest fall back to heuristic-v0
  (labeled per beat in `src`). Model means (~0.3) sit near the empirical
  5702-event laugh rate 0.237. prosody200-clean (0.862) NOT portable:
  feature defs + training data live only on /home/box.
- Semantic interpreter ported to Go/mimo (`scripts/interpret_joke.py`,
  same prompt/mechanisms/schema, curl transport — Go fingerprint-filters
  urllib) — 3/4 semantic tests PASS live on mimo-v2.5. Upstream uses
  OpenRouter+Qwen; ours never touches OpenRouter per owner rule.
- /perform audience stage (2026-10-17): entrance overlay (comedian comes
  out, walkout sting plays when the bundle has one — 3 do), TAP FOR
  SHOWTIME starts the set, reaction bar fixed at the bottom with haha 😄 /
  HAHAHA 🤣 / clap 👏 / cheer 🎉 / boo 👎 — tappable any time, even during
  the entrance. `/api/react` accepts the new types (logged with set_time_ms
  for laugh-curve training); HAHAHA counts ×3 in the finale verdict.
- Crowd bed (2026-10-17): `/api/perform/<slug>/crowd.wav` renders real CC0
  laugh clips (characters' comedy-room SFX) at heat moments, gain by p,
  applause swell at close — starts with the set at low volume. Verdict on
  the new Realtime Laughter Engine: its renderer/extractor are portable and
  good (bed built on that pattern), but its `_predict_model` feeds the
  0.862 model EIGHT ZEROED features ("we don't have exact mapping") — that
  path does NOT inherit the AUC. Our heat stays on delivery-aware (real
  features) until upstream ships the true prosody extractor.
- comedy-room personas: skimmed, deferred to party-bot work.
- A/B + agent audience (2026-10-17): rooms take `?crowd=0` (bed off,
  control) with the condition logged on every reaction (`cond` passthrough
  on /api/react). `scripts/agent_audience.py` sits in as an agent-native
  audience member: pulls heat, paces the set clock (or --fast), judges each
  beat with mimo (mechanism × confidence × heat rule, reasoning printed),
  posts laughs with true set_time_ms. Demo: 2 runs on Cathy, silent through
  setups, laughed only at the hot late-set beats (2 haha + 2 hahaha, all
  logged). Honest limits: the agent can't hear the bed (negative control
  for A/B, not a bed judge); truncations fail loudly with one retry. Review
  note: their A/B/C experiment scores ~0.51 AUC on 5702 events (chance) —
  event-level prediction is unsolved; our segment-level heat stands.
- Laugh delay harness (2026-10-17): `scripts/agent_laugh.py` — agents laugh
  when humans would: onset = beat END + 250ms base + (1-confidence)×900ms
  comprehension + seeded jitter − 150ms contagion when the room is warm
  (warmth boosts P by 0.08); HAHAHA arrives as a 2-post burst 900ms apart.
  Stamps carry the laugh moment, never the beat start. Demo: onsets
  +179–607ms, contagion visibly shortening delays run-over-run.
- Face-tracked audience (2026-10-17): perform rooms have opt-in 📷 TRACK MY
  FACE — browser-local TF.js calibration (same referee as party lab), only
  boolean smile moments leave the device (3s client cooldown, logged with
  set_time_ms + cond like any reaction). Finale renders YOUR FACE vs
  PREDICTED HEAT: your smile timestamps bucketed per beat against the heat
  strip. Privacy: explicit opt-in, stop button kills stream + model, no
  frames/probabilities uploaded, /f/ player untouched.
- Stage monitor (2026-10-17): `/perform/<slug>/monitor` is the comedian's
  view — live audience faces (WebRTC, performer as hub, Google STUN, small
  rooms) + glow pips for smile-only crowd + live reaction feed. Audience
  joins it with 📡 APPEAR (SECOND opt-in after tracking; tracking alone
  never shows your face). Signaling (`/signal`: offer/answer/ice/bye,
  capped, in-memory, never logged) + presence heartbeats (20s prune) are tiny
  Flask endpoints, no SFU, no recording code anywhere. Honest limits:
  no LiveKit (keys never landed), mesh suits ≤6 faces, monitor has no auth
  yet (unlisted slugs only).
- Live feedback loop (2026-10-17): rooms have 🎙 MIC LAUGHS (opt-in,
  WebAudio energy-burst HEURISTIC — labeled approximate in the UI, booleans
  only, `src:'mic'` logged so mic laughs stay separable from button taps).
  The monitor now shows ROOM ENERGY: trailing-15s meter + 🔥/🙂/🍅 verdict
  + per-type split, fed by the same boolean stream. The performer feels the
  room breathe: faces, pips, taps, mic laughs, one meter.
- Decaying hot-bar + KILLED (2026-10-17): monitor heat runs characters'
  real CrowdState dynamics (×0.88/event, +0.15/laugh cap 1.0, contagion ±1
  cap 5) plus wall-clock bleed so silence visibly cools the room. KILLED 💀
  is definitive and rare: `/api/perform/<slug>/verdict` requires energy ≥12
  AND ≥50% beat coverage AND ≥3 distinct tappers AND ≤1 boo, counted over
  the last 7 days only. Proven: 12× hahaha from one fan = NOT killed.
  Creators log server-side only, never leak to the feed.
- KILLED as audience STATE (2026-10-17, the guitar-hero rule): the room is
  a physics engine with RESISTANCE R (0..1, starts 0.5 cold). Laughs melt
  it (R−0.06 each, floor 0); boos rebuild it (R+0.10, cap 1); silence
  stiffens it (+0.01/10s). Heat gained per laugh is scaled by openness:
  +0.15/(1+R) — a cold room is genuinely hard to warm, a killed room stays
  easy (hysteresis). Live states: COLD (heat<0.3) → WARM (≥0.3) → HOT
  (≥0.6) → KILLED-live (≥0.85); each step down needs heat 0.15 lower than
  the step up took, so states flicker less than the meter. The 💀 badge
  stays the certified server verdict; the live KILLED state is the room
  telling you it's there before the paperwork lands.

## /perform live stage (2026-10-17)

`GET /perform` (tonight's bill, 21 stage-ready sets) + `GET /perform/<slug>`
(live room: canonical watch player + LIVE banner + predicted-heat strip +
finale verdict + next act) + `GET /api/perform/<slug>/heat` (per-beat
p_laugh contract for the future real laugh model). Shares all freaktown
logic (bundles, delivery spans, avatar bodies, /api/react laugh logging);
laugh-sim is HEURISTIC_V0 (type prior × position ramp, characters'
0.55/0.35 thresholds) — the heat endpoint is the swap-in point for
/characters' retrained laugh model (AUC ~0.55-0.65 upstream). Live at
`party.funnier.si/perform` (Caddy, zero infra) AND `www.funnier.si/perform`
(new `freaktown-perform` worker + zone route; existing funnier-web
untouched).

Performed avatar (2026-10-17): `/api/perform/<slug>/acting` derives a
sorted acting timeline (expression/gesture/look/hold/camera) from
delivery.json + measured offsets + VIBE_PROFILES (punchline_hold 450–1100ms
per vibe, seeded gestures, push-in on punchlines/closers). Perform rooms
drive the avatar on the audio clock: beat expressions via `__vrmFace`,
gesture pops, look shifts, spotlight holds, camera leans — portrait-CSS
physicality for every freak, VRM passthrough when a body is loaded. /f/
player untouched (verified: no perform driver in its HTML). Swap-in point
for characters' jev_loop delivery profiles documented on the endpoint. Upstream review: /root/characters is canonical (characters2
stale); remote has new laugh-train commits we haven't pulled. ghp token
pasted in chat was NEVER used (repos public) — rotate it.

## Realtime stack verdict (2026-10-17, researched)

- Faces are NOT VR: MediaPipe Tasks-Vision (52 blendshapes) + three-vrm in
  the browser, all client-side (RECORD mode already does this).
- LiveKit is the ecosystem winner IF we need it: rooms + voice + data
  channels + 16 avatar plugins (incl. bitHuman + Runway, both already in
  NORTHSTAR). Needs Cloud keys (open task) or self-host. Key pattern
  (IntelliVerseX): game logic stays on our Flask, voice on LiveKit,
  blendshapes as DATA not video — i.e. APPEAR could send face params, not
  faces. Paid avatar-video APIs (FaceMode/Ojin/Spatatius/Akool) ruled out
  ($0 rule). Nakama skipped: our slow-turn games don't need tick authority.
- Mutuals leads: protocol.md beat wire (`emotion/talk/gesture/camera` +
  seconds-into-audio — align our relay vocab to it); gesture-cues example
  (cue-phrase→gesture, ideal for mafia callouts/heckles); align.ts confirms
  our measured-offsets doctrine. Clone at 45f0b6d, nothing new upstream.

## Poker night (2026-10-17)

`poker` mode: fixed-limit Texas Hold'em (blinds 1/2, bets 2/4, 100 stacks,
dealer rotation, real side pots, split ties). Hole cards are per-phone
secrets (same view discipline as freaktionary); board/pot/actor public.
Bots play pot-odds poker (hole tiers preflop, made-hand + pot-odds calls,
seeded bluffs ~10%, 3-raise cap) — the level field. Proven by
`test_poker.py` (29: 13 evaluator vectors incl. wheel/kickers/ties +
secrecy + streets + showdown + pot conservation + all-bot night).
Faces roadmap: presence roster shows who's on camera; video seats reuse
the stage-monitor WebRTC pattern (not wired this pass — cards first).

## /perform trial review (2026-10-17, 10 checks, all autonomous)

VERDICT: live on box + party + www, all 8 endpoints 200, 404s correct,
193 sims + 47 contract + 9 unit green. Trial minutes pass on 3 sets
(15/10/9 beats, real 2-3MB audio + beds).

- Personae separate: easy laughs generously (8 in 10 beats), skeptic stays
  silent until heat 0.78 then cracks exactly once, normal lands between.
  Same buttons (/api/react), same stamps, different taste bars.
- Heatsheep (simulated average human, no judge, taps ~ heat): ran both
  crowd arms on both sets. Calibration read: agents converge on high-heat
  beats (biscuit 0.62-0.78 laughed by everyone, 0.30-0.33 silent except
  easy); cathy laughs cluster b7-b11 exactly where heat peaks.
- Negative control HOLDS: text agents tap identically bed vs nobed
  (can't hear the bed — as designed). Real A/B awaits humans.
- Monitor/signal/presence/feed loop verified live; finale/bill/vote paths
  verified (bad vote 400, bad slugs 404). Smile posts log with cond.
- Scripts: trial_minutes.py (3-set play-through), agent personae
  (--persona easy/skeptic/normal/heatsheep) in agent_audience.py.

## 3D engine audit + mouth A/B + agent critic (2026-10-17)

ENGINE: yes, real and running — three.js + @pixiv/three-vrm bodies,
expressionManager per-beat faces, blink timer, idle sway, gesture clips,
CameraDirector. Served inline (not the dormant packages/stage-runtime or
apps/live shells — those are designed, unbuilt, documented as such).
LIPSYNC TODAY: frequency-band envelope flap (aa/ih/oh from FFT bands).
Upgrade shipped: v1 adds ou/ee bands (?mouth=v0 control arm, default v1 on
/f/ + /perform, cond carries bed/nobed+mouthv0/v1). NOT phonemes — Rhubarb
or forced alignment is the queued upgrade (neither on the box); their
laugh-type/valence files aren't here either.
CRITIC: scripts/evaluate_performance.py scores served/delivery/acting/
mouth/crowd/observed 0-10 with stated limits (structure only — looks need
eyes, funny needs the room). Cathy 9.0, Biscuit 9.8. A/B: both arms served
(trial asserts), report cards on record; mouth differences are
browser-visible only, so agents negative-control while humans judge looks.

## Vendor review: 5 repos (2026-10-17, shallow-cloned, reviewed, removed)

- earshot (AI ears): REAL and wanted — describe/match/timeline/critique
  for audio agents, CPU-only, MIT. BLOCKED here: torch+transformers+CLAP
  weights ≈2.5GB on a 94% disk. Revisit on roomier iron; our numpy energy
  analysis covers timing until then. Nothing vendored.
- UniForge3D (multi-view→3D asset, research): GPU + conda + HF weights,
  unrunnable here. Pattern only: photo→pocket-prop is the future of the
  prop pipeline (currently Blender-spec-only). Nothing vendored.
- Ref2VA (ComfyUI ref→video, RTX 4090): same verdict — pattern matches our
  takes/record dreams, hardware says no. Nothing vendored.
- Liquid cookbook unsloth notebook (SFT decision models): training needs
  CUDA, but the RECIPE ports free — state→options-as-codes, single-pass
  choice readout. That's our judge/button policy format; runnable on mimo
  via Go today. Notes kept, no code.
- Kenney Shape (itch): download gated behind interactive claim (2-min
  human job). Meanwhile three.js primitives cover 80% of pocket-prop
  needs; claim it when someone wants pretty.
- ATTEND SDK (shipped): scripts/attend_sdk.py — one call attends a full
  set (heat → mimo judge → delay harness → same buttons → report with heat
  agreement + verdict compare). Demo: biscuit, 3 haha + 8 hahaha, 70%
  heat agreement. Limits stated in module docstring (no ears, no eyes).

## SOLO spec + focus review (2026-10-17)

- SOLO "CRACK ME" specced at docs/SOLO-MODE.md (6 slices: face gate,
  taste profile, live writer, performance, difficulty, record+share).
  Not built. Face cam + live mimo set + stone-face timer + share clips.
- Kaggle ready: priortrades token stored (~/.kaggle, 600, verified).
  Earshot runs there when wanted (this box can't hold torch+CLAP).
- FOCUS REVIEW (owner: stage first, laughter-logic second). Honest count:
  this session built ~60% laughter-logic (heat, verdicts, states, agents,
  critics, A/B harness) vs ~40% stage (rooms, entrance, acting driver,
  visemes, bed, monitor, poker/stone-face). The logic now EXCEEDS what the
  stage can show — heat predicts moments no avatar fully performs, and
  Biscuit still plays in a fallback body. Rebalance, stage-first backlog:
  1. one prepared VRM body with gesture clips (Ralph), 2. SOLO slices
  3. avatar casting per bundle (no more default-rig pups), 4. record/share
  path, 5. camera direction beyond push-in. Laughter-logic goes maintenance
  mode: no new models until the stage can perform what heat already sees.

## Venue system (2026-10-17): Cauldron gone dingy, schema jails the rest

- CAULDRON-PROFILE dingy pass: candles/Edisons/posters/brass all cut.
  Bare mic on a stained stage, chalk (not gold) sigil, crooked black
  curtains, dead bulb in a cage, sticky floor. Bare test counts the deck
  props. Prompt rewritten to forbid every dressing Marble loves.
- VENUE-SCHEMA.json (freaktown.venue.v1): id/size/room/stage/marks/props/
  light_rig/cameras/crowd/budgets/glb-sha. Sizes S/M/L bound dims,
  capacity, parses, GLB weight. Lights are temp+level+pos or they don't
  ship. scripts/validate_venue.py enforces it (stdlib only) — cauldron.json
  VALID (S, 3 marks, 11 props, 40 seats, 4 cams); junk correctly INVALID.
- VENUE-PROPS.md registry: 11 base (mic-stand IS the room, all procedural
  three.js — zero downloads) + band pack (drums/guitar/keys, M+) +
  judging pack (desk/chairs/buzzers, M+). Validator refuses unregistered ids.
- THREE HOUSES, all VALID: Cauldron (S, 40 seats, dingy cellar, darkest
  bills, best crowds) · Medium (M, 150, theatre for established comics,
  booth cam, balcony) · Red Curtain (L, 400, specials machine: band kit
  stage-left, judging desk + 3 buzzers front-center, 8 cameras incl.
  crowd + backstage + judges-cam). All glb sha pending Atlas jobs.
- Canonical props, per-venue bodies (2026-10-17): prop instances take
  `variant` (brass-worn / black / chrome mic stands — zero downloads) +
  `mesh` slot (Atlas GLB override later). Venues carry `acoustics`
  (Cauldron rt60 0.7 / Medium 1.1 / Red 1.6, bed gains) + `physics`
  (Cauldron forgiving 0.85/0.18/0.35 resist — best crowds; Red stiff
  0.9/0.12/0.6 — big rooms are hard). `/api/venue/<id>` serves truth;
  monitors take `?venue=` and run its dynamics live (verified per-venue
  DECAY on the wire). Mesh variants slot into the same field when Atlas
  delivers — no code changes.

## PLATFORM DECISION (2026-10-17, final): browser/phone/laptop. No VR.

Researched: VR comedy already exists (Soapstone 5,000+ shows) and its
platform (Horizon VR) is on life support with creation cut — audience
moving to flat. Industry consensus: browser-first reach, XR premium tier.
WebXR not production-ready (2026 testing). Our call: flat stack only —
phone browsers are the venue. No headset code paths, no native builds.
Quest-browser "Enter VR" stays a cheap future door (same three.js scene),
never the house. Budgets target a 3-year-old phone or the room degrades.

## Verify in 60 seconds

```bash
/usr/bin/python3 test_allbots.py && /usr/bin/python3 test_freeze_night.py && /usr/bin/python3 test_party.py && /usr/bin/python3 test_stone_face.py
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/play
curl -s -o /dev/null -w "%{http_code}\n" https://party.funnier.si/play
secret-scan per AGENTS.md rule 1 (must print nothing)
```
