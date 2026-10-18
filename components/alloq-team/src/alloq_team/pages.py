import reflex as rx
from alloq_commons.access import editor_only, no_access
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import window_toolbar

from alloq_team.components.employee import team_overview
from alloq_team.components.toolbar import team_filter, team_toolbar
from alloq_team.states.team_state import TeamState


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
        on_load=[TeamState.load_employees],
    )
    def _team_overview_page() -> rx.Component:
        return editor_only(team_overview(), fallback=no_access())

    return _team_overview_page
