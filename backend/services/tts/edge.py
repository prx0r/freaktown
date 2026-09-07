"""Edge TTS adapter — free fallback, no comedy tags.

Cheapest option: $0. No API key needed. Decent quality.
No pause/comedy tag support — use for quick iteration only.
"""

import asyncio
import logging
import os

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.models.draft import WordTiming

logger = logging.getLogger("freak_town.tts.edge")

EDGE_VOICES = {
    "en-US-GuyNeural": {"name": "Guy", "gender": "male", "style": "neutral"},
    "en-US-AriaNeural": {"name": "Aria", "gender": "female", "style": "warm"},
    "en-US-DavisNeural": {"name": "Davis", "gender": "male", "style": "confident"},
    "en-US-JennyNeural": {"name": "Jenny", "gender": "female", "style": "friendly"},
    "en-US-TonyNeural": {"name": "Tony", "gender": "male", "style": "casual"},
    "en-US-AndrewNeural": {"name": "Andrew", "gender": "male", "style": "narrative"},
    "en-GB-RyanNeural": {"name": "Ryan", "gender": "male", "style": "british"},
    "en-GB-SoniaNeural": {"name": "Sonia", "gender": "female", "style": "british"},
    "en-AU-WilliamNeural": {"name": "William", "gender": "male", "style": "australian"},
}


class EdgeTTSAdapter(TTSAdapter):
    """Microsoft Edge TTS — free, no API key, no comedy tags."""

    def __init__(self):
        self.default_voice = "en-US-GuyNeural"

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        try:
            import edge_tts
        except ImportError:
            raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

        voice = voice_id or self.default_voice
        word_timings: list[WordTiming] = []
        audio_chunks: list[bytes] = []

        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.append(chunk["data"])
                    elif chunk["type"] == "SentenceBoundary":
                        sent_offset_ms = chunk["offset"] / 10000
                        sent_duration_ms = chunk["duration"] / 10000
                        words = chunk["text"].split()
                        if words:
                            word_duration = sent_duration_ms / len(words)
                            for i, word in enumerate(words):
                                start = sent_offset_ms + (i * word_duration)
                                word_timings.append(WordTiming(
                                    word=word,
                                    start_ms=int(start),
                                    end_ms=int(start + word_duration),
                                    index=len(word_timings),
                                ))
                break
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(2 + attempt * 2)
                    audio_chunks = []
                    word_timings = []
                    continue
                raise RuntimeError(f"Edge TTS failed after 3 attempts for voice={voice}")

        audio_bytes = b"".join(audio_chunks)
        duration_ms = word_timings[-1].end_ms + 500 if word_timings else self._estimate_duration_ms(text)

        return TTSResult(
            audio_bytes=audio_bytes,
            audio_format="mp3",
            word_timings=word_timings,
            duration_ms=duration_ms,
            voice_id=voice,
            provider="edge",
            cost_usd=0.0,
        )

    def list_voices(self) -> list[dict]:
        return [
            {"id": vid, **info, "provider": "edge"}
            for vid, info in EDGE_VOICES.items()
        ]

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="edge",
            name="Edge TTS",
            description="Free fallback. No comedy tags. Good for quick iteration.",
            free=True,
            comedy_tags=[],
            pause_tags=[],
            cost_per_minute=0.0,
            voices=self.list_voices(),
        )


# Singleton
edge_tts_adapter = EdgeTTSAdapter()
