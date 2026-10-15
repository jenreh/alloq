import reflex as rx
from alloq_commons.components.toolbar import (
    icon_button,
    primary_button,
    segmented,
    toolbar_search,
)
from alloq_commons.components.view_mode_toggle import view_mode_toggle
from alloq_team.states.team_list_state import FILTERS
from alloq_team.states.team_state import TeamState


def team_filter() -> rx.Component:
    """Filter segments in the toolbar center."""
    return segmented(TeamState.list_filter, TeamState.set_list_filter, FILTERS)


def team_toolbar() -> list[rx.Component]:
    """Toolbar actions of the team page."""
    return [
        toolbar_search(
            TeamState.search_filter, TeamState.set_search_filter, "Name oder Rolle"
        ),
        view_mode_toggle(TeamState.view_mode, TeamState.set_view_mode),
        icon_button(
            "panel-right",
            "Inspektor ein- oder ausblenden",
            TeamState.toggle_inspector,
            active=TeamState.show_inspector,
        ),
        primary_button("Mitarbeiter anlegen", "plus", TeamState.open_add_modal),
    ]
