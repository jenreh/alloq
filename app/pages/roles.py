from collections.abc import Callable

import reflex as rx
from alloq_commons.components import page_header, roles_table, roles_toolbar
from alloq_commons.state.role_states import RoleState

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated


def create_roles_page(
    navbar: rx.Component,
    route: str = "/admin/roles",
    title: str = "Rollen",
) -> Callable:
    """Page factory for role management."""

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[RoleState.load_roles],
    )
    def _roles_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                page_header(
                    nav_path=["Administration", "Rollen"],
                    title="Rollen verwalten",
                    description="Rollen anlegen, bearbeiten und löschen.",
                ),
                roles_toolbar(),
                roles_table(),
                width="100%",
                max_width="1200px",
                spacing="6",
                pr="2rem",
                pl="2rem",
            ),
        )

    return _roles_page
