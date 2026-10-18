"""Key role for employees; the other assigned roles are additional roles.

Revision ID: ab12cd34ef56
Revises: ff77aa88bb99
Create Date: 2026-10-17 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ab12cd34ef56"
down_revision: str | None = "ff77aa88bb99"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("key_role_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_employees_key_role_id_roles",
            "roles",
            ["key_role_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        "UPDATE employees SET key_role_id = ("
        "SELECT MIN(role_id) FROM employee_roles "
        "WHERE employee_roles.employee_id = employees.id)"
    )


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_constraint("fk_employees_key_role_id_roles", type_="foreignkey")
        batch_op.drop_column("key_role_id")
