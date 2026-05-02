"""add project management entities

Revision ID: 5d3c1a7b9e02
Revises: 7f76f34e3f66
Create Date: 2026-05-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d3c1a7b9e02"
down_revision: str | None = "7f76f34e3f66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name_de", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("end_date >= start_date", name="ck_projects_date_range"),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["employees.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_projects_code"), "projects", ["code"], unique=False)
    op.create_index(
        op.f("ix_projects_created_by_id"),
        "projects",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)

    op.create_table(
        "project_statuses",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status_date", sa.Date(), nullable=False),
        sa.Column("fortschritt", sa.Integer(), nullable=False),
        sa.Column("budget_verbrauch", sa.Integer(), nullable=False),
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
            "fortschritt >= 0 AND fortschritt <= 100",
            name="ck_project_statuses_fortschritt_range",
        ),
        sa.CheckConstraint(
            "budget_verbrauch >= 0 AND budget_verbrauch <= 100",
            name="ck_project_statuses_budget_verbrauch_range",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_statuses_project_id"),
        "project_statuses",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_statuses_status_date"),
        "project_statuses",
        ["status_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_statuses_id"),
        "project_statuses",
        ["id"],
        unique=False,
    )

    op.create_table(
        "risks",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("probability", sa.String(length=20), nullable=False),
        sa.Column("impact", sa.String(length=20), nullable=False),
        sa.Column("mitigation_status", sa.String(length=20), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risks_project_id"), "risks", ["project_id"], unique=False)
    op.create_index(op.f("ix_risks_id"), "risks", ["id"], unique=False)

    op.create_table(
        "capacities",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("hours_per_week", sa.Float(), nullable=False),
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
        sa.CheckConstraint("end_date >= start_date", name="ck_capacities_date_range"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_capacities_employee_id"),
        "capacities",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_capacities_project_id"),
        "capacities",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_capacities_project_employee",
        "capacities",
        ["project_id", "employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_capacities_role_id"),
        "capacities",
        ["role_id"],
        unique=False,
    )
    op.create_index(op.f("ix_capacities_id"), "capacities", ["id"], unique=False)

    op.create_table(
        "required_capacities",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("person_days", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("person_days >= 0", name="ck_required_capacities_pd"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_required_capacities_project_id"),
        "required_capacities",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_required_capacities_role_id"),
        "required_capacities",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_required_capacities_id"),
        "required_capacities",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_required_capacities_id")
    op.drop_index(
        op.f("ix_required_capacities_role_id"), table_name="required_capacities"
    )
    op.drop_index(
        op.f("ix_required_capacities_project_id"),
        table_name="required_capacities",
    )
    op.drop_table("required_capacities")
    op.execute("DROP INDEX IF EXISTS ix_capacities_id")
    op.drop_index(op.f("ix_capacities_role_id"), table_name="capacities")
    op.drop_index("ix_capacities_project_employee", table_name="capacities")
    op.drop_index(op.f("ix_capacities_project_id"), table_name="capacities")
    op.drop_index(op.f("ix_capacities_employee_id"), table_name="capacities")
    op.drop_table("capacities")
    op.execute("DROP INDEX IF EXISTS ix_risks_id")
    op.drop_index(op.f("ix_risks_project_id"), table_name="risks")
    op.drop_table("risks")
    op.execute("DROP INDEX IF EXISTS ix_project_statuses_id")
    op.drop_index(
        op.f("ix_project_statuses_status_date"),
        table_name="project_statuses",
    )
    op.drop_index(
        op.f("ix_project_statuses_project_id"),
        table_name="project_statuses",
    )
    op.drop_table("project_statuses")
    op.execute("DROP INDEX IF EXISTS ix_projects_id")
    op.drop_index(op.f("ix_projects_created_by_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_code"), table_name="projects")
    op.drop_table("projects")
