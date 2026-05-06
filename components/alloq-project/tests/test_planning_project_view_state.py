"""Tests for PlanningProjectViewState helper functions and state."""

import datetime
from unittest.mock import MagicMock

from alloq_project.states.planning_grid_state import (
    GridCell,
    _build_weeks,
)
from alloq_project.states.planning_project_view_state import (
    EmployeeAllocationRow,
    PlanningProjectViewState,
    ProjectBlock,
    _build_project_blocks,
    _compute_project_gesamt,
    _compute_project_heat,
    _project_heat_bucket,
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


class TestBuildProjectBlocks:
    """Tests for _build_project_blocks."""

    def _make_project(
        self, id_: int, code: str, name: str, color: str = "#FFF"
    ) -> MagicMock:
        p = MagicMock()
        p.id = id_
        p.code = code
        p.name_de = name
        p.color = color
        p.state = "Aktiv"
        return p

    def _make_employee(self, id_: int, first: str, last: str) -> MagicMock:
        e = MagicMock()
        e.id = id_
        e.first_name = first
        e.last_name = last
        return e

    def _make_allocation(
        self,
        emp_id: int,
        proj_id: int,
        week_start,
        person_days: float,
    ) -> MagicMock:
        a = MagicMock()
        a.employee_id = emp_id
        a.project_id = proj_id
        a.week_start = week_start
        a.person_days = person_days
        a._cached_role_name = "Data Scientist"
        return a

    def test_empty_allocations(self) -> None:
        proj = self._make_project(1, "TST", "Test")
        emp = self._make_employee(1, "Alice", "Test")
        weeks, _ = _build_weeks(3)
        week_keys = [w.key for w in weeks]

        result = _build_project_blocks([proj], [], [], week_keys, [emp])
        # No allocations and no capacity assignments → no blocks
        assert result == []

    def test_single_allocation(self) -> None:
        proj = self._make_project(1, "TST", "Test")
        emp = self._make_employee(1, "Alice", "Smith")
        weeks, _ = _build_weeks(3)
        week_keys = [w.key for w in weeks]

        # Create an allocation for first week
        y, m, d = (int(p) for p in weeks[0].key.split("_"))
        alloc = self._make_allocation(1, 1, datetime.date(y, m, d), 3.0)

        result = _build_project_blocks([proj], [alloc], [], week_keys, [emp])
        assert len(result) == 1
        assert result[0].code == "TST"
        assert result[0].name == "Test"
        assert len(result[0].employees) == 1
        assert result[0].employees[0].name == "Alice Smith"
        assert result[0].employees[0].cells[0].value == 3.0

    def test_multiple_employees_same_project(self) -> None:
        proj = self._make_project(1, "CRM", "CRM System")
        emp1 = self._make_employee(1, "Alice", "A")
        emp2 = self._make_employee(2, "Bob", "B")
        weeks, _ = _build_weeks(2)
        week_keys = [w.key for w in weeks]

        y, m, d = (int(p) for p in weeks[0].key.split("_"))
        alloc1 = self._make_allocation(1, 1, datetime.date(y, m, d), 2.0)
        alloc2 = self._make_allocation(2, 1, datetime.date(y, m, d), 1.5)

        result = _build_project_blocks(
            [proj], [alloc1, alloc2], [], week_keys, [emp1, emp2]
        )
        assert len(result) == 1
        assert len(result[0].employees) == 2
        # Sorted alphabetically
        names = [e.name for e in result[0].employees]
        assert names == sorted(names)


class TestPlanningProjectViewState:
    """Tests for PlanningProjectViewState computed vars."""

    def test_initial_state(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        assert state.projects == []
        assert state.is_loaded is False
        assert state.collapsed_projects == []

    def test_filtered_projects_no_filter(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.projects = [
            ProjectBlock(id="proj-1", real_id=1, code="A", name="Alpha", color="#000"),
            ProjectBlock(id="proj-2", real_id=2, code="B", name="Beta", color="#FFF"),
        ]
        assert len(state.filtered_projects) == 2

    def test_filtered_projects_by_project(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.projects = [
            ProjectBlock(id="proj-1", real_id=1, code="A", name="Alpha", color="#000"),
            ProjectBlock(id="proj-2", real_id=2, code="B", name="Beta", color="#FFF"),
        ]
        state.project_filter = ["1"]
        assert len(state.filtered_projects) == 1
        assert state.filtered_projects[0].code == "A"

    def test_filtered_projects_by_employee(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.projects = [
            ProjectBlock(
                id="proj-1",
                real_id=1,
                code="A",
                name="Alpha",
                color="#000",
                employees=[
                    EmployeeAllocationRow(emp_id="emp-1", real_id=1, name="Alice")
                ],
            ),
            ProjectBlock(
                id="proj-2",
                real_id=2,
                code="B",
                name="Beta",
                color="#FFF",
                employees=[
                    EmployeeAllocationRow(emp_id="emp-2", real_id=2, name="Bob")
                ],
            ),
        ]
        state.employee_filter = ["1"]
        assert len(state.filtered_projects) == 1
        assert state.filtered_projects[0].code == "A"

    def test_filtered_projects_by_search(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.projects = [
            ProjectBlock(
                id="proj-1", real_id=1, code="CRM", name="CRM System", color="#000"
            ),
            ProjectBlock(
                id="proj-2", real_id=2, code="ML", name="ML Pipeline", color="#FFF"
            ),
        ]
        state.search_query = "pipeline"
        assert len(state.filtered_projects) == 1
        assert state.filtered_projects[0].code == "ML"

    def test_toggle_project(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.toggle_project("proj-1")
        assert "proj-1" in state.collapsed_projects

        state.toggle_project("proj-1")
        assert "proj-1" not in state.collapsed_projects

    def test_has_dirty_empty(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.projects = []
        assert state.has_dirty is False

    def test_has_dirty_with_dirty_cell(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        state.projects = [
            ProjectBlock(
                id="proj-1",
                real_id=1,
                code="A",
                name="Alpha",
                color="#000",
                employees=[
                    EmployeeAllocationRow(
                        emp_id="emp-1",
                        real_id=1,
                        name="Alice",
                        cells=[
                            GridCell(
                                key="emp-1|A|2026_05_05",
                                week_key="2026_05_05",
                                value=2.0,
                                is_dirty=True,
                            )
                        ],
                    )
                ],
            )
        ]
        assert state.has_dirty is True

    def test_commit_current(self) -> None:
        state = PlanningProjectViewState()  # type: ignore[call-arg]
        weeks, _spans = _build_weeks(1)
        wk = weeks[0].key
        state.weeks = weeks
        state.projects = [
            ProjectBlock(
                id="proj-1",
                real_id=1,
                code="TST",
                name="Test",
                color="#000",
                employees=[
                    EmployeeAllocationRow(
                        emp_id="emp-1",
                        real_id=1,
                        name="Alice",
                        cells=[
                            GridCell(
                                key=f"emp-1|TST|{wk}",
                                week_key=wk,
                                value=0.0,
                            )
                        ],
                    )
                ],
            )
        ]
        state.editing_cell = f"emp-1|TST|{wk}"
        state.draft_value = "3,5"
        state._commit_current()

        cell = state.projects[0].employees[0].cells[0]
        assert cell.value == 3.5
        assert cell.is_dirty is True
