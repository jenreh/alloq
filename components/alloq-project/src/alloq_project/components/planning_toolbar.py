from collections.abc import Callable

import reflex as rx
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.project_plan_state import ProjectPlanState

import appkit_mantine as mn


def _toggle_button(
    icon: str,
    active: bool,
    tooltip: str,
    on_click: Callable,
) -> rx.Component:
    """Reusable toggle button with tooltip for the planning toolbar."""
    return mn.tooltip(
        mn.button(
            rx.icon(
                icon,
                size=18,
                color=rx.cond(
                    active,
                    "primary",
                    "var(--alloq-text)",
                ),
            ),
            variant=rx.cond(active, "filled", "subtle"),
            auto_contrast=True,
            on_click=on_click,
            size="sm",
            p="0 8px",
            radius="md",
        ),
        label=tooltip,
        with_arrow=True,
        position="bottom",
    )


def planning_toolbar() -> rx.Component:
    """Fixed top-right toolbar for the resource planning page."""
    return rx.flex(
        mn.text_input(
            placeholder="Suchen...",
            left_section=rx.icon("search", size=16),
            value=PlanningStore.search_query,
            on_change=PlanningStore.set_search_query,
            size="sm",
            w="18rem",
        ),
        mn.button(
            mn.text("Projekt planen", size="sm"),
            left_section=rx.icon("land-plot", size=20),
            variant="filled",
            auto_contrast=True,
            size="sm",
            padding="0",
            radius="md",
            on_click=ProjectPlanState.open_modal,
        ),
        mn.tooltip(
            mn.button(
                rx.icon("save", size=18),
                variant=rx.cond(PlanningStore.has_dirty, "filled", "subtle"),
                auto_contrast=True,
                on_click=PlanningStore.save_grid,
                disabled=~PlanningStore.has_dirty | PlanningStore.is_saving,
                loading=PlanningStore.is_saving,
                size="sm",
                p="0 8px",
                radius="md",
            ),
            label="Änderungen speichern",
            with_arrow=True,
            position="bottom",
        ),
        # Project scope toggle
        mn.group(
            _toggle_button(
                icon="folder-open",
                active=PlanningStore.project_scope,
                tooltip="Nur meine Projekte",
                on_click=PlanningStore.toggle_project_scope,
            ),
            # Employee scope toggle
            _toggle_button(
                icon="users",
                active=PlanningStore.employee_scope,
                tooltip="Nur meine Mitarbeiter",
                on_click=PlanningStore.toggle_employee_scope,
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
