import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_commons.entities import RequiredCapacityEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RequiredCapacityRepository(BaseRepository[RequiredCapacityEntity, AsyncSession]):
    """Async repository for required project staffing."""

    @property
    def model_class(self) -> type[RequiredCapacityEntity]:
        return RequiredCapacityEntity

    async def find_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[RequiredCapacityEntity]:
        """Find required capacities for a project."""
        statement = select(RequiredCapacityEntity).where(
            RequiredCapacityEntity.project_id == project_id
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())


required_capacity_repo = RequiredCapacityRepository()
