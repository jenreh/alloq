"""Unsaved grid edits survive switching the planning time range."""

import datetime
from collections.abc import Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_project.services.planning_builders import split_edits
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


_STATE = "alloq_project.states.planning_grid_state"


def _mock_session_ctx(session: AsyncMock) -> Any:
    @asynccontextmanager
    async def _ctx():  # noqa: ANN202
        yield session

    return _ctx


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _db_allocations(state: PlanningStore, week_idx: int, days: float) -> list[Any]:
    """An allocation row as returned by the DB for the given loaded week."""
    y, m, d = (int(p) for p in state.weeks[week_idx].key.split("_"))
    return [
        SimpleNamespace(
            employee_id=1,
            project_id=1,
            role_id=3,
            week_start=datetime.date(y, m, d),
            person_days=days,
            role_name="",
        )
    ]


class _Planner:
    """Drives PlanningStore._populate with a fake DB."""

    def __init__(self) -> None:
        self.state = PlanningStore()
        self.state.available_employees = [
            Employee(
                id=1,
                first_name="Ada",
                last_name="Lovelace",
                role_names=["Dev"],
                role_ids=[3],
            )
        ]
        self.state.available_projects = [Project(id=1, code="P1", name_de="Projekt")]
        self.allocations: list[Any] = []
        self.assignments = [
            SimpleNamespace(employee_id=1, project_id=1, role_id=3, role_name="Dev")
        ]

    async def load(self, time_range: str = "3 Monate") -> None:
        self.state.time_range = time_range
        with self._fake_db():
            await _drain(self.state.load())

    async def switch(self, time_range: str) -> Any:
        with self._fake_db():
            self.state.set_time_range(time_range)
            return await self.state.reload_with_time_range(time_range)

    def key(self, week_idx: int) -> str:
        return f"emp-1|P1|{self.state.weeks[week_idx].key}"

    def edit(self, week_idx: int, value: float) -> str:
        key = self.key(week_idx)
        self.state.apply_cell_changes([{"key": key, "value": value}])
        return key

    def _fake_db(self) -> Any:
        planner = self

        class _Ctx:
            def __enter__(self) -> None:
                self._patches = [
                    patch.object(
                        PlanningStore, "_load_entities", AsyncMock(return_value=None)
                    ),
                    patch.object(
                        PlanningStore,
                        "_fetch_holidays",
                        AsyncMock(return_value=set()),
                    ),
                    patch.object(
                        PlanningStore,
                        "_fetch_data",
                        AsyncMock(
                            return_value=(planner.allocations, planner.assignments)
                        ),
                    ),
                ]
                for p in self._patches:
                    p.start()

            def __exit__(self, *exc: object) -> None:
                for p in self._patches:
                    p.stop()

        return _Ctx()


class TestSplitEdits:
    def test_splits_by_week_and_row(self) -> None:
        edits = {"e|A|w1": 1.0, "e|A|w9": 2.0, "e|B|w1": 3.0, "bad": 4.0}
        visible, hidden = split_edits(edits, {("e", "A")}, {"w1"})
        assert visible == {"e|A|w1": 1.0}
        assert hidden == {"e|A|w9": 2.0, "e|B|w1": 3.0, "bad": 4.0}


class TestTimeRangeKeepsEdits:
    @pytest.mark.asyncio
    async def test_edit_stays_visible_and_dirty_when_range_grows(self) -> None:
        planner = _Planner()
        await planner.load("3 Monate")
        key = planner.edit(2, 1.5)

        await planner.switch("12 Monate")

        state = planner.state
        assert len(state.weeks) == 52
        assert state.cells[key] == 1.5
        assert state.dirty_keys == [key]
        assert state.hidden_edits == {}
        assert state.has_dirty is True

    @pytest.mark.asyncio
    async def test_edit_outside_new_range_is_kept_and_restored(self) -> None:
        planner = _Planner()
        await planner.load("6 Monate")
        key = planner.edit(20, 2.0)

        toast = await planner.switch("3 Monate")

        state = planner.state
        assert key not in state.cells
        assert state.hidden_edits == {key: 2.0}
        assert state.dirty_keys == []
        assert state.has_dirty is True
        assert toast is not None

        await planner.switch("6 Monate")

        assert state.cells[key] == 2.0
        assert state.dirty_keys == [key]
        assert state.hidden_edits == {}

    @pytest.mark.asyncio
    async def test_edit_matching_db_value_is_not_dirty(self) -> None:
        planner = _Planner()
        await planner.load("3 Monate")
        key = planner.edit(1, 4.0)
        planner.allocations = _db_allocations(planner.state, 1, 4.0)

        await planner.switch("6 Monate")

        assert planner.state.cells[key] == 4.0
        assert planner.state.dirty_keys == []

    @pytest.mark.asyncio
    async def test_save_includes_hidden_edits(self) -> None:
        planner = _Planner()
        await planner.load("6 Monate")
        hidden_key = planner.edit(20, 2.0)
        await planner.switch("3 Monate")
        visible_key = planner.edit(0, 1.0)
        state = planner.state

        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(
                f"{_STATE}.capacity_allocation_repo.batch_upsert", AsyncMock()
            ) as upsert,
        ):
            await _drain(state.save_grid())

        assert upsert.await_args is not None

        rows = upsert.await_args.args[1]
        saved = {(r["week_start"].isoformat(), r["person_days"]) for r in rows}
        hidden_week = hidden_key.split("|")[2].replace("_", "-")
        visible_week = visible_key.split("|")[2].replace("_", "-")
        assert saved == {(hidden_week, 2.0), (visible_week, 1.0)}
        assert all(r["role_id"] == 3 for r in rows)
        assert state.hidden_edits == {}
        assert state.dirty_keys == []
        assert state.has_dirty is False

    @pytest.mark.asyncio
    async def test_page_load_still_starts_clean(self) -> None:
        planner = _Planner()
        await planner.load("6 Monate")
        planner.edit(20, 2.0)
        await planner.switch("3 Monate")
        planner.edit(0, 1.0)

        await planner.load("3 Monate")

        assert planner.state.dirty_keys == []
        assert planner.state.hidden_edits == {}
        assert planner.state.has_dirty is False
