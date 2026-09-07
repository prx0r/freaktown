"""Inworld TTS-2 adapter — full creative control with non-verbals.

Comedy tags supported:
  [laugh]   [breathe]   [clear throat]   [sigh]
  [giggle]  [groan]     [whisper]        [shout]

Voice cloning: yes (reference audio).
Cost: $0.15/min.

API: https://docs.inworld.ai/
"""

import logging
import os

import httpx

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.models.draft import WordTiming

logger = logging.getLogger("freak_town.tts.inworld")

COMEDY_TAGS = [
    "[laugh]", "[breathe]", "[clear throat]", "[sigh]",
    "[giggle]", "[groan]", "[whisper]", "[shout]",
]


class InworldTTS(TTSAdapter):
    """Inworld TTS-2 — full creative control, non-verbals, voice cloning."""

    def __init__(self):
        self.api_key = os.getenv("INWORLD_API_KEY", "")
        self.base_url = "https://studio.inworld.ai/v1"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError(
                "Inworld API key not set. Set INWORLD_API_KEY env var.\n"
                "Get a key at: https://inworld.ai/"
            )

        vid = voice_id or "default"

        url = f"{self.base_url}/tts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "voice_id": vid,
            "model": "tts-2",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            audio_bytes = response.content

        word_timings = self._estimate_word_timings(text)
        duration_ms = self._estimate_duration_ms(text)

        return TTSResult(
            audio_bytes=audio_bytes,
            audio_format="mp3",
            word_timings=word_timings,
            duration_ms=duration_ms,
            voice_id=vid,
            provider="inworld",
            cost_usd=len(text) / 1000 * 0.15,
            metadata={"model": "tts-2", "tags_supported": COMEDY_TAGS},
        )

    def list_voices(self) -> list[dict]:
        return [
            {"id": "default", "name": "Inworld Default", "provider": "inworld"},
        ]

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="inworld",
            name="Inworld TTS-2",
            description="Full creative control with non-verbals. $0.15/min.",
            free=False,
            requires_api_key=True,
            comedy_tags=COMEDY_TAGS,
            pause_tags=["[breathe]", "[sigh]"],
            cost_per_minute=0.15,
        )


inworld_tts = InworldTTS()
