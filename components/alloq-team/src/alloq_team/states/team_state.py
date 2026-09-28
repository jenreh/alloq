import logging
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import reflex as rx
from alloq_commons.entities.absence import AbsenceEntity
from alloq_commons.entities.capacity import CapacityEntity
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.models.employee import (
    Absence,
    AbsenceCreate,
    Employee,
    EmployeeCreate,
)
from alloq_commons.models.project import Capacity, Project
from alloq_commons.models.role import Role
from alloq_commons.models.view_mode import VIEW_MODE_GRID, VIEW_MODES
from alloq_commons.repositories.absence_repository import absence_repo
from alloq_commons.repositories.capacity_allocation_repository import (
    capacity_allocation_repo,
)
from alloq_commons.repositories.capacity_repository import capacity_repo
from alloq_commons.repositories.employee_repository import employee_repo
from alloq_commons.repositories.project_repository import project_repo
from alloq_commons.repositories.role_repository import role_repo
from alloq_commons.services.quick_project import (
    NEW_PROJECT_OPTION,
    NEW_PROJECT_VALUE,
    QuickProjectError,
    create_quick_project,
)

from appkit_commons.database.session import get_asyncdb_session
from appkit_ui.global_states import LoadingState
from appkit_user.authentication.decorators import requires_admin
from appkit_user.authentication.states import UserSession

logger = logging.getLogger(__name__)

# Upper bound for the list queries backing the team page and its dropdowns
# (the repositories default to 200). Matches the dashboard's limit.
LIST_LIMIT = 1000


def _employee_from_form(form_data: dict) -> EmployeeCreate:
    """Parse the add/edit employee form into an EmployeeCreate model."""
    raw_roles = form_data.get("role_ids", [])
    if isinstance(raw_roles, str):
        role_ids = [int(x) for x in raw_roles.split(",") if x]
    else:
        role_ids = [int(x) for x in raw_roles]

    manager_id_raw = form_data.get("manager_id")
    return EmployeeCreate(
        first_name=form_data.get("first_name", "").strip(),
        last_name=form_data.get("last_name", "").strip(),
        email=form_data.get("email", "").strip() or None,
        seniority=form_data.get("seniority", "Advanced"),
        job_title=form_data.get("job_title", "").strip() or None,
        location=form_data.get("location", "").strip() or None,
        manager_id=int(manager_id_raw) if manager_id_raw else None,
        role_ids=role_ids,
        hours_per_week=float(form_data.get("hours_per_week", 40.0)),
        # The field is optional in the form; a cleared input posts "".
        internal_hours=int(form_data.get("internal_hours") or 0),
    )


def _parse_date_range(values: list[str]) -> tuple[date, date] | None:
    """Parse a [start, end] ISO date pair; None if missing, malformed or reversed."""
    if len(values) < 2 or not values[0] or not values[1]:  # noqa: PLR2004
        return None
    try:
        start = date.fromisoformat(values[0][:10])
        end = date.fromisoformat(values[1][:10])
    except ValueError:
        return None
    return (start, end) if start <= end else None


class TeamState(UserSession):
    """State for team member management."""

    employees: rx.Field[list[Employee]] = rx.field(default_factory=list)
    selected_employee: rx.Field[Employee | None] = rx.field(None)
    absences: rx.Field[list[Absence]] = rx.field(default_factory=list)
    available_roles: rx.Field[list[Role]] = rx.field(default_factory=list)
    is_loading: rx.Field[bool] = rx.field(False)

    current_user_email: rx.Field[str] = rx.field("")
    current_employee_id: rx.Field[int | None] = rx.field(None)

    add_modal_open: rx.Field[bool] = rx.field(False)
    detail_drawer_open: rx.Field[bool] = rx.field(False)
    absence_modal_open: rx.Field[bool] = rx.field(False)
    absence_date_range: rx.Field[list[str]] = rx.field(default_factory=list)

    search_filter: rx.Field[str] = rx.field("")
    view_mode: str = rx.LocalStorage(VIEW_MODE_GRID, name="alloq_team_view_mode")
    expanded_sections: rx.Field[list[str]] = rx.field(default_factory=list)

    all_projects: rx.Field[list[Project]] = rx.field(default_factory=list)
    employee_capacities: rx.Field[list[Capacity]] = rx.field(default_factory=list)
    add_project_modal_open: rx.Field[bool] = rx.field(False)
    add_project_selected: rx.Field[str] = rx.field("")
    quick_project_name: rx.Field[str] = rx.field("")
    quick_project_code: rx.Field[str] = rx.field("")
    is_quick_creating: rx.Field[bool] = rx.field(False)

    @rx.event
    def toggle_section_expanded(self, section_key: str) -> None:
        """Toggle the expanded state of all cards in an employee section."""
        if section_key in self.expanded_sections:
            self.expanded_sections = [
                s for s in self.expanded_sections if s != section_key
            ]
        else:
            self.expanded_sections = [*self.expanded_sections, section_key]

    @rx.var(cache=False)
    def current_date(self) -> str:
        """Get the current date as an ISO string for form boundaries."""
        return datetime.now(tz=UTC).date().isoformat()

    @rx.event
    def set_absence_date_range(self, value: list[str]) -> None:
        """Set the absence date range."""
        self.absence_date_range = value

    @rx.event
    def set_search_filter(self, value: str) -> None:
        """Update the search filter."""
        self.search_filter = value

    @rx.event
    def set_view_mode(self, mode: str) -> None:
        """Switch between grid and table view; unknown modes are ignored."""
        if mode in VIEW_MODES:
            self.view_mode = mode

    @rx.var
    def filtered_employees(self) -> list[Employee]:
        """Return employees filtered by search text."""
        if not self.search_filter:
            return self.employees
        search = self.search_filter.lower()
        return [
            e
            for e in self.employees
            if search in e.first_name.lower()
            or search in e.last_name.lower()
            or any(search in rn.lower() for rn in e.role_names)
        ]

    @rx.var
    def my_employees(self) -> list[Employee]:
        """Return employees reporting to the current user."""
        if not self.current_employee_id:
            return []
        return [
            e
            for e in self.filtered_employees
            if e.manager_id == self.current_employee_id
        ]

    @rx.var
    def other_employees(self) -> list[Employee]:
        """Return employees NOT reporting to the current user."""
        if not self.current_employee_id:
            return self.filtered_employees
        return [
            e
            for e in self.filtered_employees
            if e.manager_id != self.current_employee_id
        ]

    @rx.var
    def role_select_options(self) -> list[dict[str, str]]:
        """Return roles formatted for Mantine Select data prop."""
        return [{"value": str(r.id), "label": r.name} for r in self.available_roles]

    @rx.var
    def employee_role_select_options(self) -> list[dict[str, str]]:
        """Return only roles assigned to the selected employee."""
        if not self.selected_employee:
            return []
        emp_role_ids = set(self.selected_employee.role_ids)
        return [
            {"value": str(r.id), "label": r.name}
            for r in self.available_roles
            if r.id in emp_role_ids
        ]

    @rx.var
    def employee_select_options(self) -> list[dict[str, str]]:
        """Return possible managers, excluding the employee being edited."""
        selected_id = self.selected_employee.id if self.selected_employee else None
        return [
            {"value": str(e.id), "label": f"{e.first_name} {e.last_name}"}
            for e in self.employees
            if e.id != selected_id
        ]

    @rx.var
    def form_role_ids(self) -> list[str]:
        """Convert selected employee role IDs to strings for multi-select."""
        if self.selected_employee:
            return [str(role_id) for role_id in self.selected_employee.role_ids]
        return []

    @rx.var
    def unassigned_project_options(self) -> list[dict[str, str]]:
        """Projects not yet assigned to the selected employee."""
        assigned_ids = {c.project_id for c in self.employee_capacities}
        return [
            NEW_PROJECT_OPTION,
            *(
                {"value": str(p.id), "label": f"{p.code} - {p.name_de}"}
                for p in self.all_projects
                if p.id not in assigned_ids
            ),
        ]

    @rx.var
    def quick_create_active(self) -> bool:
        """True while the inline quick-create fields should be shown."""
        return self.add_project_selected == NEW_PROJECT_VALUE

    @rx.event
    def set_add_project_selected(self, value: str) -> None:
        """Store the selected project option."""
        self.add_project_selected = value or ""

    @rx.event
    def set_quick_project_name(self, value: str) -> None:
        """Store the typed name for the project to be quick-created."""
        self.quick_project_name = value

    @rx.event
    def set_quick_project_code(self, value: str) -> None:
        """Store the typed code for the project to be quick-created."""
        self.quick_project_code = value

    def _reset_quick_create(self) -> None:
        """Clear the project selection and inline quick-create fields."""
        self.add_project_selected = ""
        self.quick_project_name = ""
        self.quick_project_code = ""
        self.is_quick_creating = False

    @rx.event
    @requires_admin
    async def open_add_project_modal(self) -> AsyncGenerator[Any]:
        """Open the add-project-to-employee modal and load the project options."""
        self._reset_quick_create()
        self.add_project_modal_open = True
        yield
        await self._load_all_projects()

    @rx.event
    def close_add_project_modal(self) -> None:
        """Close the add-project-to-employee modal."""
        self.add_project_modal_open = False
        self._reset_quick_create()

    @rx.event
    def open_add_modal(self) -> list[Any]:
        """Open the add employee modal."""
        # A stale selection would be excluded from the e-mail uniqueness check.
        self.selected_employee = None
        self.add_modal_open = True
        return [EmployeeValidationState.initialize()]

    @rx.event
    def close_add_modal(self) -> None:
        """Close the add employee modal."""
        self.add_modal_open = False

    @rx.event
    def close_detail_drawer(self) -> None:
        """Close the detail drawer."""
        self.detail_drawer_open = False
        self.selected_employee = None
        self.absences = []

    @rx.event
    def open_absence_modal(self) -> None:
        """Open the absence add modal."""
        self.absence_date_range = []
        self.absence_modal_open = True

    @rx.event
    def close_absence_modal(self) -> None:
        """Close the absence modal."""
        self.absence_modal_open = False
        self.absence_date_range = []

    async def _load_employees(self) -> None:
        """Internal load logic for employees with role names."""
        async with get_asyncdb_session() as session:
            entities = await employee_repo.find_all_paginated(session, limit=LIST_LIMIT)
            self.employees = [Employee(**e.to_dict()) for e in entities]

    async def _fetch_employee(self, employee_id: int) -> Employee | None:
        """Fetch a single employee as an Employee read model."""
        async with get_asyncdb_session() as session:
            entity = await employee_repo.find_by_id(session, employee_id)
            if not entity:
                return None
            return Employee(**entity.to_dict())

    def _upsert_employee(self, employee: Employee) -> None:
        """Insert or replace an employee in the list, preserving sort order."""
        updated = [e for e in self.employees if e.id != employee.id]
        updated.append(employee)
        updated.sort(key=lambda e: (e.last_name.lower(), e.first_name.lower()))
        self.employees = updated

    async def _load_available_roles(self) -> None:
        """Load roles for dropdown selection."""
        async with get_asyncdb_session() as session:
            entities = await role_repo.find_all_paginated(session)
            self.available_roles = [Role(**e.to_dict()) for e in entities]

    @rx.event
    @requires_admin
    async def load_employees(self) -> AsyncGenerator[Any]:
        """Load all employees from the database."""
        self.is_loading = True
        yield
        try:
            user = await self.authenticated_user
            if user and user.email:
                self.current_user_email = user.email
                async with get_asyncdb_session() as session:
                    employee = await employee_repo.find_by_email(session, user.email)
                    self.current_employee_id = employee.id if employee else None
            await self._load_employees()
            await self._load_available_roles()
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def select_employee(self, employee_id: int) -> AsyncGenerator[Any]:
        """Select an employee and open detail drawer."""
        error = ""
        try:
            employee = await self._open_employee_details(employee_id)
            if employee:
                # Reflex types handler calls as positional-only; kwargs are valid.
                yield EmployeeValidationState.initialize(  # ty: ignore[no-matching-overload]
                    employee=employee,
                    default_role_ids=[str(r) for r in employee.role_ids],
                )
            else:
                error = "Mitarbeiter nicht gefunden."
        except Exception:
            logger.exception("Failed to load employee %s", employee_id)
            error = "Fehler beim Laden des Mitarbeiters."
        if error:
            yield rx.toast.error(error, position="top-right")
        # The card sets the global loading flag before calling this handler.
        yield LoadingState.set_is_loading(False)

    async def _open_employee_details(self, employee_id: int) -> Employee | None:
        """Load an employee with absences and capacities into the detail drawer."""
        async with get_asyncdb_session() as session:
            entity = await employee_repo.find_by_id(session, employee_id)
            if not entity:
                return None
            employee = Employee(**entity.to_dict())
            absence_entities = await absence_repo.find_by_employee_id(
                session, employee_id
            )
            absences = [Absence(**a.to_dict()) for a in absence_entities]
        self.selected_employee = employee
        self.absences = absences
        self.detail_drawer_open = True
        await self._load_employee_capacities(employee_id)
        return employee

    @rx.event
    @requires_admin
    async def select_employee_and_add_absence(
        self, employee_id: int
    ) -> AsyncGenerator[Any]:
        """Select an employee and open the absence modal."""
        async with get_asyncdb_session() as session:
            entity = await employee_repo.find_by_id(session, employee_id)
            if entity:
                self.selected_employee = Employee(**entity.to_dict())
                self.open_absence_modal()
                yield

    @rx.event
    @requires_admin
    async def create_employee(self, form_data: dict) -> AsyncGenerator[Any]:
        """Create a new employee from form submission."""
        self.is_loading = True
        yield
        try:
            emp_data = _employee_from_form(form_data)

            async with get_asyncdb_session() as session:
                entity = EmployeeEntity(
                    first_name=emp_data.first_name,
                    last_name=emp_data.last_name,
                    email=emp_data.email,
                    seniority=emp_data.seniority.value,
                    job_title=emp_data.job_title,
                    location=emp_data.location,
                    manager_id=emp_data.manager_id,
                    hours_per_week=emp_data.hours_per_week,
                    internal_hours=emp_data.internal_hours,
                )
                await employee_repo.create(session, entity)
                await employee_repo.set_roles(session, entity, emp_data.role_ids)
                await session.commit()

            await self._load_employees()
            self.close_add_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Mitarbeiter '{emp_data.first_name} {emp_data.last_name}' erstellt.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to create employee")
            self.is_loading = False
            yield rx.toast.error(
                "Mitarbeiter konnte nicht erstellt werden.", position="top-right"
            )

    @rx.event
    @requires_admin
    async def update_employee(self, form_data: dict) -> AsyncGenerator[Any]:
        """Update an existing employee from form submission."""
        try:
            if not self.selected_employee:
                yield rx.toast.error(
                    "Kein Mitarbeiter ausgewählt.", position="top-right"
                )
                return

            emp_data = _employee_from_form(form_data)
            employee_id = self.selected_employee.id
            if emp_data.manager_id == employee_id:
                yield rx.toast.error(
                    "Ein Mitarbeiter kann nicht sein eigener Vorgesetzter sein.",
                    position="top-right",
                )
                return
            async with get_asyncdb_session() as session:
                entity = await employee_repo.find_by_id(session, employee_id)
                if not entity:
                    yield rx.toast.error(
                        "Mitarbeiter nicht gefunden.", position="top-right"
                    )
                    return
                entity.first_name = emp_data.first_name
                entity.last_name = emp_data.last_name
                entity.email = emp_data.email
                entity.seniority = emp_data.seniority.value
                entity.job_title = emp_data.job_title
                entity.location = emp_data.location
                entity.manager_id = emp_data.manager_id
                entity.hours_per_week = emp_data.hours_per_week
                entity.internal_hours = emp_data.internal_hours
                await employee_repo.set_roles(session, entity, emp_data.role_ids)
                await employee_repo.update(session, entity)

            updated_employee = await self._fetch_employee(employee_id)
            if updated_employee:
                self._upsert_employee(updated_employee)
            self.close_detail_drawer()
            name = f"{emp_data.first_name} {emp_data.last_name}"
            yield rx.toast.info(
                f"Mitarbeiter '{name}' aktualisiert.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to update employee")
            yield rx.toast.error(
                "Mitarbeiter konnte nicht aktualisiert werden.", position="top-right"
            )

    @rx.event
    @requires_admin
    async def delete_employee(self, employee_id: int) -> AsyncGenerator[Any]:
        """Delete an employee by ID."""
        self.is_loading = True
        yield
        try:
            async with get_asyncdb_session() as session:
                deleted = await employee_repo.delete_by_id(session, employee_id)
                if not deleted:
                    self.is_loading = False
                    yield rx.toast.error(
                        "Mitarbeiter nicht gefunden.", position="top-right"
                    )
                    return

            await self._load_employees()
            self.close_detail_drawer()
            self.is_loading = False
            yield rx.toast.info("Mitarbeiter gelöscht.", position="top-right")
        except Exception:
            logger.exception("Failed to delete employee")
            self.is_loading = False
            yield rx.toast.error(
                "Mitarbeiter konnte nicht gelöscht werden.", position="top-right"
            )

    @rx.event
    @requires_admin
    async def create_absence(self, form_data: dict) -> AsyncGenerator[Any]:
        """Create a new absence for the selected employee."""
        _ = form_data  # Reflex requires this keyword arg for on_submit
        logger.debug("create_absence called with data: %s", self.absence_date_range)
        if not self.selected_employee:
            yield rx.toast.error("Kein Mitarbeiter ausgewählt.", position="top-right")
            return

        date_range = _parse_date_range(self.absence_date_range)
        if date_range is None:
            yield rx.toast.error(
                "Bitte einen gültigen Zeitraum auswählen.", position="top-right"
            )
            return
        start, end = date_range

        if start < datetime.now(tz=UTC).date():
            yield rx.toast.error(
                "Abwesenheiten dürfen nicht in der Vergangenheit beginnen.",
                position="top-right",
            )
            return

        try:
            absence_data = AbsenceCreate(
                employee_id=self.selected_employee.id, start_date=start, end_date=end
            )

            async with get_asyncdb_session() as session:
                absence_entities = await absence_repo.find_by_employee_id(
                    session, absence_data.employee_id
                )
                # Overlaps would be double-counted in the utilization figures.
                overlaps = any(
                    a.start_date <= end and a.end_date >= start
                    for a in absence_entities
                )
                if not overlaps:
                    entity = AbsenceEntity(
                        employee_id=absence_data.employee_id,
                        start_date=absence_data.start_date,
                        end_date=absence_data.end_date,
                    )
                    await absence_repo.create(session, entity)
                    absence_entities = await absence_repo.find_by_employee_id(
                        session, absence_data.employee_id
                    )

            if overlaps:
                yield rx.toast.error(
                    "Der Zeitraum überschneidet sich mit einer bestehenden "
                    "Abwesenheit.",
                    position="top-right",
                )
                return

            self.absences = [Absence(**a.to_dict()) for a in absence_entities]

            # Reload all employees so the cards update with the new absence
            await self._load_employees()

            self.close_absence_modal()
            yield rx.toast.info("Abwesenheit eingetragen.", position="top-right")
        except Exception:
            logger.exception("Failed to create absence")
            yield rx.toast.error(
                "Abwesenheit konnte nicht eingetragen werden.", position="top-right"
            )

    @rx.event
    @requires_admin
    async def delete_absence(self, absence_id: int) -> AsyncGenerator[Any]:
        """Delete an absence by ID."""
        try:
            async with get_asyncdb_session() as session:
                await absence_repo.delete_by_id(session, absence_id)

                if self.selected_employee:
                    absence_entities = await absence_repo.find_by_employee_id(
                        session, self.selected_employee.id
                    )
                    self.absences = [Absence(**a.to_dict()) for a in absence_entities]

            await self._load_employees()

            yield rx.toast.info("Abwesenheit gelöscht.", position="top-right")
        except Exception:
            logger.exception("Failed to delete absence")
            yield rx.toast.error(
                "Abwesenheit konnte nicht gelöscht werden.", position="top-right"
            )

    async def _load_all_projects(self) -> None:
        """Load all projects for selection dropdowns."""
        async with get_asyncdb_session() as session:
            entities = await project_repo.find_all_paginated(session, limit=LIST_LIMIT)
            self.all_projects = [Project(**e.to_dict()) for e in entities]

    async def _load_employee_capacities(self, employee_id: int) -> None:
        """Load capacity assignments for a specific employee."""
        async with get_asyncdb_session() as session:
            entities = await capacity_repo.find_by_employee_id(session, employee_id)
            self.employee_capacities = [Capacity(**e.to_dict()) for e in entities]

    @rx.event
    @requires_admin
    async def assign_project_to_employee(self, form_data: dict) -> AsyncGenerator[Any]:
        """Assign a project to the selected employee."""
        if not self.selected_employee:
            yield rx.toast.error("Kein Mitarbeiter ausgewählt.", position="top-right")
            return

        project_id_raw = self.add_project_selected
        if project_id_raw == NEW_PROJECT_VALUE:
            yield rx.toast.error(
                "Bitte das neue Projekt zuerst anlegen.", position="top-right"
            )
            return
        if not project_id_raw:
            yield rx.toast.error("Bitte ein Projekt auswählen.", position="top-right")
            return

        role_id_raw = form_data.get("role_id")
        if not role_id_raw:
            yield rx.toast.error("Bitte eine Rolle auswählen.", position="top-right")
            return

        try:
            project_id = int(project_id_raw)
            role_id = int(role_id_raw)
            employee_id = self.selected_employee.id

            # Find project dates for defaults
            project = next((p for p in self.all_projects if p.id == project_id), None)
            if not project or not project.start_date or not project.end_date:
                yield rx.toast.error("Projekt nicht gefunden.", position="top-right")
                return

            async with get_asyncdb_session() as session:
                existing = await capacity_repo.find_by_project_and_employee(
                    session, project_id, employee_id
                )
                duplicate = any(c.role_id == role_id for c in existing)
                if not duplicate:
                    entity = CapacityEntity(
                        project_id=project_id,
                        employee_id=employee_id,
                        role_id=role_id,
                        start_date=project.start_date,
                        end_date=project.end_date,
                        hours_per_week=self.selected_employee.hours_per_week,
                    )
                    await capacity_repo.create(session, entity)
            if duplicate:
                yield rx.toast.info(
                    "Projekt ist mit dieser Rolle bereits zugewiesen.",
                    position="top-right",
                )
                return

            await self._load_employee_capacities(employee_id)
            self.close_add_project_modal()
            yield rx.toast.info("Projekt zugewiesen.", position="top-right")
        except Exception:
            logger.exception("Failed to assign project")
            yield rx.toast.error(
                "Projekt konnte nicht zugewiesen werden.", position="top-right"
            )

    @rx.event
    @requires_admin
    async def quick_create_project(self) -> AsyncGenerator[Any]:
        """Create a project from the inline fields and select it."""
        self.is_quick_creating = True
        yield
        try:
            async with get_asyncdb_session() as session:
                project = await create_quick_project(
                    session, self.quick_project_name, self.quick_project_code
                )
                await session.commit()
        except QuickProjectError as exc:
            self.is_quick_creating = False
            yield rx.toast.error(str(exc), position="top-right")
            return
        except Exception:
            logger.exception("Failed to quick-create project")
            self.is_quick_creating = False
            yield rx.toast.error(
                "Projekt konnte nicht angelegt werden.", position="top-right"
            )
            return

        self.all_projects = [*self.all_projects, project]
        self.add_project_selected = str(project.id)
        self.quick_project_name = ""
        self.quick_project_code = ""
        self.is_quick_creating = False
        yield rx.toast.info(f"Projekt '{project.code}' angelegt.", position="top-right")

    @rx.event
    @requires_admin
    async def remove_project_from_employee(
        self, project_id: int
    ) -> AsyncGenerator[Any]:
        """Remove a project assignment from the selected employee."""
        if not self.selected_employee:
            yield rx.toast.error("Kein Mitarbeiter ausgewählt.", position="top-right")
            return

        try:
            employee_id = self.selected_employee.id
            async with get_asyncdb_session() as session:
                # Weekly allocations have no FK to the capacity row; remove them
                # in the same transaction so they stop counting as planned load.
                deleted_capacity = await capacity_repo.delete_by_project_and_employee(
                    session, project_id, employee_id
                )
                deleted_allocations = (
                    await capacity_allocation_repo.delete_by_project_and_employee(
                        session, project_id, employee_id
                    )
                )
            if not (deleted_capacity or deleted_allocations):
                yield rx.toast.error("Zuweisung nicht gefunden.", position="top-right")
                return

            await self._load_employee_capacities(employee_id)
            yield rx.toast.info("Projektzuweisung entfernt.", position="top-right")
        except Exception:
            logger.exception("Failed to remove project assignment")
            yield rx.toast.error(
                "Projektzuweisung konnte nicht entfernt werden.", position="top-right"
            )


class EmployeeValidationState(rx.State):
    """Validation state for employee add/edit forms."""

    form_version: rx.Field[int] = rx.field(0)

    first_name: rx.Field[str] = rx.field("")
    last_name: rx.Field[str] = rx.field("")
    email: rx.Field[str] = rx.field("")
    job_title: rx.Field[str] = rx.field("")
    location: rx.Field[str] = rx.field("")
    manager_id: rx.Field[str] = rx.field("")
    seniority: rx.Field[str] = rx.field("")
    role_ids: rx.Field[list[str]] = rx.field(default_factory=list)
    hours_per_week: rx.Field[str] = rx.field("40.0")
    internal_hours: rx.Field[str] = rx.field("4")

    first_name_error: rx.Field[str] = rx.field("")
    last_name_error: rx.Field[str] = rx.field("")
    email_error: rx.Field[str] = rx.field("")
    role_ids_error: rx.Field[str] = rx.field("")
    hours_per_week_error: rx.Field[str] = rx.field("")
    internal_hours_error: rx.Field[str] = rx.field("")

    @rx.event
    def initialize(
        self,
        employee: Employee | None = None,
        default_role_ids: list[str] | None = None,
    ) -> None:
        """Reset validation state for add or edit mode."""
        if employee is None:
            self.first_name = ""
            self.last_name = ""
            self.email = ""
            self.job_title = ""
            self.location = ""
            self.manager_id = ""
            self.seniority = "Advanced"
            self.role_ids = []
            self.hours_per_week = "40.0"
            self.internal_hours = "4"
        else:
            self.first_name = employee.first_name
            self.last_name = employee.last_name
            self.email = employee.email or ""
            self.job_title = employee.job_title or ""
            self.location = employee.location or ""
            self.manager_id = (
                str(employee.manager_id)
                if getattr(employee, "manager_id", None)
                else ""
            )
            self.seniority = employee.seniority
            self.role_ids = default_role_ids or []
            self.hours_per_week = str(employee.hours_per_week)
            self.internal_hours = str(employee.internal_hours)

        self.first_name_error = ""
        self.last_name_error = ""
        self.email_error = ""
        self.role_ids_error = ""
        self.hours_per_week_error = ""
        self.internal_hours_error = ""

        self.form_version += 1

    @rx.event
    def set_first_name(self, value: str) -> None:
        self.first_name = value
        self.validate_first_name()

    @rx.event
    def set_last_name(self, value: str) -> None:
        self.last_name = value
        self.validate_last_name()

    @rx.event
    def set_email(self, value: str) -> None:
        self.email = value
        self.validate_email()

    @rx.event
    def set_job_title(self, value: str) -> None:
        self.job_title = value

    @rx.event
    def set_location(self, value: str) -> None:
        self.location = value

    @rx.event
    def set_manager_id(self, value: str | None) -> None:
        self.manager_id = value or ""

    @rx.event
    def set_seniority(self, value: str) -> None:
        self.seniority = value

    @rx.event
    def set_role_ids(self, value: list[str]) -> None:
        self.role_ids = value
        self.validate_role_ids()

    @rx.event
    def set_hours_per_week(self, value: str | float) -> None:
        self.hours_per_week = str(value)
        self.validate_hours_per_week()

    @rx.event
    def set_internal_hours(self, value: str | int) -> None:
        self.internal_hours = str(value)
        self.validate_internal_hours()

    @rx.event
    def validate_first_name(self) -> None:
        if not self.first_name or not self.first_name.strip():
            self.first_name_error = "Vorname darf nicht leer sein."
        else:
            self.first_name_error = ""

    @rx.event
    def validate_last_name(self) -> None:
        if not self.last_name or not self.last_name.strip():
            self.last_name_error = "Nachname darf nicht leer sein."
        else:
            self.last_name_error = ""

    @rx.event
    def validate_email(self) -> None:
        email = self.email.strip() if self.email else ""
        if email and "@" not in email:
            self.email_error = "Bitte eine gültige E-Mail-Adresse eingeben."
        else:
            self.email_error = ""

    @rx.event
    @requires_admin
    async def validate_email_unique(self) -> None:
        """Check email format and uniqueness against the database."""
        email = self.email.strip() if self.email else ""
        if not email:
            self.email_error = ""
            return
        if "@" not in email:
            self.email_error = "Bitte eine gültige E-Mail-Adresse eingeben."
            return
        team_state = await self.get_state(TeamState)
        exclude_id = (
            team_state.selected_employee.id if team_state.selected_employee else None
        )
        async with get_asyncdb_session() as session:
            existing = await employee_repo.find_by_email(
                session, email, exclude_id=exclude_id
            )
        if existing:
            self.email_error = "Diese E-Mail ist bereits vergeben."
        else:
            self.email_error = ""

    @rx.event
    def validate_role_ids(self) -> None:
        if not self.role_ids:
            self.role_ids_error = "Rollen-Auswahl ist erforderlich."
        else:
            self.role_ids_error = ""

    @rx.event
    def validate_hours_per_week(self) -> None:
        if not self.hours_per_week or not str(self.hours_per_week).strip():
            self.hours_per_week_error = "Geben Sie die Arbeitszeit an."
            return

        try:
            val = float(self.hours_per_week)
            if val < 0.0 or val > 80.0:  # noqa: PLR2004
                self.hours_per_week_error = "Muss zwischen 0 und 80 liegen."
            else:
                self.hours_per_week_error = ""
        except ValueError:
            self.hours_per_week_error = "Muss eine gültige Zahl sein."

    @rx.event
    def validate_internal_hours(self) -> None:
        if not self.internal_hours or not str(self.internal_hours).strip():
            self.internal_hours_error = ""
            return

        try:
            val = int(self.internal_hours)
            if val < 0:
                self.internal_hours_error = "Muss >= 0 sein."
            else:
                self.internal_hours_error = ""
        except ValueError:
            self.internal_hours_error = "Muss eine ganze Zahl sein."

    @rx.event
    def validate_all(self) -> None:
        self.validate_first_name()
        self.validate_last_name()
        self.validate_email()
        self.validate_role_ids()
        self.validate_hours_per_week()
        self.validate_internal_hours()

    @rx.var
    def has_errors(self) -> bool:
        return bool(
            self.first_name_error
            or self.last_name_error
            or self.email_error
            or self.role_ids_error
            or self.hours_per_week_error
            or self.internal_hours_error
        )

    @rx.var
    def is_form_valid(self) -> bool:
        """Check if all required fields are filled and there are no errors."""
        try:
            val = float(self.hours_per_week)
            hours_valid = 0.0 <= val <= 80.0  # noqa: PLR2004
        except ValueError:
            hours_valid = False

        return bool(
            self.first_name.strip()
            and self.last_name.strip()
            and self.role_ids
            and hours_valid
            and not self.has_errors
        )

    @rx.var
    def is_form_invalid(self) -> bool:
        return not self.is_form_valid
