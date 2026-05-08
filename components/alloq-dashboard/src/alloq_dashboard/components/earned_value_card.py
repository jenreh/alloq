"""Earned value chart KPI card."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn
from alloq_dashboard.components.kpi_card import kpi_card
from alloq_dashboard.states import BudgetBurnState


def earned_value_card() -> rx.Component:
    data = BudgetBurnState.data
    body = mn.stack(
        mn.text(
            "Budget vs. Fortschritt, alle aktiven Projekte",
            size="xs",
            c="var(--alloq-text-muted)",
        ),
        rx.cond(
            data.earned_value.length() > 0,
            mn.line_chart(
                data=data.earned_value.foreach(
                    lambda p: {
                        "Monat": p.label,
                        "Budget": p.budget_pct,
                        "Verbrauch": p.spent_pct,
                        "Fortschritt": p.progress_pct,
                    }
                ),
                data_key="Monat",
                series=[
                    {
                        "name": "Budget",
                        "color": "var(--alloq-text)",
                        "strokeDasharray": "5 5",
                    },
                    {
                        "name": "Verbrauch",
                        "color": "var(--mantine-color-yellow-5)",
                    },
                    {
                        "name": "Fortschritt",
                        "color": "var(--mantine-color-teal-5)",
                    },
                ],
                h=200,
                with_legend=True,
                with_y_axis=True,
                with_x_axis=True,
                grid_axis="y",
                curve_type="monotone",
                x_axis_props={"fontSize": 10},
                y_axis_props={"fontSize": 10},
            ),
            mn.text("Keine Verlaufsdaten.", size="sm", c="var(--alloq-text-muted)"),
        ),
        gap="md",
    )
    return kpi_card(
        title="Budget Prognosen",
        body=body,
        is_loading=BudgetBurnState.is_loading,
        error_message=BudgetBurnState.error_message,
        icon="trending-up",
    )
