"""TTS Provider Registry — select, list, and pre-process comedy tags."""

import re
import logging
from typing import Optional

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo

logger = logging.getLogger("freak_town.tts.registry")


# ── Generic comedy tag → provider-specific tag mapping ───────────────

GENERIC_TO_PROVIDER = {
    "minimax": {
        "[laugh]": "(laughs)",
        "[chuckle]": "(chuckle)",
        "[sigh]": "(sighs)",
        "[breath]": "(breath)",
        "[groan]": "(groans)",
        "[snort]": "(snorts)",
        "[hum]": "(humming)",
        "[clear_throat]": "(clears throat)",
        "[pause_short]": "(breath)",
        "[pause_medium]": "(sighs)",
        "[pause_long]": "(clears throat)",
    },
    "edge": {
        # Edge TTS has no comedy tags — strip them
    },
    "elevenlabs": {
        "[laugh]": "[laughs]",
        "[chuckle]": "[laughs]",
        "[sigh]": "[sighs]",
        "[breath]": "[stammers]",
        "[groan]": "[sighs]",
        "[whisper]": "[whispers]",
        "[pause_short]": "[drawn out]",
        "[pause_medium]": "[drawn out]",
        "[pause_long]": "[drawn out]",
    },
    "chattts": {
        "[laugh]": "[laugh]",
        "[chuckle]": "[laugh_1]",
        "[sigh]": "[break_5]",
        "[breath]": "[break_3]",
        "[groan]": "[laugh_0]",
        "[pause_short]": "[break_2]",
        "[pause_medium]": "[break_4]",
        "[pause_long]": "[break_7]",
    },
    "inworld": {
        "[laugh]": "[laugh]",
        "[chuckle]": "[giggle]",
        "[sigh]": "[sigh]",
        "[breath]": "[breathe]",
        "[groan]": "[groan]",
        "[whisper]": "[whisper]",
        "[clear_throat]": "[clear throat]",
        "[pause_short]": "[breathe]",
        "[pause_medium]": "[sigh]",
        "[pause_long]": "[clear throat]",
    },
    "gemini": {
        "[laugh]": "[laughing]",
        "[sigh]": "[sigh]",
        "[whisper]": "[whispering]",
        "[pause_short]": "[short pause]",
        "[pause_medium]": "[medium pause]",
        "[pause_long]": "[long pause]",
    },
}


def preprocess_text(text: str, provider_id: str) -> str:
    """Convert generic comedy tags to provider-specific tags.

    Generic tags:
      [laugh] [chuckle] [sigh] [breath] [groan] [whisper]
      [pause_short] [pause_medium] [pause_long]
      [clear_throat] [snort] [hum]

    These get mapped to the target provider's native tags.
    """
    mapping = GENERIC_TO_PROVIDER.get(provider_id, {})

    result = text
    for generic, specific in mapping.items():
        # Case-insensitive replacement
        pattern = re.compile(re.escape(generic), re.IGNORECASE)
        result = pattern.sub(specific, result)

    return result


# ── Provider Registry ────────────────────────────────────────────────

class TTSRegistry:
    """Central registry for all TTS providers."""

    def __init__(self):
        self._providers: dict[str, TTSAdapter] = {}
        self._default: str = "edge"

    def register(self, adapter: TTSAdapter, default: bool = False):
        info = adapter.info()
        self._providers[info.id] = adapter
        if default:
            self._default = info.id
        logger.info(f"Registered TTS provider: {info.id} ({info.name})")

    def get(self, provider_id: str | None = None) -> TTSAdapter:
        pid = provider_id or self._default
        if pid not in self._providers:
            available = list(self._providers.keys())
            raise ValueError(f"TTS provider '{pid}' not found. Available: {available}")
        adapter = self._providers[pid]
        if not adapter.is_available():
            # Fall back to edge if provider unavailable
            if pid != "edge" and "edge" in self._providers:
                logger.warning(f"Provider '{pid}' unavailable, falling back to edge")
                return self._providers["edge"]
            raise RuntimeError(f"TTS provider '{pid}' is not available")
        return adapter

    def list_providers(self) -> list[ProviderInfo]:
        return [adapter.info() for adapter in self._providers.values()]

    def list_available(self) -> list[ProviderInfo]:
        return [adapter.info() for adapter in self._providers.values() if adapter.is_available()]

    @property
    def default_id(self) -> str:
        return self._default


# ── Singleton ────────────────────────────────────────────────────────

tts_registry = TTSRegistry()

# Register all providers (order matters — first available wins for default)
def _register_all():
    from backend.services.tts.minimax import minimax_tts
    from backend.services.tts.gemini import gemini_tts
    from backend.services.tts.edge import edge_tts_adapter
    from backend.services.tts.elevenlabs import elevenlabs_tts
    from backend.services.tts.chattts import chattts_adapter
    from backend.services.tts.inworld import inworld_tts
    from backend.services.tts.qwen3 import qwen3_tts

    # MiniMax is the preferred default
    tts_registry.register(minimax_tts, default=True)
    tts_registry.register(gemini_tts)
    tts_registry.register(edge_tts_adapter)
    tts_registry.register(elevenlabs_tts)
    tts_registry.register(chattts_adapter)
    tts_registry.register(inworld_tts)
    tts_registry.register(qwen3_tts)  # Canonical open-source

    # If default is unavailable, cascade to next available
    if not tts_registry.get().is_available():
        for pid in ["gemini", "edge"]:
            try:
                adapter = tts_registry.get(pid)
                if adapter.is_available():
                    tts_registry._default = pid
                    break
            except ValueError:
                pass

_register_all()


# ── Convenience functions ────────────────────────────────────────────

def get_adapter(provider_id: str | None = None) -> TTSAdapter:
    return tts_registry.get(provider_id)

def list_providers() -> list[ProviderInfo]:
    return tts_registry.list_providers()

def list_available() -> list[ProviderInfo]:
    return tts_registry.list_available()
