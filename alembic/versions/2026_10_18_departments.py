"""Departments table; employees reference a department instead of free text.

Revision ID: de45fa67bc89
Revises: cd34ef56ab78
Create Date: 2026-10-18 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "de45fa67bc89"
down_revision: str | None = "cd34ef56ab78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("abbreviation", sa.String(length=10), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("abbreviation", name="uq_departments_abbreviation"),
    )
    op.create_index("ix_departments_name", "departments", ["name"], unique=True)

    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_employees_department_id_departments",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Free-text abbreviations entered so far become departments.
    op.execute(
        "INSERT INTO departments (name, abbreviation) "
        "SELECT MIN(TRIM(department)), SUBSTR(TRIM(department), 1, 10) "
        "FROM employees WHERE TRIM(COALESCE(department, '')) <> '' "
        "GROUP BY SUBSTR(TRIM(department), 1, 10)"
    )
    op.execute(
        "UPDATE employees SET department_id = ("
        "SELECT d.id FROM departments d "
        "WHERE d.abbreviation = SUBSTR(TRIM(employees.department), 1, 10))"
    )

    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_column("department")


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.add_column(sa.Column("department", sa.String(50), nullable=True))
    op.execute(
        "UPDATE employees SET department = ("
        "SELECT d.abbreviation FROM departments d "
        "WHERE d.id = employees.department_id)"
    )
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_constraint(
            "fk_employees_department_id_departments", type_="foreignkey"
        )
        batch_op.drop_column("department_id")

    op.drop_index("ix_departments_name", table_name="departments")
    op.drop_table("departments")
