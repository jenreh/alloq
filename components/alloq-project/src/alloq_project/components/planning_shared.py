"""Shared constants, styles, and components for planning grid views."""

from __future__ import annotations

from collections.abc import Sequence

import reflex as rx
from alloq_commons.components.excel_grid import excel_grid, grid_cell_attrs
from alloq_commons.components.formatters import de_number
from alloq_commons.components.list_view import sticky_block_header
from alloq_project.states.planning_grid_state import (
    LABEL_COL_PX,
    WEEK_COL_PX,
    GridCell,
    MonthSpan,
    PlanningStore,
    WeekColumn,
)
from reflex.vars import NumberVar, ObjectVar

import appkit_mantine as mn

# ---------------------------------------------------------------------------
# Dimension constants
# ---------------------------------------------------------------------------

LABEL_COL_WIDTH = f"{LABEL_COL_PX}px"
WEEK_COL_WIDTH = f"{WEEK_COL_PX}px"
ROW_HEIGHT = "var(--aq-grid-row, 32px)"
BLOCK_GAP = "var(--aq-grid-gap, 8px)"
ROW_LABEL_FONT_SIZE = "var(--aq-grid-label-fs)"
HEADER_ROW_HEIGHT = "30px"
MONTH_HEADER_BG = "light-dark(var(--mantine-color-blue-0), var(--mantine-color-blue-9))"

CURRENT_WEEK_BG = "var(--aq-now)"
SHORT_WEEK_BG = "light-dark(rgba(245, 189, 61, 0.3), rgba(245, 189, 61, 0.2))"
MONTH_START_BORDER = "1px solid var(--alloq-border-strong)"
REPEAT_COLOR = "var(--alloq-text-muted)"

# ---------------------------------------------------------------------------
# Style dictionaries
# ---------------------------------------------------------------------------

GRID_WRAPPER_STYLE = {
    "backgroundColor": "var(--aq-surface)",
    "overflow": "auto",
    "flex": "1",
    "minHeight": "0",
    "width": "100%",
}
"""Fills the content pane below the scope bar and scrolls both ways."""

ROW_STYLE_BASE = {
    "display": "grid",
    "alignItems": "stretch",
}

CELL_BASE = {
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "flex-end",
    "padding": "0 8px",
    "fontSize": "var(--aq-grid-fs, 0.8125rem)",
    "color": "var(--alloq-text)",
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
    "borderRight": MONTH_START_BORDER,
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
    "zIndex": "50",
    "backgroundColor": MONTH_HEADER_BG,
}

STICKY_LEFT_HEADER = {
    "position": "sticky",
    "left": "0",
    "zIndex": "50",
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

STICKY_BLOCK_HEADER = sticky_block_header("90px")

HEADER_BLOCK_STYLE = {
    "position": "sticky",
    "top": "0",
    "zIndex": "30",
    "backgroundColor": "var(--alloq-surface-muted)",
}

EMP_HEADER_BG = "var(--alloq-surface-hover)"

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


def week_cell_style(
    week_key: rx.Var[str], fallback: str = "transparent"
) -> dict[str, rx.Var[str]]:
    """Current-week background and month separator for a week column cell."""
    return {
        "backgroundColor": current_week_bg(week_key, fallback),
        "borderLeft": rx.cond(
            PlanningStore.month_start_keys.contains(week_key),
            MONTH_START_BORDER,
            "none",
        ),
    }


def grid_density_vars() -> dict[str, rx.Var[str]]:
    """CSS variables for row height, font sizes and block gap of the density."""
    compact = PlanningStore.is_compact
    return {
        "--aq-grid-row": rx.cond(compact, "24px", "32px"),
        "--aq-grid-fs": rx.cond(compact, "12px", "0.8125rem"),
        "--aq-grid-label-fs": rx.cond(
            compact, "var(--aq-grid-fs)", "var(--mantine-font-size-sm)"
        ),
        "--aq-grid-gap": rx.cond(compact, "4px", "8px"),
    }


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


def empty_grid_row() -> rx.Component:
    """A small full-width gap between two blocks."""
    return grid_row(style={"height": BLOCK_GAP})


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
PINNED_END_STYLE = {"right": "0", "marginLeft": "auto"}


def summary_stat(
    label: str, value: rx.Var[float], color: str = "var(--alloq-text)"
) -> rx.Component:
    """Muted label followed by a person-day figure."""
    return mn.group(
        mn.text(label, size="xs", c="var(--alloq-text-muted)"),
        mn.text(
            de_number(
                value=value,
                decimal_scale=2,
                fixed_decimal_scale=True,
                suffix=" PT",
            ),
            size="xs",
            fw="600",
            c=color,
        ),
        gap="4px",
        align="center",
        wrap="nowrap",
    )


def _pinned_group(*children: rx.Component, style: dict) -> rx.Component:
    return mn.group(
        *children,
        gap="md",
        align="center",
        wrap="nowrap",
        style={"position": "sticky", "padding": "0 12px", **style},
    )


def _summary_tooltip(content: rx.Component) -> rx.Component:
    return mn.tooltip(content, label=SUMMARY_TOOLTIP, open_delay=400)


def block_header_info_cell(
    *children: rx.Component,
    background: str,
    end: Sequence[rx.Component] = (),
) -> rx.Component:
    """Week-column part of a block header; its content stays horizontally pinned.

    ``children`` pin to the left edge; ``end`` pins to the right edge of the row
    or, when the row is wider than the viewport, to the viewport's right edge.
    """
    start = _pinned_group(*children, style={"left": LABEL_COL_WIDTH})
    pinned = (
        [start, _summary_tooltip(_pinned_group(*end, style=PINNED_END_STYLE))]
        if end
        else [_summary_tooltip(start)]
    )
    return mn.box(
        *pinned,
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


def month_cell(
    month: ObjectVar[MonthSpan], index: NumberVar | None = None
) -> rx.Component:
    """Header cell spanning one month; later months get a separator line."""
    return mn.box(
        mn.text(month.label, fz="11px", fw="700", c="var(--alloq-text)"),
        style={
            **CELL_BASE,
            "gridColumn": "span " + month.span.to_string(),
            "position": "relative",
            "zIndex": "0",
            "backgroundColor": MONTH_HEADER_BG,
            "fontWeight": "500",
            "justifyContent": "flex-start",
            "paddingLeft": "12px",
            "minHeight": HEADER_ROW_HEIGHT,
            "borderLeft": (
                "none"
                if index is None
                else rx.cond(index > 0, MONTH_START_BORDER, "none")
            ),
        },
    )


def week_label_cell(week: ObjectVar[WeekColumn]) -> rx.Component:
    """Header cell for a week, right-aligned above the numbers."""
    return mn.box(
        mn.text(week.label, fz="11px", c="var(--alloq-text-muted)", fw="500"),
        style={
            **CELL_BASE,
            **week_cell_style(week.key, "var(--alloq-surface-muted)"),
            "position": "relative",
            "zIndex": "0",
            "minHeight": HEADER_ROW_HEIGHT,
            "fontWeight": "500",
        },
    )


def work_days_cell(week: ObjectVar[WeekColumn]) -> rx.Component:
    """Header cell showing work days, only for weeks shortened by holidays."""
    return mn.box(
        rx.cond(week.is_short, format_de(week.work_days), rx.fragment()),
        style={
            **CELL_BASE,
            **week_cell_style(week.key, "var(--alloq-surface-muted)"),
            "position": "relative",
            "zIndex": "0",
            "minHeight": HEADER_ROW_HEIGHT,
            "backgroundColor": rx.cond(
                week.is_short,
                SHORT_WEEK_BG,
                current_week_bg(week.key, "var(--alloq-surface-muted)"),
            ),
            "fontWeight": "600",
            "fontSize": "11px",
            "borderBottom": "2px solid var(--alloq-border-strong)",
        },
    )


def label_th(
    text: str, *, accent: bool = False, last: bool = False, hint: str = ""
) -> rx.Component:
    """Sticky label header cell with an optional muted hint."""
    sticky = STICKY_LEFT_HEADER_TOP if accent else STICKY_LEFT_HEADER
    extra = {"borderBottom": "2px solid var(--alloq-border-strong)"} if last else {}
    hint_text = [mn.text(hint, size="xs", c="var(--alloq-text-muted)")] if hint else []
    return mn.box(
        mn.text(text, size="xs", fw="700", c="var(--alloq-text)"),
        *hint_text,
        style={
            **LABEL_CELL_BASE,
            **sticky,
            **extra,
            "gap": "6px",
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
            label_th("Arbeitstage (brutto)", last=True, hint="leer = volle Woche"),
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
        style={**GRID_ROOT_STYLE, **grid_density_vars()},
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
            **week_cell_style(cell.week_key),
            "position": "relative",
            "cursor": "cell",
            "userSelect": "none",
            "color": rx.cond(cell.is_repeat, REPEAT_COLOR, "var(--alloq-text)"),
            "_hover": {"backgroundColor": "var(--alloq-surface-hover)"},
        },
    )
