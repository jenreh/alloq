"""Team list data: weekly utilization, free capacity and assignments per person.

Uses the same `UtilizationService` as the planning heatmap and the dashboard,
so the numbers match.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from alloq_commons.entities.project import ProjectEntity, ProjectStateEnum
from alloq_commons.models.employee import Employee
from alloq_commons.repositories.capacity_allocation_repository import (
    capacity_allocation_repo,
)
from alloq_commons.repositories.public_holiday_repository import public_holiday_repo
from alloq_commons.services.utilization import (
    HOURS_PER_DAY,
    AbsencePeriod,
    EmployeeUtilizationSeries,
    UtilizationAllocationInput,
    UtilizationEmployeeInput,
    UtilizationService,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from appkit_commons.database.session import get_asyncdb_session

WEEKS = 8
OVERLOADED_PERCENT = 100
NO_COLOR = "#8E8E93"
"""Neutral gray for a project without its own color."""
FREE_DAYS_MIN = 2.0
"""Someone with more free days than this over the horizon counts as free."""


class TeamWeek(BaseModel):
    label: str
    percent: int
    absent: bool = False


class TeamAssignment(BaseModel):
    project_id: int
    name: str
    color: str
    days: float


class TeamOverview(BaseModel):
    """Per-person figures over the next `WEEKS` weeks."""

    employee_id: int
    load_percent: int = 0
    absent_now: bool = False
    free_days: float = 0.0
    weeks: list[TeamWeek] = []
    assignments: list[TeamAssignment] = []

    @property
    def overloaded(self) -> bool:
        return self.load_percent > OVERLOADED_PERCENT

    @property
    def free(self) -> bool:
        return self.free_days > FREE_DAYS_MIN


@dataclass(frozen=True)
class ProjectInfo:
    id: int
    name: str
    color: str


@dataclass(frozen=True)
class Allocation:
    project_id: int
    employee_id: int
    week_start: date
    person_days: float


def week_starts(today: date, weeks: int = WEEKS) -> list[date]:
    first = UtilizationService.monday_of(today)
    return [first + timedelta(weeks=i) for i in range(weeks)]


def _employee_input(employee: Employee) -> UtilizationEmployeeInput:
    return UtilizationEmployeeInput(
        employee_id=employee.id,
        name=f"{employee.first_name} {employee.last_name}".strip(),
        role_name=employee.role_names[0] if employee.role_names else "",
        internal_hours=employee.internal_hours,
        absences=tuple(
            AbsencePeriod(start_date=a.start_date, end_date=a.end_date)
            for a in employee.absences
            if a.start_date and a.end_date
        ),
        workload_percent=employee.workload_percent,
    )


def _allocation_input(allocation: Allocation) -> UtilizationAllocationInput:
    return UtilizationAllocationInput(
        project_id=allocation.project_id,
        employee_id=allocation.employee_id,
        week_start=allocation.week_start,
        person_days=allocation.person_days,
    )


def _assignments(
    employee_id: int,
    allocations: list[Allocation],
    projects: dict[int, ProjectInfo],
) -> list[TeamAssignment]:
    days: dict[int, float] = {}
    for a in allocations:
        if a.employee_id == employee_id and a.project_id in projects:
            days[a.project_id] = days.get(a.project_id, 0.0) + a.person_days
    return sorted(
        (
            TeamAssignment(
                project_id=pid,
                name=projects[pid].name,
                color=projects[pid].color,
                days=round(total, 2),
            )
            for pid, total in days.items()
            if total > 0
        ),
        key=lambda item: -item.days,
    )


def _to_overview(
    series: EmployeeUtilizationSeries,
    allocations: list[Allocation],
    projects: dict[int, ProjectInfo],
) -> TeamOverview:
    return TeamOverview(
        employee_id=series.employee_id,
        load_percent=series.current_week_percent,
        absent_now=series.current_week_is_absent,
        free_days=round(series.free_hours_next_4w / HOURS_PER_DAY, 1),
        weeks=[
            TeamWeek(label=w.week_label, percent=w.percent, absent=w.is_absent)
            for w in series.weeks
        ],
        assignments=_assignments(series.employee_id, allocations, projects),
    )


def build_overview(
    employees: list[Employee],
    allocations: list[Allocation],
    projects: dict[int, ProjectInfo],
    weeks: list[date],
    holidays: frozenset[date] = frozenset(),
) -> dict[int, TeamOverview]:
    """Utilization per week, free days and project days for every person.

    Only allocations of `projects` (the open ones) count, like the heatmap.
    """
    if not weeks:
        return {}
    counted = [a for a in allocations if a.project_id in projects]
    series = UtilizationService.compute_team_utilization_series(
        employees=[_employee_input(e) for e in employees],
        allocations=[_allocation_input(a) for a in counted],
        week_starts=weeks,
        current_week_start=weeks[0],
        free_capacity_start=weeks[0],
        free_capacity_weeks=len(weeks),
        holiday_dates=holidays,
    )
    return {s.employee_id: _to_overview(s, counted, projects) for s in series.employees}


async def _open_projects(session: AsyncSession) -> dict[int, ProjectInfo]:
    """Name and color of every project that is not completed."""
    rows = await session.execute(
        select(
            ProjectEntity.id,
            ProjectEntity.name_de,
            ProjectEntity.code,
            ProjectEntity.color,
        ).where(ProjectEntity.state != ProjectStateEnum.COMPLETED.value)
    )
    return {
        pid: ProjectInfo(id=pid, name=name or code, color=color or NO_COLOR)
        for pid, name, code, color in rows.all()
    }


async def load_inputs(
    weeks: list[date],
) -> tuple[list[Allocation], dict[int, ProjectInfo], frozenset[date]]:
    """Allocations in the horizon, open projects and public holidays."""
    async with get_asyncdb_session() as session:
        entities = await capacity_allocation_repo.find_in_range(
            session, weeks[0], weeks[-1]
        )
        projects = await _open_projects(session)
        holiday_rows = await public_holiday_repo.find_by_date_range(
            session, weeks[0], weeks[-1] + timedelta(days=4)
        )
    allocations = [
        Allocation(
            project_id=e.project_id,
            employee_id=e.employee_id,
            week_start=e.week_start,
            person_days=float(e.person_days),
        )
        for e in entities
    ]
    holidays = frozenset(h.date for h in holiday_rows if h.date)
    return allocations, projects, holidays
