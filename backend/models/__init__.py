"""Core domain models: Comedian → Act → Appearance.

The canonical data model:
  Comedian (persistent identity)
    → ActVersion (immutable appearance per episode)
      → Episode (live show instance)
        → ShowEvent (event-sourced timeline)
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


# ── Enums ──────────────────────────────────────────────────────────────

class ComedianStatus(str, enum.Enum):
    ACTIVE = "active"
    RETIRED = "retired"


class BodyArchetype(str, enum.Enum):
    HUMAN = "human"
    DOG = "dog"
    ROBOT = "robot"
    CREATURE = "creature"
    OBJECT = "object"
    MONSTER = "monster"
    ANIMAL = "animal"
    MYSTERY = "mystery"


class Authorship(str, enum.Enum):
    HUMAN = "human"
    ASSISTED = "assisted"
    AI = "ai"


class InterviewController(str, enum.Enum):
    FREAK_TOWN_AI = "freak_town_ai"
    HUMAN = "human"
    EXTERNAL_AGENT = "external_agent"


class EpisodeStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    LOCKED = "locked"
    PREPARING = "preparing"
    READY = "ready"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ShowPhase(str, enum.Enum):
    PRE_SHOW = "pre_show"
    INTRO = "intro"
    LINEUP = "lineup"
    CONTESTANT_ENTER = "contestant_enter"
    SET_ACTIVE = "set_active"
    POST_SET = "post_set"
    JUDGING = "judging"
    ROAST = "roast"
    TRANSITION = "transition"
    LIVE_TEST = "live_test"
    MODEL_REVEAL = "model_reveal"
    ELIMINATION = "elimination"
    FINALE = "finale"
    WINNER = "winner"
    OUTRO = "outro"
    ENDED = "ended"


class ShowEventType(str, enum.Enum):
    # Stage events
    SHOW_SNAPSHOT = "show.snapshot"
    SHOW_PHASE = "show.phase"
    SHOW_PAUSE = "show.pause"
    SHOW_RESUME = "show.resume"
    SHOW_END = "show.end"

    # Avatar events
    STAGE_AVATAR_ENTER = "stage.avatar.enter"
    STAGE_AVATAR_EXIT = "stage.avatar.exit"
    STAGE_AVATAR_LOOK_AT = "stage.avatar.look_at"
    STAGE_AVATAR_GESTURE = "stage.avatar.gesture"
    STAGE_AVATAR_EMOTE = "stage.avatar.emote"

    # Content events
    STAGE_SPEAK = "stage.speak"
    STAGE_CAPTION = "stage.caption"
    STAGE_MUSIC = "stage.music"
    STAGE_SFX = "stage.sfx"

    # Timer events
    TIMER_START = "timer.start"
    TIMER_PAUSE = "timer.pause"
    TIMER_FINISH = "timer.finish"

    # Score/crowd
    SCORE_UPDATE = "score.update"
    SCORE_REVEAL = "score.reveal"
    CROWD_UPDATE = "crowd.update"

    # Model reveal
    MODEL_REVEAL = "model.reveal"

    # Live test
    LIVE_TEST_ISSUE = "live_test.issue"
    LIVE_TEST_RESPONSE = "live_test.response"

    # Ella stage powers
    ELLA_MUTE = "ella.mute"
    ELLA_UNMUTE = "ella.unmute"
    ELLA_MODEL_SWAP = "ella.model_swap"
    ELLA_CONTEXT_CUT = "ella.context_cut"
    ELLA_TEMPERATURE = "ella.temperature"


class ActLinkageStatus(str, enum.Enum):
    ELIGIBLE = "eligible"
    SELECTED = "selected"
    PERFORMED = "performed"
    COMPLETED = "completed"


# ── Comedian ───────────────────────────────────────────────────────────

class Comedian(Base):
    """Persistent identity. Never mutated after creation."""

    __tablename__ = "comedians"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    body_archetype: Mapped[BodyArchetype] = mapped_column(Enum(BodyArchetype), nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ComedianStatus] = mapped_column(Enum(ComedianStatus), default=ComedianStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    versions: Mapped[list["ActVersion"]] = relationship(back_populates="comedian", order_by="ActVersion.version")
    episode_links: Mapped[list["EpisodeContestant"]] = relationship(back_populates="comedian")


class ActVersion(Base):
    """Immutable snapshot of a comedian's act. Never mutated after creation."""

    __tablename__ = "act_versions"
    __table_args__ = (UniqueConstraint("comedian_id", "version", name="uq_act_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comedian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("comedians.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("act_versions.id"), nullable=True
    )

    # Character spec
    character_name: Mapped[str] = mapped_column(String(120), nullable=False)
    character_deal: Mapped[str] = mapped_column(Text, nullable=False)  # "what's their deal"
    body_appearance: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "german_shepherd"
    outfit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    voice_profile: Mapped[str] = mapped_column(String(100), nullable=False, default="default")

    # The minute
    minute_text: Mapped[str] = mapped_column(Text, nullable=False)
    minute_authorship: Mapped[Authorship] = mapped_column(Enum(Authorship), nullable=False)
    minute_ai_assistance: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Interview config
    interview_controller: Mapped[InterviewController] = mapped_column(
        Enum(InterviewController), default=InterviewController.FREAK_TOWN_AI
    )
    interview_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    character_bible: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    character_facts: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list of strings

    # Stage directions
    entrance: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idle_animation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exit_animation: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Creator metadata
    creator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    creator_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hash for immutability
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    comedian: Mapped["Comedian"] = relationship(back_populates="versions")
    parent_version: Mapped["ActVersion | None"] = relationship(
        remote_side="ActVersion.id", foreign_keys=[parent_version_id]
    )
    episode_links: Mapped[list["EpisodeContestant"]] = relationship(back_populates="act_version")


# ── Episode ────────────────────────────────────────────────────────────

class Episode(Base):
    """A live show instance."""

    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[EpisodeStatus] = mapped_column(Enum(EpisodeStatus), default=EpisodeStatus.DRAFT)
    current_phase: Mapped[ShowPhase | None] = mapped_column(Enum(ShowPhase), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic lock

    # Scheduling
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Draw config
    max_contestants: Mapped[int] = mapped_column(Integer, default=5)
    resident_slot: Mapped[bool] = mapped_column(Boolean, default=False)

    # Room packet (hidden challenge environment)
    room_packet: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Winner
    winner_contestant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("episode_contestants.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contestants: Mapped[list["EpisodeContestant"]] = relationship(
        back_populates="episode", order_by="EpisodeContestant.draw_position"
    )
    events: Mapped[list["ShowEvent"]] = relationship(back_populates="episode", order_by="ShowEvent.seq")


class EpisodeContestant(Base):
    """A comedian's appearance in a specific episode. Links to their ActVersion."""

    __tablename__ = "episode_contestants"
    __table_args__ = (UniqueConstraint("episode_id", "comedian_id", name="uq_episode_comedian"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    comedian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("comedians.id"), nullable=False)
    act_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("act_versions.id"), nullable=False)

    # Draw
    draw_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_resident: Mapped[bool] = mapped_column(Boolean, default=False)
    linkage_status: Mapped[ActLinkageStatus] = mapped_column(
        Enum(ActLinkageStatus), default=ActLinkageStatus.ELIGIBLE
    )

    # Performance tracking
    performance_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    performance_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Crowd data snapshot
    peak_laugh_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    crowd_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ella_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)  # KEEP / ELIMINATE / etc.

    # Model reveal
    model_revealed: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    creator_revealed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    episode: Mapped["Episode"] = relationship(back_populates="contestants")
    comedian: Mapped["Comedian"] = relationship(back_populates="episode_links")
    act_version: Mapped["ActVersion"] = relationship(back_populates="episode_links")


# ── Show Events (event sourcing) ───────────────────────────────────────

class ShowEvent(Base):
    """Immutable event in the show timeline. Append-only."""

    __tablename__ = "show_events"
    __table_args__ = (UniqueConstraint("episode_id", "seq", name="uq_episode_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[ShowEventType] = mapped_column(Enum(ShowEventType), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "ella", "contestant_N", "system", "audience"
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    episode: Mapped["Episode"] = relationship(back_populates="events")


# ── Crowd / Audience ───────────────────────────────────────────────────

class AudienceSession(Base):
    """Anonymous audience connection."""

    __tablename__ = "audience_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrowdBucket(Base):
    """Aggregated crowd data per time bucket (1-second resolution)."""

    __tablename__ = "crowd_buckets"
    __table_args__ = (
        UniqueConstraint("episode_id", "contestant_id", "bucket_start", name="uq_crowd_bucket"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    contestant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("episode_contestants.id"), nullable=False
    )
    bucket_start: Mapped[int] = mapped_column(Integer, nullable=False)  # seconds from performance start
    active_viewers: Mapped[int] = mapped_column(Integer, default=0)
    unique_laughers: Mapped[int] = mapped_column(Integer, default=0)
    laugh_events: Mapped[int] = mapped_column(Integer, default=0)
    claps: Mapped[int] = mapped_column(Integer, default=0)
    boos: Mapped[int] = mapped_column(Integer, default=0)


# ── Judges / Scoring ───────────────────────────────────────────────────

class JudgeRun(Base):
    """Ella's evaluation of a performance."""

    __tablename__ = "judge_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contestant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("episode_contestants.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "anthropic", "openai"
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Interview State ────────────────────────────────────────────────────

class InterviewState(Base):
    """Tracks Ella's live conversation state with a contestant."""

    __tablename__ = "interview_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contestant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("episode_contestants.id"), nullable=False, unique=True
    )
    facts: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # discovered facts
    threads: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # open conversational threads
    contradictions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    callbacks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    comedic_targets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    last_action: Mapped[str | None] = mapped_column(String(50), nullable=True)  # PROBE, CHALLENGE, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Generation Provenance ──────────────────────────────────────────────

class GenerationRun(Base):
    """Tracks every LLM/TTS generation for reproducibility."""

    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # "minute", "interview", "tts", "judge"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    usage_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Media Assets ───────────────────────────────────────────────────────

class MediaAsset(Base):
    """Tracks files stored in R2 or local disk."""

    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # "audio", "image", "plan"
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
