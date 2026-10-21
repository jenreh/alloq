"""Toolbar of the offers page: filter segments, search, inspector toggle."""

import reflex as rx
from alloq_commons.access import offers_only
from alloq_commons.components.toolbar import (
    icon_button,
    primary_button,
    segmented,
    toolbar_search,
)

from alloq_offer.services.offers import FILTERS
from alloq_offer.states.offer_state import OfferState

SEARCH_PLACEHOLDER = "Angebot, Kunde oder Key Accounter"


def offer_filter() -> rx.Component:
    """Filter segments in the toolbar center."""
    return segmented(OfferState.list_filter, OfferState.set_list_filter, FILTERS)


def offer_toolbar() -> list[rx.Component]:
    """Toolbar actions of the offers page."""
    return [
        toolbar_search(
            OfferState.search_filter,
            OfferState.set_search_filter,
            SEARCH_PLACEHOLDER,
            width="260px",
        ),
        icon_button(
            "panel-right",
            "Inspektor ein- oder ausblenden",
            OfferState.toggle_inspector,
            active=OfferState.show_inspector,
        ),
        offers_only(
            primary_button("Angebot anlegen", "plus", OfferState.open_create_modal)
        ),
    ]
