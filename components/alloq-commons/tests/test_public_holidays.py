"""Tests for public holiday management."""

from datetime import date

import pytest
from alloq_commons.entities.public_holiday import PublicHolidayEntity
from alloq_commons.models.public_holiday import PublicHoliday, PublicHolidayCreate
from alloq_commons.repositories.public_holiday_repository import PublicHolidayRepository
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Entity Tests
# ============================================================================


class TestPublicHolidayEntity:
    """Tests for the PublicHolidayEntity database model."""

    def test_create_fixed_holiday(self) -> None:
        entity = PublicHolidayEntity(
            name="Neujahr",
            date=date(2026, 1, 1),
            is_recurring=True,
            state_code="NRW",
        )
        assert entity.name == "Neujahr"
        assert entity.date == date(2026, 1, 1)
        assert entity.is_recurring is True
        assert entity.state_code == "NRW"

    def test_create_moveable_holiday(self) -> None:
        entity = PublicHolidayEntity(
            name="Ostermontag",
            date=date(2026, 4, 6),
            is_recurring=False,
            state_code="NRW",
        )
        assert entity.is_recurring is False

    def test_to_dict(self) -> None:
        entity = PublicHolidayEntity(
            name="Fronleichnam",
            date=date(2026, 7, 4),
            is_recurring=False,
            state_code="NRW",
        )
        entity.id = 1
        entity.created = None
        entity.updated = None
        result = entity.to_dict()
        assert result["id"] == 1
        assert result["name"] == "Fronleichnam"
        assert result["date"] == date(2026, 7, 4)
        assert result["is_recurring"] is False
        assert result["state_code"] == "NRW"

    def test_tablename(self) -> None:
        assert PublicHolidayEntity.__tablename__ == "public_holidays"


# ============================================================================
# Model Tests
# ============================================================================


class TestPublicHolidayModel:
    """Tests for the PublicHoliday Pydantic model."""

    def test_defaults(self) -> None:
        holiday = PublicHoliday()
        assert holiday.id == 0
        assert holiday.name == ""
        assert holiday.is_recurring is False
        assert holiday.state_code == "NRW"
        assert holiday.created is None
        assert holiday.updated is None

    def test_from_dict(self) -> None:
        d = date(2026, 1, 1)
        holiday = PublicHoliday(id=1, name="Neujahr", date=d, is_recurring=True)
        assert holiday.id == 1
        assert holiday.name == "Neujahr"
        assert holiday.date == d
        assert holiday.is_recurring is True


class TestPublicHolidayCreateModel:
    """Tests for the PublicHolidayCreate Pydantic model."""

    def test_valid_create(self) -> None:
        h = PublicHolidayCreate(
            name="Neujahr", date=date(2026, 1, 1), is_recurring=True
        )
        assert h.name == "Neujahr"
        assert h.date == date(2026, 1, 1)
        assert h.is_recurring is True
        assert h.state_code == "NRW"

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            PublicHolidayCreate(date=date(2026, 1, 1))  # type: ignore[call-arg]

    def test_date_required(self) -> None:
        with pytest.raises(ValidationError):
            PublicHolidayCreate(name="Neujahr")  # type: ignore[call-arg]

    def test_max_length_name(self) -> None:
        with pytest.raises(ValidationError):
            PublicHolidayCreate(name="x" * 256, date=date(2026, 1, 1))

    def test_default_state_code(self) -> None:
        h = PublicHolidayCreate(name="Test", date=date(2026, 6, 1))
        assert h.state_code == "NRW"


# ============================================================================
# Repository Tests
# ============================================================================


class TestPublicHolidayRepository:
    """Tests for the PublicHolidayRepository async operations."""

    @pytest.fixture
    def repo(self) -> PublicHolidayRepository:
        return PublicHolidayRepository()

    @pytest.mark.asyncio
    async def test_find_all_paginated(self, async_session: AsyncSession) -> None:
        repo = PublicHolidayRepository()
        async_session.add(
            PublicHolidayEntity(
                name="Neujahr", date=date(2026, 1, 1), is_recurring=True
            )
        )
        async_session.add(
            PublicHolidayEntity(
                name="Ostermontag", date=date(2026, 4, 6), is_recurring=False
            )
        )
        await async_session.flush()

        results = await repo.find_all_paginated(async_session)
        assert len(results) == 2
        assert results[0].date == date(2026, 1, 1)
        assert results[1].date == date(2026, 4, 6)

    @pytest.mark.asyncio
    async def test_find_by_year(self, async_session: AsyncSession) -> None:
        repo = PublicHolidayRepository()
        async_session.add(
            PublicHolidayEntity(name="H2026", date=date(2026, 3, 1), is_recurring=False)
        )
        async_session.add(
            PublicHolidayEntity(name="H2027", date=date(2027, 3, 1), is_recurring=False)
        )
        await async_session.flush()

        results_2026 = await repo.find_by_year(async_session, 2026)
        assert len(results_2026) == 1
        assert results_2026[0].name == "H2026"

        results_2027 = await repo.find_by_year(async_session, 2027)
        assert len(results_2027) == 1
        assert results_2027[0].name == "H2027"

    @pytest.mark.asyncio
    async def test_find_by_year_empty(self, async_session: AsyncSession) -> None:
        repo = PublicHolidayRepository()
        results = await repo.find_by_year(async_session, 2025)
        assert results == []

    @pytest.mark.asyncio
    async def test_find_by_date_range(self, async_session: AsyncSession) -> None:
        repo = PublicHolidayRepository()
        async_session.add(
            PublicHolidayEntity(name="Jan", date=date(2026, 1, 1), is_recurring=True)
        )
        async_session.add(
            PublicHolidayEntity(name="Apr", date=date(2026, 4, 6), is_recurring=False)
        )
        async_session.add(
            PublicHolidayEntity(name="Dec", date=date(2026, 12, 25), is_recurring=True)
        )
        await async_session.flush()

        results = await repo.find_by_date_range(
            async_session, date(2026, 1, 1), date(2026, 6, 30)
        )
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"Jan", "Apr"}

    @pytest.mark.asyncio
    async def test_create_and_find_by_id(self, async_session: AsyncSession) -> None:
        repo = PublicHolidayRepository()
        entity = PublicHolidayEntity(
            name="Christi Himmelfahrt",
            date=date(2026, 5, 14),
            is_recurring=False,
            state_code="NRW",
        )
        await repo.create(async_session, entity)
        assert entity.id is not None

        found = await repo.find_by_id(async_session, entity.id)
        assert found is not None
        assert found.name == "Christi Himmelfahrt"
        assert found.date == date(2026, 5, 14)

    @pytest.mark.asyncio
    async def test_delete_by_id(self, async_session: AsyncSession) -> None:
        repo = PublicHolidayRepository()
        entity = PublicHolidayEntity(
            name="Pfingstmontag", date=date(2026, 6, 25), is_recurring=False
        )
        await repo.create(async_session, entity)
        holiday_id = entity.id

        deleted = await repo.delete_by_id(async_session, holiday_id)
        assert deleted is True

        found = await repo.find_by_id(async_session, holiday_id)
        assert found is None
