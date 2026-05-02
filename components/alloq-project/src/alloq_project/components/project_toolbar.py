import reflex as rx
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn


def add_project_button() -> rx.Component:
    """Button to add a new project."""
    return mn.action_icon(
        rx.icon("plus", size=20, color="black"),
        variant="filled",
        size="lg",
        radius="md",
        on_click=ProjectState.open_add_modal,
    )


def project_search_bar() -> rx.Component:
    """Search input for filtering projects."""
    return mn.text_input(
        placeholder="Suchen...",
        left_section=rx.icon("search", size=16),
        left_section_pointer_events="none",
        value=ProjectState.search_filter,
        on_change=ProjectState.set_search_filter,
        size="sm",
        w="18rem",
    )


def project_status_filter() -> rx.Component:
    """Filter projects by status."""
    return mn.select(
        data=[
            {"value": "all", "label": "Alle"},
            {"value": "active", "label": "Aktiv"},
            {"value": "planned", "label": "Geplant"},
            {"value": "risk", "label": "Risiko"},
        ],
        value=ProjectState.status_filter,
        on_change=ProjectState.set_status_filter,
        clearable=False,
        searchable=False,
        size="sm",
        w="9rem",
    )


def project_toolbar() -> rx.Component:
    """Top-right project page toolbar."""
    return rx.flex(
        project_search_bar(),
        project_status_filter(),
        add_project_button(),
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
