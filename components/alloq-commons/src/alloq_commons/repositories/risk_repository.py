import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_commons.entities import RiskEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RiskRepository(BaseRepository[RiskEntity, AsyncSession]):
    """Async repository for project risks."""

    @property
    def model_class(self) -> type[RiskEntity]:
        return RiskEntity

    async def find_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[RiskEntity]:
        """Find risks for a project."""
        statement = select(RiskEntity).where(RiskEntity.project_id == project_id)
        result = await session.execute(statement)
        return list(result.scalars().all())


risk_repo = RiskRepository()
