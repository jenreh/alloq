"""Absence actions of the planning page, built on the shared absence form."""

import datetime as dt
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.access import requires_editor
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_team.states.team_state import TeamState


class PlanningAbsenceState(rx.State):
    @rx.event
    @requires_editor
    async def create_absence(self, form_data: dict) -> AsyncGenerator[Any]:
        team = await self.get_state(TeamState)
        if not team.absence_modal_open:
            return
        async for event in team.create_absence(form_data):
            yield event
        if not team.absence_modal_open:
            yield PlanningStore.refresh

    @rx.event
    @requires_editor
    async def open_new_absence(self) -> AsyncGenerator[Any]:
        """Open the absence form without a preselected employee."""
        team = await self.get_state(TeamState)
        team.selected_employee = None
        team.open_absence_modal()
        yield

    @rx.event
    @requires_editor
    async def pick_employee(self, value: str | None) -> AsyncGenerator[Any]:
        """Choose the employee in the open form; the chosen dates stay."""
        if not value:
            return
        team = await self.get_state(TeamState)
        date_range = list(team.absence_date_range)
        async for event in team.select_employee_and_add_absence(int(value)):
            yield event
        team.absence_date_range = date_range

    @rx.event
    @requires_editor
    async def start_absence(
        self, employee_id: int, start_day: int, end_day: int
    ) -> AsyncGenerator[Any]:
        """Open the form for a range dragged on the absence timeline.

        Day numbers count from the first displayed day.
        """
        planning = await self.get_state(PlanningStore)
        horizon = planning.absence_gantt.horizon_start
        if not horizon:
            return
        first = dt.date.fromisoformat(horizon)
        start = first + dt.timedelta(days=min(start_day, end_day))
        end = first + dt.timedelta(days=max(start_day, end_day))
        if start < dt.datetime.now(tz=dt.UTC).date():
            yield rx.toast.error(
                "Abwesenheiten dürfen nicht in der Vergangenheit beginnen.",
                position="top-right",
            )
            return
        team = await self.get_state(TeamState)
        async for event in team.select_employee_and_add_absence(employee_id):
            yield event
        team.absence_date_range = [start.isoformat(), end.isoformat()]

    @rx.event
    @requires_editor
    async def delete_absence(self, absence_id: int) -> AsyncGenerator[Any]:
        team = await self.get_state(TeamState)
        async for event in team.delete_absence(absence_id):
            yield event
        yield PlanningStore.refresh
