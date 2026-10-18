"""Daily rates get a manual list price and a minimal margin.

Revision ID: ab89cd01ef23
Revises: fa67bc89de01
Create Date: 2026-10-18 05:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ab89cd01ef23"
down_revision: str | None = "fa67bc89de01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("daily_rates") as batch_op:
        batch_op.alter_column(
            "production_cost", existing_type=sa.Integer(), nullable=True
        )
        batch_op.add_column(sa.Column("list_price", sa.Integer(), nullable=True))

    with op.batch_alter_table("daily_rate_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "min_contribution_margin_percent",
                sa.Integer(),
                server_default="30",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("daily_rate_settings") as batch_op:
        batch_op.drop_column("min_contribution_margin_percent")

    op.execute("DELETE FROM daily_rates WHERE production_cost IS NULL")
    with op.batch_alter_table("daily_rates") as batch_op:
        batch_op.drop_column("list_price")
        batch_op.alter_column(
            "production_cost", existing_type=sa.Integer(), nullable=False
        )
