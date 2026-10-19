"""Department highlighting groups for the planning grid."""

from typing import TYPE_CHECKING

import reflex as rx
from alloq_project.states.planning_models import EmployeeBlock


class PlanningDepartmentMixin(rx.State, mixin=True):
    """Split visible planning employees by department highlight status."""

    if TYPE_CHECKING:
        filtered_employees: list[EmployeeBlock]

    unhighlighted_collapsed: rx.Field[bool] = rx.field(False)

    @rx.var(cache=True)
    def highlighted_employees(self) -> list[EmployeeBlock]:
        return [
            employee
            for employee in self.filtered_employees
            if employee.department_highlighted
        ]

    @rx.var(cache=True)
    def unhighlighted_employees(self) -> list[EmployeeBlock]:
        return [
            employee
            for employee in self.filtered_employees
            if not employee.department_highlighted
        ]

    @rx.event
    def toggle_unhighlighted(self) -> None:
        self.unhighlighted_collapsed = not self.unhighlighted_collapsed
