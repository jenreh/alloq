import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_commons.entities import CapacityEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CapacityRepository(BaseRepository[CapacityEntity, AsyncSession]):
    """Async repository for actual project capacity assignments."""

    @property
    def model_class(self) -> type[CapacityEntity]:
        return CapacityEntity

    async def find_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[CapacityEntity]:
        """Find actual capacity assignments for a project."""
        statement = select(CapacityEntity).where(
            CapacityEntity.project_id == project_id
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def find_by_employee_id(
        self,
        session: AsyncSession,
        employee_id: int,
    ) -> list[CapacityEntity]:
        """Find all capacity assignments for an employee."""
        statement = select(CapacityEntity).where(
            CapacityEntity.employee_id == employee_id
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def find_by_project_and_employee(
        self,
        session: AsyncSession,
        project_id: int,
        employee_id: int,
    ) -> list[CapacityEntity]:
        """Find all role capacity slots for an employee on a project."""
        statement = select(CapacityEntity).where(
            CapacityEntity.project_id == project_id,
            CapacityEntity.employee_id == employee_id,
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def delete_by_project_and_employee(
        self,
        session: AsyncSession,
        project_id: int,
        employee_id: int,
    ) -> bool:
        """Delete all capacity entries for a project-employee pair."""
        entities = await self.find_by_project_and_employee(
            session, project_id, employee_id
        )
        if not entities:
            return False
        for entity in entities:
            await session.delete(entity)
        await session.flush()
        return True


capacity_repo = CapacityRepository()
