"""Team utilization KPI card."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.dashboard import big_number

import appkit_mantine as mn
from alloq_dashboard.components.drill_down_drawer import DRILL_UTILIZATION
from alloq_dashboard.components.kpi_card import kpi_card
from alloq_dashboard.states import (
    DashboardState,
    UnderUtilizationState,
    UtilizationState,
)


def team_health_card() -> rx.Component:
    data = UnderUtilizationState.data
    body = mn.simple_grid(
        mn.stack(
            mn.group(
                mn.text(
                    data.overloaded_count.to_string(),
                    size="2.25rem",
                    fw="700",
                    c="var(--alloq-text)",
                    style={"lineHeight": "1.0"},
                ),
                mn.text(
                    "/" + data.total_employees.to_string(),
                    size="xl",
                    fw="400",
                    c="var(--alloq-text-muted)",
                    style={"lineHeight": "1.0"},
                ),
                gap="2px",
                align="baseline",
            ),
            mn.text("Überlastung", size="sm", c="var(--alloq-text-muted)"),
            gap="xs",
        ),
        mn.stack(
            mn.group(
                mn.text(
                    data.affected_count.to_string(),
                    size="2.25rem",
                    fw="700",
                    c="var(--alloq-text)",
                    style={"lineHeight": "1.0"},
                ),
                mn.text(
                    "/" + data.total_employees.to_string(),
                    size="xl",
                    fw="400",
                    c="var(--alloq-text-muted)",
                    style={"lineHeight": "1.0"},
                ),
                gap="2px",
                align="baseline",
            ),
            mn.text("Auslastungsdefizit", size="sm", c="var(--alloq-text-muted)"),
            gap="xs",
        ),
        cols=2,
        spacing="md",
    )
    return kpi_card(
        title="Team-Gesundheit",
        body=body,
        is_loading=UnderUtilizationState.is_loading,
        error_message=UnderUtilizationState.error_message,
        icon="heart-pulse",
        compact=True,
        on_open=DashboardState.open_drill_down(DRILL_UTILIZATION),
    )


def utilization_card() -> rx.Component:
    data = UtilizationState.data
    body = mn.stack(
        big_number(data.current_percent, "%"),
        mn.group(
            mn.text("KW", size="sm", c="var(--alloq-text-muted)"),
            mn.text(
                data.current_week.to_string(),
                size="sm",
                c="var(--alloq-text-muted)",
            ),
            gap="2px",
        ),
        gap="xs",
    )
    return kpi_card(
        title="Auslastung",
        body=body,
        is_loading=UtilizationState.is_loading,
        error_message=UtilizationState.error_message,
        icon="activity",
        compact=True,
        on_open=DashboardState.open_drill_down(DRILL_UTILIZATION),
    )
