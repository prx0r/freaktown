"""Motion Asset — a single retargeted, semantically-tagged animation clip.

Stored in R2, indexed in Postgres. The motion bank is the production
seed data that makes the semantic movement language actually work.

Reference: anime.dm
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MotionAsset:
    """A single animation clip with semantic metadata.

    Each asset is normalized to a canonical rig (killella-humanoid-v1),
    semantically tagged, and embeddable for motion search.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""                    # "beat_hand_01", "shrug_03"

    # Semantic tags (what this motion MEANS)
    semantic: list[str] = field(default_factory=list)  # ["gesture.beat", "gesture.emphasize"]
    text: str = ""                    # natural language: "small irritated hand emphasis"
    style: list[str] = field(default_factory=list)     # ["annoyed", "restrained", "deadpan"]

    # Body compatibility
    body_class: str = "humanoid-v1"   # which body this was normalized to

    # Animation properties
    loop: bool = False
    root_motion: bool = False
    additive: bool = False            # can be layered on top of base
    bone_mask: str = "full"           # "full", "upper_body", "head", "face"

    # Physical properties
    energy: float = 0.5               # 0=still 1=energetic
    amplitude: float = 0.5            # 0=tiny 1=huge
    duration_ms: int = 0              # 0 = use animation default

    # Source
    source: str = ""                  # "mixamo", "cmu", "100style", "killella"
    source_file: str = ""             # original filename
    license: str = ""                 # "royalty-free", "CC-BY-4.0", etc.
    attribution: str = ""             # required attribution text

    # Storage
    r2_key: str = ""                  # "motions/humanoid-v1/beat_hand_01.glb"
    file_size_bytes: int = 0
    format: str = "glb"              # "glb", "bvh", "vrma"

    # Embedding (for similarity search)
    embedding: list[float] | None = None  # vector embedding for semantic search

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "semantic": self.semantic,
            "text": self.text,
            "style": self.style,
            "body_class": self.body_class,
            "loop": self.loop,
            "additive": self.additive,
            "bone_mask": self.bone_mask,
            "energy": self.energy,
            "amplitude": self.amplitude,
            "duration_ms": self.duration_ms,
            "source": self.source,
            "license": self.license,
        }


# ── Seed Motion Catalog ────────────────────────────────────────────

SEED_MOTIONS = [
    # === IDLE ===
    MotionAsset(name="idle_neutral", semantic=["procedural.breathing"], text="neutral standing idle",
                style=["calm"], loop=True, additive=True, bone_mask="full", energy=0.1, amplitude=0.05,
                source="killella", license="proprietary"),
    MotionAsset(name="idle_nervous", semantic=["procedural.micro_fidget", "reaction.nervous"],
                text="restless fidgeting idle", style=["nervous", "anxious"], loop=True, additive=True,
                bone_mask="upper_body", energy=0.3, amplitude=0.15, source="killella", license="proprietary"),
    MotionAsset(name="idle_confident", semantic=["pose.confident", "procedural.breathing"],
                text="strong confident standing", style=["confident", "powerful"], loop=True,
                bone_mask="full", energy=0.2, amplitude=0.03, source="killella", license="proprietary"),
    MotionAsset(name="idle_slump", semantic=["pose.slump"], text="defeated slumped posture",
                style=["defeated", "tired"], loop=True, bone_mask="full", energy=0.05, amplitude=0.02,
                source="killella", license="proprietary"),

    # === GESTURE ===
    MotionAsset(name="beat_hand_01", semantic=["gesture.beat"], text="small rhythmic hand emphasis",
                style=["casual", "conversational"], loop=False, additive=True, bone_mask="upper_body",
                energy=0.3, amplitude=0.3, duration_ms=400, source="killella", license="proprietary"),
    MotionAsset(name="beat_hand_02", semantic=["gesture.beat"], text="subtle finger tap emphasis",
                style=["restrained", "precise"], loop=False, additive=True, bone_mask="upper_body",
                energy=0.2, amplitude=0.2, duration_ms=350, source="killella", license="proprietary"),
    MotionAsset(name="emphasize_01", semantic=["gesture.emphasize"], text="strong open hand emphasis",
                style=["passionate", "forceful"], loop=False, additive=True, bone_mask="upper_body",
                energy=0.7, amplitude=0.7, duration_ms=600, source="killella", license="proprietary"),
    MotionAsset(name="emphasize_02", semantic=["gesture.emphasize"], text="fist pump emphasis",
                style=["aggressive", "intense"], loop=False, additive=True, bone_mask="upper_body",
                energy=0.8, amplitude=0.8, duration_ms=500, source="killella", license="proprietary"),
    MotionAsset(name="shrug_01", semantic=["gesture.shrug"], text="classic shoulder shrug",
                style=["uncertain", "dismissive"], loop=False, bone_mask="upper_body",
                energy=0.3, amplitude=0.4, duration_ms=800, source="killella", license="proprietary"),
    MotionAsset(name="point_01", semantic=["gesture.point"], text="accusatory point",
                style=["direct", "confrontational"], loop=False, bone_mask="upper_body",
                energy=0.6, amplitude=0.6, duration_ms=500, source="killella", license="proprietary"),
    MotionAsset(name="point_02", semantic=["gesture.point"], text="casual reference point",
                style=["casual", "conversational"], loop=False, bone_mask="upper_body",
                energy=0.3, amplitude=0.3, duration_ms=400, source="killella", license="proprietary"),
    MotionAsset(name="open_palm_01", semantic=["gesture.open_palm"], text="open palm pleading gesture",
                style=["sincere", "vulnerable"], loop=False, bone_mask="upper_body",
                energy=0.4, amplitude=0.4, duration_ms=700, source="killella", license="proprietary"),
    MotionAsset(name="wave_01", semantic=["gesture.wave"], text="simple hello wave",
                style=["friendly", "warm"], loop=False, bone_mask="upper_body",
                energy=0.4, amplitude=0.5, duration_ms=1000, source="killella", license="proprietary"),

    # === GAZE ===
    MotionAsset(name="stare_01", semantic=["gaze.stare", "reaction.dead_stare"],
                text="intense blank stare", style=["deadpan", "intense"], loop=True,
                bone_mask="head", energy=0.1, amplitude=0.02, source="killella", license="proprietary"),
    MotionAsset(name="look_away_01", semantic=["gaze.away"], text="deliberate look away",
                style=["avoidant", "uncomfortable"], loop=False, bone_mask="head",
                energy=0.1, amplitude=0.05, duration_ms=600, source="killella", license="proprietary"),
    MotionAsset(name="look_ella_01", semantic=["gaze.ella"], text="look toward host",
                style=["engaged", "attentive"], loop=False, bone_mask="head",
                energy=0.2, amplitude=0.05, duration_ms=500, source="killella", license="proprietary"),
    MotionAsset(name="look_audience_01", semantic=["gaze.audience"], text="scan audience",
                style=["connecting", "inclusive"], loop=False, bone_mask="head",
                energy=0.2, amplitude=0.08, duration_ms=1200, source="killella", license="proprietary"),

    # === REACTION ===
    MotionAsset(name="double_take_01", semantic=["reaction.double_take"], text="quick look away then snap back",
                style=["surprised", "comedic"], loop=False, bone_mask="head",
                energy=0.5, amplitude=0.1, duration_ms=800, source="killella", license="proprietary"),
    MotionAsset(name="enjoy_laugh_01", semantic=["reaction.enjoy_laugh"], text="subtle smile during audience laugh",
                style=["warm", "genuine"], loop=False, bone_mask="face",
                energy=0.2, amplitude=0.1, duration_ms=2000, source="killella", license="proprietary"),
    MotionAsset(name="annoyed_01", semantic=["reaction.annoyed"], text="slight eye roll and head turn",
                style=["irritated", "done"], loop=False, bone_mask="head",
                energy=0.3, amplitude=0.15, duration_ms=900, source="killella", license="proprietary"),
    MotionAsset(name="nervous_fidget_01", semantic=["reaction.nervous"], text="hand wringing fidget",
                style=["nervous", "uncomfortable"], loop=True, additive=True, bone_mask="upper_body",
                energy=0.4, amplitude=0.2, source="killella", license="proprietary"),

    # === LOCOMOTION ===
    MotionAsset(name="enter_stage_01", semantic=["locomotion.enter"], text="confident walk onto stage",
                style=["confident", "bold"], loop=False, root_motion=True, bone_mask="full",
                energy=0.5, amplitude=0.3, duration_ms=3000, source="killella", license="proprietary"),
    MotionAsset(name="exit_stage_01", semantic=["locomotion.exit"], text="walk off stage",
                style=["neutral"], loop=False, root_motion=True, bone_mask="full",
                energy=0.4, amplitude=0.3, duration_ms=2500, source="killella", license="proprietary"),
    MotionAsset(name="pace_01", semantic=["locomotion.pace"], text="slow deliberate pacing",
                style=["contemplative", "restless"], loop=True, root_motion=True, bone_mask="full",
                energy=0.3, amplitude=0.15, source="killella", license="proprietary"),

    # === FACE ===
    MotionAsset(name="smile_01", semantic=["face.smile"], text="genuine warm smile",
                style=["warm", "friendly"], loop=False, bone_mask="face",
                energy=0.3, amplitude=0.3, duration_ms=1500, source="killella", license="proprietary"),
    MotionAsset(name="deadpan_01", semantic=["face.deadpan"], text="completely flat expression",
                style=["deadpan", "unimpressed"], loop=True, bone_mask="face",
                energy=0.0, amplitude=0.0, source="killella", license="proprietary"),
    MotionAsset(name="surprised_01", semantic=["face.surprised"], text="raised eyebrows surprise",
                style=["surprised", "shocked"], loop=False, bone_mask="face",
                energy=0.5, amplitude=0.4, duration_ms=600, source="killella", license="proprietary"),
]
