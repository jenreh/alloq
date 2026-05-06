from collections.abc import Callable

import reflex as rx
from alloq_commons.components.page_header import page_header
from alloq_project.components.project_overview import (
    add_project_modal,
    project_detail_drawer,
)

import appkit_mantine as mn
from alloq_dashboard.components.cards import dashboard_grid
from alloq_dashboard.components.drill_down_drawer import drill_down_drawer
from alloq_dashboard.states import DashboardState
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
        on_load=[
            UserState.set_available_roles(ALL_ROLES),
            DashboardState.load_all,
        ],
    )
    def _dashboard_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                page_header(
                    nav_path="Willkommen zurück, Jens!",
                    title="Aktuelle Team-Auslastung",
                    description=(
                        "Überwachen Sie wichtige Kennzahlen "
                        "und verfügbare Kapazitäten, um die Ressourcenplanung "
                        "optimal zu steuern."
                    ),
                ),
                dashboard_grid(),
                drill_down_drawer(),
                add_project_modal(),
                project_detail_drawer(),
                width="100%",
                max_width="1360px",
                gap="lg",
                pr="2rem",
                pl="2rem",
                pb="4rem",
            ),
        )

    return _dashboard_page
