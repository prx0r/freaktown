#!/usr/bin/env python3
"""Qwen3-TTS voice-bank render job. RUNS ON GPU ONLY (Kaggle T4 / Vast / Colab).

Reads HF_TOKEN from env (Kaggle user secret, same pattern as kaggle-walkouts/).
Job file: {"voice_id": "...", "ref_wav": "...", "ref_text": "...",
           "lines": [{"key": "hello", "text": "..."}]}
Writes bank/<voice_id>/line-<key>.wav + flips voice.json ready=true.

Usage (GPU box):
  pip install qwen-tts soundfile torch --index-url https://download.pytorch.org/whl/cu121
  HF_TOKEN=... python3 scripts/qwen_bank_render.py job.json
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BANK = HERE / "data" / "voice-bank"


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text())
    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("Attach HF_TOKEN and re-run.")
    import torch
    import soundfile as sf
    from qwen_tts import Qwen3TTSModel

    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-0.6B-Base", device_map="cuda:0",
        dtype=torch.float16)  # float16: T4/sm_75 has no bfloat16 kernels
    vdir = BANK / job["voice_id"]
    vdir.mkdir(parents=True, exist_ok=True)
    for line in job["lines"]:
        wavs, sr = model.generate_voice_clone(
            text=line["text"], language="English",
            ref_audio=job["ref_wav"], ref_text=job["ref_text"])
        sf.write(str(vdir / f"line-{line['key']}.wav"), wavs[0], sr)
        print("rendered", line["key"])
    meta = json.loads((vdir / "voice.json").read_text())
    meta["ready"] = True
    (vdir / "voice.json").write_text(json.dumps(meta, indent=2))
    print("bank voice ready:", job["voice_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
