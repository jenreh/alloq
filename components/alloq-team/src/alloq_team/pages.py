from collections.abc import Callable

import reflex as rx

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated
from appkit_user.user_management.states.user_states import UserState

from app.roles import ALL_ROLES


def create_team_overview_page(
    navbar: rx.Component,
    route: str = "/team",
    title: str = "Team",
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        admin_only=True,
        on_load=[UserState.set_available_roles(ALL_ROLES)],
    )
    def _team_overview_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                mn.title("Team Übersicht", order=1),
                width="100%",
                max_width="1200px",
                spacing="6",
            ),
        )

    return _team_overview_page
