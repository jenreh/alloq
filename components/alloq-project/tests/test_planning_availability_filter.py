"""Availability filtering uses the planning horizon and live remaining capacity."""

from datetime import date
from unittest.mock import patch

import pytest
from alloq_commons.models.employee import Absence, Employee
from alloq_project.services.planning_builders import (
    build_employee_meta,
    build_weeks,
    cell_key,
)
from alloq_project.states.planning_grid_state import PlanningStore


@pytest.fixture
def planning() -> PlanningStore:
    state = PlanningStore()
    with patch(
        "alloq_project.services.planning_builders.anchor_date",
        return_value=date(2026, 9, 28),
    ):
        state.weeks, state.month_spans = build_weeks(3)
    state.current_week = state.weeks[1].key
    state.available_employees = [
        Employee(id=1, first_name="Ada", role_ids=[1], internal_hours=0),
        Employee(id=2, first_name="Ben", role_ids=[2], internal_hours=0),
        Employee(id=3, first_name="Cora", role_ids=[1], internal_hours=0),
    ]
    state.employee_meta, state.absence_days = build_employee_meta(
        state.available_employees, state._week_keys()
    )
    state.employee_meta = [
        {**employee, "project_ids": ["proj-1"]} for employee in state.employee_meta
    ]
    state.project_meta = [
        {
            "id": "proj-1",
            "real_id": 1,
            "code": "A",
            "name": "Alpha",
            "color": "#000",
            "employee_ids": ["emp-1", "emp-2", "emp-3"],
        }
    ]
    state.cells = {
        cell_key(f"emp-{emp_id}", "A", week.key): days
        for emp_id, days in [(1, 3.0), (2, 5.0), (3, 6.0)]
        for week in state.weeks[1:]
    }
    state.saved_cells = dict(state.cells)
    return state


def test_disabled_by_default_and_can_be_switched_off(planning: PlanningStore) -> None:
    assert planning.available_only is False
    assert [employee.real_id for employee in planning.filtered_employees] == [1, 2, 3]
    planning.set_available_only(True)
    assert [employee.real_id for employee in planning.filtered_employees] == [1]
    planning.set_available_only(False)
    assert [employee.real_id for employee in planning.filtered_employees] == [1, 2, 3]


@pytest.mark.parametrize("view_mode", ["Grid", "Heatmap"])
def test_only_capacity_above_three_person_days(
    planning: PlanningStore, view_mode: str
) -> None:
    planning.view_mode = view_mode
    assert [employee.available_days for employee in planning.employee_blocks] == [
        4.0,
        0.0,
        0.0,
    ]
    planning.set_available_only(True)
    rows = planning.filtered_employees if view_mode == "Grid" else planning.employees
    assert [employee.real_id for employee in rows] == [1]
    if view_mode == "Heatmap":
        assert planning.avg_heat == rows[0].heat


@pytest.mark.parametrize("remaining_days", [0.0, 2.99, 3.0, 3.01, 4.0])
def test_three_person_days_is_a_strict_threshold(
    planning: PlanningStore, remaining_days: float
) -> None:
    planning.cells = {
        **planning.cells,
        cell_key("emp-1", "A", planning.weeks[1].key): 5.0 - remaining_days,
        cell_key("emp-1", "A", planning.weeks[2].key): 5.0,
    }
    planning.set_available_only(True)
    expected_ids = [1] if remaining_days > 3.0 else []
    actual_ids = [employee.real_id for employee in planning.filtered_employees]
    assert actual_ids == expected_ids


def test_intersects_existing_filters(planning: PlanningStore) -> None:
    planning.set_available_only(True)
    planning.role_filter = ["2"]
    assert planning.filtered_employees == []
    planning.role_filter = ["1"]
    assert [employee.real_id for employee in planning.filtered_employees] == [1]
    planning.employee_filter = ["2"]
    assert planning.filtered_employees == []
    planning.employee_filter = ["1"]
    planning.project_filter = ["99"]
    assert planning.filtered_employees == []
    planning.project_filter = ["1"]
    assert [employee.real_id for employee in planning.filtered_employees] == [1]


def test_reacts_to_unsaved_edits_without_losing_them(planning: PlanningStore) -> None:
    planning.set_available_only(True)
    assert [employee.real_id for employee in planning.filtered_employees] == [1]
    keys = [cell_key("emp-1", "A", week.key) for week in planning.weeks[1:]]
    changes = [{"key": key, "value": 5.0} for key in keys]
    planning.apply_cell_changes(changes)
    assert planning.filtered_employees == []
    assert len(planning.dirty_keys) == 2
    planning.set_available_only(False)
    assert len(planning.filtered_employees) == 3
    assert len(planning.dirty_keys) == 2
    assert all(planning.cells[key] == 5.0 for key in keys)


def test_reacts_to_timeframe_and_ignores_previous_week(
    planning: PlanningStore,
) -> None:
    planning.cells = {
        **planning.cells,
        cell_key("emp-2", "A", planning.weeks[2].key): 1.0,
    }
    planning.set_available_only(True)
    assert [employee.real_id for employee in planning.filtered_employees] == [1, 2]
    planning.weeks = planning.weeks[:2]
    assert planning.filtered_employees == []
    planning.weeks = planning.weeks[:1]
    assert planning.filtered_employees == []


@pytest.mark.parametrize("capacity_source", ["absence", "internal", "workload"])
def test_uses_net_capacity(planning: PlanningStore, capacity_source: str) -> None:
    if capacity_source == "absence":
        planning.absence_days = {"emp-1": [0.0, 1.0, 1.0]}
    else:
        planning.employee_meta = [
            {
                **employee,
                **(
                    {"internal_hours": 8.0}
                    if capacity_source == "internal"
                    else {"workload_percent": 80}
                ),
            }
            for employee in planning.employee_meta
        ]
    planning.set_available_only(True)
    assert planning.filtered_employees == []


def test_overbooked_weeks_do_not_cancel_available_capacity(
    planning: PlanningStore,
) -> None:
    planning.cells = {
        **planning.cells,
        cell_key("emp-1", "A", planning.weeks[1].key): 8.0,
        cell_key("emp-1", "A", planning.weeks[2].key): 1.0,
    }
    planning.set_available_only(True)
    assert [employee.real_id for employee in planning.filtered_employees] == [1]
    assert planning.filtered_employees[0].available_days == 4.0


def test_absence_view_uses_availability_filter(planning: PlanningStore) -> None:
    for employee in planning.available_employees:
        employee.absences = [
            Absence(start_date=date(2026, 10, 6), end_date=date(2026, 10, 6))
        ]
    planning.view_mode = "Abwesenheiten"
    assert len(planning.absence_gantt_rows) == 3
    planning.set_available_only(True)
    assert [row.real_id for row in planning.absence_gantt_rows] == [1]


def test_project_view_filters_resources_and_recomputes_totals(
    planning: PlanningStore,
) -> None:
    planning.view_mode = "Projekte"
    original = planning.project_blocks[0]
    assert len(planning.filtered_projects[0].employees) == 3
    planning.set_available_only(True)
    project = planning.filtered_projects[0]
    assert [employee.real_id for employee in project.employees] == [1]
    assert project.planned_days == 6.0
    assert project.gesamt[1].allocated == 3.0
    assert len(planning.project_blocks[0].employees) == 3
    assert original.planned_days == 28.0
    planning.employee_filter = ["2"]
    assert planning.filtered_projects == []


def test_project_view_hides_projects_without_available_resources(
    planning: PlanningStore,
) -> None:
    planning.view_mode = "Projekte"
    planning.project_meta = [
        {**planning.project_meta[0], "employee_ids": ["emp-2", "emp-3"]}
    ]
    planning.set_available_only(True)
    assert planning.filtered_projects == []
