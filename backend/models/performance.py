"""Performance Engine — reusable creator-authored movement policies.

A PerformanceEngine is not attached to one joke. It's a persistent,
versioned object that defines HOW a character moves. Creators build,
fork, and evolve these engines. The competition drives the meta.

Reference: anime.dm
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


# ── Style Profile ───────────────────────────────────────────────────

@dataclass
class StyleProfile:
    """The character's overall movement personality."""
    energy: float = 0.5          # 0=statue 1=manic
    stillness: float = 0.5       # 0=never still 1=frozen
    gesture_density: float = 0.5 # 0=never gesture 1=gesture constantly
    gesture_amplitude: float = 0.5  # 0=tiny 1=huge
    eye_contact: float = 0.5     # 0=never look 1=locked on
    pacing: float = 0.3          # 0=stand still 1=constant movement
    punchline_hold_ms: int = 800  # freeze after punchline

    def to_dict(self) -> dict:
        return {
            "energy": self.energy,
            "stillness": self.stillness,
            "gesture_density": self.gesture_density,
            "gesture_amplitude": self.gesture_amplitude,
            "eye_contact": self.eye_contact,
            "pacing": self.pacing,
            "punchline_hold_ms": self.punchline_hold_ms,
        }


# ── Signature Move ─────────────────────────────────────────────────

@dataclass
class SignatureMove:
    """A characteristic movement that defines the character."""
    name: str
    action: str          # semantic action, e.g. "reaction.dead_stare"
    intensity: float = 0.5
    trigger: str = ""    # e.g. "after_big_punchline", "on_ella_question"
    duration_ms: int = 0  # 0 = use motion default


# ── Timing Rule ─────────────────────────────────────────────────────

@dataclass
class TimingRule:
    """Conditional movement rule tied to show context."""
    during: str = ""       # "setup", "punchline", "tag", "interview"
    on: str = ""           # "audience_big_laugh", "ella_question", "silence"
    after: str = ""        # "punchline", "big_laugh"
    prefer: list[str] = field(default_factory=list)
    do: str = ""           # single action to execute
    hold_ms: int = 0       # freeze duration


# ── Performance Engine ─────────────────────────────────────────────

@dataclass
class PerformanceEngine:
    """Reusable movement policy for a character.

    Created by creators/agents. Versioned. Forkable.
    This is the competitive artifact — people build these, share them,
    evolve them based on audience response data.

    Example: @tom/deadpan-dog-v7
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""               # "deadpan-dog", "manic-goblin"
    creator_id: str = ""
    version: int = 1
    parent_engine_id: str | None = None  # fork chain

    # Core style
    style: StyleProfile = field(default_factory=StyleProfile)

    # Character-specific movements
    signature_moves: list[SignatureMove] = field(default_factory=list)

    # Timing rules
    rules: list[TimingRule] = field(default_factory=list)

    # Motion preferences (semantic actions preferred for each context)
    motion_preferences: dict[str, list[str]] = field(default_factory=lambda: {
        "idle": ["procedural.breathing", "procedural.sway"],
        "setup": ["gesture.beat", "gaze.audience"],
        "punchline": ["movement.freeze"],
        "post_punchline": ["reaction.dead_stare", "gaze.audience"],
        "interview": ["gaze.ella", "gesture.beat"],
        "big_laugh": ["reaction.enjoy_laugh"],
    })

    # Body fallbacks (how this engine adapts to non-humanoid bodies)
    body_fallbacks: dict[str, dict[str, str]] = field(default_factory=lambda: {
        "quadruped-v1": {
            "gesture.shrug": "gesture.emphasize",
            "gesture.point": "gesture.emphasize",
        },
        "rigid-object-v1": {
            "gesture.*": "gesture.emphasize",
            "face.*": "reaction.dead_stare",
        },
    })

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)  # ["deadpan", "dog", "low-energy"]

    def get_motion_for_context(self, context: str) -> list[str]:
        """Get preferred semantic actions for a show context."""
        return self.motion_preferences.get(context, ["procedural.breathing"])

    def get_signature_for_trigger(self, trigger: str) -> SignatureMove | None:
        """Get the signature move for a specific trigger."""
        for move in self.signature_moves:
            if move.trigger == trigger:
                return move
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "parent_engine_id": self.parent_engine_id,
            "style": self.style.to_dict(),
            "signature_moves": [
                {"name": m.name, "action": m.action, "intensity": m.intensity, "trigger": m.trigger}
                for m in self.signature_moves
            ],
            "rules": [
                {"during": r.during, "on": r.on, "after": r.after, "prefer": r.prefer, "do": r.do, "hold_ms": r.hold_ms}
                for r in self.rules
            ],
            "tags": self.tags,
        }


# ── Preset Engines ─────────────────────────────────────────────────

PRESET_ENGINES = {
    "deadpan": PerformanceEngine(
        name="Deadpan",
        style=StyleProfile(energy=0.2, stillness=0.8, gesture_density=0.15,
                           gesture_amplitude=0.3, eye_contact=0.7, pacing=0.1,
                           punchline_hold_ms=1200),
        signature_moves=[
            SignatureMove("The Stare", "reaction.dead_stare", 0.9, "after_big_punchline", 1500),
        ],
        tags=["deadpan", "low-energy", "restrained"],
    ),
    "nervous": PerformanceEngine(
        name="Nervous",
        style=StyleProfile(energy=0.6, stillness=0.2, gesture_density=0.7,
                           gesture_amplitude=0.4, eye_contact=0.3, pacing=0.5,
                           punchline_hold_ms=400),
        signature_moves=[
            SignatureMove("Fidget", "reaction.nervous", 0.6, "during_silence"),
        ],
        tags=["nervous", "high-energy", "fidgety"],
    ),
    "confident": PerformanceEngine(
        name="Confident",
        style=StyleProfile(energy=0.5, stillness=0.5, gesture_density=0.4,
                           gesture_amplitude=0.7, eye_contact=0.9, pacing=0.3,
                           punchline_hold_ms=800),
        tags=["confident", "balanced", "strong-gaze"],
    ),
    "chaotic": PerformanceEngine(
        name="Chaotic",
        style=StyleProfile(energy=0.9, stillness=0.05, gesture_density=0.9,
                           gesture_amplitude=0.9, eye_contact=0.5, pacing=0.8,
                           punchline_hold_ms=300),
        tags=["chaotic", "high-energy", "unpredictable"],
    ),
    "awkward": PerformanceEngine(
        name="Awkward",
        style=StyleProfile(energy=0.3, stillness=0.6, gesture_density=0.3,
                           gesture_amplitude=0.2, eye_contact=0.2, pacing=0.2,
                           punchline_hold_ms=600),
        signature_moves=[
            SignatureMove("Awkward Pause", "movement.freeze", 0.8, "after_punchline", 2000),
            SignatureMove("Look Away", "gaze.away", 0.7, "during_silence"),
        ],
        tags=["awkward", "low-energy", "avoidant"],
    ),
    "low_energy": PerformanceEngine(
        name="Low Energy",
        style=StyleProfile(energy=0.15, stillness=0.85, gesture_density=0.1,
                           gesture_amplitude=0.2, eye_contact=0.4, pacing=0.05,
                           punchline_hold_ms=1000),
        tags=["low-energy", "minimal", "still"],
    ),
}
