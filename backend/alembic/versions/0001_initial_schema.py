"""Esquema inicial (seção 9 do plano)

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name: str, nullable: bool = True, default_now: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.func.now() if default_now else None,
    )


def upgrade() -> None:
    # pgvector fica habilitado desde já; as colunas de embedding entram na fase 3.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "outlets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("canonical_domain", sa.String(255), nullable=False, unique=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("feed_urls", JSONB, nullable=False, server_default="[]"),
        sa.Column("collection_notes", sa.Text),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        _ts("created_at", nullable=False, default_now=True),
    )

    op.create_table(
        "outlet_bias_ratings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("outlet_id", sa.Integer, sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(200), nullable=False),
        sa.Column("rating", sa.String(32), nullable=False),
        sa.Column("methodology_url", sa.Text),
        sa.Column("reference_url", sa.Text),
        _ts("assessed_at"),
        _ts("valid_from"),
        _ts("valid_until"),
        sa.Column("confidence", sa.Float),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "articles",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("outlet_id", sa.Integer, sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("canonical_url", sa.Text, nullable=False),
        sa.Column("original_url", sa.Text, nullable=False),
        sa.Column("headline", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        _ts("published_at"),
        _ts("updated_at"),
        _ts("first_seen_at", nullable=False, default_now=True),
        _ts("collected_at", nullable=False, default_now=True),
        sa.Column("language", sa.String(10)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("content_reference", sa.Text),
        sa.Column("collection_provider", sa.String(64), nullable=False),
        sa.Column("processing_status", sa.String(32), nullable=False, server_default="new"),
        sa.UniqueConstraint("canonical_url", name="uq_articles_canonical_url"),
    )
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_content_hash", "articles", ["content_hash"])
    op.create_index("ix_articles_processing_status", "articles", ["processing_status"])

    op.create_table(
        "stories",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        _ts("first_observed_at"),
        _ts("last_observed_at"),
        _ts("created_at", nullable=False, default_now=True),
        _ts("updated_at", nullable=False, default_now=True),
    )
    op.create_index("ix_stories_last_observed_at", "stories", ["last_observed_at"])

    op.create_table(
        "story_articles",
        sa.Column("story_id", sa.BigInteger, sa.ForeignKey("stories.id"), primary_key=True),
        sa.Column("article_id", sa.BigInteger, sa.ForeignKey("articles.id"), primary_key=True),
        sa.Column("cluster_confidence", sa.Float),
        sa.Column("assignment_method", sa.String(32), nullable=False),
        _ts("assigned_at", nullable=False, default_now=True),
    )

    op.create_table(
        "claims",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("article_id", sa.BigInteger, sa.ForeignKey("articles.id"), index=True),
        sa.Column("story_id", sa.BigInteger, sa.ForeignKey("stories.id"), index=True),
        sa.Column("claim_text", sa.Text, nullable=False),
        sa.Column("claim_type", sa.String(32)),
        sa.Column("context", sa.Text),
        sa.Column("source", sa.String(32), nullable=False, server_default="user"),
        sa.Column("extraction_model", sa.String(128)),
        sa.Column("extraction_version", sa.String(64)),
        _ts("created_at", nullable=False, default_now=True),
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("claim_id", sa.BigInteger, sa.ForeignKey("claims.id"), nullable=False, index=True),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("source_title", sa.Text),
        sa.Column("source_type", sa.String(32)),
        sa.Column("relevant_passage", sa.Text),
        sa.Column("evidence_relationship", sa.String(16), nullable=False),
        _ts("published_at"),
        _ts("retrieved_at", nullable=False, default_now=True),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="unverified"),
    )

    op.create_table(
        "fact_checks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("claim_id", sa.BigInteger, sa.ForeignKey("claims.id"), nullable=False, index=True),
        sa.Column("assessment", sa.String(32), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("limitations", sa.Text),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="pending_review"),
        sa.Column("model_name", sa.String(128)),
        sa.Column("prompt_version", sa.String(64)),
        _ts("created_at", nullable=False, default_now=True),
        sa.Column("supersedes_id", sa.BigInteger, sa.ForeignKey("fact_checks.id")),
    )

    op.create_table(
        "article_analyses",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("article_id", sa.BigInteger, sa.ForeignKey("articles.id"), nullable=False, index=True),
        sa.Column("topics", JSONB),
        sa.Column("entities", JSONB),
        sa.Column("framing_summary", sa.Text),
        sa.Column("language_characteristics", JSONB),
        sa.Column("analysis_model", sa.String(128)),
        sa.Column("prompt_version", sa.String(64)),
        _ts("created_at", nullable=False, default_now=True),
    )

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("outlet_id", sa.Integer, sa.ForeignKey("outlets.id"), index=True),
        _ts("started_at", nullable=False, default_now=True),
        _ts("finished_at"),
        sa.Column("records_discovered", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("error_summary", sa.Text),
    )


def downgrade() -> None:
    for table in (
        "collection_runs",
        "article_analyses",
        "fact_checks",
        "evidence",
        "claims",
        "story_articles",
        "stories",
        "articles",
        "outlet_bias_ratings",
        "outlets",
    ):
        op.drop_table(table)
