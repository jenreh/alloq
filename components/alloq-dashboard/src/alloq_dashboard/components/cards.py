"""Eight KPI card bodies for the team-manager dashboard, plus section cards."""

from __future__ import annotations

import reflex as rx
from alloq_project.components.project_card import project_card
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn
from alloq_dashboard.components.kpi_card import kpi_card
from alloq_dashboard.states import (
    BudgetBurnState,
    DashboardState,
    FreeCapacityState,
    ProjectHealthState,
    ProjectsOverviewState,
    RiskState,
    UnderUtilizationState,
    UtilizationState,
)

DRILL_PROJECTS_OVERVIEW = "projects_overview"
DRILL_PROJECT_HEALTH = "project_health"
DRILL_BUDGET_BURN = "budget_burn"
DRILL_UTILIZATION = "utilization"
DRILL_UNDER_UTILIZATION = "under_utilization"
DRILL_RISKS = "risks"

_ROW_STYLE = {
    "padding": "8px 12px",
    "borderRadius": "6px",
    "backgroundColor": "var(--alloq-surface-muted)",
}


# --------------------------------------------------------------------------
# Reusable little widgets
# --------------------------------------------------------------------------


def _big_number(value: rx.Var, suffix: str = "") -> rx.Component:
    return mn.group(
        mn.text(
            value.to_string(),
            size="2.25rem",
            fw="700",
            c="var(--alloq-text)",
            style={"lineHeight": "1.0"},
        ),
        rx.cond(
            suffix != "",
            mn.text(suffix, size="md", c="var(--alloq-text-muted)"),
            rx.fragment(),
        ),
        gap="xs",
        align="baseline",
    )


def _stat_pill(
    label: str,
    value: rx.Var,
    color: str = "var(--alloq-text)",
) -> rx.Component:
    return mn.stack(
        mn.text(label, size="xs", c="var(--alloq-text-muted)"),
        mn.text(value.to_string(), size="lg", fw="700", c=color),
        gap="2px",
    )


def _severity_badge_color(severity: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        severity,
        ("high", "red"),
        ("Hoch", "red"),
        ("medium", "yellow"),
        ("Mittel", "yellow"),
        ("low", "green"),
        ("Niedrig", "green"),
        "gray",
    )


def _status_badge_color(status: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        status,
        ("open", "red"),
        ("Offen", "red"),
        ("in_progress", "yellow"),
        ("In Bearbeitung", "yellow"),
        ("done", "green"),
        ("Erledigt", "green"),
        "gray",
    )


def projects_overview_card() -> rx.Component:
    data = ProjectsOverviewState.data
    body = mn.stack(
        _big_number(data.total),
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
        # background_color=("light-dark(var(--alloq-warm),var(--alloq-accent-soft))"),
        on_open=DashboardState.open_drill_down(DRILL_PROJECTS_OVERVIEW),
    )


def project_health_card() -> rx.Component:
    data = ProjectHealthState.data
    body = mn.stack(
        _big_number(data.at_risk_count),
        mn.text(
            data.total_risk_count.to_string() + " Top Risiken",
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
        on_open=DashboardState.open_drill_down(DRILL_PROJECT_HEALTH),
    )


# --------------------------------------------------------------------------
# Card 5 — Team Gesundheit
# --------------------------------------------------------------------------


def utilization_card() -> rx.Component:
    data = UtilizationState.data
    body = mn.stack(
        _big_number(data.current_percent, "%"),
        mn.group(
            mn.text("Ø Auslastung · KW", size="sm", c="var(--alloq-text-muted)"),
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
        title="Team-Gesundheit",
        body=body,
        is_loading=UtilizationState.is_loading,
        error_message=UtilizationState.error_message,
        icon="heart-pulse",
        compact=True,
        on_open=DashboardState.open_drill_down(DRILL_UTILIZATION),
    )


# --------------------------------------------------------------------------
# Card 6 — Auslastung
# --------------------------------------------------------------------------


def under_utilization_card() -> rx.Component:
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
        title="Auslastung",
        body=body,
        is_loading=UnderUtilizationState.is_loading,
        error_message=UnderUtilizationState.error_message,
        icon="activity",
        compact=True,
        on_open=DashboardState.open_drill_down(DRILL_UTILIZATION),
    )


# --------------------------------------------------------------------------
# Card 7 — free capacity per role
# --------------------------------------------------------------------------


def _role_capacity_card(role: rx.Var) -> rx.Component:
    """Role capacity card matching project card design."""
    return mn.box(
        mn.card(
            mn.stack(
                mn.group(
                    mn.text(
                        role.role_name,
                        size="md",
                        fw="800",
                        c="var(--alloq-text)",
                        truncate=True,
                        w="50%",
                    ),
                    mn.group(
                        mn.stack(
                            mn.text(
                                "PT FREI",
                                size="xs",
                                c="var(--alloq-text-muted)",
                                nowrap=True,
                            ),
                            mn.number_formatter(
                                value=role.free_days,
                                thousand_separator=".",
                                decimal_separator=",",
                                minimum_fraction_digits=2,
                                maximum_fraction_digits=2,
                                style={
                                    "fontSize": "var(--mantine-font-size-lg)",
                                    "fontWeight": "700",
                                },
                            ),
                            gap="2px",
                            flex="1 1 0",
                        ),
                        mn.stack(
                            mn.text(
                                "PT GEPLANT",
                                size="xs",
                                c="var(--alloq-text-muted)",
                                nowrap=True,
                            ),
                            mn.number_formatter(
                                value=role.allocated_days,
                                thousand_separator=".",
                                decimal_separator=",",
                                minimum_fraction_digits=2,
                                maximum_fraction_digits=2,
                                style={
                                    "fontSize": "var(--mantine-font-size-lg)",
                                    "fontWeight": "700",
                                },
                            ),
                            gap="2px",
                            flex="1 1 0",
                        ),
                        mn.stack(
                            _stat_pill(
                                "Mitarbeiter",
                                role.employee_count,
                            ),
                            flex="1 1 0",
                        ),
                        justify="end",
                        nowrap=True,
                        w="42%",
                    ),
                    justify="space-between",
                    align="top",
                    w="100%",
                    wrap="nowrap",
                ),
                rx.cond(
                    role.weeks.length() > 0,
                    mn.area_chart(
                        data=role.weeks.foreach(
                            lambda p: {"label": p.label, "Frei": p.value}
                        ),
                        data_key="label",
                        series=[
                            {"name": "Frei", "color": "var(--mantine-color-green-6)"}
                        ],
                        h=120,
                        with_legend=False,
                        with_y_axis=False,
                        grid_axis="none",
                        tick_line="none",
                        x_axis_props={"fontSize": 10},
                        dot_props={"r": 4},
                        unit=" PT",
                    ),
                    rx.fragment(),
                ),
                gap="md",
            ),
            padding="lg",
            radius="lg",
            with_border=False,
            bg="transparent",
        ),
        style={
            "backgroundColor": "var(--alloq-fade-bg)",
            "borderRadius": "var(--mantine-radius-lg)",
        },
    )


def free_capacity_card() -> rx.Component:
    data = FreeCapacityState.data
    return mn.stack(
        mn.text("Freie Kapazität", size="lg", fw="700", c="var(--alloq-text)"),
        rx.cond(
            data.rows.length() > 0,
            mn.simple_grid(
                rx.foreach(data.rows, _role_capacity_card),
                cols={"base": 1, "sm": 2},
                spacing="lg",
                w="100%",
            ),
            mn.text("Keine Rollen verfügbar.", size="sm", c="var(--alloq-text-muted)"),
        ),
        gap="md",
        w="100%",
    )


# --------------------------------------------------------------------------
# NEW — Earned Value line chart card
# --------------------------------------------------------------------------


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
        title="Earned Value",
        body=body,
        is_loading=BudgetBurnState.is_loading,
        error_message=BudgetBurnState.error_message,
        icon="trending-up",
        on_open=DashboardState.open_drill_down(DRILL_BUDGET_BURN),
    )


# --------------------------------------------------------------------------
# NEW — Top Risks list card
# --------------------------------------------------------------------------


def _risk_row(risk: rx.Var) -> rx.Component:
    return mn.group(
        mn.badge(
            risk.id.to_string(),
            size="lg",
            variant="light",
            color="red",
            style={"minWidth": "2.5rem", "textAlign": "center"},
        ),
        mn.stack(
            mn.text(risk.name, size="sm", fw="600", c="var(--alloq-text)"),
            mn.group(
                mn.badge(
                    risk.project_code,
                    size="xs",
                    variant="light",
                    color="gray",
                ),
                mn.badge(
                    risk.severity,
                    size="xs",
                    variant="dot",
                    color=_severity_badge_color(risk.severity),
                ),
                mn.badge(
                    risk.mitigation_status,
                    size="xs",
                    color=_status_badge_color(risk.mitigation_status),
                    variant="light",
                ),
                gap="xs",
            ),
            gap="2px",
        ),
        gap="sm",
        w="100%",
        style=_ROW_STYLE,
    )


def top_risks_card() -> rx.Component:
    data = RiskState.data
    body = rx.cond(
        data.top_open.length() > 0,
        mn.stack(rx.foreach(data.top_open, _risk_row), gap="xs"),
        mn.text("Keine offenen Risiken.", size="sm", c="var(--alloq-text-muted)"),
    )
    return kpi_card(
        title="Top Risiken",
        body=body,
        is_loading=RiskState.is_loading,
        error_message=RiskState.error_message,
        icon="shield-alert",
        on_open=DashboardState.open_drill_down(DRILL_RISKS),
    )


# --------------------------------------------------------------------------
# NEW — Active Projects grid card (full-width section)
# --------------------------------------------------------------------------


def active_projects_grid_card() -> rx.Component:
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


def dashboard_grid() -> rx.Component:
    """Render the full dashboard layout across four sections."""
    return mn.stack(
        # Section 1: 4 compact KPI cards (top row)
        mn.simple_grid(
            utilization_card(),
            under_utilization_card(),
            projects_overview_card(),
            project_health_card(),
            cols={"base": 1, "sm": 2, "lg": 4},
            spacing="lg",
            w="100%",
        ),
        # Section 2: Earned Value chart (left) + Top Risks list (right)
        mn.simple_grid(
            earned_value_card(),
            top_risks_card(),
            cols={"base": 1, "sm": 2},
            spacing="lg",
            w="100%",
        ),
        # Section 3: Active Projects grid (full-width)
        active_projects_grid_card(),
        # Section 4: Free capacity per role
        free_capacity_card(),
        gap="xl",
        w="100%",
    )
