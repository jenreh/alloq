import logging
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import reflex as rx
from alloq_commons.entities.absence import AbsenceEntity
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.models.role import Role
from alloq_commons.repositories.absence_repository import absence_repo
from alloq_commons.repositories.employee_repository import employee_repo
from alloq_commons.repositories.role_repository import role_repo

from alloq_team.models.employee import (
    Absence,
    AbsenceCreate,
    Employee,
    EmployeeCreate,
)
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import is_authenticated

logger = logging.getLogger(__name__)


class TeamState(rx.State):
    """State for team member management."""

    employees: list[Employee] = []
    selected_employee: Employee | None = None
    absences: list[Absence] = []
    available_roles: list[Role] = []
    is_loading: bool = False

    add_modal_open: bool = False
    edit_modal_open: bool = False
    detail_drawer_open: bool = False
    absence_modal_open: bool = False
    absence_date_range: list[str] = []

    search_filter: str = ""
    view_mode: str = "grid"

    @rx.var(cache=False)
    def current_date(self) -> str:
        """Get the current date as an ISO string for form boundaries."""
        return datetime.now(tz=UTC).date().isoformat()

    def set_absence_date_range(self, value: list[str]) -> None:
        """Set the absence date range."""
        self.absence_date_range = value

    def set_search_filter(self, value: str) -> None:
        """Update the search filter."""
        self.search_filter = value

    def set_view_mode(self, mode: str) -> None:
        """Switch between grid and table view."""
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
    def role_select_options(self) -> list[dict[str, str]]:
        """Return roles formatted for Mantine Select data prop."""
        return [{"value": str(r.id), "label": r.name} for r in self.available_roles]

    @rx.var
    def form_role_ids(self) -> list[str]:
        """Convert selected employee role IDs to strings for multi-select."""
        if self.selected_employee:
            return [str(role_id) for role_id in self.selected_employee.role_ids]
        return []

    def open_add_modal(self) -> None:
        """Open the add employee modal."""
        self.add_modal_open = True

    def close_add_modal(self) -> None:
        """Close the add employee modal."""
        self.add_modal_open = False

    def open_edit_modal(self) -> None:
        """Open the edit employee modal."""
        self.edit_modal_open = True

    def close_edit_modal(self) -> None:
        """Close the edit employee modal."""
        self.edit_modal_open = False
        self.selected_employee = None

    def close_detail_drawer(self) -> None:
        """Close the detail drawer."""
        self.detail_drawer_open = False
        self.selected_employee = None
        self.absences = []

    def open_absence_modal(self) -> None:
        """Open the absence add modal."""
        self.absence_date_range = []
        self.absence_modal_open = True

    def close_absence_modal(self) -> None:
        """Close the absence modal."""
        self.absence_modal_open = False
        self.absence_date_range = []

    async def _load_employees(self) -> None:
        """Internal load logic for employees with role names."""
        async with get_asyncdb_session() as session:
            entities = await employee_repo.find_all_paginated(session)
            self.employees = [Employee(**e.to_dict()) for e in entities]

    async def _load_available_roles(self) -> None:
        """Load roles for dropdown selection."""
        async with get_asyncdb_session() as session:
            entities = await role_repo.find_all_paginated(session)
            self.available_roles = [Role(**e.to_dict()) for e in entities]

    @is_authenticated
    async def load_employees(self) -> AsyncGenerator[Any, None]:
        """Load all employees from the database."""
        self.is_loading = True
        yield
        try:
            await self._load_employees()
            await self._load_available_roles()
        finally:
            self.is_loading = False

    @is_authenticated
    async def select_employee(self, employee_id: int) -> AsyncGenerator[Any, None]:
        """Select an employee and open detail drawer."""
        async with get_asyncdb_session() as session:
            entity = await employee_repo.find_by_id(session, employee_id)
            if entity:
                self.selected_employee = Employee(**entity.to_dict())
                absence_entities = await absence_repo.find_by_employee_id(
                    session, employee_id
                )
                self.absences = [Absence(**a.to_dict()) for a in absence_entities]
                self.detail_drawer_open = True
                yield

    @is_authenticated
    async def select_employee_and_edit(
        self, employee_id: int
    ) -> AsyncGenerator[Any, None]:
        """Select an employee and open edit modal."""
        async with get_asyncdb_session() as session:
            entity = await employee_repo.find_by_id(session, employee_id)
            if entity:
                self.selected_employee = Employee(**entity.to_dict())
                self.open_edit_modal()
                yield

    @is_authenticated
    async def select_employee_and_add_absence(
        self, employee_id: int
    ) -> AsyncGenerator[Any, None]:
        """Select an employee and open the absence modal."""
        async with get_asyncdb_session() as session:
            entity = await employee_repo.find_by_id(session, employee_id)
            if entity:
                self.selected_employee = Employee(**entity.to_dict())
                self.open_absence_modal()
                yield

    @is_authenticated
    async def create_employee(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Create a new employee from form submission."""
        self.is_loading = True
        yield
        try:
            raw_roles = form_data.get("role_ids", [])
            if isinstance(raw_roles, str):
                role_ids = [int(x) for x in raw_roles.split(",") if x]
            else:
                role_ids = [int(x) for x in raw_roles]

            emp_data = EmployeeCreate(
                first_name=form_data.get("first_name", "").strip(),
                last_name=form_data.get("last_name", "").strip(),
                seniority=form_data.get("seniority", "Advanced"),
                job_title=form_data.get("job_title", "").strip() or None,
                location=form_data.get("location", "").strip() or None,
                role_ids=role_ids,
                hours_per_week=float(form_data.get("hours_per_week", 40.0)),
            )

            async with get_asyncdb_session() as session:
                entity = EmployeeEntity(
                    first_name=emp_data.first_name,
                    last_name=emp_data.last_name,
                    seniority=emp_data.seniority.value,
                    job_title=emp_data.job_title,
                    location=emp_data.location,
                    hours_per_week=emp_data.hours_per_week,
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
        except Exception as e:
            logger.error("Failed to create employee: %s", e)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Erstellen: {e}",
                position="top-right",
            )

    @is_authenticated
    async def update_employee(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Update an existing employee from form submission."""
        self.is_loading = True
        yield
        try:
            if not self.selected_employee:
                self.is_loading = False
                yield rx.toast.error(
                    "Kein Mitarbeiter ausgewählt.", position="top-right"
                )
                return

            raw_roles = form_data.get("role_ids", [])
            if isinstance(raw_roles, str):
                role_ids = [int(x) for x in raw_roles.split(",") if x]
            else:
                role_ids = [int(x) for x in raw_roles]

            emp_data = EmployeeCreate(
                first_name=form_data.get("first_name", "").strip(),
                last_name=form_data.get("last_name", "").strip(),
                seniority=form_data.get("seniority", "Advanced"),
                job_title=form_data.get("job_title", "").strip() or None,
                location=form_data.get("location", "").strip() or None,
                role_ids=role_ids,
                hours_per_week=float(form_data.get("hours_per_week", 40.0)),
            )

            async with get_asyncdb_session() as session:
                entity = await employee_repo.find_by_id(
                    session, self.selected_employee.id
                )
                if not entity:
                    self.is_loading = False
                    yield rx.toast.error(
                        "Mitarbeiter nicht gefunden.", position="top-right"
                    )
                    return
                entity.first_name = emp_data.first_name
                entity.last_name = emp_data.last_name
                entity.seniority = emp_data.seniority.value
                entity.job_title = emp_data.job_title
                entity.location = emp_data.location
                entity.hours_per_week = emp_data.hours_per_week
                await employee_repo.set_roles(session, entity, emp_data.role_ids)
                await employee_repo.update(session, entity)

            await self._load_employees()
            self.close_detail_drawer()
            self.is_loading = False
            name = f"{emp_data.first_name} {emp_data.last_name}"
            yield rx.toast.info(
                f"Mitarbeiter '{name}' aktualisiert.",
                position="top-right",
            )
        except Exception as e:
            logger.error("Failed to update employee: %s", e)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Aktualisieren: {e}",
                position="top-right",
            )

    @is_authenticated
    async def delete_employee(self, employee_id: int) -> AsyncGenerator[Any, None]:
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
        except Exception as e:
            logger.error("Failed to delete employee: %s", e)
            self.is_loading = False
            yield rx.toast.error(
                f"Fehler beim Löschen: {e}",
                position="top-right",
            )

    @is_authenticated
    async def create_absence(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Create a new absence for the selected employee."""
        _ = form_data  # Reflex requires this keyword arg for on_submit
        logger.info("create_absence called with data: %s", self.absence_date_range)
        if not self.selected_employee:
            yield rx.toast.error("Kein Mitarbeiter ausgewählt.", position="top-right")
            return

        date_range = self.absence_date_range

        if (
            not date_range
            or len(date_range) < 2  # noqa: PLR2004
            or not date_range[0]
            or not date_range[1]
        ):
            yield rx.toast.error(
                "Bitte einen gültigen Zeitraum auswählen.", position="top-right"
            )
            return

        start_date_str = date_range[0][:10]
        end_date_str = date_range[1][:10]

        if date.fromisoformat(start_date_str) < datetime.now(tz=UTC).date():
            yield rx.toast.error(
                "Abwesenheiten dürfen nicht in der Vergangenheit beginnen.",
                position="top-right",
            )
            return

        try:
            absence_data = AbsenceCreate(
                employee_id=self.selected_employee.id,
                start_date=start_date_str,
                end_date=end_date_str,
            )

            async with get_asyncdb_session() as session:
                entity = AbsenceEntity(
                    employee_id=absence_data.employee_id,
                    start_date=absence_data.start_date,
                    end_date=absence_data.end_date,
                )
                await absence_repo.create(session, entity)

                # Reload absences
                absence_entities = await absence_repo.find_by_employee_id(
                    session, self.selected_employee.id
                )
                self.absences = [Absence(**a.to_dict()) for a in absence_entities]

            # Reload all employees so the cards update with the new absence
            await self._load_employees()

            self.close_absence_modal()
            yield rx.toast.info("Abwesenheit eingetragen.", position="top-right")
        except Exception as e:
            logger.error("Failed to create absence: %s", e)
            yield rx.toast.error(
                f"Fehler beim Erstellen: {e}",
                position="top-right",
            )

    @is_authenticated
    async def delete_absence(self, absence_id: int) -> AsyncGenerator[Any, None]:
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
        except Exception as e:
            logger.error("Failed to delete absence: %s", e)
            yield rx.toast.error(
                f"Fehler beim Löschen: {e}",
                position="top-right",
            )
