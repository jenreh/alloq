import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar

from alloq_team.components.employee import team_overview
from alloq_team.components.toolbar import team_filter, team_toolbar
from alloq_team.states.team_state import TeamState
from appkit_user.authentication.components.components import requires_admin


def create_team_overview_page(
    sidebar: rx.Component,
    route: str = "/team",
    title: str = "Team",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Team",
            TeamState.subtitle,
            center=team_filter(),
            actions=team_toolbar(),
        ),
        padded=False,
        admin_only=True,
        on_load=[TeamState.load_employees],
    )
    def _team_overview_page() -> rx.Component:
        return requires_admin(team_overview())

    return _team_overview_page
