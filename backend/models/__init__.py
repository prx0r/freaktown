"""Core domain models: User → Comedian → ActVersion → Submission → Appearance.

The canonical data model from BUILD_BRIEF.md:
  User (authenticated creator)
    → Comedian (persistent identity)
      → ActVersion (immutable frozen incarnation)
        → Submission (joins The Line for an episode)
          → Appearance (selected into live show)
            → ShowEvent[] (event-sourced timeline)
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
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

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


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


class SubmissionStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    ELIGIBLE = "eligible"
    REJECTED = "rejected"


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

    # Tips
    TIP_CONFIRMED = "tip.confirmed"


# ── User ───────────────────────────────────────────────────────────────

class User(Base):
    """Authenticated creator. Identity resolved from auth token, never from browser."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    privy_user_id: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    handle: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    comedians: Mapped[list["Comedian"]] = relationship(back_populates="owner")


# ── Comedian ───────────────────────────────────────────────────────────

class Comedian(Base):
    """Persistent public character identity. Owned by a User."""

    __tablename__ = "comedians"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # NOT globally unique
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    body_archetype: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="comedians")
    versions: Mapped[list["ActVersion"]] = relationship(back_populates="comedian", order_by="ActVersion.revision")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="comedian")


# ── ActVersion ─────────────────────────────────────────────────────────

class ActVersion(Base):
    """Immutable frozen incarnation of a comedian. Never mutated after sealed_at."""

    __tablename__ = "act_versions"
    __table_args__ = (UniqueConstraint("comedian_id", "revision", name="uq_act_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comedian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("comedians.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_act_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("act_versions.id"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # The full manifest as JSONB (per BUILD_BRIEF.md section 5)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # full 64 hex chars

    # Performance Engine config (Killella Motion Language)
    performance_engine_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    comedian: Mapped["Comedian"] = relationship(back_populates="versions")
    parent_version: Mapped["ActVersion | None"] = relationship(
        remote_side="ActVersion.id", foreign_keys=[parent_act_version_id]
    )
    submissions: Mapped[list["Submission"]] = relationship(back_populates="act_version")


# ── Submission ─────────────────────────────────────────────────────────

class Submission(Base):
    """Joining The Line. An episode may have 10,000 submissions but only 5 appearance slots."""

    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    comedian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("comedians.id"), nullable=False)
    act_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("act_versions.id"), nullable=False)
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    qualification_status: Mapped[str] = mapped_column(
        String(20), default="submitted"
    )
    moderation_status: Mapped[str] = mapped_column(String(20), default="pending")
    technical_status: Mapped[str] = mapped_column(String(20), default="pending")

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    episode: Mapped["Episode"] = relationship(back_populates="submissions")
    comedian: Mapped["Comedian"] = relationship(back_populates="submissions")
    act_version: Mapped["ActVersion"] = relationship(back_populates="submissions")
    appearance: Mapped["Appearance | None"] = relationship(back_populates="submission", uselist=False)


# ── Episode ────────────────────────────────────────────────────────────

class Episode(Base):
    """A live show instance."""

    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    current_phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Scheduling
    registration_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Draw config
    max_appearances: Mapped[int] = mapped_column(Integer, default=5)
    resident_slots: Mapped[int] = mapped_column(Integer, default=1)

    # Draw verification
    eligible_set_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed_commitment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed_revealed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    draw_result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Room packet (hidden challenge environment)
    room_packet: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    submissions: Mapped[list["Submission"]] = relationship(back_populates="episode")
    appearances: Mapped[list["Appearance"]] = relationship(back_populates="episode", order_by="Appearance.draw_position")
    events: Mapped[list["ShowEvent"]] = relationship(back_populates="episode", order_by="ShowEvent.seq")


# ── Appearance ─────────────────────────────────────────────────────────

class Appearance(Base):
    """Created only when a Submission is selected in the draw. Freezes the exact ActVersion."""

    __tablename__ = "appearances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False)
    draw_position: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Performance
    performance_plan_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    performance_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    performance_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Results
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    peak_laugh_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    ella_verdict: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_revealed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    episode: Mapped["Episode"] = relationship(back_populates="appearances")
    submission: Mapped["Submission"] = relationship(back_populates="appearance")


# ── Show Events (event sourcing) ───────────────────────────────────────

class ShowEvent(Base):
    """Immutable event in the show timeline. Append-only. seq allocated by EpisodeRoom."""

    __tablename__ = "show_events"
    __table_args__ = (UniqueConstraint("episode_id", "seq", name="uq_episode_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
        UniqueConstraint("episode_id", "appearance_id", "bucket_start", name="uq_crowd_bucket"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id"), nullable=False)
    appearance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appearances.id"), nullable=False
    )
    bucket_start: Mapped[int] = mapped_column(Integer, nullable=False)
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
    appearance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appearances.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Interview State ────────────────────────────────────────────────────

class InterviewState(Base):
    """Tracks Ella's live conversation state with an appearance."""

    __tablename__ = "interview_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appearance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appearances.id"), nullable=False, unique=True
    )
    facts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    threads: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    contradictions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    callbacks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    comedic_targets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    last_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Generation Provenance ──────────────────────────────────────────────

class GenerationRun(Base):
    """Tracks every LLM/TTS generation for reproducibility."""

    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
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
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Sponsor (placeholder) ─────────────────────────────────────────────

class SponsorCampaign(Base):
    """Sponsor campaign — placeholder for future implementation."""

    __tablename__ = "sponsor_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand: Mapped[str] = mapped_column(String(200), nullable=False)
    placement: Mapped[str] = mapped_column(String(50), nullable=False)  # OPENING_READ, TRANSITION, etc.
    creative_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
