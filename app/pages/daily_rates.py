import reflex as rx
from alloq_commons.components.price_list import (
    price_list_editor,
    price_list_toolbar,
)
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.state.price_list_state import PriceListState

from appkit_user.authentication.components.components import requires_admin


def create_daily_rates_page(
    sidebar: rx.Component,
    route: str = "/admin/daily-rates",
    title: str = "Tagessätze",
) -> rx.Component:
    """Page factory for the daily rates of the roles."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Tagessätze",
            "Administration · Preislisten und Kalkulation",
            actions=price_list_toolbar(),
        ),
        admin_only=True,
        on_load=[PriceListState.load],
    )
    def _daily_rates_page() -> rx.Component:
        return requires_admin(
            price_list_editor(),
        )

    return _daily_rates_page
