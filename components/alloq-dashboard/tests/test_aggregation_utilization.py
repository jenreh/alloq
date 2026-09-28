"""Tests for dashboard utilization, capacity, and budget aggregation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from alloq_commons.entities.project import ProjectStateEnum
from alloq_dashboard.services import aggregation

_MOD = "alloq_dashboard.services.aggregation"
# Wednesday, far outside the historic planning anchor window (2026-04-27 + 13w).
_TODAY = date(2026, 9, 30)
_MONDAY = date(2026, 9, 28)


@asynccontextmanager
async def _fake_session() -> AsyncIterator[object]:
    yield object()


def _employee(
    eid: int,
    *,
    role_ids: tuple[int, ...] = (1,),
    absences: tuple[aggregation._AbsenceRow, ...] = (),
    hours_per_week: float = 40.0,
) -> aggregation._EmployeeRow:
    return aggregation._EmployeeRow(
        id=eid,
        first_name=f"E{eid}",
        last_name="",
        hours_per_week=hours_per_week,
        internal_hours=0,
        role_ids=role_ids,
        role_names=tuple(f"R{r}" for r in role_ids),
        absences=absences,
    )


def _alloc(
    eid: int, week: date, days: float, role_id: int = 1
) -> aggregation._AllocationRow:
    return aggregation._AllocationRow(
        project_id=1,
        employee_id=eid,
        role_id=role_id,
        week_start=week,
        person_days=days,
    )


def _project_row(
    pid: int = 1,
    *,
    state: str = ProjectStateEnum.ACTIVE.value,
    budget: int = 100_000,
    spent: int = 0,
    end_date: date | None = None,
) -> aggregation._ProjectRow:
    return aggregation._ProjectRow(
        id=pid,
        code=f"P{pid}",
        name_de=f"Projekt {pid}",
        state=state,
        start_date=None,
        end_date=end_date,
        budget=budget,
        color="#888",
        progress=0,
        spent=spent,
        open_risk_count=0,
    )


@contextmanager
def _utilization_inputs(
    employees: list[aggregation._EmployeeRow],
    allocations: list[aggregation._AllocationRow],
    roles: list[aggregation._RoleRow] | None = None,
    holidays: frozenset[date] = frozenset(),
) -> Iterator[None]:
    async def employee_rows(_session: object) -> list[aggregation._EmployeeRow]:
        return employees

    async def role_rows(_session: object) -> list[aggregation._RoleRow]:
        return roles or []

    async def allocation_rows(
        _session: object, start: date, end: date
    ) -> list[aggregation._AllocationRow]:
        return [a for a in allocations if start <= a.week_start <= end]

    async def project_rows(_session: object) -> list[aggregation._ProjectRow]:
        return [_project_row()]

    async def holiday_dates(_session: object, start: date, end: date) -> set[date]:
        return {d for d in holidays if start <= d <= end}

    with (
        patch(f"{_MOD}.get_asyncdb_session", _fake_session),
        patch(f"{_MOD}._load_employee_rows", employee_rows),
        patch(f"{_MOD}._load_role_rows", role_rows),
        patch(f"{_MOD}._load_allocation_rows", allocation_rows),
        patch(f"{_MOD}._load_project_rows", project_rows),
        patch(f"{_MOD}._load_holiday_dates", holiday_dates),
        patch(f"{_MOD}._today", return_value=_TODAY),
    ):
        yield


# ---------------------------------------------------------------------------
# Card 5 — utilization uses a today-based week grid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_utilization_current_week_follows_today() -> None:
    employees = [
        _employee(1),  # 100 %
        _employee(2),  # 120 % -> overloaded
        _employee(3),  # 0 % -> under-utilized
        _employee(
            4,
            absences=(
                aggregation._AbsenceRow(
                    start_date=_MONDAY, end_date=_MONDAY + timedelta(days=4)
                ),
            ),
        ),
    ]
    allocations = [_alloc(1, _MONDAY, 5.0), _alloc(2, _MONDAY, 6.0)]
    with _utilization_inputs(employees, allocations):
        payload = await aggregation.load_utilization()

    assert payload.current_week == _MONDAY.isocalendar().week
    assert payload.current_week_label == "KW40"
    assert _MONDAY in [w.week_start for w in payload.weeks]
    by_id = {e.employee_id: e for e in payload.employee_breakdown}
    assert by_id[1].current_week_percent == 100
    assert by_id[2].current_week_percent == 120
    assert by_id[4].current_week_is_absent is True
    assert payload.current_absent_count == 1
    assert payload.overloaded_count == 1
    assert payload.well_utilized_count == 1
    assert payload.under_utilized_count == 1


@pytest.mark.asyncio
async def test_load_under_utilization_counts_match_utilization() -> None:
    employees = [_employee(1), _employee(2), _employee(3)]
    allocations = [_alloc(1, _MONDAY, 5.0), _alloc(2, _MONDAY, 6.0)]
    with _utilization_inputs(employees, allocations):
        under = await aggregation.load_under_utilization()
        util = await aggregation.load_utilization()

    assert under.overloaded_count == util.overloaded_count == 1
    assert under.affected_count == util.under_utilized_count == 1
    assert under.total_employees == 3


@pytest.mark.asyncio
async def test_load_utilization_uses_holidays_and_workload_like_the_grid() -> None:
    """Holidays and part-time workload reduce capacity, as in the planning grid."""
    employees = [_employee(1), _employee(2, hours_per_week=20.0)]
    allocations = [_alloc(1, _MONDAY, 4.0), _alloc(2, _MONDAY, 2.0)]
    with _utilization_inputs(employees, allocations, holidays=frozenset({_MONDAY})):
        payload = await aggregation.load_utilization()

    by_id = {e.employee_id: e for e in payload.employee_breakdown}
    assert by_id[1].current_week_percent == 100  # 4 of 4 work days
    assert by_id[2].current_week_percent == 100  # 2 of 50 % * 4 work days
    current = next(w for w in payload.weeks if w.week_start == _MONDAY)
    assert current.available_days == 6.0


@pytest.mark.asyncio
async def test_free_capacity_subtracts_holidays_and_workload() -> None:
    employees = [_employee(1, hours_per_week=20.0)]
    roles = [aggregation._RoleRow(id=1, name="Dev")]
    with _utilization_inputs(employees, [], roles, holidays=frozenset({_MONDAY})):
        payload = await aggregation.load_free_capacity()

    first_week = payload.rows[0].weeks[0]
    assert first_week.week_start == _MONDAY
    assert first_week.value == 2.0


# ---------------------------------------------------------------------------
# Card 7 — free capacity per role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_capacity_does_not_double_count_multi_role_employee() -> None:
    horizon = [_MONDAY + timedelta(weeks=i) for i in range(aggregation.HORIZON_WEEKS)]
    employees = [
        _employee(1, role_ids=(1, 2)),  # fully booked under role 1
        _employee(2, role_ids=(2,)),  # free, role 2 only
    ]
    allocations = [_alloc(1, w, 5.0, role_id=1) for w in horizon]
    roles = [
        aggregation._RoleRow(id=1, name="Dev"),
        aggregation._RoleRow(id=2, name="Architect"),
    ]
    with _utilization_inputs(employees, allocations, roles):
        payload = await aggregation.load_free_capacity()

    by_role = {r.role_id: r for r in payload.rows}
    full_horizon_days = 5.0 * len(horizon)
    assert by_role[1].free_days == 0
    assert by_role[2].free_days == full_horizon_days
    assert by_role[2].available_days == full_horizon_days
    assert all(p.value == 5.0 for p in by_role[2].weeks)
    assert sum(m.free_days for m in by_role[1].monthly) == 0


# ---------------------------------------------------------------------------
# budget_spent is a percentage, not an amount
# ---------------------------------------------------------------------------


def test_project_summary_treats_budget_spent_as_percent() -> None:
    summary = aggregation._project_summary(
        _project_row(budget=100_000, spent=40), _TODAY
    )
    assert summary.spent_percent == 40.0
    assert summary.spent == 40_000


@pytest.mark.asyncio
async def test_load_budget_burn_totals_spent_amount() -> None:
    projects = [
        _project_row(1, budget=100_000, spent=40),
        _project_row(2, budget=50_000, spent=10),
    ]

    async def project_rows(_session: object) -> list[aggregation._ProjectRow]:
        return projects

    async def status_rows(_session: object, _ids: list[int]) -> list[object]:
        return []

    with (
        patch(f"{_MOD}.get_asyncdb_session", _fake_session),
        patch(f"{_MOD}._load_project_rows", project_rows),
        patch(f"{_MOD}._load_status_rows_for_projects", status_rows),
        patch(f"{_MOD}._today", return_value=_TODAY),
    ):
        payload = await aggregation.load_budget_burn()

    assert payload.total_budget == 150_000
    assert payload.total_spent == 45_000
    assert payload.spent_percent == 30.0


# ---------------------------------------------------------------------------
# Card 2 — project health ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_health_sorts_due_today_before_missing_end_date() -> None:
    at_risk = ProjectStateEnum.AT_RISK.value
    projects = [
        _project_row(1, state=at_risk, end_date=None),
        _project_row(2, state=at_risk, end_date=_TODAY),
        _project_row(3, state=at_risk, end_date=_TODAY + timedelta(days=10)),
    ]

    async def project_rows(_session: object) -> list[aggregation._ProjectRow]:
        return projects

    async def risk_rows(_session: object) -> list[aggregation._RiskRow]:
        return []

    with (
        patch(f"{_MOD}.get_asyncdb_session", _fake_session),
        patch(f"{_MOD}._load_project_rows", project_rows),
        patch(f"{_MOD}._load_risk_rows", risk_rows),
        patch(f"{_MOD}._today", return_value=_TODAY),
    ):
        payload = await aggregation.load_project_health()

    assert [r.id for r in payload.rows] == [2, 3, 1]


# ---------------------------------------------------------------------------
# Card 8 — risks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_risks_maps_top_open_risks_and_trend() -> None:
    risk = aggregation._RiskRow(
        id=7,
        project_id=1,
        name="Lieferverzug",
        severity=aggregation.RiskLevel.HIGH.value,
        probability=4,
        impact=5,
        mitigation_status="open",
        owner="PM",
        created_date=_MONDAY,
        updated_date=_TODAY,
    )

    async def risk_rows(_session: object) -> list[aggregation._RiskRow]:
        return [risk]

    async def project_rows(_session: object) -> list[aggregation._ProjectRow]:
        return [_project_row(1)]

    with (
        patch(f"{_MOD}.get_asyncdb_session", _fake_session),
        patch(f"{_MOD}._load_risk_rows", risk_rows),
        patch(f"{_MOD}._load_project_rows", project_rows),
        patch(f"{_MOD}._today", return_value=_TODAY),
    ):
        payload = await aggregation.load_risks()

    assert payload.open_total == 1
    assert payload.open_high == 1
    [item] = payload.top_open
    assert (item.project_code, item.score, item.updated_at) == ("P1", 20, "2026-09-30")
    # Created in the current week: absent from past weeks, present from today on.
    assert [p.value for p in payload.trend] == [0.0, 0.0, 1.0]
