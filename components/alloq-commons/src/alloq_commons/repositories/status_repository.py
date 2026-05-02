import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_commons.entities import ProjectStatusEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ProjectStatusRepository(BaseRepository[ProjectStatusEntity, AsyncSession]):
    """Async repository for project status history."""

    @property
    def model_class(self) -> type[ProjectStatusEntity]:
        return ProjectStatusEntity

    async def find_by_project_id(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[ProjectStatusEntity]:
        """Find status history for a project, newest first."""
        statement = (
            select(ProjectStatusEntity)
            .where(ProjectStatusEntity.project_id == project_id)
            .order_by(ProjectStatusEntity.status_date.desc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


status_repo = ProjectStatusRepository()
