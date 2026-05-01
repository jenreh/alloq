from collections.abc import Callable

import reflex as rx
from alloq_commons.components.page_header import page_header

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated
from appkit_user.user_management.states.user_states import UserState

from app.roles import ALL_ROLES


def create_projects_overview_page(
    navbar: rx.Component,
    route: str = "/projects",
    title: str = "Projekte",
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[UserState.set_available_roles(ALL_ROLES)],
    )
    def _projects_overview_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                page_header(
                    nav_path="Projekte",
                    title="Projektübersicht",
                    description="Verwalten Sie Ihre Projekte und deren Einstellungen.",
                ),
                width="100%",
                max_width="1200px",
                gap="0",
                pr="2rem",
                pl="2rem",
            ),
        )

    return _projects_overview_page
