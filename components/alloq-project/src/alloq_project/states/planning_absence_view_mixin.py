"""Absence timeline of the planning page; mixed into `PlanningStore`."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import reflex as rx
from alloq_project.services.planning_gantt import build_absence_gantt
from alloq_project.states.planning_models import AbsenceGanttView

if TYPE_CHECKING:
    from alloq_commons.models.employee import Employee
    from alloq_project.states.planning_models import EmployeeBlock, WeekColumn

ABSENCE_VIEW = "Abwesenheiten"


class PlanningAbsenceViewMixin(rx.State, mixin=True):
    """Bars, week coverage and summaries of the absence view.

    A mixin rather than a substate: the view reads the shared filters, weeks
    and employee blocks of `PlanningStore`.
    """

    if TYPE_CHECKING:  # Provided by PlanningStore.
        view_mode: str
        weeks: list[WeekColumn]
        holiday_dates: list[dt.date]
        available_employees: list[Employee]
        employee_blocks: list[EmployeeBlock]

        def _filter_employees(
            self, blocks: list[EmployeeBlock], *, planning_filters: bool = True
        ) -> list[EmployeeBlock]: ...

    absence_show_all: rx.Field[bool] = rx.field(False)

    @rx.event
    def set_absence_show_all(self, value: bool) -> None:
        self.absence_show_all = value

    @rx.var(cache=True)
    def absence_gantt(self) -> AbsenceGanttView:
        if self.view_mode != ABSENCE_VIEW:
            return AbsenceGanttView()
        # Project and availability filters have no control in this view.
        return build_absence_gantt(
            self._filter_employees(self.employee_blocks, planning_filters=False),
            self.available_employees,
            self.weeks,
            holidays=self.holiday_dates,
            today=dt.datetime.now().date(),  # noqa: DTZ005
            show_all=self.absence_show_all,
        )
