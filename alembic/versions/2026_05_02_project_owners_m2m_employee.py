"""project owners m2m employee

Revision ID: f8f4574e1bae
Revises: fd343f955aa8
Create Date: 2026-05-02 19:45:16.219543

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8f4574e1bae"
down_revision: str | None = "fd343f955aa8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Clear the table out first because the structures are completely incompatible and this is a local iteration anyway
    op.execute("DELETE FROM project_owners")

    with op.batch_alter_table("project_owners") as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            "fk_project_owners_employee_id_employees",
            "employees",
            ["employee_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_column("email")
        # Removing old scalar ID/timestamps since this is now an Association Table, dropping the primary constraint as well
        batch_op.drop_column("created")
        batch_op.drop_column("updated")
        batch_op.drop_column("id")

    # We must explicitly add primary key over (project_id, employee_id)
    op.create_primary_key(
        "pk_project_owners", "project_owners", ["project_id", "employee_id"]
    )


def downgrade() -> None:
    pass
