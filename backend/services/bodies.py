"""Body family animation system.

Per BUILD_BRIEF.md section 22:
  - Define BodyAdapter interface
  - Initial adapters: HumanoidVRMAdapter, DogGLBAdapter, RobotGLBAdapter, ObjectGLBAdapter
  - Characters select a body definition, they do not supply code
  - No arbitrary GLB uploads in MVP
"""

from dataclasses import dataclass, field


# ── Body Definitions ───────────────────────────────────────────────────

@dataclass
class BodyDefinition:
    """Defines a body family and its capabilities."""
    id: str  # "dog.german-shepherd.v1"
    family: str  # "dog"
    variant: str  # "german-shepherd"
    asset_url: str  # URL to GLB/VRM file
    supported_gestures: list[str] = field(default_factory=list)
    supported_emotions: list[str] = field(default_factory=list)
    mouth_mode: str = "jaw"  # "jaw", "viseme", "none"
    description: str = ""


# ── Gesture Catalog ────────────────────────────────────────────────────

GESTURES = {
    # Universal
    "idle": "Standing idle",
    "enter": "Walking onto stage",
    "exit": "Walking off stage",
    "wave": "Waving hello",
    "bow": "Taking a bow",

    # Hand gestures
    "open_hand": "Open palm gesture",
    "point": "Pointing at something",
    "fist": "Clenched fist",
    "shrug": "Shrugging",
    "dismiss": "Dismissive wave",
    "come_here": "Beckoning gesture",
    "stop": "Hand up stop gesture",
    "thumbs_up": "Thumbs up",
    "peace": "Peace sign",

    # Body
    "lean_forward": "Leaning in",
    "lean_back": "Leaning back",
    "cross_arms": "Arms crossed",
    "hands_on_hips": "Hands on hips",
    "dramatic_pose": "Dramatic pose",
    "slump": "Slumping in defeat",

    # Head
    "nod": "Nodding yes",
    "shake": "Shaking no",
    "tilt": "Head tilt",
    "look_left": "Looking left",
    "look_right": "Looking right",
    "look_up": "Looking up",
    "look_down": "Looking down",

    # Reactions
    "laugh": "Laughing",
    "facepalm": "Facepalm",
    "jaw_drop": "Jaw dropping in shock",
    "eye_roll": "Rolling eyes",
}

# ── Emotion Catalog ────────────────────────────────────────────────────

EMOTIONS = {
    "neutral": "Neutral expression",
    "confident": "Confident, self-assured",
    "confused": "Confused, puzzled",
    "angry": "Angry, frustrated",
    "happy": "Happy, delighted",
    "sad": "Sad, disappointed",
    "scared": "Scared, frightened",
    "disgusted": "Disgusted, repulsed",
    "surprised": "Surprised, shocked",
    "menacing": "Menacing, threatening",
    "warm": "Warm, affectionate",
    "contempt": "Contemptuous, dismissive",
    "bored": "Bored, unimpressed",
    "excited": "Excited, enthusiastic",
    "embarrassed": "Embarrassed, awkward",
}

# ── Body Catalog ───────────────────────────────────────────────────────

BODY_CATALOG: list[BodyDefinition] = [
    # Humanoid
    BodyDefinition(
        id="human.default.v1",
        family="human",
        variant="default",
        asset_url="/assets/bodies/human-default.vrm",
        supported_gestures=list(GESTURES.keys()),
        supported_emotions=list(EMOTIONS.keys()),
        mouth_mode="viseme",
        description="Standard human avatar",
    ),

    # Dog
    BodyDefinition(
        id="dog.german-shepherd.v1",
        family="dog",
        variant="german-shepherd",
        asset_url="/assets/bodies/dog-german-shepherd.glb",
        supported_gestures=["idle", "enter", "exit", "sit", "stand", "shake", "look_left", "look_right"],
        supported_emotions=["neutral", "happy", "sad", "confused", "angry", "excited"],
        mouth_mode="jaw",
        description="German Shepherd dog",
    ),
    BodyDefinition(
        id="dog.golden-retriever.v1",
        family="dog",
        variant="golden-retriever",
        asset_url="/assets/bodies/dog-golden-retriever.glb",
        supported_gestures=["idle", "enter", "exit", "sit", "stand", "shake", "look_left", "look_right"],
        supported_emotions=["neutral", "happy", "sad", "confused", "angry", "excited"],
        mouth_mode="jaw",
        description="Golden Retriever dog",
    ),

    # Robot
    BodyDefinition(
        id="robot.customer-service.v1",
        family="robot",
        variant="customer-service",
        asset_url="/assets/bodies/robot-customer-service.glb",
        supported_gestures=["idle", "enter", "exit", "wave", "point", "shrug", "nod", "shake"],
        supported_emotions=["neutral", "confused", "angry", "happy", "bored"],
        mouth_mode="none",
        description="Customer service robot with name tag",
    ),
    BodyDefinition(
        id="robot.industrial.v1",
        family="robot",
        variant="industrial",
        asset_url="/assets/bodies/robot-industrial.glb",
        supported_gestures=["idle", "enter", "exit", "point", "fist"],
        supported_emotions=["neutral", "angry"],
        mouth_mode="none",
        description="Heavy industrial robot",
    ),

    # Object
    BodyDefinition(
        id="object.roomba.v1",
        family="object",
        variant="roomba",
        asset_url="/assets/bodies/object-roomba.glb",
        supported_gestures=["idle", "enter", "exit", "spin", "bump"],
        supported_emotions=["neutral", "confused", "excited"],
        mouth_mode="none",
        description="Robot vacuum cleaner",
    ),
    BodyDefinition(
        id="object.toaster.v1",
        family="object",
        variant="toaster",
        asset_url="/assets/bodies/object-toaster.glb",
        supported_gestures=["idle", "enter", "exit", "pop", "shake"],
        supported_emotions=["neutral", "angry", "happy"],
        mouth_mode="none",
        description="Kitchen toaster",
    ),

    # Animal
    BodyDefinition(
        id="animal.pigeon.v1",
        family="animal",
        variant="pigeon",
        asset_url="/assets/bodies/animal-pigeon.glb",
        supported_gestures=["idle", "enter", "exit", "coo", "head_bob", "fly"],
        supported_emotions=["neutral", "confused", "scared", "angry"],
        mouth_mode="none",
        description="City pigeon",
    ),

    # Creature
    BodyDefinition(
        id="creature.goblin.v1",
        family="creature",
        variant="goblin",
        asset_url="/assets/bodies/creature-goblin.glb",
        supported_gestures=list(GESTURES.keys()),
        supported_emotions=list(EMOTIONS.keys()),
        mouth_mode="jaw",
        description="Mischievous goblin",
    ),

    # Mystery
    BodyDefinition(
        id="mystery.shadow.v1",
        family="mystery",
        variant="shadow",
        asset_url="/assets/bodies/mystery-shadow.glb",
        supported_gestures=["idle", "enter", "exit", "point"],
        supported_emotions=["neutral", "menacing"],
        mouth_mode="none",
        description="Mysterious shadow figure",
    ),
]


# ── Body Service ───────────────────────────────────────────────────────

class BodyService:
    """Manages body definitions and animations."""

    def get_catalog(self) -> list[dict]:
        """Get the full body catalog."""
        return [
            {
                "id": b.id,
                "family": b.family,
                "variant": b.variant,
                "description": b.description,
                "gestures": b.supported_gestures,
                "emotions": b.supported_emotions,
                "mouth_mode": b.mouth_mode,
            }
            for b in BODY_CATALOG
        ]

    def get_body(self, body_id: str) -> BodyDefinition | None:
        """Get a specific body definition."""
        for b in BODY_CATALOG:
            if b.id == body_id:
                return b
        return None

    def get_bodies_by_family(self, family: str) -> list[BodyDefinition]:
        """Get all bodies for a family."""
        return [b for b in BODY_CATALOG if b.family == family]

    def validate_gesture(self, body_id: str, gesture: str) -> bool:
        """Check if a body supports a gesture."""
        body = self.get_body(body_id)
        if not body:
            return False
        return gesture in body.supported_gestures

    def validate_emotion(self, body_id: str, emotion: str) -> bool:
        """Check if a body supports an emotion."""
        body = self.get_body(body_id)
        if not body:
            return False
        return emotion in body.supported_emotions


# Singleton
body_service = BodyService()
