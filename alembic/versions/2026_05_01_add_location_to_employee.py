"""add location to employee

Revision ID: 2226883368c9
Revises: b4d8e9f1a2b3
Create Date: 2026-05-01 17:24:12.516060

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2226883368c9"
down_revision: str | None = "b4d8e9f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees", sa.Column("location", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("employees", "location")
