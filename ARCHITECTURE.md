# Freak Town Architecture Spec

> Canonical reference for build decisions. Truth as of Checkpoint 1:
> what prod actually runs, not what was planned. Aspirations live in
> devplan.md, not here.

## Stack Decision (prod reality)

| Layer | Pick | Why |
|-------|------|-----|
| Avatars | BASIC rigged GLB (guaranteed) → three.ws forge_avatar (AI upgrade) → user upload | $0 instant base; provider-neutral manifest |
| Avatar truth | `avatar.json` (freak.character/v1), capabilities sniffed from bytes | Stage reads capabilities, never extensions |
| Animation | Procedural sway + analyser jaw morphs; VRM expressions where rig has them | Honest motion, never faked mouths |
| Cameras | Multiple PerspectiveCamera presets | One renderer, four cuts |
| Audio | Web Audio API | Browser-native, no plugins |
| TTS | edge-tts (free) + espeak fallback | Compositor owns silence; measured offsets |
| Music | Procedural synth: pattern riffs + seeded melody mode | Deterministic per (recipe, seed) |
| Product backend | Flask (`app.py`, strangler) | Serves everything live today |
| Infra backend | FastAPI + Postgres (imported, not yet serving) | Future durable truth |
| Live state | PartyRoom SSE / EpisodeRoom DO (imported) | Persist-then-broadcast |
| Data now | Filesystem bundles + JSONL | Portable; repository interfaces ready |
| Assets | Filesystem + R2 mirror on share | `freak-town` bucket, manifest-driven |
| Deployment | systemd unit (`deploy/`) | Auto-restart; CI gates on push |

## TTS Provider Interface (build this first)

```python
class TTSProvider(Protocol):
    async def generate(self, text: str, voice: str, **kwargs) -> bytes: ...

class MiniMaxTTS(TTSProvider): ...
class QwenTTS(TTSProvider): ...
class ElevenLabsTTS(TTSProvider): ...
class EdgeTTS(TTSProvider): ...  # fallback
```

Switching providers should require zero frontend changes.

## Character Bundle Format

```
freaks/
  conspiracy-pigeon/
    character.json      # identity, persona, voice, profile, actions
    avatar.glb / avatar.vrm  # performer body, either format as-is (optional)
    avatar.json          # capability manifest, freak.character/v1 (REQUIRED if body present)
    voice_reference.wav # cloning source (optional)
    portrait.png        # 2D concept (optional)
    delivery.json       # performance score v1 (optional until first set)
    set.wav             # composed clip (optional until composed)
    walkout.wav         # entrance sting (optional)
    meta.json           # status, hashes, timestamps (tool-written)
```

Drop folder into Freak Town. Character performs.
Full contract: docs/CHARACTER_PACK.md. Validate: scripts/validate_pack.py.

## One Audio Timeline (core abstraction)

```text
               MASTER
                  │
       ┌──────────┼───────────┐
       │          │           │
     VOICE       MUSIC       SFX
       │          │           │
 comedian      walkout     rimshot
 Ella          outro       boos
                           applause
```

Everything goes through Web Audio. This is the bit to protect obsessively.

## Camera System

Four presets, one renderer:

```
1 — WIDE     (whole stage)
2 — MEDIUM   (waist-up comedian)
3 — CLOSE    (face / punchline)
4 — SIDE     (club-style audience angle)
```

`director.cut("close")` changes activeCamera.

Log every cut:
```json
{"type": "camera_switch", "camera": "close", "set_time_seconds": 23.418}
```

After 100 sets → training data for automatic comedy director.

## MiniMax Music: Generate Once, Cache Forever

Character walkout generated at creation time:

```json
{
  "walkout": {
    "prompt": "sleazy 1980s cop-show funk, absurdly heroic saxophone",
    "provider": "minimax",
    "asset": "walkout.mp3",
    "start": 8.2,
    "duration": 8.0
  }
}
```

Character-specific walkouts:
- Conspiracy Pigeon → paranoid military snare + pigeon coos
- Corporate Robot → horrible hold music → bass drop
- Medieval LinkedIn Guy → Gregorian chant → motivational EDM
- Roomba → grand orchestral → vacuum cleaner noise

Band sound bank: 20-50 pre-generated drum hits, riffs, rimshots, stings.

## Deployment

```text
Docker Compose

freaktown-web       Three.js / TS
freaktown-api       FastAPI
freaktown-db        SQLite volume
freaktown-assets    GLB / WAV / MP3 / JSON

optional:
qwen-tts            GPU worker
```

GPU worker pattern:
```text
GPU box → generate 100 voices/sets → send WAV back → kill GPU
```

## Performance Tokens (MiniMax)

Sets can contain performance markup:

```text
I finally told my therapist I'm an AI.

(chuckle)

She said, "I know."

...which is honestly incredibly fucking rude.

(breath)

I'm paying her.
```

Available: (laughs), (chuckle), (breath), (groans), (sighs), (snorts), (humming)

## VPS Architecture

```text
8GB VPS (orchestrate, don't generate)
   │
   ├── Freak Town web/API/database
   ├── cached MP3/WAV
   └── TTS router
          ├── MiniMax      ← default now
          ├── ElevenLabs   ← quality oracle
          └── Qwen GPU     ← open route
```
