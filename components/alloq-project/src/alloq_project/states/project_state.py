import logging
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import reflex as rx
from alloq_commons.entities import ProjectEntity, ProjectStatusEntity
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.entities.required_capacity import RequiredCapacityEntity
from alloq_commons.models.project import (
    Capacity,
    Project,
    ProjectCreate,
    ProjectStatus,
    RequiredCapacity,
    RequiredCapacityCreate,
    Risk,
)
from alloq_commons.models.role import Role
from alloq_commons.repositories import (
    capacity_repo,
    employee_repo,
    project_repo,
    required_capacity_repo,
    risk_repo,
    role_repo,
    status_repo,
)

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import is_authenticated
from appkit_user.authentication.states import UserSession

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_COLOR = "#F7C948"
PROJECT_COLORS = [
    "#F7C948",
    "#7A9A80",
    "#5B7FA3",
    "#D07A55",
    "#C49000",
    "#8D6AA5",
    "#5C9AA4",
    "#B45F83",
    "#6A961E",
    "#3F6070",
]


class ProjectState(UserSession):
    """State for project management."""

    projects: list[Project] = []
    selected_project: Project | None = None
    statuses: list[ProjectStatus] = []
    risks: list[Risk] = []
    capacities: list[Capacity] = []
    required_capacities: list[RequiredCapacity] = []
    available_roles: list[Role] = []
    available_employees: list[dict[str, str]] = []
    is_loading: bool = False

    current_user_email: str = ""
    current_employee_id: int | None = None

    add_modal_open: bool = False
    detail_drawer_open: bool = False

    search_filter: str = ""
    status_filter: str = "all"
    view_mode: str = "grid"

    @rx.var(cache=False)
    def current_date(self) -> str:
        """Return the current date for status defaults."""
        return datetime.now(tz=UTC).date().isoformat()

    def set_search_filter(self, value: str) -> None:
        """Update the search filter."""
        self.search_filter = value

    def set_status_filter(self, value: str) -> None:
        """Update the status filter."""
        self.status_filter = value or "all"

    def set_view_mode(self, mode: str) -> None:
        """Set view mode. Currently only grid is rendered."""
        self.view_mode = mode

    @rx.var
    def filtered_projects(self) -> list[Project]:
        """Return projects filtered by search text and status."""
        projects = self.projects
        if self.search_filter:
            search = self.search_filter.lower()
            projects = [
                project
                for project in projects
                if search in project.code.lower() or search in project.name_de.lower()
            ]

        if self.status_filter != "all":
            projects = [
                project for project in projects if project.state == self.status_filter
            ]

        return projects

    @rx.var
    def my_projects(self) -> list[Project]:
        """Return filtered projects where the current user is project lead."""
        if not self.current_employee_id:
            return []
        return [
            p for p in self.filtered_projects if self.current_employee_id in p.owner_ids
        ]

    @rx.var
    def other_projects(self) -> list[Project]:
        """Return filtered projects where the current user is NOT project lead."""
        if not self.current_employee_id:
            return self.filtered_projects
        return [
            p
            for p in self.filtered_projects
            if self.current_employee_id not in p.owner_ids
        ]

    @rx.var
    def role_select_options(self) -> list[dict[str, str]]:
        """Return roles formatted for Mantine select data props."""
        return [
            {"value": str(role.id), "label": role.name} for role in self.available_roles
        ]

    @rx.var
    def employee_select_options(self) -> list[dict[str, str]]:
        """Return employees formatted for Mantine select data props."""
        return self.available_employees

    @rx.var
    def state_select_options(self) -> list[dict[str, str]]:
        """Return project states formatted for Mantine select."""
        return [
            {"value": state.value, "label": state.value} for state in ProjectStateEnum
        ]

    def open_add_modal(self) -> list[rx.event.EventSpec]:
        """Open the add project modal."""
        self.add_modal_open = True
        return [ProjectValidationState.initialize()]

    def close_add_modal(self) -> None:
        """Close the add project modal."""
        self.add_modal_open = False

    def close_detail_drawer(self) -> None:
        """Close the detail drawer."""
        self.detail_drawer_open = False
        self.selected_project = None
        self.statuses = []
        self.risks = []
        self.capacities = []
        self.required_capacities = []

    async def _load_projects(self) -> None:
        """Load projects from the database."""
        async with get_asyncdb_session() as session:
            entities = await project_repo.find_all_with_stats(
                session,
                search=self.search_filter or None,
            )
            projects = [Project(**entity.to_dict()) for entity in entities]
            self.projects = sorted(projects, key=lambda p: p.name_de.lower())

    async def _load_reference_data(self) -> None:
        """Load roles and employees for form controls."""
        async with get_asyncdb_session() as session:
            role_entities = await role_repo.find_all_paginated(session)
            self.available_roles = sorted(
                [Role(**entity.to_dict()) for entity in role_entities],
                key=lambda r: r.name,
            )

            employee_entities = await employee_repo.find_all_paginated(session)
            self.available_employees = [
                {
                    "value": str(entity.id),
                    "label": f"{entity.first_name} {entity.last_name}",
                }
                for entity in employee_entities
            ]

    @is_authenticated
    async def load_projects(self) -> AsyncGenerator[Any, None]:
        """Load all projects and form reference data."""
        self.is_loading = True
        yield
        try:
            user = await self.authenticated_user
            if user and user.email:
                self.current_user_email = user.email
                async with get_asyncdb_session() as session:
                    employee = await employee_repo.find_by_email(session, user.email)
                    self.current_employee_id = employee.id if employee else None
            await self._load_projects()
            await self._load_reference_data()
        finally:
            self.is_loading = False

    @is_authenticated
    async def select_project(self, project_id: int) -> AsyncGenerator[Any, None]:
        """Select a project and load drawer details."""
        async with get_asyncdb_session() as session:
            entity = await project_repo.find_by_id(session, project_id)
            if not entity:
                yield rx.toast.error("Projekt nicht gefunden.", position="top-right")
                return

            self.selected_project = Project(**entity.to_dict())
            status_entities = await status_repo.find_by_project_id(session, project_id)
            risk_entities = await risk_repo.find_by_project_id(session, project_id)
            capacity_entities = await capacity_repo.find_by_project_id(
                session,
                project_id,
            )
            required_entities = await required_capacity_repo.find_by_project_id(
                session,
                project_id,
            )
            self.statuses = [
                ProjectStatus(**status.to_dict()) for status in status_entities
            ]
            self.risks = [Risk(**risk.to_dict()) for risk in risk_entities]
            self.capacities = [
                Capacity(**capacity.to_dict()) for capacity in capacity_entities
            ]
            self.required_capacities = [
                RequiredCapacity(**capacity.to_dict()) for capacity in required_entities
            ]
            self.detail_drawer_open = True
            yield

    @is_authenticated
    async def create_project(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Create a project with required capacity rows."""
        self.is_loading = True
        yield
        try:
            project_data = self._project_create_from_form(form_data)
            async with get_asyncdb_session() as session:
                entity = ProjectEntity(
                    code=project_data.code,
                    name_de=project_data.name_de,
                    start_date=project_data.start_date,
                    end_date=project_data.end_date,
                    state=project_data.state,
                    budget=project_data.budget,
                    color=project_data.color,
                )

                if project_data.owner_ids:
                    for emp_id in project_data.owner_ids:
                        employee = await employee_repo.find_by_id(session, emp_id)
                        if employee:
                            entity.owners.append(employee)

                await project_repo.create(session, entity)
                await status_repo.create(
                    session,
                    ProjectStatusEntity(
                        project_id=entity.id,
                        status_date=datetime.now(tz=UTC).date(),
                        fortschritt=0,
                        budget_verbrauch=0,
                    ),
                )
                for capacity in project_data.required_capacities:
                    await required_capacity_repo.create(
                        session,
                        RequiredCapacityEntity(
                            project_id=entity.id,
                            role_id=capacity.role_id,
                            person_days=capacity.person_days,
                        ),
                    )
                await session.commit()

            await self._load_projects()
            self.close_add_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Projekt '{project_data.code}' erstellt.",
                position="top-right",
            )
        except Exception as exc:
            logger.error("Failed to create project: %s", exc)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Erstellen: {exc}",
                position="top-right",
            )

    @is_authenticated
    async def delete_project(self, project_id: int) -> AsyncGenerator[Any, None]:
        """Delete a project by ID."""
        self.is_loading = True
        yield
        try:
            async with get_asyncdb_session() as session:
                deleted = await project_repo.delete_by_id(session, project_id)
                if not deleted:
                    self.is_loading = False
                    yield rx.toast.error(
                        "Projekt nicht gefunden.", position="top-right"
                    )
                    return
                await session.commit()

            await self._load_projects()
            self.close_detail_drawer()
            self.is_loading = False
            yield rx.toast.info("Projekt gelöscht.", position="top-right")
        except Exception as exc:
            logger.error("Failed to delete project: %s", exc)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Löschen: {exc}",
                position="top-right",
            )

    def _project_create_from_form(self, form_data: dict) -> ProjectCreate:
        """Convert form submission data into a create model."""
        raw_ids = form_data.get("owner_ids", [])
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]

        owner_ids = [
            int(emp_id.strip())
            for item in raw_ids
            for emp_id in str(item).split(",")
            if emp_id.strip()
        ]

        required_capacities = self._required_capacities_from_form(form_data)
        return ProjectCreate(
            code=str(form_data.get("code", "")).strip(),
            name_de=str(form_data.get("name_de", "")).strip(),
            start_date=date.fromisoformat(str(form_data.get("start_date", ""))[:10]),
            end_date=date.fromisoformat(str(form_data.get("end_date", ""))[:10]),
            state=str(form_data.get("state", ProjectStateEnum.PLANNED.value)),
            budget=int(float(form_data.get("budget", 0) or 0)),
            color=str(form_data.get("color", DEFAULT_PROJECT_COLOR)),
            owner_ids=owner_ids,
            required_capacities=required_capacities,
        )

    def _required_capacities_from_form(
        self,
        form_data: dict,
    ) -> list[RequiredCapacityCreate]:
        """Extract required capacity inputs from form data."""
        capacities = []
        for role in self.available_roles:
            raw_value = form_data.get(f"required_capacity_{role.id}", "")
            if raw_value in (None, ""):
                continue
            person_days = int(float(raw_value or 0))
            if person_days <= 0:
                continue
            capacities.append(
                RequiredCapacityCreate(
                    role_id=role.id,
                    person_days=person_days,
                )
            )
        return capacities


class ProjectValidationState(rx.State):
    """Validation state for project add forms."""

    code: str = ""
    name_de: str = ""
    start_date: str = ""
    end_date: str = ""
    state: str = ProjectStateEnum.PLANNED.value
    budget: str = "0"
    color: str = DEFAULT_PROJECT_COLOR
    owner_ids: list[str] = []

    code_error: str = ""
    name_de_error: str = ""
    date_error: str = ""
    budget_error: str = ""

    @rx.event
    def initialize(self, project: Project | None = None) -> None:
        """Reset validation state for add mode or preload from a project."""
        if project is None:
            self.code = ""
            self.name_de = ""
            self.start_date = ""
            self.end_date = ""
            self.state = ProjectStateEnum.PLANNED.value
            self.budget = "0"
            self.color = DEFAULT_PROJECT_COLOR
            self.owner_ids = []
        else:
            self.code = project.code
            self.name_de = project.name_de
            self.start_date = (
                project.start_date.isoformat() if project.start_date else ""
            )
            self.end_date = project.end_date.isoformat() if project.end_date else ""
            self.state = project.state
            self.budget = str(project.budget)
            self.color = project.color
            self.owner_ids = [str(oid) for oid in project.owner_ids]

        self.code_error = ""
        self.name_de_error = ""
        self.date_error = ""
        self.budget_error = ""

    def set_code(self, value: str) -> None:
        self.code = value
        self.validate_code()

    def set_name_de(self, value: str) -> None:
        self.name_de = value
        self.validate_name_de()

    def set_start_date(self, value: str) -> None:
        self.start_date = value or ""
        self.validate_dates()

    def set_end_date(self, value: str) -> None:
        self.end_date = value or ""
        self.validate_dates()

    def set_state(self, value: str) -> None:
        self.state = value or ProjectStateEnum.PLANNED.value

    def set_budget(self, value: str | float) -> None:
        self.budget = str(value)
        self.validate_budget()

    def set_color(self, value: str) -> None:
        self.color = value

    def set_owner_ids(self, value: list[str]) -> None:
        self.owner_ids = value or []

    @rx.event
    def validate_code(self) -> None:
        self.code_error = "" if self.code.strip() else "Projekt-Code ist erforderlich."

    @rx.event
    def validate_name_de(self) -> None:
        self.name_de_error = (
            "" if self.name_de.strip() else "Name (DE) ist erforderlich."
        )

    @rx.event
    def validate_dates(self) -> None:
        if not self.start_date or not self.end_date:
            self.date_error = "Start und Ende sind erforderlich."
            return
        try:
            if date.fromisoformat(self.end_date[:10]) < date.fromisoformat(
                self.start_date[:10]
            ):
                self.date_error = "Ende darf nicht vor Start liegen."
            else:
                self.date_error = ""
        except ValueError:
            self.date_error = "Bitte gültige Daten auswählen."

    @rx.event
    def validate_budget(self) -> None:
        try:
            if int(float(self.budget or 0)) < 0:
                self.budget_error = "Budget darf nicht negativ sein."
            else:
                self.budget_error = ""
        except ValueError:
            self.budget_error = "Budget muss eine gültige Zahl sein."

    @rx.var
    def has_errors(self) -> bool:
        return bool(
            self.code_error
            or self.name_de_error
            or self.date_error
            or self.budget_error
        )

    @rx.var
    def is_form_valid(self) -> bool:
        """Check if required fields are complete and valid."""
        try:
            budget_valid = int(float(self.budget or 0)) >= 0
            dates_valid = bool(self.start_date and self.end_date)
            if dates_valid:
                dates_valid = date.fromisoformat(
                    self.end_date[:10]
                ) >= date.fromisoformat(self.start_date[:10])
        except ValueError:
            budget_valid = False
            dates_valid = False

        return bool(
            self.code.strip()
            and self.name_de.strip()
            and budget_valid
            and dates_valid
            and not self.has_errors
        )

    @rx.var
    def is_form_invalid(self) -> bool:
        return not self.is_form_valid
