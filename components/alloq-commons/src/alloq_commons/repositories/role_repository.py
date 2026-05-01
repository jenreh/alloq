import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_commons.entities import RoleEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RoleRepository(BaseRepository[RoleEntity, AsyncSession]):
    """Async repository for organizational role CRUD operations."""

    @property
    def model_class(self) -> type[RoleEntity]:
        return RoleEntity

    async def find_all_paginated(
        self,
        session: AsyncSession,
        limit: int = 200,
        offset: int = 0,
    ) -> list[RoleEntity]:
        """Find all roles with pagination, ordered by name."""
        statement = (
            select(RoleEntity).offset(offset).limit(limit).order_by(RoleEntity.name)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


role_repo = RoleRepository()
