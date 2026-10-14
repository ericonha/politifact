"""Edições de manchete: versões posteriores de título e resumo

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_revisions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("article_id", sa.BigInteger, sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("headline", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("change", JSONB),
        sa.UniqueConstraint("article_id", "content_hash", name="uq_article_revisions_hash"),
    )
    op.create_index("ix_article_revisions_article_id", "article_revisions", ["article_id"])
    op.create_index("ix_article_revisions_observed_at", "article_revisions", ["observed_at"])


def downgrade() -> None:
    op.drop_table("article_revisions")
