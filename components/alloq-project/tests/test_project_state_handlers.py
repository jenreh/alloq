"""Behavior tests for ProjectState drawer handlers and ProjectValidationState."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.models.project import (
    Project,
    ProjectStatus,
    RequiredCapacity,
    Risk,
)
from alloq_commons.models.role import Role
from alloq_project.states.project_state import ProjectState, ProjectValidationState

MODULE = "alloq_project.states.project_state"
FORM = {
    "code": "P1",
    "customer": "Acme",
    "name_de": "Neu",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "budget": "2.000",
    "owner_ids": "5, 6",
    "required_capacity_1": "10",
}


class _FakeLogin:
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


def _login_as_admin(state: Any) -> None:
    login = _FakeLogin(SimpleNamespace(user_id=1, is_admin=True))
    object.__setattr__(state, "get_state", AsyncMock(return_value=login))


def _session_ctx(session: Any) -> Any:
    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield session

    return _ctx


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _has_text(events: list[Any], text: str) -> bool:
    return any(text in repr(event) for event in events)


def _drawer_state() -> ProjectState:
    state = ProjectState()
    project = Project(
        id=1,
        code="P1",
        name_de="P1",
        budget=1000,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    state.selected_project = project
    state.projects = [project]
    state.statuses = [
        ProjectStatus(id=10, project_id=1, status_date="2026-01-05", progress=20)
    ]
    state.risks = [
        Risk(id=3, project_id=1, number=1, name="R1", probability=2, impact=2),
        Risk(id=4, project_id=1, number=2, name="R2", probability=5, impact=1),
    ]
    state.available_roles = [Role(id=1, name="Dev")]
    _login_as_admin(state)
    object.__setattr__(state, "_persist_ev_summary", AsyncMock())
    return state


def _entity(data: dict) -> MagicMock:
    entity = MagicMock()
    entity.to_dict.return_value = data
    return entity


class TestStatusDraft:
    def test_expand_status_loads_draft_and_toggles(self) -> None:
        state = _drawer_state()

        state.expand_status(10)
        assert (state.expanded_status_id, state.status_draft_progress) == (10, 20)
        assert state.status_draft_date == "2026-01-05"

        state.expand_status(10)
        assert state.expanded_status_id == 0

        state.expand_status(999)
        assert state.expanded_status_id == 0

    def test_draft_setters_clamp_and_default(self) -> None:
        state = ProjectState()

        state.set_status_draft_progress("150")
        state.set_status_draft_budget_usage("-5")
        assert (state.status_draft_progress, state.status_draft_budget_usage) == (
            100,
            0,
        )
        state.set_status_draft_progress("abc")
        state.set_status_draft_budget_usage("x")
        assert (state.status_draft_progress, state.status_draft_budget_usage) == (0, 0)

        state.set_status_progress("55.7")
        state.set_status_budget_usage("bad")
        assert (state.status_progress, state.status_budget_usage) == (55, 0)

        state.set_status_draft_notes("")
        state.set_status_draft_date("")
        state.set_status_notes("n")
        state.set_status_date("2026-02-01")
        state.set_active_tab("risks")
        state.collapse_status_edit()
        assert state.status_draft_notes == ""
        assert (state.status_notes, state.status_date) == ("n", "2026-02-01")
        assert state.active_tab == "risks"

    @pytest.mark.asyncio
    async def test_save_without_expanded_status_does_nothing(self) -> None:
        state = _drawer_state()

        assert await _drain(state.save_status_draft()) == []

    @pytest.mark.asyncio
    async def test_save_with_invalid_date_shows_error(self) -> None:
        state = _drawer_state()
        state.expand_status(10)
        state.status_draft_date = "kaputt"

        events = await _drain(state.save_status_draft())

        assert _has_text(events, "Ungültiges Datum")

    @pytest.mark.asyncio
    async def test_save_missing_status_shows_error(self) -> None:
        state = _drawer_state()
        state.expand_status(10)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=None)
            events = await _drain(state.save_status_draft())

        assert _has_text(events, "Status nicht gefunden")

    @pytest.mark.asyncio
    async def test_save_updates_entity_and_local_list(self) -> None:
        state = _drawer_state()
        state.expand_status(10)
        state.set_status_draft_progress("60")
        state.set_status_draft_budget_usage("50")
        state.set_status_draft_date("2026-03-01")
        entity = SimpleNamespace()
        session = AsyncMock()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(session)),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=entity)
            events = await _drain(state.save_status_draft())

        session.commit.assert_awaited_once()
        assert entity.__dict__["progress"] == 60
        assert entity.__dict__["status_date"] == date(2026, 3, 1)
        assert state.statuses[0].progress == 60
        assert state.statuses[0].status_date == "2026-03-01"
        assert state.expanded_status_id == 0
        assert _has_text(events, "Status aktualisiert")

    @pytest.mark.asyncio
    async def test_save_db_error_shows_toast(self) -> None:
        state = _drawer_state()
        state.expand_status(10)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(side_effect=RuntimeError("down"))
            events = await _drain(state.save_status_draft())

        assert _has_text(events, "Fehler beim Speichern des Status")

    @pytest.mark.asyncio
    async def test_delete_status_removes_entry(self) -> None:
        state = _drawer_state()
        state.expand_status(10)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(return_value=True)
            events = await _drain(state.delete_project_status(10))

        assert state.statuses == []
        assert state.expanded_status_id == 0
        assert _has_text(events, "Status gelöscht")

    @pytest.mark.asyncio
    async def test_delete_status_db_error_keeps_entry(self) -> None:
        state = _drawer_state()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.status_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(side_effect=RuntimeError("down"))
            events = await _drain(state.delete_project_status(10))

        assert len(state.statuses) == 1
        assert _has_text(events, "Fehler beim Löschen des Status")


class TestRiskDraft:
    def test_add_risk_opens_blank_draft(self) -> None:
        state = _drawer_state()
        state.risk_draft_name = "old"

        state.add_project_risk()

        assert state.expanded_risk_id == -1
        assert state.risk_draft_name == ""
        assert state.risk_draft_form_version == 1

    def test_expand_risk_loads_draft_and_toggles(self) -> None:
        state = _drawer_state()

        state.expand_risk(3)
        assert state.expanded_risk_id == 3
        assert (state.risk_draft_name, state.risk_draft_impact) == ("R1", 2)

        state.expand_risk(3)
        assert state.expanded_risk_id == 0

        state.expand_risk(999)
        assert state.expanded_risk_id == 0

    def test_draft_setters_clamp_and_default(self) -> None:
        state = ProjectState()

        state.set_risk_draft_impact("9")
        state.set_risk_draft_probability("0")
        assert (state.risk_draft_impact, state.risk_draft_probability) == (5, 1)
        state.set_risk_draft_impact("x")
        state.set_risk_draft_probability("y")
        assert (state.risk_draft_impact, state.risk_draft_probability) == (3, 3)

        state.set_risk_draft_name("")
        state.set_risk_draft_description("d")
        state.set_risk_draft_measures("m")
        state.set_risk_draft_mitigation_status("")
        state.collapse_risk_edit()
        assert (state.risk_draft_description, state.risk_draft_measures) == ("d", "m")
        assert state.risk_draft_mitigation_status == "open"

    @pytest.mark.asyncio
    async def test_save_without_project_does_nothing(self) -> None:
        state = ProjectState()
        _login_as_admin(state)

        assert await _drain(state.save_risk_draft()) == []

    @pytest.mark.asyncio
    async def test_save_new_risk_appends_and_counts(self) -> None:
        state = _drawer_state()
        state.add_project_risk()
        state.set_risk_draft_name("Neu")
        session = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda e: setattr(e, "id", 42))

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(session)),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.create = AsyncMock()
            events = await _drain(state.save_risk_draft())

        repo.create.assert_awaited_once()
        assert [r.id for r in state.risks] == [3, 4, 42]
        assert state.risks[-1].number == 3
        assert state.selected_project is not None
        assert state.selected_project.risk_count == 3
        assert state.expanded_risk_id == 0
        assert _has_text(events, "Risiko gespeichert")

    @pytest.mark.asyncio
    async def test_save_existing_risk_updates_fields(self) -> None:
        state = _drawer_state()
        state.expand_risk(3)
        state.set_risk_draft_name("Umbenannt")
        state.set_risk_draft_impact("4")
        entity = SimpleNamespace()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=entity)
            events = await _drain(state.save_risk_draft())

        assert entity.__dict__["name"] == "Umbenannt"
        assert (state.risks[0].name, state.risks[0].impact) == ("Umbenannt", 4)
        assert state.risks[1].name == "R2"
        assert _has_text(events, "Risiko gespeichert")

    @pytest.mark.asyncio
    async def test_save_missing_risk_shows_error(self) -> None:
        state = _drawer_state()
        state.expand_risk(3)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=None)
            events = await _drain(state.save_risk_draft())

        assert _has_text(events, "Risiko nicht gefunden")

    @pytest.mark.asyncio
    async def test_save_db_error_shows_toast(self) -> None:
        state = _drawer_state()
        state.expand_risk(3)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(side_effect=RuntimeError("down"))
            events = await _drain(state.save_risk_draft())

        assert _has_text(events, "Fehler beim Speichern des Risikos")

    @pytest.mark.asyncio
    async def test_delete_risk_renumbers_remaining(self) -> None:
        state = _drawer_state()
        state.expand_risk(3)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(return_value=True)
            events = await _drain(state.delete_project_risk(3))

        assert [(r.id, r.number) for r in state.risks] == [(4, 1)]
        assert state.expanded_risk_id == 0
        assert _has_text(events, "Risiko gelöscht")

    @pytest.mark.asyncio
    async def test_update_risk_text_field_and_unknown_field(self) -> None:
        state = _drawer_state()
        entity = SimpleNamespace(name="R1")

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.risk_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=entity)
            await _drain(state.update_project_risk(3, "name", "Neu"))
            await _drain(state.update_project_risk(3, "id", "99"))

        assert entity.name == "Neu"
        assert state.risks[0].name == "Neu"
        assert state.risks[0].id == 3

    def test_risk_matrix_places_risks_by_score(self) -> None:
        state = _drawer_state()

        cells = state.risk_matrix_cells

        assert len(cells) == 25
        assert (cells[0].w, cells[0].a) == (5, 1)
        assert cells[0].risk_names == ["R2"]
        by_pos = {(c.w, c.a): c for c in cells}
        assert by_pos[2, 2].risk_numbers == [1]
        assert by_pos[2, 2].score == 4
        assert by_pos[1, 1].risk_numbers == []


class TestProjectLifecycle:
    @pytest.mark.asyncio
    async def test_select_project_loads_drawer(self) -> None:
        state = ProjectState()
        _login_as_admin(state)
        project: dict[str, Any] = {"id": 1, "code": "P1", "name_de": "P1"}
        project |= {"start_date": date(2026, 1, 1), "end_date": date(2026, 3, 31)}
        status = _entity({"id": 1, "project_id": 1, "status_date": "2026-01-02"})
        newer = _entity({"id": 2, "project_id": 1, "status_date": "2026-02-02"})
        risk = _entity({"id": 7, "project_id": 1, "name": "R", "impact": 2})
        holiday = SimpleNamespace(date=date(2026, 1, 6))

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as project_repo,
            patch(f"{MODULE}.status_repo") as status_repo,
            patch(f"{MODULE}.risk_repo") as risk_repo,
            patch(f"{MODULE}.capacity_repo") as capacity_repo,
            patch(f"{MODULE}.required_capacity_repo") as required_repo,
            patch(f"{MODULE}.capacity_allocation_repo") as alloc_repo,
            patch(f"{MODULE}.public_holiday_repo") as holiday_repo,
        ):
            project_repo.find_by_id = AsyncMock(return_value=_entity(project))
            status_repo.find_by_project_id = AsyncMock(return_value=[status, newer])
            risk_repo.find_by_project_id = AsyncMock(return_value=[risk])
            capacity_repo.find_by_project_id = AsyncMock(return_value=[])
            required_repo.find_by_project_id = AsyncMock(
                return_value=[_entity({"project_id": 1, "role_id": 1})]
            )
            alloc_repo.find_by_project = AsyncMock(return_value=[])
            holiday_repo.find_by_date_range = AsyncMock(return_value=[holiday])
            events = await _drain(state.select_project(1))

        assert state.detail_drawer_open is True
        assert [s.id for s in state.statuses] == [2, 1]
        assert state.risks[0].number == 1
        assert state.holiday_dates == [date(2026, 1, 6)]
        assert state.required_capacities == [RequiredCapacity(project_id=1, role_id=1)]
        assert _has_text(events, "set_is_loading")

    @pytest.mark.asyncio
    async def test_select_missing_project_shows_error(self) -> None:
        state = ProjectState()
        _login_as_admin(state)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=None)
            events = await _drain(state.select_project(1))

        assert _has_text(events, "Projekt nicht gefunden")
        assert state.detail_drawer_open is False

    @pytest.mark.asyncio
    async def test_create_project_persists_owners_and_capacities(self) -> None:
        state = _drawer_state()
        state.add_modal_open = True
        created = Project(id=2, code="P1", name_de="Neu")
        object.__setattr__(state, "_fetch_project", AsyncMock(return_value=created))
        session = AsyncMock()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(session)),
            patch(f"{MODULE}.project_repo") as project_repo,
            patch(f"{MODULE}.status_repo") as status_repo,
            patch(f"{MODULE}.employee_repo") as employee_repo,
            patch(f"{MODULE}.required_capacity_repo") as required_repo,
            patch(f"{MODULE}.ProjectEntity") as entity_cls,
        ):
            entity_cls.return_value.owners = []
            project_repo.create = AsyncMock()
            status_repo.create = AsyncMock()
            required_repo.create = AsyncMock()
            employee_repo.find_by_id = AsyncMock(side_effect=[MagicMock(), None])
            events = await _drain(state.create_project(dict(FORM)))

        assert len(entity_cls.return_value.owners) == 1
        required_repo.create.assert_awaited_once()
        session.commit.assert_awaited_once()
        assert 2 in [p.id for p in state.projects]
        assert state.add_modal_open is False
        assert _has_text(events, "Projekt 'P1' erstellt")

    @pytest.mark.asyncio
    async def test_update_project_applies_form(self) -> None:
        state = _drawer_state()
        updated = Project(id=1, code="P1", name_de="Neu")
        object.__setattr__(state, "_fetch_project", AsyncMock(return_value=updated))
        entity = SimpleNamespace(id=1, owners=["old"], required_capacities=["old"])
        session = AsyncMock()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(session)),
            patch(f"{MODULE}.project_repo") as project_repo,
            patch(f"{MODULE}.employee_repo") as employee_repo,
        ):
            project_repo.find_by_id = AsyncMock(return_value=entity)
            employee_repo.find_by_id = AsyncMock(side_effect=["emp5", None])
            events = await _drain(state.update_project(dict(FORM)))

        assert (entity.code, entity.budget) == ("P1", 2000)
        assert entity.owners == ["emp5"]
        assert [c.person_days for c in entity.required_capacities] == [10]
        session.commit.assert_awaited_once()
        assert state.projects[0].name_de == "Neu"
        assert state.detail_drawer_open is False
        assert state.selected_project is None
        assert _has_text(events, "Projekt 'Neu' aktualisiert")

    @pytest.mark.asyncio
    async def test_update_without_selection_does_nothing(self) -> None:
        state = ProjectState()
        _login_as_admin(state)

        assert await _drain(state.update_project(dict(FORM))) == []

    @pytest.mark.asyncio
    async def test_update_missing_project_shows_error(self) -> None:
        state = _drawer_state()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.find_by_id = AsyncMock(return_value=None)
            events = await _drain(state.update_project(dict(FORM)))

        assert _has_text(events, "Projekt nicht gefunden")

    @pytest.mark.asyncio
    async def test_update_invalid_form_shows_error(self) -> None:
        state = _drawer_state()

        events = await _drain(state.update_project({**FORM, "start_date": ""}))

        assert _has_text(events, "Ungültige Projektdaten")
        assert state.selected_project is not None

    @pytest.mark.asyncio
    async def test_delete_missing_project_shows_error(self) -> None:
        state = _drawer_state()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as repo,
        ):
            repo.delete_by_id = AsyncMock(return_value=False)
            events = await _drain(state.delete_project(1))

        assert _has_text(events, "Projekt nicht gefunden")
        assert len(state.projects) == 1


def _initialize_fn() -> Any:
    return cast("Any", ProjectValidationState).initialize.fn


class TestProjectValidationInitialize:
    @pytest.mark.asyncio
    async def test_add_mode_resets_fields_and_zeroes_roles(self) -> None:
        state = ProjectValidationState()
        state.code = "OLD"
        state.code_error = "x"
        project_state = ProjectState()
        project_state.available_roles = [Role(id=1), Role(id=2)]
        object.__setattr__(state, "get_state", AsyncMock(return_value=project_state))

        await _initialize_fn()(state)

        assert (state.code, state.code_error) == ("", "")
        assert state.role_capacities == {"1": 0, "2": 0}
        assert state.form_version == 1

    @pytest.mark.asyncio
    async def test_edit_mode_preloads_project(self) -> None:
        state = ProjectValidationState()
        project_state = ProjectState()
        project_state.available_roles = [Role(id=1), Role(id=2)]
        object.__setattr__(state, "get_state", AsyncMock(return_value=project_state))
        project = Project(
            id=1,
            code="P1",
            customer="Acme",
            name_de="Name",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            budget=500,
            owner_ids=[5],
            required_capacities=[RequiredCapacity(role_id=2, person_days=8)],
        )

        await _initialize_fn()(state, project)

        assert (state.code, state.customer, state.budget) == ("P1", "Acme", 500)
        assert (state.start_date, state.end_date) == ("2026-01-01", "2026-06-30")
        assert state.owner_ids == ["5"]
        assert state.role_capacities == {"1": 0, "2": 8}


class TestProjectValidationSetters:
    def test_required_field_setters_validate(self) -> None:
        state = ProjectValidationState()

        state.set_code(" ")
        state.set_customer("")
        state.set_name_de("")
        assert state.code_error == "Projekt-Code ist erforderlich."
        assert state.customer_error == "Kunde ist erforderlich."
        assert state.name_de_error == "Name (DE) ist erforderlich."
        assert state.has_errors() is True
        assert state.is_form_invalid is True

        state.set_code("P")
        state.set_customer("C")
        state.set_name_de("N")
        assert (state.code_error, state.customer_error, state.name_de_error) == (
            "",
            "",
            "",
        )

    def test_date_setters_validate(self) -> None:
        state = ProjectValidationState()

        state.set_start_date("2026-01-01")
        assert state.date_error == "Start und Ende sind erforderlich."
        state.set_end_date("nope")
        assert state.date_error == "Bitte gültige Daten auswählen."
        state.set_end_date("2026-02-01")
        assert state.date_error == ""

    def test_budget_and_capacity_parsing(self) -> None:
        state = ProjectValidationState()

        state.set_budget("12.500")
        assert (state.budget, state.budget_error) == (12500, "")
        state.set_budget("abc")
        assert state.budget == 0
        state.set_budget(-3)
        assert state.budget_error == "Budget darf nicht negativ sein."

        state.set_role_capacity("1", "1.200")
        state.set_role_capacity("2", "x")
        assert state.role_capacities == {"1": 1200, "2": 0}
        assert state.total_capacity == 1200

    def test_simple_setters(self) -> None:
        state = ProjectValidationState()

        state.set_state("")
        state.set_color("#000000")
        state.set_owner_ids([])
        assert state.state == "Geplant"
        assert state.color == "#000000"
        assert state.owner_ids == []
