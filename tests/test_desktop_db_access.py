"""Granting database access from the users page of the desktop app."""

import importlib.util
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.elements import TextClause

from app.desktop import db_access, db_access_state
from app.desktop.db_access import (
    NO_PRINCIPAL,
    NOT_ADMIN,
    AccessOverview,
    DatabaseAccess,
    DatabaseAccessError,
    maintenance_connection,
    quote_identifier,
)
from app.desktop.db_access_state import DatabaseAccessState

ROLE = "alloq_app"
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "2026_10_15_desktop_database_role.py"
)


class FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> MagicMock:
        return MagicMock(all=lambda: self._value)


class FakeDatabase:
    """Answers the catalog queries of `db_access` and records every statement."""

    def __init__(
        self,
        *,
        can_manage: bool = True,
        members: list[str] | None = None,
        principals: dict[str, str] | None = None,
    ) -> None:
        self.can_manage = can_manage
        self.members = members or []
        self.principals = principals or {}
        self.statements: list[str] = []
        self.created: list[str] = []
        self.create_error: Exception | None = None

    async def execute(
        self, statement: TextClause, params: dict[str, Any] | None = None
    ) -> FakeResult:
        params = params or {}
        if statement is db_access._ROLE:
            return FakeResult(ROLE)
        if statement is db_access._CAN_MANAGE:
            return FakeResult(self.can_manage)
        if statement is db_access._MEMBERS:
            return FakeResult(self.members)
        if statement is db_access._PRINCIPAL:
            return FakeResult(self.principals.get(params["name"].lower()))
        if statement is db_access._CREATE_PRINCIPAL:
            if self.create_error:
                raise self.create_error
            self.created.append(params["name"])
            return FakeResult(None)
        self.statements.append(statement.text)
        return FakeResult(None)

    def factory(self) -> Callable[[], AbstractAsyncContextManager[Any]]:
        @asynccontextmanager
        async def _open() -> AsyncGenerator[Any]:
            yield self

        return _open


def _access(db: FakeDatabase) -> DatabaseAccess:
    return DatabaseAccess(sessions=db.factory(), maintenance=db.factory())


class TestQuoteIdentifier:
    def test_quotes_and_escapes(self) -> None:
        assert quote_identifier("ada@x.de") == '"ada@x.de"'
        assert quote_identifier('a"; DROP ROLE x; --') == '"a""; DROP ROLE x; --"'

    def test_rejects_nul(self) -> None:
        with pytest.raises(ValueError, match="NUL"):
            quote_identifier("a\x00b")


class TestDatabaseAccess:
    @pytest.mark.asyncio
    async def test_overview_lowercases_members(self) -> None:
        db = FakeDatabase(members=["Ada@X.de", "azure_pg_admin"])
        overview = await _access(db).overview()
        assert overview == AccessOverview(
            can_manage=True, members=frozenset({"ada@x.de", "azure_pg_admin"})
        )

    @pytest.mark.asyncio
    async def test_grant_uses_the_existing_principal(self) -> None:
        db = FakeDatabase(principals={"ada@x.de": "Ada@x.de"})
        await _access(db).grant("ada@x.de")
        assert db.created == []
        assert db.statements == ['GRANT "alloq_app" TO "Ada@x.de"']

    @pytest.mark.asyncio
    async def test_grant_creates_a_missing_principal(self) -> None:
        db = FakeDatabase()
        await _access(db).grant("bob@x.de")
        assert db.created == ["bob@x.de"]
        assert db.statements == ['GRANT "alloq_app" TO "bob@x.de"']

    @pytest.mark.asyncio
    async def test_grant_needs_admin_rights(self) -> None:
        db = FakeDatabase(can_manage=False)
        with pytest.raises(DatabaseAccessError, match="Admin-Rechte"):
            await _access(db).grant("bob@x.de")
        assert db.created == []
        assert db.statements == []

    @pytest.mark.asyncio
    async def test_unknown_microsoft_account(self) -> None:
        db = FakeDatabase()
        db.create_error = DBAPIError("SELECT", {}, Exception("no such principal"))
        with pytest.raises(DatabaseAccessError) as raised:
            await _access(db).grant("nobody@x.de")
        assert str(raised.value) == NO_PRINCIPAL.format(email="nobody@x.de")
        assert db.statements == []

    @pytest.mark.asyncio
    async def test_revoke(self) -> None:
        db = FakeDatabase(principals={"ada@x.de": "ada@x.de"})
        await _access(db).revoke("Ada@x.de")
        assert db.statements == ['REVOKE "alloq_app" FROM "ada@x.de"']

    @pytest.mark.asyncio
    async def test_revoke_without_principal_does_nothing(self) -> None:
        db = FakeDatabase()
        await _access(db).revoke("bob@x.de")
        assert db.statements == []

    @pytest.mark.asyncio
    async def test_revoke_needs_admin_rights(self) -> None:
        db = FakeDatabase(can_manage=False, principals={"ada@x.de": "ada@x.de"})
        with pytest.raises(DatabaseAccessError, match="Admin-Rechte"):
            await _access(db).revoke("ada@x.de")
        assert db.statements == []


class TestMaintenanceConnection:
    @pytest.mark.asyncio
    async def test_connects_to_the_postgres_database(self) -> None:
        config = MagicMock(url="postgresql+psycopg://:@db.example:5432/alloq")
        connection = object()

        @asynccontextmanager
        async def _begin() -> AsyncGenerator[Any]:
            yield connection

        engine = MagicMock(begin=_begin, dispose=AsyncMock())
        with (
            patch.object(db_access, "service_registry") as registry,
            patch.object(
                db_access, "create_async_engine", return_value=engine
            ) as create,
        ):
            registry.return_value.get.return_value = config
            async with maintenance_connection() as opened:
                assert opened is connection

        url = create.call_args.args[0]
        assert url.database == "postgres"
        assert url.host == "db.example"
        engine.dispose.assert_awaited_once()


def _login_state(*, is_admin: bool) -> MagicMock:
    user = MagicMock(is_admin=is_admin, user_id=1)

    async def _user() -> MagicMock:
        return user

    login_state = MagicMock()
    type(login_state).authenticated_user = property(lambda _self: _user())
    login_state.redir = AsyncMock(return_value=None)
    return login_state


def _state(*, is_admin: bool = True) -> DatabaseAccessState:
    state = DatabaseAccessState()
    object.__setattr__(
        state, "get_state", AsyncMock(return_value=_login_state(is_admin=is_admin))
    )
    return state


async def _run(handler: AsyncGenerator[Any]) -> list[Any]:
    return [event async for event in handler]


def _toasts(events: list[Any], kind: str) -> list[str]:
    return [str(e) for e in events if e is not None and kind in str(e)]


class TestDatabaseAccessState:
    @pytest.fixture
    def access(self) -> Iterator[MagicMock]:
        access = MagicMock()
        access.overview = AsyncMock(
            return_value=AccessOverview(
                can_manage=True, members=frozenset({"ada@x.de"})
            )
        )
        access.grant = AsyncMock()
        access.revoke = AsyncMock()
        with patch.object(db_access_state, "get_access", return_value=access):
            yield access

    @pytest.mark.asyncio
    async def test_load_in_the_desktop_app(self, access: MagicMock) -> None:
        state = _state()
        with patch.object(db_access_state, "is_desktop", return_value=True):
            await _run(state.load())
        access.overview.assert_awaited_once()
        assert state.can_manage is True
        assert state.members == ["ada@x.de"]
        assert state.locked is False

    @pytest.mark.asyncio
    async def test_load_on_the_server_does_nothing(self, access: MagicMock) -> None:
        state = _state()
        with patch.object(db_access_state, "is_desktop", return_value=False):
            await _run(state.load())
        access.overview.assert_not_called()
        assert state.locked is True

    @pytest.mark.asyncio
    async def test_load_failure_locks_the_switch(self, access: MagicMock) -> None:
        access.overview.side_effect = RuntimeError("connection lost")
        state = _state()
        state.can_manage = True
        with patch.object(db_access_state, "is_desktop", return_value=True):
            await _run(state.load())
        assert state.can_manage is False
        assert state.members == []

    @pytest.mark.asyncio
    async def test_load_needs_an_alloq_admin(self, access: MagicMock) -> None:
        state = _state(is_admin=False)
        with patch.object(db_access_state, "is_desktop", return_value=True):
            await _run(state.load())
        access.overview.assert_not_called()

    @pytest.mark.asyncio
    async def test_toggle_grants(self, access: MagicMock) -> None:
        state = _state()
        state.can_manage = True
        events = await _run(state.toggle("bob@x.de"))
        access.grant.assert_awaited_once_with("bob@x.de")
        access.revoke.assert_not_called()
        assert _toasts(events, "success")
        assert state.pending_email == ""

    @pytest.mark.asyncio
    async def test_toggle_revokes_a_member(self, access: MagicMock) -> None:
        state = _state()
        state.can_manage = True
        state.members = ["ada@x.de"]
        await _run(state.toggle("Ada@x.de"))
        access.revoke.assert_awaited_once_with("Ada@x.de")
        access.grant.assert_not_called()

    @pytest.mark.asyncio
    async def test_toggle_shows_the_access_error(self, access: MagicMock) -> None:
        access.grant.side_effect = DatabaseAccessError(NOT_ADMIN)
        state = _state()
        state.can_manage = True
        events = await _run(state.toggle("bob@x.de"))
        assert _toasts(events, "error")
        assert state.pending_email == ""

    @pytest.mark.asyncio
    async def test_toggle_hides_unexpected_errors(self, access: MagicMock) -> None:
        access.grant.side_effect = RuntimeError("boom")
        state = _state()
        state.can_manage = True
        events = await _run(state.toggle("bob@x.de"))
        errors = _toasts(events, "error")
        assert errors
        assert "boom" not in errors[0]

    @pytest.mark.asyncio
    async def test_toggle_without_db_admin_rights(self, access: MagicMock) -> None:
        state = _state()
        events = await _run(state.toggle("bob@x.de"))
        access.grant.assert_not_called()
        assert events == []

    @pytest.mark.asyncio
    async def test_toggle_needs_an_alloq_admin(self, access: MagicMock) -> None:
        state = _state(is_admin=False)
        state.can_manage = True
        await _run(state.toggle("bob@x.de"))
        access.grant.assert_not_called()

    @pytest.mark.asyncio
    async def test_toggle_ignores_users_without_email(self, access: MagicMock) -> None:
        state = _state()
        state.can_manage = True
        await _run(state.toggle(""))
        access.grant.assert_not_called()


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MIGRATION.stem, MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRoleMigration:
    @pytest.mark.parametrize("step", ["upgrade", "downgrade"])
    def test_only_postgresql_has_roles(self, step: str) -> None:
        migration = _migration()
        bind = MagicMock(dialect=SimpleNamespace(name="sqlite"))
        with patch.object(migration.op, "get_bind", return_value=bind):
            getattr(migration, step)()
        bind.execute.assert_not_called()

    @pytest.mark.parametrize(
        ("step", "statement"),
        [("upgrade", "_CREATE_ROLE"), ("downgrade", "_DROP_ROLE")],
    )
    def test_postgresql(self, step: str, statement: str) -> None:
        migration = _migration()
        bind = MagicMock(dialect=SimpleNamespace(name="postgresql"))
        with patch.object(migration.op, "get_bind", return_value=bind):
            getattr(migration, step)()
        bind.execute.assert_called_once_with(getattr(migration, statement))

    def test_admins_may_grant_the_role(self) -> None:
        sql = _migration()._CREATE_ROLE.text
        assert "TO azure_pg_admin WITH ADMIN OPTION" in sql
        assert "ALTER DEFAULT PRIVILEGES IN SCHEMA public" in sql
