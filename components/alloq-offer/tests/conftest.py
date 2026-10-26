"""Fixtures of the offer tests: SQLite with the workshop tables."""

import importlib.util
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from types import ModuleType

import alloq_commons.entities  # noqa: F401  (registers the projects table)
import alloq_offer.workshop.entities  # noqa: F401  (registers the workshop tables)
import alloq_offer.workshop.template_entities  # noqa: F401  (registers the template tables)
import pytest
from alloq_offer.entities import IndustryEntity, OfferEntity
from alloq_offer.workshop.ai.agents import PromptLoader
from alloq_offer.workshop.export.template_package import TemplatePackage
from alloq_offer.workshop.services import templates
from alloq_offer.workshop.services.prompts import Prompt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from appkit_commons.database.entities import Base

SEED_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "2026_10_31_offer_templates.py"
)


@cache
def template_seed() -> ModuleType:
    """The migration that seeds templates and prompts; tests use the same data."""
    spec = importlib.util.spec_from_file_location("template_seed", SEED_MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError(SEED_MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def quo_v1() -> TemplatePackage:
    """Version 1 of the seeded template, without a database."""
    seed = template_seed()
    return TemplatePackage(
        key=seed.TEMPLATE_KEY,
        version="1",
        layout_bytes=seed.LAYOUT_PATH.read_bytes(),
        **seed.payload(),
    )


class Database:
    """File-based SQLite; sessions commit on exit like appkit's session manager."""

    def __init__(self, path: Path) -> None:
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        self._maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create(self) -> None:
        seed = template_seed()
        layout = seed.LAYOUT_PATH.read_bytes()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(seed.seed, layout, datetime.now(UTC))
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
def prompts() -> PromptLoader:
    """Version 1 of the seeded prompts, without a database."""

    async def load(name: str) -> Prompt:
        return Prompt(name, 1, template_seed().PROMPTS[name])

    return load


@pytest.fixture(autouse=True)
def _fresh_template_cache() -> Iterator[None]:
    templates.clear_cache()
    yield
    templates.clear_cache()


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(tmp_path / "workshop.db")
    await database.create()
    yield database
    await database.dispose()
