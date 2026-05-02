"""'add email to employee'

Revision ID: 32a130450068
Revises: cda123f456e7
Create Date: 2026-05-02 18:15:13.656455

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32a130450068"
down_revision: str | None = "cda123f456e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
    )


def downgrade() -> None:
    op.drop_column("employees", "email")
