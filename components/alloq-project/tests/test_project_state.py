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
            Project(code="CRM", name_de="CRM"),
            Project(code="VISION", name_de="Computer Vision"),
        ]
        state.search_filter = "vision"

        result = state.filtered_projects

        assert len(result) == 1
        assert result[0].code == "VISION"

    def test_filtered_projects_by_state(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.projects = [
            Project(code="SAFE", state="Geplant"),
            Project(code="RISK", state="Risiko"),
        ]
        state.status_filter = "Risiko"

        result = state.filtered_projects

        assert len(result) == 1
        assert result[0].code == "RISK"


class TestProjectValidationState:
    """Tests for project validation state."""

    def test_initialize_defaults(self) -> None:
        state = ProjectValidationState()  # type: ignore[call-arg]
        state.initialize()

        assert state.code == ""
        assert state.color == "#F7C948"
        assert state.has_errors is False

    def test_valid_form(self) -> None:
        state = ProjectValidationState()  # type: ignore[call-arg]
        state.code = "ML-OPS"
        state.name_de = "ML-Ops Plattform"
        state.start_date = date(2026, 6, 1).isoformat()
        state.end_date = date(2026, 12, 31).isoformat()
        state.budget = "300000"

        assert state.is_form_valid is True

    def test_invalid_date_range(self) -> None:
        state = ProjectValidationState()  # type: ignore[call-arg]
        state.start_date = date(2026, 12, 31).isoformat()
        state.end_date = date(2026, 6, 1).isoformat()
        state.validate_dates()

        assert state.date_error == "Ende darf nicht vor Start liegen."
