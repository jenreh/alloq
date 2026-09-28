"""Shared constants, styles, and components for planning grid views."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.excel_grid import excel_grid, grid_cell_attrs
from alloq_commons.components.formatters import de_number
from alloq_project.states.planning_grid_state import (
    LABEL_COL_PX,
    WEEK_COL_PX,
    GridCell,
    MonthSpan,
    PlanningStore,
    WeekColumn,
)
from reflex.vars import ObjectVar

import appkit_mantine as mn

# ---------------------------------------------------------------------------
# Dimension constants
# ---------------------------------------------------------------------------

LABEL_COL_WIDTH = f"{LABEL_COL_PX}px"
WEEK_COL_WIDTH = f"{WEEK_COL_PX}px"
ROW_HEIGHT = "32px"
HEADER_ROW_HEIGHT = "30px"

CURRENT_WEEK_BG = "light-dark(rgba(255, 212, 59, 0.16), rgba(255, 212, 59, 0.08))"

# ---------------------------------------------------------------------------
# Style dictionaries
# ---------------------------------------------------------------------------

GRID_WRAPPER_STYLE = {
    "backgroundColor": "var(--alloq-surface-solid)",
    "borderRadius": "var(--mantine-radius-sm)",
    "border": "1px solid var(--alloq-border)",
    "overflow": "auto",
    "position": "fixed",
    "left": "9.3rem",
    "right": "2rem",
    "top": "12rem",
    "bottom": "32px",
}

ROW_STYLE_BASE = {
    "display": "grid",
    "alignItems": "stretch",
}

CELL_BASE = {
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "padding": "0 4px",
    "fontSize": "0.8125rem",
    "color": "var(--alloq-text)",
    "borderRight": "1px solid var(--alloq-border)",
    "borderBottom": "1px solid var(--alloq-border)",
    "minHeight": ROW_HEIGHT,
    "fontVariantNumeric": "tabular-nums",
}

LABEL_CELL_BASE = {
    **CELL_BASE,
    "justifyContent": "flex-start",
    "padding": "0 12px",
    "minWidth": LABEL_COL_WIDTH,
    "width": LABEL_COL_WIDTH,
}

STICKY_LEFT_BODY = {
    "position": "sticky",
    "left": "0",
    "zIndex": "2",
    "backgroundColor": "var(--alloq-surface-solid)",
}

STICKY_LEFT_HEADER_TOP = {
    "position": "sticky",
    "left": "0",
    "zIndex": "40",
    "backgroundColor": "var(--alloq-accent-soft)",
}

STICKY_LEFT_HEADER = {
    "position": "sticky",
    "left": "0",
    "zIndex": "40",
    "backgroundColor": "var(--alloq-surface-muted)",
}

STICKY_LEFT_GESAMT = {
    "position": "sticky",
    "left": "0",
    "zIndex": "2",
    "backgroundColor": "var(--alloq-surface-muted)",
}

STICKY_LEFT_EMP_HEADER = {
    "position": "sticky",
    "left": "0",
    "zIndex": "2",
    "backgroundColor": "var(--alloq-surface-hover)",
}

HEADER_BLOCK_STYLE = {
    "position": "sticky",
    "top": "0",
    "zIndex": "30",
    "backgroundColor": "var(--alloq-surface-muted)",
}

EMP_HEADER_BG = "var(--alloq-surface-hover)"
GESAMT_BG = "var(--alloq-surface-muted)"

# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------


def current_week_bg(
    week_key: rx.Var[str], fallback: str = "transparent"
) -> rx.Var[str]:
    """Return background color highlighting the current week."""
    return rx.cond(
        week_key == PlanningStore.current_week_key, CURRENT_WEEK_BG, fallback
    )


def grid_row(
    *children: rx.Component,
    style: dict | None = None,
    attrs: dict | None = None,
) -> rx.Component:
    """A single CSS grid row bound to PlanningStore columns."""
    return mn.box(
        *children,
        custom_attrs=attrs or {},
        style={
            **ROW_STYLE_BASE,
            "gridTemplateColumns": PlanningStore.grid_template_columns,
            "minWidth": PlanningStore.table_width,
            "width": PlanningStore.table_width,
            **(style or {}),
        },
    )


def format_de(value: rx.Var[float] | float) -> rx.Component:
    """Format a number in German locale; show blank for zero."""
    return rx.cond(
        value == 0,
        mn.box(""),
        de_number(
            value=value,
            decimal_scale=2,
            minimum_fraction_digits=2,
            fixed_decimal_scale=True,
        ),
    )


def format_gesamt(value: rx.Var[float]) -> rx.Component:
    """Format a Gesamt (total) number — always displayed."""
    return de_number(
        value=value,
        decimal_scale=2,
        minimum_fraction_digits=2,
        fixed_decimal_scale=True,
    )


# ---------------------------------------------------------------------------
# Block header info (pinned beside the label column)
# ---------------------------------------------------------------------------

SUMMARY_TOOLTIP = "Ab der aktuellen Woche bis zum Ende des Zeitraums"


def summary_stat(label: str, value: rx.Var[float]) -> rx.Component:
    """Muted label followed by a person-day figure."""
    return mn.group(
        mn.text(label, size="xs", c="var(--alloq-text-muted)"),
        de_number(
            value=value,
            decimal_scale=2,
            fixed_decimal_scale=True,
            suffix=" PT",
            size="xs",
            fw="600",
            c="var(--alloq-text)",
        ),
        gap="4px",
        align="center",
        wrap="nowrap",
    )


def block_header_info_cell(*children: rx.Component, background: str) -> rx.Component:
    """Week-column part of a block header; its content stays horizontally pinned."""
    return mn.box(
        mn.tooltip(
            mn.group(
                *children,
                gap="md",
                align="center",
                wrap="nowrap",
                style={
                    "position": "sticky",
                    "left": LABEL_COL_WIDTH,
                    "padding": "0 12px",
                },
            ),
            label=SUMMARY_TOOLTIP,
            open_delay=400,
        ),
        style={
            **CELL_BASE,
            "gridColumn": "2 / -1",
            "justifyContent": "flex-start",
            "padding": "0",
            "backgroundColor": background,
            "borderTop": "1px solid var(--alloq-border-strong)",
            "borderBottom": "1px solid var(--alloq-border-strong)",
            "borderRight": "none",
        },
    )


# ---------------------------------------------------------------------------
# Shared header components
# ---------------------------------------------------------------------------


def month_cell(month: ObjectVar[MonthSpan]) -> rx.Component:
    """Header cell spanning one month."""
    return mn.box(
        mn.text(month.label, fz="11px", fw="700", c="var(--alloq-text)"),
        style={
            **CELL_BASE,
            "gridColumn": "span " + month.span.to_string(),
            "backgroundColor": "var(--alloq-accent-soft)",
            "fontWeight": "500",
            "justifyContent": "flex-start",
            "paddingLeft": "12px",
            "minHeight": HEADER_ROW_HEIGHT,
        },
    )


def week_label_cell(week: ObjectVar[WeekColumn]) -> rx.Component:
    """Header cell for a week number."""
    return mn.box(
        mn.text(week.label, fz="11px", c="var(--alloq-text-muted)", fw="500"),
        style={
            **CELL_BASE,
            "minHeight": HEADER_ROW_HEIGHT,
            "backgroundColor": current_week_bg(week.key, "var(--alloq-surface-muted)"),
            "fontWeight": "500",
        },
    )


def work_days_cell(week: ObjectVar[WeekColumn]) -> rx.Component:
    """Header cell showing work days per week."""
    return mn.box(
        format_de(week.work_days),
        style={
            **CELL_BASE,
            "minHeight": HEADER_ROW_HEIGHT,
            "backgroundColor": current_week_bg(week.key, "var(--alloq-surface-muted)"),
            "fontWeight": "500",
            "fontSize": "11px",
            "borderBottom": "2px solid var(--alloq-border-strong)",
        },
    )


def label_th(text: str, *, accent: bool = False, last: bool = False) -> rx.Component:
    """Sticky label header cell."""
    sticky = STICKY_LEFT_HEADER_TOP if accent else STICKY_LEFT_HEADER
    extra = {"borderBottom": "2px solid var(--alloq-border-strong)"} if last else {}
    return mn.box(
        mn.text(text, size="xs", fw="700", c="var(--alloq-text)"),
        style={
            **LABEL_CELL_BASE,
            **sticky,
            **extra,
            "minHeight": HEADER_ROW_HEIGHT,
        },
    )


def header_block() -> rx.Component:
    """Three-row header: months, weeks, work days."""
    return mn.box(
        grid_row(
            label_th("Monat", accent=True),
            rx.foreach(PlanningStore.month_spans, month_cell),
        ),
        grid_row(
            label_th("Woche"),
            rx.foreach(PlanningStore.weeks, week_label_cell),
        ),
        grid_row(
            label_th("Arbeitstage (brutto)", last=True),
            rx.foreach(PlanningStore.weeks, work_days_cell),
        ),
        style=HEADER_BLOCK_STYLE,
        custom_attrs={"data-grid-header": "true"},
    )


# ---------------------------------------------------------------------------
# Shared value cell (selection/editing handled by ExcelGrid)
# ---------------------------------------------------------------------------

GRID_ROOT_STYLE = {**GRID_WRAPPER_STYLE, "outline": "none"}


def planning_excel_grid(*children: rx.Component, grid_id: str) -> rx.Component:
    """Excel-like interaction layer bound to PlanningStore."""
    return excel_grid(
        *children,
        id=grid_id,
        grid_label="Kapazitätsplanung",
        revision=PlanningStore.grid_revision,
        dirty=PlanningStore.has_dirty,
        saving=PlanningStore.is_saving,
        min_value=0,
        decimals=2,
        invalid_message="Ungültige Zahl (≥ 0)",
        on_commit=PlanningStore.apply_cell_changes,
        on_reject=PlanningStore.notify_rejected,
        on_save=PlanningStore.save_grid,
        style=GRID_ROOT_STYLE,
    )


def editable_value_cell(cell: ObjectVar[GridCell]) -> rx.Component:
    """Display cell with dirty indicator; ExcelGrid handles interaction."""
    return mn.box(
        format_de(cell.value),
        rx.cond(
            cell.is_dirty,
            mn.box(
                style={
                    "position": "absolute",
                    "top": "3px",
                    "right": "3px",
                    "width": "5px",
                    "height": "5px",
                    "borderRadius": "50%",
                    "backgroundColor": "var(--mantine-color-orange-6)",
                },
            ),
            rx.fragment(),
        ),
        custom_attrs=grid_cell_attrs(cell.key, cell.week_key, cell.value),
        style={
            **CELL_BASE,
            "position": "relative",
            "cursor": "cell",
            "userSelect": "none",
            "backgroundColor": current_week_bg(cell.week_key),
            "_hover": {"backgroundColor": "var(--alloq-surface-hover)"},
        },
    )
