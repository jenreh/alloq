import reflex as rx
from alloq_commons import theme
from alloq_commons.components.department import departments_table, departments_toolbar
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar
from alloq_commons.state.department_states import DepartmentState

import appkit_mantine as mn
from appkit_user.authentication.components.components import requires_admin


def create_departments_page(
    sidebar: rx.Component,
    route: str = "/admin/departments",
    title: str = "Abteilungen",
) -> rx.Component:
    """Page factory for department management."""

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Abteilungen",
            "Administration · Abteilungen anlegen, bearbeiten und löschen",
            actions=departments_toolbar(),
        ),
        admin_only=True,
        on_load=[DepartmentState.load_departments],
    )
    def _departments_page() -> rx.Component:
        return requires_admin(
            mn.box(
                departments_table(),
                style=theme.CARD,
                p="xs",
                w="100%",
                max_width="1200px",
            ),
        )

    return _departments_page
