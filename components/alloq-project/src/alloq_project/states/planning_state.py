import logging
from typing import Any

import reflex as rx
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_commons.models.role import Role
from alloq_commons.repositories import employee_repo, project_repo, role_repo
from alloq_project.states.planning_grid_state import PlanningGridState
from alloq_project.states.planning_project_view_state import (
    PlanningProjectViewState,
)

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.states import UserSession

logger = logging.getLogger(__name__)


class PlanningState(UserSession):
    """State for the resource planning page."""

    view_mode: str = "Grid"
    time_range: str = "3 Monate"

    # Data
    available_projects: list[Project] = []  # non-Abgeschlossen, used for grid
    all_projects: list[Project] = []  # all states, used for filter dropdown
    available_employees: list[Employee] = []
    available_roles: list[Role] = []

    is_loading: bool = False

    def set_view_mode(self, value: str) -> None:
        self.view_mode = value

    def set_time_range(self, value: str) -> Any:
        self.time_range = value
        return [
            PlanningGridState.reload_with_time_range(value),
            PlanningProjectViewState.reload_with_time_range(value),
        ]

    @rx.var(cache=True)
    def project_select_options(self) -> list[dict[str, str]]:
        """Return all projects formatted for Mantine multi-select."""
        return [
            {"value": str(p.id), "label": p.name_de or p.code}
            for p in self.all_projects
        ]

    @rx.var(cache=True)
    def employee_select_options(self) -> list[dict[str, str]]:
        """Return employees formatted for Mantine multi-select."""
        return [
            {"value": str(e.id), "label": f"{e.first_name} {e.last_name}"}
            for e in self.available_employees
        ]

    @rx.var(cache=True)
    def role_select_options(self) -> list[dict[str, str]]:
        """Return roles formatted for Mantine multi-select."""
        return [{"value": str(r.id), "label": r.name} for r in self.available_roles]

    async def load_planning_data(self) -> None:
        """Load necessary data for planning: roles, employees, and active projects."""
        self.is_loading = True
        yield

        async with get_asyncdb_session() as session:
            # Load all projects
            projects = await project_repo.find_all(session)
            all_proj = [Project(**p.to_dict()) for p in projects]
            all_proj.sort(key=lambda p: (p.name_de or p.code).lower())
            self.all_projects = all_proj
            self.available_projects = [
                p for p in all_proj if p.state != "Abgeschlossen"
            ]

            # Load employees
            employees = await employee_repo.find_all(session)
            self.available_employees = [Employee(**e.to_dict()) for e in employees]
            self.available_employees.sort(key=lambda e: (e.last_name, e.first_name))

            # Load roles
            roles = await role_repo.find_all(session)
            self.available_roles = [Role(**r.to_dict()) for r in roles]
            self.available_roles.sort(key=lambda r: r.name)

        self.is_loading = False
        yield
