"""Planning Heatmap view: pill-style cells with usage percent + colors."""

from __future__ import annotations

import reflex as rx
from alloq_project.components.planning_grid import (
    GRID_WRAPPER_STYLE,
    LABEL_COL_WIDTH,
    WEEK_COL_WIDTH,
    _row,
)
from alloq_project.states.planning_grid_state import (
    EmployeeBlock,
    HeatCell,
    MonthSpan,
    PlanningGridState,
    WeekColumn,
)

import appkit_mantine as mn

HEAT_ROW_HEIGHT = "56px"
HEAT_HEADER_BG = "var(--alloq-surface-muted)"
HEAT_FOOTER_BG = "var(--alloq-surface-muted)"

ABSENT_STRIPE_BG = (
    "repeating-linear-gradient(45deg, "
    "light-dark(rgba(0,0,0,0.04), rgba(255,255,255,0.05)), "
    "light-dark(rgba(0,0,0,0.04), rgba(255,255,255,0.05)) 4px, "
    "light-dark(rgba(0,0,0,0.10), rgba(255,255,255,0.12)) 4px, "
    "light-dark(rgba(0,0,0,0.10), rgba(255,255,255,0.12)) 8px)"
)


def _heat_bg(bucket: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        bucket,
        ("low", "light-dark(var(--mantine-color-red-1), rgba(250,82,82,0.20))"),
        ("mid", "light-dark(var(--mantine-color-yellow-2), rgba(250,176,5,0.30))"),
        (
            "high",
            "light-dark(var(--mantine-color-green-2), var(--mantine-color-green-6))",
        ),
        (
            "over",
            "light-dark(var(--mantine-color-green-4), var(--mantine-color-green-8))",
        ),
        ("absent", ABSENT_STRIPE_BG),
        "transparent",
    )


def _heat_fg(bucket: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        bucket,
        (
            "low",
            "light-dark(var(--mantine-color-red-9), var(--mantine-color-red-3))",
        ),
        (
            "mid",
            "light-dark(var(--mantine-color-yellow-9), var(--mantine-color-yellow-2))",
        ),
        (
            "high",
            "light-dark(var(--mantine-color-green-9), var(--mantine-color-green-3))",
        ),
        (
            "over",
            "light-dark(var(--mantine-color-green-9), var(--mantine-color-green-3))",
        ),
        (
            "absent",
            "light-dark(var(--mantine-color-gray-7), var(--mantine-color-gray-4))",
        ),
        "var(--alloq-text)",
    )


# ---------------------------- Header ---------------------------------------


def _heatmap_label_th(text: str) -> rx.Component:
    return mn.box(
        mn.text(
            text,
            size="xs",
            fw="700",
            c="var(--alloq-text-muted)",
            style={"letterSpacing": "0.06em", "textTransform": "uppercase"},
        ),
        style={
            "position": "sticky",
            "left": "0",
            "zIndex": "40",
            "backgroundColor": HEAT_HEADER_BG,
            "padding": "8px 16px",
            "minWidth": LABEL_COL_WIDTH,
            "width": LABEL_COL_WIDTH,
            "display": "flex",
            "alignItems": "center",
            "borderRight": "1px solid var(--alloq-border)",
            "borderBottom": "1px solid var(--alloq-border)",
        },
    )


def _month_cell(month: MonthSpan) -> rx.Component:
    return mn.box(
        mn.text(month.label, size="sm", fw="600", c="var(--alloq-text)"),
        style={
            "gridColumn": "span " + month.span.to_string(),
            "backgroundColor": HEAT_HEADER_BG,
            "padding": "10px 8px",
            "display": "flex",
            "alignItems": "center",
            "borderBottom": "1px solid var(--alloq-border)",
        },
    )


def _week_no_cell(week: WeekColumn) -> rx.Component:
    return mn.box(
        mn.text(
            week.week_no.to_string(),
            size="xs",
            c="var(--alloq-text-muted)",
            fw="500",
        ),
        style={
            "backgroundColor": HEAT_HEADER_BG,
            "padding": "6px 0 8px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "borderBottom": "1px solid var(--alloq-border)",
        },
    )


def _heatmap_header() -> rx.Component:
    return mn.box(
        _row(
            _heatmap_label_th("Mitarbeiter"),
            rx.foreach(PlanningGridState.month_spans, _month_cell),
        ),
        _row(
            mn.box(
                style={
                    "position": "sticky",
                    "left": "0",
                    "zIndex": "40",
                    "backgroundColor": HEAT_HEADER_BG,
                    "minWidth": LABEL_COL_WIDTH,
                    "width": LABEL_COL_WIDTH,
                    "borderRight": "1px solid var(--alloq-border)",
                    "borderBottom": "1px solid var(--alloq-border)",
                },
            ),
            rx.foreach(PlanningGridState.weeks, _week_no_cell),
        ),
        style={
            "position": "sticky",
            "top": "0",
            "zIndex": "30",
            "backgroundColor": HEAT_HEADER_BG,
        },
    )


# ---------------------------- Body -----------------------------------------


def _heat_pill(cell: HeatCell) -> rx.Component:
    inner = rx.cond(
        cell.is_absent,
        rx.icon("plane", size=16, color="var(--alloq-text-muted)"),
        mn.text(
            cell.percent.to_string(),
            size="sm",
            fw="600",
            c=_heat_fg(cell.bucket),
        ),
    )
    return mn.box(
        mn.box(
            inner,
            style={
                "background": _heat_bg(cell.bucket),
                "borderRadius": "6px",
                "minHeight": "36px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "width": "100%",
            },
        ),
        style={
            "padding": "6px 4px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "minHeight": HEAT_ROW_HEIGHT,
        },
    )


def _employee_label_cell(emp: EmployeeBlock) -> rx.Component:
    return mn.box(
        mn.group(
            mn.avatar(
                name=emp.name,
                color="var(--alloq-accent-strong)",
                size="md",
                radius="xl",
            ),
            mn.stack(
                mn.text(
                    emp.name,
                    size="sm",
                    fw="700",
                    c="var(--alloq-text)",
                    lh="1.15",
                ),
                rx.cond(
                    emp.job_title != "",
                    mn.text(
                        emp.job_title,
                        size="xs",
                        c="var(--alloq-text-muted)",
                    ),
                    rx.fragment(),
                ),
                gap="2px",
            ),
            gap="sm",
            align="center",
            wrap="nowrap",
        ),
        style={
            "position": "sticky",
            "left": "0",
            "zIndex": "2",
            "backgroundColor": "var(--alloq-surface-solid)",
            "padding": "0 16px",
            "minWidth": LABEL_COL_WIDTH,
            "width": LABEL_COL_WIDTH,
            "minHeight": HEAT_ROW_HEIGHT,
            "display": "flex",
            "alignItems": "center",
            "borderBottom": "1px solid var(--alloq-border)",
            "borderRight": "1px solid var(--alloq-border)",
        },
    )


def _heat_row(emp: EmployeeBlock) -> rx.Component:
    return _row(
        _employee_label_cell(emp),
        rx.foreach(emp.heat, _heat_pill),
        style={
            "minHeight": HEAT_ROW_HEIGHT,
            "_hover": {"backgroundColor": "var(--alloq-surface-hover)"},
        },
    )


# ---------------------------- Footer ---------------------------------------


def _avg_footer_cell(cell: HeatCell) -> rx.Component:
    return mn.box(
        mn.box(
            mn.text(
                cell.percent.to_string(),
                size="xs",
                fw="700",
                c=_heat_fg(cell.bucket),
            ),
            style={
                "background": _heat_bg(cell.bucket),
                "borderRadius": "6px",
                "minHeight": "32px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "width": "100%",
            },
        ),
        style={
            "padding": "4px 4px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "minHeight": HEAT_ROW_HEIGHT,
        },
    )


def _heatmap_footer() -> rx.Component:
    return _row(
        mn.box(
            mn.text(
                "Durchschnitt Ø",
                size="xs",
                fw="700",
                c="var(--alloq-text-muted)",
                style={"letterSpacing": "0.06em", "textTransform": "uppercase"},
            ),
            style={
                "position": "sticky",
                "left": "0",
                "zIndex": "40",
                "backgroundColor": HEAT_FOOTER_BG,
                "padding": "8px 16px",
                "minWidth": LABEL_COL_WIDTH,
                "width": LABEL_COL_WIDTH,
                "minHeight": HEAT_ROW_HEIGHT,
                "display": "flex",
                "alignItems": "center",
                "borderRight": "1px solid var(--alloq-border)",
            },
        ),
        rx.foreach(PlanningGridState.avg_heat, _avg_footer_cell),
        style={
            "position": "sticky",
            "bottom": "0",
            "zIndex": "20",
            "backgroundColor": HEAT_FOOTER_BG,
            "borderTop": "1px solid var(--alloq-border)",
        },
    )


def planning_heatmap() -> rx.Component:
    return rx.cond(
        PlanningGridState.is_loaded,
        mn.box(
            _heatmap_header(),
            mn.box(
                rx.foreach(PlanningGridState.employees, _heat_row),
            ),
            _heatmap_footer(),
            id="planning-heatmap-root",
            style={**GRID_WRAPPER_STYLE, "outline": "none"},
        ),
        mn.center(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Heatmap...", size="sm"),
                align="center",
                spacing="3",
            ),
            py="xl",
        ),
    )


_ = WEEK_COL_WIDTH  # re-export reference for column sizing (consumed by _row)
