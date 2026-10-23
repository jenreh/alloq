"""Fixtures of the offer tests: SQLite with the workshop tables."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import alloq_commons.entities  # noqa: F401  (registers the projects table)
import alloq_offer.workshop.entities  # noqa: F401  (registers the workshop tables)
import pytest
from alloq_offer.entities import IndustryEntity, OfferEntity
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from appkit_commons.database.entities import Base


class Database:
    """File-based SQLite; sessions commit on exit like appkit's session manager."""

    def __init__(self, path: Path) -> None:
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        self._maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.session() as session:
            session.add(IndustryEntity(id=1, name="Handel"))
            session.add(
                OfferEntity(
                    id=1,
                    title="Plattform",
                    customer="Muster AG",
                    person_days=Decimal(10),
                    risk_buffer_days=Decimal(1),
                    production_cost=Decimal(1000),
                    recommended_price=Decimal(2000),
                    key_accounter="Anna",
                    industry_id=1,
                    state="Neu",
                )
            )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(tmp_path / "workshop.db")
    await database.create()
    yield database
    await database.dispose()
