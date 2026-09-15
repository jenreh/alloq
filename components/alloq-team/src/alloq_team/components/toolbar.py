import reflex as rx
from alloq_commons.components.view_mode_toggle import view_mode_toggle
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn


def add_employee_button() -> rx.Component:
    """Button to add a new employee."""
    return mn.action_icon(
        rx.icon("plus", size=20),
        variant="filled",
        auto_contrast=True,
        size="lg",
        radius="md",
        on_click=TeamState.open_add_modal,
    )


def employee_search_bar() -> rx.Component:
    """Search input for filtering employees."""
    return mn.text_input(
        placeholder="Search by name",
        left_section=rx.icon("search", size=16),
        left_section_pointer_events="none",
        right_section=rx.cond(
            TeamState.search_filter != "",
            mn.action_icon(
                rx.icon("x", size=14),
                variant="subtle",
                color="gray",
                size="sm",
                on_click=TeamState.set_search_filter(""),
            ),
            rx.fragment(),
        ),
        value=TeamState.search_filter,
        on_change=TeamState.set_search_filter,
        size="sm",
        w="18rem",
    )


def team_toolbar() -> rx.Component:
    """Top-right team page toolbar."""
    return rx.flex(
        employee_search_bar(),
        add_employee_button(),
        mn.space(w="xs"),
        view_mode_toggle(TeamState.view_mode, TeamState.set_view_mode),
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
