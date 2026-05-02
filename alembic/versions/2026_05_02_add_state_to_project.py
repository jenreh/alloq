"""add state to project

Revision ID: 6e4a2b8c9d03
Revises: 5d3c1a7b9e02
Create Date: 2026-05-02 18:05:21.205868

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e4a2b8c9d03"
down_revision: str | None = "5d3c1a7b9e02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "state", sa.String(length=20), nullable=False, server_default="Geplant"
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "state")
