"""Single drawer that switches body by DashboardState.drill_down."""

from __future__ import annotations

from collections.abc import Callable

import reflex as rx
from alloq_commons.components.formatters import de_number
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import DRAWER_CLASS

import appkit_mantine as mn
from alloq_dashboard.components.cards import (
    DRILL_BUDGET_BURN,
    DRILL_RISKS,
    DRILL_UTILIZATION,
)
from alloq_dashboard.components.shared import ROW_STYLE, severity_badge_color
from alloq_dashboard.states import (
    BudgetBurnState,
    DashboardState,
    RiskState,
    UnderUtilizationState,
    UtilizationState,
)

HIGH_WORKLOAD_PERCENT = 70
WORKLOAD_LIMIT_PERCENT = 100


def _empty_utilization_message(message: str) -> rx.Component:
    return mn.text(message, size="sm", c="var(--alloq-text-muted)")


def _utilization_badge(percent: rx.Var) -> rx.Component:
    return mn.badge(
        de_number(percent, suffix="%"),
        size="lg",
        variant="light",
        color="blue",
    )


def _absence_badge() -> rx.Component:
    return mn.badge(
        rx.icon("plane", size=16, color="var(--alloq-text-muted)"),
        size="lg",
        variant="light",
        color="gray",
    )


def _current_utilization_badge(emp: rx.Var) -> rx.Component:
    return rx.cond(
        emp.current_week_is_absent,
        _absence_badge(),
        _utilization_badge(emp.current_week_percent),
    )


def _free_hours_line(hours: rx.Var) -> rx.Component:
    muted_text_style = {
        "fontSize": "var(--mantine-font-size-xs)",
        "color": "var(--alloq-text-muted)",
        "fontWeight": "400",
    }
    return mn.group(
        mn.text(
            "Frei nächste 4 Wochen:",
            size="xs",
            c="var(--alloq-text-muted)",
        ),
        de_number(
            hours,
            minimum_fraction_digits=0,
            maximum_fraction_digits=1,
            suffix=" h",
            style=muted_text_style,
        ),
        gap="4px",
    )


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


def _employee_bucket_sections(
    row_fn: Callable[[rx.Var], rx.Component],
    noun: str,
) -> list[rx.Component]:
    """Render Überlastet / Gut ausgelastet / Defizit / Abwesend sections."""
    data = UtilizationState.data
    summary = UnderUtilizationState.data
    well_utilized_count = (
        summary.total_employees
        - summary.overloaded_count
        - summary.affected_count
        - summary.absent_count
    )
    return [
        section(
            mn.text("Überlastet (> 100%)", size="sm", fw="600"),
            rx.cond(
                summary.overloaded_count > 0,
                rx.foreach(
                    data.employee_breakdown,
                    lambda emp: rx.cond(
                        (emp.current_week_percent > WORKLOAD_LIMIT_PERCENT)
                        & ~emp.current_week_is_absent,
                        row_fn(emp),
                        rx.fragment(),
                    ),
                ),
                _empty_utilization_message(f"Keine {noun} über 100% ausgelastet."),
            ),
        ),
        section(
            mn.text("Gut ausgelastet (70-100%)", size="sm", fw="600"),
            rx.cond(
                well_utilized_count > 0,
                rx.foreach(
                    data.employee_breakdown,
                    lambda emp: rx.cond(
                        (emp.current_week_percent >= HIGH_WORKLOAD_PERCENT)
                        & (emp.current_week_percent <= WORKLOAD_LIMIT_PERCENT)
                        & ~emp.current_week_is_absent,
                        row_fn(emp),
                        rx.fragment(),
                    ),
                ),
                _empty_utilization_message(f"Keine {noun} gut ausgelastet."),
            ),
        ),
        section(
            mn.text("Auslastungsdefizit (< 70%)", size="sm", fw="600"),
            rx.cond(
                summary.affected_count > 0,
                rx.foreach(
                    data.employee_breakdown,
                    lambda emp: rx.cond(
                        (emp.current_week_percent < HIGH_WORKLOAD_PERCENT)
                        & ~emp.current_week_is_absent,
                        row_fn(emp),
                        rx.fragment(),
                    ),
                ),
                _empty_utilization_message(f"Keine {noun} mit Auslastungsdefizit."),
            ),
        ),
        section(
            mn.text("Abwesend", size="sm", fw="600"),
            rx.cond(
                data.current_absent_count > 0,
                rx.foreach(
                    data.employee_breakdown,
                    lambda emp: rx.cond(
                        emp.current_week_is_absent,
                        row_fn(emp),
                        rx.fragment(),
                    ),
                ),
                _empty_utilization_message(f"Keine {noun} abwesend."),
            ),
        ),
    ]


def _employee_util_row(emp: rx.Var) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.text(emp.name, size="sm", fw="600"),
            _free_hours_line(emp.free_hours_next_4w),
            gap="2px",
            align="left",
            style={"flex": "1 1 0", "minWidth": "0"},
        ),
        mn.box(
            _current_utilization_badge(emp),
            style={"marginLeft": "auto", "flexShrink": "0"},
        ),
        justify="space-between",
        align="center",
        wrap="nowrap",
        w="100%",
        style=ROW_STYLE,
    )


def _utilization_body() -> rx.Component:
    data = UtilizationState.data
    return mn.stack(
        section(
            mn.text(
                "Aktuelle Auslastung: " + data.current_percent.to_string() + " %",
                size="sm",
                fw="600",
            ),
            mn.bar_chart(
                data=data.weeks.foreach(
                    lambda w: {"label": w.week_label, "Auslastung": w.percent}
                ),
                data_key="label",
                series=[
                    {
                        "name": "Auslastung",
                        "color": (
                            "light-dark(var(--mantine-color-blue-2), "
                            "var(--mantine-color-blue-9))"
                        ),
                    }
                ],
                reference_lines=[
                    {
                        "y": WORKLOAD_LIMIT_PERCENT,
                        "color": (
                            "light-dark(var(--mantine-color-blue-9), "
                            "var(--mantine-color-blue-2))"
                        ),
                        "label": "100%",
                        "labelPosition": "insideTopRight",
                    }
                ],
                h=200,
                with_legend=False,
                with_y_axis=True,
                grid_axis="y",
                x_axis_props={"fontSize": 10},
                unit="%",
            ),
        ),
        *_employee_bucket_sections(_employee_util_row, "Mitarbeiter"),
        mn.space(h="2rem"),
        gap="md",
        w="100%",
    )


def _risk_row(risk: rx.Var) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.badge(
                risk.severity,
                color=severity_badge_color(risk.severity),
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
        (DRILL_BUDGET_BURN, "Budgetverbrauch"),
        (DRILL_UTILIZATION, "Team-Auslastung"),
        (DRILL_RISKS, "Risiken"),
        "Details",
    )


def drill_down_drawer() -> rx.Component:
    """Single drawer with body switched by drill-down key."""
    return mn.drawer(
        mn.box(
            rx.match(
                DashboardState.drill_down,
                (DRILL_BUDGET_BURN, _budget_burn_body()),
                (DRILL_UTILIZATION, _utilization_body()),
                (DRILL_RISKS, _risks_body()),
                rx.fragment(),
            ),
            class_name="alloq-modal-scroll",
        ),
        title=_drill_title(DashboardState.drill_down),
        opened=DashboardState.drill_down != "",
        on_close=DashboardState.close_drill_down,
        position="right",
        size="lg",
        overlay_props={"backgroundOpacity": 0.3, "blur": 3},
        offset="15px",
        radius="md",
        class_name=DRAWER_CLASS,
        with_close_button=True,
        close_on_click_outside=True,
    )
