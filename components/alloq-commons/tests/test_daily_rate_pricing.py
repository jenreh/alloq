"""Tests for the daily rate price calculation."""

import pytest
from alloq_commons.models import DailyRate
from alloq_commons.services.daily_rate_pricing import (
    price_for_margin,
    price_rate,
    round_up_to_ten,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (1, 10), (10, 10), (11, 20), (769, 770), (1000, 1000)],
)
def test_round_up_to_ten(value: int, expected: int) -> None:
    assert round_up_to_ten(value) == expected


@pytest.mark.parametrize(
    ("cost", "percent", "expected"),
    [
        (780, 30, 1120),  # 780 / 0.70 = 1114.29 rounds up
        (780, 35, 1200),  # 780 / 0.65 = 1200 exactly
        (500, 35, 770),  # 769.23 rounds up
        (500, 0, 500),
        (500, 50, 1000),
        (0, 35, 0),
    ],
)
def test_price_is_cost_over_cost_share_rounded_up(
    cost: int, percent: int, expected: int
) -> None:
    assert price_for_margin(cost, percent) == expected


def test_price_for_full_margin_does_not_divide_by_zero() -> None:
    assert price_for_margin(10, 100) == 1000


def test_sales_price_uses_minimal_margin_and_list_price_the_margin() -> None:
    rate = price_rate(DailyRate(role_id=1, production_cost=780), 30, 35)
    assert (rate.recommended_price, rate.calculated_list_price) == (1120, 1200)
    assert rate.effective_list_price == 1200
    assert (rate.recommended_margin, rate.recommended_share) == (340, 30)
    assert (rate.list_margin, rate.list_share) == (420, 35)


def test_manual_list_price_replaces_calculated_one() -> None:
    rate = price_rate(
        DailyRate(role_id=1, production_cost=780, list_price=1300), 30, 35
    )
    assert rate.recommended_price == 1120
    assert rate.calculated_list_price == 1200
    assert (rate.effective_list_price, rate.list_margin) == (1300, 520)
    assert rate.list_share == 40


def test_without_cost_only_manual_prices_show() -> None:
    rate = price_rate(DailyRate(role_id=1, list_price=1300), 30, 35)
    assert rate.recommended_price is None
    assert rate.effective_list_price == 1300
    assert (rate.list_margin, rate.list_share) == (None, None)
