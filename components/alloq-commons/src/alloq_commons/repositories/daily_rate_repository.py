import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import (
    DailyRateEntity,
    DailyRateSettingsEntity,
    RoleEntity,
)
from alloq_commons.entities.daily_rate import (
    DEFAULT_CONTRIBUTION_MARGIN_PERCENT,
    DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT,
)
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DailyRateRepository(BaseRepository[DailyRateEntity, AsyncSession]):
    """Async repository for daily rates and their shared settings."""

    @property
    def model_class(self) -> type[DailyRateEntity]:
        return DailyRateEntity

    async def find_all_by_role_name(
        self, session: AsyncSession
    ) -> list[DailyRateEntity]:
        """Find all daily rates, ordered by role name."""
        statement = (
            select(DailyRateEntity)
            .join(RoleEntity, DailyRateEntity.role_id == RoleEntity.id)
            .order_by(RoleEntity.name)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def find_by_role_id(
        self, session: AsyncSession, role_id: int
    ) -> DailyRateEntity | None:
        """Find the daily rate of a role."""
        result = await session.execute(
            select(DailyRateEntity).where(DailyRateEntity.role_id == role_id)
        )
        return result.scalars().first()

    async def get_margins(self, session: AsyncSession) -> tuple[int, int]:
        """Minimal and regular margin in percent; defaults when none is stored."""
        settings = await self._settings(session)
        if settings is None:
            return (
                DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT,
                DEFAULT_CONTRIBUTION_MARGIN_PERCENT,
            )
        return (
            settings.min_contribution_margin_percent,
            settings.contribution_margin_percent,
        )

    async def save_margins(
        self, session: AsyncSession, minimum: int, margin: int
    ) -> None:
        """Store both margins, creating the settings row if needed."""
        settings = await self._settings(session)
        if settings is None:
            settings = DailyRateSettingsEntity()
            session.add(settings)
        settings.min_contribution_margin_percent = minimum
        settings.contribution_margin_percent = margin
        await session.flush()

    async def _settings(self, session: AsyncSession) -> DailyRateSettingsEntity | None:
        result = await session.execute(
            select(DailyRateSettingsEntity).order_by(DailyRateSettingsEntity.id)
        )
        return result.scalars().first()


daily_rate_repo = DailyRateRepository()
