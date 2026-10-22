# Party games vs agents

FUNNIER party games put a human at a table with **agent players**. Each agent is a persistent character with its own identity, persona and taste. The first game is **Try Not To Smile (TNTS)**.

Code: `packages/party` holds the pure engine, agents, identities and jokes. `apps/live/src/pages/TntsPage.tsx` is the `/tnts` room. `apps/live/src/party/faceSource.ts` holds the webcam, recorded and synthetic face feeds.

## Play TNTS vs agents (local)

```bash
npm install                                   # once (workspace)
npm run dev                                   # vite on http://127.0.0.1:5173
open http://127.0.0.1:5173/tnts               # desktop or phone on the same network (vite --host)
```

1. **Use my camera.** The browser asks for webcam permission. MediaPipe FaceLandmarker (blendshapes) loads from the jsDelivr CDN and Google's model bucket and runs **on the device**.
2. **Calibration (3 s).** Hold a neutral face. Your neutral smile level becomes your personal baseline.
3. **Start.** The agents (Doug Deadline, Madame Chrysalis, The Algorithm) take turns delivering bits through the stage.
   - On **your** turn you tell the table a joke out loud, then tap **PUNCHLINE!** The agents react from their taste models.
4. **Keep a straight face.** A smile above the threshold (0.5, relative to your neutral) held for **400 ms** costs a life. At 0 lives you are out and keep watching as a spectator.

Variants:

| URL | what |
|---|---|
| `/tnts?spectate=1` | agents only; you watch |
| `/tnts?feed=synthetic&grin=8000` | no camera: a synthetic face, neutral, grinning from 8 s |
| `/tnts?feed=recorded&src=/tnts/feeds/grin-after-6s.json` | the fake webcam: a recorded blendshape stream |
| `?lives=1&hold=400&threshold=0.5&rounds=3&turn=15000` | rules |
| `?seed=x&agents=pog.doug-deadline,pog.pete-pebble` | table |
| `?capture=1` | deterministic, `window.__tnts.renderAt(ms)` (screens/MP4) |

Tests:

```bash
npx vitest run packages/party                                   # rules, calibration, taste, game, identities
cd apps/live && npx vite build && CHROMIUM_PATH=/usr/bin/chromium NO_PROXY=127.0.0.1 npx playwright test e2e/tnts.spec.ts
```

Render the simulated round: synthetic human blendshapes; the human grins from 42 s. Frames resume across runs:

```bash
cd apps/live && CHROMIUM_PATH=/usr/bin/chromium node e2e/capture-page.mjs --path "/tnts?capture=1&seed=tnts-demo" \
  --api __tnts --mp4 tnts.mp4 --fps 10 --frames /tmp/tnts-frames --budget 100   # re-run until it encodes
```

## Rules engine (`packages/party/src/rules.ts`)

A pure reducer: `step(state, action) → { state, events }`. Time comes in on every action, so the same input list always replays to the same result.

- **Turns:** players perform in seat order and the game moves through rounds. A turn ends when the agent's bit finishes, 3.5 s after the human's punchline, or on `turnMs`. Anyone who is out is skipped. The game ends when one face is left standing, or after `rounds` (most lives wins, then most points).
- **Break:** if the adjusted smile stays above `smileThreshold` for `holdMs`, the player takes a strike. Every `strikesPerLife` strikes costs a life. The performer gets **+1 point** for each break they cause, and is never judged during their own turn.
- **Continuity:** a gap of more than `maxGapMs` (250) between samples resets the hold, so dropped frames can't join two short twitches into one break.
- **Grace:** for `graceMs` (1.5 s) after a break, the same player can't break again.
- **Spectators:** late joiners and `spectate` actions watch and are never judged. Players who are out become spectators in the UI.

## Privacy

- Video never leaves the browser. MediaPipe runs in the page, and only the **smile score** (a number) and game events go into the rules engine. In local play nothing leaves the device at all. In a shared room, only scores and events are sent.
- No frames are uploaded or stored, and no training happens on them.
- **Opt-in video:** sharing your camera with the table needs a media plane (LiveKit, `livekit_adapter.py`). It is **off by default**, and with no LiveKit configured there is nothing to share it with.
- The tile reads "video stays on this device · only scores leave".

## Calibration and fairness

- **Neutral calibration** (`calibration.ts`): the median of about 3 s of samples. A robust spread check rejects noisy calibrations (moving or talking). A "neutral" above 0.6 is rejected as a smile. Too few face frames gets the message "face the camera, light in front".
- **Resting smilers:** every sample is scored as `(raw − baseline) / (1 − baseline)`. A face whose neutral already reads 0.3 is judged on the *change* from it. The UI says "resting-smile adjusted". The hold time is the same for everyone.
- **Lighting:** a luma reading of the camera frame is checked every 500 ms. Below `minLuminance` (0.18), judging is **paused** for that player with a warning ("Too dark to read your face"). No strike is given for a face the referee can't see.

## Agent smiles are simulated (honest)

Agents have no faces to measure. Each agent has a **taste model** (`taste.ts`): mechanism weights from −1 to 1, composure, volatility and reaction latency.

- `rating` = taste × the joke's mechanisms + the writer's quality estimate + seeded noise − fatigue.
- `p(crack) = sigmoid((rating − composure) × 9)`.

One seeded draw decides between a crack and a fought-off twitch. The result is a smile **curve**. It goes into the **same rules** as human samples with `simulated: true`, and shows on the agent's face via `face.expression` (happy, at peak intensity). Every agent meter is labelled "smile: simulated (taste model)", and agent breaks say "(simulated)".

## Joke sources (`jokes.ts`)

- `ORIGINAL_DECK`: 32 original one-liners and short bits written for FUNNIER, tagged by mechanism.
- `TemplateJokeSource`: original combinatorial frames × subjects × twists.
- `LlmJokeSource`: the hook for a model later. It is **disabled** unless a caller injects `complete(prompt)`. There are no network calls and no spend.

The `party.py` decks are prompts for humans, not agent material, so they are not used.

## Add a game

1. Write a pure reducer next to `rules.ts` (`initialState`, `step`, `replay`). Keep time and randomness as inputs.
2. Add an orchestrator like `TntsGame` that turns agent decisions into `StageCue`s. The cues are set-stage events: `set.load`, `dialogue.line`, `face.expression`, `set.camera`.
3. Add a page that runs the stage in `manual` mode and calls `stage.renderAt(t)` from its own loop. Expose `window.__<game>.renderAt` for capture.
4. Add vitest tests for the reducer and a Playwright spec with a fake feed.

## Add an agent player

- **A resident:** add a party profile (persona plus taste) for a `pog.*` cast identity in `RESIDENT_PROFILES` (`identity.ts`). The name, voice and motion come from the cast registry, so there is no parallel cast. Seat it with `?agents=pog.x,…` or `new TntsGame({ agents: [...] })`.
- **Agent-made:** see the identity flow below.
