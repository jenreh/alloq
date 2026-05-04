import logging
from typing import Any

import reflex as rx
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_commons.models.role import Role
from alloq_commons.repositories import employee_repo, project_repo, role_repo
from alloq_project.states.planning_grid_state import PlanningGridState

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.states import UserSession

logger = logging.getLogger(__name__)


class PlanningState(UserSession):
    """State for the resource planning page."""

    view_mode: str = "Grid"
    time_range: str = "3 Monate"

    project_scope: bool = False  # False = "Alle Projekte", True = "Meine Projekte"
    employee_scope: bool = (
        False  # False = "Alle Mitarbeiter", True = "Meine Mitarbeiter"
    )

    role_filter: str = "all"
    project_filter: str = "all"
    employee_filter: str = "all"

    search_query: str = ""

    # Data
    available_projects: list[Project] = []
    available_employees: list[Employee] = []
    available_roles: list[Role] = []

    is_loading: bool = False

    def set_view_mode(self, value: str) -> None:
        self.view_mode = value

    def set_time_range(self, value: str) -> Any:
        self.time_range = value
        return PlanningGridState.reload_with_time_range(value)

    def toggle_project_scope(self) -> None:
        self.project_scope = not self.project_scope

    def toggle_employee_scope(self) -> None:
        self.employee_scope = not self.employee_scope

    def set_role_filter(self, value: str) -> None:
        self.role_filter = value

    def set_project_filter(self, value: str) -> None:
        self.project_filter = value

    def set_employee_filter(self, value: str) -> None:
        self.employee_filter = value

    def set_search_query(self, value: str) -> None:
        self.search_query = value

    @rx.var(cache=True)
    def project_select_options(self) -> list[dict[str, str]]:
        """Return projects formatted for Mantine select."""
        options = [{"value": "all", "label": "Alle Projekte"}]
        options.extend(
            [{"value": str(p.id), "label": p.name_de} for p in self.available_projects]
        )
        return options

    @rx.var(cache=True)
    def employee_select_options(self) -> list[dict[str, str]]:
        """Return employees formatted for Mantine select."""
        options = [{"value": "all", "label": "Alle Mitarbeiter"}]
        options.extend(
            [
                {"value": str(e.id), "label": f"{e.first_name} {e.last_name}"}
                for e in self.available_employees
            ]
        )
        return options

    @rx.var(cache=True)
    def role_select_options(self) -> list[dict[str, str]]:
        """Return roles formatted for Mantine select."""
        options = [{"value": "all", "label": "Alle Rollen"}]
        options.extend(
            [{"value": str(r.id), "label": r.name} for r in self.available_roles]
        )
        return options

    async def load_planning_data(self) -> None:
        """Load necessary data for planning: roles, employees, and active projects."""
        self.is_loading = True
        yield

        async with get_asyncdb_session() as session:
            # Load active projects (not "Abgeschlossen")
            projects = await project_repo.find_all(session)
            self.available_projects = [
                Project(**p.to_dict()) for p in projects if p.state != "Abgeschlossen"
            ]
            self.available_projects.sort(key=lambda p: p.name_de.lower())

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
