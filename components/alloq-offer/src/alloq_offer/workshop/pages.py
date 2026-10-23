"""Page factory of the offer workshop."""

import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.roles import OFFER_EDITOR_ROLE

import appkit_mantine as mn
from alloq_offer.workshop.components.workshop_view import (
    workshop_body,
    workshop_tabs,
)
from alloq_offer.workshop.routes import WORKSHOP_ROUTE
from alloq_offer.workshop.states.workshop_state import WorkshopState
from appkit_user.authentication.components.components import requires_role

BACK_LABEL = "Angebote"
NO_ACCESS = "Die Werkstatt ist nur für Angebotsbearbeiter verfügbar."


def create_offer_workshop_page(
    sidebar: rx.Component,
    route: str = WORKSHOP_ROUTE,
    title: str = "Angebotswerkstatt",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            WorkshopState.offer_title,
            WorkshopState.subtitle,
            center=workshop_tabs(),
            actions=[
                rx.link(
                    mn.button(BACK_LABEL, variant="default", size="xs", h=28),
                    href="/offers",
                )
            ],
        ),
        padded=False,
        on_load=[WorkshopState.load_workshop],
    )
    def _workshop_page() -> rx.Component:
        return requires_role(
            workshop_body(),
            role=OFFER_EDITOR_ROLE.name,
            fallback=mn.box(mn.text(NO_ACCESS), p=20),
        )

    return _workshop_page
