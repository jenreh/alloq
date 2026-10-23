"""Planning absence submission refreshes allocations only after a successful save."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.roles import EMPLOYEE_ROLE, PROJECT_MANAGER_ROLE
from alloq_project.states.planning_absence_state import PlanningAbsenceState
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_team.states.team_state import TeamState

# Allowed fakes hold the roles; the admin switch grants no planning access.
_PLANNER_ROLES = [PROJECT_MANAGER_ROLE.name, EMPLOYEE_ROLE.name]


class _AdminLogin:
    @property
    async def authenticated_user(self) -> Any:
        return SimpleNamespace(user_id=1, is_admin=True, roles=_PLANNER_ROLES)


def _get_state(team: SimpleNamespace) -> AsyncMock:
    return AsyncMock(
        side_effect=lambda cls: team if cls is TeamState else _AdminLogin()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("saved", [True, False])
async def test_refresh_only_after_saved_absence(saved: bool) -> None:
    state = PlanningAbsenceState()
    team = SimpleNamespace(absence_modal_open=True)
    form_data = {"date_range": ""}
    submitted: list[dict[str, Any]] = []

    async def create_absence(data: dict[str, Any]) -> AsyncGenerator[Any]:
        submitted.append(data)
        team.absence_modal_open = not saved
        yield None

    team.create_absence = create_absence
    with patch.object(PlanningAbsenceState, "get_state", _get_state(team)):
        events = [event async for event in state.create_absence(form_data)]

    assert submitted == [form_data]
    assert (PlanningStore.refresh in events) is saved


@pytest.mark.asyncio
async def test_closed_absence_modal_does_not_submit() -> None:
    state = PlanningAbsenceState()
    create = AsyncMock()
    team = SimpleNamespace(absence_modal_open=False, create_absence=create)
    with patch.object(PlanningAbsenceState, "get_state", _get_state(team)):
        events = [event async for event in state.create_absence({})]

    create.assert_not_called()
    assert events == []


def _get_states(team: SimpleNamespace, planning: SimpleNamespace) -> AsyncMock:
    def pick(cls: type) -> Any:
        if cls is TeamState:
            return team
        if cls is PlanningStore:
            return planning
        return _AdminLogin()

    return AsyncMock(side_effect=pick)


def _team(range_: list[str] | None = None) -> SimpleNamespace:
    team = SimpleNamespace(
        absence_date_range=range_ or [],
        absence_modal_open=False,
        selected_employee="old",
        selected_ids=[],
    )

    async def select(employee_id: int) -> AsyncGenerator[Any]:
        team.selected_ids.append(employee_id)
        team.absence_date_range = []
        team.absence_modal_open = True
        yield None

    def open_modal() -> None:
        team.absence_date_range = []
        team.absence_modal_open = True

    team.select_employee_and_add_absence = select
    team.open_absence_modal = open_modal
    return team


def _planning(horizon: str) -> SimpleNamespace:
    return SimpleNamespace(absence_gantt=SimpleNamespace(horizon_start=horizon))


@pytest.mark.asyncio
async def test_drag_opens_modal_with_employee_and_dates() -> None:
    state = PlanningAbsenceState()
    team = _team()
    with patch.object(
        PlanningAbsenceState, "get_state", _get_states(team, _planning("2099-01-05"))
    ):
        _ = [event async for event in state.start_absence(7, 11, 7)]

    assert team.selected_ids == [7]
    assert team.absence_modal_open
    assert team.absence_date_range == ["2099-01-12", "2099-01-16"]


@pytest.mark.asyncio
async def test_drag_into_the_past_is_rejected() -> None:
    state = PlanningAbsenceState()
    team = _team()
    with patch.object(
        PlanningAbsenceState, "get_state", _get_states(team, _planning("2020-01-06"))
    ):
        events = [event async for event in state.start_absence(7, 0, 2)]

    assert team.selected_ids == []
    assert not team.absence_modal_open
    assert len(events) == 1


@pytest.mark.asyncio
async def test_new_absence_starts_without_employee() -> None:
    state = PlanningAbsenceState()
    team = _team(["2099-01-12", "2099-01-16"])
    with patch.object(
        PlanningAbsenceState, "get_state", _get_states(team, _planning(""))
    ):
        _ = [event async for event in state.open_new_absence()]

    assert team.selected_employee is None
    assert team.absence_modal_open
    assert team.absence_date_range == []


@pytest.mark.asyncio
async def test_picking_an_employee_keeps_the_chosen_dates() -> None:
    state = PlanningAbsenceState()
    team = _team(["2099-01-12", "2099-01-16"])
    with patch.object(
        PlanningAbsenceState, "get_state", _get_states(team, _planning(""))
    ):
        _ = [event async for event in state.pick_employee("4")]
        _ = [event async for event in state.pick_employee("")]

    assert team.selected_ids == [4]
    assert team.absence_date_range == ["2099-01-12", "2099-01-16"]


@pytest.mark.asyncio
async def test_delete_absence_refreshes_planning() -> None:
    state = PlanningAbsenceState()
    team = _team()
    deleted: list[int] = []

    async def delete(absence_id: int) -> AsyncGenerator[Any]:
        deleted.append(absence_id)
        yield None

    team.delete_absence = delete
    with patch.object(
        PlanningAbsenceState, "get_state", _get_states(team, _planning(""))
    ):
        events = [event async for event in state.delete_absence(21)]

    assert deleted == [21]
    assert PlanningStore.refresh in events
