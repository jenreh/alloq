"""Absence timelines: inclusive dates, clipping, lanes, coverage and summaries."""

from datetime import date
from unittest.mock import patch

import pytest
from alloq_commons.models.department import Department
from alloq_commons.models.employee import Absence, Employee
from alloq_commons.role_colors import AVATAR_FALLBACK_COLOR, role_avatar_color
from alloq_project.services.planning_builders import build_employee_meta, build_weeks
from alloq_project.services.planning_gantt import build_absence_gantt
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import (
    AbsenceGanttView,
)

DAY = 60 / 7


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
            key_role_id=1,
            role_ids=[1],
            absences=[
                Absence(id=11, start_date=date(2026, 9, 30), end_date=date(2026, 9, 30))
            ],
        ),
        Employee(
            id=2,
            first_name="Ben",
            last_name="B",
            role_ids=[2],
            absences=[
                Absence(id=21, start_date=date(2026, 10, 6), end_date=date(2026, 10, 8))
            ],
        ),
    ]
    state.employee_meta, state.absence_days = build_employee_meta(
        state.available_employees, state._week_keys()
    )
    state.view_mode = "Abwesenheiten"
    return state


def _view(
    planning: PlanningStore,
    *,
    holidays: set[date] | None = None,
    today: date = date(2026, 9, 29),
    show_all: bool = False,
) -> AbsenceGanttView:
    return build_absence_gantt(
        planning.employee_blocks,
        planning.available_employees,
        planning.weeks,
        holidays=holidays,
        today=today,
        show_all=show_all,
    )


def _add_cleo(planning: PlanningStore) -> None:
    planning.available_employees = [
        *planning.available_employees,
        Employee(id=3, first_name="Cleo", last_name="C", role_ids=[1]),
    ]
    planning.employee_meta, planning.absence_days = build_employee_meta(
        planning.available_employees, planning._week_keys()
    )


def test_single_day_and_inclusive_end(planning: PlanningStore) -> None:
    planning.available_employees[0].absences = [
        Absence(id=1, start_date=date(2026, 9, 29), end_date=date(2026, 9, 29)),
        Absence(id=2, start_date=date(2026, 10, 1), end_date=date(2026, 10, 3)),
    ]
    bars = _view(planning).rows[0].bars
    assert bars[0].left_px == pytest.approx(DAY)
    assert bars[0].width_px == pytest.approx(DAY)
    assert bars[1].left_px == pytest.approx(3 * DAY)
    assert bars[1].width_px == pytest.approx(3 * DAY)
    assert bars[0].absence_id == 1
    assert bars[0].period == "Di 29.09.2026"
    assert (bars[0].work_days, bars[0].calendar_days) == (1, 1)
    assert bars[0].side_label == "29.09. · 1 AT"
    assert bars[1].label == "01.–03.10."
    assert (bars[1].work_days, bars[1].calendar_days) == (2, 3)
    assert bars[1].period == "Do 01.10.2026 – Sa 03.10.2026"
    assert "Ada A" in bars[1].aria_label


def test_wide_bars_carry_their_label_inside(planning: PlanningStore) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 9, 28), end_date=date(2026, 10, 7)),
    ]
    bar = _view(planning).rows[0].bars[0]
    assert bar.inside
    assert bar.label == "28.09.–07.10."
    assert bar.side_label == ""


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
    bars = _view(planning).rows[0].bars
    assert len(bars) == 2
    assert bars[0].left_px == 0
    assert bars[0].width_px == pytest.approx(DAY)
    assert bars[0].clipped
    assert bars[0].side_label.startswith("seit 20.09.")
    assert bars[1].left_px + bars[1].width_px == pytest.approx(120)
    assert not bars[1].clipped


def test_overlapping_periods_use_lanes_but_adjacent_periods_reuse_them(
    planning: PlanningStore,
) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 9, 28), end_date=date(2026, 10, 3)),
        Absence(start_date=date(2026, 9, 29), end_date=date(2026, 10, 1)),
        Absence(start_date=date(2026, 10, 4), end_date=date(2026, 10, 5)),
    ]
    row = _view(planning).rows[0]
    assert [bar.lane for bar in row.bars] == [0, 1, 0]
    assert row.height_px > _view(planning).rows[1].height_px


def test_rows_without_absences_only_with_show_all(planning: PlanningStore) -> None:
    planning.available_employees[0].absences = []
    assert [row.name for row in _view(planning).rows] == ["Ben B"]
    assert [row.name for row in _view(planning, show_all=True).rows] == [
        "Ada A",
        "Ben B",
    ]
    planning.available_employees[1].absences = [
        Absence(start_date=date(2026, 10, 12), end_date=date(2026, 10, 14))
    ]
    assert _view(planning).rows == []
    empty = build_absence_gantt([], [], [])
    assert empty.rows == []
    assert empty.weeks == []


def test_holidays_are_marked_and_not_counted(planning: PlanningStore) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 10, 1), end_date=date(2026, 10, 3)),
    ]
    view = _view(planning, holidays={date(2026, 10, 1), date(2026, 10, 3)})
    bar = view.rows[0].bars[0]
    assert bar.work_days == 1
    assert bar.holidays_note == "1 Feiertag nicht gezählt (01.10.)"
    assert [mark.left_px for mark in view.holidays] == [pytest.approx(3 * DAY)]
    assert [week.has_holiday for week in view.weeks] == [True, False]
    assert view.holiday_days == [3]


def test_week_header_marks_kw_and_current_week(planning: PlanningStore) -> None:
    view = _view(planning, today=date(2026, 10, 7))
    assert [week.kw for week in view.weeks] == [40, 41]
    assert [week.is_current for week in view.weeks] == [False, True]
    assert view.today_px == pytest.approx(9.5 * DAY)
    assert view.min_day == 9
    assert view.horizon_start == "2026-09-28"
    assert view.width_px == 120
    assert _view(planning, today=date(2026, 12, 1)).today_px == -1


def test_coverage_counts_lowest_presence_per_week(planning: PlanningStore) -> None:
    _add_cleo(planning)
    view = _view(planning)
    assert [cell.label for cell in view.coverage] == ["2/3", "2/3"]
    assert [cell.level for cell in view.coverage] == ["warn", "warn"]
    assert "Ada A" in view.coverage[0].title
    planning.available_employees[1].absences = [
        Absence(start_date=date(2026, 9, 30), end_date=date(2026, 9, 30))
    ]
    view = _view(planning)
    assert [cell.level for cell in view.coverage] == ["neg", "ok"]
    assert view.coverage[1].label == "3/3"
    assert view.bottleneck_label == "1 Engpass · KW 40"
    assert "Ben B" in view.rows[0].bars[0].overlap_note
    assert "KW 40" in view.rows[0].bars[0].overlap_note


def test_coverage_ignores_weekends_and_holidays(planning: PlanningStore) -> None:
    planning.available_employees[0].absences = [
        Absence(start_date=date(2026, 10, 3), end_date=date(2026, 10, 4)),
    ]
    planning.available_employees[1].absences = [
        Absence(start_date=date(2026, 10, 6), end_date=date(2026, 10, 6)),
    ]
    view = _view(planning, holidays={date(2026, 10, 6)})
    assert [cell.level for cell in view.coverage] == ["ok", "ok"]
    assert view.bottleneck_label == ""


def test_row_totals_and_next_absence(planning: PlanningStore) -> None:
    view = _view(planning)
    assert [row.total_days for row in view.rows] == [1, 3]
    assert [row.next_label for row in view.rows] == ["ab 30.09.", "ab 06.10."]
    later = _view(planning, today=date(2026, 10, 7))
    assert later.rows[0].next_label == ""
    assert later.rows[1].next_label == "bis 08.10."


def test_state_view_uses_shared_filters_and_reacts_to_changes(
    planning: PlanningStore,
) -> None:
    assert [row.real_id for row in planning.absence_gantt.rows] == [1, 2]
    planning.employee_filter = ["2"]
    assert [row.real_id for row in planning.absence_gantt.rows] == [2]
    planning.available_employees[1].absences = [
        Absence(start_date=date(2026, 10, 1), end_date=date(2026, 10, 2))
    ]
    assert len(planning.absence_gantt.rows[0].bars) == 1
    planning.employee_filter = []
    planning.role_filter = ["1"]
    assert [row.real_id for row in planning.absence_gantt.rows] == [1]
    planning.view_mode = "Grid"
    assert planning.absence_gantt.rows == []


def test_state_view_ignores_project_and_availability_filters(
    planning: PlanningStore,
) -> None:
    planning.project_filter = ["99"]
    planning.available_only = True
    assert [row.real_id for row in planning.absence_gantt.rows] == [1, 2]


def test_avatars_use_key_role_color(planning: PlanningStore) -> None:
    view = _view(planning)
    assert view.rows[0].avatar_color == role_avatar_color(1)
    assert view.rows[1].avatar_color == AVATAR_FALLBACK_COLOR


def test_changing_timeframe_and_show_all(planning: PlanningStore) -> None:
    planning.weeks = planning.weeks[:1]
    assert [row.real_id for row in planning.absence_gantt.rows] == [1]
    planning.set_absence_show_all(True)
    assert [row.real_id for row in planning.absence_gantt.rows] == [1, 2]


def test_employee_meta_retains_department_highlight_for_grid_grouping() -> None:
    employees = [
        Employee(
            id=1,
            first_name="Ada",
            last_name="A",
            department=Department(id=4, name="IT", abbreviation="IT", highlighted=True),
        ),
        Employee(id=2, first_name="Ben", last_name="B"),
    ]
    meta, _ = build_employee_meta(employees, ["2026_10_19"])

    assert [employee["department_highlighted"] for employee in meta] == [True, False]


def test_unhighlighted_department_compartment_can_collapse_and_expand() -> None:
    planning = PlanningStore()
    planning.employee_meta = [
        {"id": "emp-1", "department_highlighted": True},
        {"id": "emp-2", "department_highlighted": False},
        {"id": "emp-3", "department_highlighted": False},
    ]

    planning.toggle_all_sections()
    assert planning.collapsed_employees == ["emp-1", "emp-2", "emp-3"]
    assert planning.unhighlighted_collapsed is False

    planning.toggle_all_sections()
    assert planning.collapsed_employees == []

    planning.toggle_unhighlighted()
    assert planning.collapsed_employees == []
    assert planning.unhighlighted_collapsed is True

    planning.toggle_unhighlighted()
    assert planning.collapsed_employees == []
    assert planning.unhighlighted_collapsed is False


def test_weeks_mark_month_starts(planning: PlanningStore) -> None:
    view = _view(planning)
    assert [week.is_month_start for week in view.weeks] == [False, True]
    assert view.month_lines == [60]
