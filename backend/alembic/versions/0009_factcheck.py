"""Fase 6: investigações, versões de checagem e busca por texto nas notícias

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

FTS = ("to_tsvector('portuguese'::regconfig, "
       "(COALESCE(headline, '') || ' ') || COALESCE(summary, ''))")


def upgrade() -> None:
    # Um pedido de checagem (texto colado ou notícia coletada); pode virar várias afirmações.
    op.create_table(
        "investigations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("input_type", sa.String(16), nullable=False),  # text | article
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("article_id", sa.BigInteger, sa.ForeignKey("articles.id"), index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text),
        sa.Column("extraction", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_investigations_created_at", "investigations", ["created_at"])

    op.add_column("claims", sa.Column("investigation_id", sa.BigInteger, sa.ForeignKey("investigations.id")))
    op.add_column("claims", sa.Column("quote", sa.Text))
    op.add_column("claims", sa.Column("parsed", JSONB))
    op.create_index("ix_claims_investigation_id", "claims", ["investigation_id"])

    # Cada versão de checagem tem as próprias evidências (com a data em que foram buscadas).
    op.add_column("evidence", sa.Column("fact_check_id", sa.BigInteger, sa.ForeignKey("fact_checks.id")))
    op.add_column("evidence", sa.Column("provider", sa.String(32)))
    op.add_column("evidence", sa.Column("data", JSONB))
    op.create_index("ix_evidence_fact_check_id", "evidence", ["fact_check_id"])

    op.add_column("fact_checks", sa.Column("method", sa.String(16)))
    op.add_column("fact_checks", sa.Column("details", JSONB))
    op.add_column("fact_checks", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("fact_checks", sa.Column("review_note", sa.Text))
    op.create_index("ix_fact_checks_supersedes_id", "fact_checks", ["supersedes_id"])

    op.execute(f"CREATE INDEX IF NOT EXISTS ix_articles_fts ON articles USING GIN ({FTS})")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_fts")
    op.drop_index("ix_fact_checks_supersedes_id", table_name="fact_checks")
    for col in ("review_note", "reviewed_at", "details", "method"):
        op.drop_column("fact_checks", col)
    op.drop_index("ix_evidence_fact_check_id", table_name="evidence")
    for col in ("data", "provider", "fact_check_id"):
        op.drop_column("evidence", col)
    op.drop_index("ix_claims_investigation_id", table_name="claims")
    for col in ("parsed", "quote", "investigation_id"):
        op.drop_column("claims", col)
    op.drop_index("ix_investigations_created_at", table_name="investigations")
    op.drop_table("investigations")
