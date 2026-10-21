import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from alloq_commons.entities import ProjectEntity
from alloq_commons.repositories.search import LIKE_ESCAPE_CHAR, escape_like
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
            search_pattern = f"%{escape_like(search)}%"
            statement = statement.where(
                or_(
                    ProjectEntity.code.ilike(search_pattern, escape=LIKE_ESCAPE_CHAR),
                    ProjectEntity.customer.ilike(
                        search_pattern, escape=LIKE_ESCAPE_CHAR
                    ),
                    ProjectEntity.name_de.ilike(
                        search_pattern, escape=LIKE_ESCAPE_CHAR
                    ),
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

    async def find_all_for_planning(
        self,
        session: AsyncSession,
    ) -> list[ProjectEntity]:
        """All projects without allocation history, statuses, risks or capacities.

        The default selectin load pulls every allocation row ever stored. The
        planning page builds its team initials from
        ``capacity_allocation_repo.find_staffed_employees`` instead.
        """
        statement = select(ProjectEntity).options(
            noload(ProjectEntity.capacity_allocations),
            noload(ProjectEntity.capacities),
            noload(ProjectEntity.statuses),
            noload(ProjectEntity.risks),
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


project_repo = ProjectRepository()
