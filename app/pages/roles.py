import reflex as rx
from alloq_commons import theme
from alloq_commons.components import roles_table, roles_toolbar
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.state.role_states import RoleState

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin


def create_roles_page(
    sidebar: rx.Component,
    route: str = "/admin/roles",
    title: str = "Rollen",
) -> rx.Component:
    """Page factory for rollen management."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Rollen",
            "Administration · Rollen anlegen, bearbeiten und löschen",
            actions=roles_toolbar(),
        ),
        admin_only=True,
        on_load=[RoleState.load_roles],
    )
    def _roles_page() -> rx.Component:
        return requires_admin(
            mn.box(
                roles_table(),
                style=theme.CARD,
                p="xs",
                w="100%",
                max_width="1200px",
            ),
        )

    return _roles_page
