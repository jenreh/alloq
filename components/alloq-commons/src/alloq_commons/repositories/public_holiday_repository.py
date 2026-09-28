import logging
from datetime import date

from sqlalchemy import and_, or_, select
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
        """Find holidays within a date range (inclusive).

        Recurring holidays stored for another year are projected onto every
        year of the range (same month and day). Projected rows are transient
        copies that are never added to the session.
        """
        in_range = and_(
            PublicHolidayEntity.date >= start,
            PublicHolidayEntity.date <= end,
        )
        statement = (
            select(PublicHolidayEntity)
            .where(or_(in_range, PublicHolidayEntity.is_recurring.is_(True)))
            .order_by(PublicHolidayEntity.date.asc())
        )
        result = await session.execute(statement)
        rows = list(result.scalars().all())
        holidays = [row for row in rows if start <= row.date <= end]
        taken = {(row.date, row.state_code) for row in holidays}
        for row in rows:
            if not row.is_recurring:
                continue
            for projected in _project_recurring(row.date, start, end):
                if (projected, row.state_code) in taken:
                    continue
                taken.add((projected, row.state_code))
                holidays.append(
                    PublicHolidayEntity(
                        name=row.name,
                        date=projected,
                        is_recurring=True,
                        state_code=row.state_code,
                    )
                )
        holidays.sort(key=lambda holiday: holiday.date)
        return holidays


def _project_recurring(stored: date, start: date, end: date) -> list[date]:
    """Dates in [start, end] sharing *stored*'s month and day."""
    projected = []
    for year in range(start.year, end.year + 1):
        try:
            candidate = stored.replace(year=year)
        except ValueError:  # 29 February in a non-leap year
            continue
        if start <= candidate <= end:
            projected.append(candidate)
    return projected


public_holiday_repo = PublicHolidayRepository()
