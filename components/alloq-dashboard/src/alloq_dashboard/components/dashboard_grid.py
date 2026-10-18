"""Dashboard layout: the portfolio overview (variant C)."""

from __future__ import annotations

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.toolbar import segmented

import appkit_mantine as mn
from alloq_dashboard.components.portfolio_bubbles import portfolio_bubbles_card
from alloq_dashboard.components.portfolio_path import (
    portfolio_chains_card,
    portfolio_roles_card,
)
from alloq_dashboard.components.portfolio_risks import portfolio_risks_card
from alloq_dashboard.models import PortfolioKpi
from alloq_dashboard.services.portfolio_inputs import SCOPE_DEPARTMENT, SCOPE_TEAM
from alloq_dashboard.states import PortfolioState

SCOPE_OPTIONS = (
    {"value": SCOPE_DEPARTMENT, "label": "Ganze Abteilung"},
    {"value": SCOPE_TEAM, "label": "Direkt unterstellt"},
)


def scope_control() -> rx.Component:
    """Toolbar switch between the whole department and direct reports."""
    return segmented(
        PortfolioState.scope,
        PortfolioState.set_scope,
        SCOPE_OPTIONS,
        custom_attrs={"aria-label": "Bereich"},
    )


def _notices() -> rx.Component:
    data = PortfolioState.data.to(PortfolioKpi)
    return rx.fragment(
        rx.cond(
            PortfolioState.error_message != "",
            mn.alert(PortfolioState.error_message, color="red", variant="light"),
            rx.fragment(),
        ),
        rx.cond(
            data.notice != "",
            mn.alert(data.notice, color="blue", variant="light"),
            rx.fragment(),
        ),
    )


def dashboard_grid() -> rx.Component:
    """Four portfolio cards: projects, risks, critical path, roles."""
    grid = mn.box(
        portfolio_bubbles_card(),
        portfolio_risks_card(),
        portfolio_chains_card(),
        portfolio_roles_card(),
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(min(100%, 420px), 1fr))",
            "gap": "14px",
            "width": "100%",
            "@media (min-width: 1200px)": {
                "gridTemplateColumns": "minmax(0, 1.6fr) minmax(0, 1fr)",
            },
        },
    )
    return mn.stack(_notices(), grid, gap="sm", w="100%", c=theme.TEXT)
