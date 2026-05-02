"""Tests for project management entities, models, and repositories."""

from datetime import date

import pytest
from alloq_commons.entities import (
    CapacityEntity,
    EmployeeEntity,
    ProjectEntity,
    ProjectStatusEntity,
    RequiredCapacityEntity,
    RiskEntity,
    RiskLevel,
    RiskMitigationStatus,
    RoleEntity,
    SeniorityLevel,
)
from alloq_commons.models.project import Project, ProjectCreate, RequiredCapacityCreate
from alloq_commons.repositories import (
    CapacityRepository,
    ProjectRepository,
    RequiredCapacityRepository,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


class TestProjectEntity:
    """Tests for the ProjectEntity database model."""

    def test_create_entity(self) -> None:
        entity = ProjectEntity(
            code="ML-OPS",
            name_de="ML-Ops Plattform",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 12, 31),
            budget=300000,
            color="#F7C948",
        )
        assert entity.code == "ML-OPS"
        assert entity.budget == 300000
        assert entity.color == "#F7C948"

    def test_to_dict_includes_current_status_and_required_capacity(self) -> None:
        role = RoleEntity(name="AI Architect")
        role.id = 7
        required = RequiredCapacityEntity(role_id=7, person_days=20)
        required.id = 3
        required.project_id = 1
        required.role = role
        status = ProjectStatusEntity(
            project_id=1,
            status_date=date(2026, 6, 1),
            fortschritt=45,
            budget_verbrauch=30,
        )
        entity = ProjectEntity(
            code="ML-OPS",
            name_de="ML-Ops Plattform",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 12, 31),
            budget=300000,
            color="#F7C948",
        )
        entity.id = 1
        entity.created = None
        entity.updated = None
        entity.statuses = [status]
        entity.risks = []
        entity.capacities = []
        entity.required_capacities = [required]

        result = entity.to_dict()

        assert result["current_progress"] == 45
        assert result["current_spent"] == 30
        assert result["required_capacities"][0]["role_name"] == "AI Architect"


class TestProjectModels:
    """Tests for project Pydantic models."""

    def test_project_create_valid(self) -> None:
        project = ProjectCreate(
            code="ML-OPS",
            name_de="ML-Ops Plattform",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 12, 31),
            budget=300000,
            required_capacities=[RequiredCapacityCreate(role_id=1, person_days=20)],
        )
        assert project.code == "ML-OPS"
        assert project.required_capacities[0].person_days == 20

    def test_project_create_rejects_invalid_date_range(self) -> None:
        with pytest.raises(ValidationError):
            ProjectCreate(
                code="BAD",
                name_de="Bad",
                start_date=date(2026, 12, 31),
                end_date=date(2026, 6, 1),
                budget=1,
            )

    def test_project_team_count(self) -> None:
        project = Project(team_initials=["AH", "ML"])
        assert project.team_count == 2


class TestProjectRepository:
    """Tests for project repository operations."""

    @pytest.mark.asyncio
    async def test_find_by_code(self, async_session: AsyncSession) -> None:
        repo = ProjectRepository()
        entity = ProjectEntity(
            code="CRM-AI",
            name_de="CRM-Vorhersagemodell",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 8, 28),
            budget=480000,
            color="#F7C948",
        )
        await repo.create(async_session, entity)

        found = await repo.find_by_code(async_session, "CRM-AI")

        assert found is not None
        assert found.name_de == "CRM-Vorhersagemodell"

    @pytest.mark.asyncio
    async def test_find_all_paginated_with_search(
        self,
        async_session: AsyncSession,
    ) -> None:
        repo = ProjectRepository()
        async_session.add_all(
            [
                ProjectEntity(
                    code="CRM-AI",
                    name_de="CRM-Vorhersagemodell",
                    start_date=date(2026, 3, 2),
                    end_date=date(2026, 8, 28),
                    budget=480000,
                    color="#F7C948",
                ),
                ProjectEntity(
                    code="VISION",
                    name_de="Computer-Vision Plattform",
                    start_date=date(2026, 1, 12),
                    end_date=date(2026, 9, 30),
                    budget=720000,
                    color="#5B7FA3",
                ),
            ]
        )
        await async_session.flush()

        results = await repo.find_all_paginated(async_session, search="vision")

        assert len(results) == 1
        assert results[0].code == "VISION"


class TestCapacityRepositories:
    """Tests for capacity repository relationship queries."""

    async def _seed_project_employee_role(
        self,
        session: AsyncSession,
    ) -> tuple[ProjectEntity, EmployeeEntity, RoleEntity]:
        role = RoleEntity(name="Architect")
        employee = EmployeeEntity(
            first_name="Anna",
            last_name="Hoffmann",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40,
        )
        project = ProjectEntity(
            code="ARCH",
            name_de="Architektur",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget=100000,
            color="#8D6AA5",
        )
        session.add_all([role, employee, project])
        await session.flush()
        return project, employee, role

    @pytest.mark.asyncio
    async def test_find_by_project_and_employee(
        self,
        async_session: AsyncSession,
    ) -> None:
        project, employee, role = await self._seed_project_employee_role(async_session)
        repo = CapacityRepository()
        async_session.add(
            CapacityEntity(
                project_id=project.id,
                employee_id=employee.id,
                role_id=role.id,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 3, 31),
                hours_per_week=20,
            )
        )
        await async_session.flush()

        results = await repo.find_by_project_and_employee(
            async_session,
            project.id,
            employee.id,
        )

        assert len(results) == 1
        assert results[0].hours_per_week == 20

    @pytest.mark.asyncio
    async def test_required_capacity_find_by_project(
        self,
        async_session: AsyncSession,
    ) -> None:
        project, _employee, role = await self._seed_project_employee_role(async_session)
        repo = RequiredCapacityRepository()
        async_session.add(
            RequiredCapacityEntity(
                project_id=project.id,
                role_id=role.id,
                person_days=20,
            )
        )
        await async_session.flush()

        results = await repo.find_by_project_id(async_session, project.id)

        assert len(results) == 1
        assert results[0].person_days == 20


class TestRiskEntity:
    """Tests for project risk entity values."""

    def test_create_risk(self) -> None:
        risk = RiskEntity(
            project_id=1,
            name="Delivery delay",
            description="External dependency may slip",
            severity=RiskLevel.HIGH.value,
            probability=RiskLevel.MEDIUM.value,
            impact=RiskLevel.HIGH.value,
            mitigation_status=RiskMitigationStatus.OPEN.value,
            owner="Anna Hoffmann",
        )
        assert risk.severity == "high"
        assert risk.mitigation_status == "open"
