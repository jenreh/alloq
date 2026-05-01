import logging

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from alloq_commons.entities import EmployeeEntity, RoleEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class EmployeeRepository(BaseRepository[EmployeeEntity, AsyncSession]):
    """Async repository for team member CRUD operations."""

    @property
    def model_class(self) -> type[EmployeeEntity]:
        return EmployeeEntity

    async def find_all_paginated(
        self,
        session: AsyncSession,
        limit: int = 200,
        offset: int = 0,
        search: str | None = None,
    ) -> list[EmployeeEntity]:
        """Find all employees with pagination and optional search filter."""
        statement = select(EmployeeEntity)

        if search:
            search_pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    EmployeeEntity.first_name.ilike(search_pattern),
                    EmployeeEntity.last_name.ilike(search_pattern),
                )
            )

        statement = (
            statement.offset(offset)
            .limit(limit)
            .order_by(EmployeeEntity.last_name, EmployeeEntity.first_name)
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def set_roles(
        self,
        session: AsyncSession,
        entity: EmployeeEntity,
        role_ids: list[int],
    ) -> None:
        """Set roles for an employee by role IDs."""
        result = await session.execute(
            select(RoleEntity).where(RoleEntity.id.in_(role_ids))
        )
        roles = list(result.scalars().all())
        entity.roles = roles


employee_repo = EmployeeRepository()
