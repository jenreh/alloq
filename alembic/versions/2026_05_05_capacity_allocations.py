"""add capacity_allocations table for weekly per-employee allocations

Revision ID: 8a6c1e2b9f04
Revises: 4d1cf6f5d6a1
Create Date: 2026-05-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a6c1e2b9f04"
down_revision: str | None = "4d1cf6f5d6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capacity_allocations",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("person_days", sa.Float(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.CheckConstraint(
            "person_days >= 0", name="ck_capacity_allocations_person_days"
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "employee_id",
            "role_id",
            "week_start",
            name="uq_capacity_alloc_proj_emp_role_week",
        ),
    )
    op.create_index(
        op.f("ix_capacity_allocations_project_id"),
        "capacity_allocations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_capacity_allocations_employee_id"),
        "capacity_allocations",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_capacity_allocations_role_id"),
        "capacity_allocations",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_capacity_allocations_week_start"),
        "capacity_allocations",
        ["week_start"],
        unique=False,
    )
    op.create_index(
        "ix_capacity_alloc_project_week",
        "capacity_allocations",
        ["project_id", "week_start"],
        unique=False,
    )
    op.create_index(
        "ix_capacity_alloc_employee_week",
        "capacity_allocations",
        ["employee_id", "week_start"],
        unique=False,
    )
    op.create_index(
        op.f("ix_capacity_allocations_id"),
        "capacity_allocations",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_capacity_allocations_id"), table_name="capacity_allocations")
    op.drop_index("ix_capacity_alloc_employee_week", table_name="capacity_allocations")
    op.drop_index("ix_capacity_alloc_project_week", table_name="capacity_allocations")
    op.drop_index(
        op.f("ix_capacity_allocations_week_start"),
        table_name="capacity_allocations",
    )
    op.drop_index(
        op.f("ix_capacity_allocations_role_id"),
        table_name="capacity_allocations",
    )
    op.drop_index(
        op.f("ix_capacity_allocations_employee_id"),
        table_name="capacity_allocations",
    )
    op.drop_index(
        op.f("ix_capacity_allocations_project_id"),
        table_name="capacity_allocations",
    )
    op.drop_table("capacity_allocations")
