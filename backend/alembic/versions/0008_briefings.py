"""Resumos por seção gerados por IA (append-only)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "briefings",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("topic", sa.String(32), nullable=False),
        sa.Column("window", sa.String(8), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("story_ids", JSONB, nullable=False),
        sa.Column("result", JSONB),
        sa.Column("validation", JSONB),
        sa.Column("error", sa.Text),
    )
    op.create_index("ix_briefings_topic_window_generated", "briefings", ["topic", "window", "generated_at"])


def downgrade() -> None:
    op.drop_index("ix_briefings_topic_window_generated", table_name="briefings")
    op.drop_table("briefings")
