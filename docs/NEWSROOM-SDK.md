# Newsroom SDK (`packages/newsroom`)

Turn a news script into a directed show on the news-studio set: a rundown
goes in, a stage event timeline comes out, and the live stage (or the
headless render CLI) plays it. The SDK is generic. Channel-specific parsing
lives in that channel's own repo, in an **adapter** (see §5).

```
rundown.json ──validate──▶ layoutProgram ──▶ directShots ──▶ compile ──▶ events (t_ms)
  (Sofie-style)            (words.json or      (BBC-Ed timing      set.load · set.theme · set.camera
                            105-wpm estimate)   + news grammar)     overlay.* · dialogue.line · face.expression
                                                                    audio.sting
                                   │
            /newsroom/:id page ◀───┴───▶ packages/newsroom/cli/render.mjs → MP4
```

| File | What |
|---|---|
| `src/schema.ts` | Rundown types + dependency-free validator, `imageAllowed(lane)` |
| `src/styles.ts` | Show styles (`goodnight`, `default-news`), cadence profiles, `themePayload()` |
| `src/timing.ts` | Measured words / estimate → program clock (`layoutProgram`) |
| `src/director.ts` | Camera director (`directShots`), `newsStudioCameras()`, `isLegalCut()` |
| `src/compile.ts` | `compile(rundown, timings, opts)` → `CompiledShow`, `toShowEvents()` |
| `src/wall.ts` | `paintWallCard`: procedural wall cards, no network |
| `cli/render.mjs` | Headless rundown → MP4 / screenshots |
| `apps/live/src/pages/NewsroomPage.tsx` | `/newsroom/:id`: program feed + themed overlays, capture mode |

## 1. Concepts

### Rundown → segment → story → piece (from Sofie)

The data model follows Sofie, the open-source broadcast automation system
from NRK and SuperFly.tv (rundown → segment → part → piece):

| Sofie | newsroom | Example |
|---|---|---|
| Rundown | **Show** (`RundownV1`) | Goodnight News E01 |
| Segment | **Segment** (`kind: open \| section \| close`) | ritual open, "around the world", ritual close |
| Part | **Story** | the Jersey story |
| Piece | **Piece** | anchor read, wall card, lower third, sting |

Piece types:

| `type` | Owns time? | Fields |
|---|---|---|
| `anchor_read` | yes | `chair?`, `text`, `words?`, `emotion?`, `numbers? {figure,label}` |
| `reporter_read` | yes | `chair`, `text`, `name?`, `locale?`, `country?`, `words?`, `numbers?` |
| `wall` | no | `layout: headline\|country\|numbers\|title\|close`, `headline`, `kicker?`, `body?`, `figure?`, `credit?`, `image_url?`, `image_license?` |
| `lower_third` | no | `name`, `title?`, `hide?` |
| `ticker` | no | `items[]` |
| `jingle` | yes | `kind: open\|sting\|close`, `asset?`, `duration_ms?` |
| `ots` | no | `text`, `kicker?` (over-the-shoulder box, drawn as a wall card) |

Reads and jingles own time. Graphics fire at the start of the **next read**
in their story. A graphic placed **before a jingle** goes up with the jingle,
which is how the title card sits under the open.

**Chairs.** `cast.anchors[]` map chairs to seats (`anchor1`). Reporters are
`remote` by default. A remote reporter is "in shot" when the wall is visible:
the wall shows their country card, and the lower third shows their name and
locale. A `studio` reporter takes a seat instead.

### Timing

`layoutProgram()` uses, in order of preference:
1. `piece.words`: measured words for that line, relative ms. This is the face layer's `{word,start_ms,end_ms}` format.
2. `timings.lines[lineId]`: the same, keyed by line id (`piece.id` or `"<storyId>#<pieceIndex>"`).
3. `timings.episodeWords`: one episode-wide `words.json` on the audio clock. It is aligned to the reads in order, with greedy resync. Line starts then follow the audio.
4. A fallback **estimate** at the style's `wpm` (105 for goodnight). The words share the line's time by length, and pauses after commas and sentence ends come out of the same budget. Every line it touches gets `estimated: true`. The compiled show gets `estimated: true`, `timing_source: "estimated" | "mixed"`, and a warning.

### The camera director

**Timing follows BBC R&D's Ed** (Wright et al., IBC 2018):

* Lay out evenly spaced cuts at `(lmax + lmin) / 2`.
* Move each cut toward the nearest speech event by at most `(lmax − lmin) / 4`. A speech event is a sentence end (strength 2), a line or speaker boundary (2.5 or 3), a comma (1), or a word gap (0).
* No shot may fall outside `[lmin, lmax]`. If no legal cut exists, the shot is flagged `forced` and a warning names it. It is never hidden.

**Selection also follows Ed's guidelines:**

* Keep the speaker in shot. This is a hard constraint.
* Switch between one-shots and two-shots / 3/4 shots for variety.
* Cut away to an establishing wide now and then (`establish_every`).
* Cut away to a reaction shot now and then (`reaction_chance`). This only happens while a remote reporter speaks, so it is the anchor listening.
* Favour closer framings while someone speaks and wider ones in silence.
* Penalise recently used crops (`recent_window`).

The choice is deterministic: a PRNG seeded with the rundown id.

**Broadcast grammar is laid first, as fixed beats:**

| Beat | Shot |
|---|---|
| open | wide under the jingle → slow eased push-in to the anchor (`open_push_ms`) |
| new story | the wall headline goes up on a **wide or 3/4 (`wall-ots`)** first. The cut to the single comes after the wall has held `lmin`, and is placed so that both shots stay inside the bounds |
| reporter read | the wall's country card, plus a name · locale lower third. The figure card comes when the figure is spoken |
| numbers line | the full-wall "the numbers" card on a 3/4. The single waits until the figure has been spoken, where the bounds allow |
| section change | the sting plays on the wide. The next story's headline flashes up on that same wide |
| close | settle on the anchor for the close bones → slow pull-out to the wide (`close_pull_ms`) |

**Cut rules:**

* Never cut mid-word.
* Never cut inside the last `tail_hold_ms` (0.5 s) of a line.
* A repair pass splits or re-frames any shot that would lose its speaker.
* The same framing twice in a row is merged, or the later shot is re-framed.

On one-shots the wall behind the anchor is big and cropped. There it shows
its **ambient** layout (paper and sunrise, no text), and the card comes back
on the next wider shot.

### Show styles

A style is data: palette, fonts, wall family, lighting tint, overlay flavour,
jingle refs, the anchor's face emotion, and a **cadence profile**.
`compile()` emits it as `set.theme`. The stage tints the lights and the set,
the wall painter switches family, and the newsroom page restyles the lower
third, ticker and bug.

| | `goodnight` (sleep channel) | `default-news` (brisk) |
|---|---|---|
| lmin / lmax | **7 s / 16 s** | **2.5 s / 6 s** |
| moves | eased 2.4 s push-ins into one-shots, 7 % creep on holds | hard cuts, no creep |
| open push / close pull | 5.2 s / 7 s | 1.2 s / 2.5 s |
| wpm (estimates) | 105 | 160 |
| gaps (line / story) | 0.9 s / 1.6 s | 0.25 s / 0.5 s |
| look | paper-light sunrise wall, accent `#F5C86B` on black, serif, slow ticker | blue broadcast wall, sans, fast ticker |

The goodnight style uses no strobe, no wipes, no LIVE badge and no
breaking-news furniture. The sun on its wall "breathes" over a 22 s period.

### Wall cards

`paintWallCard(ctx, card, theme, t)` is a stage-runtime `WallPainter`.

* **Families:** `paper-sunrise` and `broadcast`.
* **Layouts:** `title`, `headline`, `country`, `numbers`, `close`, `ambient`.
* **Text fitting:** text shrinks to fit, wraps to a line cap, then ellipsizes. It never clips.
* **Images:** an image is drawn only if `compile()` passed `image_url` through, which requires `imageAllowed(lane)`. Only `verbatim-ok` (public domain / open re-use) qualifies. © news (`fact-rewrite`) and unknown lanes always get the procedural card.
* **Network:** none. The only fetch is that optional image.

## 2. Authoring a rundown

```json
{
  "schema": "freaktown.newsroom.rundown/v1",
  "id": "my-show-2026-10-22", "title": "My Show", "show_style": "goodnight", "date": "2026-10-22",
  "cast": {
    "anchors":   [{ "chair": "anchor", "name": "Anchor", "seat": "anchor1" }],
    "reporters": [{ "chair": "reporter:en-ke", "name": "Correspondent", "locale": "EN-KE" }]
  },
  "segments": [
    { "id": "open", "title": "Open", "kind": "open", "stories": [{ "id": "open-ritual", "pieces": [
      { "type": "wall", "layout": "title", "headline": "My Show", "kicker": "22 October 2026" },
      { "type": "ticker", "items": ["Story one", "Story two"] },
      { "type": "jingle", "kind": "open" },
      { "type": "anchor_read", "text": "…" } ] }] },
    { "id": "world", "title": "Around the world", "kind": "section", "stories": [
      { "id": "s1", "country": "Kenya", "source": { "name": "Example Wire", "url": "https://…", "license": "fact-rewrite" }, "pieces": [
        { "type": "wall", "headline": "Story one", "kicker": "Kenya", "credit": "Example Wire" },
        { "type": "anchor_read", "text": "From Kenya: …" },
        { "type": "reporter_read", "chair": "reporter:en-ke", "country": "Kenya", "text": "…" },
        { "type": "anchor_read", "text": "…", "numbers": { "figure": "75–1", "label": "…" } } ] } ] },
    { "id": "close", "title": "Close", "kind": "close", "stories": [{ "id": "close-ritual", "pieces": [
      { "type": "wall", "layout": "close", "headline": "My Show" },
      { "type": "anchor_read", "text": "…" },
      { "type": "jingle", "kind": "close" } ] }] }
  ]
}
```

To compile in code:

```ts
import { compile, validateRundown } from '@freaktown/newsroom';
const v = validateRundown(json);            // { ok, errors[] }: never throws
const show = compile(json, { episodeWords }); // or {} for estimates
show.events  // [{ t_ms, type, payload }] in order
show.shots   // [{ start_ms, end_ms, cue, cls, reason, move_ms?, creep?, forced? }]
```

To play or render it:

```bash
npm run build                                    # apps/live/dist
# realtime preview (vite preview / any static host of dist):
#   /newsroom/demo?rundown=/newsroom/demo-goodnight.json
# deterministic frame: /newsroom/demo?rundown=…&capture=1&t=30000
CHROMIUM_PATH=/usr/bin/chromium node packages/newsroom/cli/render.mjs rundown.json -o show.mp4 \
  [--words words.json] [--audio master.wav] [--quality high] [--fps 25] [--from ms --to ms]
node packages/newsroom/cli/render.mjs rundown.json -o show.mp4 --shots 19000,40000 --viewports desktop,mobile
```

The CLI serves `apps/live/dist` itself (no network). It frame-steps
`/newsroom?capture=1`, screenshots each frame (canvas plus DOM overlays), and
encodes with ffmpeg: silent audio, `--tone` for a quiet placeholder tone, or
`--audio`. Frames are kept in `<out>.frames/` until the encode, so a killed
render resumes where it stopped. It also writes `<out>.json` with the timing
source (**ESTIMATED** or measured), the cadence used, every shot and a
per-second camera log. Speed on 2 ARM cores with SwiftShader, 1280×720 at
`--quality high`: about 0.25 s per frame.

## 3. Adding a show style

```ts
import { registerShowStyle, withOverrides, DEFAULT_NEWS } from '@freaktown/newsroom';
registerShowStyle({
  ...withOverrides(DEFAULT_NEWS, { id: 'late-desk', cadence: { lmin_ms: 4000, lmax_ms: 9000, move_ms: 900 } }),
  name: 'Late desk', brand: 'Late Desk',
  palette: { bg: '#05050a', paper: '#eef2ff', ink: '#101426', accent: '#8fb3ff', accent2: '#ff7a59', muted: '#1b2140', glow: '#24306a' },
  wall: { family: 'broadcast', brandLine: 'LATE DESK' },
});
```

* `wall.family` chooses the painter. To add a new family, add a branch in `src/wall.ts`: one function `(ctx, card, theme, t)` that handles each layout. Use `fitText()` for every string. Keep `ambient` text-free.
* `overlay.lowerThird: 'paper' | 'broadcast'` and `overlay.ticker` style the DOM overlays in `NewsroomPage`.
* Styles must be registered in the bundle that compiles. The page compiles in-browser, so a new style has to be registered in `apps/live` before `compile()` runs there. Otherwise, compile in Node and load the timeline with `?timeline=`.

## 4. Tuning cadence

| Field | Effect |
|---|---|
| `lmin_ms`, `lmax_ms` | Ed bounds. The mean shot is about `(lmin+lmax)/2`, and the snap window is ±`(lmax−lmin)/4` |
| `move_ms` | Eased move into one-shots that follows a wider shot (0 = hard cuts) |
| `creep` | Slow push-in over a held one-shot or 3/4 (fraction of the camera-to-target distance) |
| `open_wide_ms`, `open_push_ms`, `close_pull_ms` | Ritual camera moves |
| `line_gap_ms`, `story_gap_ms` | Breath between reads and stories. These are also cut windows |
| `tail_hold_ms` | No cut in the last N ms of a line (0.5 s) |
| `wpm` | Estimate pace when there are no measured words |
| `establish_every`, `reaction_chance`, `recent_window` | Ed variety knobs |

Worked example for goodnight: even spacing is 11.5 s and the snap window is
±2.25 s. A 23 s story becomes wall-ots (headline, ≥7 s) → single, cut at the
sentence end nearest the middle. With measured words the cuts move to real
pauses. The invariants are the same either way: tests run both styles
against bounds, no mid-word cuts, speaker in shot, and headline-before-single.
Change one knob and run `npx vitest run packages/newsroom`. The snapshot in
`tests/__snapshots__` shows the new timeline shape (`-u` to accept).

## 5. Writing an adapter for another channel

An adapter turns a channel's own script format into a rundown. It lives in
**that channel's repo**, never in freaktown. Goodnight News has one at
`damn/projects/goodnight-news/studio/adapter.py`. The same shape works for
damn's `absurd-news` or `tonight-on-earth`:

1. **Parse structure, never write prose.** Map the format's markers to segments and stories: section headings, story markers, speaker tags, jingle tags. Every `text` must be copied from the script. Headlines should be verbatim (first sentence, a source title, or an owner-given slug). Figures may be re-rendered as digits, because that is a display transform. damn's EXTRACT, NEVER WRITE law applies.
2. **Chairs.** One anchor chair per seat. Reporter chairs carry `locale`, and `presence: remote` puts them on the wall. If chairs are not cast yet, use placeholder labels ("Correspondent") and say so in `meta`.
3. **Metadata.** Fill `story.source {name,url,license}` from your candidates or manifest, and set `country` (it becomes the wall kicker). The licence lane drives images through `imageAllowed()`.
4. **Numbers.** Mark at most one figure line per story with `numbers: {figure, label}`. That line gets the full-wall card.
5. **Style.** Pick a registered style, or register your own (§3). An absurd-news show would probably want `default-news` or a new brisk style. A tonight-on-earth show would want a calm one.
6. **Validate.** `validateRundown()` (TS) or your own schema check. Commit a sample rundown and a test that proves every read is verbatim.
7. **Render.** `render.mjs rundown.json --words words.json --audio master.wav`. Pass the measured words from your TTS or alignment step as soon as you have them, because estimates are only for previews.

## 6. What changed in the stage (additive only)

* **Contracts** (`packages/contracts/src/sets.ts`):
  * `set.theme` (`SetThemePayloadV1`) and `audio.sting`.
  * `set.camera` gains `move_ms` / `ease` / `creep` / `creep_ms`.
  * `overlay.headline` gains `layout` / `body` / `figure` / `credit` / `image_url` / `image_license`.
  * Existing consumers ignore the new fields.
* **`SetStage`:**
  * `cut(cue, source, {move_ms, creep})` makes eased moves and slow push-ins.
  * `theme(p)` tints the lights and the set.
  * `headline(text, kicker, card)` sends the card to a host `WallPainter` (`config.wallPainter` / `setWallPainter`).
  * `config.manual` + `renderAt(ms)` + `advanceClock(ms)` give a deterministic clock for capture: no RAF, and every timer reads show time.
* **`SetEventExecutor`** handles `set.theme` and the new `set.camera` / `overlay.headline` fields.
* **News studio:**
  * A new `wall-ots` camera preset (3/4 on anchor1 with the whole wall). It has a `portrait` override for phones; `CameraPresetDef.portrait` is a new optional field.
  * Builder support for `setWall` / `setWallPainter` / `setTheme`.
  * Named lights (`light:key` etc.) so themes can tint them.
* **`apps/live`:** the `/newsroom/:showId` page, plus `public/newsroom/demo-*.json` (placeholder text).

## 7. Tests

```bash
npx vitest run packages/newsroom        # schema (8) · director invariants ×2 styles + timing (29) · compile + snapshot (4)
cd apps/live && CHROMIUM_PATH=/usr/bin/chromium NO_PROXY=127.0.0.1 npx playwright test e2e/newsroom.spec.ts
#   wall headline appears (DOM mirror + telemetry + bright wall pixels), desktop + mobile; numbers + country cards
```

## Credits

* **Sofie** TV automation (NRK, SuperFly.tv), for the rundown → segment → part → piece model: https://github.com/nrkno/sofie-core
* **BBC R&D "Ed"**, for shot sequencing and selection rules: C. Wright, J. Allnut, R. Campbell, M. Evans, R. Forman, J. Gibson, S. Jolly, L. Kerlin, Z. Lechelt, G. Phillipson, M. Shotton, "AI in production: video analysis and machine learning for expanded live events coverage", IBC 2018: https://discovery.ucl.ac.uk/id/eprint/10103780/1/IBC2018_wrightBBC_revised_noLogo.pdf

No code was copied from either project. They supplied the model and the rules.
