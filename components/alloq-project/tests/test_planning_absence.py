"""Planning absence submission refreshes allocations only after a successful save."""

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_project.states.planning_absence_state import PlanningAbsenceState
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_team.states.team_state import TeamState


class _AdminLogin:
    @property
    async def authenticated_user(self) -> Any:
        return SimpleNamespace(user_id=1, is_admin=True)


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
