"""Tests for project Reflex state helpers."""

from datetime import date

from alloq_commons.models.project import Project
from alloq_project.states.project_state import ProjectState, ProjectValidationState


class TestProjectState:
    """Tests for ProjectState computed behavior."""

    def test_initial_state(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        assert state.projects == []
        assert state.selected_project is None
        assert state.add_modal_open is False
        assert state.status_filter == "all"

    def test_filtered_projects_by_search(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.projects = [
            Project(code="CRM", customer="Acme GmbH", name_de="CRM"),
            Project(code="VISION", customer="Muster AG", name_de="Computer Vision"),
        ]
        state.search_filter = "vision"

        result = state.filtered_projects

        assert len(result) == 1
        assert result[0].code == "VISION"

    def test_filtered_projects_by_customer_search(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.projects = [
            Project(code="CRM", customer="Acme GmbH", name_de="CRM"),
            Project(code="VISION", customer="Muster AG", name_de="Computer Vision"),
        ]
        state.search_filter = "acme"

        result = state.filtered_projects

        assert len(result) == 1
        assert result[0].code == "CRM"

    def test_filtered_projects_by_state(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.projects = [
            Project(code="SAFE", customer="Muster AG", state="Geplant"),
            Project(code="RISK", customer="Acme GmbH", state="Risiko"),
        ]
        state.status_filter = "Risiko"

        result = state.filtered_projects

        assert len(result) == 1
        assert result[0].code == "RISK"

    def test_view_mode_defaults_to_grid(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        assert state.view_mode == "grid"

    def test_set_view_mode_accepts_known_modes(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.set_view_mode("table")
        assert state.view_mode == "table"
        state.set_view_mode("grid")
        assert state.view_mode == "grid"

    def test_set_view_mode_ignores_unknown_mode(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.set_view_mode("table")
        state.set_view_mode("kanban")
        assert state.view_mode == "table"

    def test_sort_defaults(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        assert state.sort_column == "name"
        assert state.sort_desc is False

    def test_toggle_sort_same_column_flips_direction(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.toggle_sort("name")
        assert state.sort_column == "name"
        assert state.sort_desc is True
        state.toggle_sort("name")
        assert state.sort_desc is False

    def test_toggle_sort_new_column_resets_ascending(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.toggle_sort("name")
        state.toggle_sort("budget")
        assert state.sort_column == "budget"
        assert state.sort_desc is False

    def test_toggle_sort_ignores_unknown_column(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.toggle_sort("bogus")
        assert state.sort_column == "name"
        assert state.sort_desc is False

    def test_my_and_other_projects_follow_sort_order(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.current_employee_id = 7
        state.projects = [
            Project(code="M1", name_de="Mine A", budget=100, owner_ids=[7]),
            Project(code="O1", name_de="Other A", budget=300),
            Project(code="M2", name_de="Mine B", budget=200, owner_ids=[7]),
            Project(code="O2", name_de="Other B", budget=50),
        ]
        state.toggle_sort("budget")
        state.toggle_sort("budget")

        assert [p.code for p in state.my_projects] == ["M2", "M1"]
        assert [p.code for p in state.other_projects] == ["O1", "O2"]


class TestProjectValidationState:
    """Tests for project validation state."""

    def test_initialize_defaults(self) -> None:
        state = ProjectValidationState()  # type: ignore[call-arg]

        assert state.code == ""
        assert state.color == "#F7C948"
        assert state.budget == 0
        assert state.has_errors() is False

    def test_valid_form(self) -> None:
        state = ProjectValidationState()  # type: ignore[call-arg]
        state.code = "ML-OPS"
        state.customer = "Muster AG"
        state.name_de = "ML-Ops Plattform"
        state.start_date = date(2026, 6, 1).isoformat()
        state.end_date = date(2026, 12, 31).isoformat()
        state.budget = 300000

        assert state.is_form_valid is True

    def test_invalid_date_range(self) -> None:
        state = ProjectValidationState()  # type: ignore[call-arg]
        state.start_date = date(2026, 12, 31).isoformat()
        state.end_date = date(2026, 6, 1).isoformat()
        state.validate_dates()

        assert state.date_error == "Ende darf nicht vor Start liegen."
