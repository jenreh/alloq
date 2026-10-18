"""Rename the project CATS number to a neutral booking number.

Revision ID: ef56ab78cd90
Revises: de45fa67bc89
Create Date: 2026-10-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "ef56ab78cd90"
down_revision: str | None = "de45fa67bc89"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("cats_number", new_column_name="booking_number")


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("booking_number", new_column_name="cats_number")
