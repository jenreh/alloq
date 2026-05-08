"""Shared constants, styles, and components for planning grid views."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.formatters import de_number
from alloq_project.states.planning_grid_state import (
    LABEL_COL_PX,
    WEEK_COL_PX,
    GridCell,
    MonthSpan,
    PlanningStore,
    WeekColumn,
)
from reflex.event import EventHandler, key_event
from reflex_components_core.el.elements.typography import Div

import appkit_mantine as mn

# ---------------------------------------------------------------------------
# KeyDiv — shared key-event capable div
# ---------------------------------------------------------------------------


class KeyDiv(Div):
    """rx.el.div subclass that supports on_key_down."""

    on_key_down: EventHandler[key_event] = None


key_div = KeyDiv.create

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


def grid_row(*children: rx.Component, style: dict | None = None) -> rx.Component:
    """A single CSS grid row bound to PlanningStore columns."""
    return mn.box(
        *children,
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
# Shared header components
# ---------------------------------------------------------------------------


def month_cell(month: MonthSpan) -> rx.Component:
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


def week_label_cell(week: WeekColumn) -> rx.Component:
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


def work_days_cell(week: WeekColumn) -> rx.Component:
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
    )


# ---------------------------------------------------------------------------
# Shared editor input
# ---------------------------------------------------------------------------


def editor_input() -> rx.Component:
    """Inline editor input used in both grid views."""
    return mn.text_input(
        default_value=PlanningStore.draft_value,
        on_change=PlanningStore.set_draft,
        on_blur=PlanningStore.commit_edit,
        on_key_down=PlanningStore.handle_key,
        size="xs",
        auto_focus=True,
        class_name="grid-editor",
        custom_attrs={"key": PlanningStore.editing_cell},
        style={
            "width": "100%",
            "& input": {
                "height": ROW_HEIGHT,
                "minHeight": ROW_HEIGHT,
                "padding": "0 4px",
                "textAlign": "center",
                "fontSize": "0.8125rem",
                "border": "2px solid var(--mantine-color-blue-5)",
                "borderRadius": "0",
                "backgroundColor": "var(--alloq-surface-solid)",
                "color": "var(--alloq-text)",
            },
        },
    )


# ---------------------------------------------------------------------------
# Shared value cell with editing support
# ---------------------------------------------------------------------------


def editable_value_cell(cell: GridCell) -> rx.Component:
    """Value cell with click-to-edit, dirty indicator, and active highlight."""
    is_editing = PlanningStore.editing_cell == cell.key
    is_active = PlanningStore.active_cell == cell.key
    return mn.box(
        rx.cond(
            is_editing,
            editor_input(),
            mn.box(
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
                on_click=PlanningStore.start_edit(cell.key),
                style={
                    "width": "100%",
                    "height": "100%",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "cursor": "pointer",
                    "position": "relative",
                    "boxShadow": rx.cond(
                        is_active,
                        "inset 0 0 0 2px var(--mantine-color-blue-5)",
                        "none",
                    ),
                    "_hover": {
                        "backgroundColor": "var(--alloq-surface-hover)",
                    },
                },
            ),
        ),
        style={
            **CELL_BASE,
            "padding": "0",
            "position": "relative",
            "backgroundColor": current_week_bg(cell.week_key),
        },
        custom_attrs={"data-active-cell": rx.cond(is_active, "true", "false")},
    )
