"""Dashboard layout grid composition."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn
from alloq_dashboard.components.capacity_card import role_capacity_cards
from alloq_dashboard.components.earned_value_card import earned_value_card
from alloq_dashboard.components.project_cards import (
    active_projects_grid,
    project_health_card,
    projects_card,
)
from alloq_dashboard.components.top_risks_card import top_risks_card
from alloq_dashboard.components.utilization_cards import (
    team_health_card,
    utilization_card,
)


def dashboard_grid() -> rx.Component:
    """Render the full dashboard layout across four sections."""
    return mn.stack(
        mn.simple_grid(
            utilization_card(),
            team_health_card(),
            projects_card(),
            project_health_card(),
            cols={"base": 1, "sm": 2, "lg": 4},
            spacing="lg",
            w="100%",
        ),
        mn.simple_grid(
            earned_value_card(),
            top_risks_card(),
            cols={"base": 1, "sm": 2},
            spacing="lg",
            w="100%",
        ),
        active_projects_grid(),
        role_capacity_cards(),
        gap="xl",
        w="100%",
    )
