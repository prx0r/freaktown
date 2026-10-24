# Newsroom studio (Blender 5.2): script in, episode out

One master studio, dressed by a **skin**, with any **anchor** seated, directed by a camera grammar and rendered on
free GitHub runners. Three things change per show, and none of them needs a code edit:

| You want to…            | You touch                                   | Command flag            |
|-------------------------|---------------------------------------------|-------------------------|
| make a new episode      | a script file (tagged text or JSON)         | `--script`              |
| swap the presenter      | a VRM / GLB file                            | `--anchor`              |
| add a new show look     | one JSON file in `sets/blender/news_skins/` | `--skin`                |

## Pieces

| File (sets/blender/)        | What it does                                                                                   |
|-----------------------------|------------------------------------------------------------------------------------------------|
| `newsroom_show.py`          | The one command: script → TTS → align → timeline → cards → audio mix → episode folder (→ render) |
| `newsroom_programme.py`     | Script loader and the programme clock (reads, card schedule, lower thirds, moods, stings)       |
| `newsroom_cameras.py`       | Pure-maths camera kit (12 shots) + the director: grammar, holds, cuts between words, 30° rule, headline-crop guard |
| `newsroom_build.py`         | The master studio: one Geometry Nodes graph + LED panel / brushed metal / lens node groups, lights |
| `newsroom_looks.py`         | Those node groups (LED wall face, anisotropic metal, compositor lens finish)                   |
| `newsroom_studio.py`        | Master studio + skin + anchor: stills of every camera, emotion close-ups, hero with volume haze |
| `newsroom_anchor.py`        | Any VRM/GLB at the desk: checkFace (exit 3 if it cannot express), seat, measure eye/mouth      |
| `face_express.py`           | The shared expressive map (same JSON as the web stage's `face/expressive.ts`)                  |
| `newsroom_gfx.py`           | Wall cards, desk band, bug, lower thirds, intro/outro (OFL fonts in `newsroom_fonts/`)          |
| `newsroom_episode.py`       | Direct + bake the episode onto the anchor, render a chunk (plates + anchor-only shortcut)       |
| `newsroom_finish.py`        | Overlays + grain + encode with the master, blackdetect, sample sheet, throughput               |
| `newsroom_sheets.py`        | Labelled contact sheets for review                                                             |
| `news_skins/*.json`         | The skins: goodnight, galactic, night-wire                                                     |
| `episodes/<name>/`          | An episode folder (what CI renders)                                                            |

CI: `.github/workflows/blender-newsroom-studio.yml` (Blender 5.2.2, x86-64, free `ubuntu-24.04` runners):
`check` → `stills` × skin (every camera) → `hero` → `emotions` → `swap` → `episode` × 12 chunks → `finish`
(episode.mp4, sheet.jpg, throughput.json). It runs on pushes to the PR branch and by hand (Actions → "blender
newsroom studio" → Run workflow, with `episode`, `samples`, `mode`).

## 1. A new episode from a new script

Write the script as tagged plain text (`.txt`), one read per line:

```
# Goodnight News
[open] Good evening, and welcome back to Goodnight News.
[open] Here is what the world got right today.
## Euclid discovers new comet | the European Space Agency
[tee] First: Euclid discovers new comet. From the European Space Agency.
[body] The telescope spotted it on 3 May, and astronomers are *delighted*.
## Seagrass comeback | the Marine Trust
[tee] Second: Seagrass comeback. From the Marine Trust.
[body] Meadows that vanished in the 1930s are growing back.
[close] That's all for tonight. Goodnight.
```

- `[open]` / `[close]`: consecutive lines become one read (one TTS file).
- `## title | source` starts a story: its headline goes on the wall card and the lower third.
- `[tee]` lines get the wall shot; `[body]` lines start on the medium and punch in on emphasis: a number, a word in
  `*asterisks*`, or an exclamation.
- A Goodnight-engine `script.json` (`{"lines": [{speaker, text, kind, story}], "stories": [...]}`) works as is.

Then:

```bash
python3 sets/blender/newsroom_show.py --script my_script.txt --skin goodnight \
    --anchor static/avatars/default-v1.vrm --out sets/blender/episodes/my-episode
```

This writes `sets/blender/episodes/my-episode/` with programme.json, align.json, cards/, env.json (mouth drive),
vo_dry.wav, master.wav (−14 LUFS integrated, −1.5 dBTP), episode.json. TTS is Fish Audio **s2.1-pro-free only**:
any other model is refused in code. Set `FISH_API_KEY`. Reads are cached by text, voice and speed, so a re-run is free.

To render it, commit the folder and run the workflow with `episode=my-episode` (or `--render ci` prints the exact
step). `--render local` works on an x86 box with Blender 5.2.

## 2. Swap the presenter

Pass a different `--anchor`. Any VRM or GLB works if it can express. Before anything renders, `checkFace` needs a
mouth, blink, smile and brow channel; otherwise the run stops with `ANCHOR REFUSED` (exit 3). Check a file first:

```bash
python3 sets/blender/face_express.py check path/to/character.glb
```

- Height is normalised: under 1.2 m or over 2.1 m is scaled to 1.65 m. The anchor is seated so the eyes sit at the
  desk eye-line.
- Eye and mouth heights are measured from the shapes that move them. Every camera re-solves from those numbers, so a
  taller or shorter presenter is framed the same way.
- Rigs: VRoid (J_Bip_*), VRM humanoid, Mixamo and Meshy bone names are all recognised.
- Proof stills:
  `blender -b --factory-startup --python sets/blender/newsroom_studio.py -- --skill $V2B_SKILL --skin goodnight --cards out/cards/goodnight --anchor path/to/character.glb --strict --stills out/swap --views CAM_WIDE,CAM_MEDIUM,CAM_CLOSE`
- Commit the file under `static/avatars/` and pass `--anchor` to `newsroom_show.py`, or `--anchor` to
  `newsroom_episode.py` to re-render an existing episode with a new presenter.

## 3. Add a skin (a new show look)

Copy a skin and edit the copy. A skin is one JSON file in `sets/blender/news_skins/`; its file name is its id.

```bash
cp sets/blender/news_skins/night-wire.json sets/blender/news_skins/morning-desk.json
# edit "id", then the fields below
python3 sets/blender/newsroom_gfx.py cards --skin morning-desk --sample --out /tmp/cards/morning-desk   # check the cards
```

| Key       | What it controls                                                                                      |
|-----------|-------------------------------------------------------------------------------------------------------|
| `base`    | The decor preset it starts from: `late-night`, `goodnight` or `breaking` (`newsroom_presets/`)        |
| `studio`  | Overrides of that preset's Geometry Nodes inputs: room size, trim colour, props (Globe, Laptop, LED Pillars, Second Seat) |
| `look`    | Lights (`key`, `fill`, `rim`, `kicker`, `desk`, `wash`, their `*_color`), `ambient`, `practicals`, haze, glow, fringe, vignette, grade tint, saturation, LED wall `wall_brightness` / `wall_px`, film `grain` |
| `brand`   | `title`, `tagline`, `anchor_name`, `desk_text`, `signoff`, `palette` (paper, ink, accent, lower-third and desk colours), `fonts` (any OFL font in `newsroom_fonts/` or next to the skin), `card_style`, `caps` |
| `music`   | `key`, `style` (`bells` = the Goodnight default, `pulse`, `stabs`) and `bar_s`. The music is procedural (audiopost), never a licensed track |
| `tone`    | The anchor's mood per read kind: `[emotion, intensity]` for open / tee / body / close                  |

`card_style`: `paper-sun`, `starfield` and `wire` are the built-in painters. **Any other value uses the generic
painter**, which draws a clean layout from the palette over `brand.assets.card_background` (an image path relative
to `news_skins/`). A new skin therefore needs no code at all.

Then use `--skin morning-desk` with `newsroom_show.py` or `newsroom_studio.py`. To have CI render its stills, add
it to the `stills` matrix in the workflow; that is the only edit, and it is optional. `tests/contract/test_news_skins.py` checks every skin in the folder.

## Camera kit and director

Shots: `CAM_CRANE_A`, `CAM_WIDE`, `CAM_MEDIUM`, `CAM_CLOSE` (3/4 from camera-right, 32°), `CAM_XCU` (−24°),
`CAM_DESK34`, `CAM_WALL` (the whole headline in frame), `CAM_SCREEN` (wall only, anchor out of frame),
`CAM_PUSH_A/B`, `CAM_DOLLY_A/B`, and `CAM_TWO` when a co-anchor is cast.

Rules (each is tested in `tests/contract/test_newsroom_cameras.py`):

- **Grammar:** intro crane → wide; first read → medium; each tee → wall; story body → medium, then a close on
  emphasis; inserts, push or dolly on long reads; sign-off → close, pull out wide on the last word; outro crane.
- **Holds:** at least 2.2 s per shot and at most 8.5 s while a read goes on. A move always lands before the next cut.
- **Cuts land between words:** in a pause if one is within 0.7 s, otherwise on the nearest word boundary.
- **30° rule:** a cut must change the size by two classes or the angle by at least 30°.
- **Headline guard:** the wall shows the headline only when the whole wall is in frame, or none of it. A partial
  frame (push-ins, close-ups) shows the skin's ambient art.

## Render cost

See the PR for measured numbers. The `finish` job writes `throughput.json` with:
- s/frame for full frames and for anchor-only frames (plates mode)
- the cost of each plate
- the CPU model of each runner

Local previews on an aarch64 box: Blender 5.1 needs a local-only shim, and Intel OIDN crashes there, so set
`NEWS_DENOISE=0` / `CLUB_DENOISE=0`. Never commit the shim.
