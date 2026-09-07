"""Freak Town config — env vars with sensible defaults."""

import os

# LLM (Ella uses OpenAI by default, switch to ANTHROPIC if you want)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELLA_MODEL = os.getenv("ELLA_MODEL", "gpt-4o-mini")

# TTS
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-GuyNeural")
TTS_VOICE_ELLA = os.getenv("TTS_VOICE_ELLA", "en-US-AriaNeural")
TTS_OUTPUT_DIR = os.getenv("TTS_OUTPUT_DIR", "audio_output")

# Show
MAX_ACTS = int(os.getenv("MAX_ACTS", "5"))
ACT_DURATION_SEC = int(os.getenv("ACT_DURATION_SEC", "60"))
