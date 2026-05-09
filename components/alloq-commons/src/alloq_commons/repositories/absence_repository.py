import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import AbsenceEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class AbsenceRepository(BaseRepository[AbsenceEntity, AsyncSession]):
    """Async repository for absence period CRUD operations."""

    @property
    def model_class(self) -> type[AbsenceEntity]:
        return AbsenceEntity

    async def find_by_employee_id(
        self,
        session: AsyncSession,
        employee_id: int,
    ) -> list[AbsenceEntity]:
        """Find all absences for a specific employee."""
        statement = (
            select(AbsenceEntity)
            .where(AbsenceEntity.employee_id == employee_id)
            .order_by(AbsenceEntity.start_date.asc())
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def find_active_by_employee_id(
        self,
        session: AsyncSession,
        employee_id: int,
        as_of_date: date | None = None,
    ) -> list[AbsenceEntity]:
        """Find active absences covering the given date."""
        if as_of_date is None:
            as_of_date = datetime.now(tz=UTC).date()

        statement = (
            select(AbsenceEntity)
            .where(
                AbsenceEntity.employee_id == employee_id,
                AbsenceEntity.start_date <= as_of_date,
                AbsenceEntity.end_date >= as_of_date,
            )
            .order_by(AbsenceEntity.start_date)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


absence_repo = AbsenceRepository()
