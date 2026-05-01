"""Tests for team member (employee) management."""

from datetime import date

import pytest
from alloq_commons.entities.absence import AbsenceEntity
from alloq_commons.entities.employee import EmployeeEntity, SeniorityLevel
from alloq_commons.entities.role import RoleEntity
from alloq_commons.repositories.absence_repository import AbsenceRepository
from alloq_commons.repositories.employee_repository import EmployeeRepository
from alloq_team.models.employee import (
    Absence,
    AbsenceCreate,
    Employee,
    EmployeeCreate,
    EmployeeUpdate,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Entity Tests
# ============================================================================


class TestEmployeeEntity:
    """Tests for the EmployeeEntity database model."""

    def test_create_entity(self) -> None:
        entity = EmployeeEntity(
            first_name="Max",
            last_name="Mustermann",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40.0,
        )
        assert entity.first_name == "Max"
        assert entity.last_name == "Mustermann"
        assert entity.seniority == "Senior"
        assert entity.hours_per_week == 40.0

    def test_to_dict(self) -> None:
        entity = EmployeeEntity(
            first_name="Anna",
            last_name="Schmidt",
            seniority=SeniorityLevel.EXPERT.value,
            job_title="Software Engineer",
            hours_per_week=32.0,
        )
        entity.id = 5
        entity.created = None
        entity.updated = None
        entity.roles = []
        result = entity.to_dict()
        assert result["id"] == 5
        assert result["first_name"] == "Anna"
        assert result["last_name"] == "Schmidt"
        assert result["job_title"] == "Software Engineer"
        assert result["seniority"] == "Expert"
        assert result["role_ids"] == []
        assert result["role_names"] == []
        assert result["hours_per_week"] == 32.0

    def test_tablename(self) -> None:
        assert EmployeeEntity.__tablename__ == "employees"


class TestAbsenceEntity:
    """Tests for the AbsenceEntity database model."""

    def test_create_entity(self) -> None:
        entity = AbsenceEntity(
            employee_id=1,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 14),
        )
        assert entity.employee_id == 1
        assert entity.start_date == date(2025, 6, 1)
        assert entity.end_date == date(2025, 6, 14)

    def test_to_dict(self) -> None:
        entity = AbsenceEntity(
            employee_id=3,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 5),
        )
        entity.id = 10
        entity.created = None
        entity.updated = None
        result = entity.to_dict()
        assert result["id"] == 10
        assert result["employee_id"] == 3
        assert result["start_date"] == date(2025, 7, 1)
        assert result["end_date"] == date(2025, 7, 5)

    def test_tablename(self) -> None:
        assert AbsenceEntity.__tablename__ == "absences"


class TestSeniorityLevel:
    """Tests for SeniorityLevel enum."""

    def test_values(self) -> None:
        assert SeniorityLevel.ADVANCED.value == "Advanced"
        assert SeniorityLevel.SENIOR.value == "Senior"
        assert SeniorityLevel.EXPERT.value == "Expert"

    def test_enum_count(self) -> None:
        assert len(SeniorityLevel) == 4


# ============================================================================
# Model Tests
# ============================================================================


class TestEmployeeModel:
    """Tests for the Employee Pydantic read model."""

    def test_defaults(self) -> None:
        emp = Employee()
        assert emp.id == 0
        assert emp.first_name == ""
        assert emp.last_name == ""
        assert emp.seniority == ""
        assert emp.role_ids == []
        assert emp.role_names == []
        assert emp.hours_per_week == 40.0

    def test_from_dict(self) -> None:
        emp = Employee(
            id=1,
            first_name="Max",
            last_name="Mustermann",
            seniority="Senior",
            role_ids=[1, 2],
            role_names=["Developer", "Architect"],
            hours_per_week=35.0,
        )
        assert emp.id == 1
        assert emp.first_name == "Max"
        assert emp.role_names == ["Developer", "Architect"]


class TestEmployeeCreateModel:
    """Tests for the EmployeeCreate Pydantic model."""

    def test_valid_employee(self) -> None:
        emp = EmployeeCreate(
            first_name="Max",
            last_name="Mustermann",
            seniority=SeniorityLevel.SENIOR,
            role_ids=[1],
            hours_per_week=40.0,
        )
        assert emp.first_name == "Max"
        assert emp.seniority == SeniorityLevel.SENIOR

    def test_first_name_required(self) -> None:
        with pytest.raises(ValidationError):
            EmployeeCreate(
                last_name="Mustermann",
                seniority=SeniorityLevel.SENIOR,
                role_ids=[1],
            )  # type: ignore[call-arg]

    def test_hours_per_week_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            EmployeeCreate(
                first_name="Max",
                last_name="Mustermann",
                seniority=SeniorityLevel.SENIOR,
                role_ids=[1],
                hours_per_week=-1.0,
            )

    def test_max_length_first_name(self) -> None:
        with pytest.raises(ValidationError):
            EmployeeCreate(
                first_name="x" * 256,
                last_name="Mustermann",
                seniority=SeniorityLevel.SENIOR,
                role_ids=[1],
            )

    def test_default_hours(self) -> None:
        emp = EmployeeCreate(
            first_name="Max",
            last_name="Mustermann",
            seniority=SeniorityLevel.ADVANCED,
            role_ids=[1],
        )
        assert emp.hours_per_week == 40.0


class TestEmployeeUpdateModel:
    """Tests for the EmployeeUpdate Pydantic model."""

    def test_valid_update(self) -> None:
        upd = EmployeeUpdate(
            first_name="Anna",
            last_name="Schmidt",
            seniority=SeniorityLevel.EXPERT,
            role_ids=[2],
            hours_per_week=32.0,
        )
        assert upd.first_name == "Anna"
        assert upd.hours_per_week == 32.0


class TestAbsenceModel:
    """Tests for the Absence Pydantic models."""

    def test_absence_defaults(self) -> None:
        absence = Absence()
        assert absence.id == 0
        assert absence.employee_id == 0
        assert absence.start_date is None
        assert absence.end_date is None

    def test_absence_create_valid(self) -> None:
        absence = AbsenceCreate(
            employee_id=1,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 14),
        )
        assert absence.employee_id == 1
        assert absence.start_date == date(2025, 6, 1)

    def test_absence_create_requires_dates(self) -> None:
        with pytest.raises(ValidationError):
            AbsenceCreate(employee_id=1)  # type: ignore[call-arg]


# ============================================================================
# Repository Tests
# ============================================================================


class TestEmployeeRepository:
    """Tests for the EmployeeRepository async operations."""

    async def _seed_role(self, session: AsyncSession) -> RoleEntity:
        """Create a role for relationship reference."""
        role = RoleEntity(name="Developer", description="Software Developer")
        session.add(role)
        await session.flush()
        return role

    @pytest.mark.asyncio
    async def test_create(self, async_session: AsyncSession) -> None:
        role = await self._seed_role(async_session)
        repo = EmployeeRepository()
        entity = EmployeeEntity(
            first_name="Max",
            last_name="Mustermann",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40.0,
        )
        entity.roles = [role]
        created = await repo.create(async_session, entity)
        assert created.id is not None
        assert created.first_name == "Max"

    @pytest.mark.asyncio
    async def test_find_all_paginated(self, async_session: AsyncSession) -> None:
        role = await self._seed_role(async_session)
        repo = EmployeeRepository()
        for i in range(3):
            emp = EmployeeEntity(
                first_name=f"Person{i}",
                last_name=f"Last{i}",
                seniority=SeniorityLevel.ADVANCED.value,
                hours_per_week=40.0,
            )
            emp.roles = [role]
            async_session.add(emp)
        await async_session.flush()

        results = await repo.find_all_paginated(async_session, limit=10)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_find_all_paginated_with_search(
        self, async_session: AsyncSession
    ) -> None:
        role = await self._seed_role(async_session)
        repo = EmployeeRepository()
        emp1 = EmployeeEntity(
            first_name="Anna",
            last_name="Schmidt",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40.0,
        )
        emp1.roles = [role]
        async_session.add(emp1)
        emp2 = EmployeeEntity(
            first_name="Max",
            last_name="Mustermann",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40.0,
        )
        emp2.roles = [role]
        async_session.add(emp2)
        await async_session.flush()

        results = await repo.find_all_paginated(async_session, search="anna")
        assert len(results) == 1
        assert results[0].first_name == "Anna"

    @pytest.mark.asyncio
    async def test_find_by_id(self, async_session: AsyncSession) -> None:
        role = await self._seed_role(async_session)
        repo = EmployeeRepository()
        entity = EmployeeEntity(
            first_name="Test",
            last_name="User",
            seniority=SeniorityLevel.EXPERT.value,
            hours_per_week=20.0,
        )
        entity.roles = [role]
        await repo.create(async_session, entity)

        found = await repo.find_by_id(async_session, entity.id)
        assert found is not None
        assert found.first_name == "Test"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, async_session: AsyncSession) -> None:
        repo = EmployeeRepository()
        result = await repo.find_by_id(async_session, 9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self, async_session: AsyncSession) -> None:
        role = await self._seed_role(async_session)
        repo = EmployeeRepository()
        entity = EmployeeEntity(
            first_name="Old",
            last_name="Name",
            seniority=SeniorityLevel.ADVANCED.value,
            hours_per_week=40.0,
        )
        entity.roles = [role]
        await repo.create(async_session, entity)

        entity.first_name = "New"
        entity.last_name = "Updated"
        updated = await repo.update(async_session, entity)
        assert updated.first_name == "New"
        assert updated.last_name == "Updated"

    @pytest.mark.asyncio
    async def test_delete_by_id(self, async_session: AsyncSession) -> None:
        role = await self._seed_role(async_session)
        repo = EmployeeRepository()
        entity = EmployeeEntity(
            first_name="ToDelete",
            last_name="User",
            seniority=SeniorityLevel.SENIOR.value,
            hours_per_week=40.0,
        )
        entity.roles = [role]
        async_session.add(entity)
        await async_session.flush()

        deleted = await repo.delete_by_id(async_session, entity.id)
        assert deleted is True

        found = await repo.find_by_id(async_session, entity.id)
        assert found is None


class TestAbsenceRepository:
    """Tests for the AbsenceRepository async operations."""

    async def _seed_employee(self, session: AsyncSession) -> EmployeeEntity:
        """Create a role and employee for FK reference."""
        role = RoleEntity(name="Tester", description="QA")
        session.add(role)
        await session.flush()

        employee = EmployeeEntity(
            first_name="Test",
            last_name="Employee",
            seniority=SeniorityLevel.ADVANCED.value,
            hours_per_week=40.0,
        )
        employee.roles = [role]
        session.add(employee)
        await session.flush()
        return employee

    @pytest.mark.asyncio
    async def test_create_absence(self, async_session: AsyncSession) -> None:
        employee = await self._seed_employee(async_session)
        repo = AbsenceRepository()
        entity = AbsenceEntity(
            employee_id=employee.id,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 14),
        )
        created = await repo.create(async_session, entity)
        assert created.id is not None
        assert created.employee_id == employee.id

    @pytest.mark.asyncio
    async def test_find_by_employee_id(self, async_session: AsyncSession) -> None:
        employee = await self._seed_employee(async_session)
        repo = AbsenceRepository()
        async_session.add(
            AbsenceEntity(
                employee_id=employee.id,
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 7),
            )
        )
        async_session.add(
            AbsenceEntity(
                employee_id=employee.id,
                start_date=date(2025, 7, 1),
                end_date=date(2025, 7, 5),
            )
        )
        await async_session.flush()

        results = await repo.find_by_employee_id(async_session, employee.id)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_find_by_employee_id_empty(self, async_session: AsyncSession) -> None:
        employee = await self._seed_employee(async_session)
        repo = AbsenceRepository()
        results = await repo.find_by_employee_id(async_session, employee.id)
        assert results == []

    @pytest.mark.asyncio
    async def test_find_active_by_employee_id(
        self, async_session: AsyncSession
    ) -> None:
        employee = await self._seed_employee(async_session)
        repo = AbsenceRepository()
        # Active absence (covers today-like date)
        async_session.add(
            AbsenceEntity(
                employee_id=employee.id,
                start_date=date(2025, 5, 1),
                end_date=date(2025, 5, 31),
            )
        )
        # Past absence
        async_session.add(
            AbsenceEntity(
                employee_id=employee.id,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 10),
            )
        )
        await async_session.flush()

        results = await repo.find_active_by_employee_id(
            async_session, employee.id, as_of_date=date(2025, 5, 15)
        )
        assert len(results) == 1
        assert results[0].start_date == date(2025, 5, 1)

    @pytest.mark.asyncio
    async def test_delete_absence(self, async_session: AsyncSession) -> None:
        employee = await self._seed_employee(async_session)
        repo = AbsenceRepository()
        entity = AbsenceEntity(
            employee_id=employee.id,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 5),
        )
        async_session.add(entity)
        await async_session.flush()

        deleted = await repo.delete_by_id(async_session, entity.id)
        assert deleted is True
