# Extending the live stage

Companion to [`LIVE-STAGE.md`](LIVE-STAGE.md). Every recipe keeps the three
rules: **contracts in one place** (`packages/contracts`), **control only sends
commands**, **the stage only obeys events**. Paths are from the repo root.

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
import { adaptSealedSet } from '@freaktown/stage-runtime';
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
SHOTS_DIR=/tmp/shots npx playwright test   # where screenshots go (default /workspace/work/freaktown-live/shots)
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
- **news-studio** — anchors `anchor1`/`anchor2` seated behind a curved FREAK NEWS desk;
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
