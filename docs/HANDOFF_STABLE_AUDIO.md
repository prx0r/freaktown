# Handoff: Stable Audio Open Small → Killella build

> For the Killella agent. Freak Town side is done up to the disk limit;
> this doc is everything needed to finish music integration over there.

## Status: link works, weights authorized, not downloaded here

- HF gated access for `stabilityai/stable-audio-open-small` is **authorized
  and verified** (range request returns 206 with real bytes).
- The HF token in agent-vault (`HF_TOKEN`) has license access. Use it via
  `Authorization: Bearer` header or `HF_TOKEN` env with huggingface_hub.
- NOT downloaded on the Freak Town VPS: disk is at 96% (~3GB free) and the
  model + torch working set needs ~2GB with safe headroom. Do it on a box
  with room.

## What to install

```bash
pip install diffusers accelerate safetensors torch  # torch CPU is fine
```

Pin what resolves for you; Freak Town venv has diffusers 0.40.0 /
accelerate 1.14.0 / torch 2.14.0 (CPU) if you want version parity.

## What to download

```python
from huggingface_hub import snapshot_download
snapshot_download(
    "stabilityai/stable-audio-open-small",
    local_dir="./models/stable-audio-open-small",
    allow_patterns=["*.safetensors", "*.json", "*.txt"],
)
```

## How to render (from Stability's own instructions)

```python
conditioning = [{"prompt": prompt, "seconds_total": 10}]
output = generate_diffusion_cond(
    model,
    steps=8,
    cfg_scale=1.0,
    conditioning=conditioning,
    sampler_type="pingpong",
    device=device,  # "cuda" if available else "cpu" — CPU works, benchmark yours
)
# then TRIM to seconds_total: Open Small fills its ~11s latent window
# and the tail past `duration` should be silence/cut.
```

Expected CPU behavior: unknown on your hardware — benchmark one 10s render
first. If 10s audio takes >45s wall clock, use the background-job UX below.

## Prompt compiler (already proven in Freak Town)

Keep the frontend contract exactly:

```json
POST /api/walkout
{"genre": "funk", "mood": "absurd", "energy": "high",
 "shape": "hit", "duration": 10, "seed": 381992}
```

Compile server-side (never expose free text):

```python
GENRES = {
  "funk":       {"instruments": "wah guitar, punchy electric bass, muted brass stabs", "bpm": 118},
  "rock":       {"instruments": "distorted power chords, punchy live drums", "bpm": 138},
  "electronic": {"instruments": "driving synth bass, neon pads, tight electronic drums", "bpm": 128},
  "jazz":       {"instruments": "walking upright bass, brushed drums, muted brass", "bpm": 108},
  "orchestral": {"instruments": "brass section, timpani, sweeping strings", "bpm": 100},
  "comedy":     {"instruments": "tuba, plucked strings, slide whistle accents", "bpm": 100},
  "hip-hop":    {"instruments": "deep 808 bass, crisp snare, hi-hat rolls", "bpm": 92},
  "disco":      {"instruments": "four-on-the-floor drums, funky bassline, string stabs", "bpm": 120},
}
SHAPES = {
  "hit":    "immediate strong entrance hit, no slow intro, front-loaded impact",
  "groove": "continuous tight groove, loop-like structure",
  "build":  "rapid build in intensity, decisive final hit",
  "fanfare": "short ceremonial fanfare phrase, clear beginning and ending",
  "weird":  "quirky characterful production, unusual sonic detail, comedic",
}

def build_walkout_prompt(recipe):
    g = GENRES[recipe["genre"]]
    return (
        "TrackType: Music, "
        "10-second instrumental comedy walk-on sting, "
        f"Genre: {recipe['genre']}, {g['instruments']}, "
        f"{recipe['mood']}, {recipe['energy']} energy, {g['bpm']} BPM, "
        f"{SHAPES[recipe['shape']]}, immediate hook in the first half second, "
        "one memorable musical motif, clean stereo production, "
        "hard decisive ending at exactly 10 seconds, no vocals, no lyrics")
```

SFX prompts use a different shape — source + action + production:

```text
TrackType: SFX, {source}, {action}, {production}
e.g. "TrackType: SFX, solo trombone, three exaggerated descending wah-wah
notes, dry cartoon comedy sting, fast decay"
```

## Cache + bundle contract (important)

- Cache key MUST cover provider + model + prompt_version + recipe + seed,
  or a prompt-compiler change will serve stale audio for the same recipe.
- `AGAIN` = same recipe, new seed only. Never mutate the prompt on AGAIN.
- Save into the freak bundle as `walkout.wav` (or `.mp3`) + `walkout.json`
  recipe sidecar. Freak Town's `save_set` already writes this shape —
  point it at real renders when available:
  `{"genre","mood","energy","shape","seed","provider","duration","audio"}`.

## Two audio classes (don't mix them)

- **Generated before performance** (walkout, exit sting, Golden Ticket theme):
  Stable Audio, background job if slow. UX: INSTANT procedural preview
  now, REAL render when ready.
- **Preloaded live bank** (rimshot, bomb, airhorn, sting): generate ~100 once,
  load into the stage AudioBus before show start, playback latency ~instant.

## Paths NOT recommended (already eliminated)

- HuggingFace Inference API: serves zero audio models (probed 4/4, all
  "not supported by provider"). Dead end, don't retry.
- MiniMax hosted music API: free tier discontinued Aug 2026; the vaulted
  MiniMax keys don't authenticate to the platform API. Dead end.
- MiniMax-Music3 self-host: 57GB weights + 24GB VRAM class GPU. Wrong
  economics for 10-second stings.
- fal Stable Audio 3 Small: plumbing built and proven, but the fal account
  has zero balance. Viable the moment it's topped up (~$22/1000 renders).

## License

Stability AI Community License. Commercial use free under $1M annual
revenue. HF account access already granted — no further clicks needed.
