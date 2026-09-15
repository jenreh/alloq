"""Tests for the project pivot of PlanningStore and its helper functions."""

import datetime
from unittest.mock import MagicMock

from alloq_project.states.planning_grid_state import (
    EmployeeAllocationRow,
    GridCell,
    PlanningStore,
    ProjectBlock,
    _build_employee_meta,
    _build_project_meta,
    _build_weeks,
    _ck,
    _compute_project_gesamt,
    _compute_project_heat,
    _ingest_allocations,
    _project_heat_bucket,
    _wire_pairs,
)


class TestProjectHeatBucket:
    """Tests for _project_heat_bucket."""

    def test_zero_allocation(self) -> None:
        assert _project_heat_bucket(0.0) == "low"

    def test_low_allocation(self) -> None:
        assert _project_heat_bucket(1.5) == "mid"

    def test_mid_allocation(self) -> None:
        assert _project_heat_bucket(3.0) == "high"

    def test_high_allocation(self) -> None:
        assert _project_heat_bucket(5.0) == "over"


class TestComputeProjectGesamt:
    """Tests for _compute_project_gesamt."""

    def test_empty_project(self) -> None:
        weeks, _ = _build_weeks(3)
        block = ProjectBlock(
            id="proj-1",
            real_id=1,
            code="TST",
            name="Test",
            color="#000",
            employees=[],
        )
        result = _compute_project_gesamt(weeks, block)
        assert len(result) == 3
        assert all(c.allocated == 0.0 for c in result)
        assert all(c.bucket == "low" for c in result)

    def test_with_allocations(self) -> None:
        weeks, _ = _build_weeks(2)
        emp = EmployeeAllocationRow(
            emp_id="emp-1",
            real_id=1,
            name="Alice",
            role_short="DS",
            cells=[
                GridCell(key="emp-1|TST|k0", week_key=weeks[0].key, value=2.0),
                GridCell(key="emp-1|TST|k1", week_key=weeks[1].key, value=3.0),
            ],
        )
        block = ProjectBlock(
            id="proj-1",
            real_id=1,
            code="TST",
            name="Test",
            color="#000",
            employees=[emp],
        )
        result = _compute_project_gesamt(weeks, block)
        assert result[0].allocated == 2.0
        assert result[1].allocated == 3.0

    def test_multiple_employees(self) -> None:
        weeks, _ = _build_weeks(1)
        emp1 = EmployeeAllocationRow(
            emp_id="emp-1",
            real_id=1,
            name="Alice",
            cells=[
                GridCell(key="emp-1|TST|k", week_key=weeks[0].key, value=2.0),
            ],
        )
        emp2 = EmployeeAllocationRow(
            emp_id="emp-2",
            real_id=2,
            name="Bob",
            cells=[
                GridCell(key="emp-2|TST|k", week_key=weeks[0].key, value=1.5),
            ],
        )
        block = ProjectBlock(
            id="proj-1",
            real_id=1,
            code="TST",
            name="Test",
            color="#000",
            employees=[emp1, emp2],
        )
        result = _compute_project_gesamt(weeks, block)
        assert result[0].allocated == 3.5


class TestComputeProjectHeat:
    """Tests for _compute_project_heat."""

    def test_no_employees(self) -> None:
        weeks, _ = _build_weeks(2)
        block = ProjectBlock(
            id="proj-1",
            real_id=1,
            code="TST",
            name="Test",
            color="#000",
            employees=[],
        )
        result = _compute_project_heat(weeks, block)
        assert len(result) == 2
        assert all(c.percent == 0 for c in result)

    def test_full_utilization(self) -> None:
        weeks, _ = _build_weeks(1)
        emp = EmployeeAllocationRow(
            emp_id="emp-1",
            real_id=1,
            name="Alice",
            cells=[
                GridCell(
                    key="emp-1|TST|k",
                    week_key=weeks[0].key,
                    value=weeks[0].work_days,
                ),
            ],
        )
        block = ProjectBlock(
            id="proj-1",
            real_id=1,
            code="TST",
            name="Test",
            color="#000",
            employees=[emp],
        )
        result = _compute_project_heat(weeks, block)
        assert result[0].percent == 100
        assert result[0].bucket == "high"


def _make_project(id_: int, code: str, name: str, color: str = "#FFF") -> MagicMock:
    p = MagicMock()
    p.id = id_
    p.code = code
    p.name_de = name
    p.color = color
    p.state = "Aktiv"
    return p


def _make_employee(id_: int, first: str, last: str) -> MagicMock:
    e = MagicMock()
    e.id = id_
    e.first_name = first
    e.last_name = last
    e.job_title = ""
    e.absences = []
    e.role_names = []
    e.role_ids = []
    e.internal_hours = 4
    e.hours_per_week = 40.0
    e.workload_percent = 100
    return e


def _make_allocation(
    emp_id: int, proj_id: int, week_start: datetime.date, person_days: float
) -> MagicMock:
    a = MagicMock()
    a.employee_id = emp_id
    a.project_id = proj_id
    a.week_start = week_start
    a.person_days = person_days
    a._cached_role_name = "Data Scientist"
    return a


def _week_date(key: str) -> datetime.date:
    y, m, d = (int(p) for p in key.split("_"))
    return datetime.date(y, m, d)


def _populated_store(
    projects: list[MagicMock],
    employees: list[MagicMock],
    allocations: list[MagicMock],
    num_weeks: int = 2,
) -> PlanningStore:
    """Build a store the same way ``PlanningStore._populate`` does, minus the DB."""
    weeks, spans = _build_weeks(num_weeks)
    wks = [w.key for w in weeks]
    emp_meta, absence_map = _build_employee_meta(employees, wks)
    proj_meta, proj_idx = _build_project_meta(projects)
    cells, role_lookup, pairs = _ingest_allocations(allocations, [], proj_idx, set(wks))
    _wire_pairs(emp_meta, proj_idx, pairs)

    state = PlanningStore()  # type: ignore[call-arg]
    state.weeks = weeks
    state.month_spans = spans
    state.cells = cells
    state.employee_meta = emp_meta
    state.project_meta = proj_meta
    state.role_lookup = role_lookup
    state.absence_days = absence_map
    return state


class TestProjectBlocks:
    """Tests for the PlanningStore.project_blocks pivot."""

    def test_no_allocations_yields_empty_blocks(self) -> None:
        state = _populated_store(
            [_make_project(1, "TST", "Test")], [_make_employee(1, "Alice", "A")], []
        )
        blocks = state.project_blocks
        assert len(blocks) == 1
        assert blocks[0].employees == []

    def test_single_allocation(self) -> None:
        weeks, _ = _build_weeks(2)
        alloc = _make_allocation(1, 1, _week_date(weeks[0].key), 3.0)
        state = _populated_store(
            [_make_project(1, "TST", "Test")],
            [_make_employee(1, "Alice", "Smith")],
            [alloc],
        )
        blocks = state.project_blocks
        assert blocks[0].code == "TST"
        assert blocks[0].name == "Test"
        assert len(blocks[0].employees) == 1
        assert blocks[0].employees[0].name == "Alice Smith"
        assert blocks[0].employees[0].cells[0].value == 3.0
        assert blocks[0].gesamt[0].allocated == 3.0

    def test_employees_sorted_by_name(self) -> None:
        weeks, _ = _build_weeks(2)
        wk = _week_date(weeks[0].key)
        state = _populated_store(
            [_make_project(1, "CRM", "CRM System")],
            [_make_employee(2, "Bob", "B"), _make_employee(1, "Alice", "A")],
            [_make_allocation(2, 1, wk, 1.5), _make_allocation(1, 1, wk, 2.0)],
        )
        names = [e.name for e in state.project_blocks[0].employees]
        assert names == ["Alice A", "Bob B"]

    def test_empty_without_weeks(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        assert state.project_blocks == []


class TestPlanningStoreProjectView:
    """Tests for PlanningStore project-view filters and interactions."""

    def _two_project_store(self) -> PlanningStore:
        weeks, _ = _build_weeks(2)
        wk = _week_date(weeks[0].key)
        return _populated_store(
            [_make_project(1, "A", "Alpha"), _make_project(2, "B", "Beta")],
            [_make_employee(1, "Alice", "A"), _make_employee(2, "Bob", "B")],
            [_make_allocation(1, 1, wk, 1.0), _make_allocation(2, 2, wk, 1.0)],
        )

    def test_initial_state(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        assert state.projects == []
        assert state.is_loaded is False
        assert state.collapsed_projects == []

    def test_filtered_projects_no_filter(self) -> None:
        state = self._two_project_store()
        assert len(state.filtered_projects) == 2

    def test_filtered_projects_by_project(self) -> None:
        state = self._two_project_store()
        state.project_filter = ["1"]
        assert [p.code for p in state.filtered_projects] == ["A"]

    def test_filtered_projects_by_employee(self) -> None:
        state = self._two_project_store()
        state.employee_filter = ["2"]
        assert [p.code for p in state.filtered_projects] == ["B"]

    def test_toggle_project(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        state.toggle_project("proj-1")
        assert "proj-1" in state.collapsed_projects

        state.toggle_project("proj-1")
        assert "proj-1" not in state.collapsed_projects

    def test_has_dirty_empty(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        assert state.has_dirty is False

    def test_has_dirty_with_dirty_key(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        state.dirty_keys = ["emp-1|A|2026_05_05"]
        assert state.has_dirty is True

    def test_commit_current(self) -> None:
        state = self._two_project_store()
        key = _ck("emp-1", "A", state.weeks[0].key)
        state.editing_cell = key
        state.draft_value = "3,5"

        assert state._commit_current() == (key, 3.5)
        assert state.cells[key] == 3.5
        assert key in state.dirty_keys
        cell = state.project_blocks[0].employees[0].cells[0]
        assert cell.value == 3.5
        assert cell.is_dirty is True

    def test_commit_current_rejects_invalid_draft(self) -> None:
        state = self._two_project_store()
        key = _ck("emp-1", "A", state.weeks[0].key)
        state.editing_cell = key
        state.draft_value = "abc"

        assert state._commit_current() is None
        assert state.dirty_keys == []
