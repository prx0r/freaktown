"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-09-06

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────
    comedianstatus = sa.Enum("active", "retired", name="comedianstatus")
    comedianstatus.create(op.get_bind(), checkfirst=True)

    bodyarchetype = sa.Enum("human", "dog", "robot", "creature", "object", "monster", "animal", "mystery", name="bodyarchetype")
    bodyarchetype.create(op.get_bind(), checkfirst=True)

    authorship = sa.Enum("human", "assisted", "ai", name="authorship")
    authorship.create(op.get_bind(), checkfirst=True)

    interviewcontroller = sa.Enum("freak_town_ai", "human", "external_agent", name="interviewcontroller")
    interviewcontroller.create(op.get_bind(), checkfirst=True)

    episodestatus = sa.Enum("draft", "open", "locked", "preparing", "ready", "live", "completed", "cancelled", "failed", name="episodestatus")
    episodestatus.create(op.get_bind(), checkfirst=True)

    showphase = sa.Enum(
        "pre_show", "intro", "lineup", "contestant_enter", "set_active", "post_set",
        "judging", "roast", "transition", "live_test", "model_reveal", "elimination",
        "finale", "winner", "outro", "ended",
        name="showphase",
    )
    showphase.create(op.get_bind(), checkfirst=True)

    showeventtype = sa.Enum(
        "show.snapshot", "show.phase", "show.pause", "show.resume", "show.end",
        "stage.avatar.enter", "stage.avatar.exit", "stage.avatar.look_at",
        "stage.avatar.gesture", "stage.avatar.emote",
        "stage.speak", "stage.caption", "stage.music", "stage.sfx",
        "timer.start", "timer.pause", "timer.finish",
        "score.update", "score.reveal", "crowd.update",
        "model.reveal", "live_test.issue", "live_test.response",
        "ella.mute", "ella.unmute", "ella.model_swap", "ella.context_cut", "ella.temperature",
        name="showeventtype",
    )
    showeventtype.create(op.get_bind(), checkfirst=True)

    actlinkagestatus = sa.Enum("eligible", "selected", "performed", "completed", name="actlinkagestatus")
    actlinkagestatus.create(op.get_bind(), checkfirst=True)

    # ── Comedians ──────────────────────────────────────────────────
    op.create_table(
        "comedians",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("slug", sa.String(140), nullable=False, unique=True),
        sa.Column("body_archetype", bodyarchetype, nullable=False),
        sa.Column("premise", sa.Text, nullable=False),
        sa.Column("status", comedianstatus, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Act Versions ───────────────────────────────────────────────
    op.create_table(
        "act_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("comedian_id", UUID(as_uuid=True), sa.ForeignKey("comedians.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("parent_version_id", UUID(as_uuid=True), sa.ForeignKey("act_versions.id"), nullable=True),
        sa.Column("character_name", sa.String(120), nullable=False),
        sa.Column("character_deal", sa.Text, nullable=False),
        sa.Column("body_appearance", sa.String(200), nullable=True),
        sa.Column("outfit", sa.String(200), nullable=True),
        sa.Column("voice_profile", sa.String(100), nullable=False, server_default="default"),
        sa.Column("minute_text", sa.Text, nullable=False),
        sa.Column("minute_authorship", authorship, nullable=False),
        sa.Column("minute_ai_assistance", sa.Text, nullable=True),
        sa.Column("interview_controller", interviewcontroller, server_default="freak_town_ai"),
        sa.Column("interview_model", sa.String(100), nullable=True),
        sa.Column("character_bible", JSONB, nullable=True),
        sa.Column("character_facts", JSONB, nullable=True),
        sa.Column("entrance", sa.String(100), nullable=True),
        sa.Column("idle_animation", sa.String(100), nullable=True),
        sa.Column("exit_animation", sa.String(100), nullable=True),
        sa.Column("creator_id", sa.String(100), nullable=True),
        sa.Column("creator_note", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("comedian_id", "version", name="uq_act_version"),
    )

    # ── Episodes ───────────────────────────────────────────────────
    op.create_table(
        "episodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", episodestatus, server_default="draft"),
        sa.Column("current_phase", showphase, nullable=True),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("registration_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_contestants", sa.Integer, server_default="5"),
        sa.Column("resident_slot", sa.Boolean, server_default="false"),
        sa.Column("room_packet", JSONB, nullable=True),
        sa.Column("winner_contestant_id", UUID(as_uuid=True), sa.ForeignKey("episode_contestants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Episode Contestants ────────────────────────────────────────
    op.create_table(
        "episode_contestants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("comedian_id", UUID(as_uuid=True), sa.ForeignKey("comedians.id"), nullable=False),
        sa.Column("act_version_id", UUID(as_uuid=True), sa.ForeignKey("act_versions.id"), nullable=False),
        sa.Column("draw_position", sa.Integer, nullable=True),
        sa.Column("is_resident", sa.Boolean, server_default="false"),
        sa.Column("linkage_status", actlinkagestatus, server_default="eligible"),
        sa.Column("performance_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performance_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("peak_laugh_share", sa.Float, nullable=True),
        sa.Column("crowd_score", sa.Float, nullable=True),
        sa.Column("ella_verdict", sa.String(50), nullable=True),
        sa.Column("model_revealed", sa.Boolean, server_default="false"),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("creator_revealed", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("episode_id", "comedian_id", name="uq_episode_comedian"),
    )

    # Now add the FK from episodes to episode_contestants
    op.create_foreign_key("fk_episode_winner", "episodes", "episode_contestants", ["winner_contestant_id"], ["id"])

    # ── Show Events ────────────────────────────────────────────────
    op.create_table(
        "show_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("type", showeventtype, nullable=False),
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
        sa.Column("contestant_id", UUID(as_uuid=True), sa.ForeignKey("episode_contestants.id"), nullable=False),
        sa.Column("bucket_start", sa.Integer, nullable=False),
        sa.Column("active_viewers", sa.Integer, server_default="0"),
        sa.Column("unique_laughers", sa.Integer, server_default="0"),
        sa.Column("laugh_events", sa.Integer, server_default="0"),
        sa.Column("claps", sa.Integer, server_default="0"),
        sa.Column("boos", sa.Integer, server_default="0"),
        sa.UniqueConstraint("episode_id", "contestant_id", "bucket_start", name="uq_crowd_bucket"),
    )

    # ── Judge Runs ─────────────────────────────────────────────────
    op.create_table(
        "judge_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("contestant_id", UUID(as_uuid=True), sa.ForeignKey("episode_contestants.id"), nullable=False),
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
        sa.Column("contestant_id", UUID(as_uuid=True), sa.ForeignKey("episode_contestants.id"), nullable=False, unique=True),
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


def downgrade() -> None:
    op.drop_table("media_assets")
    op.drop_table("generation_runs")
    op.drop_table("interview_states")
    op.drop_table("judge_runs")
    op.drop_table("crowd_buckets")
    op.drop_table("audience_sessions")
    op.drop_table("show_events")
    op.drop_table("episode_contestants")
    op.drop_table("episodes")
    op.drop_table("act_versions")
    op.drop_table("comedians")

    sa.Enum(name="actlinkagestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="showeventtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="showphase").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="episodestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="interviewcontroller").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="authorship").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="bodyarchetype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="comedianstatus").drop(op.get_bind(), checkfirst=True)
