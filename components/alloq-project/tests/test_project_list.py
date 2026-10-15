"""Project list: filter, grouping, inspector selection and rendering."""

import json

import reflex as rx
from alloq_commons.models.project import Project, RequiredCapacity
from alloq_project.components.project_inspector import project_inspector
from alloq_project.components.project_table import (
    COLUMNS,
    project_list,
    project_table,
)
from alloq_project.components.project_toolbar import project_filter, project_toolbar
from alloq_project.states.project_list_state import FILTERS, status_tone
from alloq_project.states.project_state import ProjectState


def _state() -> ProjectState:
    state = ProjectState()
    state.current_employee_id = 7
    state.projects = [
        Project(
            id=1,
            code="A",
            name_de="Alpha",
            state="Aktiv",
            owner_ids=[7],
            required_capacities=[RequiredCapacity(role_id=1, person_days=10)],
        ),
        Project(
            id=2,
            code="B",
            name_de="Beta",
            state="Geplant",
            owner_ids=[7],
            required_capacities=[RequiredCapacity(role_id=1, person_days=20)],
        ),
        Project(
            id=3,
            code="C",
            name_de="Gamma",
            state="Risiko",
            required_capacities=[RequiredCapacity(role_id=1, person_days=30)],
        ),
        Project(
            id=4,
            code="D",
            name_de="Delta",
            state="Aktiv",
            required_capacities=[RequiredCapacity(role_id=1, person_days=40)],
        ),
    ]
    return state


def _ids(projects: list[Project]) -> list[int]:
    return [p.id for p in projects]


class TestFilter:
    def test_all_groups_own_and_other_projects(self) -> None:
        state = _state()
        assert _ids(state.mine_rows) == [1, 2]
        assert _ids(state.other_rows) == [4, 3]
        assert state.row_count == 4

    def test_mine_hides_other_projects(self) -> None:
        state = _state()
        state.set_list_filter("Meine")
        assert _ids(state.mine_rows) == [1, 2]
        assert state.other_rows == []

    def test_state_filter_applies_to_both_groups(self) -> None:
        state = _state()
        state.set_list_filter("Aktiv")
        assert _ids(state.mine_rows) == [1]
        assert _ids(state.other_rows) == [4]

    def test_unknown_filter_falls_back_to_all(self) -> None:
        state = _state()
        state.set_list_filter("Kanban")
        assert state.list_filter == "Alle"
        assert FILTERS[0] == "Alle"

    def test_visible_total_pt_sums_only_visible_projects(self) -> None:
        state = _state()
        assert state.visible_total_pt == 100

        state.set_list_filter("Aktiv")
        assert state.visible_total_pt == 50

        state.set_list_filter("Meine")
        assert state.visible_total_pt == 30


class TestInspector:
    def test_defaults_to_first_row(self) -> None:
        state = _state()
        assert state.inspected is not None
        assert state.inspected.id == 1

    def test_follows_selection(self) -> None:
        state = _state()
        state.inspect(3)
        assert state.inspected is not None
        assert state.inspected.id == 3
        assert state.inspected_tone == "negative"

    def test_selection_outside_filter_falls_back(self) -> None:
        state = _state()
        state.inspect(3)
        state.set_list_filter("Geplant")
        assert state.inspected is not None
        assert state.inspected.id == 2

    def test_empty_list_has_no_selection(self) -> None:
        state = ProjectState()
        assert state.inspected is None
        assert state.inspected_tone == "neutral"

    def test_toggle_inspector(self) -> None:
        state = _state()
        assert state.show_inspector is True
        state.toggle_inspector()
        assert state.show_inspector is False
        state.toggle_inspector()
        assert state.show_inspector is True


def test_subtitle_counts_active_and_at_risk() -> None:
    assert _state().subtitle == "4 Projekte · 3 aktiv · 1 gefährdet"


def test_status_tones() -> None:
    assert status_tone("Aktiv") == "positive"
    assert status_tone("Geplant") == "info"
    assert status_tone("unbekannt") == "neutral"


def test_inspector_shows_team_member_planned_capacity() -> None:
    rendered = str(project_inspector())
    assert "planned_pt" in rendered
    assert " PT" in rendered
    assert "state_select_options" in rendered
    assert "update_inspected_project_state" in rendered


class TestRendering:
    def test_list_has_groups_header_and_rows(self) -> None:
        rendered = str(project_list())
        assert ("Bedarf", "total_pt", True) in COLUMNS
        for text in (
            "Meine Projekte",
            "Weitere Projekte",
            "Zeitraum",
            "Bedarf",
            "total_pt",
            "aq-tfoot",
            "visible_total_pt",
            "aq-thead",
        ):
            assert text in rendered
        assert "mine_rows" in rendered
        assert '["top"] : "30px"' in rendered

    def test_table_has_inspector(self) -> None:
        rendered = str(project_table(rx.text("leer")))
        assert "Projektdetails" in rendered
        assert "aq-inspector" in rendered
        assert "leer" in rendered

    def test_toolbar_has_filter_search_and_primary_button(self) -> None:
        assert "aq-segmented" in str(project_filter())
        rendered = " ".join(str(c) for c in project_toolbar())
        assert json.dumps("Projekt anlegen")[1:-1] in rendered
        assert "Projekt oder Kunde" in rendered
