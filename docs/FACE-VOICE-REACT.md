# FACE-VOICE-REACT — expressive faces, linked to voice, that react

Three channels, one face. The invariant (from `LipSync.ts`, now enforced
on both sides of the stack):

| channel | driver | writes ONLY |
|---|---|---|
| mouth | voice audio (analyser realtime, or Rhubarb offline) | visemes / jaw |
| face | beats + reactions (smoothed, never pops) | emotion morphs |
| blink | its own timer | blink |

Channels never clear each other. Unknown values are skipped, never raised.

## 1. Voice -> mouth (speaking)

Two paths, same intents (`POG_FACE_V1` in `face_profiles.py`):

- **Offline (pre-rendered sets):** `scripts/rhubarb_cues.py` emits
  `pog.mouth-cues.v1` (poses A-H/X + jaw angle + audio sha).
  `backend/services/freaktown/face_voice.py::mouth_cues_to_face_frames`
  translates poses to viseme intents via `RHUBARB_TO_INTENT`
  (calibration v1, one dict, retunable) and resolves them to real morph
  names with `to_pog_face()`. A viseme the avatar lacks falls back to
  `jaw_open` at the pose's angle — jaw is the honest universal mouth.
- **Realtime (live, any source):** `LipSyncAdapter` reads the voice-bus
  analyser. Source-agnostic by construction: set.wav, Edge TTS, Qwen
  Omni PCM, LiveKit track, human mic all move the same mouth.

Qwen Omni's audio-out (24 kHz mono PCM chunks) plays through the voice
bus (`OmniVoiceBridge`), so the mouth moves with zero new lipsync code.

## 2. Beats -> face (expressive, no pops)

Delivery beats already carry `expression` (deadpan/excited/whisper/
shout/normal). The old path was dead: `cues.py` emitted `face_whisper`
style actions the runtime never matched (`face_` vs `face.`), so live
faces ignored beats entirely.

Fix, all additive, no contract renamed. **Full-face range, FACS
calibrated:** recipes follow AUBlendNet ICCV'25 Table 2 (Happy 6+12,
Sad 1+4+15, Surprise 1+2+5+27, Fear 1+2+4+5+7+20+26, Anger 4+5+7+9+23,
Disgust 9+5+16, Contempt 4+14+64; AU->ARKit map in `face_profiles.py`).
BEAT (76h measured ARKit weights/emotion) is the future calibration
source; current weights are the hand prior. VRM avatars keep the
5-preset path unchanged. Where emotion comes from, in priority order: (1) authored beat words, (2) room events via
`resolve_expression`, (3) Omni tone override (`emotion` + `intensity`
heard from the room's prosody), (4) procedural stillness.

## 3. Room -> face (reacting, via Qwen Omni)

The reactor is ears + improv brain, NOT lipsync. Mouth keeps running
off its own audio; the reactor only emits face/gaze/gesture intents.

```
room mic -> VAD gate (local, $0) -> reaction window?
  no  -> local energy only (laugh curve from POG presses)
  yes -> Qwen Omni realtime (hears 2-4 s, returns JSON intent)
       -> ReactionPolicy.decide -> ExpressionLayer
```

Cost discipline: Omni hears windows, not streams. A show opens at most
a handful of 2-4 s windows (laugh bursts, heckle energy, post-punch
silence). Local VAD decides when a window is worth it; cooldowns bound
the count. Key from `QWEN_API_KEY` env only — the module refuses to run
without it and stores nothing.

Reaction vocabulary (existing verbs only):

| room event | face | gesture/gaze | hold |
|---|---|---|---|
| single laugh / POG | smirk 0.7 | - | 800 ms |
| laugh burst (>=3 POG / 2 s) | smile 1.0 | lean 0.5 | 1500 ms |
| applause (sustained crowd) | smile 1.0 | lean 0.4 | 2000 ms |
| heckle (shout-band + speech) | annoyed 0.8 | gaze.audience | 1200 ms |
| silence after punch (>2.5 s) | surprised 0.4 | lean 0.6 | 1000 ms |

All thresholds live in `ReactionPolicy` (pure function, tested). Tune
without touching the reactor or the renderer.
## 4. The TalkingHead path (GLB-direct, ARKit)
The stage was VRM-only (`No VRM found in GLB` reject) while the whole
cast is GLB-first with ARKit/Oculus shapes. Now both paths exist:

- **VRM avatars:** LipSyncAdapter (analyser) + ExpressionLayer, unchanged.
- **GLB avatars:** `MorphVisemePlayer` binds whatever `viseme_*`/ARKit
  mouth morphs the file actually carries and plays the take's
  `visemes.json` (TalkingHead `speakAudio` shape, PP/FF at 0.9).
- **One rules engine:** `vendor/talkinghead/lipsync-en.mjs` (MIT, kept
  verbatim with NOTICE) converts English text to Oculus visemes.
  `scripts/build_visemes.py --take <dir>` turns `timeline.json` into
  `visemes.json`; the live client attaches it to preload as `visemes`.
  No language modules duplicated, no drift between bank and stage.

Next TTS upgrade when a voice earns it: HeadTTS/Kokoro REST (MIT, CPU
RTF 0.2, returns words + visemes + phonemes in this exact shape) or
Chatterbox-Turbo (MIT, native `[laughs]`/`[sighs]` tags — written for
puppets). Both replace edge-tts+Rhubarb for new takes; old takes keep
working (analyser fallback never removed).

## 5. Ears (Phonon, $0)

`fermion transcribe --json` (Fermion Phonon-2, Apache-2.0) gives
segments + word timestamps + hotwords (character names) on CPU/CUDA
with no account. Shape: room mic -> Phonon segments -> VAD windows ->
ReactionPolicy -> ExpressionLayer. Qwen Omni stays the paid improv
brain for windows worth hearing; everything else runs deaf on local
energy. Not installed on this box (torch deps need gigabytes and the
disk is 94%) — it belongs on the room machine, called exactly like the
GPU voice-bank pattern (render there, ship WAV/JSON back).

The reactor is ears + improv brain, NOT lipsync. Mouth keeps running
off its own audio; the reactor only emits face/gaze/gesture events on
the same cue bus scripted beats use (`sendReaction` / `MotionCue`).

```

## 6. Speech-synced upper face (AU prosody track)

Mouth says the words (visemes); the upper face moves *with* them, on
the same clock. `backend/services/freaktown/au_track.py` reads set.wav
(stdlib only) and emits `aus.json`: per-40ms frames of accent
(onsets ~ pitch accents -> AU1+AU2 brow flash), arousal (RMS level ->
AU5 eye widening), phrase_end (silence gaps -> AU45 blink + decay).
Scales are absolute (dB-anchored), so whispers read calm and shouts
read hot. `scripts/build_aus.py` builds it next to `visemes.json`;
preload carries it as `aus`, and the layer merges it under
beat/reactor emotions (prosody lifts, beats decide).

AUBlendNet verdict (ICCV'25, MIT): the model itself is not runnable
here (11 GB VRAM, Baidu-hosted data, 2-commit repo) — but its design
is adopted wholesale. AUs are the intermediate representation between
speech/emotion and blendshapes; Table 2 is our recipe authority (see
`face_profiles.py`); BEAT is the future calibration source. When a GPU
box is available, their AU->blendshape resolver slots in behind
`expression_morphs()` without touching callers.
