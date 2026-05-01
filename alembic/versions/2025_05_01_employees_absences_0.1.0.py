"""Create employees and absences tables

Revision ID: a3c7d8e4f5g6
Revises: d2a9b9f2d1e2
Create Date: 2025-05-01 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c7d8e4f5g6"
down_revision: str | None = "d2a9b9f2d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("seniority", sa.String(length=50), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("hours_per_week", sa.Float(), nullable=False, server_default="40.0"),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
    )
    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employees_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_employees_first_name"), ["first_name"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_employees_last_name"), ["last_name"], unique=False
        )

    op.create_table(
        "absences",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
    )
    with op.batch_alter_table("absences", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_absences_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_absences_employee_id"), ["employee_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("absences", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_absences_employee_id"))
        batch_op.drop_index(batch_op.f("ix_absences_id"))
    op.drop_table("absences")

    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_employees_last_name"))
        batch_op.drop_index(batch_op.f("ix_employees_first_name"))
        batch_op.drop_index(batch_op.f("ix_employees_id"))
    op.drop_table("employees")
