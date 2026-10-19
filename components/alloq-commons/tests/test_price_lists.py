"""Price list arithmetic, templates and transactional persistence."""

from decimal import Decimal

import pytest
from alloq_commons.models.price_list import PriceList, PricePosition
from alloq_commons.repositories.price_list_repository import (
    PriceListConflict,
    price_list_repo,
)
from alloq_commons.services.price_list_pricing import calculate_position, parse_money
from alloq_commons.services.price_list_templates import price_list_template
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.parametrize(
    ("basis", "cost", "daily", "minimum"),
    [
        ("day", "710.00", "710.00", "1015"),
        ("hour", "83.91", "671.28", "959"),
        ("hour", "88.52", "708.16", "1012"),
        ("day", "1000", "1000", "1429"),
    ],
)
def test_calculation(basis: str, cost: str, daily: str, minimum: str) -> None:
    sheet = PriceList(name="Test", cost_basis=basis)
    row = calculate_position(
        PricePosition(label="Engineer", cost=cost, sales_price="1450"), sheet
    )
    assert row.daily_cost == Decimal(daily)
    assert row.minimum_daily == Decimal(minimum)
    assert row.minimum_hourly == Decimal(minimum) / Decimal("8")
    assert row.hourly_sales == Decimal("181.25")


def test_missing_sales_and_legacy_target_margin() -> None:
    position = PricePosition(la="Junior", cost="710")
    sheet = PriceList(name="Test")
    assert calculate_position(position, sheet).daily_sales is None
    sheet.target_margin = Decimal("35")
    assert calculate_position(position, sheet).daily_sales == Decimal("1093")
    position.sales_price = Decimal("900")
    result = calculate_position(position, sheet)
    assert result.daily_sales == Decimal("900")
    assert result.below_minimum
    assert calculate_position(PricePosition(la="Extern"), sheet).minimum_daily is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.280,00 €", "1280.00"),
        ("83,91", "83.91"),
        ("83.91", "83.91"),
        ("", None),
        (None, None),
        ("1.000", "1000"),
        ("0,01", "0.01"),
    ],
)
def test_money_parsing(raw: str | None, expected: str | None) -> None:
    assert parse_money(raw) == (Decimal(expected) if expected else None)


@pytest.mark.parametrize(
    "raw", ["NaN", "Infinity", "-5", "abc", "1,2,3", "100001", "0", "1.2345"]
)
def test_invalid_money(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_money(raw)


@pytest.mark.parametrize(
    "data", [{"hours_per_day": 0}, {"minimum_margin": 100}, {"name": " "}]
)
def test_invalid_settings(data: dict) -> None:
    with pytest.raises(ValidationError):
        PriceList(**{"name": "Test", **data})


def test_position_identity_and_optional_role() -> None:
    with pytest.raises(ValidationError):
        PricePosition().validate_identity()
    PricePosition(la="Junior").validate_identity()
    assert PricePosition(label="Mischsatz").role_id is None


@pytest.mark.parametrize(
    ("template", "count", "basis"),
    [("germany", 9, "hour"), ("2025", 7, "day"), ("2026", 4, "hour")],
)
def test_templates(template: str, count: int, basis: str) -> None:
    sheet = price_list_template(template)
    assert len(sheet.positions) == count
    assert sheet.cost_basis == basis
    assert sheet.target_margin is None
    if template == "germany":
        assert sheet.as_of is None
        assert all(p.sales_price is None for p in sheet.positions)
    if template == "2026":
        assert sheet.positions[0].la == "Junior"
        assert sheet.positions[0].label == ""
        assert str(sheet.as_of) == "2026-01-01"


async def test_repository_save_order_clone_archive_and_conflict(
    async_session: AsyncSession,
) -> None:
    sheet = price_list_template("2025")
    saved = await price_list_repo.save_document(async_session, sheet)
    assert saved.id > 0
    assert saved.version == 1
    stale = saved.model_copy(deep=True)
    saved.positions.reverse()
    saved.positions[0].sales_price = Decimal("1600.01")
    saved = await price_list_repo.save_document(async_session, saved)
    assert saved.version == 2
    with pytest.raises(PriceListConflict):
        await price_list_repo.save_document(async_session, stale)
    loaded = await price_list_repo.load(async_session, saved.id)
    assert loaded.positions[0].label == "Extern?"
    assert loaded.positions[0].sales_price == Decimal("1600.01")
    clone = loaded.duplicate()
    clone.name = "2027"
    clone = await price_list_repo.save_document(async_session, clone)
    assert clone.id != loaded.id
    assert all(
        a.id != b.id for a, b in zip(clone.positions, loaded.positions, strict=True)
    )
    loaded.archived = True
    await price_list_repo.save_document(async_session, loaded)
    assert len(await price_list_repo.list_all(async_session)) == 2


async def test_invalid_position_does_not_write(async_session: AsyncSession) -> None:
    sheet = PriceList(name="Bad", positions=[PricePosition()])
    with pytest.raises(ValidationError):
        await price_list_repo.save_document(async_session, sheet)
    assert await price_list_repo.list_all(async_session) == []
