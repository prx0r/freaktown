"""Gemini Flash TTS adapter — free default with comedy tags.

Comedy tags supported:
  [short pause]  ~250ms
  [medium pause] ~500ms
  [long pause]   ~1000ms+
  [laughing]
  [sigh]
  [whispering]
  [sarcasm]
  [clears throat]

Voices: 30 voices, multi-speaker dialogue supported.
Cost: Free in Google AI Studio. ~$0.01/min in production.
"""

import json
import logging
import os
from dataclasses import dataclass

import httpx

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.models.draft import WordTiming

logger = logging.getLogger("freak_town.tts.gemini")

GEMINI_VOICES = {
    "Puck": {"name": "Puck", "gender": "male", "style": "playful"},
    "Charon": {"name": "Charon", "gender": "male", "style": "narrative"},
    "Kore": {"name": "Kore", "gender": "female", "style": "warm"},
    "Fenrir": {"name": "Fenrir", "gender": "male", "style": "deep"},
    "Aoede": {"name": "Aoede", "gender": "female", "style": "singing"},
    "Leda": {"name": "Leda", "gender": "female", "style": "youthful"},
    "Orus": {"name": "Orus", "gender": "male", "style": "firm"},
    "Zephyr": {"name": "Zephyr", "gender": "male", "style": "gentle"},
}

# Comedy tags Gemini supports
COMEDY_TAGS = {
    "pause_short": "[short pause]",
    "pause_medium": "[medium pause]",
    "pause_long": "[long pause]",
    "laugh": "[laughing]",
    "sigh": "[sigh]",
    "whisper": "[whispering]",
    "sarcasm": "[sarcasm]",
    "clear_throat": "[clears throat]",
}


class GeminiFlashTTS(TTSAdapter):
    """Google Gemini Flash TTS — free default with comedy tags."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = "gemini-2.5-flash-preview-tts"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError(
                "Gemini API key not set. Set GEMINI_API_KEY env var.\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )

        voice = voice_id or "Puck"

        # Gemini TTS uses the generateContent API with audio response
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice}
                    }
                },
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        # Extract audio from response
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        audio_data = None
        for part in parts:
            if "inlineData" in part:
                import base64
                audio_data = base64.b64decode(part["inlineData"]["data"])
                break

        if not audio_data:
            raise RuntimeError("Gemini returned no audio data")

        # Estimate word timings (Gemini doesn't provide word-level timing)
        word_timings = self._estimate_word_timings(text)
        duration_ms = self._estimate_duration_ms(text)

        return TTSResult(
            audio_bytes=audio_data,
            audio_format="wav",
            word_timings=word_timings,
            duration_ms=duration_ms,
            voice_id=voice,
            provider="gemini",
            metadata={"model": self.model, "tags_supported": list(COMEDY_TAGS.values())},
        )

    def list_voices(self) -> list[dict]:
        return [
            {"id": vid, **info, "provider": "gemini"}
            for vid, info in GEMINI_VOICES.items()
        ]

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="gemini",
            name="Gemini Flash TTS",
            description="Free default with comedy tags. ~$0.01/min in production.",
            default=True,
            free=True,
            requires_api_key=True,
            comedy_tags=list(COMEDY_TAGS.values()),
            pause_tags=["[short pause]", "[medium pause]", "[long pause]"],
            cost_per_minute=0.01,
            voices=self.list_voices(),
        )


# Singleton
gemini_tts = GeminiFlashTTS()
