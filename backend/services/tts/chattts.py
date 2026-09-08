"""ChatTTS adapter — self-hosted open source with comedy tags.

Comedy tags supported:
  [uv_break]     (micro pause)
  [lbreak]       (line break pause)
  [break_0]-[break_7]  (pause intensity levels)
  [laugh]        (laugh)
  [laugh_0]-[laugh_2]  (laugh intensity levels)

Requires: GPU (CUDA) + chat-tts package.
Cost: Free (self-hosted).

API: https://github.com/2noise/ChatTTS
"""

import logging
import os
import subprocess

from backend.services.tts.base import TTSAdapter, TTSResult, ProviderInfo
from backend.models.draft import WordTiming

logger = logging.getLogger("freak_town.tts.chattts")

COMEDY_TAGS = [
    "[uv_break]", "[lbreak]",
    "[break_0]", "[break_1]", "[break_2]", "[break_3]",
    "[break_4]", "[break_5]", "[break_6]", "[break_7]",
    "[laugh]", "[laugh_0]", "[laugh_1]", "[laugh_2]",
]


class ChatTTSAdapter(TTSAdapter):
    """ChatTTS — free self-hosted TTS with comedy tag support."""

    def __init__(self):
        self._model = None
        self._available = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import chat_tts  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
            logger.info("ChatTTS not installed. Install with: pip install chat-tts")
        return self._available

    def _get_model(self):
        if self._model is None:
            import chat_tts
            self._model = chat_tts.Chat()
            self._model.load(compile=False)
        return self._model

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> TTSResult:
        if not self.is_available():
            raise RuntimeError(
                "ChatTTS not installed. Run: pip install chat-tts\n"
                "Requires GPU (CUDA) for reasonable speed."
            )

        model = self._get_model()

        # Generate speaker embedding (deterministic from voice_id seed)
        import torch
        seed = hash(voice_id or "default") % (2**31)
        torch.manual_seed(seed)
        rand_spk = model.sample_random_speaker()

        params_infer = chat_tts.Chat.InferCodeParams(
            spk_emb=rand_spk,
            temperature=0.3,
            top_P=0.7,
            top_K=20,
        )
        params_refine = chat_tts.Chat.RefineTextParams(
            prompt="[oral_2][laugh_0][break_4]",
        )

        output = model.infer(
            text,
            params_infer_code=params_infer,
            params_refine_text=params_refine,
        )

        # ChatTTS returns numpy array
        import numpy as np
        audio_data = output[0]

        # Convert to bytes (16-bit PCM)
        audio_int16 = (audio_data * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()

        word_timings = self._estimate_word_timings(text)
        duration_ms = int(len(audio_data) / 24000 * 1000)  # 24kHz sample rate

        return TTSResult(
            audio_bytes=audio_bytes,
            audio_format="wav",
            word_timings=word_timings,
            duration_ms=duration_ms,
            voice_id=voice_id or "default",
            provider="chattts",
            cost_usd=0.0,
            metadata={"tags_supported": COMEDY_TAGS, "sample_rate": 24000},
        )

    def list_voices(self) -> list[dict]:
        return [
            {"id": "default", "name": "ChatTTS Default", "gender": "neutral", "provider": "chattts"},
        ]

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="chattts",
            name="ChatTTS",
            description="Free self-hosted TTS. Comedy tags: [laugh], [break_0-7]. Needs GPU.",
            free=True,
            requires_gpu=True,
            comedy_tags=COMEDY_TAGS,
            pause_tags=["[uv_break]", "[lbreak]", "[break_0]", "[break_7]"],
            cost_per_minute=0.0,
        )


chattts_adapter = ChatTTSAdapter()
