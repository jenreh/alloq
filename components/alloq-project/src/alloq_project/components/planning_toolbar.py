from collections.abc import Callable

import reflex as rx
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.project_plan_state import ProjectPlanState

import appkit_mantine as mn


def _toggle_button(
    icon: str,
    active: bool,
    tooltip_on: str,
    tooltip_off: str,
    on_click: Callable,
) -> rx.Component:
    """Reusable toggle button for the planning toolbar.

    The tooltip explains the current filter state and what a click does,
    so the icon-only button is understandable on hover.

    The button is wrapped in a box because its state-dependent props make
    Reflex compile it into a memoized sub-component, which cannot receive
    the ref that Mantine's tooltip attaches to its child. Without a plain
    ref-forwarding element in between, the tooltip never opens.
    """
    return mn.tooltip(
        mn.box(
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
            display="flex",
        ),
        label=rx.cond(active, tooltip_on, tooltip_off),
        with_arrow=True,
        position="bottom",
        multiline=True,
        w=240,
    )


def planning_toolbar() -> rx.Component:
    """Fixed top-right toolbar for the resource planning page."""
    return rx.flex(
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
                tooltip_on=(
                    "Es werden nur eigene Projekte angezeigt. Klicken, um "
                    "wieder alle Projekte zu sehen."
                ),
                tooltip_off=(
                    "Es werden alle Projekte angezeigt. Klicken, um auf die "
                    "eigenen Projekte zu filtern."
                ),
                on_click=PlanningStore.toggle_project_scope,
            ),
            # Employee scope toggle
            _toggle_button(
                icon="users",
                active=PlanningStore.employee_scope,
                tooltip_on=(
                    "Es werden nur eigene Mitarbeiter angezeigt. Klicken, um "
                    "wieder alle Mitarbeiter zu sehen."
                ),
                tooltip_off=(
                    "Es werden alle Mitarbeiter angezeigt. Klicken, um auf "
                    "die eigenen Mitarbeiter zu filtern."
                ),
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
