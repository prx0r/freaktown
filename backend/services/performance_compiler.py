"""PerformancePlan compiler.

Takes a minute text + voice profile and produces a timed PerformancePlan
that the stage client can play back synchronously.

The plan contains:
  - Full audio asset
  - Script segments with timing
  - Animation/gesture cues
  - Total duration
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict

from backend.services.tts import generate_speech, VOICE_CATALOG


@dataclass
class Cue:
    """A timed stage action."""
    at_ms: int
    type: str  # "gesture", "emote", "look_at", "caption"
    value: str = ""


@dataclass
class Segment:
    """A chunk of the performance with timing."""
    start_ms: int
    end_ms: int
    text: str
    emotion: str = "neutral"


@dataclass
class PerformancePlan:
    """A fully compiled, playable performance artifact."""
    performance_id: str
    comedian_name: str
    duration_ms: int
    audio_asset_path: str
    script: str
    segments: list[Segment]
    cues: list[Cue]
    voice_key: str
    content_hash: str

    def to_dict(self) -> dict:
        return {
            "performance_id": self.performance_id,
            "comedian_name": self.comedian_name,
            "duration_ms": self.duration_ms,
            "audio_asset_path": self.audio_asset_path,
            "script": self.script,
            "segments": [asdict(s) for s in self.segments],
            "cues": [asdict(c) for c in self.cues],
            "voice_key": self.voice_key,
            "content_hash": self.content_hash,
        }


# ── Cue generation heuristics ──────────────────────────────────────────

def _generate_cues_from_text(text: str, duration_ms: int) -> list[Cue]:
    """Generate animation/emote cues based on text analysis.

    This is a simple heuristic-based system for MVP.
    Later this can be LLM-driven or use prosody analysis.
    """
    cues = []

    # Split into sentences, preserving punctuation for detection
    # First split on sentence boundaries, then strip
    raw_sentences = []
    for part in text.replace("!", "!|").replace("?", "?|").split("|"):
        stripped = part.strip()
        if stripped:
            raw_sentences.append(stripped)

    if not raw_sentences:
        return [Cue(at_ms=0, type="gesture", value="idle")]

    ms_per_sentence = duration_ms // max(len(raw_sentences), 1)

    for i, sentence in enumerate(raw_sentences):
        at_ms = i * ms_per_sentence
        lower = sentence.lower()

        # Check for question BEFORE stripping punctuation
        is_question = "?" in sentence

        # Emotion/gesture heuristics
        if any(w in lower for w in ["kill", "die", "dead", "murder", "destroy"]):
            cues.append(Cue(at_ms=at_ms, type="emote", value="menacing"))
            cues.append(Cue(at_ms=at_ms, type="gesture", value="point"))
        elif any(w in lower for w in ["love", "beautiful", "amazing", "wonderful"]):
            cues.append(Cue(at_ms=at_ms, type="emote", value="warm"))
            cues.append(Cue(at_ms=at_ms, type="gesture", value="open_hand"))
        elif any(w in lower for w in ["fuck", "shit", "damn", "ass", "hell"]):
            cues.append(Cue(at_ms=at_ms, type="emote", value="angry"))
            cues.append(Cue(at_ms=at_ms, type="gesture", value="fist"))
        elif is_question:
            cues.append(Cue(at_ms=at_ms, type="gesture", value="shrug"))
            cues.append(Cue(at_ms=at_ms, type="emote", value="confused"))
        elif any(w in lower for w in ["so", "listen", "look", "okay"]):
            cues.append(Cue(at_ms=at_ms, type="gesture", value="open_hand"))
        elif i == 0:
            cues.append(Cue(at_ms=at_ms, type="gesture", value="wave"))
            cues.append(Cue(at_ms=at_ms, type="emote", value="confident"))
        elif i == len(raw_sentences) - 1:
            cues.append(Cue(at_ms=at_ms, type="gesture", value="bow"))

    # Add opening and closing
    cues.insert(0, Cue(at_ms=0, type="gesture", value="enter"))
    cues.append(Cue(at_ms=duration_ms - 500, type="gesture", value="exit"))

    return sorted(cues, key=lambda c: c.at_ms)


def _segment_script(text: str, duration_ms: int, max_segment_ms: int = 8000) -> list[Segment]:
    """Break script into timed segments for captions/display."""
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]

    if not sentences:
        return [Segment(start_ms=0, end_ms=duration_ms, text=text, emotion="neutral")]

    ms_per_sentence = duration_ms // max(len(sentences), 1)
    segments = []

    for i, sentence in enumerate(sentences):
        start = i * ms_per_sentence
        end = min((i + 1) * ms_per_sentence, duration_ms)
        lower = sentence.lower()

        emotion = "neutral"
        if any(w in lower for w in ["kill", "die", "dead"]):
            emotion = "menacing"
        elif any(w in lower for w in ["love", "beautiful"]):
            emotion = "warm"
        elif any(w in lower for w in ["fuck", "shit", "damn"]):
            emotion = "angry"
        elif "?" in sentence:
            emotion = "confused"

        segments.append(Segment(start_ms=start, end_ms=end, text=sentence, emotion=emotion))

    return segments


async def compile_performance(
    comedian_name: str,
    minute_text: str,
    voice_key: str = "default",
) -> PerformancePlan:
    """Compile a comedian's minute into a PerformancePlan.

    1. Generate audio via edge-tts
    2. Segment the script
    3. Generate animation cues
    4. Package into immutable plan
    """
    # Generate audio
    audio_result = await generate_speech(text=minute_text, voice_key=voice_key)
    duration_ms = audio_result["duration_ms"]

    # Segment script
    segments = _segment_script(minute_text, duration_ms)

    # Generate cues
    cues = _generate_cues_from_text(minute_text, duration_ms)

    # Create plan
    content_hash = hashlib.sha256(
        f"{comedian_name}|{minute_text}|{voice_key}|{duration_ms}".encode()
    ).hexdigest()[:16]

    plan = PerformancePlan(
        performance_id=f"perf_{uuid.uuid4().hex[:12]}",
        comedian_name=comedian_name,
        duration_ms=duration_ms,
        audio_asset_path=audio_result["file_path"],
        script=minute_text,
        segments=segments,
        cues=cues,
        voice_key=voice_key,
        content_hash=content_hash,
    )

    return plan
