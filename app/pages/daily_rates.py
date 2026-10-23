import reflex as rx
from alloq_commons.components.price_list import (
    price_list_editor,
    price_list_toolbar,
)
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.state.price_list_state import PriceListState


def create_daily_rates_page(
    sidebar: rx.Component,
    route: str = "/daily-rates",
    title: str = "Tagessätze",
) -> rx.Component:
    """Page factory for the price lists; every user reads, admins edit."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Tagessätze",
            "Preislisten und Kalkulation",
            actions=price_list_toolbar(),
        ),
        on_load=[PriceListState.load],
    )
    def _daily_rates_page() -> rx.Component:
        return price_list_editor()

    return _daily_rates_page
