"""Rendering checks for the planning grid."""

from alloq_project.components.planning_grid import (
    GESAMT_OVER_BG,
    _absence_row,
    _absence_value_cell,
    _employee_block,
    _employee_header_row,
    _gesamt_row,
    _gesamt_value_cell,
    _internal_row,
    _internal_value_cell,
)
from alloq_project.components.planning_project_view import (
    _project_block,
    _project_gesamt_row,
    _project_header_row,
)
from alloq_project.components.planning_shared import (
    BLOCK_GAP,
    MONTH_HEADER_BG,
    STICKY_BLOCK_HEADER,
    STICKY_LEFT_HEADER,
    STICKY_LEFT_HEADER_TOP,
    empty_grid_row,
    label_th,
    month_cell,
)
from alloq_project.states.planning_models import (
    EmployeeBlock,
    GesamtCell,
    GridCell,
    MonthSpan,
    ProjectBlock,
)
from reflex.vars import ObjectVar


def test_month_header_stays_behind_opaque_frozen_column() -> None:
    month = ObjectVar("month", MonthSpan)

    month_rendered = str(month_cell(month))
    label_rendered = str(label_th("Monat", accent=True))

    assert MONTH_HEADER_BG == (
        "light-dark(var(--mantine-color-blue-0), var(--mantine-color-blue-9))"
    )
    assert STICKY_LEFT_HEADER_TOP["backgroundColor"] == MONTH_HEADER_BG
    assert STICKY_LEFT_HEADER_TOP["zIndex"] == "50"
    assert STICKY_LEFT_HEADER["zIndex"] == "50"
    assert f'["backgroundColor"] : "{MONTH_HEADER_BG}"' in month_rendered
    assert f'["backgroundColor"] : "{MONTH_HEADER_BG}"' in label_rendered
    assert '["position"] : "relative"' in month_rendered
    assert '["zIndex"] : "0"' in month_rendered


def test_employee_and_project_headers_stick_below_the_three_row_table_header() -> None:
    assert STICKY_BLOCK_HEADER == {
        "position": "sticky",
        "top": "90px",
        "zIndex": "20",
    }
    employee_header = str(_employee_header_row(ObjectVar("emp", EmployeeBlock)))
    project_header = str(_project_header_row(ObjectVar("proj", ProjectBlock)))

    assert '["top"] : "90px"' in employee_header
    assert '["top"] : "90px"' in project_header


def test_employee_header_formats_name_last_name_first() -> None:
    rendered = str(_employee_header_row(ObjectVar("emp", EmployeeBlock)))

    assert (
        rendered.index('["last_name"]')
        < rendered.index('", "')
        < rendered.index('["first_name"]')
    )


def test_employee_header_pins_stats_to_the_right_edge() -> None:
    rendered = str(_employee_header_row(ObjectVar("emp", EmployeeBlock)))
    stats = rendered[rendered.index('["right"] : "0"') :]

    assert '["marginLeft"] : "auto"' in stats
    assert "Geplant" in stats
    assert "Frei" in stats
    assert "Projekt zuweisen" not in stats


def test_empty_grid_row_is_a_small_gap_without_cells() -> None:
    row = empty_grid_row()

    assert row.children == []
    assert BLOCK_GAP == "var(--aq-grid-gap, 8px)"
    assert f'["height"] : "{BLOCK_GAP}"' in str(row)


def test_employee_block_renders_gap_after_gesamt() -> None:
    rendered = str(_employee_block(ObjectVar("emp", EmployeeBlock)))

    assert rendered.index("Gesamt (frei)") < rendered.index(f'"{BLOCK_GAP}"')


def test_project_block_renders_gap_after_gesamt() -> None:
    rendered = str(_project_block(ObjectVar("proj", ProjectBlock)))

    assert rendered.index("Gesamt (allokiert)") < rendered.index(f'"{BLOCK_GAP}"')


def test_team_and_project_gesamt_labels_use_the_same_font_size() -> None:
    employee = ObjectVar("emp", EmployeeBlock)
    project = ObjectVar("proj", ProjectBlock)

    assert 'size:"12px"' in str(_gesamt_row(employee))
    assert 'size:"12px"' in str(_project_gesamt_row(project))


def test_absence_and_internal_values_use_muted_plain_text() -> None:
    cell = ObjectVar("cell", GridCell)

    for render_cell in (_absence_value_cell, _internal_value_cell):
        rendered = str(render_cell(cell))

        assert '["color"] : "var(--alloq-text-muted)"' in rendered
        assert "MantineBadge" not in rendered
        assert "mantine-color-" not in rendered
        assert "borderRadius" not in rendered
        assert 'size:"xs"' in rendered


def test_absence_and_internal_labels_match_header_subtitle_style() -> None:
    employee = ObjectVar("emp", EmployeeBlock)

    for render_row in (_absence_row, _internal_row):
        rendered = str(render_row(employee))

        assert 'size:"xs"' in rendered
        assert 'c:"var(--alloq-text-muted)"' in rendered


def test_gesamt_values_tint_only_overbooked_cells() -> None:
    cell = ObjectVar("cell", GesamtCell)

    rendered = str(_gesamt_value_cell(cell))

    assert '["color"] :' in rendered
    assert GESAMT_OVER_BG in rendered
    assert "var(--mantine-color-red-7)" in rendered
    assert "var(--mantine-color-green-7)" in rendered
    assert '["fontSize"] : "11px"' not in rendered
