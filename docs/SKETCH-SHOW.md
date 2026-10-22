# Sketch show: `@funnier/sketch`

Turn a written sketch into a performed, directed sketch on any stage set
(news studio, poker table, podcast, comedy club). The sketch layer is pure
data in, plain set events out: the same `TimedEvent` timeline the newsroom
compiler emits, so every SetStage host plays it (the `/sketch` page, the
render CLI, a live room).

```
script (funnier.sketch/v1)
   │  validateSketch / assertSketch            schema.ts
   ▼
identities  ── pog.* registry → names, voices, reaction delays      identities.ts
   ▼
timing      ── one clock: lines, pauses, laugh holds, moves         timing.ts
   ▼
gaze        ── who looks at whom, idle life, micro nods             gaze.ts
   ▼
director    ── comedy shot grammar + Ed cut timing                  director.ts
   ▼
compileSketch → funnier.sketch.timeline/v1 (set events)             compile.ts
```

`rundown.ts` sits beside the pipeline. It gives a whole-show template
(cold open → monologue → sketches → news desk → goodnights) and cast-size
defaults, built from aggregate sketch-show structure statistics (see
"Data" below).

---

## 1. Concepts

| term | meaning |
|---|---|
| **script** | one JSON document, `schema: "funnier.sketch/v1"`. It has a cast, scenes and timing overrides. |
| **cast entry** | `role` (what the script calls the character: `"anchor"`, `"buffer"`), `identity` (a persistent id like `pog.the-buffer`) and `seat` (a seat or mark on the set). |
| **scene** | a group of beats on one set. Most sketches have one scene. |
| **beat** | the comedy unit. `kind` is one of `setup`, `game`, `escalation`, `turn`, `punch`, `button` or `scene` (neutral). The director and gaze read the kind. For example, the first line of the `game` beat gets a wide shot so the audience sees the board, and `turn` and `punch` beats can get a camera glance. |
| **item** | a `line` or a stage direction. Items in a beat run in order on one clock. |
| **game** | the one-sentence description of what escalates. Writers need it; it is not performed. |
| **laugh window** | opened by `hold_for_laugh`. The picture holds: a cut may land at its start (usually to a reaction) but never inside it. |

**Which items own time.** Lines are sequential and own time. `pause`,
`hold_for_laugh` and `move` with `wait: true` also own time. Every other
direction fires at the cursor and overlaps the next line. With
`during: "prev"` it fires inside the previous line instead.

---

## 2. An annotated example

This is cut down from `apps/live/public/sketches/the-tell.sketch.json`
(poker table, original fiction):

```jsonc
{
  "schema": "funnier.sketch/v1",
  "id": "the-tell",                       // lowercase slug: file name, URL, render name
  "title": "The Tell",
  "set": "poker-table",                   // any set id in the stage registry
  "premise": "Three sharks try to read the one player with a perfect poker face.",
  "game": "The Buffer's 'poker face' is lag: every reaction arrives a beat late.",
  "cast": [
    { "role": "chair",  "identity": "pog.chairman-meow",    "seat": "seat1" },
    { "role": "sarge",  "identity": "pog.sergeant-sled",    "seat": "seat3" },
    { "role": "buffer", "identity": "pog.the-buffer",       "seat": "seat7" }
  ],
  "timing": { "idle_glance_chance": 0.15 },   // per-script override of DEFAULT_SKETCH_TIMING
  "scenes": [{ "id": "table", "beats": [
    { "id": "setup", "kind": "setup", "items": [
      // raw set event passthrough: the poker table deals real cards
      { "type": "prop", "event": "poker.deal", "payload": { "hand_id": "h1", "seat": 7,
        "cards": [{ "rank": "2", "suit": "clubs" }, { "rank": "7", "suit": "hearts" }] } },
      // "to" sets the addressee. The speaker's gaze goes there.
      { "type": "line", "who": "chair", "to": "camera",
        "text": "Minutes of this hand. Present: myself, the Sergeant, and the Buffer." },
      { "type": "line", "who": "sarge", "to": "buffer",
        "text": "The Buffer. Never blinks. Never flinches. I do not trust it." }
    ]},
    { "id": "game", "kind": "game", "items": [            // first line here = the game-reveal wide
      { "type": "line", "who": "sarge", "to": "buffer", "text": "I raise." },
      { "type": "look", "who": "chair", "at": "buffer", "ms": 2400 },   // overlaps what follows
      { "type": "react", "who": "buffer", "kind": "deadpan" },          // fires after the identity's reaction delay
      { "type": "pause", "ms": 1600 },                                  // silence, owns time
      { "type": "line", "who": "chair", "text": "Let the minutes show: no twitch.", "emotion": "smug" },
      { "type": "hold_for_laugh", "ms": 1100 }                          // laugh window: no cuts inside
    ]},
    { "id": "escalate", "kind": "escalation", "items": [
      { "type": "line", "who": "sarge", "to": "buffer", "text": "Fine. I am all in. Read that, you statue." },
      // during:"prev" puts the point inside the line just before it, on word 4 ("all")
      { "type": "gesture", "who": "sarge", "kind": "point", "during": "prev", "at_word": 4 },
      { "type": "react", "who": "buffer", "kind": "shock" },
      { "type": "line", "who": "buffer", "to": "sarge", "text": "Wait. Who does not trust me?" },
      { "type": "look", "who": "sarge", "at": "buffer", "double_take": true },   // glance, away, snap back
      { "type": "hold_for_laugh" }                                      // default laugh_hold_ms
    ]},
    { "id": "button", "kind": "button", "items": [
      { "type": "line", "who": "buffer", "text": "I call." },
      { "type": "button" },                // marks the button; director closes on whoever delivers it
      { "type": "blackout", "fade_ms": 900 }   // the ending. Nothing may follow it.
    ]}
  ]}]
}
```

To play it:

- **In the browser:** `/sketch` (control panel), or
  `/sketch/the-tell?demo=the-tell`, or
  `/sketch/my-sketch?script=<url-to-json>`
- **Headless MP4:** `npm run sketch:render -- apps/live/public/sketches/the-tell.sketch.json -o out/the-tell.mp4 --tone`
- **In code:**
  ```ts
  import { assertSketch, compileSketch } from '@funnier/sketch';
  assertSketch(json);                       // lists every problem, not just the first
  const c = compileSketch(json);            // { events, shots, duration_ms, estimated, warnings, … }
  // hand c.events to a SetStage host in t_ms order, or pull sketchEventsBetween(c, from, to) per frame
  ```

---

## 3. Stage-direction reference

Every item has a `type`. Roles must be cast roles; the validator rejects
unknown roles, self-looks, and anything after a blackout.

| type | fields | owns time? | notes |
|---|---|---|---|
| `line` | `who`, `text`, `emotion?`, `to?`, `words?`, `id?` | yes | `to` is a role, `camera` or `audience`. The default addressee is the previous speaker if they spoke within about 6 s, else the room. `words` holds measured word times relative to line start and overrides the WPM estimate. `emotion` becomes a `face.expression`. |
| `look` | `who`, `at`, `ms?`, `double_take?` + anchor | no | `at` is a role, `camera`, `audience`, `up`, `down`, `prop:<wall\|table\|board\|cards\|pot\|desk>`, or `{ "point": [x,y,z] }`. A look at `camera` cuts to that character's close-up. |
| `react` | `who`, `kind`, `ms?` + anchor | no | `kind` is one of `smirk`, `eye-roll`, `shock`, `deadpan`, `laugh-break`. It fires after the identity's `reaction_delay_ms`. The director cuts to the reactor and, inside a laugh hold, takes the hold's start. |
| `gesture` | `who`, `kind`, `ms?`, `intensity?` + anchor | no | `kind` is one of `point`, `shrug`, `open`, `wave`, `nod`, `lean-in`, `lean-back`, `slump`, `freeze`. |
| `move` | `who`, `to`, `ms?`, `wait?` + anchor | only with `wait` | `to` is a seat or mark id. Seats are tracked through moves, so later shots frame the new position. |
| `pause` | `ms` | yes | silence at the cursor |
| `hold_for_laugh` | `ms?` | yes | opens a laugh window after the previous line (default `laugh_hold_ms`) |
| `headline` | `text`, `kicker?`, `layout?`, `body?`, `figure?` + anchor | no | `overlay.headline` on news sets. The director cuts to the wall shot. |
| `prop` | `event`, `payload` + anchor | no | raw set event passthrough (`poker.deal`, `poker.board`, `poker.showdown`, `overlay.lower_third`, …). The director may cut to the prop shot. |
| `camera` | `cue`, `hold_ms?` + anchor | no | manual override. It takes any set cue, and `ots:a>b` / `two-shot:a+b` may use roles. It outranks everything except the open and the blackout. |
| `button` | (none) | no | marks the button line for the director |
| `blackout` | `fade_ms?`, `delay_ms?` | (the end) | `overlay.blackout`. No cuts after it. |

**Anchor** (any non-time-owning direction):

- default: at the cursor (after the previous item)
- `"during": "prev"` puts the direction inside the line right before it. Add one of:
  - `at_word` (0-based)
  - `offset_ms` from the line's start
  - `from_end_ms` before the line's end

**Director grammar** (fixed shots are laid first; Ed fills the free time):

| moment | shot |
|---|---|
| open | establishing wide |
| first line of the `game` beat | wide (the "game reveal") |
| look / react / double-take | the looker or reactor (reaction close-up) |
| headline / prop | the wall (`wall-ots`) or board shot |
| laugh hold | the picture holds |
| button | close on whoever delivers the button |
| `camera` item | exactly what you asked for |

Collisions closer than `lmin` keep the higher-ranked shot. Free time
between fixed shots gets Ed cuts (BBC R&D cadence): laid at
`(lmax+lmin)/2` and snapped up to `(lmax−lmin)/4` toward the nearest
speech boundary, never inside a word. The `sketch` cadence uses
`lmin 1.8 s` and `lmax 5 s`.

---

## 4. How identities plug in

There is no second character registry. The sketch layer reads the repo's
persistent identity system:

| source | provides |
|---|---|
| `assets/character-meshes/cast/cast-index.json` | 39 `pog.*` identities: name, mesh family, comic engine |
| `assets/character-meshes/cast/lifecycle.json` | each identity's voice |
| `assets/character-meshes/cast/motion-*.json` | `pog.motion-style.v1`: energy, confidence, nervousness, theatricality, `reaction_delay_ms`, … |

`npm run sketch:identities` (`scripts/build-identities.mjs`) snapshots
these into `src/identities.generated.json`. A drift test fails if the
snapshot falls behind the cast files.

At compile time `resolveCast()` fills each cast entry's display name and
timing traits from the registry. `toCastMembers()` turns them into the
stage's `CastMemberV1` (the `set.cast` wire type shared with the newsroom
and live sets).

- **Reaction timing is per character.** A nervous identity reacts faster
  than a deadpan one because `react` waits for that identity's
  `reaction_delay_ms`. `react_delay_ms` is only the fallback.
- **Unknown ids** (guests, humans, one-offs like `guest.wren`) are allowed
  if the cast entry carries an inline `name`. `avatar_url` picks the body:
  `basic`, `basic:robot`, `avatars/<x>.vrm` or a GLB URL.
- `listIdentities()` / `getIdentity(id)` give writers and tools the
  roster.

---

## 5. Timing tuning

The knobs live in `SketchTiming` (`DEFAULT_SKETCH_TIMING` in `schema.ts`).
Override them per script with `"timing": { … }`, or per compile with
`compileSketch(s, { timing, cadence })`.

| knob | default | raise it when… |
|---|---|---|
| `wpm` | 165 | lines feel slow (only applies to estimated timing) |
| `line_gap_ms` | 260 | dialogue feels rushed / stepped-on |
| `beat_gap_ms` | 380 | beats blur together |
| `laugh_hold_ms` | 1400 | punches don't land; lower it for a faster, drier sketch |
| `look_ms` | 1400 | looks feel twitchy |
| `double_take` | 320 / 520 / 1300 | the take reads as a glitch; widen `away_ms` |
| `react_delay_ms` | 220 | (fallback only; identity motion-style wins) |
| `react_ms` | 1500 | reactions vanish before the cut lands |
| `move_ms` | 1400 | walks look like teleports |
| `idle_glance_chance` / `idle_glance_ms` | 0.22 / 700 | listeners look frozen; lower it when the scene is a stare-down (`the-tell` uses 0.15) |
| `nod_chance` | 0.35 | listeners look dead; lower it if it gets bobble-heady |
| `camera_glance_on_turn` | true | (set false for pure fourth-wall sketches) |

**Rules of thumb:**

- **Measure, don't estimate.** Renders made from estimated timing say so
  (`timing_source: "estimated"` in the `<out>.json` beside the MP4). Once
  TTS or recorded audio exists, put measured `words` on each line (Fish
  word clocks, whisper alignments). Cuts then snap to real word
  boundaries.
- **Punch → hold → react.** For a laugh, put the `react` before or just
  inside the `hold_for_laugh`. The director then cuts to the reactor at
  the hold's start, which is the classic laugh cutaway.
- **Lead the line with gestures.** Use `during: "prev"` with `at_word` on
  the operative word rather than a free-floating direction afterwards.
- **Ed's spacing comes from cadence, not timing.** To make the cutting
  busier or calmer, pass `cadence: { ...SKETCH_CADENCE, lmin_ms, lmax_ms }`.

---

## 6. Extending

| you want… | do this |
|---|---|
| a new **reaction** or **gesture** | Add it to `ReactionKind`/`GestureKind` (and the `*_KINDS` arrays) in `schema.ts`, then map it to face actions in `REACTION_ACTIONS`/`GESTURE_ACTIONS` (`compile.ts`). If it needs a new face action, add it in the stage face layer (LIVE-STAGE-EXTENDING §10). |
| a new **direction type** | Add the item interface to `schema.ts` (with `ITEM_TYPES` and validation), place it on the clock in `timing.ts` (decide whether it owns time), emit events in `compile.ts`, and give it a shot rule plus a `RANK` in `director.ts` if it should drive the camera. |
| a new **set** | Make the set (LIVE-STAGE-EXTENDING §8). For sketches you only need seat/mark ids and the standard cue grammar (`wide`, `single:`, `close:`, `reaction:`, `two-shot:`, `ots:`). Add a `prop` shot in `cameraTableFor()` if the set has a hero prop. |
| set-specific **props** | No code: use `{ "type": "prop", "event": "<set event>", "payload": {…} }`. The executor already understands it. |
| a new **identity** | Add it to the cast files under `assets/character-meshes/cast/`, run `npm run sketch:identities`, and commit the regenerated snapshot. |
| a different **show shape** | `showRundownTemplate({ sketches, filmed, sets })`. Defaults come from `data/structure-stats.json`. |

Doctrine (same as the newsroom): the stage obeys events only, and
compiling is deterministic. Seeded gaze and idle life mean the same
script gives the same timeline. Tests pin this.

---

## 7. Data: sketch-show structure statistics

`data/structure-stats.json` holds aggregate counts (903 episodes, seasons
1–46, 13,704 segments): segment order, live/filmed counts, cast size per
segment type, how often sketches recur, and rundown shapes. It was built
by `scripts/snl_structure_stats.py` from
[hhllcks/snldb](https://github.com/hhllcks/snldb), which was scraped from
[snlarchives.net](https://snlarchives.net).

snldb has **no LICENSE**, so only derived aggregates are committed. The
repo holds no raw files, scripts, transcripts, or performer, character or
sketch names. Raw downloads stay outside the repo and are gitignored
(`data/snldb/`, `**/snldb/`).

---

## 8. Tests

- `packages/sketch/tests/`:
  - `schema.test.ts`: the validator and its error lists
  - `director.test.ts`: grammar, no cuts in laugh windows, `lmin` spacing, word-boundary snapping
  - `gaze.test.ts`: precedence order, determinism
  - `identities-rundown.test.ts`: registry drift, cast resolution, rundown defaults
- `apps/live/e2e/sketch.spec.ts`: `/sketch` loads the demos, compiles,
  and plays in capture mode, and the stage follows the compiled shots and
  looks.

---

## 9. Roadmap

1. **LLM writer → schema.** A writer agent takes a premise, a game and a
   cast picked from the identity roster, and emits `funnier.sketch/v1`.
   - `validateSketch()` is the contract. Its error list feeds straight
     back to the model for repair.
   - Beat kinds give the model the shape (setup → game → escalation →
     turn → punch → button).
   - `rundown.ts` cast-size ranges keep casts realistic per segment type.
   - Each identity's `engine` line (its comic engine) is the character
     brief.
2. **Measured audio in the loop.** TTS per line (identity voice from
   `lifecycle.json`) → word clocks → `words` on every line → re-compile.
   Timing becomes `measured` and the director snaps to real words.
3. **Live agents improvising within beats.** The script fixes the beats
   (kind, who's in it, the game, the button). Character agents improvise
   the lines inside each beat in real time, within a time budget per beat.
   - The timing and director layers run incrementally on the lines
     produced so far, using the same doctrine as the live room.
   - `hold_for_laugh` windows can open from real audience signal instead
     of being fixed.
   - The blackout still belongs to the script.
4. **Show assembly.** `showRundownTemplate()` → one script per slot
   (cold open on the comedy club, news desk on the news studio) → a
   single show render, with recurring sketches reusing scripts the way
   about a fifth of real live sketches are installments.
