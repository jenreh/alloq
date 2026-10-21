import reflex as rx
from alloq_commons import theme
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_offer.components.industry import industries_table, industries_toolbar
from alloq_offer.states.industry_state import IndustryState

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin


def create_industries_page(
    sidebar: rx.Component,
    route: str = "/admin/industries",
    title: str = "Branchen",
) -> rx.Component:
    """Page factory for the industries offers can use."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Branchen",
            "Administration · Branchen für Angebote pflegen",
            actions=industries_toolbar(),
        ),
        admin_only=True,
        on_load=[IndustryState.load_industries],
    )
    def _industries_page() -> rx.Component:
        return requires_admin(
            mn.box(
                industries_table(),
                style=theme.CARD,
                p="xs",
                w="100%",
                max_width="1200px",
            ),
        )

    return _industries_page
