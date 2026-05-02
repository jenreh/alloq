"""remove name_en from project

Revision ID: cda123f456e7
Revises: 6e4a2b8c9d03
Create Date: 2026-05-02 18:25:21.205868

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cda123f456e7"
down_revision: str | None = "6e4a2b8c9d03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("projects", "name_en")


def downgrade() -> None:
    op.add_column(
        "projects", sa.Column("name_en", sa.String(length=255), nullable=True)
    )
