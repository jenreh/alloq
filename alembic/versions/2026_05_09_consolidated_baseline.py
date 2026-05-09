"""Consolidated baseline — single migration reflecting current entity schema.

Replaces all prior incremental migrations. Represents the DB state after
applying the full migration history up to 2026-05-09.

Revision ID: aa11bb22cc33
Revises:
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy_utils import StringEncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import FernetEngine

from alembic import op
from app import configuration

# revision identifiers, used by Alembic.
revision: str = "aa11bb22cc33"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def get_encryption_key() -> str:
    config = configuration.app.database
    return str(config.encryption_key.get_secret_value())


def upgrade() -> None:  # noqa: PLR0915
    encryption_key = get_encryption_key()

    # ── auth_users ──────────────────────────────────────────────────────────
    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("_password", sa.String(length=200), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("needs_password_reset", sa.Boolean(), nullable=False),
        sa.Column(
            "roles",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "last_login",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
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
        sa.UniqueConstraint("email"),
    )
    with op.batch_alter_table("auth_users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_auth_users_id"), ["id"], unique=False)

    # ── auth_oauth_accounts ──────────────────────────────────────────────────
    op.create_table(
        "auth_oauth_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("account_id", sa.String(length=100), nullable=False),
        sa.Column("account_email", sa.String(length=200), nullable=False),
        sa.Column(
            "access_token",
            StringEncryptedType(sa.Unicode(), encryption_key, FernetEngine),
            nullable=False,
        ),
        sa.Column(
            "refresh_token",
            StringEncryptedType(sa.Unicode(), encryption_key, FernetEngine),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.String(length=500), nullable=True),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "account_id", name="uq_oauth_provider_account"),
    )
    with op.batch_alter_table("auth_oauth_accounts", schema=None) as batch_op:
        batch_op.create_index("ix_oauth_accounts_user_id", ["user_id"], unique=False)

    # ── auth_oauth_states ────────────────────────────────────────────────────
    op.create_table(
        "auth_oauth_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("code_verifier", sa.String(length=200), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("auth_oauth_states", schema=None) as batch_op:
        batch_op.create_index(
            "ix_oauth_states_expires_at", ["expires_at"], unique=False
        )

    # ── auth_sessions ────────────────────────────────────────────────────────
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )

    # Seed default admin user
    op.execute(
        """
        INSERT INTO auth_users
        (email, name, avatar_url, is_active, is_admin, is_verified, _password,
         created, updated, last_login, needs_password_reset, roles)
        VALUES(
            'admin',
            'Default Admin (please change)',
            '',
            true,
            true,
            true,
            'scrypt:32768:8:1$bIA8HVQhPyudwZyV$76d044d2322d395a3a9c95b29337c0c4d24e2426d86d246cc72095fe2455be0540590ecea3c4d433262ea9d9aaa44eaa285363eed568451895ef25652911a2dc',
            '2025-02-03 10:18:40.258',
            '2025-02-03 10:19:14.354',
            '2025-02-03 10:19:14.354',
            false,
            '{"user"}'
        );
        """
    )

    # ── roles ────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "abbreviation", sa.String(length=3), nullable=False, server_default=""
        ),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("ramp_up", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ramp_down", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.UniqueConstraint("name"),
    )
    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_roles_id"), ["id"], unique=False)
        batch_op.create_index(batch_op.f("ix_roles_name"), ["name"], unique=True)

    # ── employees ────────────────────────────────────────────────────────────
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("seniority", sa.String(length=50), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("hours_per_week", sa.Float(), nullable=False, server_default="40.0"),
        sa.Column("internal_hours", sa.Integer(), nullable=False, server_default="4"),
        sa.Column(
            "manager_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.UniqueConstraint("email"),
    )
    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_employees_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_employees_first_name"), ["first_name"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_employees_last_name"), ["last_name"], unique=False
        )

    # ── employee_roles (M2M) ─────────────────────────────────────────────────
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

    # ── absences ─────────────────────────────────────────────────────────────
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

    # ── projects ─────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("customer", sa.String(length=255), nullable=True, server_default=""),
        sa.Column("name_de", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "state", sa.String(length=20), nullable=False, server_default="Geplant"
        ),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column(
            "color", sa.String(length=7), nullable=False, server_default="#FFD43B"
        ),
        sa.Column("ev_earned_value", sa.Float(), nullable=True),
        sa.Column("ev_actual_cost", sa.Float(), nullable=True),
        sa.Column("ev_eac_linear", sa.Float(), nullable=True),
        sa.Column("ev_eac_additive", sa.Float(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)
    op.create_index(op.f("ix_projects_code"), "projects", ["code"], unique=False)

    # ── project_owners (M2M) ──────────────────────────────────────────────────
    op.create_table(
        "project_owners",
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        op.f("ix_project_owners_project_id"),
        "project_owners",
        ["project_id"],
        unique=False,
    )

    # ── project_statuses ─────────────────────────────────────────────────────
    op.create_table(
        "project_statuses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("status_date", sa.Date(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("budget_spent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("earned_value", sa.Float(), nullable=True),
        sa.Column("actual_cost", sa.Float(), nullable=True),
        sa.Column("eac_linear", sa.Float(), nullable=True),
        sa.Column("eac_additive", sa.Float(), nullable=True),
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
            "progress >= 0 AND progress <= 100",
            name="ck_project_statuses_progress_range",
        ),
        sa.CheckConstraint(
            "budget_spent >= 0 AND budget_spent <= 100",
            name="ck_project_statuses_budget_spent_range",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("project_statuses", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_project_statuses_id"), ["id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_project_statuses_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_project_statuses_status_date"),
            ["status_date"],
            unique=False,
        )

    # ── risks ─────────────────────────────────────────────────────────────────
    op.create_table(
        "risks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("impact", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "mitigation_status",
            sa.String(length=30),
            nullable=False,
            server_default="open",
        ),
        sa.Column("measures", sa.String(length=2000), nullable=True),
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
    with op.batch_alter_table("risks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_risks_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_risks_project_id"), ["project_id"], unique=False
        )

    # ── capacities ────────────────────────────────────────────────────────────
    op.create_table(
        "capacities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
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
        sa.CheckConstraint("end_date >= start_date", name="ck_capacities_date_range"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("capacities", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_capacities_id"), ["id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_capacities_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_capacities_employee_id"), ["employee_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_capacities_role_id"), ["role_id"], unique=False
        )
        batch_op.create_index(
            "ix_capacities_project_employee",
            ["project_id", "employee_id"],
            unique=False,
        )

    # ── capacity_allocations ──────────────────────────────────────────────────
    op.create_table(
        "capacity_allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("person_days", sa.Float(), nullable=False, server_default="0.0"),
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
    with op.batch_alter_table("capacity_allocations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_capacity_allocations_id"), ["id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_capacity_allocations_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_capacity_allocations_employee_id"),
            ["employee_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_capacity_allocations_role_id"),
            ["role_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_capacity_allocations_week_start"),
            ["week_start"],
            unique=False,
        )
        batch_op.create_index(
            "ix_capacity_alloc_project_week",
            ["project_id", "week_start"],
            unique=False,
        )
        batch_op.create_index(
            "ix_capacity_alloc_employee_week",
            ["employee_id", "week_start"],
            unique=False,
        )

    # ── required_capacities ───────────────────────────────────────────────────
    op.create_table(
        "required_capacities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("person_days", sa.Integer(), nullable=False),
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
    with op.batch_alter_table("required_capacities", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_required_capacities_id"), ["id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_required_capacities_project_id"),
            ["project_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_required_capacities_role_id"),
            ["role_id"],
            unique=False,
        )


def downgrade() -> None:  # noqa: PLR0915
    with op.batch_alter_table("required_capacities", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_required_capacities_role_id"))
        batch_op.drop_index(batch_op.f("ix_required_capacities_project_id"))
        batch_op.drop_index(batch_op.f("ix_required_capacities_id"))
    op.drop_table("required_capacities")

    with op.batch_alter_table("capacity_allocations", schema=None) as batch_op:
        batch_op.drop_index("ix_capacity_alloc_employee_week")
        batch_op.drop_index("ix_capacity_alloc_project_week")
        batch_op.drop_index(batch_op.f("ix_capacity_allocations_week_start"))
        batch_op.drop_index(batch_op.f("ix_capacity_allocations_role_id"))
        batch_op.drop_index(batch_op.f("ix_capacity_allocations_employee_id"))
        batch_op.drop_index(batch_op.f("ix_capacity_allocations_project_id"))
        batch_op.drop_index(batch_op.f("ix_capacity_allocations_id"))
    op.drop_table("capacity_allocations")

    with op.batch_alter_table("capacities", schema=None) as batch_op:
        batch_op.drop_index("ix_capacities_project_employee")
        batch_op.drop_index(batch_op.f("ix_capacities_role_id"))
        batch_op.drop_index(batch_op.f("ix_capacities_employee_id"))
        batch_op.drop_index(batch_op.f("ix_capacities_project_id"))
        batch_op.drop_index(batch_op.f("ix_capacities_id"))
    op.drop_table("capacities")

    with op.batch_alter_table("risks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_risks_project_id"))
        batch_op.drop_index(batch_op.f("ix_risks_id"))
    op.drop_table("risks")

    with op.batch_alter_table("project_statuses", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_project_statuses_status_date"))
        batch_op.drop_index(batch_op.f("ix_project_statuses_project_id"))
        batch_op.drop_index(batch_op.f("ix_project_statuses_id"))
    op.drop_table("project_statuses")

    op.drop_index(op.f("ix_project_owners_project_id"), table_name="project_owners")
    op.drop_table("project_owners")

    op.drop_index(op.f("ix_projects_code"), table_name="projects")
    op.drop_index(op.f("ix_projects_id"), table_name="projects")
    op.drop_table("projects")

    with op.batch_alter_table("absences", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_absences_employee_id"))
        batch_op.drop_index(batch_op.f("ix_absences_id"))
    op.drop_table("absences")

    op.drop_table("employee_roles")

    with op.batch_alter_table("employees", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_employees_last_name"))
        batch_op.drop_index(batch_op.f("ix_employees_first_name"))
        batch_op.drop_index(batch_op.f("ix_employees_id"))
    op.drop_table("employees")

    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_roles_name"))
        batch_op.drop_index(batch_op.f("ix_roles_id"))
    op.drop_table("roles")

    op.drop_table("auth_sessions")

    with op.batch_alter_table("auth_oauth_states", schema=None) as batch_op:
        batch_op.drop_index("ix_oauth_states_expires_at")
    op.drop_table("auth_oauth_states")

    with op.batch_alter_table("auth_oauth_accounts", schema=None) as batch_op:
        batch_op.drop_index("ix_oauth_accounts_user_id")
    op.drop_table("auth_oauth_accounts")

    with op.batch_alter_table("auth_users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auth_users_id"))
    op.drop_table("auth_users")
