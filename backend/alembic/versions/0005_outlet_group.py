"""Grupo do veículo (nacional / internacional)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outlets",
        sa.Column("outlet_group", sa.String(16), nullable=False, server_default="nacional"),
    )
    op.create_index("ix_outlets_outlet_group", "outlets", ["outlet_group"])


def downgrade() -> None:
    op.drop_index("ix_outlets_outlet_group", table_name="outlets")
    op.drop_column("outlets", "outlet_group")
