"""Tests for ProjectResourceState (Ressourcen tab of the project drawer)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import reflex as rx
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import (
    CapacityAllocation,
    Project,
    RequiredCapacity,
)
from alloq_commons.models.role import Role
from alloq_project.components.project_resource_tab import ressourcen_tab
from alloq_project.services.resource_planning import PlanTarget
from alloq_project.states.project_resource_state import ProjectResourceState
from alloq_project.states.project_state import ProjectState

MODULE = "alloq_project.states.project_resource_state"
W1 = date(2026, 9, 14)
W2 = date(2026, 9, 21)


def _mock_session_ctx(session: AsyncMock):
    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _project_state() -> MagicMock:
    project_state = MagicMock()
    project_state.selected_project = Project(id=1, name_de="Caracho")
    project_state.projects = [Project(id=1, name_de="Caracho")]
    project_state.allocation_plan = []
    return project_state


@asynccontextmanager
async def _patch_states(
    state: ProjectResourceState, project_state: MagicMock
) -> AsyncIterator[None]:
    """Bypass auth and route get_state(ProjectState) to a mock."""

    async def _true() -> bool:
        return True

    async def _get_state(cls: type) -> Any:
        if cls is ProjectState:
            return project_state
        login_state = MagicMock()
        login_state.is_authenticated = _true()
        return login_state

    original_get_state = type(state).get_state
    object.__setattr__(state, "get_state", AsyncMock(side_effect=_get_state))
    try:
        yield
    finally:
        object.__setattr__(state, "get_state", original_get_state)


def _loaded_state() -> ProjectResourceState:
    state = ProjectResourceState()  # type: ignore[call-arg]
    state.project_id = 1
    state.project_start = "2026-09-14"
    state.project_end = "2026-12-31"
    state.start_iso = "2026-09-14"
    state.end_iso = "2026-09-25"
    state.role_id = "3"
    state.days_per_week = 3.0
    state.roles = [Role(id=3, name="Dev"), Role(id=4, name="Architekt")]
    state.employees = [
        Employee(id=1, first_name="Anna", last_name="Test", role_ids=[3]),
        Employee(id=2, first_name="Bert", last_name="Test", role_ids=[4]),
    ]
    state.allocations = [
        CapacityAllocation(employee_id=1, role_id=3, week_start=W1, person_days=2.0),
        CapacityAllocation(employee_id=1, role_id=3, week_start=W2, person_days=2.0),
    ]
    return state


class TestInputs:
    """Tests for form input handlers and derived vars."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("7", 5.0), ("0.2", 0.5), ("2.3", 2.5), ("2,5", 2.5), (4, 4.0)],
    )
    def test_days_per_week_clamped_to_half_steps(
        self, raw: float | str, expected: float
    ) -> None:
        state = _loaded_state()

        state.set_days_per_week(raw)

        assert state.days_per_week == expected

    def test_invalid_days_keep_previous_value(self) -> None:
        state = _loaded_state()

        state.set_days_per_week("abc")

        assert state.days_per_week == 3.0

    def test_dates_clamped_to_project_range(self) -> None:
        state = _loaded_state()

        state.set_start("2026-01-01")
        state.set_end("2027-06-30T00:00:00")

        assert state.start_iso == "2026-09-14"
        assert state.end_iso == "2026-12-31"

    def test_invalid_date_keeps_previous_value(self) -> None:
        state = _loaded_state()

        state.set_start("")

        assert state.start_iso == "2026-09-14"

    def test_form_error_messages(self) -> None:
        state = _loaded_state()
        assert state.form_error == ""

        state.start_iso = "2026-10-01"
        assert state.form_error == "Von muss vor Bis liegen."

        state.start_iso = "2026-09-14"
        state.role_id = ""
        assert state.form_error == "Bitte eine Rolle wählen."

    def test_candidates_and_periods(self) -> None:
        state = _loaded_state()

        assert [c.employee_id for c in state.candidates] == [1]
        assert state.candidates[0].already_planned is True
        assert len(state.periods) == 1
        assert state.periods[0].employee_name == "Anna Test"
        assert state.role_options == [
            {"value": "3", "label": "Dev"},
            {"value": "4", "label": "Architekt"},
        ]

    def test_edit_period_fills_form_and_cancel_clears(self) -> None:
        state = _loaded_state()
        key = state.periods[0].key

        state.edit_period(key)

        assert state.editing_key == key
        assert (state.start_iso, state.end_iso) == ("2026-09-14", "2026-09-25")
        assert state.days_per_week == 2.0
        assert state.is_editing is True

        state.cancel_edit()
        assert state.editing_key == ""


class TestLoad:
    """Tests for loading the selected project's resource data."""

    @pytest.mark.asyncio
    async def test_load_splits_allocations_and_sets_defaults(self) -> None:
        state = ProjectResourceState()  # type: ignore[call-arg]
        project_entity = MagicMock()
        project_entity.to_dict.return_value = {
            "id": 1,
            "name_de": "Caracho",
            "start_date": W1,
            "end_date": date(2026, 12, 31),
            "required_capacities": [
                RequiredCapacity(role_id=3, person_days=4).model_dump(),
                RequiredCapacity(role_id=4, person_days=10).model_dump(),
            ],
        }
        employee_entity = MagicMock()
        employee_entity.to_dict.return_value = Employee(
            id=1, first_name="Anna", role_ids=[3]
        ).model_dump()
        role_entities = [MagicMock(), MagicMock()]
        role_entities[0].to_dict.return_value = Role(
            id=4, name="Architekt"
        ).model_dump()
        role_entities[1].to_dict.return_value = Role(id=3, name="Dev").model_dump()
        own = MagicMock()
        own.to_dict.return_value = CapacityAllocation(
            project_id=1, employee_id=1, role_id=3, week_start=W1, person_days=4.0
        ).model_dump()
        other = MagicMock(project_id=2, employee_id=1, week_start=W1, person_days=1.5)
        mine = MagicMock(project_id=1, employee_id=1, week_start=W1, person_days=4.0)
        holiday = MagicMock(date=date(2026, 10, 3))

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.project_repo") as project_repo,
            patch(f"{MODULE}.employee_repo") as employee_repo,
            patch(f"{MODULE}.role_repo") as role_repo,
            patch(f"{MODULE}.public_holiday_repo") as holiday_repo,
            patch(f"{MODULE}.capacity_allocation_repo") as alloc_repo,
        ):
            project_repo.find_by_id = AsyncMock(return_value=project_entity)
            employee_repo.find_all_paginated = AsyncMock(return_value=[employee_entity])
            role_repo.find_all_paginated = AsyncMock(return_value=role_entities)
            holiday_repo.find_by_date_range = AsyncMock(return_value=[holiday])
            alloc_repo.find_in_range = AsyncMock(return_value=[other, mine])
            alloc_repo.find_by_project = AsyncMock(return_value=[own])
            async with _patch_states(state, _project_state()):
                await _drain(state.load_selected())

        assert state.is_loading is False
        assert state.other_pt == {"1": {"2026-09-14": 1.5}}
        assert state.holiday_dates == [date(2026, 10, 3)]
        assert [r.name for r in state.roles] == ["Architekt", "Dev"]
        assert (state.start_iso, state.end_iso) == ("2026-09-14", "2026-12-31")
        # Dev (3) is fully covered by 4 PT, so Architekt (4) is the default.
        assert state.role_id == "4"
        assert len(state.periods) == 1

    @pytest.mark.asyncio
    async def test_load_without_selected_project_does_nothing(self) -> None:
        state = ProjectResourceState()  # type: ignore[call-arg]
        project_state = _project_state()
        project_state.selected_project = None

        async with _patch_states(state, project_state):
            events = await _drain(state.load_selected())

        assert events == []
        assert state.project_id == 0


class TestSave:
    """Tests for assign, edit-save and delete handlers."""

    @pytest.mark.asyncio
    async def test_assign_applies_plan_and_syncs_project_state(self) -> None:
        state = _loaded_state()
        state.allocations = []
        project_state = _project_state()
        refreshed = MagicMock()
        refreshed.to_dict.return_value = CapacityAllocation(
            employee_id=1, role_id=3, week_start=W1, person_days=3.0
        ).model_dump()
        project_entity = MagicMock()
        project_entity.to_dict.return_value = {"id": 1, "name_de": "Neu"}

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.apply_resource_plan", AsyncMock(return_value=2)) as apply,
            patch(f"{MODULE}.delete_resource_period", AsyncMock()) as delete,
            patch(f"{MODULE}.capacity_allocation_repo") as alloc_repo,
            patch(f"{MODULE}.project_repo") as project_repo,
        ):
            alloc_repo.find_by_project = AsyncMock(return_value=[refreshed])
            project_repo.find_by_id = AsyncMock(return_value=project_entity)
            async with _patch_states(state, project_state):
                events = await _drain(state.assign(1))

        apply.assert_awaited_once()
        assert apply.await_args is not None
        assert apply.await_args.args[1:] == (
            PlanTarget(project_id=1, employee_id=1, role_id=3),
            W1,
            date(2026, 9, 25),
            [(W1, 3.0), (W2, 3.0)],
        )
        delete.assert_not_awaited()
        assert state.is_saving is False
        assert len(state.allocations) == 1
        assert len(project_state.allocation_plan) == 1
        assert project_state.projects[0].name_de == "Neu"
        assert events

    @pytest.mark.asyncio
    async def test_edit_save_deletes_old_period_first(self) -> None:
        state = _loaded_state()
        state.edit_period(state.periods[0].key)
        state.set_days_per_week(1)
        calls: list[str] = []

        async def _delete(*_args: Any) -> int:
            calls.append("delete")
            return 2

        async def _apply(*_args: Any) -> int:
            calls.append("apply")
            return 2

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(f"{MODULE}.apply_resource_plan", _apply),
            patch(f"{MODULE}.delete_resource_period", _delete),
            patch(f"{MODULE}.capacity_allocation_repo") as alloc_repo,
            patch(f"{MODULE}.project_repo") as project_repo,
        ):
            alloc_repo.find_by_project = AsyncMock(return_value=[])
            project_repo.find_by_id = AsyncMock(return_value=None)
            async with _patch_states(state, _project_state()):
                await _drain(state.assign(1))

        assert calls == ["delete", "apply"]
        assert state.editing_key == ""

    @pytest.mark.asyncio
    async def test_assign_without_capacity_does_not_save(self) -> None:
        state = _loaded_state()
        state.other_pt = {"1": {"2026-09-14": 5.0, "2026-09-21": 5.0}}

        with patch(f"{MODULE}.apply_resource_plan", AsyncMock()) as apply:
            async with _patch_states(state, _project_state()):
                events = await _drain(state.assign(1))

        apply.assert_not_awaited()
        assert events

    @pytest.mark.asyncio
    async def test_assign_with_form_error_does_not_save(self) -> None:
        state = _loaded_state()
        state.role_id = ""

        with patch(f"{MODULE}.apply_resource_plan", AsyncMock()) as apply:
            async with _patch_states(state, _project_state()):
                await _drain(state.assign(1))

        apply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_assign_error_toasts_instead_of_raising(self) -> None:
        state = _loaded_state()

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(
                f"{MODULE}.apply_resource_plan",
                AsyncMock(side_effect=RuntimeError("db down")),
            ),
        ):
            async with _patch_states(state, _project_state()):
                events = await _drain(state.assign(1))

        assert state.is_saving is False
        assert events

    @pytest.mark.asyncio
    async def test_delete_period(self) -> None:
        state = _loaded_state()
        key = state.periods[0].key
        state.edit_period(key)

        with (
            patch(f"{MODULE}.get_asyncdb_session", _mock_session_ctx(AsyncMock())),
            patch(
                f"{MODULE}.delete_resource_period", AsyncMock(return_value=2)
            ) as delete,
            patch(f"{MODULE}.capacity_allocation_repo") as alloc_repo,
            patch(f"{MODULE}.project_repo") as project_repo,
        ):
            alloc_repo.find_by_project = AsyncMock(return_value=[])
            project_repo.find_by_id = AsyncMock(return_value=None)
            async with _patch_states(state, _project_state()):
                await _drain(state.delete_period(key))

        assert delete.await_args is not None
        assert delete.await_args.args[1:] == (
            PlanTarget(project_id=1, employee_id=1, role_id=3),
            W1,
            date(2026, 9, 25),
        )
        assert state.allocations == []
        assert state.editing_key == ""

    @pytest.mark.asyncio
    async def test_delete_unknown_period_is_noop(self) -> None:
        state = _loaded_state()

        with patch(f"{MODULE}.delete_resource_period", AsyncMock()) as delete:
            async with _patch_states(state, _project_state()):
                await _drain(state.delete_period("nope"))

        delete.assert_not_awaited()


class TestComponent:
    """Smoke test for the tab component."""

    def test_ressourcen_tab_renders(self) -> None:
        assert isinstance(ressourcen_tab(), rx.Component)
