"""Planning index migration: runs offline on SQLite and matches the entities."""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import alloq_commons.entities  # noqa: F401 - registers every table on Base
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from appkit_commons.database.entities import Base

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.desktop import schema

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "2026_10_21_planning_indexes.py"
)

_COLUMNS = {
    "projects": "id INTEGER PRIMARY KEY, code TEXT UNIQUE",
    "roles": "id INTEGER PRIMARY KEY",
    "departments": "id INTEGER PRIMARY KEY",
    "employees": (
        "id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT UNIQUE,"
        " department_id INTEGER, manager_id INTEGER, key_role_id INTEGER"
    ),
    "employee_roles": "employee_id INTEGER, role_id INTEGER,"
    " PRIMARY KEY (employee_id, role_id)",
    "project_owners": "project_id INTEGER, employee_id INTEGER,"
    " PRIMARY KEY (project_id, employee_id)",
    "capacities": "id INTEGER PRIMARY KEY, project_id INTEGER, employee_id INTEGER,"
    " role_id INTEGER, UNIQUE (project_id, employee_id, role_id)",
    "capacity_allocations": (
        "id INTEGER PRIMARY KEY, project_id INTEGER, employee_id INTEGER,"
        " role_id INTEGER, week_start DATE, person_days REAL,"
        " UNIQUE (project_id, employee_id, role_id, week_start)"
    ),
}

# Non-unique indexes of the touched tables at the previous revision.
BEFORE: dict[str, dict[str, list[str]]] = {
    "projects": {"ix_projects_id": ["id"], "ix_projects_code": ["code"]},
    "employees": {
        "ix_employees_id": ["id"],
        "ix_employees_first_name": ["first_name"],
        "ix_employees_last_name": ["last_name"],
    },
    "employee_roles": {},
    "project_owners": {"ix_project_owners_project_id": ["project_id"]},
    "capacities": {
        "ix_capacities_id": ["id"],
        "ix_capacities_project_id": ["project_id"],
        "ix_capacities_employee_id": ["employee_id"],
        "ix_capacities_role_id": ["role_id"],
        "ix_capacities_project_employee": ["project_id", "employee_id"],
    },
    "capacity_allocations": {
        "ix_capacity_allocations_id": ["id"],
        "ix_capacity_allocations_project_id": ["project_id"],
        "ix_capacity_allocations_employee_id": ["employee_id"],
        "ix_capacity_allocations_role_id": ["role_id"],
        "ix_capacity_allocations_week_start": ["week_start"],
        "ix_capacity_alloc_project_week": ["project_id", "week_start"],
        "ix_capacity_alloc_employee_week": ["employee_id", "week_start"],
    },
}

AFTER: dict[str, set[str]] = {
    "projects": {"ix_projects_id"},
    "employees": {
        "ix_employees_id",
        "ix_employees_first_name",
        "ix_employees_last_name",
        "ix_employees_department_id",
        "ix_employees_manager_id",
        "ix_employees_key_role_id",
    },
    "employee_roles": {"ix_employee_roles_role_id"},
    "project_owners": {"ix_project_owners_employee_id"},
    "capacities": {
        "ix_capacities_id",
        "ix_capacities_employee_id",
        "ix_capacities_role_id",
    },
    "capacity_allocations": {
        "ix_capacity_allocations_id",
        "ix_capacity_allocations_role_id",
        "ix_capacity_alloc_project_week",
        "ix_capacity_alloc_employee_week",
        "ix_capacity_alloc_week_cover",
    },
}


@pytest.fixture(scope="module")
def migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def connection() -> Iterator[Connection]:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        for table, columns in _COLUMNS.items():
            conn.execute(sa.text(f"CREATE TABLE {table} ({columns})"))
        for table, indexes in BEFORE.items():
            for name, columns in indexes.items():
                conn.execute(
                    sa.text(f"CREATE INDEX {name} ON {table} ({', '.join(columns)})")
                )
        yield conn


def _run(module: ModuleType, step: str, conn: Connection) -> None:
    operations = Operations(MigrationContext.configure(conn))
    with patch.object(module, "op", operations):
        getattr(module, step)()


def _indexes(conn: Connection) -> dict[str, set[str]]:
    inspector = sa.inspect(conn)
    return {
        table: {str(i["name"]) for i in inspector.get_indexes(table)} for table in AFTER
    }


def test_follows_offers_and_is_known(migration: ModuleType) -> None:
    assert migration.down_revision == "ce01a2b3c4d5"
    assert migration.revision in schema.KNOWN_REVISIONS


def test_upgrade_leaves_planned_indexes(
    migration: ModuleType, connection: Connection
) -> None:
    _run(migration, "upgrade", connection)

    assert _indexes(connection) == AFTER


def test_cover_index_leads_with_week_start(
    migration: ModuleType, connection: Connection
) -> None:
    _run(migration, "upgrade", connection)

    cover = next(
        i
        for i in sa.inspect(connection).get_indexes("capacity_allocations")
        if i["name"] == "ix_capacity_alloc_week_cover"
    )
    assert cover["column_names"] == ["week_start"]


def test_downgrade_restores_previous_indexes(
    migration: ModuleType, connection: Connection
) -> None:
    _run(migration, "upgrade", connection)
    _run(migration, "downgrade", connection)

    assert _indexes(connection) == {t: set(i) for t, i in BEFORE.items()}


def test_entities_declare_the_migrated_indexes() -> None:
    declared = {
        table: {i.name for i in Base.metadata.tables[table].indexes} for table in AFTER
    }

    assert declared == AFTER


def test_cover_index_includes_grid_columns() -> None:
    cover = next(
        i
        for i in Base.metadata.tables["capacity_allocations"].indexes
        if i.name == "ix_capacity_alloc_week_cover"
    )

    assert cover.dialect_options["postgresql"]["include"] == [
        "employee_id",
        "project_id",
        "role_id",
        "person_days",
    ]
