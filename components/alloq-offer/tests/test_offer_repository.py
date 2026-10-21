"""Tests for the offer repository against in-memory SQLite."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alloq_offer.entities import IndustryEntity, OfferEntity
from alloq_offer.repository import industry_repo, offer_repo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from appkit_commons.database.entities import Base


def _entity(title: str, updated: datetime, industry_id: int = 1) -> OfferEntity:
    return OfferEntity(
        title=title,
        customer="Kunde",
        person_days=Decimal(10),
        risk_buffer_days=Decimal(1),
        production_cost=Decimal(1000),
        recommended_price=Decimal(1500),
        key_accounter="KA",
        industry_id=industry_id,
        state="Neu",
        updated=updated,
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(IndustryEntity(id=1, name="Öffentlicher Sektor"))
        await db.commit()
        yield db
    await engine.dispose()


async def test_find_all_ordered_newest_first(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    session.add_all(
        [
            _entity("alt", now - timedelta(days=2)),
            _entity("neu", now),
            _entity("mittel", now - timedelta(days=1)),
        ]
    )
    await session.commit()

    result = await offer_repo.find_all_ordered(session)

    assert [o.title for o in result] == ["neu", "mittel", "alt"]


async def test_industries_are_ordered_by_name(session: AsyncSession) -> None:
    session.add_all([IndustryEntity(name="Handel"), IndustryEntity(name="Pharma")])
    await session.commit()

    result = await industry_repo.find_all_ordered(session)

    assert [i.name for i in result] == ["Handel", "Öffentlicher Sektor", "Pharma"]


async def test_count_offers_includes_archived(session: AsyncSession) -> None:
    session.add(IndustryEntity(id=2, name="Handel"))
    archived = _entity("alt", datetime.now(UTC))
    archived.archived = True
    session.add_all([archived, _entity("neu", datetime.now(UTC))])
    await session.commit()

    assert await industry_repo.count_offers(session, 1) == 2
    assert await industry_repo.count_offers(session, 2) == 0
