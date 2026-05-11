from collections.abc import Callable

import reflex as rx
from alloq_commons.components import page_header
from alloq_commons.components.public_holiday import holidays_table, holidays_toolbar
from alloq_commons.states.holiday_state import HolidayState

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated


def create_holidays_page(
    navbar: rx.Component,
    route: str = "/admin/holidays",
    title: str = "Feiertage",
) -> Callable:
    """Page factory for public holiday management."""

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[HolidayState.load_holidays],
    )
    def _holidays_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                page_header(
                    nav_path=["Administration", "Feiertage"],
                    title="Feiertage verwalten",
                    description="NRW-Feiertage anlegen, bearbeiten und löschen.",
                ),
                holidays_toolbar(),
                mn.box(
                    holidays_table(),
                    background_color="var(--alloq-fade-bg)",
                    border_radius="var(--mantine-radius-lg)",
                    p="1rem",
                    w="100%",
                ),
                max_width="1200px",
                min_width="862px",
                spacing="6",
                pr=".8rem",
                pl="2rem",
            ),
        )

    return _holidays_page
