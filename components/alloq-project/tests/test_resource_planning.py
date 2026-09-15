"""Tests for the simplified per-project resource planning service."""

from datetime import date

import pytest
from alloq_commons.entities import (
    CapacityAllocationEntity,
    CapacityEntity,
    EmployeeEntity,
    ProjectEntity,
    RoleEntity,
)
from alloq_commons.models.employee import Absence, Employee
from alloq_commons.models.project import CapacityAllocation
from alloq_commons.repositories import capacity_allocation_repo, capacity_repo
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
from sqlalchemy.ext.asyncio import AsyncSession

W1 = date(2026, 9, 14)  # Monday
W2 = date(2026, 9, 21)
W3 = date(2026, 9, 28)
W5 = date(2026, 10, 12)


def _employee(
    employee_id: int = 1,
    *,
    first_name: str = "Anna",
    role_ids: list[int] | None = None,
    hours_per_week: float = 40.0,
    internal_hours: int = 0,
    absences: list[Absence] | None = None,
) -> Employee:
    return Employee(
        id=employee_id,
        first_name=first_name,
        last_name="Test",
        seniority="Senior",
        role_ids=role_ids if role_ids is not None else [3],
        hours_per_week=hours_per_week,
        internal_hours=internal_hours,
        absences=absences or [],
    )


def _alloc(
    week: date, person_days: float, *, employee_id: int = 1, role_id: int = 3
) -> CapacityAllocation:
    return CapacityAllocation(
        project_id=1,
        employee_id=employee_id,
        role_id=role_id,
        week_start=week,
        person_days=person_days,
    )


class TestWeekStarts:
    """Tests for week_starts."""

    def test_spans_mondays_across_year_boundary(self) -> None:
        weeks = week_starts(date(2026, 12, 30), date(2027, 1, 6))

        assert weeks == [date(2026, 12, 28), date(2027, 1, 4)]

    def test_single_week(self) -> None:
        assert week_starts(date(2026, 9, 16), date(2026, 9, 18)) == [W1]

    def test_end_before_start_is_empty(self) -> None:
        assert week_starts(W2, W1) == []


class TestWeeklyFreeDays:
    """Tests for weekly_free_days."""

    def test_full_week_without_constraints(self) -> None:
        free = weekly_free_days(_employee(), [W1], set(), {})

        assert free == {W1: 5.0}

    def test_holiday_reduces_capacity(self) -> None:
        free = weekly_free_days(_employee(), [W1], {date(2026, 9, 16)}, {})

        assert free[W1] == 4.0

    def test_absence_reduces_capacity(self) -> None:
        absence = Absence(start_date=W1, end_date=date(2026, 9, 15))

        free = weekly_free_days(_employee(absences=[absence]), [W1], set(), {})

        assert free[W1] == 3.0

    def test_part_time_scales_capacity(self) -> None:
        free = weekly_free_days(_employee(hours_per_week=20.0), [W1], set(), {})

        assert free[W1] == 2.5

    def test_internal_hours_reduce_capacity(self) -> None:
        free = weekly_free_days(_employee(internal_hours=8), [W1], set(), {})

        assert free[W1] == 4.0

    def test_other_projects_reduce_and_floor_at_zero(self) -> None:
        free = weekly_free_days(_employee(), [W1, W2], set(), {W1: 2.0, W2: 7.0})

        assert free == {W1: 3.0, W2: 0.0}


class TestPlanWeeklyDays:
    """Tests for plan_weekly_days."""

    def test_pro_rates_partial_first_week(self) -> None:
        days = plan_weekly_days(
            date(2026, 9, 16), date(2026, 9, 25), 3.0, {W1: 5.0, W2: 5.0}
        )

        assert days == [(W1, 1.8), (W2, 3.0)]

    def test_caps_at_free_capacity(self) -> None:
        days = plan_weekly_days(W1, date(2026, 9, 25), 3.0, {W1: 1.0, W2: 5.0})

        assert days == [(W1, 1.0), (W2, 3.0)]

    def test_skips_weeks_without_capacity(self) -> None:
        days = plan_weekly_days(W1, date(2026, 9, 25), 3.0, {W1: 0.0, W2: 5.0})

        assert days == [(W2, 3.0)]


class TestFindCandidates:
    """Tests for find_candidates."""

    def _find(self, employees: list[Employee], planned: set[int] | None = None) -> list:
        other_pt = {
            2: {W1: 5.0},
            3: {W1: 4.0, W2: 4.0},
        }
        return find_candidates(
            employees,
            role_id=3,
            start=W1,
            end=date(2026, 9, 25),
            days_per_week=2.0,
            holidays=set(),
            other_pt=other_pt,
            planned_employee_ids=planned or set(),
        )

    def test_uses_average_not_minimum(self) -> None:
        result = self._find([_employee(2, first_name="Bert")])

        assert len(result) == 1
        assert result[0].avg_free_days == 2.5
        assert result[0].conflict_weeks == 1

    def test_excludes_below_threshold_and_other_roles(self) -> None:
        employees = [
            _employee(1),
            _employee(3, first_name="Carl"),
            _employee(4, first_name="Dora", role_ids=[9]),
        ]

        result = self._find(employees)

        assert [c.employee_id for c in result] == [1]
        assert result[0].conflict_weeks == 0

    def test_planned_people_always_included_first(self) -> None:
        employees = [_employee(1), _employee(3, first_name="Carl")]

        result = self._find(employees, planned={3})

        assert [c.employee_id for c in result] == [3, 1]
        assert result[0].already_planned is True
        assert result[0].name == "Carl Test"


class TestGroupIntoPeriods:
    """Tests for group_into_periods."""

    def test_groups_consecutive_weeks_per_role(self) -> None:
        allocations = [
            _alloc(W1, 3.0),
            _alloc(W2, 3.0),
            _alloc(W3, 2.0),
            _alloc(W5, 3.0),
            _alloc(W1, 1.0, role_id=4),
            _alloc(W2, 0.0, role_id=4),
        ]

        periods = group_into_periods(
            allocations, {1: "Anna Test"}, {3: "Dev", 4: "Architekt"}
        )

        assert [(p.role_name, p.start, p.end) for p in periods] == [
            ("Architekt", "2026-09-14", "2026-09-18"),
            ("Dev", "2026-09-14", "2026-10-02"),
            ("Dev", "2026-10-12", "2026-10-16"),
        ]
        dev = periods[1]
        assert dev.days_per_week == 3.0
        assert dev.total_pt == 8.0
        assert dev.employee_name == "Anna Test"
        assert dev.key == "1-3-2026-09-14"

    def test_empty(self) -> None:
        assert group_into_periods([], {}, {}) == []


# ============================================================================
# Persistence (SQLite)
# ============================================================================


async def _seed(session: AsyncSession) -> tuple[int, int, int, int]:
    project = ProjectEntity(
        code="RES",
        customer="Kunde",
        name_de="Ressourcen",
        start_date=W1,
        end_date=date(2026, 12, 31),
        budget=1000,
    )
    employee = EmployeeEntity(first_name="Anna", last_name="Test", seniority="Senior")
    dev = RoleEntity(name="Dev", abbreviation="DEV")
    arch = RoleEntity(name="Architekt", abbreviation="ARC")
    session.add_all([project, employee, dev, arch])
    await session.flush()
    return project.id, employee.id, dev.id, arch.id


async def _rows(session: AsyncSession, project_id: int) -> list[tuple]:
    rows = await capacity_allocation_repo.find_by_project(session, project_id)
    return sorted((r.week_start, r.role_id, r.person_days) for r in rows)


async def _capacity_roles(
    session: AsyncSession, project_id: int, employee_id: int
) -> dict[int, tuple[date, date]]:
    caps = await capacity_repo.find_by_project_and_employee(
        session, project_id, employee_id
    )
    return {c.role_id: (c.start_date, c.end_date) for c in caps}


def _entity(
    project_id: int, employee_id: int, role_id: int, week: date, pd: float
) -> CapacityAllocationEntity:
    return CapacityAllocationEntity(
        project_id=project_id,
        employee_id=employee_id,
        role_id=role_id,
        week_start=week,
        person_days=pd,
    )


class TestApplyResourcePlan:
    """Tests for apply_resource_plan."""

    @pytest.mark.asyncio
    async def test_replaces_only_weeks_in_range_for_all_roles(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, dev, arch = await _seed(async_session)
        async_session.add_all(
            [_entity(pid, eid, dev, w, 3.0) for w in (W1, W2, W3)]
            + [
                CapacityEntity(
                    project_id=pid,
                    employee_id=eid,
                    role_id=dev,
                    start_date=W1,
                    end_date=date(2026, 10, 2),
                )
            ]
        )
        await async_session.flush()

        count = await apply_resource_plan(
            async_session,
            PlanTarget(pid, eid, arch),
            W2,
            date(2026, 9, 25),
            [(W2, 2.0)],
        )

        assert count == 1
        assert await _rows(async_session, pid) == [
            (W1, dev, 3.0),
            (W2, arch, 2.0),
            (W3, dev, 3.0),
        ]
        caps = await _capacity_roles(async_session, pid, eid)
        assert caps[arch] == (W2, date(2026, 9, 25))
        assert dev in caps

    @pytest.mark.asyncio
    async def test_prunes_capacity_of_role_without_remaining_rows(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, dev, arch = await _seed(async_session)
        async_session.add_all(
            [
                _entity(pid, eid, dev, W2, 3.0),
                CapacityEntity(
                    project_id=pid,
                    employee_id=eid,
                    role_id=dev,
                    start_date=W2,
                    end_date=date(2026, 9, 25),
                ),
            ]
        )
        await async_session.flush()

        await apply_resource_plan(
            async_session,
            PlanTarget(pid, eid, arch),
            W2,
            date(2026, 9, 25),
            [(W2, 2.0)],
        )

        assert set(await _capacity_roles(async_session, pid, eid)) == {arch}

    @pytest.mark.asyncio
    async def test_widens_existing_capacity(self, async_session: AsyncSession) -> None:
        pid, eid, dev, _ = await _seed(async_session)
        async_session.add(
            CapacityEntity(
                project_id=pid,
                employee_id=eid,
                role_id=dev,
                start_date=W2,
                end_date=date(2026, 9, 25),
            )
        )
        await async_session.flush()

        await apply_resource_plan(
            async_session,
            PlanTarget(pid, eid, dev),
            W1,
            date(2026, 10, 2),
            [(W1, 3.0), (W2, 3.0), (W3, 3.0)],
        )

        caps = await _capacity_roles(async_session, pid, eid)
        assert caps == {dev: (W1, date(2026, 10, 2))}


class TestDeleteResourcePeriod:
    """Tests for delete_resource_period."""

    @pytest.mark.asyncio
    async def test_keeps_capacity_while_rows_remain(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, dev, arch = await _seed(async_session)
        await apply_resource_plan(
            async_session,
            PlanTarget(pid, eid, dev),
            W1,
            date(2026, 10, 2),
            [(W1, 3.0), (W2, 3.0), (W3, 3.0)],
        )
        async_session.add(_entity(pid, eid, arch, W2, 1.0))
        await async_session.flush()

        deleted = await delete_resource_period(
            async_session, PlanTarget(pid, eid, dev), W2, date(2026, 9, 25)
        )

        assert deleted == 1
        assert await _rows(async_session, pid) == [
            (W1, dev, 3.0),
            (W2, arch, 1.0),
            (W3, dev, 3.0),
        ]
        assert dev in await _capacity_roles(async_session, pid, eid)

    @pytest.mark.asyncio
    async def test_removes_capacity_when_no_rows_left(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, dev, _ = await _seed(async_session)
        await apply_resource_plan(
            async_session,
            PlanTarget(pid, eid, dev),
            W1,
            date(2026, 9, 25),
            [(W1, 3.0), (W2, 3.0)],
        )

        await delete_resource_period(
            async_session, PlanTarget(pid, eid, dev), W1, date(2026, 9, 25)
        )

        assert await _rows(async_session, pid) == []
        assert await _capacity_roles(async_session, pid, eid) == {}


class TestDeleteInRangeRepository:
    """Tests for CapacityAllocationRepository.delete_for_project_employee_in_range."""

    @pytest.mark.asyncio
    async def test_with_and_without_role_filter(
        self, async_session: AsyncSession
    ) -> None:
        pid, eid, dev, arch = await _seed(async_session)
        async_session.add_all(
            [
                _entity(pid, eid, dev, W1, 1.0),
                _entity(pid, eid, arch, W1, 1.0),
                _entity(pid, eid, dev, W2, 1.0),
                _entity(pid, eid, dev, W3, 1.0),
            ]
        )
        await async_session.flush()

        by_role = await capacity_allocation_repo.delete_for_project_employee_in_range(
            async_session, pid, eid, W1, W2, role_id=dev
        )
        all_roles = await capacity_allocation_repo.delete_for_project_employee_in_range(
            async_session, pid, eid, W1, W2
        )

        assert by_role == 2
        assert all_roles == 1
        assert await _rows(async_session, pid) == [(W3, dev, 1.0)]
