import reflex as rx
from alloq_project.states.planning_state import PlanningState

import appkit_mantine as mn


def planning_toolbar() -> rx.Component:
    """Fixed top-right toolbar for the resource planning page."""
    return rx.flex(
        mn.text_input(
            placeholder="Suchen...",
            left_section=rx.icon("search", size=16),
            value=PlanningState.search_query,
            on_change=PlanningState.set_search_query,
            size="sm",
            w="18rem",
        ),
        mn.button(
            mn.text("Projekt planen", size="sm", c="black"),
            left_section=rx.icon("plus", size=20, color="black"),
            variant="filled",
            size="sm",
            padding="0",
            radius="md",
        ),
        # Project scope toggle
        mn.group(
            mn.button(
                rx.icon(
                    "folder-open",
                    size=18,
                    color=rx.cond(
                        PlanningState.project_scope == "Meine Projekte",
                        "black",
                        "var(--alloq-text)",
                    ),
                ),
                variant="filled",
                bg=rx.cond(
                    PlanningState.project_scope == "Meine Projekte",
                    "alloqWarm.5",
                    "var(--alloq-fade-bg)",
                ),
                on_click=PlanningState.toggle_project_scope,
                size="sm",
                p="0 8px",
                radius="md",
            ),
            # Employee scope toggle
            mn.button(
                rx.icon(
                    "users",
                    size=18,
                    color=rx.cond(
                        PlanningState.employee_scope == "Meine Mitarbeiter",
                        "black",
                        "var(--alloq-text)",
                    ),
                ),
                variant=rx.cond(
                    PlanningState.employee_scope == "Meine Mitarbeiter",
                    "filled",
                    "subtle",
                ),
                bg=rx.cond(
                    PlanningState.employee_scope == "Meine Mitarbeiter",
                    "alloqWarm.5",
                    "var(--alloq-fade-bg)",
                ),
                on_click=PlanningState.toggle_employee_scope,
                size="sm",
                p="0 8px",
                radius="md",
            ),
            gap="4px",
            ml="6px",
        ),
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
