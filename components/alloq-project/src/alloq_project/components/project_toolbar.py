import reflex as rx
from alloq_commons.components.toolbar import (
    icon_button,
    primary_button,
    segmented,
    toolbar_search,
)
from alloq_commons.components.view_mode_toggle import view_mode_toggle
from alloq_project.states.project_list_state import FILTERS
from alloq_project.states.project_state import ProjectState


def project_filter() -> rx.Component:
    """Filter segments in the toolbar center."""
    return segmented(ProjectState.list_filter, ProjectState.set_list_filter, FILTERS)


def project_toolbar() -> list[rx.Component]:
    """Toolbar actions of the projects page."""
    return [
        toolbar_search(
            ProjectState.search_filter,
            ProjectState.set_search_filter,
            "Projekt oder Kunde",
        ),
        view_mode_toggle(ProjectState.view_mode, ProjectState.set_view_mode),
        icon_button(
            "panel-right",
            "Inspektor ein- oder ausblenden",
            ProjectState.toggle_inspector,
            active=ProjectState.show_inspector,
        ),
        primary_button("Projekt anlegen", "plus", ProjectState.open_add_modal),
    ]
