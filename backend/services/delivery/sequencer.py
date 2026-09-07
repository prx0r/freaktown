"""Delivery Sequencer — canonical freaktown.delivery.v1 format.

Freak Town owns exact timing. TTS models are actors, Freak Town is the director.

  flat text
       ↓
  DELIVERY SCORE (beats with pause_after_ms, pace, emphasis)
       ↓
  TTS generates spoken regions
       ↓
  AUDIO COMPOSITOR inserts exact silence
       ↓
  final WAV (pause_after_ms means EXACTLY that many ms)

Schema:
{
  "version": "freaktown.delivery.v1",
  "voice": {"provider": "qwen3", "voice_id": "pigeon-v3"},
  "beats": [
    {"id": "b1", "type": "setup", "text": "...",
     "delivery": {"pace": 1.0, "energy": 0.65},
     "pause_after_ms": 180}
  ]
}
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("freak_town.delivery")

SCHEMA_VERSION = "freaktown.delivery.v1"

BEAT_TYPES = ["setup", "escalation", "misdirect", "punchline", "tag", "callback", "actout", "closer"]


@dataclass
class DeliveryBeat:
    id: str = field(default_factory=lambda: f"b{uuid.uuid4().hex[:6]}")
    type: str = "setup"
    text: str = ""
    pace: float = 1.0
    energy: float = 0.6
    emphasis: float = 0.5
    pause_before_ms: int = 0
    pause_after_ms: int = 200
    stage: str = ""  # hold, gesture, gaze, none


@dataclass
class DeliveryScore:
    provider: str = "qwen3"
    voice_id: str = "default"
    beats: list[DeliveryBeat] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "voice": {"provider": self.provider, "voice_id": self.voice_id},
            "beats": [
                {
                    "id": b.id, "type": b.type, "text": b.text,
                    "delivery": {"pace": b.pace, "energy": b.energy, "emphasis": b.emphasis},
                    "pause_before_ms": b.pause_before_ms,
                    "pause_after_ms": b.pause_after_ms,
                    "stage": b.stage,
                }
                for b in self.beats
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeliveryScore":
        voice = data.get("voice", {})
        beats = [
            DeliveryBeat(
                id=b.get("id", f"b{i}"), type=b.get("type", "setup"), text=b.get("text", ""),
                pace=b.get("delivery", {}).get("pace", 1.0),
                energy=b.get("delivery", {}).get("energy", 0.6),
                emphasis=b.get("delivery", {}).get("emphasis", 0.5),
                pause_before_ms=b.get("pause_before_ms", 0),
                pause_after_ms=b.get("pause_after_ms", 200),
                stage=b.get("stage", ""),
            )
            for i, b in enumerate(data.get("beats", []))
        ]
        return cls(provider=voice.get("provider", "qwen3"), voice_id=voice.get("voice_id", "default"), beats=beats)


# ── Vanilla arranger: flat text → beats ─────────────────────────────

def arrange(text: str) -> DeliveryScore:
    """Split flat text into beats with conservative timing defaults.

    Ordinary punctuation → normal micro-prosody (TTS handles it).
    Explicit silence only at high-confidence beat boundaries.
    Punchlines get a modest anticipatory beat + larger post-punchline hold
    (so the comedian never talks over the laugh).
    """
    # Split into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    beats: list[DeliveryBeat] = []

    for i, sent in enumerate(sentences):
        is_last = i == len(sentences) - 1
        is_first = i == 0
        word_count = len(sent.split())
        has_question = "?" in sent
        has_exclaim = "!" in sent

        if is_last and word_count <= 12:
            btype, pause_after, energy = "punchline", 850, 0.8
        elif is_last:
            btype, pause_after, energy = "closer", 650, 0.7
        elif is_first:
            btype, pause_after, energy = "setup", 180, 0.65
        elif has_question or has_exclaim:
            btype, pause_after, energy = "escalation", 320, 0.7
        elif word_count > 25:
            btype, pause_after, energy = "setup", 250, 0.6
        else:
            btype, pause_after, energy = "setup", 200, 0.6

        beats.append(DeliveryBeat(
            type=btype, text=sent, energy=energy,
            pause_after_ms=pause_after,
            stage="hold" if btype == "punchline" else "",
        ))

    return DeliveryScore(beats=beats)


# ── Audio compositor: beats + TTS regions → final WAV with exact silence

async def compose(score: DeliveryScore) -> bytes:
    """Render a DeliveryScore into final WAV.

    Qwen/TTS generates each spoken beat; Freak Town inserts exact silence.
    Returns WAV bytes (silence placeholder when TTS unavailable).
    """
    try:
        from backend.services.tts import get_adapter
        adapter = get_adapter(score.provider if score.provider != "qwen3" else None)
    except Exception:
        adapter = None

    segments: list[bytes] = []
    sample_rate = 24000

    for beat in score.beats:
        # pause_before
        if beat.pause_before_ms > 0:
            segments.append(_silence(beat.pause_before_ms, sample_rate))
        # spoken region
        audio = b""
        if adapter:
            try:
                result = await adapter.synthesize(beat.text, score.voice_id)
                audio = result.audio_bytes
            except Exception as e:
                logger.warning(f"Beat {beat.id} TTS failed: {e}")
        segments.append(audio)
        # pause_after (EXACT, regardless of provider)
        if beat.pause_after_ms > 0:
            segments.append(_silence(beat.pause_after_ms, sample_rate))

    if not segments:
        return _wav_header(sample_rate, 0)

    # Concatenate: try proper WAV merge, fall back to raw silence placeholder
    try:
        import io, wave
        out = io.BytesIO()
        frames = b"".join(segments)
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(frames if len(frames) % 2 == 0 else frames + b"\x00")
        return out.getvalue()
    except Exception:
        return _wav_header(sample_rate, sum(len(s) for s in segments))


def _silence(ms: int, sample_rate: int = 24000) -> bytes:
    """Exact silence: N ms of 16-bit PCM zeros."""
    frames = int(ms * sample_rate / 1000)
    return b"\x00\x00" * frames


def _wav_header(sample_rate: int, n_bytes: int) -> bytes:
    """Minimal WAV header for empty/placeholder output."""
    import struct
    data_len = n_bytes if n_bytes % 2 == 0 else n_bytes + 1
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_len, b"WAVE", b"fmt ", 16,
        1, 1, sample_rate, sample_rate * 2, 2, 16, b"data", data_len,
    ) + b"\x00" * data_len
