"""Add internal_hours to employee.

Revision ID: 8a3f2c1d4e5b
Revises: 20260506_ramp
Create Date: 2026-05-06
"""

import sqlalchemy as sa

from alembic import op

revision = "8a3f2c1d4e5b"
down_revision = "20260506_ramp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("internal_hours", sa.Integer(), nullable=False, server_default="4"),
    )


def downgrade() -> None:
    op.drop_column("employees", "internal_hours")
