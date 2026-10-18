"""Price calculation of daily rates.

A contribution margin is a share of the selling price: with 30 % margin the
production cost is the other 70 %, so price = cost / (1 - margin). Prices are
rounded up to the next 10 EUR. The recommended sales price always uses the
minimal margin; the list price uses the regular margin unless a manual list
price replaces it.
"""

from alloq_commons.models import DailyRate

ROUNDING_STEP = 10


def round_up_to_ten(value: int) -> int:
    """Round a whole euro amount up to the next multiple of 10."""
    return -(-value // ROUNDING_STEP) * ROUNDING_STEP


def price_for_margin(production_cost: int, margin_percent: int) -> int:
    """Selling price that yields the margin, rounded up to the next 10 EUR."""
    cost_share = max(100 - margin_percent, 1)
    # Integer ceiling of cost * 100 / cost_share in steps of 10, without floats.
    steps = -(-production_cost * 100 // (cost_share * ROUNDING_STEP))
    return steps * ROUNDING_STEP


def _margin(cost: int | None, price: int | None) -> int | None:
    if cost is None or price is None:
        return None
    return price - cost


def _share(cost: int | None, price: int | None) -> int | None:
    margin = _margin(cost, price)
    if margin is None or not price:
        return None
    return round(margin * 100 / price)


def price_rate(rate: DailyRate, min_margin: int, margin: int) -> DailyRate:
    """Copy of the rate with calculated and effective prices filled in."""
    cost = rate.production_cost
    recommended = price_for_margin(cost, min_margin) if cost else None
    calculated_list = price_for_margin(cost, margin) if cost else None
    listed = rate.list_price or calculated_list
    return rate.model_copy(
        update={
            "recommended_price": recommended,
            "recommended_margin": _margin(cost, recommended),
            "recommended_share": _share(cost, recommended),
            "calculated_list_price": calculated_list,
            "effective_list_price": listed,
            "list_margin": _margin(cost, listed),
            "list_share": _share(cost, listed),
        }
    )
