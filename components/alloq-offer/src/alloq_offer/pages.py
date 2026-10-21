"""Page factory of the offers page."""

import reflex as rx
from alloq_commons.access import no_access, offers_only
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar

import appkit_mantine as mn
from alloq_offer.components.offer_modal import offer_modal
from alloq_offer.components.offer_table import offer_table
from alloq_offer.components.offer_toolbar import offer_filter, offer_toolbar
from alloq_offer.states.offer_state import OfferState


def create_offers_page(
    sidebar: rx.Component,
    route: str = "/offers",
    title: str = "Angebote",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Angebote",
            OfferState.subtitle,
            center=offer_filter(),
            actions=offer_toolbar(),
        ),
        padded=False,
        on_load=[OfferState.load_offers],
    )
    def _offers_page() -> rx.Component:
        return offers_only(
            mn.box(
                offer_modal(),
                offer_table(),
                style={"display": "flex", "flexDirection": "column", "minHeight": "0"},
            ),
            fallback=no_access(),
        )

    return _offers_page
