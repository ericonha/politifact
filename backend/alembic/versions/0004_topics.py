"""Seções temáticas em notícias e histórias

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("feed_categories", JSONB))
    op.add_column("articles", sa.Column("topic", sa.String(32)))
    op.add_column("articles", sa.Column("topic_source", sa.String(16)))
    op.create_index("ix_articles_topic", "articles", ["topic"])
    op.add_column("stories", sa.Column("topic", sa.String(32)))
    op.create_index("ix_stories_topic", "stories", ["topic"])
    # Os artigos já coletados são classificados por `python -m app.topics_backfill`,
    # que o serviço `migrate` roda logo depois das migrações.


def downgrade() -> None:
    op.drop_index("ix_stories_topic", table_name="stories")
    op.drop_column("stories", "topic")
    op.drop_index("ix_articles_topic", table_name="articles")
    op.drop_column("articles", "topic_source")
    op.drop_column("articles", "topic")
    op.drop_column("articles", "feed_categories")
