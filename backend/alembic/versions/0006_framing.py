"""Fase 5: análises de enquadramento e avaliações atribuídas de veículos

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cada análise é uma linha nova (nunca sobrescreve): tipo + versão do prompt/modelo.
    op.add_column("article_analyses", sa.Column("analysis_type", sa.String(16), nullable=False,
                                                server_default="observable"))
    op.add_column("article_analyses", sa.Column("result", JSONB))
    op.add_column("article_analyses", sa.Column("validation", JSONB))
    op.create_index("ix_article_analyses_lookup", "article_analyses",
                    ["article_id", "analysis_type", "prompt_version"])

    # Avaliações de orientação: histórico preservado; a mesma avaliação não entra duas vezes.
    op.create_unique_constraint("uq_outlet_rating", "outlet_bias_ratings",
                                ["outlet_id", "provider", "assessed_at"])


def downgrade() -> None:
    op.drop_constraint("uq_outlet_rating", "outlet_bias_ratings", type_="unique")
    op.drop_index("ix_article_analyses_lookup", table_name="article_analyses")
    op.drop_column("article_analyses", "validation")
    op.drop_column("article_analyses", "result")
    op.drop_column("article_analyses", "analysis_type")
