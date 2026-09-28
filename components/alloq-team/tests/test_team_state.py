"""Tests for TeamState / EmployeeValidationState event handlers."""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.entities.absence import AbsenceEntity
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_team.states.team_state import EmployeeValidationState, TeamState

from appkit_user.authentication.states import LoginState

MODULE = "alloq_team.states.team_state"


class _FakeLoginState:
    """Stand-in for LoginState: yields a fresh awaitable user on each access."""

    def __init__(self, user: Any) -> None:
        self._user = user

    @property
    def authenticated_user(self) -> Any:
        async def _get() -> Any:
            return self._user

        return _get()

    @property
    def is_authenticated(self) -> Any:
        async def _get() -> bool:
            return self._user is not None

        return _get()

    async def redir(self) -> None:
        return None


def _user(*, is_admin: bool) -> MagicMock:
    user = MagicMock()
    user.is_admin = is_admin
    user.user_id = 1
    user.email = "admin@corp.test"
    return user


@contextmanager
def _as_user(state: Any, *, is_admin: bool = True, **others: Any) -> Iterator[None]:
    """Route ``state.get_state`` to a fake LoginState (and optional others)."""
    login = _FakeLoginState(_user(is_admin=is_admin))

    async def _get_state(cls: type) -> Any:
        if cls is LoginState:
            return login
        return others[cls.__name__]

    original = type(state).get_state
    object.__setattr__(state, "get_state", _get_state)
    try:
        yield
    finally:
        object.__setattr__(state, "get_state", original)


def _session_ctx(session: Any) -> Callable[[], Any]:
    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield session

    return _ctx


async def _run(handler: Any, *args: Any) -> list[Any]:
    """Drive an async-generator or coroutine handler and collect its output."""
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return [item async for item in result]
    return [await result]


def _employee_entity(emp_id: int = 7) -> EmployeeEntity:
    entity = EmployeeEntity(
        first_name="Alice",
        last_name="Admin",
        seniority="Senior",
        hours_per_week=40.0,
        internal_hours=4,
    )
    entity.id = emp_id
    entity.created = None
    entity.updated = None
    entity.roles = []
    entity.absences = []
    return entity


def _absence_entity(start: date, end: date, absence_id: int = 1) -> AbsenceEntity:
    entity = AbsenceEntity(employee_id=7, start_date=start, end_date=end)
    entity.id = absence_id
    entity.created = None
    entity.updated = None
    return entity


def _form(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "first_name": "Bob",
        "last_name": "Builder",
        "email": "bob@corp.test",
        "seniority": "Senior",
        "job_title": "",
        "location": "",
        "manager_id": "",
        "role_ids": "1",
        "hours_per_week": "40",
        "internal_hours": "4",
    }
    data.update(overrides)
    return data


@pytest.fixture
def repos() -> Iterator[dict[str, AsyncMock]]:
    """Patch every repository and the DB session used by the team state."""
    session = AsyncMock()
    mocks = {
        name: AsyncMock()
        for name in (
            "employee_repo",
            "absence_repo",
            "capacity_repo",
            "capacity_allocation_repo",
            "project_repo",
            "role_repo",
        )
    }
    patches = [patch(f"{MODULE}.{name}", mock) for name, mock in mocks.items()]
    patches.append(patch(f"{MODULE}.get_asyncdb_session", _session_ctx(session)))
    for p in patches:
        p.start()
    mocks["session"] = session
    try:
        yield mocks
    finally:
        for p in patches:
            p.stop()


def _toasts(items: list[Any]) -> str:
    return " ".join(str(i) for i in items if i is not None)


# ============================================================================
# Authorization
# ============================================================================


GUARDED_TEAM_HANDLERS: list[tuple[str, tuple[Any, ...]]] = [
    ("load_employees", ()),
    ("select_employee", (7,)),
    ("select_employee_and_add_absence", (7,)),
    ("open_add_project_modal", ()),
    ("create_employee", (_form(),)),
    ("update_employee", (_form(),)),
    ("delete_employee", (7,)),
    ("create_absence", ({},)),
    ("delete_absence", (1,)),
    ("assign_project_to_employee", ({"role_id": "1"},)),
    ("quick_create_project", ()),
    ("remove_project_from_employee", (3,)),
]


DB_ERROR_TEXT = "duplicate key value violates uq_employees_email (bob@corp.test)"


@asynccontextmanager
async def _failing_session() -> AsyncIterator[Any]:
    raise RuntimeError(DB_ERROR_TEXT)
    yield  # pragma: no cover


class TestTeamStateHidesDatabaseErrors:
    @pytest.mark.usefixtures("repos")
    @pytest.mark.parametrize(
        ("name", "args"),
        [
            ("create_employee", (_form(),)),
            ("update_employee", (_form(),)),
            ("delete_employee", (7,)),
            ("create_absence", ({},)),
            ("delete_absence", (1,)),
            ("assign_project_to_employee", ({"role_id": "1"},)),
            ("quick_create_project", ()),
            ("remove_project_from_employee", (3,)),
        ],
    )
    async def test_toast_does_not_leak_exception_text(
        self, name: str, args: tuple[Any, ...]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        state.add_project_selected = "3"
        state.all_projects = [
            Project(
                id=3,
                code="P3",
                start_date=date(2099, 1, 1),
                end_date=date(2099, 12, 31),
            )
        ]
        state.absence_date_range = ["2099-01-05", "2099-01-06"]
        with (
            _as_user(state),
            patch(f"{MODULE}.get_asyncdb_session", _failing_session),
        ):
            items = await _run(getattr(state, name), *args)

        text = _toasts(items)
        assert "error" in text
        assert DB_ERROR_TEXT not in text
        assert "uq_employees_email" not in text


class TestTeamStateAuthorization:
    @pytest.mark.parametrize(("name", "args"), GUARDED_TEAM_HANDLERS)
    async def test_non_admin_is_rejected(
        self, repos: dict[str, AsyncMock], name: str, args: tuple[Any, ...]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        state.add_project_selected = "3"
        state.absence_date_range = ["2099-01-05", "2099-01-06"]
        with (
            _as_user(state, is_admin=False),
            patch(f"{MODULE}.create_quick_project", AsyncMock()) as quick,
        ):
            items = await _run(getattr(state, name), *args)

        assert "keine Berechtigung" in _toasts(items)
        for key, mock in repos.items():
            if key != "session":
                assert mock.mock_calls == [], f"{name} touched {key}"
        quick.assert_not_awaited()

    async def test_admin_can_delete_employee(self, repos: dict[str, AsyncMock]) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["employee_repo"].delete_by_id = AsyncMock(return_value=True)
        repos["employee_repo"].find_all_paginated = AsyncMock(return_value=[])
        with _as_user(state):
            await _run(state.delete_employee, 7)

        repos["employee_repo"].delete_by_id.assert_awaited_once_with(
            repos["session"], 7
        )

    async def test_email_uniqueness_check_requires_admin(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = EmployeeValidationState()  # type: ignore[call-arg]
        state.email = "alice@corp.test"
        with _as_user(state, is_admin=False, TeamState=TeamState()):  # type: ignore[call-arg]
            await _run(state.validate_email_unique)

        repos["employee_repo"].find_by_email.assert_not_awaited()
        assert state.email_error == ""


# ============================================================================
# Project assignment
# ============================================================================


class TestAssignProjectToEmployee:
    @staticmethod
    def _state() -> TeamState:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        state.add_project_selected = "3"
        state.all_projects = [
            Project(
                id=3,
                code="P3",
                start_date=date(2099, 1, 1),
                end_date=date(2099, 12, 31),
            )
        ]
        return state

    async def test_same_role_twice_does_not_insert_duplicate(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = self._state()
        existing = MagicMock(role_id=1)
        repos["capacity_repo"].find_by_project_and_employee = AsyncMock(
            return_value=[existing]
        )
        with _as_user(state):
            items = await _run(state.assign_project_to_employee, {"role_id": "1"})

        repos["capacity_repo"].create.assert_not_awaited()
        assert "bereits" in _toasts(items)

    async def test_other_role_is_inserted(self, repos: dict[str, AsyncMock]) -> None:
        state = self._state()
        repos["capacity_repo"].find_by_project_and_employee = AsyncMock(
            return_value=[MagicMock(role_id=2)]
        )
        repos["capacity_repo"].find_by_employee_id = AsyncMock(return_value=[])
        with _as_user(state):
            items = await _run(state.assign_project_to_employee, {"role_id": "1"})

        repos["capacity_repo"].create.assert_awaited_once()
        assert "zugewiesen" in _toasts(items)


class TestRemoveProjectFromEmployee:
    async def test_also_deletes_weekly_allocations(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        repos["capacity_repo"].delete_by_project_and_employee = AsyncMock(
            return_value=True
        )
        repos["capacity_repo"].find_by_employee_id = AsyncMock(return_value=[])
        with _as_user(state):
            await _run(state.remove_project_from_employee, 3)

        repos["capacity_repo"].delete_by_project_and_employee.assert_awaited_once_with(
            repos["session"], 3, 7
        )
        alloc = repos["capacity_allocation_repo"].delete_by_project_and_employee
        alloc.assert_awaited_once_with(repos["session"], 3, 7)

    async def test_orphaned_allocations_are_removed_without_capacity_row(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        repos["capacity_repo"].delete_by_project_and_employee = AsyncMock(
            return_value=False
        )
        repos["capacity_allocation_repo"].delete_by_project_and_employee = AsyncMock(
            return_value=True
        )
        repos["capacity_repo"].find_by_employee_id = AsyncMock(return_value=[])
        with _as_user(state):
            items = await _run(state.remove_project_from_employee, 3)

        assert "entfernt" in _toasts(items)


class TestOpenAddProjectModal:
    async def test_loads_projects_lazily(self, repos: dict[str, AsyncMock]) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["project_repo"].find_all_paginated = AsyncMock(return_value=[])
        with _as_user(state):
            await _run(state.open_add_project_modal)

        assert state.add_project_modal_open is True
        repos["project_repo"].find_all_paginated.assert_awaited_once()


# ============================================================================
# Employee selection
# ============================================================================


class TestSelectEmployee:
    async def test_missing_employee_resets_loading_and_toasts(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["employee_repo"].find_by_id = AsyncMock(return_value=None)
        with _as_user(state):
            items = await _run(state.select_employee, 99)

        text = _toasts(items)
        assert "nicht gefunden" in text
        assert "set_is_loading" in text
        assert state.detail_drawer_open is False

    async def test_db_error_resets_loading(self, repos: dict[str, AsyncMock]) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["employee_repo"].find_by_id = AsyncMock(side_effect=RuntimeError("x"))
        with _as_user(state):
            items = await _run(state.select_employee, 99)

        assert "set_is_loading" in _toasts(items)

    async def test_opens_drawer_without_loading_all_projects(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["employee_repo"].find_by_id = AsyncMock(return_value=_employee_entity())
        repos["absence_repo"].find_by_employee_id = AsyncMock(return_value=[])
        repos["capacity_repo"].find_by_employee_id = AsyncMock(return_value=[])
        with _as_user(state):
            items = await _run(state.select_employee, 7)

        assert state.detail_drawer_open is True
        assert state.selected_employee is not None
        assert state.selected_employee.id == 7
        assert "set_is_loading" in _toasts(items)
        repos["project_repo"].find_all_paginated.assert_not_awaited()


# ============================================================================
# Employee create / update
# ============================================================================


class TestCreateEmployee:
    async def test_empty_internal_hours_does_not_crash(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["employee_repo"].find_all_paginated = AsyncMock(return_value=[])
        with _as_user(state):
            items = await _run(state.create_employee, _form(internal_hours=""))

        assert "erstellt" in _toasts(items)
        created = repos["employee_repo"].create.await_args.args[1]
        assert created.internal_hours == 0

    async def test_loads_employees_with_explicit_limit(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        repos["employee_repo"].find_all_paginated = AsyncMock(return_value=[])
        await state._load_employees()

        kwargs = repos["employee_repo"].find_all_paginated.await_args.kwargs
        assert kwargs["limit"] > 200


class TestUpdateEmployee:
    async def test_rejects_self_as_manager(self, repos: dict[str, AsyncMock]) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        with _as_user(state):
            items = await _run(state.update_employee, _form(manager_id="7"))

        assert "Vorgesetzter" in _toasts(items)
        repos["employee_repo"].update.assert_not_awaited()

    async def test_empty_internal_hours_does_not_crash(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        entity = _employee_entity()
        repos["employee_repo"].find_by_id = AsyncMock(return_value=entity)
        with _as_user(state):
            items = await _run(state.update_employee, _form(internal_hours=""))

        assert "aktualisiert" in _toasts(items)
        assert entity.internal_hours == 0


class TestEmployeeSelectOptions:
    def test_excludes_selected_employee(self) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.employees = [
            Employee(id=1, first_name="A", last_name="One"),
            Employee(id=2, first_name="B", last_name="Two"),
        ]
        state.selected_employee = state.employees[0]
        assert [o["value"] for o in state.employee_select_options] == ["2"]

    def test_open_add_modal_clears_stale_selection(self) -> None:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=1, first_name="A", last_name="One")
        state.open_add_modal()
        assert state.selected_employee is None
        assert state.add_modal_open is True


# ============================================================================
# Absences
# ============================================================================


class TestCreateAbsence:
    def _state(self, date_range: list[str]) -> TeamState:
        state = TeamState()  # type: ignore[call-arg]
        state.selected_employee = Employee(id=7, first_name="A", last_name="B")
        state.absence_date_range = date_range
        return state

    async def test_malformed_date_toasts_instead_of_raising(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = self._state(["2099-13-45", "2099-01-06"])
        with _as_user(state):
            items = await _run(state.create_absence, {})

        assert "gültigen Zeitraum" in _toasts(items)
        repos["absence_repo"].create.assert_not_awaited()

    async def test_reversed_range_is_rejected(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = self._state(["2099-01-10", "2099-01-05"])
        with _as_user(state):
            items = await _run(state.create_absence, {})

        assert "gültigen Zeitraum" in _toasts(items)
        repos["absence_repo"].create.assert_not_awaited()

    async def test_overlapping_absence_is_rejected(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = self._state(["2099-01-05", "2099-01-07"])
        repos["absence_repo"].find_by_employee_id = AsyncMock(
            return_value=[_absence_entity(date(2099, 1, 5), date(2099, 1, 6))]
        )
        with _as_user(state):
            items = await _run(state.create_absence, {})

        assert "überschneidet" in _toasts(items)
        repos["absence_repo"].create.assert_not_awaited()

    async def test_creates_non_overlapping_absence(
        self, repos: dict[str, AsyncMock]
    ) -> None:
        state = self._state(["2099-01-12", "2099-01-13"])
        existing = [_absence_entity(date(2099, 1, 5), date(2099, 1, 6))]
        repos["absence_repo"].find_by_employee_id = AsyncMock(return_value=existing)
        repos["employee_repo"].find_all_paginated = AsyncMock(return_value=[])
        with _as_user(state):
            items = await _run(state.create_absence, {})

        assert "eingetragen" in _toasts(items)
        created = repos["absence_repo"].create.await_args.args[1]
        assert created.start_date == date(2099, 1, 12)
        assert created.end_date == date(2099, 1, 13)
