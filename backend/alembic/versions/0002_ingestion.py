"""Fase 2: campos de ingestão

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("feed_guid", sa.Text))
    op.create_index("ix_articles_outlet_published", "articles", ["outlet_id", "published_at"])
    op.create_index("ix_collection_runs_started_at", "collection_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_collection_runs_started_at", table_name="collection_runs")
    op.drop_index("ix_articles_outlet_published", table_name="articles")
    op.drop_column("articles", "feed_guid")
