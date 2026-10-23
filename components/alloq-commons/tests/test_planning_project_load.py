"""Planning page project load: no allocation history, team from one query."""

from datetime import date

import pytest
from alloq_commons.entities import (
    CapacityAllocationEntity,
    EmployeeEntity,
    ProjectEntity,
    RequiredCapacityEntity,
    RoleEntity,
    SeniorityLevel,
)
from alloq_commons.repositories import (
    CapacityAllocationRepository,
    ProjectRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

# Staffing may start before and end after these dates.
START = date(2026, 3, 4)
END = date(2026, 3, 27)


def _employee(first: str, last: str) -> EmployeeEntity:
    return EmployeeEntity(
        first_name=first,
        last_name=last,
        seniority=SeniorityLevel.SENIOR.value,
        hours_per_week=40,
    )


async def _seed(
    session: AsyncSession, weeks: list[tuple[str, date, float]]
) -> ProjectEntity:
    """One project and role; one allocation per (last name, week, days)."""
    project = ProjectEntity(
        code="PLAN",
        name_de="Planung",
        start_date=START,
        end_date=END,
        budget=1000,
        color="#000000",
    )
    role = RoleEntity(name="Dev")
    employees = {last: _employee(last[0], last) for last, _, _ in weeks}
    session.add_all([project, role, *employees.values()])
    await session.flush()
    session.add(
        RequiredCapacityEntity(project_id=project.id, role_id=role.id, person_days=20)
    )
    session.add_all(
        CapacityAllocationEntity(
            project_id=project.id,
            employee_id=employees[last].id,
            role_id=role.id,
            week_start=week,
            person_days=days,
        )
        for last, week, days in weeks
    )
    await session.flush()
    session.expunge_all()
    return project


class TestFindAllForPlanning:
    @pytest.mark.asyncio
    async def test_skips_allocation_history(self, async_session: AsyncSession) -> None:
        await _seed(async_session, [("Berg", date(2026, 3, 9), 2.0)])

        projects = await ProjectRepository().find_all_for_planning(async_session)

        assert len(projects) == 1
        assert projects[0].capacity_allocations == []
        assert projects[0].to_dict()["team_initials"] == []

    @pytest.mark.asyncio
    async def test_keeps_required_capacities(self, async_session: AsyncSession) -> None:
        await _seed(async_session, [])

        projects = await ProjectRepository().find_all_for_planning(async_session)

        required = projects[0].to_dict()["required_capacities"]
        assert [rc["person_days"] for rc in required] == [20]


class TestFindStaffedEmployees:
    @pytest.mark.asyncio
    async def test_one_row_per_employee_outside_project_dates_too(
        self, async_session: AsyncSession
    ) -> None:
        project = await _seed(
            async_session,
            [
                ("Berg", date(2026, 2, 16), 1.0),
                ("Berg", date(2026, 3, 16), 2.0),
                ("Kern", date(2026, 4, 6), 3.0),
            ],
        )

        rows = await CapacityAllocationRepository().find_staffed_employees(
            async_session
        )

        assert [tuple(r) for r in rows] == [
            (project.id, "B", "Berg"),
            (project.id, "K", "Kern"),
        ]

    @pytest.mark.asyncio
    async def test_ignores_zero_days(self, async_session: AsyncSession) -> None:
        await _seed(async_session, [("Berg", date(2026, 3, 9), 0.0)])

        rows = await CapacityAllocationRepository().find_staffed_employees(
            async_session
        )

        assert rows == []

    @pytest.mark.asyncio
    async def test_sorted_by_name(self, async_session: AsyncSession) -> None:
        await _seed(
            async_session,
            [("Zander", date(2026, 3, 9), 1.0), ("Arndt", date(2026, 3, 9), 1.0)],
        )

        rows = await CapacityAllocationRepository().find_staffed_employees(
            async_session
        )

        assert [r.last_name for r in rows] == ["Arndt", "Zander"]
