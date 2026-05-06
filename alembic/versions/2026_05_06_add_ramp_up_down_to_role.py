"""Add ramp_up and ramp_down to roles table.

Revision ID: 20260506_ramp
Revises: 2026_05_05_capacity_allocations
Create Date: 2026-05-06
"""

import sqlalchemy as sa

from alembic import op

revision = "20260506_ramp"
down_revision = "8a6c1e2b9f04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("ramp_up", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "roles",
        sa.Column("ramp_down", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("roles", "ramp_down")
    op.drop_column("roles", "ramp_up")
