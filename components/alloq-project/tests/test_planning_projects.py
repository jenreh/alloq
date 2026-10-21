"""Planning project load: team initials without the allocation history."""

from datetime import date

import pytest
from alloq_commons.entities import (
    CapacityAllocationEntity,
    EmployeeEntity,
    ProjectEntity,
    RoleEntity,
    SeniorityLevel,
)
from alloq_project.services.planning_projects import (
    load_planning_projects,
    team_initials_by_project,
)
from sqlalchemy.ext.asyncio import AsyncSession


class TestTeamInitialsByProject:
    def test_groups_by_project_in_row_order(self) -> None:
        rows = [(1, "Anna", "Arndt"), (2, "Ben", "Berg"), (1, "Zoe", "Zander")]

        assert team_initials_by_project(rows) == {1: ["AA", "ZZ"], 2: ["BB"]}

    def test_empty(self) -> None:
        assert team_initials_by_project([]) == {}


class TestLoadPlanningProjects:
    @pytest.mark.asyncio
    async def test_staffing_outside_project_dates_counts(
        self, async_session: AsyncSession
    ) -> None:
        project = ProjectEntity(
            code="PLAN",
            name_de="Planung",
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 27),
            budget=1000,
            color="#000000",
        )
        early = EmployeeEntity(
            first_name="Anna",
            last_name="Berg",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40,
        )
        late = EmployeeEntity(
            first_name="Carl",
            last_name="Kern",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40,
        )
        role = RoleEntity(name="Dev")
        async_session.add_all([project, early, late, role])
        await async_session.flush()
        async_session.add_all(
            CapacityAllocationEntity(
                project_id=project.id,
                employee_id=employee.id,
                role_id=role.id,
                week_start=week,
                person_days=2.0,
            )
            for employee, week in [
                (early, date(2026, 2, 16)),
                (late, date(2026, 4, 13)),
            ]
        )
        await async_session.flush()
        async_session.expunge_all()

        projects = await load_planning_projects(async_session)

        assert [(p.code, p.team_initials) for p in projects] == [("PLAN", ["AB", "CK"])]
