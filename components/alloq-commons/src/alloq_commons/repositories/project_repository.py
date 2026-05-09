import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import ProjectEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ProjectRepository(BaseRepository[ProjectEntity, AsyncSession]):
    """Async repository for project CRUD operations."""

    @property
    def model_class(self) -> type[ProjectEntity]:
        return ProjectEntity

    async def find_all_paginated(
        self,
        session: AsyncSession,
        limit: int = 200,
        offset: int = 0,
        search: str | None = None,
    ) -> list[ProjectEntity]:
        """Find all projects with relationships and optional search filter."""
        statement = select(ProjectEntity)

        if search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    ProjectEntity.code.ilike(search_pattern),
                    ProjectEntity.customer.ilike(search_pattern),
                    ProjectEntity.name_de.ilike(search_pattern),
                )
            )

        statement = (
            statement.offset(offset)
            .limit(limit)
            .order_by(ProjectEntity.start_date.desc(), ProjectEntity.code)
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def find_by_code(
        self,
        session: AsyncSession,
        code: str,
    ) -> ProjectEntity | None:
        """Find a project by its unique code."""
        statement = select(ProjectEntity).where(ProjectEntity.code == code)
        result = await session.execute(statement)
        return result.scalars().unique().one_or_none()

    async def find_all_with_stats(
        self,
        session: AsyncSession,
        limit: int = 200,
        offset: int = 0,
        search: str | None = None,
    ) -> list[ProjectEntity]:
        """Find all projects with relationship-derived stats loaded."""
        return await self.find_all_paginated(session, limit, offset, search)


project_repo = ProjectRepository()
