"""Pure offer logic: state change, derived values, filtering, grouping, sorting."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from alloq_offer.entities import OfferStateEnum
from alloq_offer.models import Offer

FILTER_ALL: Final = "Alle"
FILTER_ARCHIVED: Final = "Archiviert"
FILTERS: Final[tuple[str, ...]] = (
    FILTER_ALL,
    OfferStateEnum.NEW.value,
    OfferStateEnum.IN_PROGRESS.value,
    OfferStateEnum.SENT.value,
    FILTER_ARCHIVED,
)
GROUP_ORDER: Final[tuple[str, ...]] = (
    OfferStateEnum.NEW.value,
    OfferStateEnum.IN_PROGRESS.value,
    OfferStateEnum.SENT.value,
)
SORT_COLUMNS: Final[tuple[str, ...]] = (
    "title",
    "key_accounter",
    "industry",
    "state",
    "person_days",
    "production_cost",
    "recommended_price",
    "sent_date",
)


def apply_state_change(
    state: str,  # noqa: ARG001
    sent_date: date | None,
    new_state: str,
    today: date,
) -> date | None:
    """Sent date after moving to ``new_state``.

    Moving to "Versendet" without a date sets ``today``; every other change
    keeps the date, also when moving back to an earlier state.
    """
    if new_state == OfferStateEnum.SENT and sent_date is None:
        return today
    return sent_date


def total_days(offer: Offer) -> Decimal:
    """Person days plus risk buffer."""
    return offer.person_days + offer.risk_buffer_days


def margin_pct(offer: Offer) -> Decimal | None:
    """Margin in percent of the recommended price; None when it is 0."""
    if not offer.recommended_price:
        return None
    return (
        (offer.recommended_price - offer.production_cost)
        / offer.recommended_price
        * 100
    )


@dataclass(frozen=True)
class OfferTotals:
    """Footer sums of a list of offers."""

    person_days: Decimal = Decimal(0)
    production_cost: Decimal = Decimal(0)
    recommended_price: Decimal = Decimal(0)


def totals(offers: list[Offer]) -> OfferTotals:
    """Sum of person days (incl. buffer), costs and recommended prices."""
    return OfferTotals(
        person_days=sum((total_days(o) for o in offers), Decimal(0)),
        production_cost=sum((o.production_cost for o in offers), Decimal(0)),
        recommended_price=sum((o.recommended_price for o in offers), Decimal(0)),
    )


def search_offers(offers: list[Offer], query: str) -> list[Offer]:
    """Offers whose title, customer or account manager contain ``query``."""
    needle = query.strip().casefold()
    if not needle:
        return list(offers)
    return [
        o
        for o in offers
        if needle in o.title.casefold()
        or needle in o.customer.casefold()
        or needle in o.key_accounter.casefold()
    ]


def filter_offers(offers: list[Offer], list_filter: str) -> list[Offer]:
    """Apply a filter segment; archived offers show only under "Archiviert"."""
    if list_filter == FILTER_ARCHIVED:
        return [o for o in offers if o.archived]
    active = [o for o in offers if not o.archived]
    if list_filter in GROUP_ORDER:
        return [o for o in active if o.state == list_filter]
    return active


_SORT_KEYS: Final[dict[str, Callable[[Offer], object]]] = {
    "title": lambda o: o.title.casefold(),
    "key_accounter": lambda o: o.key_accounter.casefold(),
    "industry": lambda o: o.industry.casefold(),
    "state": lambda o: GROUP_ORDER.index(o.state) if o.state in GROUP_ORDER else -1,
    "person_days": total_days,
    "production_cost": lambda o: o.production_cost,
    "recommended_price": lambda o: o.recommended_price,
}


def sort_offers(offers: list[Offer], column: str, *, desc: bool) -> list[Offer]:
    """Sort by ``column``; unknown columns keep the order. Empty dates go last."""
    if column == "sent_date":
        dated = [o for o in offers if o.sent_date is not None]
        empty = [o for o in offers if o.sent_date is None]
        dated.sort(key=lambda o: o.sent_date or date.min, reverse=desc)
        return dated + empty
    key = _SORT_KEYS.get(column)
    if key is None:
        return list(offers)
    return sorted(offers, key=key, reverse=desc)


def group_offers(offers: list[Offer]) -> dict[str, list[Offer]]:
    """Offers per state group in display order; keeps the incoming order."""
    return {g: [o for o in offers if o.state == g] for g in GROUP_ORDER}


def visible_offers(
    offers: list[Offer],
    *,
    query: str,
    list_filter: str,
    sort_column: str,
    sort_desc: bool,
) -> list[Offer]:
    """Search, filter and sort in one step."""
    return sort_offers(
        filter_offers(search_offers(offers, query), list_filter),
        sort_column,
        desc=sort_desc,
    )
