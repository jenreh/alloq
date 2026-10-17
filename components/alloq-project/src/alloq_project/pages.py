import reflex as rx
from alloq_commons.components.shell import app_page
from alloq_commons.components.toolbar import scope_bar, window_toolbar

import appkit_mantine as mn
from alloq_project.components.planning_filter_row import (
    absence_filter_row,
    planning_filter_row,
    planning_view_switch,
)
from alloq_project.components.planning_gantt import planning_gantt
from alloq_project.components.planning_grid import planning_grid
from alloq_project.components.planning_project_view import (
    planning_project_view,
)
from alloq_project.components.planning_toolbar import planning_toolbar
from alloq_project.components.project_overview import project_overview
from alloq_project.components.project_plan_modal import project_plan_modal
from alloq_project.components.project_toolbar import project_filter, project_toolbar
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.project_state import ProjectState
from appkit_user.authentication.components.components import requires_admin


def create_planning_page(
    sidebar: rx.Component,
    route: str = "/plan",
    title: str = "Ressourcenplanung",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Ressourcenplanung",
            rx.cond(
                PlanningStore.view_mode == "Abwesenheiten",
                "Abwesenheiten und Besetzung je Woche",
                "Kapazität und Zuweisungen je Woche",
            ),
            center=planning_view_switch(),
            actions=planning_toolbar(),
        ),
        scope=scope_bar(
            rx.cond(
                PlanningStore.view_mode == "Abwesenheiten",
                absence_filter_row(),
                planning_filter_row(),
            )
        ),
        padded=False,
        admin_only=True,
        on_load=PlanningStore.load,
    )
    def _planning_page() -> rx.Component:
        return requires_admin(
            mn.box(
                rx.match(
                    PlanningStore.view_mode,
                    ("Grid", planning_grid()),
                    ("Abwesenheiten", planning_gantt()),
                    ("Projekte", planning_project_view()),
                    rx.fragment(),
                ),
                project_plan_modal(),
                class_name="aq-planning-body",
            ),
        )

    return _planning_page


def create_projects_overview_page(
    sidebar: rx.Component,
    route: str = "/projects",
    title: str = "Projekte",
) -> rx.Component:

    @app_page(
        route=route,
        title=title,
        sidebar=sidebar,
        toolbar=window_toolbar(
            "Projekte",
            ProjectState.subtitle,
            center=project_filter(),
            actions=project_toolbar(),
        ),
        padded=False,
        admin_only=True,
        on_load=[ProjectState.load_projects],
    )
    def _projects_overview_page() -> rx.Component:
        return requires_admin(project_overview())

    return _projects_overview_page
