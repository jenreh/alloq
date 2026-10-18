import reflex as rx
from alloq_commons import theme
from alloq_commons.components.daily_rate import (
    daily_rates_table,
    daily_rates_toolbar,
    margin_settings,
)
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.state.daily_rate_states import DailyRateState

import appkit_mantine as mn
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
            "Administration · Herstellkosten und Verkaufspreise je Rolle",
            actions=daily_rates_toolbar(),
        ),
        admin_only=True,
        on_load=[DailyRateState.load_daily_rates],
    )
    def _daily_rates_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                margin_settings(),
                mn.box(
                    daily_rates_table(),
                    style=theme.CARD,
                    p="xs",
                    w="100%",
                    max_width="1200px",
                ),
                gap="md",
                w="100%",
            ),
        )

    return _daily_rates_page
