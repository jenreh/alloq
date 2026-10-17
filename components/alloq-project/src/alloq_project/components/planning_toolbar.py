import reflex as rx
from alloq_commons.components.toolbar import icon_button, primary_button
from alloq_project.states.planning_absence_state import PlanningAbsenceState
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.project_plan_state import ProjectPlanState

import appkit_mantine as mn


def _separator() -> rx.Component:
    return mn.box(w=1, h=18, mx=4, bg="var(--aq-border-strong)")


def planning_toolbar() -> list[rx.Component]:
    """Toolbar actions of the resource planning page."""
    return [
        rx.cond(
            (PlanningStore.view_mode == "Grid")
            | (PlanningStore.view_mode == "Projekte"),
            icon_button(
                rx.cond(
                    PlanningStore.all_sections_collapsed,
                    "list-chevrons-up-down",
                    "list-chevrons-down-up",
                ),
                rx.cond(
                    PlanningStore.all_sections_collapsed,
                    "Alle ausklappen",
                    "Alle einklappen",
                ),
                PlanningStore.toggle_all_sections,
                active=PlanningStore.all_sections_collapsed,
            ),
            rx.fragment(),
        ),
        rx.cond(
            (PlanningStore.view_mode == "Grid")
            | (PlanningStore.view_mode == "Projekte"),
            icon_button(
                rx.cond(PlanningStore.is_compact, "unfold-vertical", "fold-vertical"),
                rx.cond(
                    PlanningStore.is_compact,
                    "Kompakte Zeilen – klicken für normale Höhe",
                    "Normale Zeilen – klicken für kompakte Höhe",
                ),
                PlanningStore.toggle_grid_density,
                active=PlanningStore.is_compact,
            ),
            rx.fragment(),
        ),
        icon_button(
            "folder-kanban",
            rx.cond(
                PlanningStore.project_scope,
                "Nur eigene Projekte – klicken für alle",
                "Alle Projekte – klicken für eigene",
            ),
            PlanningStore.toggle_project_scope,
            active=PlanningStore.project_scope,
        ),
        icon_button(
            "users",
            rx.cond(
                PlanningStore.employee_scope,
                "Nur eigene Mitarbeiter – klicken für alle",
                "Alle Mitarbeiter – klicken für eigene",
            ),
            PlanningStore.toggle_employee_scope,
            active=PlanningStore.employee_scope,
        ),
        _separator(),
        icon_button(
            "save",
            "Änderungen speichern (⌘S)",
            PlanningStore.save_grid,
            active=PlanningStore.has_dirty,
            disabled=~PlanningStore.has_dirty | PlanningStore.is_saving,
            loading=PlanningStore.is_saving,
        ),
        rx.cond(
            PlanningStore.view_mode == "Abwesenheiten",
            primary_button(
                "Abwesenheit eintragen", "plus", PlanningAbsenceState.open_new_absence
            ),
            primary_button("Projekt planen", "plus", ProjectPlanState.open_modal),
        ),
    ]
