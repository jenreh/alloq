"""Tests for the offer repository against in-memory SQLite."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alloq_offer.entities import OfferEntity
from alloq_offer.repository import offer_repo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from appkit_commons.database.entities import Base


def _entity(title: str, updated: datetime) -> OfferEntity:
    return OfferEntity(
        title=title,
        customer="Kunde",
        person_days=Decimal(10),
        risk_buffer_days=Decimal(1),
        production_cost=Decimal(1000),
        recommended_price=Decimal(1500),
        key_accounter="KA",
        ciu="CP",
        state="Neu",
        updated=updated,
    )


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
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
