"""ElevenLabs v3 adapter — quality ceiling with best tag library.

Comedy tags supported:
  [laughs]  [sighs]  [whispers]  [stammers]  [drawn out]  [rushed]

Voice cloning: instant + professional.
Cost: $0.17/min. Free tier: 10K chars/month.

API: https://elevenlabs.io/docs/api-reference
"""

import logging
import os

import httpx

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.models.draft import WordTiming

logger = logging.getLogger("freak_town.tts.elevenlabs")

COMEDY_TAGS = ["[laughs]", "[sighs]", "[whispers]", "[stammers]", "[drawn out]", "[rushed]"]


class ElevenLabsTTS(TTSAdapter):
    """ElevenLabs v3 — best quality, best tag library, $0.17/min."""

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.base_url = "https://api.elevenlabs.io/v1"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError(
                "ElevenLabs API key not set. Set ELEVENLABS_API_KEY env var.\n"
                "Get a free key at: https://elevenlabs.io/"
            )

        # Default to Rachel voice
        vid = voice_id or "21m00Tcm4TlvDq8ikWAM"

        url = f"{self.base_url}/text-to-speech/{vid}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True,
            },
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
            provider="elevenlabs",
            cost_usd=len(text) / 1000 * 0.17,
            metadata={"model": "eleven_multilingual_v2", "tags_supported": COMEDY_TAGS},
        )

    async def list_voices(self) -> list[dict]:
        if not self.api_key:
            return [{"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "provider": "elevenlabs"}]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.base_url}/voices",
                    headers={"xi-api-key": self.api_key},
                )
                r.raise_for_status()
                voices = r.json().get("voices", [])
                return [
                    {"id": v["voice_id"], "name": v["name"], "provider": "elevenlabs"}
                    for v in voices[:20]
                ]
        except Exception:
            return [{"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "provider": "elevenlabs"}]

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="elevenlabs",
            name="ElevenLabs v3",
            description="Best quality, best tag library. $0.17/min. 10K chars free.",
            free=False,
            requires_api_key=True,
            comedy_tags=COMEDY_TAGS,
            pause_tags=["[drawn out]", "[rushed]"],
            cost_per_minute=0.17,
        )


elevenlabs_tts = ElevenLabsTTS()
