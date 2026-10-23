"""Page factory of the offers page."""

import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.roles import OFFER_EDITOR_ROLE

import appkit_mantine as mn
from alloq_offer.components.offer_modal import accept_modal, offer_modal
from alloq_offer.components.offer_table import offer_table
from alloq_offer.components.offer_toolbar import offer_filter, offer_toolbar
from alloq_offer.states.offer_state import OfferState
from appkit_user.authentication.components.components import requires_role


def offers_content() -> rx.Component:
    """Offer list for every signed-in user; the edit modal for offer editors."""
    return mn.box(
        requires_role(
            rx.fragment(offer_modal(), accept_modal()), role=OFFER_EDITOR_ROLE.name
        ),
        offer_table(),
        style={"display": "flex", "flexDirection": "column", "minHeight": "0"},
    )


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
        return offers_content()

    return _offers_page
