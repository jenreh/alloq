"""Add abbreviation to roles table.

Revision ID: 20260507_abbr
Revises: 8a3f2c1d4e5b
Create Date: 2026-05-07
"""

import sqlalchemy as sa

from alembic import op

revision = "20260507_abbr"
down_revision = "8a3f2c1d4e5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("abbreviation", sa.String(3), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("roles", "abbreviation")
