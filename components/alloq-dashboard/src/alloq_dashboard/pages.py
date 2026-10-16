from typing import cast

import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.roles import ALL_ROLES
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_dashboard.components.dashboard_grid import dashboard_grid
from alloq_dashboard.components.drill_down_drawer import drill_down_drawer
from alloq_dashboard.states import DashboardState
from appkit_user.authentication.backend.models import User
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.states import UserSession
from appkit_user.user_management.states.user_states import UserState


def _greeting() -> rx.Var:
    """Personal greeting for the signed-in user; generic when no name is set."""
    # appkit_user declares ``user`` as a plain field; class access yields a Var.
    user = cast("ObjectVar[User]", UserSession.user)
    name = user.name
    return rx.cond(
        name,
        "Willkommen zurück, " + name.to(str) + "!",
        "Willkommen zurück!",
    )


def create_dashboard_page(
    sidebar: rx.Component,
    route: str = "/",
    title: str = "Übersicht",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar("Übersicht", _greeting()),
        admin_only=True,
        on_load=[
            UserState.set_available_roles(ALL_ROLES),
            DashboardState.load_all,
        ],
    )
    def _dashboard_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                dashboard_grid(),
                drill_down_drawer(),
                width="100%",
                max_width="1360px",
                gap="lg",
            ),
        )

    return _dashboard_page
