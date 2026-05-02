"""add_manager_id_to_employee

Revision ID: 2759d8f91359
Revises: f8f4574e1bae
Create Date: 2026-05-02 20:47:05.529618

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2759d8f91359"
down_revision: str | None = "f8f4574e1bae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("employees", "manager_id")
