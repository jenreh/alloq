"""Tests for inline quick-create of projects in the planning grid."""

import datetime
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.models.project import Project
from alloq_commons.services.quick_project import NEW_PROJECT_VALUE, QuickProjectError
from alloq_project.states.planning_grid_state import PlanningStore


def _mock_session_ctx(session: AsyncMock):
    """Create an async context manager mock for get_asyncdb_session."""

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


def _new_project() -> Project:
    start = datetime.date(2026, 9, 14)
    return Project(
        id=7,
        code="NEU",
        name_de="Neue Plattform",
        start_date=start,
        end_date=start + datetime.timedelta(days=90),
    )


def _state_with_open_modal() -> PlanningStore:
    state = PlanningStore()  # type: ignore[call-arg]
    state.add_project_emp_id = "emp-1"
    state.employee_meta = [
        {"id": "emp-1", "real_id": 1, "project_ids": ["proj-1"], "role_ids": [3]}
    ]
    state.project_meta = [{"id": "proj-1", "real_id": 1, "code": "ALT"}]
    state.available_projects = [Project(id=1, code="ALT", name_de="Altes Projekt")]
    return state


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


class TestQuickCreateOptions:
    """Tests for the option list backing the project select."""

    def test_options_lead_with_create_entry(self) -> None:
        state = _state_with_open_modal()

        state._rebuild_add_project_options()

        assert state.add_project_options[0]["value"] == NEW_PROJECT_VALUE

    def test_options_exclude_already_assigned_projects(self) -> None:
        state = _state_with_open_modal()

        state._rebuild_add_project_options()

        values = [opt["value"] for opt in state.add_project_options]
        assert values == [NEW_PROJECT_VALUE]

    def test_quick_create_active_tracks_selection(self) -> None:
        state = PlanningStore()  # type: ignore[call-arg]
        assert state.quick_create_active is False

        state.set_add_project_selected(NEW_PROJECT_VALUE)

        assert state.quick_create_active is True


class TestQuickCreateProject:
    """Tests for the quick_create_project event handler."""

    @pytest.mark.asyncio
    async def test_selects_created_project(self) -> None:
        state = _state_with_open_modal()
        state.set_add_project_selected(NEW_PROJECT_VALUE)
        state.quick_project_name = "Neue Plattform"
        state.quick_project_code = "NEU"
        project = _new_project()

        with (
            patch(
                "alloq_project.states.planning_grid_state.get_asyncdb_session",
                _mock_session_ctx(AsyncMock()),
            ),
            patch(
                "alloq_project.states.planning_grid_state.create_quick_project",
                AsyncMock(return_value=project),
            ),
        ):
            await _drain(state.quick_create_project())

        assert state.add_project_selected == "7"
        assert state.quick_create_active is False
        assert project in state.available_projects
        assert project in state.all_projects
        assert state.quick_project_name == ""
        assert state.quick_project_code == ""
        assert state.is_quick_creating is False

    @pytest.mark.asyncio
    async def test_created_project_is_selectable(self) -> None:
        state = _state_with_open_modal()
        state.quick_project_name = "Neue Plattform"
        state.quick_project_code = "NEU"

        with (
            patch(
                "alloq_project.states.planning_grid_state.get_asyncdb_session",
                _mock_session_ctx(AsyncMock()),
            ),
            patch(
                "alloq_project.states.planning_grid_state.create_quick_project",
                AsyncMock(return_value=_new_project()),
            ),
        ):
            await _drain(state.quick_create_project())

        labels = {opt["value"]: opt["label"] for opt in state.add_project_options}
        assert labels["7"] == "NEU - Neue Plattform"

    @pytest.mark.asyncio
    async def test_keeps_input_when_rejected(self) -> None:
        state = _state_with_open_modal()
        state.set_add_project_selected(NEW_PROJECT_VALUE)
        state.quick_project_name = "Neue Plattform"
        state.quick_project_code = "ZU-LANG"

        with (
            patch(
                "alloq_project.states.planning_grid_state.get_asyncdb_session",
                _mock_session_ctx(AsyncMock()),
            ),
            patch(
                "alloq_project.states.planning_grid_state.create_quick_project",
                AsyncMock(side_effect=QuickProjectError("Kürzel zu lang.")),
            ),
        ):
            await _drain(state.quick_create_project())

        assert state.quick_create_active is True
        assert state.quick_project_name == "Neue Plattform"
        assert state.quick_project_code == "ZU-LANG"
        assert state.is_quick_creating is False
        assert state.available_projects == [
            Project(id=1, code="ALT", name_de="Altes Projekt")
        ]


class TestAssignWithPendingQuickCreate:
    """Tests that an un-created project cannot be assigned."""

    @pytest.mark.asyncio
    async def test_rejects_uncreated_project(self) -> None:
        state = _state_with_open_modal()
        state.set_add_project_selected(NEW_PROJECT_VALUE)
        session = AsyncMock()

        with patch(
            "alloq_project.states.planning_grid_state.get_asyncdb_session",
            _mock_session_ctx(session),
        ):
            await _drain(state.add_project_to_employee_grid({"role_id": "3"}))

        session.commit.assert_not_called()
        assert state.add_project_emp_id == "emp-1"

    @pytest.mark.asyncio
    async def test_rejects_empty_selection(self) -> None:
        state = _state_with_open_modal()
        session = AsyncMock()

        with patch(
            "alloq_project.states.planning_grid_state.get_asyncdb_session",
            _mock_session_ctx(session),
        ):
            await _drain(state.add_project_to_employee_grid({"role_id": "3"}))

        session.commit.assert_not_called()
