from collections.abc import Callable

import reflex as rx
from alloq_commons.components.page_header import page_header

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated
from appkit_user.user_management.states.user_states import UserState

from app.roles import ALL_ROLES


def create_dashboard_page(
    navbar: rx.Component,
    route: str = "/",
    title: str = "Dashboard",
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[UserState.set_available_roles(ALL_ROLES)],
    )
    def _dashboard_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                page_header(
                    # TODO(jens): Dynamisch mit Username  # noqa: FIX002
                    nav_path="Willkommnen zurück, Jens!",
                    title="Aktuelle Team-Auslastung",
                    description=(
                        "Überwachen Sie wichtige Kennzahlen "
                        "und verfügbare Kapazitäten, um die Ressourcenplanung "
                        "optimal zu steuern."
                    ),
                ),
                width="100%",
                max_width="1200px",
                gap="0",
                pr="2rem",
                pl="2rem",
            ),
        )

    return _dashboard_page
