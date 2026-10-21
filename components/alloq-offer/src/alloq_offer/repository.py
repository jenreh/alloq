"""Async repository for offers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import OfferEntity
from appkit_commons.database.base_repository import BaseRepository


class OfferRepository(BaseRepository[OfferEntity, AsyncSession]):
    """Async repository for offer reads and writes (offers are never deleted)."""

    @property
    def model_class(self) -> type[OfferEntity]:
        return OfferEntity

    async def find_all_ordered(self, session: AsyncSession) -> list[OfferEntity]:
        """All offers, most recently updated first."""
        statement = select(OfferEntity).order_by(
            OfferEntity.updated.desc(), OfferEntity.id.desc()
        )
        result = await session.execute(statement)
        return list(result.scalars().all())


offer_repo = OfferRepository()
