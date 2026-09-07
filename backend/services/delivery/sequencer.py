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

import asyncio
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("freak_town.delivery")

SCHEMA_VERSION = "freaktown.delivery.v1"

BEAT_TYPES = ["setup", "escalation", "misdirect", "punchline", "tag", "callback", "actout", "closer"]

# Canonical mix format: 16-bit PCM, mono, 24 kHz. Everything is decoded
# to this before silence insertion, and the final WAV is encoded from it.
CANONICAL_SAMPLE_RATE = 24000
CANONICAL_CHANNELS = 1
CANONICAL_SAMPWIDTH = 2


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
    # Black Room (freaktown.delivery.v1) performance intent. Carried
    # through untouched so the stage can direct voice, body and camera.
    expression: str = "normal"  # deadpan|excited|whisper|shout|normal
    gesture: str = ""  # still|shrug|point|lean|wave|...
    camera: str = ""  # wide|medium|close|side
    sound: str = "none"  # rimshot|drum_hit|laugh_track|crowd_cheer|none


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
                    "delivery": {"pace": b.pace, "energy": b.energy, "emphasis": b.emphasis,
                                 "expression": b.expression},
                    "pause_before_ms": b.pause_before_ms,
                    "pause_after_ms": b.pause_after_ms,
                    "stage": b.stage,
                    "gesture": b.gesture,
                    "camera": b.camera,
                    "sound": b.sound,
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
                expression=b.get("delivery", {}).get("expression", b.get("expression", "normal")),
                gesture=b.get("gesture", ""),
                camera=b.get("camera", ""),
                sound=b.get("sound", "none"),
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
            # Black Room direction defaults (mirror freaktown detect_beats):
            # punchlines freeze + rimshot on close camera; closers on close.
            gesture="still" if btype in ("punchline", "closer") else "",
            camera="close" if btype in ("punchline", "closer") else "medium",
            sound="rimshot" if btype == "punchline" else "none",
        ))

    return DeliveryScore(beats=beats)


# ── Audio compositor: beats + TTS regions → final WAV with exact silence

_FFMPEG: str | None = None
_FFMPEG_CHECKED = False


def _require_ffmpeg() -> str:
    """Locate the ffmpeg binary. Raises loudly — never silently degrade."""
    global _FFMPEG, _FFMPEG_CHECKED
    if not _FFMPEG_CHECKED:
        _FFMPEG = shutil.which("ffmpeg")
        _FFMPEG_CHECKED = True
    if not _FFMPEG:
        raise RuntimeError(
            "ffmpeg is required to decode provider audio (mp3/wav/ogg) to "
            "canonical PCM. Install it: apt-get install ffmpeg"
        )
    return _FFMPEG


async def _decode_to_canonical_pcm(audio: bytes, audio_format: str) -> bytes:
    """Decode provider audio (mp3/wav/ogg/...) to canonical PCM16 mono 24kHz.

    Uses the declared `audio_format` only for diagnostics; ffmpeg probes
    the container itself. Returns raw PCM16LE frames (no WAV header).
    """
    ffmpeg = _require_ffmpeg()
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-v", "error",
        "-i", "pipe:0",
        "-f", "s16le", "-ac", str(CANONICAL_CHANNELS), "-ar", str(CANONICAL_SAMPLE_RATE),
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(audio), timeout=180)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise RuntimeError(f"ffmpeg decode timed out (format={audio_format})")
    if proc.returncode != 0:
        detail = err.decode(errors="replace")[:300] if err else "unknown error"
        raise RuntimeError(f"ffmpeg decode failed (format={audio_format}): {detail}")
    if len(out) % 2:
        out += b"\x00"
    return out


def _encode_wav(frames: bytes) -> bytes:
    """Encode canonical PCM16 mono 24kHz frames as a valid WAV."""
    import io
    import wave

    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(CANONICAL_CHANNELS)
        w.setsampwidth(CANONICAL_SAMPWIDTH)
        w.setframerate(CANONICAL_SAMPLE_RATE)
        w.writeframes(frames)
    return out.getvalue()


async def compose(score: DeliveryScore) -> bytes:
    """Render a DeliveryScore into final WAV.

    Pipeline (freaktown.delivery.v1 contract):

        provider MP3/WAV/OGG
                ↓ ffmpeg decode
        canonical PCM16 mono 24kHz
                ↓
        insert exact silence (pause_before_ms / pause_after_ms)
                ↓
        encode final WAV

    TTS adapters declare their container in `audio_format`; we never
    assume raw PCM. pause_after_ms means EXACTLY that many ms of silence,
    regardless of provider.

    Fail-loud contract: a TTS/decode failure on ANY beat with text fails
    the whole build (RuntimeError listing the failed beats). A contestant
    standing silent for six seconds is not a valid compiled performance —
    only READY builds (validate_score + successful compose) enter a show.
    If ffmpeg itself is missing we raise — a corrupt or fake file is
    worse than an error.
    """
    failures = validate_score(score)
    if failures:
        raise ValueError(f"invalid delivery score: {failures[0]}")

    try:
        from backend.services.tts import get_adapter
        adapter = get_adapter(score.provider if score.provider != "qwen3" else None)
    except Exception as e:
        raise RuntimeError(f"no TTS provider available: {e}")

    if adapter is None:
        raise RuntimeError("no TTS provider available")

    _require_ffmpeg()

    pcm_segments: list[bytes] = []
    failed: list[str] = []

    for beat in score.beats:
        # pause_before (EXACT)
        if beat.pause_before_ms > 0:
            pcm_segments.append(_silence(beat.pause_before_ms, CANONICAL_SAMPLE_RATE))
        # spoken region: synthesize, then decode to canonical PCM
        if beat.text.strip() and adapter:
            try:
                result = await adapter.synthesize(beat.text, score.voice_id)
                pcm_segments.append(await _decode_to_canonical_pcm(result.audio_bytes, result.audio_format))
            except Exception as e:
                failed.append(f"{beat.id}: {e}")
        # pause_after (EXACT, regardless of provider)
        if beat.pause_after_ms > 0:
            pcm_segments.append(_silence(beat.pause_after_ms, CANONICAL_SAMPLE_RATE))

    if failed:
        raise RuntimeError(f"performance build failed ({len(failed)} beats): " + "; ".join(failed))

    return _encode_wav(b"".join(pcm_segments))


def validate_score(score: DeliveryScore) -> list[str]:
    """Pre-build validation. Empty list = READY to compose.

    States: DRAFT (has text) → GENERATING (compose running) →
    VALIDATING (these checks) → READY (valid WAV) / FAILED (raised).
    """
    problems: list[str] = []
    if not score.beats:
        problems.append("score has no beats")
        return problems
    for i, beat in enumerate(score.beats):
        if not beat.text.strip():
            problems.append(f"beats[{i}] ({beat.id}) has empty text")
        if beat.pause_after_ms < 0 or beat.pause_after_ms > 10_000:
            problems.append(f"beats[{i}] ({beat.id}) pause_after_ms out of range")
        if beat.type not in BEAT_TYPES:
            problems.append(f"beats[{i}] ({beat.id}) unknown type {beat.type!r}")
    return problems


def _silence(ms: int, sample_rate: int = CANONICAL_SAMPLE_RATE) -> bytes:
    """Exact silence: N ms of 16-bit PCM zeros."""
    frames = int(ms * sample_rate / 1000)
    return b"\x00\x00" * frames
