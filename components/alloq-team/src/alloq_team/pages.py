from collections.abc import Callable

import reflex as rx
from alloq_commons.components.page_header import page_header

import appkit_mantine as mn
from alloq_team.components.employee import team_overview, team_toolbar
from alloq_team.states.team_state import TeamState
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated


def create_team_overview_page(
    navbar: rx.Component,
    route: str = "/team",
    title: str = "Team",
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[TeamState.load_employees],
    )
    def _team_overview_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                team_toolbar(),
                page_header(
                    title="Teamübersicht",
                    description="Verwalten Sie Ihr Team und dessen Verfügbarkeit.",
                ),
                team_overview(),
                width="100%",
                gap="md",
                pr="2rem",
                pl="2rem",
                pt="2rem",
                pb="4rem",
            ),
        )

    return _team_overview_page
