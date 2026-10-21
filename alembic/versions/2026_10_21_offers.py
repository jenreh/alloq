"""Add offers (Angebote) table.

Revision ID: ce01a2b3c4d5
Revises: bd91ef12ac34
Create Date: 2026-10-21 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ce01a2b3c4d5"
down_revision: str | None = "bd91ef12ac34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("customer", sa.String(255), nullable=False),
        sa.Column("person_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("risk_buffer_days", sa.Numeric(8, 2), nullable=False),
        sa.Column("production_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("recommended_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("key_accounter", sa.String(255), nullable=False),
        sa.Column("ciu", sa.String(10), nullable=False),
        sa.Column("sharepoint_url", sa.String(2048), nullable=True),
        sa.Column("sent_date", sa.Date(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_offers_state", "offers", ["state"])


def downgrade() -> None:
    op.drop_index("ix_offers_state", table_name="offers")
    op.drop_table("offers")
