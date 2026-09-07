"""Base TTS adapter — abstract interface all providers implement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from backend.models.draft import WordTiming


@dataclass
class TTSResult:
    """Unified result from any TTS provider."""
    audio_bytes: bytes
    audio_format: str  # "mp3", "wav", "ogg"
    word_timings: list[WordTiming]
    duration_ms: int
    voice_id: str
    provider: str
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ProviderInfo:
    """Metadata about a TTS provider."""
    id: str
    name: str
    description: str
    default: bool = False
    free: bool = False
    requires_api_key: bool = False
    requires_gpu: bool = False
    comedy_tags: list[str] = field(default_factory=list)
    pause_tags: list[str] = field(default_factory=list)
    cost_per_minute: float = 0.0
    voices: list[dict] = field(default_factory=list)


class TTSAdapter(ABC):
    """Abstract base for all TTS providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        """Synthesize text to speech with word timings."""
        ...

    @abstractmethod
    def list_voices(self) -> list[dict]:
        """List available voices for this provider."""
        ...

    @abstractmethod
    def info(self) -> ProviderInfo:
        """Return provider metadata."""
        ...

    def is_available(self) -> bool:
        """Check if this provider can be used right now."""
        return True

    def _estimate_word_timings(self, text: str) -> list[WordTiming]:
        """Fallback: estimate word timings at ~150 WPM."""
        words = text.split()
        ms_per_word = 400
        return [
            WordTiming(word=w, start_ms=i * ms_per_word,
                       end_ms=(i + 1) * ms_per_word, index=i)
            for i, w in enumerate(words)
        ]

    def _estimate_duration_ms(self, text: str) -> int:
        return int(len(text.split()) / 150 * 60 * 1000)
