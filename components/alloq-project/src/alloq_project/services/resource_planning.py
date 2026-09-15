"""Simplified resource planning for one project.

Plans an employee in a role for a date range with a fixed number of days per
week. Weekly person-days are capped by the employee's free capacity (holidays,
absences, part-time, internal hours and other projects).
"""

import logging
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from alloq_commons.entities import CapacityEntity
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import (
    CapacityAllocation,
    ResourceCandidate,
    ResourcePeriod,
)
from alloq_commons.repositories import capacity_allocation_repo, capacity_repo
from alloq_commons.services.utilization import (
    WORK_DAYS_PER_WEEK,
    AbsencePeriod,
    UtilizationService,
)
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_EPSILON = 1e-6
_FRIDAY_OFFSET = 4


@dataclass(frozen=True)
class PlanTarget:
    """Who is planned on which project in which role."""

    project_id: int
    employee_id: int
    role_id: int


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_starts(start: date, end: date) -> list[date]:
    """Mondays from the week of ``start`` to the week of ``end`` (inclusive)."""
    if end < start:
        return []
    weeks: list[date] = []
    current = _monday(start)
    while current <= end:
        weeks.append(current)
        current += timedelta(weeks=1)
    return weeks


def _weekdays_in_range(week_start: date, start: date, end: date) -> int:
    """Count Mon-Fri days of the week that fall inside [start, end]."""
    first = max(week_start, start)
    last = min(week_start + timedelta(days=_FRIDAY_OFFSET), end)
    return max(0, (last - first).days + 1)


def weekly_free_days(
    employee: Employee,
    weeks: list[date],
    holidays: set[date],
    other_pt_by_week: dict[date, float],
) -> dict[date, float]:
    """Free person-days per week after holidays, absences, internal and others."""
    absences = [
        AbsencePeriod(start_date=a.start_date, end_date=a.end_date)
        for a in employee.absences
        if a.start_date and a.end_date
    ]
    free: dict[date, float] = {}
    for week in weeks:
        work_days = UtilizationService.work_days_for_week(
            week, holidays, workload_percent=employee.workload_percent
        )
        absence_days = UtilizationService.absence_days_in_week(absences, week)
        internal_days = UtilizationService.cap_internal_days(
            employee.internal_hours, absence_days, work_days=work_days
        )
        other = other_pt_by_week.get(week, 0.0)
        free[week] = max(0.0, work_days - absence_days - internal_days - other)
    return free


def _requested_days(week: date, start: date, end: date, days_per_week: float) -> float:
    return days_per_week * _weekdays_in_range(week, start, end) / WORK_DAYS_PER_WEEK


def plan_weekly_days(
    start: date,
    end: date,
    days_per_week: float,
    free_by_week: dict[date, float],
) -> list[tuple[date, float]]:
    """Weekly person-days to store: pro-rated request capped by free capacity."""
    planned: list[tuple[date, float]] = []
    for week in week_starts(start, end):
        requested = _requested_days(week, start, end, days_per_week)
        value = min(requested, free_by_week.get(week, 0.0))
        value = math.floor(value * 10 + _EPSILON) / 10
        if value > 0:
            planned.append((week, value))
    return planned


def find_candidates(  # noqa: PLR0913
    employees: list[Employee],
    role_id: int,
    *,
    start: date,
    end: date,
    days_per_week: float,
    holidays: set[date],
    other_pt: dict[int, dict[date, float]],
    planned_employee_ids: set[int],
) -> list[ResourceCandidate]:
    """Role holders with enough average free capacity, plus planned people."""
    weeks = week_starts(start, end)
    if not weeks:
        return []
    candidates: list[ResourceCandidate] = []
    for employee in employees:
        if role_id not in employee.role_ids:
            continue
        free = weekly_free_days(
            employee, weeks, holidays, other_pt.get(employee.id, {})
        )
        avg_free = sum(free.values()) / len(weeks)
        planned = employee.id in planned_employee_ids
        if not planned and avg_free + _EPSILON < days_per_week:
            continue
        conflicts = sum(
            1
            for week in weeks
            if free[week] + _EPSILON < _requested_days(week, start, end, days_per_week)
        )
        candidates.append(
            ResourceCandidate(
                employee_id=employee.id,
                name=f"{employee.first_name} {employee.last_name}".strip(),
                seniority=employee.seniority,
                avg_free_days=round(avg_free, 1),
                conflict_weeks=conflicts,
                already_planned=planned,
            )
        )
    candidates.sort(key=lambda c: (not c.already_planned, -c.avg_free_days, c.name))
    return candidates


def _build_period(
    employee_id: int,
    role_id: int,
    rows: list[tuple[date, float]],
    employee_names: dict[int, str],
    role_names: dict[int, str],
) -> ResourcePeriod:
    start = rows[0][0]
    values = [pd for _, pd in rows]
    return ResourcePeriod(
        key=f"{employee_id}-{role_id}-{start.isoformat()}",
        employee_id=employee_id,
        employee_name=employee_names.get(employee_id, ""),
        role_id=role_id,
        role_name=role_names.get(role_id, ""),
        start=start.isoformat(),
        end=(rows[-1][0] + timedelta(days=_FRIDAY_OFFSET)).isoformat(),
        days_per_week=Counter(values).most_common(1)[0][0],
        total_pt=round(sum(values), 1),
    )


def group_into_periods(
    allocations: list[CapacityAllocation],
    employee_names: dict[int, str],
    role_names: dict[int, str],
) -> list[ResourcePeriod]:
    """Group consecutive weekly allocations per (employee, role) into periods."""
    by_pair: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for alloc in allocations:
        if alloc.week_start is None or alloc.person_days <= 0:
            continue
        by_pair.setdefault((alloc.employee_id, alloc.role_id), []).append(
            (alloc.week_start, alloc.person_days)
        )

    periods: list[ResourcePeriod] = []
    for (employee_id, role_id), rows in by_pair.items():
        rows.sort()
        run: list[tuple[date, float]] = [rows[0]]
        for row in rows[1:]:
            if row[0] - run[-1][0] == timedelta(weeks=1):
                run.append(row)
                continue
            periods.append(
                _build_period(employee_id, role_id, run, employee_names, role_names)
            )
            run = [row]
        periods.append(
            _build_period(employee_id, role_id, run, employee_names, role_names)
        )
    periods.sort(key=lambda p: (p.employee_name, p.start, p.role_name))
    return periods


# ---------------------------------------------------------------------------
# Persistence (callers own the transaction)
# ---------------------------------------------------------------------------


async def _prune_capacities(
    session: AsyncSession, project_id: int, employee_id: int, role_ids: set[int]
) -> None:
    """Delete assignment rows of ``role_ids`` that no longer have allocations."""
    if not role_ids:
        return
    remaining = {
        row.role_id
        for row in await capacity_allocation_repo.find_by_project(session, project_id)
        if row.employee_id == employee_id
    }
    capacities = await capacity_repo.find_by_project_and_employee(
        session, project_id, employee_id
    )
    for capacity in capacities:
        if capacity.role_id in role_ids and capacity.role_id not in remaining:
            await session.delete(capacity)
    await session.flush()


async def _sync_capacity(
    session: AsyncSession, target: PlanTarget, start: date, end: date
) -> None:
    """Create or widen the (project, employee, role) assignment row."""
    capacities = await capacity_repo.find_by_project_and_employee(
        session, target.project_id, target.employee_id
    )
    existing = next((c for c in capacities if c.role_id == target.role_id), None)
    if existing is None:
        session.add(
            CapacityEntity(
                project_id=target.project_id,
                employee_id=target.employee_id,
                role_id=target.role_id,
                start_date=start,
                end_date=end,
                hours_per_week=40.0,
            )
        )
    else:
        existing.start_date = min(existing.start_date, start)
        existing.end_date = max(existing.end_date, end)
    await session.flush()


async def apply_resource_plan(
    session: AsyncSession,
    target: PlanTarget,
    start: date,
    end: date,
    days: list[tuple[date, float]],
) -> int:
    """Replace the employee's project allocations in the range with ``days``."""
    weeks = week_starts(start, end)
    if not weeks:
        return 0
    replaced = await capacity_allocation_repo.find_by_project_in_range(
        session, target.project_id, weeks[0], weeks[-1]
    )
    affected_roles = {
        r.role_id for r in replaced if r.employee_id == target.employee_id
    }
    await capacity_allocation_repo.delete_for_project_employee_in_range(
        session, target.project_id, target.employee_id, weeks[0], weeks[-1]
    )
    rows = [
        {
            "project_id": target.project_id,
            "employee_id": target.employee_id,
            "role_id": target.role_id,
            "week_start": week,
            "person_days": person_days,
        }
        for week, person_days in days
    ]
    await capacity_allocation_repo.batch_upsert(session, rows)
    if rows:
        await _sync_capacity(session, target, start, end)
    await _prune_capacities(
        session,
        target.project_id,
        target.employee_id,
        affected_roles - {target.role_id},
    )
    log.debug(
        "Planned employee %d on project %d: %d weeks",
        target.employee_id,
        target.project_id,
        len(rows),
    )
    return len(rows)


async def delete_resource_period(
    session: AsyncSession, target: PlanTarget, start: date, end: date
) -> int:
    """Delete one role's allocations in the range and prune its assignment."""
    weeks = week_starts(start, end)
    if not weeks:
        return 0
    deleted = await capacity_allocation_repo.delete_for_project_employee_in_range(
        session,
        target.project_id,
        target.employee_id,
        weeks[0],
        weeks[-1],
        role_id=target.role_id,
    )
    await _prune_capacities(
        session, target.project_id, target.employee_id, {target.role_id}
    )
    return deleted
