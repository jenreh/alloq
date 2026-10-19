"""Pure fixed-point pricing and strict German currency parsing."""

import re
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation

from alloq_commons.models.price_list import PricedPosition, PriceList, PricePosition

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
MAX_PRICE = Decimal("100000")


def parse_money(value: str | float | Decimal | None) -> Decimal | None:
    """Parse a currency value without discarding signs or invalid characters."""
    raw = str(value if value is not None else "").strip()
    raw = raw.removesuffix("€").strip().replace("\u00a0", "")
    if not raw:
        return None
    if "," in raw:
        if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d{1,2}", raw):
            raise ValueError("Invalid currency")
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    elif not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        raise ValueError("Invalid currency")
    try:
        amount = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError("Invalid currency") from error
    if not amount.is_finite() or not 0 < amount <= MAX_PRICE:
        raise ValueError("Currency outside bounds")
    return amount


def margin_price(cost: Decimal, margin: Decimal) -> Decimal:
    return (cost / (1 - margin / HUNDRED)).to_integral_value(rounding=ROUND_CEILING)


def calculate_position(row: PricePosition, sheet: PriceList) -> PricedPosition:
    hours = sheet.hours_per_day
    daily = row.cost
    if daily is not None and sheet.cost_basis == "hour":
        daily *= hours
    minimum = margin_price(daily, sheet.minimum_margin) if daily is not None else None
    sales = row.sales_price
    if sales is None and daily is not None and sheet.target_margin is not None:
        sales = margin_price(daily, sheet.target_margin)
    return PricedPosition(
        hourly_cost=daily / hours if daily is not None else None,
        daily_cost=daily,
        minimum_daily=minimum,
        minimum_hourly=minimum / hours if minimum is not None else None,
        daily_sales=sales,
        hourly_sales=sales / hours if sales is not None else None,
        below_minimum=sales is not None and minimum is not None and sales < minimum,
    )


def format_money(value: Decimal | None) -> str:
    if value is None:
        return ""
    rounded = value.quantize(CENT, rounding=ROUND_HALF_UP)
    return (
        f"{rounded:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " €"
    )
