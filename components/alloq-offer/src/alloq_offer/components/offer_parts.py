"""Small shared pieces of the offer list and inspector."""

import reflex as rx
from alloq_commons.components.formatters import de_number, format_date_de
from alloq_commons.components.list_view import badge

from alloq_offer.entities import OfferStateEnum

EMPTY_FILTERED = "Keine Angebote mit diesem Filter."
EMPTY_FILTERED_HINT = "Passen Sie die Suche oder den Filter an."
EMPTY_ALL = "Noch keine Angebote vorhanden."
EMPTY_ALL_HINT = "Legen Sie Ihr erstes Angebot an."
RESET_FILTERS = "Filter zurücksetzen"
NO_SELECTION = "Kein Angebot ausgewählt."
STATE_TONES: dict[str, str] = {
    OfferStateEnum.NEW.value: "info",
    OfferStateEnum.IN_PROGRESS.value: "warning",
    OfferStateEnum.SENT.value: "positive",
}


def state_badge(state: rx.Var[str]) -> rx.Component:
    tone = rx.match(state, *STATE_TONES.items(), "neutral")
    return badge(state, tone)


def euro(value: rx.Var) -> rx.Component:
    return de_number(value=value.to(float), decimal_scale=2, suffix=" €")


def days(value: rx.Var) -> rx.Component:
    return de_number(
        value=value.to(float),
        decimal_scale=2,
        minimum_fraction_digits=0,
        suffix=" PT",
    )


def date_or_dash(value: rx.Var) -> rx.Var:
    """DD.MM.YYYY from an ISO date string, "–" when empty."""
    return rx.cond(value, format_date_de(value), "–")
