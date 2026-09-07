# Freak Town Architecture Spec

> From peer review + agent analysis. Canonical reference for build decisions.

## Stack Decision

| Layer | Pick | Why |
|-------|------|-----|
| Avatars | three.ws-generated/rigged GLBs | Portable, lipsync built-in |
| Animation | Three.js AnimationMixer + visemes | Standard, well-supported |
| Cameras | Multiple PerspectiveCamera presets | One renderer, four cuts |
| Audio | Web Audio API | Browser-native, no plugins |
| TTS now | MiniMax Speech 2.8 Turbo | Performance tokens (laughs, chuckle, breath) |
| TTS quality | MiniMax Speech 2.8 HD | Keep clips worth |
| Open-source TTS | Qwen3-TTS 0.6B Base | Apache-2.0, 2.5GB, voice cloning |
| Quality ceiling | ElevenLabs | Voice changer, emotional delivery |
| Music | MiniMax Music 2.6 | Walkout stings, band sounds |
| Backend | FastAPI | Python, async, WebSocket support |
| Data | SQLite + canonical JSON | Simple, portable |
| Assets | filesystem initially; R2 later | Start simple |
| Deployment | Docker Compose | No Kubernetes |
| GPU | separate optional worker | Not on main VPS |

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
    character.json      # name, premise, voice config, walkout prompt
    avatar.glb          # three.ws rigged GLB
    voice.wav           # reference audio for cloning
    walkout.mp3         # MiniMax generated
    success_sting.mp3   # crowd goes wild
    bomb_sting.mp3      # crickets
    system_prompt.md    # personality for LLM judge
```

Drop folder into Freak Town. Character performs.

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
