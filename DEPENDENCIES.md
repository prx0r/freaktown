# Dependencies NOT in this repo

Setup list for a fresh clone. Nothing here belongs in git.

## Python (pip — see requirements.txt / requirements-dev.txt)

Runtime: flask, httpx, pillow, boto3, edge-tts, openai, jsonschema,
fal-client, mcp, livekit-api. Dev/test: see requirements-dev.txt.

## System binaries (apt/manual)

`ffmpeg` (audio/video renders), `node` (stage runtime, contract tests),
`blender` (factory scripts in `scripts/blender_factory.py`), rclone if you
mirror media to R2. The venv in the old handover (`~/.venvs/freaktown`) is
gone — recreate from requirements.txt.

## Secrets (never commit; gitignored)

`.env`, `.hf_token` / `.hf-token` / `HF_TOKEN`, voice reference audio rights
(record with consenting performers or commercially permitted voices),
LiveKit credentials, fal keys, Cloudflare tokens, `emails/.state.json`.

## Services

LiveKit (rooms), fal (renders), OpenAI/OpenRouter (writers/judges),
Hugging Face (Qwen bank renders need `HF_TOKEN` in vault — GPU runs on
Kaggle/Colab/Vast, never this box), R2/S3 media (boto3), Meshy (bodies —
verify each model's IP status and riggability; community CC0 labels don't
clear underlying character designs).

## Runtime state (gitignored `data/`)

`data/voice-bank/` (ref.wav + transcripts + voice.json per voice),
reactions/events/funnel jsonl, portraits, beat cache. Rebuild via scripts;
never commit audio or reference recordings.

## GPU (off-box)

No GPU here. Voice-bank renders, TTS-heavy jobs and any neural lipsync go
to Kaggle/Colab/Vast. Blender runs CPU-only.
