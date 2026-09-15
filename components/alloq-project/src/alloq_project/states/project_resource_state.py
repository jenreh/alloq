"""State for the Ressourcen tab of the project detail drawer."""

import logging
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any

import reflex as rx
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import (
    CapacityAllocation,
    Project,
    ResourceCandidate,
    ResourcePeriod,
)
from alloq_commons.models.role import Role
from alloq_commons.repositories import (
    capacity_allocation_repo,
    employee_repo,
    project_repo,
    public_holiday_repo,
    role_repo,
)
from alloq_project.services.resource_planning import (
    PlanTarget,
    apply_resource_plan,
    delete_resource_period,
    find_candidates,
    group_into_periods,
    plan_weekly_days,
    week_starts,
    weekly_free_days,
)
from alloq_project.states.project_state import ProjectState

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import is_authenticated

log = logging.getLogger(__name__)

MIN_DAYS_PER_WEEK = 0.5
MAX_DAYS_PER_WEEK = 5.0
DEFAULT_DAYS_PER_WEEK = 3.0
EMPLOYEE_LIMIT = 1000
TOAST_POSITION = "top-right"


def _parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


class ProjectResourceState(rx.State):
    """Plan employees on the selected project with von/bis/Tage pro Woche/Rolle."""

    project_id: int = 0
    project_start: str = ""
    project_end: str = ""
    employees: list[Employee] = []
    roles: list[Role] = []
    holiday_dates: list[date] = []
    # {employee_id: {week_start_iso: person_days}} on other projects
    other_pt: dict[str, dict[str, float]] = {}
    allocations: list[CapacityAllocation] = []

    role_id: str = ""
    start_iso: str = ""
    end_iso: str = ""
    days_per_week: float = DEFAULT_DAYS_PER_WEEK
    editing_key: str = ""
    form_version: int = 0

    is_loading: bool = False
    is_saving: bool = False

    # ------------------------------------------------------------------
    # Computed vars
    # ------------------------------------------------------------------

    @rx.var
    def role_options(self) -> list[dict[str, str]]:
        return [{"value": str(r.id), "label": r.name} for r in self.roles]

    @rx.var
    def periods(self) -> list[ResourcePeriod]:
        names = {e.id: f"{e.first_name} {e.last_name}".strip() for e in self.employees}
        role_names = {r.id: r.name for r in self.roles}
        return group_into_periods(self.allocations, names, role_names)

    @rx.var
    def form_error(self) -> str:
        if not self.role_id:
            return "Bitte eine Rolle wählen."
        start, end = _parse_iso(self.start_iso), _parse_iso(self.end_iso)
        if start is None or end is None:
            return "Bitte Von und Bis angeben."
        if end < start:
            return "Von muss vor Bis liegen."
        return ""

    @rx.var
    def is_editing(self) -> bool:
        return self.editing_key != ""

    @rx.var
    def candidates(self) -> list[ResourceCandidate]:
        start, end = _parse_iso(self.start_iso), _parse_iso(self.end_iso)
        if self.form_error or start is None or end is None:
            return []
        return find_candidates(
            self.employees,
            role_id=int(self.role_id),
            start=start,
            end=end,
            days_per_week=self.days_per_week,
            holidays=set(self.holiday_dates),
            other_pt=self._other_pt_by_employee(),
            planned_employee_ids={a.employee_id for a in self.allocations},
        )

    def _other_pt_by_employee(self) -> dict[int, dict[date, float]]:
        return {
            int(employee_id): {
                date.fromisoformat(week): pt for week, pt in weeks.items()
            }
            for employee_id, weeks in self.other_pt.items()
        }

    # ------------------------------------------------------------------
    # Form inputs
    # ------------------------------------------------------------------

    def _clamp_to_project(self, value: str) -> str | None:
        parsed = _parse_iso(value)
        if parsed is None:
            return None
        lower, upper = _parse_iso(self.project_start), _parse_iso(self.project_end)
        if lower and parsed < lower:
            parsed = lower
        if upper and parsed > upper:
            parsed = upper
        return parsed.isoformat()

    def set_role_id(self, value: str | None) -> None:
        self.role_id = str(value or "")

    def set_start(self, value: str) -> None:
        clamped = self._clamp_to_project(value)
        if clamped is not None:
            self.start_iso = clamped

    def set_end(self, value: str) -> None:
        clamped = self._clamp_to_project(value)
        if clamped is not None:
            self.end_iso = clamped

    def set_days_per_week(self, value: float | str) -> None:
        try:
            parsed = float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return
        stepped = round(parsed * 2) / 2
        self.days_per_week = max(MIN_DAYS_PER_WEEK, min(MAX_DAYS_PER_WEEK, stepped))

    def edit_period(self, key: str) -> None:
        period = self._period(key)
        if period is None:
            return
        self.editing_key = key
        self.role_id = str(period.role_id)
        self.start_iso = self._clamp_to_project(period.start) or period.start
        self.end_iso = self._clamp_to_project(period.end) or period.end
        self.days_per_week = period.days_per_week
        self.form_version += 1

    def cancel_edit(self) -> None:
        self.editing_key = ""
        self.form_version += 1

    def _period(self, key: str) -> ResourcePeriod | None:
        return next((p for p in self.periods if p.key == key), None)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @is_authenticated
    async def load_selected(self) -> AsyncGenerator[Any, None]:
        """Load resource data for the project selected in the drawer."""
        project_state = await self.get_state(ProjectState)
        project = project_state.selected_project
        if project is None or not project.id:
            return
        self.is_loading = True
        yield
        try:
            await self._load(project.id)
        except Exception as exc:
            log.error("Failed to load resource plan: %s", exc)
            yield rx.toast.error(
                "Ressourcen konnten nicht geladen werden.", position=TOAST_POSITION
            )
        finally:
            self.is_loading = False

    async def _load(self, project_id: int) -> None:
        async with get_asyncdb_session() as session:
            entity = await project_repo.find_by_id(session, project_id)
            if entity is None:
                msg = "Projekt nicht gefunden."
                raise LookupError(msg)
            project = Project(**entity.to_dict())
            start = project.start_date or date.today()  # noqa: DTZ011
            end = project.end_date or start
            employee_entities = await employee_repo.find_all_paginated(
                session, limit=EMPLOYEE_LIMIT
            )
            role_entities = await role_repo.find_all_paginated(session)
            holiday_rows = await public_holiday_repo.find_by_date_range(
                session, start, end
            )
            in_range = await capacity_allocation_repo.find_in_range(
                session, week_starts(start, end)[0], end
            )
            own = await capacity_allocation_repo.find_by_project(session, project_id)

        self.project_id = project_id
        self.project_start = start.isoformat()
        self.project_end = end.isoformat()
        self.employees = [Employee(**e.to_dict()) for e in employee_entities]
        self.roles = sorted(
            (Role(**r.to_dict()) for r in role_entities), key=lambda r: r.name
        )
        self.holiday_dates = [row.date for row in holiday_rows if row.date]
        self.other_pt = self._aggregate_other_pt(in_range, project_id)
        self.allocations = [CapacityAllocation(**a.to_dict()) for a in own]
        self.role_id = self._default_role_id(project)
        self.start_iso = self.project_start
        self.end_iso = self.project_end
        self.days_per_week = DEFAULT_DAYS_PER_WEEK
        self.editing_key = ""
        self.form_version += 1

    @staticmethod
    def _aggregate_other_pt(
        rows: list[Any], project_id: int
    ) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for row in rows:
            if row.project_id == project_id or row.week_start is None:
                continue
            weeks = out.setdefault(str(row.employee_id), {})
            week = row.week_start.isoformat()
            weeks[week] = weeks.get(week, 0.0) + float(row.person_days or 0.0)
        return out

    def _default_role_id(self, project: Project) -> str:
        """First required role not yet covered by planned PT, else first role."""
        planned: dict[int, float] = {}
        for alloc in self.allocations:
            planned[alloc.role_id] = planned.get(alloc.role_id, 0.0) + alloc.person_days
        required = [rc for rc in project.required_capacities if rc.role_id]
        for capacity in required:
            if planned.get(capacity.role_id, 0.0) < capacity.person_days:
                return str(capacity.role_id)
        if required:
            return str(required[0].role_id)
        return str(self.roles[0].id) if self.roles else ""

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    @is_authenticated
    async def assign(self, employee_id: int) -> AsyncGenerator[Any, None]:
        """Plan the employee with the current form values (replaces in range)."""
        if self.form_error:
            yield rx.toast.error(self.form_error, position=TOAST_POSITION)
            return
        employee = next((e for e in self.employees if e.id == employee_id), None)
        start, end = _parse_iso(self.start_iso), _parse_iso(self.end_iso)
        if employee is None or start is None or end is None:
            return
        free = weekly_free_days(
            employee,
            week_starts(start, end),
            set(self.holiday_dates),
            self._other_pt_by_employee().get(employee_id, {}),
        )
        days = plan_weekly_days(start, end, self.days_per_week, free)
        if not days:
            yield rx.toast.warning(
                "Keine freie Kapazität im Zeitraum.", position=TOAST_POSITION
            )
            return

        editing = self._period(self.editing_key) if self.editing_key else None
        self.is_saving = True
        yield
        try:
            async with get_asyncdb_session() as session:
                if editing is not None:
                    await delete_resource_period(
                        session,
                        self._target(editing.employee_id, editing.role_id),
                        date.fromisoformat(editing.start),
                        date.fromisoformat(editing.end),
                    )
                await apply_resource_plan(
                    session,
                    self._target(employee_id, int(self.role_id)),
                    start,
                    end,
                    days,
                )
                await session.commit()
            self.editing_key = ""
            await self._refresh_after_change()
            name = f"{employee.first_name} {employee.last_name}".strip()
            yield rx.toast.info(f"{name} eingeplant.", position=TOAST_POSITION)
        except Exception as exc:
            log.error("Failed to save resource plan: %s", exc)
            yield rx.toast.error(
                f"Fehler beim Speichern: {exc}", position=TOAST_POSITION
            )
        finally:
            self.is_saving = False

    @is_authenticated
    async def delete_period(self, key: str) -> AsyncGenerator[Any, None]:
        """Delete one planned period."""
        period = self._period(key)
        if period is None:
            return
        try:
            async with get_asyncdb_session() as session:
                await delete_resource_period(
                    session,
                    self._target(period.employee_id, period.role_id),
                    date.fromisoformat(period.start),
                    date.fromisoformat(period.end),
                )
                await session.commit()
            if self.editing_key == key:
                self.cancel_edit()
            await self._refresh_after_change()
            yield rx.toast.info("Zeitraum gelöscht.", position=TOAST_POSITION)
        except Exception as exc:
            log.error("Failed to delete resource period: %s", exc)
            yield rx.toast.error(f"Fehler beim Löschen: {exc}", position=TOAST_POSITION)

    def _target(self, employee_id: int, role_id: int) -> PlanTarget:
        return PlanTarget(self.project_id, employee_id, role_id)

    async def _refresh_after_change(self) -> None:
        """Reload own allocations and push them to the drawer and overview."""
        async with get_asyncdb_session() as session:
            own = await capacity_allocation_repo.find_by_project(
                session, self.project_id
            )
            self.allocations = [CapacityAllocation(**a.to_dict()) for a in own]
            entity = await project_repo.find_by_id(session, self.project_id)
            project = Project(**entity.to_dict()) if entity else None

        project_state = await self.get_state(ProjectState)
        project_state.allocation_plan = list(self.allocations)
        if project is not None:
            project_state.projects = [
                project if p.id == project.id else p for p in project_state.projects
            ]
