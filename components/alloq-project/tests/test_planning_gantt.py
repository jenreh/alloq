"""Absence timelines preserve inclusive dates, clipping, lanes and filters."""

from datetime import date
from unittest.mock import patch

import pytest
from alloq_commons.models.employee import Absence, Employee
from alloq_project.services.planning_builders import build_employee_meta, build_weeks
from alloq_project.services.planning_gantt import build_absence_gantt
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import AbsenceGanttRow


@pytest.fixture
def planning() -> PlanningStore:
    state = PlanningStore()
    with patch(
        "alloq_project.services.planning_builders.anchor_date",
        return_value=date(2026, 9, 28),
    ):
        state.weeks, state.month_spans = build_weeks(2)
    state.available_employees = [
        Employee(
            id=1,
            first_name="Ada",
            last_name="A",
            role_ids=[1],
            absences=[
                Absence(start_date=date(2026, 9, 30), end_date=date(2026, 9, 30))
            ],
        ),
        Employee(
            id=2,
            first_name="Ben",
            last_name="B",
            role_ids=[2],
            absences=[
                Absence(start_date=date(2026, 10, 6), end_date=date(2026, 10, 8))
            ],
        ),
    ]
    state.employee_meta, state.absence_days = build_employee_meta(
        state.available_employees, state._week_keys()
    )
    state.view_mode = "Abwesenheiten"
    return state


def _rows(planning: PlanningStore) -> list[AbsenceGanttRow]:
    return build_absence_gantt(
        planning.employee_blocks, planning.available_employees, planning.weeks
    )


def test_single_day_and_inclusive_end(planning: PlanningStore) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 9, 29), end_date=date(2026, 9, 29)),
        Absence(start_date=date(2026, 10, 1), end_date=date(2026, 10, 3)),
    ]
    bars = _rows(planning)[0].bars
    assert bars[0].left_px == pytest.approx(60 / 7)
    assert bars[0].width_px == pytest.approx(60 / 7)
    assert bars[1].left_px == pytest.approx(180 / 7)
    assert bars[1].width_px == pytest.approx(180 / 7)
    assert "29.09.2026" in bars[0].tooltip
    assert "1 Kalendertag" in bars[0].tooltip
    assert bars[0].tooltip.splitlines() == [
        "Ada A",
        "29.09.2026 - 29.09.2026",
        "1 Kalendertag",
    ]
    assert bars[1].tooltip.splitlines()[-1] == "3 Kalendertage"


def test_clips_to_horizon_and_ignores_invalid_or_outside_periods(
    planning: PlanningStore,
) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 9, 20), end_date=date(2026, 9, 28)),
        Absence(start_date=date(2026, 10, 11), end_date=date(2026, 10, 20)),
        Absence(start_date=date(2026, 9, 1), end_date=date(2026, 9, 27)),
        Absence(start_date=date(2026, 10, 12), end_date=date(2026, 10, 14)),
        Absence(start_date=None, end_date=date(2026, 10, 1)),
        Absence(start_date=date(2026, 10, 3), end_date=date(2026, 10, 1)),
    ]
    bars = _rows(planning)[0].bars
    assert len(bars) == 2
    assert bars[0].left_px == 0
    assert bars[0].width_px == pytest.approx(60 / 7)
    assert "20.09.2026" in bars[0].tooltip
    assert bars[1].left_px + bars[1].width_px == pytest.approx(120)


def test_overlapping_periods_use_lanes_but_adjacent_periods_reuse_them(
    planning: PlanningStore,
) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 9, 28), end_date=date(2026, 10, 3)),
        Absence(start_date=date(2026, 9, 29), end_date=date(2026, 10, 1)),
        Absence(start_date=date(2026, 10, 4), end_date=date(2026, 10, 5)),
    ]
    row = _rows(planning)[0]
    assert [bar.lane for bar in row.bars] == [0, 1, 0]
    assert row.height_px >= 72


def test_omits_resources_without_overlapping_absences_and_handles_empty_horizon(
    planning: PlanningStore,
) -> None:
    planning.available_employees[0].absences = []
    assert [row.name for row in _rows(planning)] == ["Ben B"]
    planning.available_employees[1].absences = [
        Absence(start_date=date(2026, 10, 12), end_date=date(2026, 10, 14))
    ]
    assert _rows(planning) == []
    assert build_absence_gantt([], [], []) == []


def test_changing_timeframe_removes_resources_without_visible_absences(
    planning: PlanningStore,
) -> None:
    assert [row.real_id for row in planning.absence_gantt_rows] == [1, 2]
    planning.weeks = planning.weeks[:1]
    assert [row.real_id for row in planning.absence_gantt_rows] == [1]


def test_gantt_uses_shared_filters_and_reacts_to_absence_changes(
    planning: PlanningStore,
) -> None:
    assert [row.real_id for row in planning.absence_gantt_rows] == [1, 2]
    planning.employee_filter = ["2"]
    assert [row.real_id for row in planning.absence_gantt_rows] == [2]
    planning.available_employees[1].absences = [
        Absence(start_date=date(2026, 10, 1), end_date=date(2026, 10, 2))
    ]
    assert len(planning.absence_gantt_rows[0].bars) == 1
    planning.employee_filter = []
    planning.role_filter = ["1"]
    assert [row.real_id for row in planning.absence_gantt_rows] == [1]
    planning.view_mode = "Grid"
    assert planning.absence_gantt_rows == []
