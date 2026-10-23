"""Link an accepted offer to the project created from it.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-10-22 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = "fk_offers_project_id_projects"
INDEX_NAME = "ix_offers_project_id"


def upgrade() -> None:
    with op.batch_alter_table("offers") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            FK_NAME, "projects", ["project_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index(INDEX_NAME, ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("offers") as batch:
        batch.drop_index(INDEX_NAME)
        batch.drop_constraint(FK_NAME, type_="foreignkey")
        batch.drop_column("project_id")
