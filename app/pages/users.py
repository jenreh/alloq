from collections.abc import Callable

import reflex as rx
from alloq_commons.components import page_header

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated
from appkit_user.user_management.components.user import (
    add_user_button,
    search_user_input,
    user_table_view,
)
from appkit_user.user_management.states.user_states import UserState

from app.roles import ALL_ROLES


def user_toolbar() -> rx.Component:
    """Top-right role page toolbar."""
    return rx.flex(
        search_user_input(),
        add_user_button(),
        width="auto",
        gap="12px",
        align="center",
        justify="end",
        style={
            "position": "fixed",
            "top": "2.25rem",
            "right": "2rem",
            "z_index": "20",
        },
    )


def create_users_page(
    navbar: rx.Component,
    route: str = "/admin/users",
    title: str = "Benutzer",
    additional_components: list[rx.Component] | None = None,
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[UserState.set_available_roles(ALL_ROLES)],
    )
    def _users_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                page_header(
                    nav_path=["Administration", "Benutzer"],
                    title="Benutzer verwalten",
                    description="Benutzer anlegen, bearbeiten und löschen.",
                ),
                user_toolbar(),
                mn.box(
                    user_table_view(additional_components=additional_components),
                    background_color="var(--alloq-fade-bg)",
                    border_radius="var(--mantine-radius-lg)",
                    p="1rem",
                    w="100%",
                ),
                width="100%",
                max_width="1200px",
                spacing="6",
                pr="2rem",
                pl="2rem",
            ),
        )

    return _users_page
