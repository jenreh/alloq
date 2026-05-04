from collections.abc import Callable

import reflex as rx
from alloq_commons.components.page_header import page_header

import appkit_mantine as mn
from alloq_project.components.planning_toolbar import planning_toolbar
from alloq_project.components.project_overview import project_overview
from alloq_project.components.project_toolbar import project_toolbar
from alloq_project.states.project_state import ProjectState
from appkit_user.authentication.components.components import requires_admin
from appkit_user.authentication.templates import authenticated


def create_planning_page(
    navbar: rx.Component,
    route: str = "/plan",
    title: str = "Ressourcenplanung",
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
    )
    def _planning_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                planning_toolbar(),
                page_header(
                    title="Ressourcenplanung",
                    description=(
                        "Wer ist wann verfügbar? Lücken erkennen, Projekte zuweisen, "
                        "What-if simulieren."
                    ),
                ),
                width="100%",
                gap="md",
                pr="2rem",
                pl="2rem",
                pt="2.1rem",
                pb="4rem",
            ),
        )

    return _planning_page


def create_projects_overview_page(
    navbar: rx.Component,
    route: str = "/projects",
    title: str = "Projekte",
) -> Callable:

    @authenticated(
        route=route,
        title=title,
        navbar=navbar,
        with_header=False,
        admin_only=True,
        on_load=[ProjectState.load_projects],
    )
    def _projects_overview_page() -> rx.Component:
        return requires_admin(
            mn.stack(
                project_toolbar(),
                page_header(
                    title="Projekte",
                    description=(
                        "Alle laufenden und geplanten Projekte mit Budget und "
                        "Fortschritt."
                    ),
                ),
                project_overview(),
                width="100%",
                gap="md",
                pr="2rem",
                pl="2rem",
                pt="2.1rem",
                pb="4rem",
            ),
        )

    return _projects_overview_page
