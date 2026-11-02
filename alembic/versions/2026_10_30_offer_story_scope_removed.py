"""Offer stories lose their scope; every live story belongs to the offer.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-10-30 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: str | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("offer_stories", schema=None) as batch_op:
        batch_op.drop_column("scope")


def downgrade() -> None:
    # The scope is lost; restored stories count as offered.
    with op.batch_alter_table("offer_stories", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scope",
                sa.String(length=20),
                nullable=False,
                server_default="angeboten",
            )
        )
