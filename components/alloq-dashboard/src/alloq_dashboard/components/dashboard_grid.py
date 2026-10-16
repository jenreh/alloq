"""Dashboard layout grid composition."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn
from alloq_dashboard.components.utilization_cards import (
    team_health_card,
    utilization_card,
)


def dashboard_grid() -> rx.Component:
    """Render the team utilization dashboard."""
    return mn.simple_grid(
        utilization_card(),
        team_health_card(),
        cols={"base": 1, "sm": 2},
        spacing="lg",
        w="100%",
    )
