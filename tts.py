"""Text-to-speech via edge-tts (free, no API key)."""

import asyncio
import hashlib
import os
from pathlib import Path

import edge_tts

OUTPUT_DIR = Path(os.getenv("TTS_OUTPUT_DIR", "audio_output"))


async def synthesize(text: str, voice: str = "en-US-GuyNeural", filename: str | None = None) -> Path:
    """Generate speech audio file. Returns path to the MP3."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not filename:
        h = hashlib.sha256(text.encode()).hexdigest()[:12]
        filename = f"{h}.mp3"

    out_path = OUTPUT_DIR / filename
    if out_path.exists():
        return out_path

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))
    return out_path


def synthesize_sync(text: str, voice: str = "en-US-GuyNeural", filename: str | None = None) -> Path:
    """Sync wrapper for synthesize."""
    return asyncio.run(synthesize(text, voice, filename))
