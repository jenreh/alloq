"""Tests for the role resolution of PlanningStore.save_grid."""

import datetime
from collections.abc import Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_project.services.planning_builders import build_weeks
from alloq_project.states.planning_grid_state import PlanningStore


class _FakeLogin:
    """LoginState stand-in for the admin guard on PlanningStore handlers."""

    def __init__(self, *, is_admin: bool) -> None:
        self.is_admin = is_admin

    @property
    async def authenticated_user(self) -> Any:
        return SimpleNamespace(user_id=1, is_admin=self.is_admin)

    async def redir(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _admin_login() -> Iterator[None]:
    """Run every handler as an admin unless a test overrides ``get_state``."""
    login = _FakeLogin(is_admin=True)
    with patch.object(PlanningStore, "get_state", AsyncMock(return_value=login)):
        yield


ROLE_A = 3
ROLE_B = 5


def _mock_session_ctx(session: AsyncMock):
    """Create an async context manager mock for get_asyncdb_session."""

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


def _employee() -> Employee:
    return Employee(
        id=1,
        first_name="Ada",
        last_name="Lovelace",
        role_names=["Architect", "Developer"],
        role_ids=[ROLE_A, ROLE_B],
    )


def _allocation(role_id: int, week_start: datetime.date) -> SimpleNamespace:
    return SimpleNamespace(
        employee_id=1,
        project_id=1,
        role_id=role_id,
        week_start=week_start,
        person_days=1.0,
        role_name="",
    )


def _assignment(role_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(
        employee_id=1,
        project_id=1,
        role_id=role_id,
        role_name="Developer" if role_id else "",
    )


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


async def _saved_role_ids(
    allocations: list[SimpleNamespace], assignments: list[SimpleNamespace]
) -> set[int]:
    """Load the grid, edit the first cell and return the saved role ids."""
    state = PlanningStore()  # type: ignore[call-arg]
    state.available_employees = [_employee()]
    state.available_projects = [Project(id=1, code="P1", name_de="Projekt")]
    with (
        patch.object(PlanningStore, "_fetch_holidays", AsyncMock(return_value=set())),
        patch.object(
            PlanningStore,
            "_fetch_data",
            AsyncMock(return_value=(allocations, assignments)),
        ),
    ):
        await state._populate(2)

    key = f"emp-1|P1|{state.weeks[0].key}"
    state.cells = {**state.cells, key: 2.0}
    state.dirty_keys = [key]
    repo = AsyncMock()
    with (
        patch(
            "alloq_project.states.planning_grid_state.get_asyncdb_session",
            _mock_session_ctx(AsyncMock()),
        ),
        patch(
            "alloq_project.states.planning_grid_state.capacity_allocation_repo",
            repo,
        ),
    ):
        await _drain(state.save_grid())

    rows = repo.batch_upsert.call_args.args[1]
    return {row["role_id"] for row in rows}


class TestSaveGridRole:
    """save_grid stores the role of the employee-project assignment."""

    @pytest.mark.asyncio
    async def test_uses_assignment_role_not_first_employee_role(self) -> None:
        assert await _saved_role_ids([], [_assignment(ROLE_B)]) == {ROLE_B}

    @pytest.mark.asyncio
    async def test_existing_allocation_role_takes_precedence(self) -> None:
        weeks, _ = build_weeks(2)
        week = datetime.date(*(int(p) for p in weeks[0].key.split("_")))
        allocations = [_allocation(ROLE_B, week)]

        saved = await _saved_role_ids(allocations, [_assignment(ROLE_A)])

        assert saved == {ROLE_B}

    @pytest.mark.asyncio
    async def test_falls_back_to_first_employee_role(self) -> None:
        assert await _saved_role_ids([], [_assignment(None)]) == {ROLE_A}
