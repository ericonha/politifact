"""Veículos favoritos

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outlets", sa.Column("favorite", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("outlets", "favorite")
