import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities.public_holiday import PublicHolidayEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PublicHolidayRepository(BaseRepository[PublicHolidayEntity, AsyncSession]):
    """Async repository for public holiday CRUD operations."""

    @property
    def model_class(self) -> type[PublicHolidayEntity]:
        return PublicHolidayEntity

    async def find_all_paginated(
        self,
        session: AsyncSession,
        limit: int = 500,
        offset: int = 0,
    ) -> list[PublicHolidayEntity]:
        """Find all holidays ordered by date."""
        statement = (
            select(PublicHolidayEntity)
            .offset(offset)
            .limit(limit)
            .order_by(PublicHolidayEntity.date.asc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def find_by_year(
        self,
        session: AsyncSession,
        year: int,
    ) -> list[PublicHolidayEntity]:
        """Find all holidays in a given year, ordered by date."""
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        statement = (
            select(PublicHolidayEntity)
            .where(
                PublicHolidayEntity.date >= start,
                PublicHolidayEntity.date <= end,
            )
            .order_by(PublicHolidayEntity.date.asc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def find_by_date_range(
        self,
        session: AsyncSession,
        start: date,
        end: date,
    ) -> list[PublicHolidayEntity]:
        """Find holidays within a date range (inclusive)."""
        statement = (
            select(PublicHolidayEntity)
            .where(
                PublicHolidayEntity.date >= start,
                PublicHolidayEntity.date <= end,
            )
            .order_by(PublicHolidayEntity.date.asc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


public_holiday_repo = PublicHolidayRepository()
