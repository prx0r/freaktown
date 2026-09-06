"""motion_assets table — stores motion bank metadata + embeddings.

Revision ID: 002
Revises: 001
Create Date: 2026-09-06

Motion assets are the production seed data for the Killella Motion Language.
Each asset is a retargeted, semantically-tagged animation clip.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "motion_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),

        # Semantic metadata
        sa.Column("semantic", JSONB, nullable=False, server_default="[]"),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("style", JSONB, nullable=False, server_default="[]"),

        # Body compatibility
        sa.Column("body_class", sa.String(30), nullable=False, server_default="humanoid-v1"),

        # Animation properties
        sa.Column("loop", sa.Boolean, server_default="false"),
        sa.Column("root_motion", sa.Boolean, server_default="false"),
        sa.Column("additive", sa.Boolean, server_default="false"),
        sa.Column("bone_mask", sa.String(30), server_default="full"),

        # Physical properties
        sa.Column("energy", sa.Float, server_default="0.5"),
        sa.Column("amplitude", sa.Float, server_default="0.5"),
        sa.Column("duration_ms", sa.Integer, server_default="0"),

        # Source
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=True),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("attribution", sa.Text, nullable=True),

        # Storage
        sa.Column("r2_key", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, server_default="0"),
        sa.Column("format", sa.String(10), server_default="glb"),

        # Embedding (for similarity search — pgvector later)
        sa.Column("embedding", JSONB, nullable=True),

        # Metadata
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for common queries
    op.create_index("ix_motion_assets_body_class", "motion_assets", ["body_class"])
    op.create_index("ix_motion_assets_source", "motion_assets", ["source"])
    op.create_index("ix_motion_assets_semantic", "motion_assets", ["semantic"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("motion_assets")
