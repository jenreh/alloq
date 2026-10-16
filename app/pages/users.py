from collections.abc import Callable

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.desktop import is_desktop

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.user_management.components.user import (
    add_user_button,
    add_user_modal,
    edit_user_modal,
    search_user_input,
    user_table_view,
)
from appkit_user.user_management.states.user_states import UserState

from app.components.db_access_button import database_access_button
from app.desktop.db_access_state import DatabaseAccessState
from app.roles import ALL_ROLES


def user_toolbar() -> list[rx.Component]:
    """Toolbar actions of the users page."""
    return [search_user_input(), add_user_button()]


def row_actions() -> list[Callable[..., rx.Component]]:
    """Extra row buttons. Only the desktop app connects to the database as the
    signed-in person, so only there an admin can grant database access."""
    return [database_access_button] if is_desktop() else []


def create_users_page(
    sidebar: rx.Component,
    route: str = "/admin/users",
    title: str = "Benutzer",
    additional_components: list[rx.Component] | None = None,
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Benutzer",
            "Administration · Benutzer anlegen, bearbeiten und löschen",
            actions=user_toolbar(),
        ),
        admin_only=True,
        on_load=[
            UserState.set_available_roles(ALL_ROLES),
            UserState.load_users,
            DatabaseAccessState.load,
        ],
    )
    def _users_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                # Rendered here because this page composes user_table_view()
                # plus its own toolbar instead of users_table(), which is what
                # otherwise mounts these two. Without them the add/edit buttons
                # flip UserState.*_modal_open but nothing is on screen to react.
                add_user_modal(),
                edit_user_modal(),
                mn.box(
                    user_table_view(
                        additional_components=[
                            *row_actions(),
                            *(additional_components or []),
                        ]
                    ),
                    style=theme.CARD,
                    p="xs",
                    w="100%",
                ),
                width="100%",
                max_width="1200px",
            ),
        )

    return _users_page
