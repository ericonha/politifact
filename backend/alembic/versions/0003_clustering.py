"""Fase 3: deduplicação, embeddings e decisões de agrupamento

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vetor sem dimensão fixa: permite trocar de modelo sem migração.
    # (Um índice HNSW exige dimensão fixa; não precisamos dele por enquanto,
    # porque a comparação é feita em Python sobre as últimas 48–72 h.)
    op.add_column("articles", sa.Column("embedding", Vector()))
    op.add_column("articles", sa.Column("embedding_model", sa.String(128)))
    op.add_column("articles", sa.Column("duplicate_of_id", sa.BigInteger, sa.ForeignKey("articles.id")))
    op.add_column("articles", sa.Column("duplicate_method", sa.String(32)))
    op.create_index("ix_articles_duplicate_of_id", "articles", ["duplicate_of_id"])

    op.create_table(
        "clustering_decisions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("article_id", sa.BigInteger, sa.ForeignKey("articles.id"), nullable=False, index=True),
        sa.Column("story_id", sa.BigInteger, sa.ForeignKey("stories.id"), index=True),
        sa.Column("candidate_story_id", sa.BigInteger, sa.ForeignKey("stories.id")),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("details", JSONB),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by_id", sa.BigInteger, sa.ForeignKey("clustering_decisions.id")),
    )
    op.create_index(
        "ix_clustering_decisions_pending",
        "clustering_decisions",
        ["decision"],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_clustering_decisions_pending", table_name="clustering_decisions")
    op.drop_table("clustering_decisions")
    op.drop_index("ix_articles_duplicate_of_id", table_name="articles")
    op.drop_column("articles", "duplicate_method")
    op.drop_column("articles", "duplicate_of_id")
    op.drop_column("articles", "embedding_model")
    op.drop_column("articles", "embedding")
