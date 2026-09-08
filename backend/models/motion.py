"""Killella Motion Language — core data models.

Defines the semantic movement vocabulary, body capability manifests,
and the Performance Engine abstraction.

Reference: anime.dm
"""

import enum
from dataclasses import dataclass, field


# ── Semantic Action Vocabulary ──────────────────────────────────────

class SemanticCategory(str, enum.Enum):
    LOCOMOTION = "locomotion"
    GESTURE = "gesture"
    GAZE = "gaze"
    REACTION = "reaction"
    POSE = "pose"
    FACE = "face"
    PROCEDURAL = "procedural"


# Canonical semantic actions that any body can interpret
SEMANTIC_ACTIONS = {
    # Locomotion
    "locomotion.enter": "Walk onto stage",
    "locomotion.exit": "Walk off stage",
    "locomotion.walk": "Walk in place or small area",
    "locomotion.pace": "Slow deliberate pacing",
    "locomotion.freeze": "Stop all movement",

    # Gesture
    "gesture.beat": "Small rhythmic hand movement for emphasis",
    "gesture.emphasize": "Strong hand/arm emphasis",
    "gesture.point": "Point at something",
    "gesture.shrug": "Shrug shoulders",
    "gesture.open_palm": "Open palm gesture",
    "gesture.dismiss": "Dismissive wave",
    "gesture.come_here": "Beckoning",
    "gesture.stop": "Hand up stop",
    "gesture.thumbs_up": "Thumbs up",
    "gesture.wave": "Waving hello",

    # Gaze
    "gaze.audience": "Look at audience",
    "gaze.ella": "Look at Ella/host",
    "gaze.ground": "Look down",
    "gaze.sky": "Look up",
    "gaze.left": "Look stage left",
    "gaze.right": "Look stage right",
    "gaze.away": "Look away, avoid eye contact",
    "gaze.stare": "Fixed intense stare",

    # Reaction
    "reaction.dead_stare": "Blank stare after punchline",
    "reaction.confused": "Confused reaction",
    "reaction.annoyed": "Annoyed reaction",
    "reaction.enjoy_laugh": "Enjoy the audience laughing",
    "reaction.bored": "Bored, unimpressed",
    "reaction.shock": "Shocked reaction",
    "reaction.double_take": "Look away then look back",
    "reaction.nervous": "Nervous fidgeting",

    # Pose
    "pose.confident": "Confident standing pose",
    "pose.slump": "Slumped defeat",
    "pose.lean_forward": "Leaning in intently",
    "pose.lean_back": "Leaning back relaxed",
    "pose.cross_arms": "Arms crossed",
    "pose.hands_on_hips": "Hands on hips",

    # Face
    "face.neutral": "Neutral expression",
    "face.smile": "Smile",
    "face.frown": "Frown",
    "face.annoyed": "Annoyed expression",
    "face.smug": "Smug, self-satisfied",
    "face.deadpan": "Completely flat expression",
    "face.surprised": "Surprised expression",
    "face.disgusted": "Disgusted expression",

    # Procedural
    "procedural.breathing": "Natural breathing sway",
    "procedural.micro_fidget": "Small restless movements",
    "procedural sway": "Gentle body sway",
}


# ── Body Capability Manifest ────────────────────────────────────────

@dataclass
class CapabilityManifest:
    """Declares what a body can do semantically.

    The manifest maps semantic actions to body-specific implementations.
    If an action is not mapped, the compiler uses semantic fallbacks.
    """
    body_class: str  # "humanoid-v1", "quadruped-v1", "rigid-object-v1"
    capabilities: list[str]  # ["locomotion.walk", "gesture.beat", ...]

    # Semantic fallback mapping: when a requested action isn't directly
    # supported, map it to an alternative
    fallbacks: dict[str, str] = field(default_factory=dict)

    # Body-specific parameters
    max_gesture_amplitude: float = 1.0
    supports_additive: bool = True
    supports_face_expressions: bool = True
    supports_root_motion: bool = True

    def can_do(self, action: str) -> bool:
        """Check if this body can perform a semantic action."""
        if action in self.capabilities:
            return True
        if action in self.fallbacks:
            return True
        # Check prefix match (e.g. "gesture.beat" matches "gesture.*")
        prefix = action.split(".")[0] + ".*"
        return prefix in self.capabilities

    def resolve(self, action: str) -> str:
        """Resolve a semantic action to its actual implementation.

        Returns the action itself if directly supported,
        the fallback if one exists, or the wildcard match.
        """
        if action in self.capabilities:
            return action
        if action in self.fallbacks:
            return self.fallbacks[action]
        prefix = action.split(".")[0] + ".*"
        if prefix in self.capabilities:
            return action  # wildcard supports it
        return action  # compiler will handle missing


# ── Predefined Capability Manifests ────────────────────────────────

HUMANOID_V1 = CapabilityManifest(
    body_class="humanoid-v1",
    capabilities=[
        "locomotion.walk", "locomotion.pace", "locomotion.freeze",
        "locomotion.enter", "locomotion.exit",
        "gaze.audience", "gaze.ella", "gaze.ground", "gaze.sky",
        "gaze.left", "gaze.right", "gaze.away", "gaze.stare",
        "gesture.beat", "gesture.emphasize", "gesture.point",
        "gesture.shrug", "gesture.open_palm", "gesture.dismiss",
        "gesture.come_here", "gesture.stop", "gesture.thumbs_up",
        "gesture.wave",
        "reaction.dead_stare", "reaction.confused", "reaction.annoyed",
        "reaction.enjoy_laugh", "reaction.bored", "reaction.shock",
        "reaction.double_take", "reaction.nervous",
        "pose.confident", "pose.slump", "pose.lean_forward",
        "pose.lean_back", "pose.cross_arms", "pose.hands_on_hips",
        "face.*",
        "procedural.breathing", "procedural.micro_fidget", "procedural.sway",
    ],
    max_gesture_amplitude=1.0,
    supports_additive=True,
    supports_face_expressions=True,
    supports_root_motion=True,
)

QUADRUPED_V1 = CapabilityManifest(
    body_class="quadruped-v1",
    capabilities=[
        "locomotion.walk", "locomotion.pace", "locomotion.freeze",
        "locomotion.enter", "locomotion.exit",
        "gaze.audience", "gaze.ella", "gaze.ground",
        "gaze.left", "gaze.right",
        "gesture.emphasize", "gesture.wave",
        "reaction.dead_stare", "reaction.confused", "reaction.annoyed",
        "reaction.enjoy_laugh", "reaction.nervous",
        "pose.sit", "pose.confident",
        "procedural.breathing", "procedural.sway",
    ],
    fallbacks={
        "gesture.shrug": "gesture.emphasize",
        "gesture.point": "gesture.emphasize",
        "gesture.beat": "gesture.emphasize",
        "gesture.open_palm": "gesture.emphasize",
        "gesture.dismiss": "gesture.emphasize",
        "gaze.stare": "gaze.audience",
        "gaze.sky": "gaze.audience",
        "gaze.away": "gaze.ground",
        "reaction.shock": "reaction.confused",
        "reaction.double_take": "reaction.confused",
        "reaction.bored": "reaction.dead_stare",
        "pose.slump": "pose.sit",
        "pose.lean_forward": "pose.confident",
        "pose.lean_back": "pose.confident",
        "pose.cross_arms": "pose.confident",
        "pose.hands_on_hips": "pose.confident",
        "face.*": "reaction.*",
        "procedural.micro_fidget": "procedural.sway",
    },
    max_gesture_amplitude=0.7,
    supports_additive=False,
    supports_face_expressions=False,
    supports_root_motion=True,
)

RIGID_OBJECT_V1 = CapabilityManifest(
    body_class="rigid-object-v1",
    capabilities=[
        "locomotion.enter", "locomotion.exit", "locomotion.freeze",
        "gaze.audience", "gaze.ella",
        "gesture.emphasize",
        "reaction.dead_stare", "reaction.confused",
        "pose.confident",
    ],
    fallbacks={
        "locomotion.walk": "locomotion.freeze",
        "locomotion.pace": "locomotion.freeze",
        "gesture.beat": "gesture.emphasize",
        "gesture.shrug": "gesture.emphasize",
        "gesture.point": "gesture.emphasize",
        "gesture.open_palm": "gesture.emphasize",
        "gesture.dismiss": "gesture.emphasize",
        "gesture.wave": "gesture.emphasize",
        "gaze.stare": "gaze.audience",
        "gaze.left": "gaze.audience",
        "gaze.right": "gaze.audience",
        "gaze.away": "gaze.audience",
        "gaze.ground": "gaze.audience",
        "gaze.sky": "gaze.audience",
        "reaction.annoyed": "reaction.dead_stare",
        "reaction.bored": "reaction.dead_stare",
        "reaction.enjoy_laugh": "reaction.dead_stare",
        "reaction.shock": "reaction.confused",
        "reaction.nervous": "reaction.dead_stare",
        "pose.*": "pose.confident",
        "face.*": "reaction.*",
        "procedural.*": "gesture.emphasize",
    },
    max_gesture_amplitude=0.5,
    supports_additive=False,
    supports_face_expressions=False,
    supports_root_motion=False,
)

BODY_MANIFESTS: dict[str, CapabilityManifest] = {
    "humanoid-v1": HUMANOID_V1,
    "quadruped-v1": QUADRUPED_V1,
    "rigid-object-v1": RIGID_OBJECT_V1,
}
