import logging
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import reflex as rx
from alloq_commons.entities import ProjectEntity, ProjectStatusEntity
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.entities.required_capacity import RequiredCapacityEntity
from alloq_commons.entities.risk import RiskEntity
from alloq_commons.models.project import (
    Capacity,
    Project,
    ProjectCreate,
    ProjectStatus,
    RequiredCapacity,
    RequiredCapacityCreate,
    Risk,
    RiskMatrixCell,
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
from alloq_project.services.forecast import EVForecastService, EVSummary

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


def _parse_localized_int(value: float | str | None) -> int:
    """Parse numeric input values that may contain German separators."""
    raw = str(value or 0).strip()
    raw = raw.replace(".", "").replace(",", ".")
    return int(float(raw)) if raw else 0


_SCORE_LOW = 4
_SCORE_MEDIUM = 9
_SCORE_HIGH = 15
_SCORE_VERY_HIGH = 20

# Maps impact score (1-5) to a representative EUR value within each tier
_IMPACT_SCORE_TO_EUR: dict[int, int] = {
    1: 10_000,
    2: 60_000,
    3: 300_000,
    4: 750_000,
    5: 1_500_000,
}


def _risk_score_color(score: int) -> str:
    """Return background color for a risk matrix cell based on score."""
    if score <= _SCORE_LOW:
        return "var(--alloq-risk-low)"
    if score <= _SCORE_MEDIUM:
        return "var(--alloq-risk-medium)"
    if score <= _SCORE_HIGH:
        return "var(--alloq-risk-high)"
    if score <= _SCORE_VERY_HIGH:
        return "var(--alloq-risk-very-high)"
    return "var(--alloq-risk-critical)"


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
    active_tab: str = "status"

    # Status form input state
    status_progress: int = 0
    status_budget_usage: int = 0
    status_notes: str = ""
    status_form_version: int = 0

    # Status edit draft state (0=none, positive=editing existing)
    expanded_status_id: int = 0
    status_draft_progress: int = 0
    status_draft_budget_usage: int = 0
    status_draft_notes: str = ""
    status_draft_date: str = ""

    # Risk draft state (0=none, -1=new unsaved, positive=editing existing)
    expanded_risk_id: int = 0
    risk_draft_name: str = ""
    risk_draft_description: str = ""
    risk_draft_measures: str = ""
    risk_draft_impact: int = 3
    risk_draft_probability: int = 3
    risk_draft_mitigation_status: str = "Offen"
    risk_draft_form_version: int = 0

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
                if (
                    search in project.code.lower()
                    or search in project.customer.lower()
                    or search in project.name_de.lower()
                )
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
    def active_projects(self) -> list[Project]:
        """Return projects in active or at-risk state."""
        active_states = {ProjectStateEnum.ACTIVE, ProjectStateEnum.AT_RISK}
        return [p for p in self.projects if p.state in active_states]

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
        self.active_tab = "status"
        self.status_progress = 0
        self.status_budget_usage = 0
        self.status_notes = ""
        self.expanded_status_id = 0
        self.status_draft_progress = 0
        self.status_draft_budget_usage = 0
        self.status_draft_notes = ""
        self.status_draft_date = ""
        self.expanded_risk_id = 0
        self.risk_draft_name = ""
        self.risk_draft_description = ""
        self.risk_draft_measures = ""
        self.risk_draft_impact = 3
        self.risk_draft_probability = 3
        self.risk_draft_mitigation_status = "Offen"

    async def _load_projects(self) -> None:
        """Load projects from the database."""
        async with get_asyncdb_session() as session:
            entities = await project_repo.find_all_with_stats(
                session,
                search=self.search_filter or None,
            )
            projects = [Project(**entity.to_dict()) for entity in entities]
            self.projects = sorted(projects, key=lambda p: p.name_de.lower())

    async def _fetch_project(self, project_id: int) -> Project | None:
        """Fetch a single project as a Project read model with stats."""
        async with get_asyncdb_session() as session:
            entity = await project_repo.find_by_id(session, project_id)
            if not entity:
                return None
            return Project(**entity.to_dict())

    def _upsert_project(self, project: Project) -> None:
        """Insert or replace a project in the list, preserving sort order."""
        updated = [p for p in self.projects if p.id != project.id]
        updated.append(project)
        updated.sort(key=lambda p: p.name_de.lower())
        self.projects = updated

    def _remove_project(self, project_id: int) -> None:
        """Remove a project from the list by id."""
        self.projects = [p for p in self.projects if p.id != project_id]

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
            self.risks = [
                Risk(**{**risk.to_dict(), "number": i + 1})
                for i, risk in enumerate(risk_entities)
            ]
            self.capacities = [
                Capacity(**capacity.to_dict()) for capacity in capacity_entities
            ]
            self.required_capacities = [
                RequiredCapacity(**capacity.to_dict()) for capacity in required_entities
            ]
            self.detail_drawer_open = True
            yield ProjectValidationState.initialize(self.selected_project)

    @is_authenticated
    async def create_project(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Create a project with required capacity rows."""
        try:
            project_data = self._project_create_from_form(form_data)
            async with get_asyncdb_session() as session:
                entity = ProjectEntity(
                    code=project_data.code,
                    customer=project_data.customer,
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
                new_project_id = entity.id

            new_project = await self._fetch_project(new_project_id)
            if new_project:
                self._upsert_project(new_project)
            self.close_add_modal()
            yield rx.toast.info(
                f"Projekt '{project_data.code}' erstellt.",
                position="top-right",
            )
        except Exception as exc:
            logger.error("Failed to create project: %s", exc)
            yield rx.toast.error(
                f"Fehler beim Erstellen: {exc}",
                position="top-right",
            )

    @is_authenticated
    async def update_project(self, form_data: dict) -> AsyncGenerator[Any, None]:
        """Update the selected project with form data."""
        if not self.selected_project:
            return
        project_id = self.selected_project.id
        try:
            project_data = self._project_create_from_form(form_data)
            async with get_asyncdb_session() as session:
                entity = await project_repo.find_by_id(session, project_id)
                if not entity:
                    yield rx.toast.error(
                        "Projekt nicht gefunden.", position="top-right"
                    )
                    return

                entity.code = project_data.code
                entity.customer = project_data.customer
                entity.name_de = project_data.name_de
                entity.start_date = project_data.start_date
                entity.end_date = project_data.end_date
                entity.state = project_data.state
                entity.budget = project_data.budget
                entity.color = project_data.color

                entity.owners.clear()
                for emp_id in project_data.owner_ids:
                    employee = await employee_repo.find_by_id(session, emp_id)
                    if employee:
                        entity.owners.append(employee)

                entity.required_capacities.clear()
                for capacity in project_data.required_capacities:
                    entity.required_capacities.append(
                        RequiredCapacityEntity(
                            project_id=entity.id,
                            role_id=capacity.role_id,
                            person_days=capacity.person_days,
                        )
                    )

                await session.commit()

            updated_project = await self._fetch_project(project_id)
            if updated_project:
                self._upsert_project(updated_project)
            self.close_detail_drawer()
            yield rx.toast.info(
                f"Projekt '{project_data.code}' aktualisiert.",
                position="top-right",
            )
        except Exception as exc:
            logger.error("Failed to update project: %s", exc)
            yield rx.toast.error(
                f"Fehler beim Aktualisieren: {exc}",
                position="top-right",
            )

    @is_authenticated
    async def delete_project(self, project_id: int) -> AsyncGenerator[Any, None]:
        """Delete a project by ID."""
        try:
            async with get_asyncdb_session() as session:
                deleted = await project_repo.delete_by_id(session, project_id)
                if not deleted:
                    yield rx.toast.error(
                        "Projekt nicht gefunden.", position="top-right"
                    )
                    return
                await session.commit()

            self._remove_project(project_id)
            self.close_detail_drawer()
            yield rx.toast.info("Projekt gelöscht.", position="top-right")
        except Exception as exc:
            logger.error("Failed to delete project: %s", exc)
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

        # Form submissions from components with thousand_separator may send a
        # formatted string like "30.000" instead of "30000". We manually parse
        # these locally to be safe.
        budget = _parse_localized_int(form_data.get("budget", 0))

        return ProjectCreate(
            code=str(form_data.get("code", "")).strip(),
            customer=str(form_data.get("customer", "")).strip(),
            name_de=str(form_data.get("name_de", "")).strip(),
            start_date=date.fromisoformat(str(form_data.get("start_date", ""))[:10]),
            end_date=date.fromisoformat(str(form_data.get("end_date", ""))[:10]),
            state=str(form_data.get("state", ProjectStateEnum.PLANNED.value)),
            budget=budget,
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
            raw_value = str(
                form_data.get(f"required_capacity_{role.id}", "") or 0
            ).strip()
            if not raw_value:
                continue
            try:
                person_days = _parse_localized_int(raw_value)
            except (TypeError, ValueError):
                continue

            if person_days <= 0:
                continue

            capacities.append(
                RequiredCapacityCreate(
                    role_id=role.id,
                    person_days=person_days,
                )
            )
        return capacities

    def set_active_tab(self, tab: str) -> None:
        """Switch the active drawer tab."""
        self.active_tab = tab

    def set_status_progress(self, value: float | str) -> None:
        """Update the status progress field."""
        try:
            self.status_progress = max(0, min(100, int(float(value or 0))))
        except (TypeError, ValueError):
            self.status_progress = 0

    def set_status_budget_usage(self, value: float | str) -> None:
        """Update the status budget usage field."""
        try:
            self.status_budget_usage = max(0, min(100, int(float(value or 0))))
        except (TypeError, ValueError):
            self.status_budget_usage = 0

    def set_status_notes(self, value: str) -> None:
        """Update the status notes field."""
        self.status_notes = value or ""

    @is_authenticated
    async def add_project_status(self) -> AsyncGenerator[Any, None]:
        """Save current status form as a new history entry."""
        if not self.selected_project:
            return
        project_id = self.selected_project.id
        try:
            today = datetime.now(tz=UTC).date()
            async with get_asyncdb_session() as session:
                entity = ProjectStatusEntity(
                    project_id=project_id,
                    status_date=today,
                    fortschritt=self.status_progress,
                    budget_verbrauch=self.status_budget_usage,
                    anmerkung=self.status_notes or None,
                )
                await status_repo.create(session, entity)
                await session.commit()
                await session.refresh(entity)
                new_status = ProjectStatus(
                    id=entity.id,
                    project_id=project_id,
                    status_date=today.isoformat(),
                    fortschritt=self.status_progress,
                    budget_verbrauch=self.status_budget_usage,
                    anmerkung=self.status_notes,
                )
            self.statuses = [new_status, *self.statuses]
            self.status_progress = 0
            self.status_budget_usage = 0
            self.status_notes = ""
            self.status_form_version += 1
            yield rx.toast.info("Status gespeichert.", position="top-right")
        except Exception as exc:
            logger.error("Failed to save project status: %s", exc)
            yield rx.toast.error(
                "Fehler beim Speichern des Status.",
                position="top-right",
            )

    def expand_status(self, status_id: int) -> None:
        """Toggle the inline edit form for an existing status entry."""
        if self.expanded_status_id == status_id:
            self.expanded_status_id = 0
            return
        status = next((s for s in self.statuses if s.id == status_id), None)
        if not status:
            return
        self.expanded_status_id = status_id
        self.status_draft_progress = status.fortschritt
        self.status_draft_budget_usage = status.budget_verbrauch
        self.status_draft_notes = status.anmerkung
        self.status_draft_date = status.status_date

    def collapse_status_edit(self) -> None:
        """Close the status edit form without saving."""
        self.expanded_status_id = 0

    def set_status_draft_progress(self, value: float | str) -> None:
        """Update status draft progress field."""
        try:
            self.status_draft_progress = max(0, min(100, int(float(value or 0))))
        except (TypeError, ValueError):
            self.status_draft_progress = 0

    def set_status_draft_budget_usage(self, value: float | str) -> None:
        """Update status draft budget usage field."""
        try:
            self.status_draft_budget_usage = max(0, min(100, int(float(value or 0))))
        except (TypeError, ValueError):
            self.status_draft_budget_usage = 0

    def set_status_draft_notes(self, value: str) -> None:
        """Update status draft notes field."""
        self.status_draft_notes = value or ""

    def set_status_draft_date(self, value: str) -> None:
        """Update status draft date field."""
        self.status_draft_date = value or ""

    @is_authenticated
    async def save_status_draft(self) -> AsyncGenerator[Any, None]:
        """Persist edits to an existing status entry."""
        status_id = self.expanded_status_id
        if status_id <= 0:
            return
        try:
            new_date = date.fromisoformat(self.status_draft_date[:10])
        except (ValueError, IndexError):
            yield rx.toast.error("Ungültiges Datum.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                entity = await status_repo.find_by_id(session, status_id)
                if not entity:
                    yield rx.toast.error("Status nicht gefunden.", position="top-right")
                    return
                entity.status_date = new_date
                entity.fortschritt = self.status_draft_progress
                entity.budget_verbrauch = self.status_draft_budget_usage
                entity.anmerkung = self.status_draft_notes or None
                await session.commit()
            self.statuses = [
                ProjectStatus(
                    **{
                        **s.model_dump(),
                        "status_date": new_date.isoformat(),
                        "fortschritt": self.status_draft_progress,
                        "budget_verbrauch": self.status_draft_budget_usage,
                        "anmerkung": self.status_draft_notes,
                    }
                )
                if s.id == status_id
                else s
                for s in self.statuses
            ]
            self.expanded_status_id = 0
            yield rx.toast.info("Status aktualisiert.", position="top-right")
        except Exception as exc:
            logger.error("Failed to update status %s: %s", status_id, exc)
            yield rx.toast.error(
                "Fehler beim Speichern des Status.",
                position="top-right",
            )

    @is_authenticated
    async def delete_project_status(self, status_id: int) -> AsyncGenerator[Any, None]:
        """Delete a status history entry by ID."""
        try:
            async with get_asyncdb_session() as session:
                deleted = await status_repo.delete_by_id(session, status_id)
                if not deleted:
                    return
                await session.commit()
            if status_id == self.expanded_status_id:
                self.expanded_status_id = 0
            self.statuses = [s for s in self.statuses if s.id != status_id]
            yield rx.toast.info("Status gelöscht.", position="top-right")
        except Exception as exc:
            logger.error("Failed to delete status %s: %s", status_id, exc)
            yield rx.toast.error(
                "Fehler beim Löschen des Status.",
                position="top-right",
            )

    def add_project_risk(self) -> None:
        """Open a draft form for a new risk without persisting yet."""
        self.expanded_risk_id = -1
        self.risk_draft_name = ""
        self.risk_draft_description = ""
        self.risk_draft_measures = ""
        self.risk_draft_impact = 3
        self.risk_draft_probability = 3
        self.risk_draft_mitigation_status = "Offen"
        self.risk_draft_form_version += 1

    def expand_risk(self, risk_id: int) -> None:
        """Toggle the inline edit form for an existing risk."""
        if self.expanded_risk_id == risk_id:
            self.expanded_risk_id = 0
            return
        risk = next((r for r in self.risks if r.id == risk_id), None)
        if not risk:
            return
        self.expanded_risk_id = risk_id
        self.risk_draft_name = risk.name
        self.risk_draft_description = risk.description
        self.risk_draft_measures = risk.measures
        self.risk_draft_impact = risk.auswirkung_score
        self.risk_draft_probability = risk.probability
        self.risk_draft_mitigation_status = risk.mitigation_status
        self.risk_draft_form_version += 1

    def collapse_risk_edit(self) -> None:
        """Close the risk edit form without saving."""
        self.expanded_risk_id = 0

    def set_risk_draft_name(self, value: str) -> None:
        """Update risk draft name."""
        self.risk_draft_name = value or ""

    def set_risk_draft_description(self, value: str) -> None:
        """Update risk draft description."""
        self.risk_draft_description = value or ""

    def set_risk_draft_measures(self, value: str) -> None:
        """Update risk draft measures."""
        self.risk_draft_measures = value or ""

    def set_risk_draft_impact(self, value: str) -> None:
        """Update risk draft impact score (1-5)."""
        try:
            self.risk_draft_impact = max(1, min(5, int(value or 3)))
        except (TypeError, ValueError):
            self.risk_draft_impact = 3

    def set_risk_draft_probability(self, value: str) -> None:
        """Update risk draft probability (1-5)."""
        try:
            self.risk_draft_probability = max(1, min(5, int(value or 3)))
        except (TypeError, ValueError):
            self.risk_draft_probability = 3

    def set_risk_draft_mitigation_status(self, value: str) -> None:
        """Update risk draft mitigation status."""
        self.risk_draft_mitigation_status = value or "Offen"

    @is_authenticated
    async def save_risk_draft(self) -> AsyncGenerator[Any, None]:
        """Persist the current risk draft (create new or update existing)."""
        if not self.selected_project:
            return
        project_id = self.selected_project.id
        try:
            if self.expanded_risk_id == -1:
                async with get_asyncdb_session() as session:
                    entity = RiskEntity(
                        project_id=project_id,
                        name=self.risk_draft_name or "Neues Risiko",
                        description=self.risk_draft_description,
                        probability=self.risk_draft_probability,
                        impact=_IMPACT_SCORE_TO_EUR.get(self.risk_draft_impact, 10_000),
                        mitigation_status=self.risk_draft_mitigation_status,
                        measures=self.risk_draft_measures or None,
                    )
                    await risk_repo.create(session, entity)
                    await session.commit()
                    await session.refresh(entity)
                    new_number = len(self.risks) + 1
                    new_risk = Risk(**{**entity.to_dict(), "number": new_number})
                self.risks = [*self.risks, new_risk]
                self.expanded_risk_id = 0
                yield rx.toast.info("Risiko gespeichert.", position="top-right")
            elif self.expanded_risk_id > 0:
                risk_id = self.expanded_risk_id
                async with get_asyncdb_session() as session:
                    entity = await risk_repo.find_by_id(session, risk_id)
                    if not entity:
                        yield rx.toast.error(
                            "Risiko nicht gefunden.", position="top-right"
                        )
                        return
                    entity.name = self.risk_draft_name
                    entity.description = self.risk_draft_description
                    entity.measures = self.risk_draft_measures or None
                    entity.impact = _IMPACT_SCORE_TO_EUR.get(
                        self.risk_draft_impact, 10_000
                    )
                    entity.probability = self.risk_draft_probability
                    entity.mitigation_status = self.risk_draft_mitigation_status
                    await session.commit()
                self.risks = [
                    Risk(
                        **{
                            **r.model_dump(),
                            "name": self.risk_draft_name,
                            "description": self.risk_draft_description,
                            "measures": self.risk_draft_measures,
                            "impact": _IMPACT_SCORE_TO_EUR.get(
                                self.risk_draft_impact, 10_000
                            ),
                            "probability": self.risk_draft_probability,
                            "mitigation_status": self.risk_draft_mitigation_status,
                        }
                    )
                    if r.id == risk_id
                    else r
                    for r in self.risks
                ]
                self.expanded_risk_id = 0
                yield rx.toast.info("Risiko gespeichert.", position="top-right")
        except Exception as exc:
            logger.error("Failed to save risk draft: %s", exc)
            yield rx.toast.error(
                "Fehler beim Speichern des Risikos.",
                position="top-right",
            )

    @is_authenticated
    async def update_project_risk(
        self, risk_id: int, field: str, value: str
    ) -> AsyncGenerator[Any, None]:
        """Update a single field on a risk."""
        try:
            async with get_asyncdb_session() as session:
                entity = await risk_repo.find_by_id(session, risk_id)
                if not entity:
                    return
                allowed = {
                    "name",
                    "description",
                    "measures",
                    "impact",
                    "probability",
                    "mitigation_status",
                }
                if field not in allowed:
                    return
                if field in ("impact", "probability"):
                    setattr(entity, field, int(float(value or 0)))
                else:
                    setattr(entity, field, str(value or ""))
                await session.commit()

            self.risks = [
                Risk(
                    **{
                        **r.model_dump(),
                        field: (
                            int(float(value or 0))
                            if field in ("impact", "probability")
                            else str(value or "")
                        ),
                    }
                )
                if r.id == risk_id
                else r
                for r in self.risks
            ]
        except Exception as exc:
            logger.error("Failed to update risk %s: %s", risk_id, exc)
            yield rx.toast.error(
                "Fehler beim Aktualisieren des Risikos.",
                position="top-right",
            )

    @is_authenticated
    async def delete_project_risk(self, risk_id: int) -> AsyncGenerator[Any, None]:
        """Delete a risk by ID and renumber remaining risks."""
        try:
            async with get_asyncdb_session() as session:
                deleted = await risk_repo.delete_by_id(session, risk_id)
                if not deleted:
                    return
                await session.commit()
            if risk_id == self.expanded_risk_id:
                self.expanded_risk_id = 0
            remaining = [r for r in self.risks if r.id != risk_id]
            self.risks = [
                Risk(**{**r.model_dump(), "number": i + 1})
                for i, r in enumerate(remaining)
            ]
            yield rx.toast.info("Risiko gelöscht.", position="top-right")
        except Exception as exc:
            logger.error("Failed to delete risk %s: %s", risk_id, exc)
            yield rx.toast.error(
                "Fehler beim Löschen des Risikos.",
                position="top-right",
            )

    @rx.var
    def sorted_risks(self) -> list[Risk]:
        """Risks sorted by creation date descending (newest first)."""
        return sorted(
            self.risks,
            key=lambda r: r.created or "",
            reverse=True,
        )

    @rx.var
    def risk_matrix_cells(self) -> list[RiskMatrixCell]:
        """Return 25 cells for the 5x5 risk matrix (row-major, top to bottom)."""
        cells = []
        for w in range(5, 0, -1):
            for a in range(1, 6):
                score = w * a
                risk_numbers = [
                    r.number
                    for r in self.risks
                    if r.probability == w and r.auswirkung_score == a
                ]
                risk_names = [
                    r.name
                    for r in self.risks
                    if r.probability == w and r.auswirkung_score == a
                ]
                cells.append(
                    RiskMatrixCell(
                        w=w,
                        a=a,
                        score=score,
                        risk_numbers=risk_numbers,
                        risk_names=risk_names,
                        color=_risk_score_color(score),
                    )
                )
        return cells

    @rx.var
    def ev_chart_data(self) -> list[dict]:
        """Build EV chart data with PV, EV, AC and two forecast curves."""
        if not self.selected_project:
            return []
        return EVForecastService.build_chart_data(self.selected_project, self.statuses)

    @rx.var
    def ev_summary(self) -> EVSummary:
        """Final AC/EV and EAC forecasts at the latest status."""
        if not self.selected_project:
            return EVSummary()
        return EVForecastService.build_summary(self.selected_project, self.statuses)


class ProjectValidationState(rx.State):
    """Validation state for project add forms."""

    form_version: int = 0
    code: str = ""
    customer: str = ""
    name_de: str = ""
    start_date: str = ""
    end_date: str = ""
    state: str = ProjectStateEnum.PLANNED.value
    budget: int = 0
    color: str = DEFAULT_PROJECT_COLOR
    owner_ids: list[str] = []
    role_capacities: dict[str, int] = {}

    code_error: str = ""
    customer_error: str = ""
    name_de_error: str = ""
    date_error: str = ""
    budget_error: str = ""

    @rx.event(background=True)
    async def initialize(self, project: Project | None = None) -> None:
        """Reset validation state for add mode or preload from a project."""
        async with self:
            if project is None:
                self.code = ""
                self.customer = ""
                self.name_de = ""
                self.start_date = ""
                self.end_date = ""
                self.state = ProjectStateEnum.PLANNED.value
                self.budget = 0
                self.color = DEFAULT_PROJECT_COLOR
                self.owner_ids = []

                # Get available roles to initialize capacities to 0
                project_state = await self.get_state(ProjectState)
                self.role_capacities = {
                    str(role.id): 0 for role in project_state.available_roles
                }
            else:
                self.code = project.code
                self.customer = project.customer
                self.name_de = project.name_de
                self.start_date = (
                    project.start_date.isoformat() if project.start_date else ""
                )
                self.end_date = project.end_date.isoformat() if project.end_date else ""
                self.state = project.state
                self.budget = project.budget
                self.color = project.color
                self.owner_ids = [str(oid) for oid in project.owner_ids]

                project_state = await self.get_state(ProjectState)
                role_caps = {str(role.id): 0 for role in project_state.available_roles}
                role_caps.update(
                    {
                        str(c.role_id): c.person_days
                        for c in getattr(project, "required_capacities", [])
                    }
                )
                self.role_capacities = role_caps

            self.code_error = ""
            self.customer_error = ""
            self.name_de_error = ""
            self.date_error = ""
            self.budget_error = ""
            self.form_version += 1

    def set_code(self, value: str) -> None:
        self.code = value
        self.validate_code()

    def set_customer(self, value: str) -> None:
        self.customer = value
        self.validate_customer()

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

    def set_budget(self, value: float | str) -> None:
        try:
            self.budget = _parse_localized_int(value)
        except (TypeError, ValueError):
            self.budget = 0
        self.validate_budget()

    def set_color(self, value: str) -> None:
        self.color = value

    def set_owner_ids(self, value: list[str]) -> None:
        self.owner_ids = value or []

    @rx.event
    def validate_code(self) -> None:
        self.code_error = "" if self.code.strip() else "Projekt-Code ist erforderlich."

    @rx.event
    def validate_customer(self) -> None:
        self.customer_error = "" if self.customer.strip() else "Kunde ist erforderlich."

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
            budget = _parse_localized_int(self.budget)
        except (TypeError, ValueError):
            self.budget_error = "Budget muss eine gültige Zahl sein."
            return

        if budget < 0:
            self.budget_error = "Budget darf nicht negativ sein."
        else:
            self.budget_error = ""

    @rx.var(cache=True)
    def total_capacity(self) -> int:
        return sum(self.role_capacities.values())

    def set_role_capacity(self, role_id: str, value: float | str) -> None:
        try:
            self.role_capacities[role_id] = _parse_localized_int(value)
        except (TypeError, ValueError):
            self.role_capacities[role_id] = 0

    def has_errors(self) -> bool:
        return bool(
            self.code_error
            or self.customer_error
            or self.name_de_error
            or self.date_error
            or self.budget_error
        )

    @rx.var
    def is_form_valid(self) -> bool:
        """Check if required fields are complete and valid."""
        try:
            budget_valid = _parse_localized_int(self.budget) >= 0
            dates_valid = bool(self.start_date and self.end_date)
            if dates_valid:
                dates_valid = date.fromisoformat(
                    self.end_date[:10]
                ) >= date.fromisoformat(self.start_date[:10])
        except (TypeError, ValueError):
            budget_valid = False
            dates_valid = False

        return bool(
            self.code.strip()
            and self.customer.strip()
            and self.name_de.strip()
            and budget_valid
            and dates_valid
            and not self.has_errors()
        )

    @rx.var
    def is_form_invalid(self) -> bool:
        return not self.is_form_valid
