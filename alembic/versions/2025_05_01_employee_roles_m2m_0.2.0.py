"""Convert employee role from FK to many-to-many

Revision ID: b4d8e9f1a2b3
Revises: a3c7d8e4f5g6
Create Date: 2025-05-01 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d8e9f1a2b3"
down_revision: str | None = "a3c7d8e4f5g6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the association table
    op.create_table(
        "employee_roles",
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Migrate existing role_id data to the new association table
    op.execute(
        "INSERT INTO employee_roles (employee_id, role_id) "
        "SELECT id, role_id FROM employees WHERE role_id IS NOT NULL"
    )

    # Drop the old role_id FK and column
    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.drop_constraint("employees_role_id_fkey", type_="foreignkey")
        batch_op.drop_column("role_id")


def downgrade() -> None:
    # Re-add role_id column
    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role_id", sa.Integer(), nullable=True))

    # Restore first role from association table
    op.execute(
        "UPDATE employees SET role_id = ("
        "  SELECT role_id FROM employee_roles "
        "  WHERE employee_roles.employee_id = employees.id "
        "  LIMIT 1"
        ")"
    )

    # Make role_id NOT NULL and add FK
    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.alter_column("role_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "employees_role_id_fkey",
            "roles",
            ["role_id"],
            ["id"],
        )

    # Drop the association table
    op.drop_table("employee_roles")
