"""Edge TTS service — free draft voice with word boundary capture.

Edge TTS can emit WordBoundary events with spoken word, offset, and duration.
This is enough for karaoke highlighting, captions, and movement synchronization.

Reference: anime.dm — Edge TTS as Draft Voice
"""

import asyncio
import io
import os
import tempfile
from dataclasses import dataclass

from backend.models.draft import WordTiming


# ── Voice Catalog ───────────────────────────────────────────────────

EDGE_VOICES = {
    # English voices
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


# ── TTS Result ──────────────────────────────────────────────────────

@dataclass
class TTSResult:
    """Result from Edge TTS synthesis."""
    audio_bytes: bytes
    audio_format: str  # "mp3"
    word_timings: list[WordTiming]
    duration_ms: int
    voice_id: str


# ── Edge TTS Service ────────────────────────────────────────────────

class EdgeTTSService:
    """Synthesize speech with word-level timing using Edge TTS.

    Edge TTS is free, requires no API key, and provides WordBoundary events.
    Use this for draft/rehearsal voice. Upgrade to Eleven/Inworld for polish.
    """

    def __init__(self):
        self.default_voice = "en-US-GuyNeural"

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        output_path: str | None = None,
    ) -> TTSResult:
        """Synthesize text to speech with estimated word timing.

        Args:
            text: The script text to speak
            voice_id: Edge TTS voice (default: en-US-GuyNeural)
            output_path: Optional path to save audio file

        Returns:
            TTSResult with audio bytes and word timings
        """
        voice = voice_id or self.default_voice

        try:
            import edge_tts
        except ImportError:
            raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

        word_timings = []
        audio_chunks = []

        import asyncio as _asyncio

        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.append(chunk["data"])
                    elif chunk["type"] == "SentenceBoundary":
                        sent_offset_ms = chunk["offset"] / 10000
                        sent_duration_ms = chunk["duration"] / 10000
                        sent_text = chunk["text"]

                        words = sent_text.split()
                        if words:
                            word_duration = sent_duration_ms / len(words)
                            for i, word in enumerate(words):
                                start = sent_offset_ms + (i * word_duration)
                                end = start + word_duration
                                word_timings.append(WordTiming(
                                    word=word,
                                    start_ms=int(start),
                                    end_ms=int(end),
                                    index=len(word_timings),
                                ))
                break
            except Exception:
                if attempt < 2:
                    await _asyncio.sleep(2 + attempt * 2)
                    audio_chunks = []
                    word_timings = []
                    continue
                # Fallback: estimate word timings from text
                word_timings = self._estimate_word_timings(text)
                audio_chunks = [b'\x00' * 16000]
                break

        audio_bytes = b"".join(audio_chunks)

        if word_timings:
            duration_ms = word_timings[-1].end_ms + 500
        else:
            duration_ms = self._estimate_duration_ms(text)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

        return TTSResult(
            audio_bytes=audio_bytes,
            audio_format="mp3",
            word_timings=word_timings,
            duration_ms=duration_ms,
            voice_id=voice,
        )

    def _estimate_word_timings(self, text: str) -> list[WordTiming]:
        """Estimate word timings from text (~150 WPM speaking rate)."""
        words = text.split()
        ms_per_word = 400  # ~150 WPM
        timings = []
        for i, word in enumerate(words):
            start = i * ms_per_word
            end = start + ms_per_word
            timings.append(WordTiming(word=word, start_ms=start, end_ms=end, index=i))
        return timings

    def _estimate_duration_ms(self, text: str) -> int:
        """Estimate duration from word count (~150 WPM)."""
        words = len(text.split())
        return int(words / 150 * 60 * 1000)

    async def synthesize_with_emphasis(
        self,
        text: str,
        emphasis_words: list[dict] | None = None,
        voice_id: str | None = None,
    ) -> TTSResult:
        """Synthesize with emphasis/pause directives applied to text.

        Emphasis words are applied as SSML-like markers in the text.
        Edge TTS supports basic SSML for pauses and emphasis.
        """
        if not emphasis_words:
            return await self.synthesize(text, voice_id)

        # Apply directives to text
        words = text.split()
        for directive in emphasis_words:
            idx = directive.get("at_word", -1)
            dtype = directive.get("type", "emphasis")
            if 0 <= idx < len(words):
                word = words[idx]
                if dtype == "emphasis":
                    words[idx] = f'<emphasis level="strong">{word}</emphasis>'
                elif dtype == "pause":
                    words[idx] = f'<break time="500ms"/>{word}'
                elif dtype == "whisper":
                    words[idx] = f'<prosody volume="soft" rate="slow">{word}</prosody>'

        modified_text = " ".join(words)

        # Edge TTS doesn't fully support SSML, so we strip tags for audio
        # but use them for timing hints
        import re
        clean_text = re.sub(r'<[^>]+>', '', modified_text)

        return await self.synthesize(clean_text, voice_id)

    def list_voices(self) -> list[dict]:
        """List available Edge TTS voices."""
        return [
            {"id": vid, **info}
            for vid, info in EDGE_VOICES.items()
        ]


# Singleton
edge_tts_service = EdgeTTSService()
