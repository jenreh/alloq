"""Single drawer that switches body by DashboardState.drill_down."""

from __future__ import annotations

from collections.abc import Callable

import reflex as rx
from alloq_commons.components import ROW_STYLE
from alloq_commons.components.formatters import de_number, format_date_de
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import DRAWER_CLASS

import appkit_mantine as mn
from alloq_dashboard.states import (
    BudgetBurnState,
    DashboardState,
    UnderUtilizationState,
    UtilizationState,
)

DRILL_UTILIZATION = "utilization"
DRILL_EARNED_VALUE = "earned_value"
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
                    lambda w: {
                        "label": w.week_label,
                        "Auslastung": rx.cond(
                            w.week_label == data.current_week_label, 0, w.percent
                        ),
                        "Aktuelle Woche": rx.cond(
                            w.week_label == data.current_week_label, w.percent, 0
                        ),
                    }
                ),
                data_key="label",
                chart_type="stacked",
                series=[
                    {
                        "name": "Auslastung",
                        "color": (
                            "light-dark(var(--mantine-color-blue-2), "
                            "var(--mantine-color-blue-9))"
                        ),
                    },
                    {
                        "name": "Aktuelle Woche",
                        "color": "var(--mantine-color-blue-6)",
                    },
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


def _ev_stat_cell(
    label: str,
    value: rx.Var,
    *,
    color: str | None = None,
) -> rx.Component:
    style: dict = {
        "fontSize": "var(--mantine-font-size-xs)",
        "fontWeight": "700",
    }
    if color:
        style["color"] = f"var(--mantine-color-{color}-6)"
    return mn.stack(
        mn.text(label, size="xs", c="dimmed", fw="500"),
        de_number(
            value,
            decimal_scale=0,
            fixed_decimal_scale=True,
            suffix=" \u20ac",
            style=style,
        ),
        gap="1px",
        align="left",
    )


def _ev_project_row(p: rx.Var) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(
                p.name,
                size="sm",
                fw="600",
                truncate=True,
                style={"flex": "1 1 0"},
            ),
            mn.text(
                format_date_de(p.start_date) + " → " + format_date_de(p.end_date),
                size="xs",
                c="dimmed",
                style={"flexShrink": "0", "whiteSpace": "nowrap"},
            ),
            align="center",
            gap="xs",
            w="100%",
            wrap="nowrap",
        ),
        mn.progress(
            value=p.progress,
            color=p.color,
            size="sm",
            radius="xl",
            bg="var(--alloq-meter-track)",
            w="100%",
        ),
        mn.simple_grid(
            _ev_stat_cell("Budget", p.budget),
            _ev_stat_cell("Prognose lin.", p.ev_eac_linear, color="teal"),
            _ev_stat_cell("Prognose add.", p.ev_eac_additive, color="violet"),
            _ev_stat_cell("Fertigst.wert", p.ev_earned_value),
            _ev_stat_cell("Ist-Kosten", p.ev_actual_cost),
            cols=5,
            spacing="xs",
            w="100%",
        ),
        gap="xs",
        style={
            **ROW_STYLE,
            "backgroundColor": "var(--alloq-fade-bg)",
            "padding": "12px 18px",
        },
        w="100%",
    )


def _earned_value_body() -> rx.Component:
    rows = BudgetBurnState.data.rows
    return mn.stack(
        # mn.text("Aktive Projekte", size="sm", fw="600", p="6px 18px"),
        rx.cond(
            rows.length() > 0,
            mn.stack(
                rx.foreach(
                    rows,
                    lambda p: rx.cond(
                        (p.state == "Aktiv") | (p.state == "Risiko"),
                        _ev_project_row(p),
                        rx.fragment(),
                    ),
                ),
                gap="xs",
                w="100%",
            ),
            mn.text(
                "Keine aktiven Projekte.",
                size="sm",
                c="var(--alloq-text-muted)",
            ),
        ),
    )


def _drill_title(key: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        key,
        (DRILL_UTILIZATION, "Team-Auslastung"),
        (DRILL_EARNED_VALUE, "Budget Prognosen (aktive Projekte)"),
        "Details",
    )


def drill_down_drawer() -> rx.Component:
    """Single drawer with body switched by drill-down key."""
    return mn.drawer(
        mn.box(
            rx.match(
                DashboardState.drill_down,
                (DRILL_UTILIZATION, _utilization_body()),
                (DRILL_EARNED_VALUE, _earned_value_body()),
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
