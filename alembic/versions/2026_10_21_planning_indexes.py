"""Planning indexes: covering week index, foreign-key indexes, drop duplicates.

Adds ``ix_capacity_alloc_week_cover`` on ``capacity_allocations (week_start)``
with the grid columns as INCLUDE (PostgreSQL only; SQLite gets a plain index),
so the planning grid reads its week window from the index alone. It replaces
``ix_capacity_allocations_week_start``.

Indexes foreign keys that had none, so deletes of departments, roles and
employees do not scan the referencing tables: ``employees.department_id``,
``employees.manager_id``, ``employees.key_role_id``,
``project_owners.employee_id`` and ``employee_roles.role_id``.

Drops indexes that a primary key, a unique constraint or a longer index with
the same leading columns already covers. Every allocation upsert of the grid
updates each index, so fewer indexes make saving cheaper.

Revision ID: df12a3b4c5e6
Revises: ce01a2b3c4d5
Create Date: 2026-10-21 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "df12a3b4c5e6"
down_revision: str | None = "ce01a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COVER_INDEX = "ix_capacity_alloc_week_cover"
COVER_INCLUDE = ["employee_id", "project_id", "role_id", "person_days"]

FOREIGN_KEY_INDEXES: list[tuple[str, str, str]] = [
    ("ix_employees_department_id", "employees", "department_id"),
    ("ix_employees_manager_id", "employees", "manager_id"),
    ("ix_employees_key_role_id", "employees", "key_role_id"),
    ("ix_project_owners_employee_id", "project_owners", "employee_id"),
    ("ix_employee_roles_role_id", "employee_roles", "role_id"),
]

# name, table, columns; recreated as they were on downgrade.
REDUNDANT_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_capacity_allocations_week_start", "capacity_allocations", ["week_start"]),
    ("ix_capacity_allocations_project_id", "capacity_allocations", ["project_id"]),
    ("ix_capacity_allocations_employee_id", "capacity_allocations", ["employee_id"]),
    ("ix_capacities_project_id", "capacities", ["project_id"]),
    ("ix_capacities_project_employee", "capacities", ["project_id", "employee_id"]),
    ("ix_project_owners_project_id", "project_owners", ["project_id"]),
    ("ix_projects_code", "projects", ["code"]),
]


def upgrade() -> None:
    op.create_index(
        COVER_INDEX,
        "capacity_allocations",
        ["week_start"],
        unique=False,
        if_not_exists=True,
        postgresql_include=COVER_INCLUDE,
    )
    for name, table, column in FOREIGN_KEY_INDEXES:
        op.create_index(name, table, [column], unique=False, if_not_exists=True)
    for name, table, _ in REDUNDANT_INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)


def downgrade() -> None:
    for name, table, columns in REDUNDANT_INDEXES:
        op.create_index(name, table, columns, unique=False, if_not_exists=True)
    for name, table, _ in FOREIGN_KEY_INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)
    op.drop_index(COVER_INDEX, table_name="capacity_allocations", if_exists=True)
