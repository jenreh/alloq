"""Toolbar of the offers page: filter segments, search, inspector toggle."""

import reflex as rx
from alloq_commons.components.toolbar import (
    icon_button,
    primary_button,
    segmented,
    toolbar_search,
)
from alloq_commons.roles import OFFER_EDITOR_ROLE

from alloq_offer.services.offers import FILTERS
from alloq_offer.states.offer_state import OfferState
from appkit_user.authentication.components.components import requires_role

SEARCH_PLACEHOLDER = "Angebot, Kunde oder Account Manager"


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
        requires_role(
            primary_button("Angebot anlegen", "plus", OfferState.open_create_modal),
            role=OFFER_EDITOR_ROLE.name,
        ),
    ]
