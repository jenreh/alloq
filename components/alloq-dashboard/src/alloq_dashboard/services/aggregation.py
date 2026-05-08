"""Async aggregation functions powering the dashboard KPI cards.

Each function loads minimal data through existing alloq_commons repositories,
materializes every needed field into plain dataclasses while the session is
still open, then reduces the data into a typed payload outside the session.
This avoids `DetachedInstanceError` on lazy-loaded ORM relationships.
"""

from __future__ import annotations

import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, timedelta

from alloq_commons.entities.capacity_allocation import CapacityAllocationEntity
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.entities.project import ProjectEntity, ProjectStateEnum
from alloq_commons.entities.risk import (
    HIGH_RISK_SCORE_THRESHOLD,
    RiskEntity,
    RiskLevel,
    RiskMitigationStatus,
)
from alloq_commons.entities.role import RoleEntity
from alloq_commons.entities.status import ProjectStatusEntity
from alloq_commons.repositories import (
    capacity_allocation_repo,
    employee_repo,
    project_repo,
    risk_repo,
)
from alloq_commons.services.utilization import (
    PLANNING_ANCHOR_DATE,
    AbsencePeriod,
    TeamUtilizationSeries,
    UtilizationAllocationInput,
    UtilizationEmployeeInput,
    UtilizationService,
    WeekUtilizationResult,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_dashboard.models import (
    BudgetBurnKpi,
    EarnedValuePoint,
    EmployeeUtilization,
    FreeCapacityKpi,
    MonthlyRoleCapacity,
    ProjectHealthKpi,
    ProjectsOverviewKpi,
    ProjectSummary,
    RiskItem,
    RiskKpi,
    RoleCapacity,
    StateCount,
    TrendPoint,
    UnderUtilizationKpi,
    UtilizationKpi,
    WeeklyUtilization,
)
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

WORK_DAYS_PER_WEEK = 5
HOURS_PER_DAY = 8.0
TREND_WEEKS_BACK = 2
HORIZON_WEEKS = 12
UNDER_UTIL_THRESHOLD = 70
OVER_UTIL_THRESHOLD = 100
BUDGET_DELTA_THRESHOLD = 0.10
PROGRESS_RISK_THRESHOLD = 80
DEADLINE_RISK_DAYS = 30
SORT_END_DATE_FALLBACK = 9999


SEVERITY_LOW_MAX = 4
SEVERITY_MEDIUM_MAX = 15


_ROLE_COLORS = [
    "#4ade80",  # green
    "#facc15",  # yellow
    "#60a5fa",  # blue
    "#fb923c",  # orange
    "#c084fc",  # purple
    "#f87171",  # red
    "#34d399",  # emerald
    "#a78bfa",  # violet
    "#38bdf8",  # sky
    "#f472b6",  # pink
]

STATE_COLORS: dict[str, str] = {
    ProjectStateEnum.PLANNED.value: "#94a3b8",
    ProjectStateEnum.ACTIVE.value: "#22c55e",
    ProjectStateEnum.AT_RISK.value: "#ef4444",
    ProjectStateEnum.COMPLETED.value: "#6366f1",
}


# --------------------------------------------------------------------------
# Plain transport rows materialized inside session
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _ProjectRow:
    id: int
    code: str
    name_de: str
    state: str
    start_date: date | None
    end_date: date | None
    budget: int
    color: str
    progress: int
    spent: int
    open_risk_count: int


@dataclass(frozen=True)
class _RiskRow:
    id: int
    project_id: int
    name: str
    severity: str
    probability: int
    impact: int
    mitigation_status: str
    owner: str | None
    created_date: date | None
    updated_date: date | None


@dataclass(frozen=True)
class _StatusRow:
    project_id: int
    status_date: date
    fortschritt: int
    budget_verbrauch: int


@dataclass(frozen=True)
class _AllocationRow:
    project_id: int
    employee_id: int
    role_id: int
    week_start: date
    person_days: float


@dataclass(frozen=True)
class _AbsenceRow:
    start_date: date
    end_date: date


@dataclass(frozen=True)
class _EmployeeRow:
    id: int
    first_name: str
    last_name: str
    hours_per_week: float
    internal_hours: int
    role_ids: tuple[int, ...]
    role_names: tuple[str, ...]
    absences: tuple[_AbsenceRow, ...]


@dataclass(frozen=True)
class _RoleRow:
    id: int
    name: str
    color: str = "#888"


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def _today() -> date:
    return datetime.datetime.now(tz=UTC).date()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _week_label(week_start: date) -> str:
    return f"KW{week_start.isocalendar().week:02d}"


_MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
)


def _month_label(d: date) -> str:
    return _MONTH_NAMES[d.month - 1]


def _build_month_grid(year: int) -> list[date]:
    """Return the first day of each month for the given calendar year."""
    return [date(year, m, 1) for m in range(1, 13)]


def _build_week_grid(today: date, back: int, forward: int) -> list[date]:
    """Return a list of Monday-aligned week_starts spanning [back, forward)."""
    start = _monday(today) - timedelta(weeks=back)
    return [start + timedelta(weeks=i) for i in range(back + forward)]


def _build_planning_week_grid(num_weeks: int) -> list[date]:
    return UtilizationService.planning_week_starts(
        num_weeks=num_weeks,
        anchor_date=PLANNING_ANCHOR_DATE,
    )


def _heat_bucket(percent: int) -> str:
    return UtilizationService.heat_bucket(percent)


def _project_summary(row: _ProjectRow, today: date) -> ProjectSummary:
    spent_pct = (row.spent / row.budget * 100) if row.budget else 0.0
    days_to_end = (row.end_date - today).days if row.end_date else 0
    return ProjectSummary(
        id=row.id,
        code=row.code,
        name=row.name_de,
        state=row.state,
        start_date=row.start_date,
        end_date=row.end_date,
        days_to_end=days_to_end,
        progress=row.progress,
        budget=row.budget,
        spent=row.spent,
        spent_percent=round(spent_pct, 1),
        risk_count=row.open_risk_count,
        color=row.color or "#888",
    )


def _classify_at_risk(
    summary: ProjectSummary,
    high_open_risk_pids: set[int],
) -> bool:
    if summary.state == ProjectStateEnum.AT_RISK.value:
        return True
    if summary.id in high_open_risk_pids:
        return True
    if (
        summary.budget
        and (summary.spent / summary.budget) - (summary.progress / 100)
        > BUDGET_DELTA_THRESHOLD
    ):
        return True
    return bool(
        summary.days_to_end is not None
        and 0 <= summary.days_to_end <= DEADLINE_RISK_DAYS
        and summary.progress < PROGRESS_RISK_THRESHOLD,
    )


def _employee_available_days(emp: _EmployeeRow, week_start: date) -> float:
    """Available days using the shared heatmap formula."""
    absences = [
        AbsencePeriod(start_date=a.start_date, end_date=a.end_date)
        for a in emp.absences
    ]
    result = UtilizationService.compute_heat_from_raw(
        used_days=0.0,
        internal_hours=emp.internal_hours,
        absences=absences,
        week_start=week_start,
    )
    return result.available_days


# --------------------------------------------------------------------------
# Data loaders — every entity attribute is read inside the session
# --------------------------------------------------------------------------


def _project_to_row(entity: ProjectEntity) -> _ProjectRow:
    latest = entity.statuses[0] if entity.statuses else None
    open_risks = sum(
        1
        for r in entity.risks or []
        if r.mitigation_status == RiskMitigationStatus.OPEN.value
        and r.probability * r.impact >= HIGH_RISK_SCORE_THRESHOLD
    )
    return _ProjectRow(
        id=entity.id,
        code=entity.code,
        name_de=entity.name_de,
        state=entity.state,
        start_date=entity.start_date,
        end_date=entity.end_date,
        budget=entity.budget or 0,
        color=entity.color or "#888",
        progress=latest.fortschritt if latest else 0,
        spent=latest.budget_verbrauch if latest else 0,
        open_risk_count=open_risks,
    )


def _severity_from_score(probability: int, impact: int) -> str:
    """Derive severity label from probability * impact."""
    score = probability * impact
    if score <= SEVERITY_LOW_MAX:
        return RiskLevel.LOW.value
    if score <= SEVERITY_MEDIUM_MAX:
        return RiskLevel.MEDIUM.value
    return RiskLevel.HIGH.value


def _risk_to_row(entity: RiskEntity) -> _RiskRow:
    created = entity.created.date() if entity.created else None
    updated = entity.updated.date() if entity.updated else None
    return _RiskRow(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        severity=_severity_from_score(entity.probability, entity.impact),
        probability=entity.probability,
        impact=entity.impact,
        mitigation_status=entity.mitigation_status,
        owner=None,
        created_date=created,
        updated_date=updated,
    )


def _status_to_row(entity: ProjectStatusEntity) -> _StatusRow:
    return _StatusRow(
        project_id=entity.project_id,
        status_date=entity.status_date,
        fortschritt=entity.fortschritt,
        budget_verbrauch=entity.budget_verbrauch,
    )


def _allocation_to_row(entity: CapacityAllocationEntity) -> _AllocationRow:
    return _AllocationRow(
        project_id=entity.project_id,
        employee_id=entity.employee_id,
        role_id=entity.role_id,
        week_start=entity.week_start,
        person_days=float(entity.person_days),
    )


def _employee_to_row(entity: EmployeeEntity) -> _EmployeeRow:
    role_ids: list[int] = []
    role_names: list[str] = []
    for role in entity.roles or []:
        role_ids.append(role.id)
        role_names.append(role.name)
    absences: list[_AbsenceRow] = [
        _AbsenceRow(start_date=absence.start_date, end_date=absence.end_date)
        for absence in entity.absences or []
        if absence.start_date and absence.end_date
    ]
    return _EmployeeRow(
        id=entity.id,
        first_name=entity.first_name,
        last_name=entity.last_name,
        hours_per_week=float(entity.hours_per_week or 40.0),
        internal_hours=int(entity.internal_hours or 0),
        role_ids=tuple(role_ids),
        role_names=tuple(role_names),
        absences=tuple(absences),
    )


def _role_to_row(entity: RoleEntity, index: int = 0) -> _RoleRow:
    color = _ROLE_COLORS[index % len(_ROLE_COLORS)]
    return _RoleRow(id=entity.id, name=entity.name, color=color)


async def _load_project_rows(session: AsyncSession) -> list[_ProjectRow]:
    entities = await project_repo.find_all_paginated(session, limit=1000)
    return [_project_to_row(e) for e in entities]


async def _load_risk_rows(session: AsyncSession) -> list[_RiskRow]:
    entities = await risk_repo.find_open_by_min_score(session)
    return [_risk_to_row(e) for e in entities]


async def _load_status_rows(session: AsyncSession, since: date) -> list[_StatusRow]:
    statement = (
        select(ProjectStatusEntity)
        .where(ProjectStatusEntity.status_date >= since)
        .order_by(ProjectStatusEntity.status_date)
    )
    result = await session.execute(statement)
    return [_status_to_row(e) for e in result.scalars().all()]


async def _load_allocation_rows(
    session: AsyncSession,
    start: date,
    end: date,
) -> list[_AllocationRow]:
    entities = await capacity_allocation_repo.find_in_range(session, start, end)
    return [_allocation_to_row(e) for e in entities]


async def _load_employee_rows(session: AsyncSession) -> list[_EmployeeRow]:
    entities = await employee_repo.find_all_paginated(session, limit=1000)
    return [_employee_to_row(e) for e in entities]


async def _load_role_rows(session: AsyncSession) -> list[_RoleRow]:
    result = await session.execute(select(RoleEntity).order_by(RoleEntity.name))
    return [_role_to_row(e, i) for i, e in enumerate(result.scalars().all())]


# --------------------------------------------------------------------------
# Card 1 — projects overview
# --------------------------------------------------------------------------


async def load_projects_overview() -> ProjectsOverviewKpi:
    today = _today()
    async with get_asyncdb_session() as session:
        projects = await _load_project_rows(session)
    counts: dict[str, int] = defaultdict(int)
    for p in projects:
        counts[p.state] += 1
    by_state = [
        StateCount(
            state=s.value,
            count=counts.get(s.value, 0),
            color=STATE_COLORS[s.value],
        )
        for s in ProjectStateEnum
    ]
    rows = sorted(
        (_project_summary(p, today) for p in projects),
        key=lambda s: (s.state, s.name.lower()),
    )
    active_rows = [
        s
        for s in rows
        if s.state in (ProjectStateEnum.ACTIVE.value, ProjectStateEnum.AT_RISK.value)
    ]
    active_count = counts.get(ProjectStateEnum.ACTIVE.value, 0) + counts.get(
        ProjectStateEnum.AT_RISK.value, 0
    )
    return ProjectsOverviewKpi(
        total=active_count,
        active=counts.get(ProjectStateEnum.ACTIVE.value, 0),
        planned=counts.get(ProjectStateEnum.PLANNED.value, 0),
        at_risk=counts.get(ProjectStateEnum.AT_RISK.value, 0),
        completed=counts.get(ProjectStateEnum.COMPLETED.value, 0),
        by_state=by_state,
        rows=rows,
        active_rows=active_rows,
    )


# --------------------------------------------------------------------------
# Card 2 — project health
# --------------------------------------------------------------------------


async def load_project_health() -> ProjectHealthKpi:
    today = _today()
    async with get_asyncdb_session() as session:
        projects = await _load_project_rows(session)
        risks = await _load_risk_rows(session)
    summaries = [
        _project_summary(p, today)
        for p in projects
        if p.state != ProjectStateEnum.COMPLETED.value
    ]
    at_risk = [s for s in summaries if s.state == ProjectStateEnum.AT_RISK.value]
    healthy = [s for s in summaries if s not in at_risk]

    trend_weeks = _build_week_grid(today, TREND_WEEKS_BACK, 1)
    risk_trend: list[TrendPoint] = []
    for week_start in trend_weeks:
        cutoff = week_start + timedelta(days=6)
        opened = sum(1 for r in risks if r.created_date and r.created_date <= cutoff)
        risk_trend.append(
            TrendPoint(
                label=_week_label(week_start),
                week_start=week_start,
                value=float(opened),
            )
        )

    return ProjectHealthKpi(
        at_risk_count=len(at_risk),
        healthy_count=len(healthy),
        total_risk_count=len(risks),
        rows=sorted(
            at_risk,
            key=lambda s: s.days_to_end or SORT_END_DATE_FALLBACK,
        ),
        risk_trend=risk_trend,
    )


# --------------------------------------------------------------------------
# Earned Value helper
# --------------------------------------------------------------------------


def _build_earned_value_series(
    active: list[_ProjectRow],
    by_project: dict[int, list[_StatusRow]],
    total_budget: int,
    today: date,
) -> list[EarnedValuePoint]:
    """Build monthly EV series (Budget %, Spent %, Progress %) for the current year."""
    months = _build_month_grid(today.year)
    result: list[EarnedValuePoint] = []
    for m_start in months:
        last_month = 12
        if m_start.month == last_month:
            m_end = date(m_start.year, last_month, 31)
        else:
            m_end = date(m_start.year, m_start.month + 1, 1) - timedelta(days=1)

        planned = 0.0
        for p in active:
            if not p.start_date or not p.end_date or not p.budget:
                continue
            total_days = (p.end_date - p.start_date).days
            if total_days <= 0:
                continue
            elapsed = min((m_end - p.start_date).days, total_days)
            if elapsed <= 0:
                continue
            planned += p.budget * (elapsed / total_days)
        budget_pct = round(planned / total_budget * 100, 1) if total_budget else 0.0

        monthly_spent = 0
        for p in active:
            past = [s for s in by_project.get(p.id, []) if s.status_date <= m_end]
            if not past:
                continue
            past.sort(key=lambda s: s.status_date)
            monthly_spent += past[-1].budget_verbrauch
        spent_pct = (
            round(monthly_spent / total_budget * 100, 1) if total_budget else 0.0
        )

        progress_vals = []
        for p in active:
            past = [s for s in by_project.get(p.id, []) if s.status_date <= m_end]
            if not past:
                continue
            past.sort(key=lambda s: s.status_date)
            progress_vals.append(past[-1].fortschritt)
        avg_progress = (
            round(sum(progress_vals) / len(progress_vals), 1) if progress_vals else 0.0
        )

        result.append(
            EarnedValuePoint(
                label=_month_label(m_start),
                budget_pct=budget_pct,
                spent_pct=spent_pct,
                progress_pct=avg_progress,
            )
        )
    return result


async def load_budget_burn() -> BudgetBurnKpi:
    today = _today()
    year_start = date(today.year, 1, 1)
    async with get_asyncdb_session() as session:
        projects = await _load_project_rows(session)
        history = await _load_status_rows(session, year_start)

    active = [
        p
        for p in projects
        if p.state in (ProjectStateEnum.ACTIVE.value, ProjectStateEnum.AT_RISK.value)
    ]
    total_budget = sum(p.budget or 0 for p in active)
    total_spent = sum(p.spent for p in active)
    summaries = [_project_summary(p, today) for p in active]
    spent_percent = (total_spent / total_budget * 100) if total_budget else 0.0

    by_project: dict[int, list[_StatusRow]] = defaultdict(list)
    for s in history:
        by_project[s.project_id].append(s)

    # Legacy weekly sparkline (backward compat for drill-down)
    weeks = _build_week_grid(today, TREND_WEEKS_BACK, 1)
    trend: list[TrendPoint] = []
    for week_start in weeks:
        week_end = week_start + timedelta(days=6)
        weekly_spent = 0
        for p in active:
            past = [s for s in by_project.get(p.id, []) if s.status_date <= week_end]
            if not past:
                continue
            past.sort(key=lambda s: s.status_date)
            weekly_spent += past[-1].budget_verbrauch
        trend.append(
            TrendPoint(
                label=_week_label(week_start),
                week_start=week_start,
                value=float(weekly_spent),
            )
        )

    # Monthly Earned Value series (Budget planned %, Spent %, Progress %)
    earned_value = _build_earned_value_series(active, by_project, total_budget, today)

    return BudgetBurnKpi(
        total_budget=total_budget,
        total_spent=total_spent,
        spent_percent=round(spent_percent, 1),
        trend=trend,
        earned_value=earned_value,
        rows=sorted(summaries, key=lambda s: -s.spent_percent),
    )


# --------------------------------------------------------------------------
# Utilization helpers (shared by cards 5, 6, 7)
# --------------------------------------------------------------------------


async def _load_utilization_inputs(
    weeks_back: int = TREND_WEEKS_BACK,
    weeks_forward: int = HORIZON_WEEKS,
    weeks: list[date] | None = None,
) -> tuple[
    list[_EmployeeRow],
    list[_AllocationRow],
    list[_RoleRow],
    list[date],
]:
    today = _today()
    week_starts = weeks or _build_week_grid(today, weeks_back, weeks_forward)
    async with get_asyncdb_session() as session:
        employees = await _load_employee_rows(session)
        roles = await _load_role_rows(session)
        allocations = await _load_allocation_rows(
            session,
            week_starts[0],
            week_starts[-1],
        )
        projects = await _load_project_rows(session)

    # Match heatmap: only count allocations for non-completed projects
    active_project_ids = {
        p.id for p in projects if p.state != ProjectStateEnum.COMPLETED.value
    }
    allocations = [a for a in allocations if a.project_id in active_project_ids]

    return employees, allocations, roles, week_starts


def _utilization_per_employee(
    series: TeamUtilizationSeries,
) -> list[EmployeeUtilization]:
    return [
        EmployeeUtilization(
            employee_id=employee.employee_id,
            name=employee.name,
            role_name=employee.role_name,
            avg_percent=employee.avg_percent,
            current_week_percent=employee.current_week_percent,
            current_week_is_absent=employee.current_week_is_absent,
            free_hours_next_4w=employee.free_hours_next_4w,
            weeks=[
                _weekly_utilization_result_to_model(week) for week in employee.weeks
            ],
        )
        for employee in series.employees
    ]


def _weekly_utilization_summary(
    series: TeamUtilizationSeries,
) -> list[WeeklyUtilization]:
    return [_weekly_utilization_result_to_model(week) for week in series.weeks]


def _weekly_utilization_result_to_model(
    week: WeekUtilizationResult,
) -> WeeklyUtilization:
    return WeeklyUtilization(
        week_label=week.week_label,
        week_start=week.week_start,
        used_days=week.used_days,
        available_days=week.available_days,
        percent=week.percent,
        bucket=week.bucket,
        is_absent=week.is_absent,
    )


def _to_utilization_employee(emp: _EmployeeRow) -> UtilizationEmployeeInput:
    return UtilizationEmployeeInput(
        employee_id=emp.id,
        name=f"{emp.first_name} {emp.last_name}".strip(),
        role_name=emp.role_names[0] if emp.role_names else "",
        internal_hours=emp.internal_hours,
        absences=tuple(
            AbsencePeriod(start_date=a.start_date, end_date=a.end_date)
            for a in emp.absences
        ),
    )


def _to_utilization_allocation(a: _AllocationRow) -> UtilizationAllocationInput:
    return UtilizationAllocationInput(
        project_id=a.project_id,
        employee_id=a.employee_id,
        week_start=a.week_start,
        person_days=a.person_days,
    )


def _utilization_series(
    employees: list[_EmployeeRow],
    allocations: list[_AllocationRow],
    weeks: list[date],
) -> TeamUtilizationSeries:
    today = _today()
    return UtilizationService.compute_team_utilization_series(
        employees=[_to_utilization_employee(emp) for emp in employees],
        allocations=[_to_utilization_allocation(a) for a in allocations],
        week_starts=weeks,
        current_week_start=_monday(today),
        free_capacity_start=_monday(today),
    )


# --------------------------------------------------------------------------
# Card 5 — utilization
# --------------------------------------------------------------------------


UTIL_WEEKS_BACK = 1
UTIL_WEEKS_FORWARD = 12


async def load_utilization() -> UtilizationKpi:
    planning_weeks = _build_planning_week_grid(UTIL_WEEKS_BACK + UTIL_WEEKS_FORWARD)
    employees, allocations, _roles, weeks = await _load_utilization_inputs(
        weeks_back=UTIL_WEEKS_BACK,
        weeks_forward=UTIL_WEEKS_FORWARD,
        weeks=planning_weeks,
    )
    series = _utilization_series(employees, allocations, weeks)
    breakdown = _utilization_per_employee(series)
    weekly_summary = _weekly_utilization_summary(series)

    today = _today()
    current_idx = next(
        (i for i, w in enumerate(weeks) if w == _monday(today)),
        UTIL_WEEKS_BACK,
    )
    current = weekly_summary[current_idx] if weekly_summary else None
    past_start = weekly_summary[0].week_label if weekly_summary else ""
    past_end = (
        weekly_summary[UTIL_WEEKS_BACK - 1].week_label
        if len(weekly_summary) >= UTIL_WEEKS_BACK
        else past_start
    )
    return UtilizationKpi(
        current_percent=current.percent if current else 0,
        current_bucket=current.bucket if current else "low",
        current_week=today.isocalendar().week,
        current_week_label=current.week_label if current else "",
        past_weeks_start_label=past_start,
        past_weeks_end_label=past_end,
        current_absent_count=sum(1 for emp in breakdown if emp.current_week_is_absent),
        weeks=weekly_summary,
        employee_breakdown=breakdown,
    )


# --------------------------------------------------------------------------
# Card 6 — under-utilization
# --------------------------------------------------------------------------


async def load_under_utilization() -> UnderUtilizationKpi:
    employees, allocations, _roles, weeks = await _load_utilization_inputs()
    breakdown = _utilization_per_employee(
        _utilization_series(employees, allocations, weeks)
    )

    active = [emp for emp in breakdown if not emp.current_week_is_absent]
    absent_count = len(breakdown) - len(active)
    affected = sorted(
        [emp for emp in active if emp.current_week_percent < UNDER_UTIL_THRESHOLD],
        key=lambda e: -e.free_hours_next_4w,
    )
    overloaded = [
        emp for emp in active if emp.current_week_percent > OVER_UTIL_THRESHOLD
    ]
    total_free = round(sum(e.free_hours_next_4w for e in affected), 1)
    return UnderUtilizationKpi(
        affected_count=len(affected),
        total_free_hours=total_free,
        total_employees=len(breakdown),
        overloaded_count=len(overloaded),
        absent_count=absent_count,
        top=affected[:3],
        rows=affected,
    )


# --------------------------------------------------------------------------
# Card 7 — free capacity per role
# --------------------------------------------------------------------------


def _monthly_role_capacity(
    emps: list[_EmployeeRow],
    role_id: int,
    alloc_by_role_week: dict[int, dict[date, float]],
    horizon_weeks: list[date],
    today: date,
) -> list[MonthlyRoleCapacity]:
    """Compute free capacity per month for the next 3 calendar months."""
    result: list[MonthlyRoleCapacity] = []
    for delta in range(3):
        m_month = (today.month - 1 + delta) % 12 + 1
        m_year = today.year + (today.month - 1 + delta) // 12
        label = _month_label(date(m_year, m_month, 1))
        month_weeks = [
            w for w in horizon_weeks if w.month == m_month and w.year == m_year
        ]
        m_avail = 0.0
        m_alloc = 0.0
        for week_start in month_weeks:
            m_avail += sum(_employee_available_days(e, week_start) for e in emps)
            m_alloc += alloc_by_role_week.get(role_id, {}).get(week_start, 0.0)
        m_free = max(0.0, m_avail - m_alloc)
        m_pct = round((m_free / m_avail) * 100) if m_avail > 0 else 0
        result.append(
            MonthlyRoleCapacity(
                label=label,
                free_percent=m_pct,
                free_days=round(m_free, 1),
                available_days=round(m_avail, 1),
            )
        )
    return result


async def load_free_capacity() -> FreeCapacityKpi:
    employees, allocations, roles, weeks = await _load_utilization_inputs()
    today = _today()
    horizon_weeks = [w for w in weeks if w >= _monday(today)][:HORIZON_WEEKS]
    if not horizon_weeks:
        return FreeCapacityKpi(horizon_weeks=HORIZON_WEEKS, rows=[])

    horizon_set = set(horizon_weeks)
    alloc_by_role_week: dict[int, dict[date, float]] = defaultdict(
        lambda: defaultdict(float),
    )
    for a in allocations:
        if a.week_start in horizon_set:
            alloc_by_role_week[a.role_id][a.week_start] += a.person_days

    role_employees: dict[int, list[_EmployeeRow]] = defaultdict(list)
    for emp in employees:
        for rid in emp.role_ids:
            role_employees[rid].append(emp)

    rows: list[RoleCapacity] = []
    for role in roles:
        emps = role_employees.get(role.id, [])
        weekly_points: list[TrendPoint] = []
        total_avail = 0.0
        total_alloc = 0.0
        for week_start in horizon_weeks:
            avail = sum(_employee_available_days(e, week_start) for e in emps)
            alloc = alloc_by_role_week.get(role.id, {}).get(week_start, 0.0)
            free = max(0.0, avail - alloc)
            total_avail += avail
            total_alloc += alloc
            weekly_points.append(
                TrendPoint(
                    label=_week_label(week_start),
                    week_start=week_start,
                    value=round(free, 1),
                )
            )
        free_total = max(0.0, total_avail - total_alloc)
        free_pct = round((free_total / total_avail) * 100) if total_avail > 0 else 0
        monthly = _monthly_role_capacity(
            emps, role.id, alloc_by_role_week, horizon_weeks, today
        )
        rows.append(
            RoleCapacity(
                role_id=role.id,
                role_name=role.name,
                color=role.color,
                available_days=round(total_avail, 1),
                allocated_days=round(total_alloc, 1),
                free_days=round(free_total, 1),
                free_percent=free_pct,
                weeks=weekly_points,
                employee_count=len(emps),
                employee_names=sorted(
                    f"{e.first_name} {e.last_name}".strip() for e in emps
                ),
                monthly=monthly,
            )
        )
    rows.sort(key=lambda r: -r.free_days)
    return FreeCapacityKpi(horizon_weeks=len(horizon_weeks), rows=rows)


# --------------------------------------------------------------------------
# Card 8 — risk surface
# --------------------------------------------------------------------------


async def load_risks() -> RiskKpi:
    today = _today()
    async with get_asyncdb_session() as session:
        risks = await _load_risk_rows(session)
        projects = await _load_project_rows(session)

    project_by_id = {p.id: p for p in projects}

    severity_count: dict[str, int] = defaultdict(int)
    for r in risks:
        severity_count[r.severity] += 1

    top_open: list[RiskItem] = []
    for r in risks:
        proj = project_by_id.get(r.project_id)
        top_open.append(
            RiskItem(
                id=r.id,
                project_id=r.project_id,
                project_code=proj.code if proj else "",
                project_name=proj.name_de if proj else "",
                name=r.name,
                severity=r.severity,
                probability=r.probability,
                impact=r.impact,
                score=r.probability * r.impact,
                mitigation_status=r.mitigation_status,
                owner=r.owner,
                updated_at=r.updated_date.isoformat() if r.updated_date else "",
            )
        )

    weeks = _build_week_grid(today, TREND_WEEKS_BACK, 1)
    trend: list[TrendPoint] = []
    for week_start in weeks:
        cutoff = week_start + timedelta(days=6)
        cnt = sum(1 for r in risks if r.created_date and r.created_date <= cutoff)
        trend.append(
            TrendPoint(
                label=_week_label(week_start),
                week_start=week_start,
                value=float(cnt),
            )
        )

    return RiskKpi(
        open_total=len(risks),
        open_high=severity_count.get(RiskLevel.HIGH.value, 0),
        open_medium=severity_count.get(RiskLevel.MEDIUM.value, 0),
        open_low=severity_count.get(RiskLevel.LOW.value, 0),
        top_open=top_open,
        trend=trend,
    )
