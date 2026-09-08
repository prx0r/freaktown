"""MiniMax Speech 2.8 adapter — default TTS with comedy tags.

Comedy tags supported:
  (laughs)     (chuckle)    (breath)     (groans)
  (sighs)      (snorts)     (humming)    (clears throat)

Voice cloning: 10 seconds to 5 minutes of reference audio.
Cost: ~$0.01/min (Turbo), ~$0.03/min (HD).

API: https://platform.minimax.io/docs/api-reference
"""

import base64
import logging
import os

import httpx

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.models.draft import WordTiming

logger = logging.getLogger("freak_town.tts.minimax")

MINIMAX_VOICES = {
    "Calm_Woman": {"name": "Calm Woman", "gender": "female", "style": "calm"},
    "Confident_Woman": {"name": "Confident Woman", "gender": "female", "style": "confident"},
    "Gentle_Woman": {"name": "Gentle Woman", "gender": "female", "style": "gentle"},
    "Warm_Woman": {"name": "Warm Woman", "gender": "female", "style": "warm"},
    "Narrator_Man": {"name": "Narrator Man", "gender": "male", "style": "narrative"},
    "Deep_Voice_Man": {"name": "Deep Voice Man", "gender": "male", "style": "deep"},
    "Young_Man": {"name": "Young Man", "gender": "male", "style": "youthful"},
    "Old_Man": {"name": "Old Man", "gender": "male", "style": "elderly"},
}

COMEDY_TAGS = [
    "(laughs)", "(chuckle)", "(breath)", "(groans)",
    "(sighs)", "(snorts)", "(humming)", "(clears throat)",
]


class MiniMaxTTS(TTSAdapter):
    """MiniMax Speech 2.8 — default provider with comedy performance tags."""

    def __init__(self):
        self.api_key = os.getenv("MINIMAX_API_KEY", "")
        self.group_id = os.getenv("MINIMAX_GROUP_ID", "")
        self.base_url = "https://api.minimax.chat/v1"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError(
                "MiniMax API key not set. Set MINIMAX_API_KEY env var.\n"
                "Get a key at: https://platform.minimax.io/"
            )

        voice = voice_id or "Calm_Woman"

        url = f"{self.base_url}/t2a_v2"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "speech-02-turbo",
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if "data" not in data or "audio" not in data.get("data", {}):
            raise RuntimeError(f"MiniMax returned no audio: {data}")

        audio_hex = data["data"]["audio"]
        audio_bytes = bytes.fromhex(audio_hex)

        # MiniMax doesn't provide word-level timing — estimate
        word_timings = self._estimate_word_timings(text)
        duration_ms = self._estimate_duration_ms(text)

        return TTSResult(
            audio_bytes=audio_bytes,
            audio_format="mp3",
            word_timings=word_timings,
            duration_ms=duration_ms,
            voice_id=voice,
            provider="minimax",
            metadata={"model": "speech-02-turbo", "tags_supported": COMEDY_TAGS},
        )

    def list_voices(self) -> list[dict]:
        return [
            {"id": vid, **info, "provider": "minimax"}
            for vid, info in MINIMAX_VOICES.items()
        ]

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="minimax",
            name="MiniMax Speech 2.8",
            description="Default TTS with comedy performance tags. ~$0.01/min.",
            default=True,
            free=False,
            requires_api_key=True,
            comedy_tags=COMEDY_TAGS,
            pause_tags=["(breath)", "(sighs)"],
            cost_per_minute=0.01,
            voices=self.list_voices(),
        )


minimax_tts = MiniMaxTTS()
