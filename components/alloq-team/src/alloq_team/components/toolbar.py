import reflex as rx
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn


def view_mode_toggle() -> rx.Component:
    """Toggle between grid and table view."""
    return mn.group(
        mn.action_icon(
            rx.icon(
                "layout-grid",
                size=20,
                color=rx.cond(
                    TeamState.view_mode == "grid", "black", "var(--alloq-text)"
                ),
            ),
            variant=rx.cond(TeamState.view_mode == "grid", "filled", "subtle"),
            size="lg",
            radius="md",
            on_click=lambda: TeamState.set_view_mode("grid"),
        ),
        mn.action_icon(
            rx.icon(
                "list",
                size=20,
                color=rx.cond(
                    TeamState.view_mode == "table", "black", "var(--alloq-text)"
                ),
            ),
            variant=rx.cond(TeamState.view_mode == "table", "filled", "subtle"),
            size="lg",
            radius="md",
            on_click=lambda: TeamState.set_view_mode("table"),
        ),
        gap="2px",
    )


def add_employee_button() -> rx.Component:
    """Button to add a new employee."""
    return mn.action_icon(
        rx.icon("plus", size=20, color="black"),
        variant="filled",
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
        view_mode_toggle(),
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
