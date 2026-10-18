"""Readability helpers of the planning grid: repeats, defaults, Gesamt states."""

import datetime as dt

from alloq_project.components.planning_grid import (
    ABSENCE_HATCH,
    _absence_value_cell,
    _employee_header_row,
    _gesamt_value_cell,
    _internal_row,
)
from alloq_project.components.planning_shared import (
    HOLIDAY_IMAGE,
    editable_value_cell,
)
from alloq_project.services.planning_builders import (
    MINUS,
    anchor_date,
    build_weeks,
    compute_gesamt,
    gesamt_state,
    mark_defaults,
    mark_repeats,
    week_title,
)
from alloq_project.states.planning_display_mixin import (
    COMPACT,
    NORMAL,
    PlanningDisplayState,
    holiday_bands,
)
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.planning_models import (
    COMPACT_WEEK_COL_PX,
    LABEL_COL_PX,
    WEEK_COL_PX,
    AbsenceRow,
    EmployeeBlock,
    GesamtCell,
    GridCell,
    ProjectAllocationRow,
    WeekColumn,
)
from reflex.vars import ObjectVar


def _cells(values: list[float]) -> list[GridCell]:
    return [GridCell(week_key=f"w{i}", value=v) for i, v in enumerate(values)]


def _week(key: str, work_days: float = 5.0) -> WeekColumn:
    return WeekColumn(key=key, label=key, month_label="Okt 26", work_days=work_days)


# === build_weeks ===


def test_build_weeks_marks_first_week_of_each_new_month() -> None:
    weeks, _ = build_weeks(13)

    expected = [
        i > 0 and weeks[i].month_label != weeks[i - 1].month_label
        for i in range(len(weeks))
    ]
    assert [w.is_month_start for w in weeks] == expected
    assert any(expected)
    assert weeks[0].is_month_start is False


def test_build_weeks_marks_weeks_shortened_by_holidays() -> None:
    holiday = anchor_date() + dt.timedelta(days=2)

    weeks, _ = build_weeks(2, {holiday})

    assert weeks[0].work_days == 4.0
    assert weeks[0].is_short is True
    assert weeks[1].is_short is False
    assert weeks[0].title == week_title(weeks[0].week_no, anchor_date(), [holiday])
    assert "Feiertag" not in weeks[1].title
    assert weeks[0].holiday_days == [2]
    assert weeks[1].holiday_days == []


def test_week_title_names_start_day_and_holidays() -> None:
    monday = dt.date(2026, 12, 21)

    assert week_title(52, monday, []) == "KW 52 · ab Mo 21.12.2026"
    assert week_title(52, monday, [dt.date(2026, 12, 24), dt.date(2026, 12, 25)]) == (
        "KW 52 · ab Mo 21.12.2026 · Feiertag 24.12., 25.12."
    )


# === mark_repeats / mark_defaults ===


def test_mark_repeats_flags_values_equal_to_the_previous_week() -> None:
    cells = mark_repeats(_cells([5.0, 5.0, 5.0, 2.0, 2.0, 0.0, 0.0, 5.0]))

    assert [c.is_repeat for c in cells] == [
        False,
        True,
        True,
        False,
        True,
        False,
        False,
        False,
    ]


def test_mark_repeats_ignores_float_noise() -> None:
    cells = mark_repeats(_cells([0.1 + 0.2, 0.3]))

    assert cells[1].is_repeat is True


def test_mark_defaults_flags_cells_with_the_usual_value() -> None:
    cells = mark_defaults(_cells([0.5, 0.5, 0.0, 0.5]), 0.5)

    assert [c.is_default for c in cells] == [True, True, False, True]


# === Gesamt ===


def test_gesamt_state_has_three_visual_states() -> None:
    assert gesamt_state(-0.01) == "over"
    assert gesamt_state(5.0 - 4.5 - 0.5) == "zero"
    assert gesamt_state(0.5) == "free"


def test_compute_gesamt_keeps_overbooking_visible_in_absence_weeks() -> None:
    weeks = [_week("w0"), _week("w1", work_days=3.0)]
    block = EmployeeBlock(
        id="e1",
        name="Bert",
        initials="B",
        role="DS",
        role_color="",
        projects=[
            ProjectAllocationRow(
                project_id="1",
                code="P1",
                name="P1",
                color="",
                cells=_cells([10.0, 0.0]),
            )
        ],
        absence=AbsenceRow(cells=_cells([1.0, 0.0])),
        internal=AbsenceRow(cells=_cells([0.5, 0.5])),
    )

    first, second = compute_gesamt(weeks, block)

    assert first.value == -6.5
    assert first.state == "over"
    assert first.has_absence is True
    assert first.breakdown == (
        f"Arbeitstage 5,00 {MINUS} Projekte 10,00 {MINUS} Intern 0,50"
        f" {MINUS} Abwesenheit 1,00 = {MINUS}6,50 PT frei"
    )
    assert second.state == "free"
    assert second.has_absence is False


# === Density mixin ===


def test_density_toggles_between_normal_and_compact() -> None:
    state = PlanningStore()

    assert state.grid_density == NORMAL
    state.toggle_grid_density()
    assert state.grid_density == COMPACT
    state.toggle_grid_density()
    assert state.grid_density == NORMAL


def test_compact_density_narrows_week_columns() -> None:
    state = PlanningStore()
    state.weeks = [_week("w0"), _week("w1")]

    assert state.grid_template_columns == f"{LABEL_COL_PX}px repeat(2, {WEEK_COL_PX}px)"
    assert state.table_width == f"{LABEL_COL_PX + 2 * WEEK_COL_PX}px"

    state.grid_density = COMPACT

    assert state.is_compact is True
    assert state.grid_template_columns == (
        f"{LABEL_COL_PX}px repeat(2, {COMPACT_WEEK_COL_PX}px)"
    )
    assert state.table_width == f"{LABEL_COL_PX + 2 * COMPACT_WEEK_COL_PX}px"


def test_month_start_keys_list_the_first_week_of_new_months() -> None:
    state = PlanningStore()
    state.weeks = [
        _week("a"),
        WeekColumn(
            key="b", label="b", month_label="Nov 26", work_days=5, is_month_start=True
        ),
    ]

    assert state.month_start_keys == ["b"]


def test_holiday_bands_draw_one_plain_band_per_day() -> None:
    assert holiday_bands([3]) == (
        "linear-gradient(to right, transparent 42.8571%, "
        "var(--aq-holiday) 42.8571% 57.1429%, transparent 57.1429%)"
    )
    assert holiday_bands([3, 4]).count("linear-gradient") == 2
    assert holiday_bands([]) == ""


def test_holiday_backgrounds_cover_only_weeks_with_holidays() -> None:
    state = PlanningStore()
    state.weeks = [
        _week("a"),
        WeekColumn(
            key="b", label="b", month_label="Dez 26", work_days=3, holiday_days=[3, 4]
        ),
    ]

    assert state.holiday_backgrounds == {"b": holiday_bands([3, 4])}


def test_display_mixin_is_mixed_into_the_store() -> None:
    assert issubclass(PlanningStore, PlanningDisplayState)


# === Rendering ===


def test_repeated_values_render_muted() -> None:
    rendered = str(editable_value_cell(ObjectVar("cell", GridCell)))

    assert '["is_repeat"]' in rendered
    assert "var(--alloq-text-muted)" in rendered
    assert '["justifyContent"] : "flex-end"' in rendered


def test_week_cells_draw_holidays_as_their_background() -> None:
    for rendered in (
        str(editable_value_cell(ObjectVar("cell", GridCell))),
        str(_gesamt_value_cell(ObjectVar("cell", GesamtCell))),
    ):
        assert "holiday_backgrounds" in rendered
        assert '["--aq-holidays"]' in rendered
        assert f'["backgroundImage"] : "{HOLIDAY_IMAGE}"' in rendered


def test_absence_cell_keeps_its_hatch_above_the_holidays() -> None:
    rendered = str(_absence_value_cell(ObjectVar("cell", GridCell)))

    assert f"{ABSENCE_HATCH}, {HOLIDAY_IMAGE}" in rendered


def test_gesamt_cell_tints_overbooking_and_never_uses_blue() -> None:
    rendered = str(_gesamt_value_cell(ObjectVar("cell", GesamtCell)))

    assert '"over"' in rendered
    assert "red" in rendered
    assert "blue" not in rendered
    assert '["breakdown"]' in rendered
    assert '["has_absence"]' in rendered


def test_internal_row_hides_the_usual_value() -> None:
    rendered = str(_internal_row(ObjectVar("emp", EmployeeBlock)))

    assert '["is_default"]' in rendered
    assert '["internal_days"]' in rendered


def test_collapsed_employee_header_shows_gesamt_cells() -> None:
    rendered = str(_employee_header_row(ObjectVar("emp", EmployeeBlock)))

    assert '["gesamt"]' in rendered
    assert "collapsed_employees" in rendered
    assert "Überbucht" not in rendered
