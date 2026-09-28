"""Tests for project Reflex state helpers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project, ProjectStatus, Risk
from alloq_project.states.project_state import (
    _EMPLOYEE_PAGE_SIZE,
    ProjectState,
    ProjectValidationState,
    _parse_localized_int,
)
from sqlalchemy.exc import IntegrityError


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


# ---------------------------------------------------------------------------
# Event handler tests (authorization, persistence, error handling)
# ---------------------------------------------------------------------------

MODULE = "alloq_project.states.project_state"


class _FakeLogin:
    """Stand-in for LoginState as seen by the auth decorators."""

    def __init__(self, user: Any) -> None:
        self._user = user

    @property
    async def authenticated_user(self) -> Any:
        return self._user

    @property
    async def is_authenticated(self) -> bool:
        return self._user is not None

    async def redir(self) -> None:
        return None


def _login_as(state: Any, *, is_admin: bool = True) -> None:
    """Route the state's get_state(LoginState) to a fake (non-)admin user."""
    login = _FakeLogin(SimpleNamespace(user_id=1, is_admin=is_admin))

    async def _get_state(_cls: type) -> Any:
        return login

    object.__setattr__(state, "get_state", AsyncMock(side_effect=_get_state))


def _mock_session_ctx(session: AsyncMock) -> Any:
    @asynccontextmanager
    async def _ctx() -> AsyncIterator[AsyncMock]:
        yield session

    return _ctx


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _has_text(events: list[Any], text: str) -> bool:
    return any(text in repr(event) for event in events)


def _drawer_state() -> ProjectState:
    state = ProjectState()  # type: ignore[call-arg]
    state.selected_project = Project(id=1, code="P1", name_de="P1", budget=1000)
    state.projects = [state.selected_project]
    state.statuses = [
        ProjectStatus(id=10, project_id=1, status_date="2026-01-05", progress=20)
    ]
    state.risks = [Risk(id=3, project_id=1, name="R", probability=2, impact=2)]
    return state


class TestParseLocalizedInt:
    """Tests for German-formatted number parsing."""

    def test_numbers_are_not_treated_as_formatted_strings(self) -> None:
        assert _parse_localized_int(12.5) == 12
        assert _parse_localized_int(30000.0) == 30000
        assert _parse_localized_int(30000) == 30000

    def test_german_formatted_strings(self) -> None:
        assert _parse_localized_int("30.000") == 30000
        assert _parse_localized_int("1.234,56") == 1234
        assert _parse_localized_int("") == 0


class TestProjectStateAuthorization:
    """Mutating/reading handlers must be admin-only server-side."""

    @pytest.mark.asyncio
    async def test_non_admin_cannot_delete_project(self) -> None:
        state = _drawer_state()
        _login_as(state, is_admin=False)

        with patch(f"{MODULE}.project_repo") as repo:
            repo.delete_by_id = AsyncMock(return_value=True)
            events = await _drain(state.delete_project(1))

        repo.delete_by_id.assert_not_awaited()
        assert _has_text(events, "Berechtigung")
        assert len(state.projects) == 1

    @pytest.mark.asyncio
    async def test_admin_can_delete_project(self) -> None:
        state = _drawer_state()
        _login_as(state)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(return_value=True)
            await _drain(state.delete_project(1))

        repo.delete_by_id.assert_awaited_once()
        assert state.projects == []

    @pytest.mark.asyncio
    async def test_non_admin_cannot_load_projects(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        _login_as(state, is_admin=False)

        with patch(f"{MODULE}.project_repo") as repo:
            repo.find_all_with_stats = AsyncMock(return_value=[])
            await _drain(state.load_projects())

        repo.find_all_with_stats.assert_not_awaited()


class TestProjectStateHandlers:
    """Behavior of project/status/risk handlers."""

    @pytest.mark.asyncio
    async def test_delete_status_of_other_project_is_ignored(self) -> None:
        state = _drawer_state()
        _login_as(state)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(return_value=True)
            await _drain(state.delete_project_status(999))

        repo.delete_by_id.assert_not_awaited()
        assert len(state.statuses) == 1

    @pytest.mark.asyncio
    async def test_delete_risk_of_other_project_is_ignored(self) -> None:
        state = _drawer_state()
        _login_as(state)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(return_value=True)
            await _drain(state.delete_project_risk(999))

        repo.delete_by_id.assert_not_awaited()
        assert len(state.risks) == 1

    @pytest.mark.asyncio
    async def test_update_risk_clamps_scores(self) -> None:
        state = _drawer_state()
        _login_as(state)
        entity = SimpleNamespace(probability=2, impact=2)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=entity)
            await _drain(state.update_project_risk(3, "probability", "7"))
            await _drain(state.update_project_risk(3, "impact", "0"))

        assert (entity.probability, entity.impact) == (5, 1)
        assert (state.risks[0].probability, state.risks[0].impact) == (5, 1)

    @pytest.mark.asyncio
    async def test_add_status_with_stale_form_version_is_ignored(self) -> None:
        state = _drawer_state()
        state.status_date = "2026-02-01"
        state.status_form_version = 2
        _login_as(state)

        with patch(f"{MODULE}.status_repo") as repo:
            repo.create = AsyncMock()
            await _drain(state.add_project_status(1))

        repo.create.assert_not_awaited()
        assert len(state.statuses) == 1

    @pytest.mark.asyncio
    async def test_add_status_with_current_form_version_saves(self) -> None:
        state = _drawer_state()
        state.status_date = "2026-02-01"
        state.status_progress = 40
        state.status_form_version = 2
        _login_as(state)
        object.__setattr__(state, "_persist_ev_summary", AsyncMock())
        session = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda e: setattr(e, "id", 11))

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(session)),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.create = AsyncMock()
            await _drain(state.add_project_status(2))

        repo.create.assert_awaited_once()
        assert [s.id for s in state.statuses] == [11, 10]
        assert state.status_form_version == 3

    @pytest.mark.asyncio
    async def test_select_project_db_error_resets_global_loading(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        _login_as(state)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(side_effect=RuntimeError("db down"))
            events = await _drain(state.select_project(1))

        assert _has_text(events, "set_is_loading")
        assert not _has_text(events, "db down")
        assert state.detail_drawer_open is False

    @pytest.mark.asyncio
    async def test_duplicate_code_shows_friendly_error_without_sql(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        _login_as(state)
        session = AsyncMock()
        session.commit = AsyncMock(
            side_effect=IntegrityError(
                "INSERT INTO project (code) VALUES (?)", {"code": "P1"}, Exception()
            )
        )
        form = {
            "code": "P1",
            "customer": "C",
            "name_de": "N",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "budget": "1.000",
        }

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(session)),
            patch(f"{MODULE}.project_repo") as project_repo,
            patch(f"{MODULE}.status_repo") as status_repo,
        ):
            project_repo.create = AsyncMock()
            status_repo.create = AsyncMock()
            events = await _drain(state.create_project(form))

        assert _has_text(events, "Projekt-Code bereits vergeben")
        assert not _has_text(events, "INSERT")

    @pytest.mark.asyncio
    async def test_load_projects_ignores_search_filter(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.search_filter = "abc"

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.find_all_with_stats = AsyncMock(return_value=[])
            await state._load_projects()

        assert repo.find_all_with_stats.await_args is not None
        assert repo.find_all_with_stats.await_args.kwargs.get("search") is None

    @pytest.mark.asyncio
    async def test_current_employee_matched_case_insensitively(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        state.current_user_email = "Jens@Example.de"
        employee = MagicMock(id=7, first_name="Jens", last_name="R")
        employee.hours_per_week = 40.0
        employee.to_dict.return_value = Employee(
            id=7, first_name="Jens", email="jens@example.de"
        ).model_dump()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.role_repo") as role_repo,
            patch(f"{MODULE}.employee_repo") as employee_repo,
        ):
            role_repo.find_all_paginated = AsyncMock(return_value=[])
            employee_repo.find_all_paginated = AsyncMock(return_value=[employee])
            await state._load_reference_data()

        assert state.current_employee_id == 7

    @pytest.mark.asyncio
    async def test_load_reference_data_pages_through_all_employees(self) -> None:
        state = _drawer_state()
        state.current_user_email = "jens@example.de"

        def _employee(emp_id: int, email: str) -> MagicMock:
            entity = MagicMock(id=emp_id, first_name="E", last_name=str(emp_id))
            entity.hours_per_week = 40.0
            entity.to_dict.return_value = Employee(
                id=emp_id, first_name="E", email=email
            ).model_dump()
            return entity

        first_page = [
            _employee(i, f"other{i}@example.de")
            for i in range(1, _EMPLOYEE_PAGE_SIZE + 1)
        ]
        second_page = [_employee(999, "jens@example.de")]

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.role_repo") as role_repo,
            patch(f"{MODULE}.employee_repo") as employee_repo,
        ):
            role_repo.find_all_paginated = AsyncMock(return_value=[])
            employee_repo.find_all_paginated = AsyncMock(
                side_effect=[first_page, second_page]
            )
            await state._load_reference_data()

        assert state.current_employee_id == 999
        assert len(state.available_employees) == _EMPLOYEE_PAGE_SIZE + 1

    @pytest.mark.asyncio
    async def test_persist_ev_summary_refreshes_overview_project(self) -> None:
        state = _drawer_state()
        entity = MagicMock()
        entity.to_dict.return_value = {
            "id": 1,
            "code": "P1",
            "name_de": "P1",
            "budget": 1000,
            "current_progress": 60,
        }

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=entity)
            await state._persist_ev_summary()

        assert state.projects[0].current_progress == 60
        assert state.selected_project is not None
        assert state.selected_project.current_progress == 60

    @pytest.mark.asyncio
    async def test_load_projects_pages_past_repository_limit(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]

        def _entity(i: int) -> MagicMock:
            entity = MagicMock()
            entity.to_dict.return_value = {"id": i, "code": f"P{i}", "name_de": f"P{i}"}
            return entity

        pages = [[_entity(i) for i in range(200)], [_entity(200)]]

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.find_all_with_stats = AsyncMock(side_effect=pages)
            await state._load_projects()

        assert len(state.projects) == 201

    def test_invalid_form_color_falls_back_to_default(self) -> None:
        state = ProjectState()  # type: ignore[call-arg]
        form = {
            "code": "P1",
            "customer": "C",
            "name_de": "N",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "color": "red;x",
        }

        assert state._project_create_from_form(form).color == "#F7C948"
        form["color"] = "#5B7FA3"
        assert state._project_create_from_form(form).color == "#5B7FA3"
