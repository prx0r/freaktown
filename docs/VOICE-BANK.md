# Voice bank — 5-second clones that set this on fire

One 3–10s clean clip + its transcript = a full TTS voice for any pog.
Engine: Qwen3-TTS Base (Apache-2.0, SOTA 3-sec clone, 10 languages,
streaming). Needs a CUDA GPU, so renders happen on Kaggle/Colab/Vast —
never on this box. `HF_TOKEN` lives in the vault (`main`), same pattern
as `kaggle-walkouts/`.

## Contract: `data/voice-bank/<voice-id>/`

- `ref.wav` — 3–10s, single speaker, no music/noise, natural pace.
- `ref.txt` — exact transcript of ref.wav (Qwen needs the pair).
- `voice.json` — `{id, label, ref_wav, ref_text, ready}`.
  `ready: true` only after a rendered cache exists; the revoice page lists
  ★ bank voices automatically once ready.

## Render job (GPU)

`scripts/qwen_bank_render.py` reads a job file
`{voice_id, ref_wav, ref_text, lines: [...]}` and writes one wav per line
into the bank dir. Run it on Kaggle free T4 (see `kaggle-walkouts/`
for the secrets pattern) or any CUDA box. First bank target: your own
silly voices performed into the mic — original, ownable, no IP risk.

## The one rule

Clone voices you own or have permission to use: your own performances,
VoiceDesign descriptions, presets, willing friends. Never rip protected
cartoon/celebrity voices into the bank — that poisons the asset.

## Lanes today

- edge-tts (6 voices): free, keyless, instant. Default everywhere.
- Kokoro (4 voices): free, local CPU, clearly warmer. Revoice-ready now.
- bank ★ (Qwen clones): your cast. Scaffolded; first render needs a GPU.
- ElevenLabs oracle: later, behind the same router, for hero renders.
