"""Shared constants, styles, and components for planning grid views."""

from __future__ import annotations

from collections.abc import Sequence

import reflex as rx
from alloq_commons.access import CAN_EDIT
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
MONTH_ROW_HEIGHT = "28px"
WEEK_ROW_HEIGHT = "36px"
HEADER_ROW_LINE = "1px solid var(--alloq-border)"
HEADER_BOTTOM_LINE = "2px solid var(--alloq-border-strong)"
NUMERIC = {"fontVariantNumeric": "tabular-nums", "whiteSpace": "nowrap"}

CURRENT_WEEK_BG = "var(--aq-now)"
HOLIDAY_BG = "light-dark(rgba(214, 140, 0, 0.16), rgba(227, 174, 82, 0.2))"
HOLIDAY_IMAGE = "var(--aq-holidays, none)"
"""Holiday day bands of a week cell; ``--aq-holidays`` is set per cell."""
HOLIDAY_DOT = {
    "width": "5px",
    "height": "5px",
    "borderRadius": "50%",
    "backgroundColor": "var(--aq-warning)",
}
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

VIEW_COLUMN_STYLE = {
    "display": "flex",
    "flexDirection": "column",
    "flex": "1",
    "minHeight": "0",
    "width": "100%",
}
"""Stacks a scrolling view above its legend footer."""

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

STICKY_BLOCK_HEADER = sticky_block_header("64px")

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
    """Current-week background, holiday bands and month separator of a week cell.

    The bands are the cell's background, so the cell editor covers them.
    """
    return {
        "backgroundColor": current_week_bg(week_key, fallback),
        "--aq-holidays": PlanningStore.holiday_backgrounds[week_key],
        "backgroundImage": HOLIDAY_IMAGE,
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
        "--aq-holiday": HOLIDAY_BG,
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
# Legend footer
# ---------------------------------------------------------------------------

DIRTY_DOT_COLOR = "var(--mantine-color-orange-6)"
EDIT_HINT = "Tippen zum Bearbeiten · ⌘S speichert"
CELL_SWATCH = {
    "width": "18px",
    "height": "14px",
    "borderRadius": "3px",
    "boxShadow": "inset 0 0 0 1px var(--aq-border)",
}


def legend_item(swatch: dict | rx.Component, label: str) -> rx.Component:
    """Small sample (a styled box or any component) followed by its label."""
    sample = (
        swatch
        if isinstance(swatch, rx.Component)
        else mn.box(style={"width": "18px", "height": "10px", **swatch})
    )
    return mn.group(
        sample,
        mn.text(label, fz="12px", c="var(--aq-text-muted)"),
        gap=6,
        wrap="nowrap",
    )


def legend_footer(*items: rx.Component, hint: str) -> rx.Component:
    """Bottom row below a planning view: legend items left, hint right."""
    return mn.box(
        mn.group(
            *items,
            mn.text(hint, fz="12px", c="var(--aq-text-tertiary)", ml="auto"),
            gap="md",
        ),
        px=16,
        py=10,
        style={"borderTop": "1px solid var(--aq-separator)", "flexShrink": "0"},
    )


def week_legend_items() -> list[rx.Component]:
    """Legend items for the week cells shared by the team and project view."""
    return [
        legend_item(
            {**CELL_SWATCH, "backgroundColor": CURRENT_WEEK_BG}, "Aktuelle Woche"
        ),
        legend_item({**CELL_SWATCH, "backgroundColor": HOLIDAY_BG}, "Feiertag"),
        legend_item(
            mn.text("1,00", fz="11px", c=REPEAT_COLOR, style={"lineHeight": "1"}),
            "Wie Vorwoche",
        ),
        legend_item(
            {
                "width": "6px",
                "height": "6px",
                "borderRadius": "50%",
                "backgroundColor": DIRTY_DOT_COLOR,
            },
            "Ungespeichert",
        ),
    ]


# ---------------------------------------------------------------------------
# Shared header components
# ---------------------------------------------------------------------------


def month_head(
    label: rx.Var[str], separator: rx.Var[str] | str, style: dict
) -> rx.Component:
    """Month label of the timeline header, shared by all planning views."""
    return mn.box(
        mn.text(label, fz="12px", fw="650", truncate=True),
        style={
            "boxSizing": "border-box",
            "display": "flex",
            "alignItems": "center",
            "padding": "0 10px",
            "borderLeft": separator,
            **style,
        },
    )


def week_head(
    *,
    kw: rx.Var[int],
    label: rx.Var[str],
    title: rx.Var[str],
    is_current: rx.Var[bool],
    is_month_start: rx.Var[bool],
    has_holiday: rx.Var[bool],
    style: dict,
) -> rx.Component:
    """Week cell of the timeline header (KW, start date, holiday dot)."""
    return mn.box(
        mn.text(
            "KW ",
            kw,
            fz="11px",
            fw="650",
            c=rx.cond(is_current, "var(--aq-warning)", "var(--aq-text)"),
            style=NUMERIC,
        ),
        mn.group(
            mn.text(label, fz="10.5px", c="var(--aq-text-muted)", style=NUMERIC),
            rx.cond(has_holiday, mn.box(style=HOLIDAY_DOT)),
            gap=3,
            wrap="nowrap",
        ),
        custom_attrs={"title": title},
        style={
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "gap": "1px",
            "boxSizing": "border-box",
            "borderLeft": rx.cond(
                is_month_start, MONTH_START_BORDER, "1px solid var(--aq-separator)"
            ),
            "backgroundColor": rx.cond(is_current, CURRENT_WEEK_BG, "transparent"),
            **style,
        },
    )


def month_cell(
    month: ObjectVar[MonthSpan], index: NumberVar | None = None
) -> rx.Component:
    """Grid header cell spanning one month; later months get a separator line."""
    return month_head(
        month.label,
        "none" if index is None else rx.cond(index > 0, MONTH_START_BORDER, "none"),
        {
            "gridColumn": "span " + month.span.to_string(),
            "position": "relative",
            "zIndex": "0",
        },
    )


def week_label_cell(week: ObjectVar[WeekColumn]) -> rx.Component:
    """Grid header cell for a week, like the absence timeline."""
    return week_head(
        kw=week.week_no,
        label=week.label,
        title=week.title,
        is_current=week.key == PlanningStore.current_week_key,
        is_month_start=week.is_month_start,
        has_holiday=week.is_short,
        style={"position": "relative", "zIndex": "0"},
    )


def label_th(text: rx.Var[str] | str) -> rx.Component:
    """Sticky label header cell."""
    return mn.box(
        mn.text(text, fz="12.5px", fw="650", c="var(--alloq-text)"),
        style={
            **LABEL_CELL_BASE,
            **STICKY_LEFT_HEADER,
            "borderBottom": "none",
            "minHeight": "0",
        },
    )


def header_block(title: str, count: rx.Var[str]) -> rx.Component:
    """Two-row timeline header (months, weeks) as in the absence view."""
    return mn.box(
        grid_row(
            label_th(title),
            rx.foreach(PlanningStore.month_spans, month_cell),
            style={"height": MONTH_ROW_HEIGHT, "borderBottom": HEADER_ROW_LINE},
        ),
        grid_row(
            label_th(count),
            rx.foreach(PlanningStore.weeks, week_label_cell),
            style={"height": WEEK_ROW_HEIGHT, "borderBottom": HEADER_BOTTOM_LINE},
        ),
        # As wide as the rows, so the background reaches the last week.
        style={**HEADER_BLOCK_STYLE, "width": PlanningStore.table_width},
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
        read_only=~CAN_EDIT,
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
                    "backgroundColor": DIRTY_DOT_COLOR,
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
