"""Version-checked, atomic price-list persistence; caller owns the transaction."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities.price_list import PriceListEntity, PricePositionEntity
from alloq_commons.models.price_list import PriceList
from appkit_commons.database.base_repository import BaseRepository


class PriceListConflict(ValueError):
    """The document changed since the user's draft was loaded."""


class PriceListRepository(BaseRepository[PriceListEntity, AsyncSession]):
    @property
    def model_class(self) -> type[PriceListEntity]:
        return PriceListEntity

    async def list_all(self, session: AsyncSession) -> list[PriceList]:
        result = await session.scalars(
            select(PriceListEntity)
            .order_by(
                PriceListEntity.archived, PriceListEntity.name, PriceListEntity.id
            )
            .execution_options(populate_existing=True)
        )
        return [PriceList(**entity.to_dict()) for entity in result]

    async def load(self, session: AsyncSession, sheet_id: int) -> PriceList:
        result = await session.scalar(
            select(PriceListEntity)
            .where(PriceListEntity.id == sheet_id)
            .execution_options(populate_existing=True)
        )
        if result is None:
            raise PriceListConflict("Price list no longer exists")
        return PriceList(**result.to_dict())

    async def save_document(self, session: AsyncSession, sheet: PriceList) -> PriceList:
        document = PriceList.model_validate(sheet.model_dump())
        for row in document.positions:
            row.validate_identity()
        values = document.model_dump(exclude={"id", "version", "positions"})
        if document.id:
            changed = await session.scalar(
                update(PriceListEntity)
                .where(
                    PriceListEntity.id == document.id,
                    PriceListEntity.version == document.version,
                )
                .values(**values, version=document.version + 1)
                .returning(PriceListEntity.id)
            )
            if changed is None:
                raise PriceListConflict("Stale price list")
            entity = await session.scalar(
                select(PriceListEntity)
                .where(PriceListEntity.id == document.id)
                .execution_options(populate_existing=True)
            )
        else:
            entity = PriceListEntity(**values, version=1, positions=[])
            session.add(entity)
            await session.flush()
        if entity is None:
            raise PriceListConflict("Price list no longer exists")
        existing = {row.id: row for row in entity.positions}
        positions = []
        for index, row in enumerate(document.positions):
            position = existing.get(row.id)
            if position is None:
                position = PricePositionEntity(price_list_id=entity.id)
            for key, value in row.model_dump(exclude={"id", "key"}).items():
                setattr(position, key, value)
            position.sort_order = index
            positions.append(position)
        entity.positions = positions
        await session.flush()
        return PriceList(**entity.to_dict())


price_list_repo = PriceListRepository()
