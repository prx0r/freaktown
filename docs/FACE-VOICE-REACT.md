# FACE-VOICE-REACT — expressive faces, linked to voice, that react
(live-stage architecture)

Three channels, one face. The invariant (shared by LipSync,
Performer, MouthTrack): mouth = voice, face = beats + reactions,
blink = own timer. Channels never clear each other. Unknown values are
skipped, never raised.

## 1. Voice -> mouth (speaking)

Two paths, same clock (`MouthTrack.sample(t)` on the media clock):

- **Offline (sealed sets):** `scripts/rhubarb_cues.py` emits
  `pog.mouth-cues.v1` envelope spans; `scripts/build_visemes.py` emits
  `visemes.json` (TalkingHead-en full-word phonetics from
  `vendor/talkinghead/lipsync-en.mjs`, MIT). `loadSealedSet` fetches
  both; the track prefers real phonetics, falls back to vowel groups.
- **Realtime (live, any source):** `LipSyncAdapter` reads the voice-bus
  analyser. Source-agnostic: set.wav, Edge TTS, Qwen Omni PCM
  (`OmniVoiceBridge`), LiveKit track, human mic.

## 2. Beats -> face (FACS recipes on GlbAvatar)

Delivery beats carry `expression` (17 words and counting).
`Performer`'s FACE_MAP resolves actions to the 5 emotion presets;
`GlbAvatar.setExpression` renders the full FACS recipe per preset
(happy = smile + cheek squint per AU6+12; angry = brow drop + squint +
nose + press per AU4+5+7+9+23; etc. — authority: AUBlendNet Table 2,
map in `face_profiles.py`). VRM avatars keep the 5-preset path; ARKit
GLBs get brows, squint/wide eyes, cheeks, nose. Where emotion comes
from, in precedence order: (1) authored beat words, (2) room events via
`resolve_expression`, (3) Omni tone override (`emotion` + `intensity`),
(4) procedural stillness.

## 3. Room -> face (reacting, via Qwen Omni + crowd.reaction)

The reactor is ears + improv brain, NOT lipsync. Mouth keeps running
off its own audio; the reactor emits `crowd.reaction` kinds
(`to_stage_kind`: room_laugh->laugh, applause->clap, heckle->boo,
silence->crickets), which play sfx + excite the room + trigger the
matching `reaction.*` face: `omni -> ReactionPolicy -> crowd.reaction
-> Performer`.

```
room mic -> VAD gate (local, $0) -> reaction window?
  no  -> local energy only (laugh curve from POG presses)
  yes -> Qwen Omni (hears 2-4 s, returns JSON intent)
       -> resolve_expression -> crowd.reaction
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

The cast is GLB-first with ARKit/Oculus shapes. `GlbAvatar` binds
whatever `viseme_*`/ARKit morphs (plus VRM0/MMD variants) the file
actually carries and plays the take's `visemes.json` (TalkingHead
`speakAudio` shape). No VRM conversion required.

- **One rules engine:** `vendor/talkinghead/lipsync-en.mjs` (MIT, kept
  verbatim with NOTICE) converts English text to Oculus visemes.
  `scripts/build_visemes.py --take <dir>` turns `timeline.json` into
  `visemes.json`; `loadSealedSet` fetches it with the set.

Next TTS upgrade when a voice earns it: HeadTTS/Kokoro REST (MIT, CPU
RTF 0.2, returns words + visemes + phonemes in this exact shape) or
Chatterbox-Turbo (MIT, native `[laughs]`/`[sighs]` tags — written for
puppets). Both replace edge-tts+Rhubarb for new takes; old takes keep
working (analyser fallback never removed).

## 5. Ears (Phonon, $0)

`fermion transcribe --json` (Fermion Phonon-2, Apache-2.0) gives
segments + word timestamps + hotwords (character names) on CPU/CUDA
with no account. Shape: room mic -> Phonon segments -> VAD windows ->
ReactionPolicy -> crowd.reaction -> Performer. Qwen Omni stays the paid
improv brain for windows worth hearing; everything else runs deaf on
local energy. Not installed on this box (torch deps need gigabytes and
the disk is 94%) — it belongs on the room machine, called exactly like
the GPU voice-bank pattern (render there, ship WAV/JSON back).

## 6. Speech-synced upper face (AU prosody track)

Mouth says the words (visemes); the upper face moves *with* them, on
the same clock. `backend/services/funnier/au_track.py` reads set.wav
(stdlib only) and emits `aus.json`: per-40ms frames of accent
(onsets ~ pitch accents -> AU1+AU2 brow flash), arousal (RMS level ->
AU5 eye widening), phrase_end (silence gaps -> AU45 blink + decay).
Scales are absolute (dB-anchored), so whispers read calm and shouts
read hot. `scripts/build_aus.py` builds it next to `visemes.json`;
`loadSealedSet` fetches it with the set, and the tick merges it under
beat/reactor emotions (prosody lifts, beats decide, both sampled on
the media clock).

AUBlendNet verdict (ICCV'25, MIT): the model itself is not runnable
here (11 GB VRAM, Baidu-hosted data, 2-commit repo) — but its design
is adopted wholesale. AUs are the intermediate representation between
speech/emotion and blendshapes; Table 2 is our recipe authority (see
`face_profiles.py`); BEAT is the future calibration source. When a GPU
box is available, their AU->blendshape resolver slots in behind
`expression_morphs()` without touching callers.
