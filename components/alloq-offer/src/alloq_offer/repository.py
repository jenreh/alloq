"""Async repositories for offers and industries."""

import unicodedata
from collections.abc import Iterable

from alloq_commons.entities import ProjectEntity
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import IndustryEntity, OfferEntity
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

    async def project_codes(
        self, session: AsyncSession, project_ids: Iterable[int]
    ) -> dict[int, str]:
        """Project code per id for the given project ids."""
        ids = set(project_ids)
        if not ids:
            return {}
        result = await session.execute(
            select(ProjectEntity.id, ProjectEntity.code).where(
                ProjectEntity.id.in_(ids)
            )
        )
        return dict(result.tuples().all())


offer_repo = OfferRepository()


def _sort_key(name: str) -> str:
    """'Öffentlich' sorts next to 'Offen', not after 'Z' as in the C collation."""
    return unicodedata.normalize("NFKD", name).casefold()


class IndustryRepository(BaseRepository[IndustryEntity, AsyncSession]):
    """Async repository for the customer industries."""

    @property
    def model_class(self) -> type[IndustryEntity]:
        return IndustryEntity

    async def find_all_ordered(self, session: AsyncSession) -> list[IndustryEntity]:
        """All industries ordered by name; umlauts sort like their base letter."""
        result = await session.execute(select(IndustryEntity))
        return sorted(result.scalars().all(), key=lambda i: _sort_key(i.name))

    async def count_offers(self, session: AsyncSession, industry_id: int) -> int:
        """Number of offers, archived ones included, that use the industry."""
        result = await session.execute(
            select(func.count())
            .select_from(OfferEntity)
            .where(OfferEntity.industry_id == industry_id)
        )
        return result.scalar_one()


industry_repo = IndustryRepository()
