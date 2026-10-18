"""Legend footer of the planning views (team, absences, projects)."""

import json

from alloq_project.components.planning_gantt import planning_gantt
from alloq_project.components.planning_grid import (
    ABSENCE_HATCH,
    GESAMT_OVER_BG,
    OVERBOOKED_LABEL,
    planning_grid,
)
from alloq_project.components.planning_project_view import planning_project_view
from alloq_project.components.planning_shared import (
    CURRENT_WEEK_BG,
    EDIT_HINT,
    HOLIDAY_BG,
    MONTH_START_BORDER,
    legend_footer,
    legend_item,
)

import appkit_mantine as mn


def _js(text: str) -> str:
    """Text as the compiled component spells it (non-ASCII escaped)."""
    return json.dumps(text)[1:-1]


COMMON_LABELS = ("Aktuelle Woche", "Feiertag", "Ungespeichert")


def test_legend_item_renders_swatch_dict_and_label() -> None:
    rendered = str(legend_item({"backgroundColor": "red"}, "Rot"))

    assert '["backgroundColor"] : "red"' in rendered
    assert "Rot" in rendered


def test_legend_item_accepts_a_component_as_sample() -> None:
    rendered = str(legend_item(mn.text("1,00"), "Wert"))

    assert "1,00" in rendered
    assert "Wert" in rendered


def test_legend_footer_has_top_border_and_hint() -> None:
    rendered = str(legend_footer(legend_item({}, "A"), hint="Tipp"))

    assert '["borderTop"] : "1px solid var(--aq-separator)"' in rendered
    assert "Tipp" in rendered


def test_team_view_legend_explains_cell_styles() -> None:
    rendered = str(planning_grid())

    for label in (*COMMON_LABELS, "Wie Vorwoche", "Abwesenheit"):
        assert label in rendered
    for style in (CURRENT_WEEK_BG, GESAMT_OVER_BG, ABSENCE_HATCH):
        assert style in rendered
    assert HOLIDAY_BG in rendered
    assert MONTH_START_BORDER in rendered
    assert _js(OVERBOOKED_LABEL) in rendered
    assert _js(EDIT_HINT) in rendered


def test_project_view_legend_explains_cell_styles() -> None:
    rendered = str(planning_project_view())

    for label in (*COMMON_LABELS, "Wie Vorwoche"):
        assert label in rendered
    assert _js(OVERBOOKED_LABEL) not in rendered
    assert _js(EDIT_HINT) in rendered


def test_absence_view_keeps_its_legend() -> None:
    rendered = str(planning_gantt())

    for label in ("Neu (ziehen)", "Feiertag", "Wochenende", "Heute"):
        assert label in rendered
    assert HOLIDAY_BG in rendered
    assert "135deg" not in rendered
