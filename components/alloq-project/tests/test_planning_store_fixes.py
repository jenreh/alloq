"""PlanningStore: admin guard, heatmap filters, refresh and save edge cases."""

import datetime
from collections.abc import Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.entities import (
    AbsenceEntity,
    CapacityAllocationEntity,
    EmployeeEntity,
    ProjectEntity,
    RoleEntity,
)
from alloq_commons.models.project import Project
from alloq_commons.repositories import capacity_allocation_repo
from alloq_project.services.planning_builders import (
    absence_days_for_week,
    anchor_date,
    build_weeks,
    cell_key,
    parse_cell_changes,
    split_cell_key,
)
from alloq_project.states.planning_grid_state import PlanningStore
from sqlalchemy.ext.asyncio import AsyncSession

_STATE = "alloq_project.states.planning_grid_state"


class _FakeLogin:
    def __init__(self, *, is_admin: bool) -> None:
        self.is_admin = is_admin

    @property
    async def authenticated_user(self) -> Any:
        return SimpleNamespace(user_id=1, is_admin=self.is_admin)

    async def redir(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _admin_login() -> Iterator[None]:
    login = _FakeLogin(is_admin=True)
    with patch.object(PlanningStore, "get_state", AsyncMock(return_value=login)):
        yield


def _mock_session_ctx(session: Any) -> Any:
    @asynccontextmanager
    async def _ctx():  # noqa: ANN202
        yield session

    return _ctx


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _store(view_mode: str = "Grid") -> PlanningStore:
    weeks, spans = build_weeks(3)
    state = PlanningStore()  # type: ignore[call-arg]
    state.view_mode = view_mode
    state.weeks = weeks
    state.month_spans = spans
    state.employee_meta = [
        {
            "id": "emp-1",
            "real_id": 1,
            "name": "Alice A",
            "initials": "AA",
            "project_ids": ["proj-1"],
            "role_ids": [3],
        },
        {
            "id": "emp-2",
            "real_id": 2,
            "name": "Bob B",
            "initials": "BB",
            "project_ids": ["proj-1"],
            "role_ids": [4],
        },
    ]
    state.project_meta = [
        {"id": "proj-1", "real_id": 1, "code": "A", "name": "Alpha", "color": "#000"},
    ]
    state.cells = {cell_key("emp-1", "A", weeks[0].key): 5.0}
    state.saved_cells = dict(state.cells)
    return state


class TestAdminGuard:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_save_grid(self) -> None:
        state = _store()
        state.apply_cell_changes(
            [{"key": cell_key("emp-1", "A", state.weeks[1].key), "value": 2}]
        )
        upsert = AsyncMock()
        with (
            patch.object(
                PlanningStore,
                "get_state",
                AsyncMock(return_value=_FakeLogin(is_admin=False)),
            ),
            patch(f"{_STATE}.capacity_allocation_repo.batch_upsert", upsert),
        ):
            events = await _drain(state.save_grid())
        upsert.assert_not_called()
        assert len(events) == 1
        assert state.dirty_keys

    @pytest.mark.asyncio
    async def test_non_admin_cannot_load(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        with (
            patch.object(
                PlanningStore,
                "get_state",
                AsyncMock(return_value=_FakeLogin(is_admin=False)),
            ),
            patch.object(PlanningStore, "_load_entities", AsyncMock()) as load,
        ):
            await _drain(state.load())
        load.assert_not_called()


class TestHeatmapRespectsFilters:
    def test_employee_filter_limits_rows_and_average(self) -> None:
        state = _store("Heatmap")
        assert [e.real_id for e in state.employees] == [1, 2]
        state.employee_filter = ["2"]
        assert [e.real_id for e in state.employees] == [2]
        # Only Bob (nothing planned) is averaged, not Alice's 5 PT week.
        assert state.avg_heat[0].percent == state.employees[0].heat[0].percent

    def test_role_filter(self) -> None:
        state = _store("Heatmap")
        state.role_filter = ["3"]
        assert [e.real_id for e in state.employees] == [1]


class TestLoadErrors:
    @pytest.mark.asyncio
    async def test_db_error_resets_loading_and_toasts(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        with patch.object(
            PlanningStore,
            "_load_entities",
            AsyncMock(side_effect=RuntimeError("db down")),
        ):
            events = await _drain(state.load())
        assert state.is_loading is False
        assert any(e is not None for e in events)


class TestRefreshKeepsEdits:
    @pytest.mark.asyncio
    async def test_refresh_keeps_unsaved_edits(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        state.available_projects = [Project(id=1, code="A", name_de="Alpha")]
        with (
            patch.object(PlanningStore, "_load_entities", AsyncMock()),
            patch.object(
                PlanningStore, "_fetch_holidays", AsyncMock(return_value=set())
            ),
            patch.object(
                PlanningStore,
                "_fetch_data",
                AsyncMock(
                    return_value=(
                        [],
                        [
                            SimpleNamespace(
                                employee_id=1, project_id=1, role_id=3, role_name="Dev"
                            )
                        ],
                    )
                ),
            ),
        ):
            state.available_employees = []
            await state.refresh()
            key = cell_key("emp-1", "A", state.weeks[0].key)
            state.hidden_edits = {key: 3.0}
            await state.refresh()
        assert {**state.hidden_edits, **state.cells}.get(key) == 3.0

    @pytest.mark.asyncio
    async def test_add_and_remove_trigger_refresh_not_load(self) -> None:
        state = _store()
        state.add_project_emp_id = "emp-1"
        state.available_projects = [
            Project(
                id=1,
                code="A",
                name_de="Alpha",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 3, 1),
            )
        ]
        state.add_project_selected = "1"
        session = AsyncMock()
        session.add = lambda _obj: None
        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(session)),
            patch(
                f"{_STATE}.capacity_repo.find_by_project_and_employee",
                AsyncMock(return_value=[]),
            ),
        ):
            added = await _drain(state.add_project_to_employee_grid({"role_id": "3"}))
        assert PlanningStore.refresh in added
        assert PlanningStore.load not in added

    @pytest.mark.asyncio
    async def test_remove_drops_only_that_rows_edits(self) -> None:
        state = _store()
        removed = cell_key("emp-1", "A", state.weeks[1].key)
        kept = cell_key("emp-2", "A", state.weeks[1].key)
        state.apply_cell_changes(
            [{"key": removed, "value": 1}, {"key": kept, "value": 2}]
        )
        state.hidden_edits = {cell_key("emp-1", "A", "2030_01_07"): 4.0}
        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(
                f"{_STATE}.capacity_repo.delete_by_project_and_employee", AsyncMock()
            ),
            patch(
                f"{_STATE}.capacity_allocation_repo.delete_by_project_and_employee",
                AsyncMock(),
            ),
        ):
            events = await _drain(state.remove_project_from_employee_grid("emp-1", 1))
        assert PlanningStore.refresh in events
        assert state.dirty_keys == [kept]
        assert state.hidden_edits == {}


class TestAddProjectGuards:
    @pytest.mark.asyncio
    async def test_existing_assignment_is_not_duplicated(self) -> None:
        state = _store()
        state.add_project_emp_id = "emp-1"
        state.add_project_selected = "1"
        state.available_projects = [
            Project(
                id=1,
                code="A",
                name_de="Alpha",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 3, 1),
            )
        ]
        session = AsyncMock()
        added: list[Any] = []
        session.add = added.append
        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(session)),
            patch(
                f"{_STATE}.capacity_repo.find_by_project_and_employee",
                AsyncMock(return_value=[SimpleNamespace(role_id=3)]),
            ),
        ):
            await _drain(state.add_project_to_employee_grid({"role_id": "3"}))
        assert added == []

    @pytest.mark.asyncio
    async def test_non_numeric_role_is_rejected(self) -> None:
        state = _store()
        state.add_project_emp_id = "emp-1"
        state.add_project_selected = "1"
        events = await _drain(state.add_project_to_employee_grid({"role_id": "x"}))
        assert len(events) == 1


class TestSaveGridRoles:
    @pytest.mark.asyncio
    async def test_edit_updates_the_row_the_cell_shows(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        state.available_projects = [Project(id=1, code="A", name_de="Alpha")]
        with (
            patch.object(
                PlanningStore, "_fetch_holidays", AsyncMock(return_value=set())
            ),
            patch.object(
                PlanningStore, "_fetch_data", AsyncMock(return_value=([], []))
            ),
        ):
            await state._populate(3)
        weeks = [
            datetime.date(*(int(p) for p in w.key.split("_"))) for w in state.weeks
        ]
        allocations = [
            SimpleNamespace(
                employee_id=1,
                project_id=1,
                role_id=3,
                week_start=weeks[0],
                person_days=3.0,
                role_name="A",
            ),
            SimpleNamespace(
                employee_id=1,
                project_id=1,
                role_id=5,
                week_start=weeks[1],
                person_days=3.0,
                role_name="B",
            ),
        ]
        state.available_employees = []
        with (
            patch.object(
                PlanningStore, "_fetch_holidays", AsyncMock(return_value=set())
            ),
            patch.object(
                PlanningStore, "_fetch_data", AsyncMock(return_value=(allocations, []))
            ),
        ):
            await state._populate(3)
        state.employee_meta = [
            {"id": "emp-1", "real_id": 1, "project_ids": ["proj-1"], "role_ids": [3]}
        ]
        key = cell_key("emp-1", "A", state.weeks[1].key)
        state.hidden_edits = {key: 2.0}
        upsert = AsyncMock()
        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{_STATE}.capacity_allocation_repo.batch_upsert", upsert),
        ):
            await _drain(state.save_grid())
        rows = upsert.await_args.args[1]
        assert [(r["role_id"], r["person_days"]) for r in rows] == [(5, 2.0)]

    @pytest.mark.asyncio
    async def test_unmappable_edit_stays_pending(self) -> None:
        state = _store()
        good = cell_key("emp-1", "A", state.weeks[1].key)
        gone = cell_key("emp-1", "GONE", state.weeks[1].key)
        state.apply_cell_changes([{"key": good, "value": 2}])
        state.hidden_edits = {gone: 1.0}
        with (
            patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{_STATE}.capacity_allocation_repo.batch_upsert", AsyncMock()),
        ):
            events = await _drain(state.save_grid())
        assert state.dirty_keys == []
        assert state.hidden_edits == {gone: 1.0}
        assert len([e for e in events if e is not None]) == 2  # success + warning


class TestPipeInProjectCode:
    def test_split_cell_key_keeps_pipes_in_code(self) -> None:
        assert split_cell_key("emp-1|AB|1|2026_01_05") == (
            "emp-1",
            "AB|1",
            "2026_01_05",
        )
        assert split_cell_key("no-separators") is None

    def test_parse_accepts_code_with_pipe(self) -> None:
        key = "emp-1|AB|1|2026_01_05"
        updates, rejected = parse_cell_changes(
            [{"key": key, "value": 1}], {("emp-1", "AB|1")}, {"2026_01_05"}
        )
        assert (updates, rejected) == ({key: 1.0}, 0)


class TestAllocationRepository:
    async def _seed(self, session: AsyncSession) -> tuple[int, int, int]:
        project = ProjectEntity(
            code="R",
            customer="K",
            name_de="Repo",
            start_date=datetime.date(2026, 1, 5),
            end_date=datetime.date(2026, 3, 1),
            budget=1,
        )
        employee = EmployeeEntity(first_name="A", last_name="B", seniority="Senior")
        role = RoleEntity(name="Dev", abbreviation="DEV")
        session.add_all([project, employee, role])
        await session.flush()
        return project.id, employee.id, role.id

    @pytest.mark.asyncio
    async def test_batch_upsert_collapses_duplicate_keys(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, rid = await self._seed(async_session)
        week = datetime.date(2026, 1, 5)
        row = {
            "project_id": pid,
            "employee_id": eid,
            "role_id": rid,
            "week_start": week,
        }
        count = await capacity_allocation_repo.batch_upsert(
            async_session, [{**row, "person_days": 1.0}, {**row, "person_days": 2.0}]
        )
        stored = await capacity_allocation_repo.find_by_project(async_session, pid)
        assert count == 1
        assert [r.person_days for r in stored] == [2.0]

    @pytest.mark.asyncio
    async def test_find_cells_in_range_returns_role_name(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, rid = await self._seed(async_session)
        async_session.add(
            CapacityAllocationEntity(
                project_id=pid,
                employee_id=eid,
                role_id=rid,
                week_start=datetime.date(2026, 1, 12),
                person_days=3.0,
            )
        )
        await async_session.flush()
        rows = await capacity_allocation_repo.find_cells_in_range(
            async_session, datetime.date(2026, 1, 5), datetime.date(2026, 1, 31)
        )
        assert [(r.employee_id, r.role_name, r.person_days) for r in rows] == [
            (eid, "Dev", 3.0)
        ]


def test_absence_days_for_week_counts_overlapping_absences_once() -> None:
    """Overlapping absences share workdays; the grid must not double-count."""
    week_start = datetime.date(2026, 4, 27)
    absences = [
        SimpleNamespace(
            start_date=datetime.date(2026, 4, 27), end_date=datetime.date(2026, 4, 29)
        ),
        SimpleNamespace(
            start_date=datetime.date(2026, 4, 28), end_date=datetime.date(2026, 4, 30)
        ),
        SimpleNamespace(start_date=None, end_date=None),
    ]

    assert absence_days_for_week(absences, week_start) == 4.0


@pytest.mark.asyncio
async def test_load_entities_keeps_absences_in_displayed_past_weeks() -> None:
    """Absences that ended before today but inside the grid window are kept."""
    first_day = anchor_date()
    employee = EmployeeEntity(
        first_name="Anna",
        last_name="Berg",
        seniority="Senior",
        hours_per_week=40,
        internal_hours=0,
    )
    employee.id = 1
    employee.absences = [
        AbsenceEntity(id=1, employee_id=1, start_date=first_day, end_date=first_day),
        AbsenceEntity(
            id=2,
            employee_id=1,
            start_date=first_day - datetime.timedelta(days=14),
            end_date=first_day - datetime.timedelta(days=10),
        ),
    ]
    state = PlanningStore()  # type: ignore[call-arg]
    with (
        patch(f"{_STATE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
        patch(f"{_STATE}.project_repo.find_all", AsyncMock(return_value=[])),
        patch(f"{_STATE}.employee_repo.find_all", AsyncMock(return_value=[employee])),
        patch(f"{_STATE}.role_repo.find_all", AsyncMock(return_value=[])),
        patch.object(PlanningStore, "_resolve_current_employee", AsyncMock()),
    ):
        await state._load_entities()  # noqa: SLF001

    absences = state.available_employees[0].absences
    assert [a.start_date for a in absences] == [first_day]


_DB_ERROR = "duplicate key value violates uq_capacities_proj_emp_role"


@asynccontextmanager
async def _failing_session() -> Any:
    raise RuntimeError(_DB_ERROR)
    yield  # pragma: no cover


def _failing_store() -> PlanningStore:
    state = _store()
    state.apply_cell_changes(
        [{"key": cell_key("emp-1", "A", state.weeks[1].key), "value": 2}]
    )
    state.add_project_emp_id = "emp-1"
    state.add_project_selected = "1"
    state.available_projects = [
        Project(
            id=1,
            code="A",
            start_date=datetime.date(2099, 1, 1),
            end_date=datetime.date(2099, 12, 31),
        )
    ]
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("save_grid", ()),
        ("quick_create_project", ()),
        ("add_project_to_employee_grid", ({"role_id": "3"},)),
        ("remove_project_from_employee_grid", ("emp-1", 1)),
    ],
)
async def test_error_toasts_do_not_leak_exception_text(
    name: str, args: tuple[Any, ...]
) -> None:
    state = _failing_store()
    with patch(f"{_STATE}.get_asyncdb_session", _failing_session):
        events = await _drain(getattr(state, name)(*args))

    text = " ".join(str(e) for e in events if e is not None)
    assert "error" in text
    assert _DB_ERROR not in text
