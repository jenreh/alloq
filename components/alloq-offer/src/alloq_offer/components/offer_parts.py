"""Small shared pieces of the offer list and inspector."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.formatters import de_number, format_date_de
from alloq_commons.components.list_view import badge

import appkit_mantine as mn
from alloq_offer.entities import OfferStateEnum

EMPTY_FILTERED = "Keine Angebote mit diesem Filter."
EMPTY_FILTERED_HINT = "Passen Sie die Suche oder den Filter an."
EMPTY_ALL = "Noch keine Angebote vorhanden."
EMPTY_ALL_HINT = "Legen Sie Ihr erstes Angebot an."
RESET_FILTERS = "Filter zurücksetzen"
NO_SELECTION = "Kein Angebot ausgewählt."
NO_SELECTION_HINT = "Wählen Sie links ein Angebot aus, um die Details zu sehen."
STATE_TONES: dict[str, str] = {
    OfferStateEnum.NEW.value: "info",
    OfferStateEnum.IN_PROGRESS.value: "warning",
    OfferStateEnum.SENT.value: "positive",
}


def state_badge(state: rx.Var[str]) -> rx.Component:
    tone = rx.match(state, *STATE_TONES.items(), "neutral")
    return badge(state, tone)


def _dash_when_zero(value: rx.Var, number: rx.Component) -> rx.Component:
    """A zero calculation value means "not calculated yet"."""
    return rx.cond(
        value.to(float) > 0,
        number,
        mn.text("–", fz="inherit", lh="inherit", c=theme.TEXT_MUTED),
    )


def euro(value: rx.Var) -> rx.Component:
    return _dash_when_zero(
        value, de_number(value=value.to(float), decimal_scale=2, suffix=" €")
    )


def days(value: rx.Var) -> rx.Component:
    return _dash_when_zero(
        value,
        de_number(
            value=value.to(float),
            decimal_scale=2,
            minimum_fraction_digits=0,
            suffix=" PT",
        ),
    )


def date_or_dash(value: rx.Var) -> rx.Var:
    """DD.MM.YYYY from an ISO date string, "–" when empty."""
    return rx.cond(value, format_date_de(value), "–")
