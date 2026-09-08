"""PerformanceDraft — the editable, disposable performance object.

While editing, the creator works with a PerformanceDraft.
When they press WATCH, the draft compiles to a PerformancePlan.
When they press ENTER SHOW, the draft freezes into an ActVersion.

This separation is critical:
- Editing = disposable, instant, throwaway
- Show artifact = immutable, frozen, permanent

Reference: anime.dm, Green Room spec
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class VoiceMode(str, Enum):
    DRAFT = "draft"          # Edge TTS — free, fast
    PERFORMANCE = "performance"  # Inworld — good sync/lipsync
    EXPRESSIVE = "expressive"    # Eleven v3 — directed acting
    CUSTOM = "custom"            # Creator's own provider


@dataclass
class WordTiming:
    """A single word with its timing from TTS."""
    word: str
    start_ms: int
    end_ms: int
    index: int  # position in script


@dataclass
class StageDirection:
    """A movement/reaction cue attached to a specific word or time.

    Created by the creator clicking a word and typing a direction.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    at_word: int = -1           # word index (-1 = at_time instead)
    at_ms: int = 0              # fallback: absolute time
    action: str = ""            # semantic action: gaze.ella, gesture.shrug, etc.
    emotion: str = ""           # face emotion: annoyed, surprised, etc.
    intensity: float = 0.5
    description: str = ""       # original natural language
    duration_ms: int = 0        # 0 = use default
    resolved: dict = field(default_factory=dict)  # after AI parsing


@dataclass
class SpeechDirective:
    """A voice acting direction attached to a word."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    at_word: int = -1
    word: str = ""
    directive_type: str = ""    # "emphasis", "pause", "whisper", "sarcastic", etc.
    intensity: float = 0.5
    description: str = ""       # original natural language


@dataclass
class SignatureMoveSaved:
    """A saved signature move from the Green Room."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    directions: list[StageDirection] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PerformanceDraft:
    """The editable performance object in the Green Room.

    Not sealed. Not permanent. Disposable until ENTER SHOW.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    comedian_id: str = ""
    episode_id: str | None = None

    # Script
    script: str = ""
    word_timings: list[WordTiming] = field(default_factory=list)

    # Voice
    voice_mode: VoiceMode = VoiceMode.DRAFT
    voice_id: str = "en-US-GuyNeural"  # Edge TTS default
    audio_r2_key: str = ""
    audio_duration_ms: int = 0

    # Performance
    stage_directions: list[StageDirection] = field(default_factory=list)
    speech_directives: list[SpeechDirective] = field(default_factory=list)

    # Style (overrides PerformanceEngine defaults)
    style_overrides: dict = field(default_factory=dict)

    # Saved signature moves
    signature_moves: list[SignatureMoveSaved] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    # Compilation cache
    compiled_plan: dict | None = None
    compiled_at: datetime | None = None

    @property
    def estimated_duration_ms(self) -> int:
        """Estimate duration from word timings or word count."""
        if self.word_timings:
            return self.word_timings[-1].end_ms if self.word_timings else 0
        # Fallback: ~150 WPM
        words = len(self.script.split())
        return int(words / 150 * 60 * 1000)

    @property
    def duration_status(self) -> str:
        """Color status: green/amber/red based on duration."""
        ms = self.audio_duration_ms or self.estimated_duration_ms
        sec = ms / 1000
        if sec <= 60:
            return "green"
        elif sec <= 65:
            return "amber"
        else:
            return "red"

    def add_direction_at_word(self, word_index: int, action: str = "",
                              emotion: str = "", description: str = "",
                              intensity: float = 0.5) -> StageDirection:
        """Add a stage direction at a specific word."""
        d = StageDirection(
            at_word=word_index,
            action=action,
            emotion=emotion,
            description=description,
            intensity=intensity,
        )
        self.stage_directions.append(d)
        self.updated_at = datetime.now(timezone.utc)
        return d

    def add_speech_directive(self, word_index: int, directive_type: str,
                             description: str = "", intensity: float = 0.5) -> SpeechDirective:
        """Add a voice acting direction at a specific word."""
        word = ""
        if 0 <= word_index < len(self.word_timings):
            word = self.word_timings[word_index].word

        d = SpeechDirective(
            at_word=word_index,
            word=word,
            directive_type=directive_type,
            description=description,
            intensity=intensity,
        )
        self.speech_directives.append(d)
        self.updated_at = datetime.now(timezone.utc)
        return d

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "comedian_id": self.comedian_id,
            "script": self.script,
            "word_count": len(self.script.split()),
            "estimated_duration_ms": self.estimated_duration_ms,
            "audio_duration_ms": self.audio_duration_ms,
            "duration_status": self.duration_status,
            "voice_mode": self.voice_mode.value,
            "voice_id": self.voice_id,
            "stage_directions": [
                {"id": d.id, "at_word": d.at_word, "action": d.action,
                 "emotion": d.emotion, "description": d.description}
                for d in self.stage_directions
            ],
            "speech_directives": [
                {"id": d.id, "at_word": d.at_word, "word": d.word,
                 "type": d.directive_type, "description": d.description}
                for d in self.speech_directives
            ],
            "signature_moves": [
                {"id": m.id, "name": m.name, "description": m.description}
                for m in self.signature_moves
            ],
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
        }
