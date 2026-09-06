"""initial schema — canonical domain model

Revision ID: 001
Revises:
Create Date: 2026-09-06

This migration matches the canonical domain model per BUILD_BRIEF.md:
  User → Comedian → ActVersion → Submission → Appearance

Enum columns use sa.String with application-level validation via Pydantic.
PostgreSQL native enums are created separately for type safety.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def _create_enum(name, values):
    """Create a PostgreSQL enum type, ignoring if it already exists."""
    op.execute(
        f"DO $$ BEGIN "
        f"CREATE TYPE {name} AS ENUM ({', '.join(repr(v) for v in values)}); "
        f"EXCEPTION WHEN duplicate_object THEN null; END $$"
    )


def upgrade() -> None:
    # ── PostgreSQL enum types (created for type safety, not used as column types) ──
    _create_enum("userrole", ["user", "admin"])
    _create_enum("comedianstatus", ["active", "retired"])
    _create_enum("bodyarchetype", ["human", "dog", "robot", "creature", "object", "monster", "animal", "mystery"])
    _create_enum("authorship", ["human", "assisted", "ai"])
    _create_enum("interviewcontroller", ["freak_town_ai", "human", "external_agent"])
    _create_enum("submissionstatus", ["draft", "submitted", "validating", "eligible", "rejected"])
    _create_enum("episodestatus", ["draft", "open", "locked", "preparing", "ready", "live", "completed", "cancelled", "failed"])
    _create_enum("showphase", [
        "pre_show", "intro", "lineup", "contestant_enter", "set_active", "post_set",
        "judging", "roast", "transition", "live_test", "model_reveal", "elimination",
        "finale", "winner", "outro", "ended",
    ])
    _create_enum("showeventtype", [
        "show.snapshot", "show.phase", "show.pause", "show.resume", "show.end",
        "stage.avatar.enter", "stage.avatar.exit", "stage.avatar.look_at",
        "stage.avatar.gesture", "stage.avatar.emote",
        "stage.speak", "stage.caption", "stage.music", "stage.sfx",
        "timer.start", "timer.pause", "timer.finish",
        "score.update", "score.reveal", "crowd.update",
        "model.reveal", "live_test.issue", "live_test.response",
        "ella.mute", "ella.unmute", "ella.model_swap", "ella.context_cut", "ella.temperature",
        "tip.confirmed",
    ])

    # ── Users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("privy_user_id", sa.String(200), unique=True, nullable=True),
        sa.Column("handle", sa.String(50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), server_default="user"),  # userrole enum
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Comedians ──────────────────────────────────────────────────
    op.create_table(
        "comedians",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False, unique=True),
        sa.Column("premise", sa.Text, nullable=False),
        sa.Column("body_archetype", sa.String(20), nullable=False),  # bodyarchetype enum
        sa.Column("status", sa.String(20), server_default="active"),  # comedianstatus enum
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Act Versions ───────────────────────────────────────────────
    op.create_table(
        "act_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("comedian_id", UUID(as_uuid=True), sa.ForeignKey("comedians.id"), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("parent_act_version_id", UUID(as_uuid=True), sa.ForeignKey("act_versions.id"), nullable=True),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("comedian_id", "revision", name="uq_act_version"),
    )

    # ── Episodes ───────────────────────────────────────────────────
    op.create_table(
        "episodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft"),  # episodestatus enum
        sa.Column("current_phase", sa.String(30), nullable=True),  # showphase enum
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("registration_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_appearances", sa.Integer, server_default="5"),
        sa.Column("resident_slots", sa.Integer, server_default="1"),
        sa.Column("eligible_set_hash", sa.String(64), nullable=True),
        sa.Column("seed_commitment", sa.String(64), nullable=True),
        sa.Column("seed_revealed", sa.String(64), nullable=True),
        sa.Column("draw_result_json", JSONB, nullable=True),
        sa.Column("room_packet", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Submissions ────────────────────────────────────────────────
    op.create_table(
        "submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("comedian_id", UUID(as_uuid=True), sa.ForeignKey("comedians.id"), nullable=False),
        sa.Column("act_version_id", UUID(as_uuid=True), sa.ForeignKey("act_versions.id"), nullable=False),
        sa.Column("submitted_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("qualification_status", sa.String(20), server_default="submitted"),  # submissionstatus
        sa.Column("moderation_status", sa.String(20), server_default="pending"),
        sa.Column("technical_status", sa.String(20), server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.UniqueConstraint("episode_id", "comedian_id", name="uq_episode_comedian_submission"),
    )

    # ── Appearances ────────────────────────────────────────────────
    op.create_table(
        "appearances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("submission_id", UUID(as_uuid=True), sa.ForeignKey("submissions.id"), nullable=False, unique=True),
        sa.Column("draw_position", sa.Integer, nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("performance_plan_id", sa.String(100), nullable=True),
        sa.Column("performance_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performance_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("peak_laugh_share", sa.Float, nullable=True),
        sa.Column("ella_verdict", sa.String(50), nullable=True),
        sa.Column("model_revealed", sa.Boolean, server_default="false"),
        sa.UniqueConstraint("episode_id", "draw_position", name="uq_episode_draw_position"),
    )

    # ── Show Events ────────────────────────────────────────────────
    op.create_table(
        "show_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("type", sa.String(40), nullable=False),  # showeventtype enum
        sa.Column("actor", sa.String(100), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("episode_id", "seq", name="uq_episode_seq"),
    )

    # ── Audience Sessions ──────────────────────────────────────────
    op.create_table(
        "audience_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Crowd Buckets ──────────────────────────────────────────────
    op.create_table(
        "crowd_buckets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("appearance_id", UUID(as_uuid=True), sa.ForeignKey("appearances.id"), nullable=False),
        sa.Column("bucket_start", sa.Integer, nullable=False),
        sa.Column("active_viewers", sa.Integer, server_default="0"),
        sa.Column("unique_laughers", sa.Integer, server_default="0"),
        sa.Column("laugh_events", sa.Integer, server_default="0"),
        sa.Column("claps", sa.Integer, server_default="0"),
        sa.Column("boos", sa.Integer, server_default="0"),
        sa.UniqueConstraint("episode_id", "appearance_id", "bucket_start", name="uq_crowd_bucket"),
    )

    # ── Judge Runs ─────────────────────────────────────────────────
    op.create_table(
        "judge_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("appearance_id", UUID(as_uuid=True), sa.ForeignKey("appearances.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("output_json", JSONB, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Interview States ───────────────────────────────────────────
    op.create_table(
        "interview_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("appearance_id", UUID(as_uuid=True), sa.ForeignKey("appearances.id"), nullable=False, unique=True),
        sa.Column("facts", JSONB, nullable=True),
        sa.Column("threads", JSONB, nullable=True),
        sa.Column("contradictions", JSONB, nullable=True),
        sa.Column("callbacks", JSONB, nullable=True),
        sa.Column("comedic_targets", JSONB, nullable=True),
        sa.Column("turn_count", sa.Integer, server_default="0"),
        sa.Column("last_action", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Generation Runs ────────────────────────────────────────────
    op.create_table(
        "generation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("input_json", JSONB, nullable=True),
        sa.Column("output_json", JSONB, nullable=True),
        sa.Column("usage_json", JSONB, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Media Assets ───────────────────────────────────────────────
    op.create_table(
        "media_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("bytes", sa.Integer, nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── API Keys ───────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scopes", sa.Text, server_default="comedian:read,comedian:create,submission:create,submission:read"),
        sa.Column("rate_limit", sa.Integer, server_default="100"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Sponsor Campaigns ──────────────────────────────────────────
    op.create_table(
        "sponsor_campaigns_v2",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_name", sa.String(200), nullable=False),
        sa.Column("placement", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("creative_json", JSONB, nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget_usd", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sponsor_campaigns_v2")
    op.drop_table("api_keys")
    op.drop_table("media_assets")
    op.drop_table("generation_runs")
    op.drop_table("interview_states")
    op.drop_table("judge_runs")
    op.drop_table("crowd_buckets")
    op.drop_table("audience_sessions")
    op.drop_table("show_events")
    op.drop_table("appearances")
    op.drop_table("submissions")
    op.drop_table("episodes")
    op.drop_table("act_versions")
    op.drop_table("comedians")
    op.drop_table("users")

    for enum_name in [
        "showeventtype", "showphase", "episodestatus", "submissionstatus",
        "interviewcontroller", "authorship", "bodyarchetype", "comedianstatus", "userrole",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
