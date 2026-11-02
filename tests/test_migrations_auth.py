"""Tests for the migrations of the appkit-user password and throttle tables."""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, Final
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from appkit_commons.database.entities import Base
from appkit_user.authentication.backend.database import entities  # noqa: F401

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS: Final = Path(__file__).resolve().parents[1] / "alembic" / "versions"
THROTTLE_REVISION: Final = "d9c4081a9088"  # pragma: allowlist secret
PASSWORD_TABLES: Final = {
    "auth_password_reset_tokens",
    "auth_password_history",
    "auth_password_reset_requests",
}
# In appkit's migration but not on its entity.
REQUEST_INDEXES: Final = {
    "idx_password_reset_requests_email_created",
    "idx_password_reset_requests_created",
}


def _load(filename: str) -> ModuleType:
    path = VERSIONS / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(module: ModuleType, step: str, conn: Connection) -> None:
    operations = Operations(MigrationContext.configure(conn))
    with patch.object(module, "op", operations):
        getattr(module, step)()


def _schema_differences(conn: Connection, tables: set[str]) -> list[Any]:
    """What Alembic would change so that ``tables`` match the appkit-user entities."""

    def include_object(
        obj: Any, name: str | None, kind: str, _reflected: bool, _other: Any
    ) -> bool:
        if kind == "index" and name in REQUEST_INDEXES:
            return False
        table = name if kind == "table" else obj.table.name
        return table in tables

    context = MigrationContext.configure(
        conn, opts={"include_object": include_object, "compare_type": True}
    )
    return compare_metadata(context, Base.metadata)


@pytest.fixture
def migration() -> ModuleType:
    return _load("2026_11_02_add_password_reset_tables.py")


@pytest.fixture
def conn() -> Iterator[Connection]:
    """A database with the one table the password tables point at."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql("CREATE TABLE auth_users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO auth_users (id) VALUES (1)")
        yield connection


def _insert_token(conn: Connection, token: str) -> None:
    conn.exec_driver_sql(
        "INSERT INTO auth_password_reset_tokens"
        " (user_id, token, reset_type, expires_at)"
        " VALUES (1, ?, 'admin_forced', '2026-11-02 12:00:00')",
        (token,),
    )


def test_follows_the_login_throttle(migration: ModuleType) -> None:
    assert migration.down_revision == THROTTLE_REVISION


def test_password_tables_match_the_entities(
    migration: ModuleType, conn: Connection
) -> None:
    _run(migration, "upgrade", conn)

    assert _schema_differences(conn, PASSWORD_TABLES) == []


def test_reset_requests_keep_the_indexes_of_appkit(
    migration: ModuleType, conn: Connection
) -> None:
    _run(migration, "upgrade", conn)

    indexes = sa.inspect(conn).get_indexes("auth_password_reset_requests")

    assert {index["name"] for index in indexes} == REQUEST_INDEXES


def test_login_throttle_table_matches_the_entity(conn: Connection) -> None:
    _run(_load("2026_11_02_add_login_throttle.py"), "upgrade", conn)

    assert _schema_differences(conn, {"auth_login_throttle"}) == []


def test_token_defaults_to_unused(migration: ModuleType, conn: Connection) -> None:
    _run(migration, "upgrade", conn)

    _insert_token(conn, "first")

    row = conn.exec_driver_sql(
        "SELECT is_used, created, updated FROM auth_password_reset_tokens"
    ).one()
    assert not row.is_used
    assert row.created is not None
    assert row.updated is not None


def test_token_is_unique(migration: ModuleType, conn: Connection) -> None:
    _run(migration, "upgrade", conn)
    _insert_token(conn, "same")

    with pytest.raises(IntegrityError):
        _insert_token(conn, "same")


def test_deleting_a_user_removes_tokens_and_history(
    migration: ModuleType, conn: Connection
) -> None:
    _run(migration, "upgrade", conn)
    _insert_token(conn, "first")
    conn.exec_driver_sql(
        "INSERT INTO auth_password_history (user_id, password_hash) VALUES (1, 'hash')"
    )

    conn.exec_driver_sql("DELETE FROM auth_users WHERE id = 1")

    for count in (
        "SELECT COUNT(*) FROM auth_password_reset_tokens",
        "SELECT COUNT(*) FROM auth_password_history",
    ):
        assert conn.exec_driver_sql(count).scalar() == 0


def test_keeps_a_table_that_already_exists(
    migration: ModuleType, conn: Connection
) -> None:
    conn.exec_driver_sql(
        "CREATE TABLE auth_password_history (id INTEGER PRIMARY KEY, kept TEXT)"
    )
    conn.exec_driver_sql("INSERT INTO auth_password_history (kept) VALUES ('old')")

    _run(migration, "upgrade", conn)

    assert PASSWORD_TABLES <= set(sa.inspect(conn).get_table_names())
    assert (
        conn.exec_driver_sql("SELECT kept FROM auth_password_history").scalar() == "old"
    )


def test_downgrade_drops_the_tables(migration: ModuleType, conn: Connection) -> None:
    _run(migration, "upgrade", conn)

    _run(migration, "downgrade", conn)

    assert not PASSWORD_TABLES & set(sa.inspect(conn).get_table_names())
