"""TTS Adapter Layer — unified interface for all TTS providers.

Every adapter returns the same TTSResult. The preprocessor converts
generic comedy directives into provider-specific tags.

Provider hierarchy (default → upgrade):
  1. MiniMax Speech 2.8  — best comedy tags, ~$0.01/min
  2. Gemini Flash TTS    — free, good tags
  3. Edge TTS            — free fallback, no tags
  4. ElevenLabs v3       — best tag library, $0.17/min
  5. Inworld TTS-2       — full control, $0.15/min
  6. ChatTTS             — self-hosted, free, needs GPU
"""

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.services.tts.registry import tts_registry, get_adapter, list_providers, list_available

# ── Backward compatibility shims ─────────────────────────────────────
# Existing code imports generate_speech, VOICE_CATALOG, list_voices
# from this module. Provide them via the adapter layer.

async def generate_speech(text: str, voice_id: str = "en-US-GuyNeural", **kwargs) -> TTSResult:
    """Legacy shim — use get_adapter().synthesize() instead."""
    adapter = get_adapter()
    return await adapter.synthesize(text, voice_id)

def list_voices(provider: str = "") -> list[dict]:
    """Legacy shim — use get_adapter().list_voices() instead."""
    return get_adapter(provider or None).list_voices()

def VOICE_CATALOG() -> list[dict]:
    """Legacy shim — returns edge TTS voices."""
    from backend.services.tts.edge import EDGE_VOICES
    return [{"id": vid, **info} for vid, info in EDGE_VOICES.items()]

__all__ = [
    "TTSAdapter", "TTSResult", "ProviderInfo",
    "tts_registry", "get_adapter", "list_providers", "list_available",
    "generate_speech", "VOICE_CATALOG", "list_voices",
]
