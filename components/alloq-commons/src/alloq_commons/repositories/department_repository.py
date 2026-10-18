from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import DepartmentEntity
from appkit_commons.database.base_repository import BaseRepository


class DepartmentRepository(BaseRepository[DepartmentEntity, AsyncSession]):
    """Async repository for department CRUD operations."""

    @property
    def model_class(self) -> type[DepartmentEntity]:
        return DepartmentEntity

    async def find_all_paginated(
        self,
        session: AsyncSession,
        limit: int = 200,
        offset: int = 0,
    ) -> list[DepartmentEntity]:
        """Find all departments with pagination, ordered by name."""
        statement = (
            select(DepartmentEntity)
            .offset(offset)
            .limit(limit)
            .order_by(DepartmentEntity.name)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


department_repo = DepartmentRepository()
