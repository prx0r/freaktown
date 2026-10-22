# Extending the live stage

Companion to [`LIVE-STAGE.md`](LIVE-STAGE.md). Every recipe keeps the three
rules: **contracts in one place** (`packages/contracts`), **control only sends
commands**, **the stage only obeys events**. Paths are from the repo root.

> **News shows:** for rundown-driven news (anchors, reporters, wall headlines,
> a BBC-Ed-style camera director, show styles, headless MP4 render) use the
> newsroom SDK: [`docs/NEWSROOM-SDK.md`](NEWSROOM-SDK.md) (`packages/newsroom`).
>
> **Sketches:** for scripted comedy in any set (beats, stage directions,
> persistent identities, laugh holds, a comedy shot grammar, headless MP4
> render) use the sketch layer: [`docs/SKETCH-SHOW.md`](SKETCH-SHOW.md)
> (`packages/sketch`).

---

## 1. Add a character

A character on the live stage is *a body URL + a set*. The body tier is chosen
by `loadAvatar()` (`packages/stage-runtime/src/avatars/loadAvatar.ts`):

| `avatar_url` | Driver | Mouth |
|---|---|---|
| `avatars/<name>.vrm` (or a `.glb` with VRM extensions) | `VrmAvatar` | VRM presets `aa ih ou ee oh` (≥2 → `viseme`), else `jawOpen` |
| `meshes/<name>.glb`, any URL to a plain GLB | `GlbAvatar` | sniffed: visemes → `viseme`, `jawOpen`/`mouthOpen` → `morph`, jaw bone → `jaw`, else `none` |
| `basic` / `basic:robot` | `BasicAvatar` | always (`jaw`) |
| anything that fails to load | `BasicAvatar` + `avatarFallback` reason in telemetry | always |

### VRM

1. Drop the file in `static/avatars/` (served at `/avatars/` in dev and copied
   into `dist/avatars/` by the Vite plugin). Keep files < 5 MB in git where
   possible; bigger bodies belong in R2 (absolute URL) per `docs/BOUNDARIES.md`.
2. Point a set at it (section 3) or pick it in /control.
3. Check telemetry: `/stage/demo?debug=1` shows `avatar vrm:<name> mouth=viseme`.

Expression mapping is semantic → VRM preset (`src/performance/Performer.ts`):

```ts
// Performer.ts — face cue → emotion weights (each driver maps emotions to its rig)
const FACE_MAP: Record<string, Partial<Emotions>> = {
  'face.smile': { happy: 1 },
  'face.smug': { happy: 0.6, relaxed: 0.5 },
  'face.annoyed': { angry: 1 },
  // add: a new semantic face
  'face.wince': { sad: 0.5, surprised: 0.4 },
};
```

`VrmAvatar` writes `happy/angry/sad/surprised/relaxed` + `blink` + visemes with
`expressionManager.setValue()`; names the model lacks are skipped, never faked.

### GLB (three.ws / Meshy / character-meshes)

Add morph-name aliases where the sniffer looks (`src/avatars/GlbAvatar.ts`).
Only names that exist in the bytes are ever driven:

```ts
const VISEME_NAMES: Record<VisemeKey, string[]> = {
  aa: ['viseme_aa', 'v_aa', 'aa', 'A', 'mouth_a', 'Fcl_MTH_A', /* add */ 'MTH_A'],
  // …
};
const OPEN_NAMES = ['jawOpen', 'mouthOpen', /* add a vendor's name */ 'Mouth_Open_01'];
const EMOTION_NAMES = { happy: ['mouthSmileLeft', 'mouthSmileRight', 'happy'], /* … */ };
```

Bones are found by regex (`/head$|head_|:head/i`, `/spine2|spine1|spine|chest/i`,
`/jaw/i`). A static mesh (no bones) gets whole-body puppet motion. If the GLB ships
an `idle` clip it plays on an `AnimationMixer` under the procedural layer.

To know what a mesh really has before casting it:

```ts
const { driver } = await loadAvatar({ url: '/meshes/quaternius_cc0-husky-1095.glb' });
console.log(driver.caps); // { kind:'glb', mouthMode:'none'|'morph'|…, morphNames:[…] }
```

### BASIC

`new BasicAvatar({ name, seed, variant: 'human' | 'robot' })` — the palette is
seeded by the character id. New variants go in `BasicAvatar.ts` (build primitives
in the constructor; keep `setMouth/setBlink/setExpression/setPose` working).

### Pose mapping

Gestures produce a rig-neutral `PoseState` (`src/avatars/types.ts`: breath, sway,
spine/head angles, shoulder shrug, per-arm `raise/out/bend/wave`). Each driver maps
it; for a new rig implement `AvatarDriver.setPose()`. VRM uses normalized humanoid
bones (T-pose, faces +Z), so the same numbers work for every VRM.

---

## 2. Add a camera preset and a cue rule

**Preset** — the name is a wire contract, so add it in both places:

```ts
// packages/contracts/src/show.ts
export type CameraPresetV1 = | "WIDE_STAGE" | … | "BALCONY";
export const CAMERA_NAMES: CameraPresetV1[] = [ …, "BALCONY" ];
```

```ts
// packages/stage-runtime/src/CameraDirector.ts — the Record<CameraPresetV1,…>
// type makes the build fail until every contract name has framing.
BALCONY: { position: [0, 4.2, 9.5], target: [0, 1.2, 0], fov: 38 },
```

Framing assumes the performer normalized to 1.7 m at the origin, mic stand at
`x=+0.42` (keep side angles on `x<0`). Optional: map a hotkey in `KEYBOARD_MAP`
and add a button to `CAMERAS` in `apps/live/src/pages/ControlPage.tsx`. The DO and
LocalRoom gate `camera.cut` with `validateCameraCut`, so unknown names are dropped
until the contract has them. Mirror the name in `backend/contracts.py`
(`CameraPresetV1`) to keep pogtown's parity test green.

**Cue rule** — automatic cuts are written by the set adapter
(`src/plan/setAdapter.ts`, `adaptSealedSet`). `pushCam()` enforces ≥1.2 s between
cuts and never repeats the current shot:

```ts
case 'callback': {                                  // a new beat type
  pushCam(beat.start_ms + 150, 'BALCONY', 'callback');
  cues.push(cue(beat.start_ms + 200, 'gaze.left', 0.7, 1200, 'head'));
  break;
}
```

Add a test in `packages/stage-runtime/tests/setAdapter.test.ts` (the existing
"close-ups only on punchlines / no strobing" test shows the pattern).

---

## 3. Add a set (build_set.py → adapter)

```bash
source /home/ubuntu/.venvs/freaktown/bin/activate      # box; any python with edge-tts
PYTHONPATH=. python3 scripts/build_set.py --character pog.chairman-meow --outdir /tmp/sets/chairman-meow
# or --setplan takes/<id>.plan.json (status must be SCRIPT_APPROVED)

d=apps/live/public/sets/chairman-meow && mkdir -p $d
cp /tmp/sets/chairman-meow/{timeline.json,mouth_cues.json,set_plan.json} $d/
ffmpeg -i /tmp/sets/chairman-meow/set.wav -ac 1 -ar 24000 -b:a 64k $d/set.mp3   # keep git small
```

Register it in `apps/live/public/sets/index.json`:

```json
{ "id": "chairman-meow", "title": "Chairman Meow — Collective bargaining",
  "character_name": "Chairman Meow", "character_id": "pog.chairman-meow",
  "premise": "Collective bargaining from high furniture.",
  "set_url": "sets/chairman-meow", "audio_url": "sets/chairman-meow/set.mp3",
  "avatar_url": "basic", "avatar_note": "BASIC procedural body",
  "beats": 6, "duration_ms": 58000, "source": "scripts/build_set.py --character pog.chairman-meow" }
```

The stage adapts the folder itself when it receives `performance.preload` with a
`set_url` (`loadSealedSet` → `adaptSealedSet`): words are laid onto the envelope's
voiced spans, cues come from beat types (`setup / escalation / punchline / closer`)
and `performance.{expression,gesture,look}` in the delivery. To precompute instead
(e.g. a server endpoint), send the plan inline:

```ts
import { adaptSealedSet } from '@funnier/stage-runtime';
const plan = adaptSealedSet({ timeline, mouthCues, setPlan, durationMs });
await client.preloadPerformance({ performance_id, audio_url, avatar_url, plan });
```

Sets served from elsewhere (box, R2) work the same — `set_url`/`audio_url` may be
absolute (mind CORS).

---

## 4. New event / command types (contracts → room → executor)

Example: `stage.spotlight { color, intensity }` from the operator.

1. **Contract** — `packages/contracts/src/show.ts` (types stay dependency-free):

   ```ts
   export interface SpotlightPayloadV1 { color: string; intensity?: number }
   ```

   If it changes room state (phase, pause, active performer), extend
   `applyEpisodeEvent` in `packages/contracts/src/episode.ts` — both the DO and
   LocalRoom call it, so they stay identical. Pure display events need nothing here.

2. **Room** — the DO persists + broadcasts any `/command` type already
   (`edge/worker/episode-room.ts` `handleCommand → executeCommand`), as does
   `LocalRoom.execute`. Add validation next to the `camera.cut` gate when the
   payload must be checked before it is persisted.

3. **Control** — one method on `ControlClient` (`apps/live/src/control/controlClient.ts`):

   ```ts
   spotlight(color: string, intensity = 1) {
     return this.command('stage.spotlight', { color, intensity });
   }
   ```

4. **Stage** — one `case` in `StageEventExecutor.execute`
   (`packages/stage-runtime/src/StageEventExecutor.ts`) calling a runtime method:

   ```ts
   case 'stage.spotlight':
     if (typeof payload.color === 'string') this.runtime.setSpotlight(payload.color, Number(payload.intensity ?? 1));
     break;
   ```

   Events run serially in seq order and are replayed for late stages, so make the
   handler idempotent-ish (setting state, not toggling it).

5. **Test** — a LocalTransport test that the command arrives as an event, plus an
   executor-level assertion in e2e (`window.__stage.executor.executed`).

Stage-originated facts (like `performance.ready`) go the other way:
`consumer.sendStageAck({ event: 'stage.something', … })` — the DO only accepts
ACKs from an authenticated stage socket and persists them as events.

---

## 5. A new transport

Implement `LiveTransport` (`packages/stage-runtime/src/live/LiveTransport.ts`):

```ts
export class PartyRoomTransport implements LiveTransport {   // e.g. Flask SSE + POST
  readonly kind = 'local' as const;                          // widen the union if needed
  private handlers = new HandlerSet();
  private es: EventSource | null = null;
  get connected() { return this.es?.readyState === 1; }
  subscribe(h: LiveHandlers) { return this.handlers.add(h); }
  async connect(ep: string, opts: LiveConnectOptions = {}) {
    this.es = new EventSource(`/party/${ep}/events?since=${opts.since ?? 0}`);
    this.es.onmessage = (m) => {
      const msg = JSON.parse(m.data);
      if (msg.type === 'show.snapshot') this.handlers.snapshot(msg.data);
      else this.handlers.event(msg.data);                    // {seq,type,actor,payload,created_at}
    };
  }
  disconnect() { this.es?.close(); this.es = null; }
  async command(type: string, payload = {}, commandId?: string) {
    const r = await fetch(`/party/cmd`, { method: 'POST', body: JSON.stringify({ type, payload, commandId }) });
    return r.json();
  }
  sendStageAck(p: Record<string, unknown>) { void this.command(String(p.event), { actor: 'stage', ...p }); }
  sendReaction() {} sendCameraCut() {} sendHeartbeat() {}
}
```

Contract for any transport: deliver events with monotonically increasing `seq`,
send a snapshot then the replay (`seq > since`) on connect, persist before
broadcast, and never echo-skip the sender (LocalTransport delivers locally because
BroadcastChannel doesn't echo). `EventConsumer` dedups by seq, so at-least-once is
fine. Wire it in `apps/live/src/live/transport.ts` (`createTransport`) behind a
`?transport=` value, and copy `tests/LocalTransport.test.ts` as its test.

---

## 6. Props and lighting

The room is `StageSet` (`packages/stage-runtime/src/StageSet.ts`) — procedural,
no binary assets. Add geometry in the constructor; light rigs are fields so the
runtime can animate them:

```ts
// a stool prop already exists; a glowing "APPLAUSE" sign:
const sign = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.4),
  new THREE.MeshBasicMaterial({ map: neonTexture('APPLAUSE'), transparent: true, toneMapped: false }));
sign.position.set(-3, 3.6, -2.2);
this.group.add(sign);
```

```ts
// a show-driven light: expose a method, call it from an executor case
setSpot(color: string, intensity = 1): void {
  this.spot.color.set(color);
  this.spot.intensity = 70 * intensity;
}
```

Keep the performer area clear: mic stand at `(0.42, 0, 0.45)`, deck top at `y=0`,
front edge `z=2.2`, audience rows from `z=3`. Shadows come only from the key spot
(`quality=low` disables them). Every extra shadow-casting or per-pixel light costs
a lot on phones and in software GL — prefer emissive/`MeshBasicMaterial` glow.
Crowd energy (`StageSet.excite()`) bobs the audience and warms the house light;
reactions call it via `runtime.react(kind)`. GLB props: load with `GLTFLoader` and
add to `this.group`; host the bytes in R2 like avatars.

Sounds: `SfxSynth.play(name)` (procedural). Real samples: send
`audio.sfx.play { url }` or pass `sfxUrl` to `StageEventExecutor`.

---

## 7. Running the tests

```bash
npm install
npm test                    # vitest: 79 tests — adapter, transports, consumer, camera, mouth,
                            # performer, showStore, EpisodeRoom logic, Ella reflex, Privy
npm run typecheck
npm run build               # → apps/live/dist

cd apps/live
CHROMIUM_PATH=/usr/bin/chromium NO_PROXY=127.0.0.1 npx playwright test
#   live-stage.spec.ts  control→stage (local): clock, mouth, face, blink, cuts,
#                       pause/resume, reactions, screenshots; BASIC + mobile; late join
#   room.spec.ts        same over wrangler dev EpisodeRoom (needs ROOM_URL)
SHOTS_DIR=/tmp/shots npx playwright test   # where screenshots go (default /workspace/work/funnier-live/shots)
```

Python stays as before: `pytest tests/contract -q`, `python3 test_party.py`.

---

## 8. Adding a set (news studio, podcast, poker table …)

A **set** is a `SetDefinition` (pure data) + a procedural builder (three.js) + optional CC0
GLB decor. The stage picks the renderer from the room: the latest `set.load` event decides
(`StagePage` → `comedy-club`/none = classic `StageRuntime`, anything else = `SetStagePage`
with the multi-seat `SetStage`). Control never touches the stage — the Set panel in
`/control` only sends commands.

```text
/control SetsPanel ──set.load / set.camera / dialogue.line / overlay.* / poker.*──► room ──► SetEventExecutor ──► SetStage
/play/:ep/seat/:n  ──seat.join / poker.intent──────────────────────────────────────► room ──► (dealer in /control applies it)
```

| File | What |
|---|---|
| `packages/contracts/src/sets.ts` | wire types: `SetLoadPayloadV1`, `CastMemberV1`, `DialogueLinePayloadV1`, overlays, `Poker*PayloadV1`, `SET_EVENT_TYPES` |
| `packages/stage-runtime/src/sets/types.ts` | `SetDefinition`, `SeatAnchor`, `CameraPresetDef`, `LightingRig`, `EnvironmentDef` |
| `…/sets/definitions.ts` | the four sets (data) · `…/sets/registry.ts` `SET_REGISTRY`, `findSeat` |
| `…/sets/camera.ts` | seat-aware cue resolver (pure, unit-tested) |
| `…/sets/builders/sets.ts` | procedural builders (`SET_BUILDERS[id]`) |
| `…/sets/SetStage.ts` · `SetEventExecutor.ts` | renderer + event → runtime mapping |
| `…/sets/autoDirector.ts` | active-speaker auto cuts |
| `…/sets/poker/*` | `PokerDealer` (poker-ts → events), `PokerShow` (bots, quips, human seat), `PokerProps` (cards/chips/button meshes) |
| `…/sets/demos.ts` | demo episodes (timed command lists) |
| `apps/live/src/control/SetsPanel.tsx`, `pages/SetStagePage.tsx`, `pages/PlayPage.tsx` | UI |

### Walkthrough: a "game show" set

1. **Definition** (`definitions.ts`) — seats, cameras, lights, overlays:

   ```ts
   export const GAME_SHOW: SetDefinition = {
     id: 'game-show', name: 'Game show', description: 'Three podiums and a host.',
     environment: { builder: 'game-show' },                 // procedural, zero downloads
     seats: [
       { id: 'host', position: [-2, 0, 0.5], rotation: 0.5, role: 'host', pose: 'standing' },
       { id: 'p1', position: [0.5, 0, -0.5], rotation: 0, role: 'player', pose: 'standing' },
       { id: 'p2', position: [1.6, 0, -0.5], rotation: 0, role: 'player', pose: 'standing' },
     ],
     cameras: {
       wide: { position: [0, 2.2, 6], target: [0, 1.3, 0], fov: 44, label: 'Wide' },
       'host-single': { seat: 'host', position: [0.2, 0.05, 1.8], target: [0, -0.1, 0], fov: 30 }, // seat-local
     },
     defaultCamera: 'wide',
     lighting: { ambient: { color: '#334', intensity: 0.8 }, key: { color: '#fff', intensity: 2.5, position: [2, 4, 4] }, background: '#05030a' },
     props: ['podiums', 'buzzers'], overlays: ['lower_third'], controlCameras: ['wide', 'host-single'],
   };
   ```

   Coordinates are metres, avatars face **+Z at yaw 0**; `rotation` is yaw. Seated seats
   (`pose: 'seated'`) put BASIC bodies on their seated legs and bend VRM hips/knees
   (`AvatarDriver.setSeated`). A camera with `seat` is in the seat's local frame
   (x = side, y = up from the head, z = forward) so it follows the seat.

2. **Builder** (`builders/sets.ts`): `SET_BUILDERS['game-show'] = (def, ctx) => ({ group, update, dispose })`.
   Use `applyLighting(group, def.lighting, ctx)`, `chair()`, `placeAtSeats()`, canvas
   textures for signs/screens; keep every material cheap (`MeshBasicMaterial` glow, one
   shadow-casting key light; `ctx.low` = software GL/phones). Expose `setHeadline` /
   `setOnAir` if overlays drive the scene.

3. **Register**: `SET_REGISTRY.register(GAME_SHOW)` (registry.ts). `validateSetDefinition`
   rejects duplicate seats and cameras bound to unknown seats.

4. **Cast + perform** (commands from control or a script):

   ```ts
   send('set.load', { setId: 'game-show', cast: [{ seat: 'host', character_id: 'pog.x', name: 'X', avatar_url: 'basic' }] });
   send('dialogue.line', { seat: 'host', text: 'Welcome back!' });     // mouth + gestures + auto cut
   send('set.camera', { cue: 'two-shot:p1+p2' });                     // operator cut
   ```

### Camera cues

`set.camera { cue }` — `wide` · any preset name · `close:<seat>` · `single:<seat>` ·
`reaction:<seat>` · `two-shot:<a>+<b>` · `overhead` · `orbit` · `auto`. `<seat>` is a seat
id, a role (`host`, `guest`, `anchor`) or an index. `set.auto_director {on}` toggles the
active-speaker director (speaker change → single, every third line a close, quick
back-and-forth → two-shot, 4 s silence → wide, ≥1.2 s between cuts). The classic
`camera.cut` contract names stay comedy-club only (the room validates them); set cues go
through `set.camera`, which needs no contract change per set.

### Overlays

DOM, not WebGL (`SetStagePage`): `overlay.lower_third {name,title,show}`,
`overlay.ticker {items}`, `overlay.headline {text,kicker}` (also redraws the news video
wall texture), podcast ON AIR + speaker strap from `dialogue.line`, poker HUD from `poker.*`.

### Props and licensing

Props are procedural. Third-party GLBs go in `environment.glb` (url, licence, source,
transform, `hideNodes`, `verified`) and **must** have a row in `assets/sets/LICENSES.md`.
Unverified decor loads only with `?setglb=1`. Commit bytes only < 5 MB after optimisation;
otherwise load the publisher's CC0 CDN URL (CORS) and rely on the procedural fallback.

### Per-set notes

- **comedy-club** — set #1; one standing seat; rendered by the classic `StageRuntime`
  (sealed-set plans, VRM visemes). `set.load {setId:'comedy-club'}` switches back.
- **news-studio** — anchors `anchor1`/`anchor2` seated behind a curved FUNNIER NEWS desk;
  video wall (canvas texture) shows `overlay.headline`; lower third + scrolling ticker.
  Cameras: wide, anchor1-single, anchor2-single, two-shot, screen (3/4 over-shoulder with
  the wall). Demo: 3 headlines, anchor + co-anchor tag, scripted cuts.
- **podcast** — round table, 4 seats (`seat1` host … `seat4`), boom-arm mics, headphones,
  acoustic panels, pulsing ON AIR sign. Cameras: wide, two-shot, per-seat singles + any
  `close:`; demo runs on the auto director (active speaker).
- **poker-table** — oval felt (3.0 × 1.4 m), 8 seats around it facing the centre, seat 4
  `open` for a human. `PokerDealer` wraps **poker-ts** (MIT) and emits
  `poker.hand_start / deal / turn / action / chips / board / showdown`; `PokerShow` runs
  bots (`botDecision`: tight / loose / maniac / calling-station) with quips as
  `dialogue.line`, cuts to reaction/close/board/overhead, and applies `poker.intent` from
  `/play/:ep/seat/:n` (phone UI: take seat → hole cards → fold / check·call / raise slider).
  The human appears as a BASIC body via `seat.join`. A human who doesn't act in 30 s
  auto-checks/folds. **Hole cards are public in the event log** — fine for a broadcast
  show, not for real-money play; game truth for anything beyond a show belongs in pogtown.

### Multi-writer note (LocalTransport)

`/play` and `/control` write to the same LocalRoom from different renderer processes; a
localStorage write can lag its BroadcastChannel message. `LocalRoom.execute(…, known)`
merges events the writer already saw on the wire so the dealer's answer to a
`poker.intent` never reuses its seq (covered in `tests/sets.test.ts`).

### Tests

`packages/stage-runtime/tests/sets.test.ts` (registry, seats, camera targeting, auto
director, text mouth, demo timelines, LocalRoom merge) and `poker.test.ts` (poker-ts event
mapping, folds, showdown chip totals, bots, PokerShow with a human seat).
`apps/live/e2e/sets.spec.ts`: each set loads + demo runs + ≥2 cuts + no console errors;
poker human seat acts from `/play` and the stage reflects it to showdown; comedy club
switch-back. Screenshots → `$SHOTS_DIR/sets`.

---

## 9. Modifying and extending each set (recipes)

All paths under `packages/stage-runtime/src/sets/` unless noted. After any change:
`npm test && npm run build`, then `cd apps/live && npx playwright test e2e/sets.spec.ts`.

### 9.1 Swap in a GLB environment (any set)

```ts
// definitions.ts — e.g. news studio
environment: {
  builder: 'news-studio',                  // procedural set stays underneath (fallback + anchors)
  glb: {
    url: 'https://cdn.3dassets.dev/assets/35527/v1/model.glb',   // CORS CDN, or 'sets-assets/studio.glb' (apps/live/public)
    license: 'CC0-1.0', source: 'https://3dassets.dev/assets/…',
    transform: { position: [0, 0, -9], rotation: Math.PI / 2, scale: 1 },  // line its desk up with the seats
    hideNodes: ['GreenRoom', 'Gallery'],   // crop parts of a big scene by node-name substring
    verified: true,                        // false → only loads with /stage/:ep?setglb=1
  },
},
```

To *replace* procedural parts instead of layering, hide them in the builder when a GLB is
present (e.g. skip the cyclorama) — keep seats/chairs so cameras stay valid. Workflow:
load with `?setglb=1&debug=1`, adjust `transform` until the desk sits behind the anchor
seats, flip `verified: true`, add a row to `assets/sets/LICENSES.md`. Committed bytes must
be < 5 MB after `npx @gltf-transform/cli optimize in.glb out.glb --compress meshopt`.

### 9.2 Add or move seats

```ts
// podcast: a 5th seat at the far side, facing the centre
const PODCAST_SEATS = [ …, podSeat('seat5', 180, 'guest3') ];   // degrees from -Z; around() faces the centre
// news: move anchor2 further left and make it standing
seat('anchor2', -1.1, -0.55, 0, 'co-anchor', 'standing'),
// poker: 10 seats instead of 8 — change POKER_SEATS and PokerDealer numSeats (default 8)
const POKER_SEATS = 10;   // new PokerDealer(seats, blinds, 10)
```

Seat ids are referenced by camera presets (`seat: 'seat1'`), demo casts (`demos.ts`) and
`POKER_HUMAN_SEAT` — rename all three together. `validateSetDefinition` throws on a
duplicate id or a camera bound to a missing seat; `sets.test.ts` checks poker seats face
the centre. Chairs, mics and headphones are placed by the builder from `def.seats`, so
they follow automatically.

### 9.3 Per-set cameras

```ts
cameras: {
  // absolute
  'crane': { position: [0, 4.5, 6], target: [0, 1, -1], fov: 40, label: 'Crane' },
  // seat-bound: offsets in the seat's frame (x side, y up from head, z forward)
  'host-ots': { seat: 'seat1', position: [0.35, 0.1, -0.6], target: [-0.4, -0.1, 2.0], fov: 34, label: 'Host OTS' },
  // slow orbit around the target (rad/s)
  'drift': { position: [0, 2.2, 4], target: [0, 0.9, 0], fov: 42, orbit: 0.1 },
},
controlCameras: ['wide', 'crane', 'host-ots', 'drift'],   // buttons in /control
```

Generic cues need no preset: `close:<seat>`, `single:<seat>`, `reaction:<seat>`,
`two-shot:a+b`, `overhead`, `orbit`. Tune their offsets in `camera.ts`
(`resolveCameraCue`); head height per pose is `HEAD_HEIGHT`. The auto director's rules
(`autoDirector.ts`) and the poker cut policy (`PokerShow.apply`) choose cues by name.

### 9.4 Props

Props are built in the set's builder (`builders/sets.ts`). Per-seat props use the seat:

```ts
for (const s of def.seats) {
  const [x, y, z] = seatLocal(s, [0.25, -0.45, 0.35]);   // right of the knees, table height
  group.add(cyl(0.04, 0.035, 0.1, std(0xeeeeee), x, 0.8, z));   // a mug
}
```

Animated props: return `update(dt, wallMs)` from the builder; show-driven props expose a
method on `BuiltSet` (like `setHeadline` / `setOnAir`) and get an executor case (§4).
Poker's moving parts live in `poker/PokerProps.ts` (cards, chip stacks, pot, button;
`spot(seat, k, lateral)` gives felt positions between centre and seat).

### 9.5 Overlays (ticker, strap, ON AIR, lower third)

DOM in `apps/live/src/pages/SetStagePage.tsx`, state in `SetStage.overlay`:

```ts
send('overlay.ticker', { items: ['MARKETS: chips +4%', 'WEATHER: puns'] });  // scrolls (CSS ftTicker in index.html)
send('overlay.lower_third', { name: 'Dana Deadline', title: 'Anchor', show: true });  // show:false hides
send('overlay.headline', { text: 'Robot wins pie contest', kicker: 'breaking' });     // DOM state + video-wall texture
```

The podcast speaker strap comes from `dialogue.line` (`overlay.speaker`); ON AIR is
`overlay.onAir` + the 3D sign (`BuiltSet.setOnAir`). A new overlay = a field on
`OverlayState`, an executor case, a JSX block gated by `tele.setId`, and its hook name in
`def.overlays`.

### 9.6 Poker rules and bots

```ts
new PokerDealer(seats, { smallBlind: 25, bigBlind: 50 }, 8);   // blinds, seats (poker-ts Table)
// ante: poker-ts Table({ ante: 5, smallBlind, bigBlind }) — pass through in PokerDealer's constructor
pokerSeats('You')                  // demos.ts: who sits where, stacks, bot style
{ seat: 2, name: 'Chairman Meow', stack: 1000, kind: 'bot', style: 'maniac' }   // tight | loose | maniac | calling-station
```

Bot behaviour is `botDecision(turn, strength, style, rnd)` in `poker/PokerDealer.ts`
(preflop strength from `holeStrength`; post-flop it currently reuses it — a hand
evaluator on the board is the natural next step). Quips: `QUIPS` / `quip(kind, n)`.
Timing: `PokerShow({ botDelayMs, humanTimeoutMs, quips, directCameras })`. Multiple hands:
call `dealHand()` again (button rotates via poker-ts). Event contract:
`poker.hand_start / deal / turn / action / chips / board / showdown` (`contracts/src/sets.ts`);
`poker.test.ts` covers the mapping — extend it when you change rules.

### 9.7 The human seat

`/play/:ep/seat/:n` (`PlayPage.tsx`): `seat.join {seat, name, avatar_url, kind:'human'}` →
the stage casts a BASIC body (or `avatar_url`) into that seat; the player acts with
`poker.intent {seat, action, amount}`; the dealer in /control applies it only on that
seat's turn (`PokerShow.apply`, errors shown in the Set panel). Make more seats human:
mark them `kind: 'human'` in `pokerSeats()` and `open: true` in the definition. For
phones on other networks use the EpisodeRoom transport (`?transport=room`) — the DO's
`/command` needs a **player-scoped token** before this is safe in prod (today: admin
auth or `LIVE_DEV_OPEN`). Hole cards are public in the log (broadcast show only).

### 9.8 A new set from scratch (checklist)

1. `definitions.ts`: `SetDefinition` (id, seats, cameras, lighting, overlays, controlCameras).
2. `builders/sets.ts`: `SET_BUILDERS['<id>'] = (def, ctx) => { … return { group, update, dispose } }`.
3. `registry.ts`: `.register(MY_SET)` on `SET_REGISTRY`.
4. `demos.ts`: a cast + `TimedCommand[]`; wire it in `SetsPanel.runDemo`.
5. Overlays (optional) in `SetStagePage.tsx`; new events in `contracts/src/sets.ts` + executor.
6. Tests: registry/camera assertions in `sets.test.ts`; a block in `e2e/sets.spec.ts`.
7. Licences: any third-party asset → `assets/sets/LICENSES.md`.

---

## 10. Faces: expressions, ARKit blendshapes, visemes, affect (live-face)

One interface for every body tier. `packages/stage-runtime/src/face/`:

| File | What | Ported from |
|---|---|---|
| `arkit.ts` | `ARKIT_52`, `ARKIT_MOUTH`, `OCULUS_15`, `OCULUS_TO_VRM` (Oculus-15 → VRM-5), `arkitToFace()` (52 blendshapes → visemes/emotions/blink), `faceToArkit()` (our plan face → ARKit for ARKit-only GLBs), `smileFusion()` | `app.py` `ARKIT_MOUTH`/`OCULUS_MOUTH`, `WAWA_MAP`, `applyFace` (MediaPipe → VRM) and `static/affect-servo.js` `smileFusion` on **`feature/mutuals-acting-party-smiles` (008d4f5, 2026-10-17)** |
| `affect.ts` | `affectToDelivery(a,v,p)` (exact port, parity-tested) + `affectToEmotions(a,v,p)` (new: A/V/P → VRM emotions) | `static/affect-servo.js` (lab rig, same branch / main 4cfe7c3) |
| `vocab.ts` | harness emotion/gesture/camera vocabulary, `FACE_ALIASES` (`face_excited`, `reaction.smile`, `lean_in` …), `normalizeFaceAction`, `emotionToFaceAction`, set-camera equivalents | `harness_adapter.py` + the `face_*` map added to `StageRuntime.ts` on the same branch (vocabulary inspired by github.com/mutuals-inc/character-harness, Apache-2.0) |
| `harnessBeats.ts` | `compileHarnessBeats(text, beats, words)` — mutuals-beats/v1 acting beats on **measured** word timings, fails closed | `compile_harness_beats` (same branch) |
| `FaceChannel.ts` | composes base (Performer + plan/text mouth) + affect hold + live ARKit stream, and `FaceChannel.apply(driver, frame)` | new |

Also ported: the **sealed SDK export contract test** from **`sdk-sealed-export` (8acd6b0,
2026-10-21)** — `tests/sealedSdkExport.test.ts` + `tests/fixtures/sealed-buddha/`
(characters-repo `seal_set.py` output → `adaptSealedSet`, deadpan face, koan freeze).
Neither feature branch was merged; only what the stage needs was copied.

### Driver interface

```ts
interface AvatarDriver {
  setMouth(open, visemes); setExpression(emotions); setBlink(amount);   // every tier (unchanged)
  setBlendshapes?(weights: Record<string, number>): void;                // NEW, optional: raw ARKit names
}
```

- **VRM** (`VrmAvatar`): presets `aa ih ou ee oh` + `happy angry sad surprised relaxed` +
  `blink` as before; `setBlendshapes` writes ARKit names the VRM carries as **custom
  expressions** (VRM 1.0 allows any name), never overwrites presets.
- **GLB** (`GlbAvatar`): sniffed visemes/`jawOpen`/emotions as before; `setBlendshapes`
  writes any morph whose name is in the bytes (ARKit-52 GLBs, MetaPerson, Ready Player Me).
  ARKit-only GLBs now perform text/plan mouths and emotion cues via `faceToArkit`.
- **BASIC**: emotions/visemes/blink by construction; `setBlendshapes` adds asymmetric brows
  (`browOuterUp*`/`browDown*`), smile/mouth side shift, `eyeWide*` pupils, `cheekPuff`.

Rule kept: **never fake a mouth** — a GLB with no mouth morphs/jaw still reports
`mouthMode: none`, and `setBlendshapes` ignores names that aren't in its bytes.

### Driving faces

```ts
// 1. per line, from the set/dialogue (harness vocabulary or face actions)
send('dialogue.line', { seat: 'seat2', text: 'Absolutely not.', emotion: 'annoyed' });
// 2. a cue any time (classic stage: omit seat)
send('face.expression', { seat: 'seat2', emotion: 'surprised', intensity: 1, duration_ms: 2500 });
// 3. live puppeteering: ARKit-52 frames (MediaPipe FaceLandmarker categories → name: score)
send('face.blendshapes', { seat: 'seat1', weights: { jawOpen: 0.6, mouthSmileLeft: 0.8, eyeBlinkLeft: 0 } });
// 4. affect servo: three numbers steer the face for hold_ms
send('face.affect', { seat: 'anchor1', a: 0.7, v: 0.6, p: 0.2, hold_ms: 4000 });
// 5. acted lines: beats on measured word timings (e.g. edge-TTS WordBoundary), relative to line start
send('dialogue.line', { seat: 'seat1', text: 'It filed a complaint.', words: [{ word: 'It', start_ms: 0, end_ms: 120 }, …],
  beats: [{ span: 'complaint', emotion: 'deadpan', camera: 'push-in' }] });
```

Sealed sets: drop `words.json` (measured `[{word,start_ms,end_ms}]`) and optionally
`acting.json` (`{schema:'mutuals-beats/v1', beats:[…]}`) next to `timeline.json`;
`loadSealedSet` picks them up, prefers measured words over the envelope spread
(`plan.source.words = 'measured'`) and merges acting cues/cameras (warnings in
`plan.source.acting_warnings`). Without measured words the overlay is refused, as on the
branch ("never estimate timings for an acted punchline").

Layering (`FaceChannel.sample`): Performer face cues (`face.*`, aliases normalised) → max-blend
affect emotions → live ARKit overrides mouth + blink while fresh (450 ms stale timeout,
smoothing 0.5) unless the plan mouth is speaking louder; emotions always max-blend.
Telemetry: `window.__setStage.telemetry().seats[i].emotions / faceSources`,
`window.__stage.runtime.faceSources`.

### Extending

- New semantic face: add to `FACE_MAP` in `performance/Performer.ts` (and an alias in `vocab.ts`).
- New source vocabulary (e.g. Apple Live Link names, Oculus visemes from Rhubarb/wawa):
  convert to ARKit or VRM-5 in `arkit.ts` and send `face.blendshapes` / visemes.
- A per-character face profile (gain/offsets per channel): wrap `FaceChannel.apply` —
  e.g. `frame.emotions.happy *= profile.smileGain` — before writing the driver.
- Not ported (lab/audience only on the branch): the webcam smile referee (`smile-referee.js`),
  WebRTC monitor, face A/B harness pages, MFCC in-browser lipsync, Kalidokit body solve.
  The A/B-tested `WAWA_MAP` table is what the stage uses from that work.

Tests: `packages/stage-runtime/tests/face.test.ts` (maps, smileFusion/affect parity with
`affect-servo.js`, alias normalisation, Performer alias render, harness beats incl.
fail-closed cases, sealed-set measured words + acting overlay, FaceChannel layering/staleness,
BASIC + GLB `setBlendshapes`); e2e podcast test sends `face.expression` and a synthetic
ARKit stream from the Set panel and checks the seat's face telemetry.

## 11. News shows: the newsroom SDK

Rundown-driven news on the `news-studio` set lives in `packages/newsroom`.
It covers a Sofie-style rundown (show → segment → story → piece), show styles
(`goodnight` calm, `default-news` brisk), a camera director that follows BBC
R&D's Ed rules plus broadcast grammar, `compile()` to the set events above,
procedural wall cards, the `/newsroom/:id` page and a headless render CLI.
Channel adapters live in the channel's own repo. Full guide:
[`docs/NEWSROOM-SDK.md`](NEWSROOM-SDK.md).

## 12. Sketches: the sketch layer

Scripted sketches in any set live in `packages/sketch`. A
`funnier.sketch/v1` script contains a cast of persistent `pog.*`
identities on seats, plus scenes → beats → lines and stage directions
(look, react, gesture, move, pause, hold_for_laugh, headline, prop,
camera, button, blackout). `compileSketch()` lays it on one clock, plans
gaze, directs cameras (Ed timing plus a comedy grammar: game-reveal wide,
reaction cutaways, no cuts inside laugh windows) and emits the set events
above. It has a `/sketch` page and a headless render CLI
(`npm run sketch:render`). Full guide, direction reference and timing
knobs: [`docs/SKETCH-SHOW.md`](SKETCH-SHOW.md).
