"""Connect the shared absence form to the planning refresh."""

from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_team.states.team_state import TeamState

from appkit_user.authentication.decorators import requires_admin


class PlanningAbsenceState(rx.State):
    @rx.event
    @requires_admin
    async def create_absence(self, form_data: dict) -> AsyncGenerator[Any]:
        team = await self.get_state(TeamState)
        if not team.absence_modal_open:
            return
        async for event in team.create_absence(form_data):
            yield event
        if not team.absence_modal_open:
            yield PlanningStore.refresh
