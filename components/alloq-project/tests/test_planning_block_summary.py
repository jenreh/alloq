"""Tests for the per-block summaries shown next to employee/project headers."""

import datetime
from unittest.mock import MagicMock

from alloq_project.services.planning_builders import (
    anchor_date,
    build_employee_meta,
    build_project_meta,
    build_weeks,
    current_week_key,
    employee_summary,
    ingest_allocations,
    project_summary,
    wire_pairs,
)
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import (
    AbsenceRow,
    EmployeeAllocationRow,
    EmployeeBlock,
    GesamtCell,
    GridCell,
    ProjectAllocationRow,
    ProjectBlock,
)


def _cells(weeks: list, values: list[float]) -> list[GridCell]:
    return [
        GridCell(week_key=w.key, value=v) for w, v in zip(weeks, values, strict=True)
    ]


def _emp_block(
    weeks: list, projects: list[list[float]], free: list[float]
) -> EmployeeBlock:
    return EmployeeBlock(
        id="emp-1",
        name="Alice",
        initials="A",
        role="DS",
        role_color="",
        projects=[
            ProjectAllocationRow(
                project_id=str(i),
                code=f"P{i}",
                name="",
                color="",
                cells=_cells(weeks, vals),
            )
            for i, vals in enumerate(projects)
        ],
        absence=AbsenceRow(cells=[]),
        gesamt=[
            GesamtCell(week_key=w.key, value=v, bucket="")
            for w, v in zip(weeks, free, strict=True)
        ],
    )


def _emp_row(
    weeks: list, role: str, values: list[float], name: str = ""
) -> EmployeeAllocationRow:
    return EmployeeAllocationRow(
        role_short=role,
        role_name=name or role,
        role_color=f"color-{role}",
        cells=_cells(weeks, values),
    )


class TestCurrentWeekKey:
    def test_is_week_after_anchor(self) -> None:
        weeks, _ = build_weeks(3)
        assert current_week_key() == weeks[1].key

    def test_is_monday(self) -> None:
        y, m, d = (int(p) for p in current_week_key().split("_"))
        assert datetime.date(y, m, d).weekday() == 0
        assert datetime.date(y, m, d) > anchor_date()


class TestEmployeeSummary:
    def test_skips_weeks_before_current(self) -> None:
        weeks, _ = build_weeks(3)
        block = _emp_block(weeks, [[5.0, 1.0, 2.0], [9.0, 0.5, 0.0]], [9.0, 1.0, 2.5])
        planned, available = employee_summary(block, weeks[1].key)
        assert planned == 3.5
        assert available == 3.5

    def test_available_ignores_overbooked_weeks(self) -> None:
        weeks, _ = build_weeks(3)
        block = _emp_block(weeks, [[0.0, 6.0, 1.0]], [0.0, -1.5, 3.0])
        _, available = employee_summary(block, weeks[0].key)
        assert available == 3.0

    def test_no_projects(self) -> None:
        weeks, _ = build_weeks(2)
        block = _emp_block(weeks, [], [4.5, 4.5])
        assert employee_summary(block, weeks[1].key) == (0.0, 4.5)

    def test_rounds_to_two_decimals(self) -> None:
        weeks, _ = build_weeks(3)
        block = _emp_block(weeks, [[0.0, 0.1, 0.2]], [0.0, 0.1, 0.2])
        assert employee_summary(block, weeks[0].key) == (0.3, 0.3)


class TestProjectSummary:
    def test_total_and_roles_from_current_week(self) -> None:
        weeks, _ = build_weeks(3)
        block = ProjectBlock(
            employees=[
                _emp_row(weeks, "DS", [7.0, 2.0, 2.0]),
                _emp_row(weeks, "AIA", [1.0, 0.0, 1.5]),
                _emp_row(weeks, "DS", [0.0, 1.0, 0.0]),
            ]
        )
        total, roles = project_summary(block, weeks[1].key)
        assert total == 6.5
        assert [(r.code, r.days, r.color) for r in roles] == [
            ("AIA", 1.5, "color-AIA"),
            ("DS", 5.0, "color-DS"),
        ]

    def test_omits_roles_without_days(self) -> None:
        weeks, _ = build_weeks(2)
        block = ProjectBlock(
            employees=[
                _emp_row(weeks, "DS", [3.0, 0.0]),
                _emp_row(weeks, "PM", [0.0, 1.0]),
            ]
        )
        total, roles = project_summary(block, weeks[1].key)
        assert total == 1.0
        assert [r.code for r in roles] == ["PM"]

    def test_no_employees(self) -> None:
        weeks, _ = build_weeks(2)
        assert project_summary(ProjectBlock(), weeks[1].key) == (0.0, [])

    def test_roles_sharing_an_abbreviation_stay_separate(self) -> None:
        weeks, _ = build_weeks(1)
        block = ProjectBlock(
            employees=[
                _emp_row(weeks, "SD", [1.0], name="Senior Developer"),
                _emp_row(weeks, "SD", [2.0], name="Software Developer"),
            ]
        )
        total, roles = project_summary(block, weeks[0].key)
        assert total == 3.0
        assert [(r.code, r.days) for r in roles] == [("SD", 1.0), ("SD", 2.0)]


def _employee(emp_id: int) -> MagicMock:
    e = MagicMock()
    e.id = emp_id
    e.first_name = "Alice"
    e.last_name = "A"
    e.job_title = ""
    e.role_names = ["Data Scientist"]
    e.role_ids = [1]
    e.absences = []
    e.internal_hours = 0
    e.hours_per_week = 40.0
    e.workload_percent = 100
    return e


def _project(pid: int, code: str) -> MagicMock:
    p = MagicMock()
    p.id = pid
    p.code = code
    p.name_de = code
    p.color = "#000"
    p.state = "Aktiv"
    return p


def _allocation(week_key: str, days: float) -> MagicMock:
    a = MagicMock()
    a.employee_id = 1
    a.project_id = 1
    a.week_start = datetime.date(*(int(p) for p in week_key.split("_")))
    a.person_days = days
    a.role_id = 1
    a._cached_role_name = "Data Scientist"
    return a


class TestStoreBlocksCarrySummary:
    def _store(self) -> PlanningStore:
        weeks, spans = build_weeks(3)
        wks = [w.key for w in weeks]
        emp_meta, absence_map = build_employee_meta([_employee(1)], wks)
        proj_meta, proj_idx = build_project_meta([_project(1, "TST")])
        allocs = [_allocation(wks[0], 4.0), _allocation(wks[2], 2.0)]
        cells, role_lookup, _, pairs = ingest_allocations(
            allocs, [], proj_idx, set(wks)
        )
        wire_pairs(emp_meta, proj_idx, pairs)
        state = PlanningStore()  # type: ignore[call-arg]
        state.weeks = weeks
        state.month_spans = spans
        state.cells = cells
        state.saved_cells = dict(cells)
        state.employee_meta = emp_meta
        state.project_meta = proj_meta
        state.role_lookup = role_lookup
        state.absence_days = absence_map
        return state

    def test_employee_block(self) -> None:
        state = self._store()
        block = state.employee_blocks[0]
        expected_free = sum(max(g.value, 0.0) for g in block.gesamt[1:])
        assert block.planned_days == 2.0
        assert block.available_days == round(expected_free, 2)

    def test_project_block(self) -> None:
        block = self._store().project_blocks[0]
        assert block.planned_days == 2.0
        assert [(r.code, r.days) for r in block.role_totals] == [("DS", 2.0)]

    def test_summary_uses_week_of_last_populate(self) -> None:
        state = self._store()
        state.current_week = state.weeks[0].key
        assert state.current_week_key == state.weeks[0].key
        assert state.employee_blocks[0].planned_days == 6.0
        assert state.project_blocks[0].planned_days == 6.0
