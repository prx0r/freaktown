"""edge-tts voice generation service.

Generates audio from text using Microsoft Edge's free TTS.
Stores output as .mp3 files with metadata.
"""

import hashlib
import uuid
from pathlib import Path

import edge_tts

from backend.config import settings

# Voice catalog — expand as needed
VOICE_CATALOG = {
    "default": "en-US-GuyNeural",
    "ella": "en-US-AriaNeural",
    "deep_male": "en-US-DavisNeural",
    "british_male": "en-GB-RyanNeural",
    "energetic_female": "en-US-JennyNeural",
    "old_male": "en-US-GregNeural",
    "robotic": "en-US-ChristopherNeural",
    "warm_female": "en-US-AmberNeural",
    "skeptical_male": "en-US-BrandonNeural",
    "dramatic_female": "en-US-NancyNeural",
}

# Audio output directory
AUDIO_DIR = Path("data/generated/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


async def generate_speech(
    text: str,
    voice_key: str = "default",
    output_filename: str | None = None,
) -> dict:
    """Generate speech audio from text.

    Returns dict with:
      - file_path: path to generated audio
      - voice: edge-tts voice used
      - duration_ms: estimated duration
      - content_hash: hash of text+voice for dedup
    """
    voice = VOICE_CATALOG.get(voice_key, voice_key)  # allow raw voice names too

    content_hash = hashlib.sha256(f"{text}|{voice}".encode()).hexdigest()[:16]

    if output_filename is None:
        output_filename = f"{content_hash}.mp3"

    file_path = AUDIO_DIR / output_filename

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(file_path))

    # Estimate duration from file size (rough: 16kbps mp3)
    file_size = file_path.stat().st_size
    estimated_duration_ms = int((file_size / 16000) * 1000)

    return {
        "file_path": str(file_path),
        "voice": voice,
        "voice_key": voice_key,
        "duration_ms": estimated_duration_ms,
        "content_hash": content_hash,
        "text": text,
    }


async def generate_conversation_line(
    text: str,
    character_voice: str = "default",
    emotion: str | None = None,
) -> dict:
    """Generate a single conversation line for stage playback.

    Used for Ella's interview responses and contestant answers.
    """
    result = await generate_speech(text=text, voice_key=character_voice)
    result["emotion"] = emotion
    return result


async def generate_ella_line(text: str, emotion: str = "neutral") -> dict:
    """Generate Ella's speech line."""
    return await generate_conversation_line(
        text=text,
        character_voice="ella",
        emotion=emotion,
    )


def list_voices() -> list[dict]:
    """Return available voice profiles."""
    return [
        {"key": k, "voice_id": v}
        for k, v in VOICE_CATALOG.items()
    ]
