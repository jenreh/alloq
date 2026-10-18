"""Plain inputs of the portfolio overview, loaded once per request.

Every entity attribute is read inside the session and copied into frozen
dataclasses, so the calculations in ``resource_path`` and ``portfolio`` stay
pure and testable without a database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import date, timedelta

from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.entities.project import ProjectEntity
from alloq_commons.entities.risk import RiskEntity
from alloq_commons.entities.role import RoleEntity
from alloq_commons.models.employee import STANDARD_WEEKLY_HOURS
from alloq_commons.repositories import (
    employee_repo,
    project_repo,
    public_holiday_repo,
    risk_repo,
)
from alloq_commons.repositories.risk_repository import MAX_RISK_IMPACT, MIN_RISK_IMPACT
from sqlalchemy import select

from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

SCOPE_DEPARTMENT = "department"
SCOPE_TEAM = "team"
SCOPES = (SCOPE_DEPARTMENT, SCOPE_TEAM)
LOOKAHEAD_WEEKS = 52
MAX_ROWS = 1000


@dataclass(frozen=True)
class AllocationInput:
    employee_id: int
    role_id: int
    week_start: date
    person_days: float


@dataclass(frozen=True)
class ProjectInput:
    id: int
    code: str
    name: str
    state: str
    start_date: date
    end_date: date
    budget: int
    progress: int = 0
    eac: float = 0.0
    owner_ids: tuple[int, ...] = ()
    required: tuple[tuple[int, float], ...] = ()
    allocations: tuple[AllocationInput, ...] = ()


@dataclass(frozen=True)
class EmployeeInput:
    id: int
    name: str
    role_ids: tuple[int, ...] = ()
    manager_id: int | None = None
    internal_hours: int = 0
    workload_percent: int = 100
    absences: tuple[tuple[date, date], ...] = ()


@dataclass(frozen=True)
class RoleInput:
    id: int
    name: str


@dataclass(frozen=True)
class RiskInput:
    id: int
    project_id: int
    name: str
    probability: int
    impact: int
    mitigation_status: str = "open"


@dataclass(frozen=True)
class PortfolioInputs:
    """Everything the portfolio needs.

    ``projects`` and ``employees`` are the scope shown; ``all_projects`` and
    ``all_employees`` stay complete, because bookings on any project use up a
    person's time.
    """

    projects: tuple[ProjectInput, ...] = ()
    all_projects: tuple[ProjectInput, ...] = ()
    employees: tuple[EmployeeInput, ...] = ()
    all_employees: tuple[EmployeeInput, ...] = ()
    roles: tuple[RoleInput, ...] = ()
    risks: tuple[RiskInput, ...] = ()
    holidays: frozenset[date] = frozenset()
    current_employee_id: int | None = None


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def team_employee_ids(inputs: PortfolioInputs) -> set[int]:
    """Direct reports of the signed-in employee."""
    manager = inputs.current_employee_id
    if manager is None:
        return set()
    return {e.id for e in inputs.all_employees if e.manager_id == manager}


def booking_projects(inputs: PortfolioInputs) -> tuple[ProjectInput, ...]:
    return inputs.all_projects or inputs.projects


def apply_scope(inputs: PortfolioInputs, scope: str) -> PortfolioInputs:
    """Restrict people to direct reports and projects to owned ones."""
    if scope != SCOPE_TEAM:
        return inputs
    manager = inputs.current_employee_id
    team = team_employee_ids(inputs)
    return replace(
        inputs,
        employees=tuple(e for e in inputs.all_employees if e.id in team),
        projects=tuple(
            p
            for p in booking_projects(inputs)
            if manager is not None and manager in p.owner_ids
        ),
    )


def _latest_eac(entity: ProjectEntity) -> float:
    """EAC from the project, else from its newest status snapshot."""
    if entity.ev_eac_additive:
        return float(entity.ev_eac_additive)
    latest = entity.statuses[0] if entity.statuses else None
    if latest is None:
        return 0.0
    for value in (latest.eac_additive, latest.eac_linear):
        if value:
            return float(value)
    budget = float(entity.budget or 0)
    spent = (
        float(latest.actual_cost)
        if latest.actual_cost
        else budget * (latest.budget_spent or 0) / 100.0
    )
    if spent > 0 and latest.progress:
        return spent / (latest.progress / 100.0)
    return 0.0


def project_to_input(entity: ProjectEntity) -> ProjectInput:
    latest = entity.statuses[0] if entity.statuses else None
    required: dict[int, float] = {}
    for rc in entity.required_capacities or []:
        required[rc.role_id] = required.get(rc.role_id, 0.0) + float(rc.person_days)
    return ProjectInput(
        id=entity.id,
        code=entity.code,
        name=entity.name_de,
        state=entity.state,
        start_date=entity.start_date,
        end_date=entity.end_date,
        budget=entity.budget or 0,
        progress=latest.progress if latest else 0,
        eac=_latest_eac(entity),
        owner_ids=tuple(o.id for o in entity.owners or []),
        required=tuple(sorted(required.items())),
        allocations=tuple(
            AllocationInput(
                employee_id=a.employee_id,
                role_id=a.role_id,
                week_start=a.week_start,
                person_days=float(a.person_days),
            )
            for a in entity.capacity_allocations or []
        ),
    )


def employee_to_input(entity: EmployeeEntity) -> EmployeeInput:
    return EmployeeInput(
        id=entity.id,
        name=f"{entity.first_name} {entity.last_name}".strip(),
        role_ids=tuple(r.id for r in entity.roles or []),
        manager_id=entity.manager_id,
        internal_hours=int(entity.internal_hours or 0),
        workload_percent=round(
            float(entity.hours_per_week or STANDARD_WEEKLY_HOURS)
            / STANDARD_WEEKLY_HOURS
            * 100
        ),
        absences=tuple(
            (a.start_date, a.end_date)
            for a in entity.absences or []
            if a.start_date and a.end_date
        ),
    )


def risk_to_input(entity: RiskEntity) -> RiskInput:
    return RiskInput(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        probability=clamp(entity.probability, MIN_RISK_IMPACT, MAX_RISK_IMPACT),
        impact=clamp(entity.impact, MIN_RISK_IMPACT, MAX_RISK_IMPACT),
        mitigation_status=entity.mitigation_status,
    )


async def load_inputs(today: date, email: str | None) -> PortfolioInputs:
    """Load projects, people, roles, open risks and holidays."""
    monday = today - timedelta(days=today.weekday())
    async with get_asyncdb_session() as session:
        projects = await project_repo.find_all_paginated(session, limit=MAX_ROWS)
        project_rows = tuple(project_to_input(p) for p in projects)
        employees = await employee_repo.find_all_paginated(session, limit=MAX_ROWS)
        employee_rows = tuple(employee_to_input(e) for e in employees)
        result = await session.execute(select(RoleEntity).order_by(RoleEntity.name))
        role_rows = tuple(RoleInput(id=r.id, name=r.name) for r in result.scalars())
        risks = await risk_repo.find_open_by_min_score(session, min_score=0)
        risk_rows = tuple(risk_to_input(r) for r in risks)
        holidays = await public_holiday_repo.find_by_date_range(
            session, monday, monday + timedelta(weeks=LOOKAHEAD_WEEKS)
        )
        holiday_dates = frozenset(h.date for h in holidays if h.date)
        current = await employee_repo.find_by_email(session, email) if email else None
        current_id = current.id if current else None
    logger.debug(
        "Portfolio inputs: %d projects, %d employees, %d risks",
        len(project_rows),
        len(employee_rows),
        len(risk_rows),
    )
    return PortfolioInputs(
        projects=project_rows,
        all_projects=project_rows,
        employees=employee_rows,
        all_employees=employee_rows,
        roles=role_rows,
        risks=risk_rows,
        holidays=holiday_dates,
        current_employee_id=current_id,
    )
