"""Single drawer that switches body by DashboardState.drill_down."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn
from alloq_dashboard.components.cards import (
    DRILL_BUDGET_BURN,
    DRILL_PROJECT_HEALTH,
    DRILL_PROJECTS_OVERVIEW,
    DRILL_RISKS,
    DRILL_UNDER_UTILIZATION,
    DRILL_UTILIZATION,
)
from alloq_dashboard.states import (
    BudgetBurnState,
    DashboardState,
    ProjectHealthState,
    ProjectsOverviewState,
    RiskState,
    UnderUtilizationState,
    UtilizationState,
)

ROW_STYLE = {
    "padding": "8px 12px",
    "borderRadius": "6px",
    "backgroundColor": "var(--alloq-surface-muted)",
}


def _project_row(project: rx.Var) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.group(
                mn.box(
                    style={
                        "width": "4px",
                        "height": "20px",
                        "borderRadius": "2px",
                        "backgroundColor": project.color,
                        "flexShrink": "0",
                    },
                ),
                mn.text(
                    project.code + " — " + project.name,
                    size="sm",
                    fw="600",
                    c="var(--alloq-text)",
                ),
                mn.badge(project.state, size="xs", color="gray", variant="light"),
                gap="sm",
                align="center",
            ),
            mn.group(
                mn.text(
                    "Fortschritt: " + project.progress.to_string() + "%",
                    size="xs",
                    c="var(--alloq-text-muted)",
                ),
                mn.text(
                    "Verbrauch: " + project.spent_percent.to_string() + "%",
                    size="xs",
                    c="var(--alloq-text-muted)",
                ),
                rx.cond(
                    project.end_date,
                    mn.text(
                        "Ende: " + project.end_date.to_string(),
                        size="xs",
                        c="var(--alloq-text-muted)",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    project.risk_count > 0,
                    mn.badge(
                        project.risk_count.to_string() + " Risiko",
                        size="xs",
                        color="red",
                        variant="light",
                    ),
                    rx.fragment(),
                ),
                gap="md",
                align="center",
            ),
            gap="2px",
        ),
        justify="space-between",
        align="center",
        w="100%",
        style=ROW_STYLE,
    )


def _projects_overview_body() -> rx.Component:
    data = ProjectsOverviewState.data
    return mn.stack(
        mn.text("Verteilung", size="sm", fw="600", c="var(--alloq-text)"),
        mn.group(
            rx.foreach(
                data.by_state,
                lambda s: mn.stack(
                    mn.text(s.state, size="xs", c="var(--alloq-text-muted)"),
                    mn.badge(
                        s.count.to_string(),
                        size="lg",
                        color="gray",
                        variant="light",
                    ),
                    gap="4px",
                    align="center",
                    style={**ROW_STYLE, "flex": "1"},
                ),
            ),
            gap="sm",
            w="100%",
            grow=True,
        ),
        mn.divider(),
        mn.text("Alle Projekte", size="sm", fw="600", c="var(--alloq-text)"),
        rx.foreach(data.rows, _project_row),
        gap="sm",
        w="100%",
    )


def _project_health_body() -> rx.Component:
    data = ProjectHealthState.data
    return mn.stack(
        mn.group(
            mn.badge(
                data.at_risk_count.to_string() + " gefährdet",
                color="red",
                variant="filled",
                size="lg",
            ),
            mn.badge(
                data.healthy_count.to_string() + " gesund",
                color="green",
                variant="light",
                size="lg",
            ),
            gap="md",
        ),
        mn.divider(),
        rx.cond(
            data.rows.length() > 0,
            mn.stack(rx.foreach(data.rows, _project_row), gap="xs"),
            mn.text("Keine Projekte gefährdet.", c="var(--alloq-text-muted)"),
        ),
        gap="md",
        w="100%",
    )


def _budget_burn_body() -> rx.Component:
    data = BudgetBurnState.data
    return mn.stack(
        mn.group(
            mn.stack(
                mn.text("Budget", size="xs", c="var(--alloq-text-muted)"),
                mn.text(data.total_budget.to_string() + " €", size="lg", fw="700"),
                gap="2px",
            ),
            mn.stack(
                mn.text("Verbrauch", size="xs", c="var(--alloq-text-muted)"),
                mn.text(data.total_spent.to_string() + " €", size="lg", fw="700"),
                gap="2px",
            ),
            mn.stack(
                mn.text("Quote", size="xs", c="var(--alloq-text-muted)"),
                mn.text(data.spent_percent.to_string() + " %", size="lg", fw="700"),
                gap="2px",
            ),
            gap="lg",
        ),
        mn.divider(),
        mn.text("Verlauf", size="sm", fw="600"),
        mn.line_chart(
            data=data.trend.foreach(lambda p: {"label": p.label, "Verbrauch": p.value}),
            data_key="label",
            series=[{"name": "Verbrauch", "color": "var(--mantine-color-orange-6)"}],
            h=180,
            with_legend=False,
            with_y_axis=True,
            grid_axis="y",
            curve_type="monotone",
        ),
        mn.divider(),
        mn.text("Pro Projekt (sortiert nach Quote)", size="sm", fw="600"),
        rx.foreach(data.rows, _project_row),
        gap="md",
        w="100%",
    )


def _employee_util_row(emp: rx.Var) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(emp.name, size="sm", fw="600"),
            rx.cond(
                emp.role_name != "",
                mn.badge(emp.role_name, size="xs", color="gray", variant="light"),
                rx.fragment(),
            ),
            mn.badge(
                emp.avg_percent.to_string() + "%",
                size="md",
                variant="light",
                color="blue",
            ),
            gap="sm",
            align="center",
        ),
        mn.text(
            "Frei nächste 4 Wochen: " + emp.free_hours_next_4w.to_string() + " h",
            size="xs",
            c="var(--alloq-text-muted)",
        ),
        gap="2px",
        style=ROW_STYLE,
    )


def _utilization_body() -> rx.Component:
    data = UtilizationState.data
    return mn.stack(
        mn.text(
            "Aktuelle Auslastung: " + data.current_percent.to_string() + " %",
            size="lg",
            fw="700",
        ),
        mn.bar_chart(
            data=data.weeks.foreach(
                lambda w: {"label": w.week_label, "Auslastung": w.percent}
            ),
            data_key="label",
            series=[{"name": "Auslastung", "color": "var(--mantine-color-blue-6)"}],
            h=200,
            with_legend=False,
            with_y_axis=True,
            grid_axis="y",
            x_axis_props={"fontSize": 10},
        ),
        mn.divider(),
        mn.text("Pro Mitarbeiter", size="sm", fw="600"),
        rx.foreach(data.employee_breakdown, _employee_util_row),
        gap="md",
        w="100%",
    )


def _under_utilization_body() -> rx.Component:
    data = UnderUtilizationState.data
    return mn.stack(
        mn.group(
            mn.badge(
                data.affected_count.to_string() + " unter 70%",
                color="yellow",
                size="lg",
                variant="filled",
            ),
            mn.badge(
                data.total_free_hours.to_string() + " h frei (4 Wo)",
                color="blue",
                size="lg",
                variant="light",
            ),
            gap="md",
        ),
        mn.divider(),
        rx.cond(
            data.rows.length() > 0,
            mn.stack(rx.foreach(data.rows, _employee_util_row), gap="xs"),
            mn.text(
                "Alle Mitarbeiter sind ≥ 70% ausgelastet.",
                c="var(--alloq-text-muted)",
            ),
        ),
        gap="md",
        w="100%",
    )


def _severity_color(severity: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        severity,
        ("high", "red"),
        ("medium", "yellow"),
        ("low", "green"),
        "gray",
    )


def _risk_row(risk: rx.Var) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.badge(
                risk.severity,
                color=_severity_color(risk.severity),
                size="sm",
                variant="filled",
            ),
            mn.text(risk.name, size="sm", fw="600", c="var(--alloq-text)"),
            gap="sm",
            align="center",
        ),
        mn.group(
            mn.text(
                risk.project_code + " — " + risk.project_name,
                size="xs",
                c="var(--alloq-text-muted)",
            ),
            rx.cond(
                risk.owner,
                mn.text(
                    "Owner: " + risk.owner.to_string(),
                    size="xs",
                    c="var(--alloq-text-muted)",
                ),
                rx.fragment(),
            ),
            gap="md",
        ),
        gap="2px",
        style=ROW_STYLE,
    )


def _risks_body() -> rx.Component:
    data = RiskState.data
    return mn.stack(
        mn.simple_grid(
            mn.group(
                mn.text("Hoch", size="sm"),
                mn.badge(data.open_high.to_string(), color="red", size="lg"),
                justify="space-between",
                style=ROW_STYLE,
            ),
            mn.group(
                mn.text("Mittel", size="sm"),
                mn.badge(data.open_medium.to_string(), color="yellow", size="lg"),
                justify="space-between",
                style=ROW_STYLE,
            ),
            mn.group(
                mn.text("Niedrig", size="sm"),
                mn.badge(data.open_low.to_string(), color="green", size="lg"),
                justify="space-between",
                style=ROW_STYLE,
            ),
            cols={"base": 3},
            spacing="sm",
            w="100%",
        ),
        mn.divider(),
        mn.text("Top offene Risiken", size="sm", fw="600"),
        rx.cond(
            data.top_open.length() > 0,
            mn.stack(rx.foreach(data.top_open, _risk_row), gap="xs"),
            mn.text("Keine offenen Risiken.", c="var(--alloq-text-muted)"),
        ),
        gap="md",
        w="100%",
    )


def _drill_title(key: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        key,
        (DRILL_PROJECTS_OVERVIEW, "Aktuelle Projekte"),
        (DRILL_PROJECT_HEALTH, "Projekt-Gesundheit"),
        (DRILL_BUDGET_BURN, "Budgetverbrauch"),
        (DRILL_UTILIZATION, "Team-Auslastung"),
        (DRILL_UNDER_UTILIZATION, "Auslastungslücken"),
        (DRILL_RISKS, "Risiken"),
        "Details",
    )


def drill_down_drawer() -> rx.Component:
    """Single drawer with body switched by drill-down key."""
    return mn.drawer(
        mn.box(
            rx.match(
                DashboardState.drill_down,
                (DRILL_PROJECTS_OVERVIEW, _projects_overview_body()),
                (DRILL_PROJECT_HEALTH, _project_health_body()),
                (DRILL_BUDGET_BURN, _budget_burn_body()),
                (DRILL_UTILIZATION, _utilization_body()),
                (DRILL_UNDER_UTILIZATION, _under_utilization_body()),
                (DRILL_RISKS, _risks_body()),
                rx.fragment(),
            ),
            p="md",
        ),
        title=_drill_title(DashboardState.drill_down),
        opened=DashboardState.drill_down != "",
        on_close=DashboardState.close_drill_down,
        position="right",
        size="lg",
        overlay_props={"backgroundOpacity": 0.3, "blur": 3},
        offset="15px",
        radius="md",
        with_close_button=True,
        close_on_click_outside=True,
    )
