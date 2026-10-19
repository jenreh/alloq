"""Add department highlighting for team views.

Revision ID: bd91ef12ac34
Revises: bc90de12fa34
Create Date: 2026-10-19 17:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "bd91ef12ac34"
down_revision: str | None = "bc90de12fa34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("departments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "highlighted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("departments") as batch_op:
        batch_op.drop_column("highlighted")
