"""Projects overview KPI card."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.dashboard import big_number
from alloq_project.components.project_card import project_card
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn
from alloq_dashboard.components.kpi_card import kpi_card
from alloq_dashboard.states import ProjectHealthState, ProjectsOverviewState


def active_projects_grid() -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text("Aktive Projekte", size="lg", fw="700", c="var(--alloq-text)"),
            mn.button(
                "Projekt anlegen",
                size="sm",
                variant="filled",
                auto_contrast=True,
                left_section=rx.icon("plus", size=20),
                on_click=ProjectState.open_add_modal,
            ),
            justify="space-between",
            w="100%",
        ),
        rx.cond(
            ProjectState.active_projects.length() > 0,
            mn.simple_grid(
                rx.foreach(ProjectState.active_projects, project_card),
                cols={"base": 1, "sm": 2, "lg": 3},
                spacing="md",
            ),
            mn.text("Keine aktiven Projekte.", size="sm", c="var(--alloq-text-muted)"),
        ),
        gap="md",
        w="100%",
    )


def project_health_card() -> rx.Component:
    data = ProjectHealthState.data
    body = mn.stack(
        big_number(data.at_risk_count),
        mn.text(
            data.total_risk_count.to_string() + " kritische Risiken",
            size="sm",
            fw="600",
            c="var(--mantine-color-red-6)",
        ),
        gap="xs",
    )
    return kpi_card(
        title="Gefährdet",
        body=body,
        is_loading=ProjectHealthState.is_loading,
        error_message=ProjectHealthState.error_message,
        icon="triangle-alert",
        compact=True,
    )


def projects_card() -> rx.Component:
    data = ProjectsOverviewState.data
    body = mn.stack(
        big_number(data.total),
        mn.text(
            "+" + data.planned.to_string() + " Geplant",
            size="sm",
            fw="600",
            c="var(--alloq-accent-text)",
        ),
        gap="xs",
    )
    return kpi_card(
        title="Aktive Projekte",
        body=body,
        is_loading=ProjectsOverviewState.is_loading,
        error_message=ProjectsOverviewState.error_message,
        icon="folder-kanban",
        compact=True,
    )
