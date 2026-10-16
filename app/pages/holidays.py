import reflex as rx
from alloq_commons import theme
from alloq_commons.components.public_holiday import holidays_table, holidays_toolbar
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.states.holiday_state import HolidayState

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin


def create_holidays_page(
    sidebar: rx.Component,
    route: str = "/admin/holidays",
    title: str = "Feiertage",
) -> rx.Component:
    """Page factory for feiertage management."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Feiertage",
            "Administration · NRW-Feiertage pflegen",
            actions=holidays_toolbar(),
        ),
        admin_only=True,
        on_load=[HolidayState.load_holidays],
    )
    def _holidays_page() -> rx.Component:
        return requires_admin(
            mn.box(
                holidays_table(),
                style=theme.CARD,
                p="xs",
                w="100%",
                max_width="1200px",
            ),
        )

    return _holidays_page
