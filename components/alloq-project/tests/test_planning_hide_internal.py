"""The planning grid can hide internal projects and the absence rows."""

from datetime import date
from unittest.mock import patch

import pytest
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_project.components.planning_filter_row import planning_filter_row
from alloq_project.components.planning_grid import _employee_block
from alloq_project.services.planning_builders import (
    build_employee_meta,
    build_project_meta,
    build_weeks,
    cell_key,
)
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import EmployeeBlock
from reflex.vars import ObjectVar


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
    ]
    state.employee_meta, state.absence_days = build_employee_meta(
        state.available_employees, state._week_keys()
    )
    state.employee_meta = [
        {**employee, "project_ids": ["proj-1", "proj-2"]}
        for employee in state.employee_meta
    ]
    meta, _ = build_project_meta(
        [
            Project(id=1, code="A", name_de="Alpha"),
            Project(id=2, code="I", name_de="Intern", is_internal=True),
        ]
    )
    state.project_meta = [{**project, "employee_ids": ["emp-1"]} for project in meta]
    state.cells = {
        cell_key("emp-1", code, week.key): 1.0
        for code in ("A", "I")
        for week in state.weeks
    }
    state.saved_cells = dict(state.cells)
    return state


def test_project_meta_carries_internal_flag() -> None:
    meta, _ = build_project_meta(
        [Project(id=1, code="A"), Project(id=2, code="I", is_internal=True)]
    )
    assert [project["is_internal"] for project in meta] == [False, True]


def test_disabled_by_default_and_can_be_switched_off(planning: PlanningStore) -> None:
    assert planning.hide_internal is False
    assert [p.code for p in planning.filtered_employees[0].projects] == ["A", "I"]
    planning.set_hide_internal(True)
    assert [p.code for p in planning.filtered_employees[0].projects] == ["A"]
    planning.set_hide_internal(False)
    assert [p.code for p in planning.filtered_employees[0].projects] == ["A", "I"]


def test_hiding_keeps_totals_of_internal_work(planning: PlanningStore) -> None:
    before = planning.filtered_employees[0]
    planning.set_hide_internal(True)
    after = planning.filtered_employees[0]
    assert after.gesamt == before.gesamt
    assert after.planned_days == before.planned_days
    assert [p.code for p in planning.employee_blocks[0].projects] == ["A", "I"]


def test_hides_internal_project_blocks_in_project_view(
    planning: PlanningStore,
) -> None:
    planning.view_mode = "Projekte"
    assert [p.code for p in planning.filtered_projects] == ["A", "I"]
    planning.set_hide_internal(True)
    assert [p.code for p in planning.filtered_projects] == ["A"]


def test_employee_block_hides_internal_and_absence_rows() -> None:
    rendered = str(_employee_block(ObjectVar("emp", EmployeeBlock)))
    assert "hide_internal" in rendered
    assert rendered.index("hide_internal") < rendered.index('"Interne Projekte"')
    assert rendered.index("hide_internal") < rendered.index('"Abwesenheit"')


def test_filter_row_has_hide_internal_switch() -> None:
    rendered = str(planning_filter_row())
    assert '"Interne & Abwesenheit ausblenden"' in rendered
    assert "set_hide_internal" in rendered
