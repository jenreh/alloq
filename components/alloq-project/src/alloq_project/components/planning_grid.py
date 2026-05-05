"""Planning Grid view (Stage B: CSS Grid + inline editing)."""

from __future__ import annotations

import reflex as rx
from alloq_project.states.planning_grid_state import (
    LABEL_COL_PX,
    WEEK_COL_PX,
    EmployeeBlock,
    GesamtCell,
    GridCell,
    MonthSpan,
    PlanningGridState,
    ProjectAllocationRow,
    WeekColumn,
)
from reflex.event import EventHandler, key_event
from reflex_components_core.el.elements.typography import Div

import appkit_mantine as mn


class _KeyDiv(Div):
    """rx.el.div subclass that supports on_key_down."""

    on_key_down: EventHandler[key_event] = None


key_div = _KeyDiv.create

LABEL_COL_WIDTH = f"{LABEL_COL_PX}px"
WEEK_COL_WIDTH = f"{WEEK_COL_PX}px"
ROW_HEIGHT = "32px"
HEADER_ROW_HEIGHT = "30px"

GRID_WRAPPER_STYLE = {
    "backgroundColor": "var(--alloq-surface-solid)",
    "borderRadius": "var(--mantine-radius-sm)",
    "border": "1px solid var(--alloq-border)",
    "overflow": "auto",
    # "height": "calc(100vh - 232px)",
    # "maxWidth": "100%",
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

STICKY_LEFT_NETROW = {
    "position": "sticky",
    "left": "0",
    "zIndex": "40",
    "backgroundColor": "var(--alloq-surface-solid)",
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


def _row(*children: rx.Component, style: dict | None = None) -> rx.Component:
    return mn.box(
        *children,
        style={
            **ROW_STYLE_BASE,
            "gridTemplateColumns": PlanningGridState.grid_template_columns,
            "minWidth": PlanningGridState.table_width,
            "width": PlanningGridState.table_width,
            **(style or {}),
        },
    )


def _format_de(value: rx.Var[float] | float) -> rx.Component:
    return rx.cond(
        value == 0,
        mn.box(""),
        mn.number_formatter(
            value=value,
            decimal_scale=1,
            decimal_separator=",",
            thousand_separator=".",
        ),
    )


def _format_gesamt(value: rx.Var[float]) -> rx.Component:
    return mn.number_formatter(
        value=value,
        decimal_scale=1,
        fixed_decimal_scale=True,
        decimal_separator=",",
        thousand_separator=".",
    )


def _gesamt_bg(bucket: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        bucket,
        (
            "available",
            "light-dark(var(--mantine-color-green-1), rgba(64, 192, 87, 0.18))",
        ),
        (
            "balanced",
            "light-dark(var(--mantine-color-green-0), rgba(64, 192, 87, 0.10))",
        ),
        (
            "tight",
            "light-dark(var(--mantine-color-violet-1), rgba(151, 117, 250, 0.22))",
        ),
        (
            "over",
            "light-dark(var(--mantine-color-red-2), rgba(250, 82, 82, 0.28))",
        ),
        (
            "absent",
            "light-dark(var(--mantine-color-blue-1), rgba(34, 139, 230, 0.22))",
        ),
        "transparent",
    )


def _gesamt_color(bucket: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        bucket,
        (
            "over",
            "light-dark(var(--mantine-color-red-9), var(--mantine-color-red-3))",
        ),
        (
            "tight",
            "light-dark(var(--mantine-color-violet-9), var(--mantine-color-violet-3))",
        ),
        (
            "available",
            "light-dark(var(--mantine-color-green-9), var(--mantine-color-green-3))",
        ),
        (
            "balanced",
            "light-dark(var(--mantine-color-green-8), var(--mantine-color-green-4))",
        ),
        (
            "absent",
            "light-dark(var(--mantine-color-blue-9), var(--mantine-color-blue-3))",
        ),
        "var(--alloq-text)",
    )


# ---------------------------- Header ---------------------------------------


def _month_cell(month: MonthSpan) -> rx.Component:
    return mn.box(
        mn.text(month.label, size="sm", fw="700", c="var(--alloq-text)"),
        style={
            **CELL_BASE,
            "gridColumn": "span " + month.span.to_string(),
            "backgroundColor": "var(--alloq-accent-soft)",
            "fontWeight": "700",
            "justifyContent": "flex-start",
            "paddingLeft": "12px",
            "minHeight": HEADER_ROW_HEIGHT,
        },
    )


def _week_label_cell(week: WeekColumn) -> rx.Component:
    return mn.box(
        mn.text(week.label, size="xs", c="var(--alloq-text-muted)", fw="500"),
        style={
            **CELL_BASE,
            "minHeight": HEADER_ROW_HEIGHT,
            "backgroundColor": "var(--alloq-surface-muted)",
        },
    )


def _work_days_cell(week: WeekColumn) -> rx.Component:
    return mn.box(
        _format_de(week.work_days),
        style={
            **CELL_BASE,
            "minHeight": HEADER_ROW_HEIGHT,
            "backgroundColor": "var(--alloq-surface-muted)",
            "fontWeight": "500",
        },
    )


def _net_days_cell(week: WeekColumn) -> rx.Component:
    return mn.box(
        _format_de(week.net_days),
        style={
            **CELL_BASE,
            "minHeight": HEADER_ROW_HEIGHT,
            "backgroundColor": "var(--alloq-surface-solid)",
            "fontWeight": "500",
            "borderBottom": "2px solid var(--alloq-border-strong)",
        },
    )


def _label_th(text: str, *, accent: bool = False, last: bool = False) -> rx.Component:
    if accent:
        sticky = STICKY_LEFT_HEADER_TOP
    elif last:
        sticky = STICKY_LEFT_NETROW
    else:
        sticky = STICKY_LEFT_HEADER
    extra = {"borderBottom": "2px solid var(--alloq-border-strong)"} if last else {}
    return mn.box(
        mn.text(text, size="sm", fw="700", c="var(--alloq-text)"),
        style={
            **LABEL_CELL_BASE,
            **sticky,
            **extra,
            "minHeight": HEADER_ROW_HEIGHT,
        },
    )


def _header_block() -> rx.Component:
    return mn.box(
        _row(
            _label_th("Monat", accent=True),
            rx.foreach(PlanningGridState.month_spans, _month_cell),
        ),
        _row(
            _label_th("Woche"),
            rx.foreach(PlanningGridState.weeks, _week_label_cell),
        ),
        _row(
            _label_th("Arbeitstage (brutto)"),
            rx.foreach(PlanningGridState.weeks, _work_days_cell),
        ),
        _row(
            _label_th("Arbeitstage (excl. Meetings)", last=True),
            rx.foreach(PlanningGridState.weeks, _net_days_cell),
        ),
        style=HEADER_BLOCK_STYLE,
    )


# ---------------------------- Employee block --------------------------------


def _employee_header_row(emp: EmployeeBlock) -> rx.Component:
    is_collapsed = PlanningGridState.collapsed_employees.contains(emp.id)
    return _row(
        mn.box(
            mn.group(
                mn.action_icon(
                    rx.cond(
                        is_collapsed,
                        rx.icon("chevron-right", size=16, stroke_width=2),
                        rx.icon("chevron-down", size=16, stroke_width=2),
                    ),
                    variant="subtle",
                    color="gray",
                    size="sm",
                    on_click=PlanningGridState.toggle_employee(emp.id),
                ),
                mn.avatar(
                    name=emp.name,
                    color="var(--alloq-accent-strong)",
                    size="sm",
                    radius="xl",
                ),
                mn.text(emp.name, size="sm", fw="700", c="var(--alloq-text)"),
                mn.badge(
                    emp.role,
                    size="xs",
                    radius="sm",
                    variant="filled",
                    color="gray",
                    style={
                        "backgroundColor": emp.role_color,
                        "color": "var(--alloq-text)",
                        "textTransform": "none",
                        "fontWeight": "700",
                    },
                ),
                gap="sm",
                align="center",
                wrap="nowrap",
            ),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_EMP_HEADER,
                "borderTop": "1px solid var(--alloq-border-strong)",
                "borderBottom": "1px solid var(--alloq-border-strong)",
            },
        ),
        mn.box(
            "",
            style={
                **CELL_BASE,
                "gridColumn": "2 / -1",
                "backgroundColor": EMP_HEADER_BG,
                "borderTop": "1px solid var(--alloq-border-strong)",
                "borderBottom": "1px solid var(--alloq-border-strong)",
                "borderRight": "none",
            },
        ),
    )


def _project_label_cell(project: ProjectAllocationRow) -> rx.Component:
    return mn.box(
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
                c="var(--alloq-text)",
                truncate=True,
            ),
            gap="sm",
            align="center",
            wrap="nowrap",
        ),
        style={
            **LABEL_CELL_BASE,
            **STICKY_LEFT_BODY,
            "paddingLeft": "16px",
        },
    )


def _editor_input() -> rx.Component:
    return mn.text_input(
        default_value=PlanningGridState.draft_value,
        on_change=PlanningGridState.set_draft,
        on_blur=PlanningGridState.commit_edit,
        on_key_down=PlanningGridState.handle_key,
        size="xs",
        auto_focus=True,
        class_name="grid-editor",
        custom_attrs={"key": PlanningGridState.editing_cell},
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


def _project_value_cell(cell: GridCell) -> rx.Component:
    is_editing = PlanningGridState.editing_cell == cell.key
    is_active = PlanningGridState.active_cell == cell.key
    return mn.box(
        rx.cond(
            is_editing,
            _editor_input(),
            mn.box(
                _format_de(cell.value),
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
                on_click=PlanningGridState.start_edit(cell.key),
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
        },
    )


def _project_row_view(project: ProjectAllocationRow) -> rx.Component:
    return _row(
        _project_label_cell(project),
        rx.foreach(project.cells, _project_value_cell),
    )


def _absence_value_cell(cell: GridCell) -> rx.Component:
    return mn.box(
        rx.cond(
            cell.value > 0,
            mn.box(
                _format_de(cell.value),
                style={
                    "backgroundColor": (
                        "light-dark(var(--mantine-color-blue-1), "
                        "rgba(34, 139, 230, 0.22))"
                    ),
                    "color": (
                        "light-dark(var(--mantine-color-blue-9), "
                        "var(--mantine-color-blue-3))"
                    ),
                    "borderRadius": "4px",
                    "padding": "2px 6px",
                    "fontWeight": "500",
                    "minWidth": "26px",
                    "textAlign": "center",
                },
            ),
            mn.text("", size="sm"),
        ),
        style=CELL_BASE,
    )


def _absence_row(emp: EmployeeBlock) -> rx.Component:
    return _row(
        mn.box(
            mn.group(
                mn.box(
                    style={
                        "width": "4px",
                        "height": "20px",
                        "borderRadius": "2px",
                        "backgroundColor": "var(--mantine-color-blue-4)",
                        "flexShrink": "0",
                    },
                ),
                mn.text("Abwesenheit", size="sm", c="var(--alloq-text-muted)"),
                gap="sm",
                align="center",
                wrap="nowrap",
            ),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_BODY,
                "paddingLeft": "16px",
            },
        ),
        rx.foreach(emp.absence.cells, _absence_value_cell),
    )


def _gesamt_value_cell(cell: GesamtCell) -> rx.Component:
    return mn.box(
        _format_gesamt(cell.value),
        style={
            **CELL_BASE,
            "backgroundColor": _gesamt_bg(cell.bucket),
            "color": _gesamt_color(cell.bucket),
            "fontWeight": "600",
        },
    )


def _gesamt_row(emp: EmployeeBlock) -> rx.Component:
    return _row(
        mn.box(
            mn.text("Gesamt (frei)", size="sm", fw="700", c="var(--alloq-text)"),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_GESAMT,
            },
        ),
        rx.foreach(emp.gesamt, _gesamt_value_cell),
    )


def _employee_block(emp: EmployeeBlock) -> rx.Component:
    is_collapsed = PlanningGridState.collapsed_employees.contains(emp.id)
    return mn.box(
        _employee_header_row(emp),
        rx.cond(
            ~is_collapsed,
            mn.box(
                rx.foreach(emp.projects, _project_row_view),
                _absence_row(emp),
                _gesamt_row(emp),
            ),
            rx.fragment(),
        ),
    )


def planning_grid() -> rx.Component:
    return rx.cond(
        PlanningGridState.is_loaded,
        key_div(
            _header_block(),
            mn.box(
                rx.foreach(PlanningGridState.employees, _employee_block),
            ),
            id="planning-grid-root",
            style={
                **GRID_WRAPPER_STYLE,
                "outline": "none",
                # "width": PlanningGridState.table_width,
            },
            tab_index=0,
            on_key_down=PlanningGridState.handle_grid_key,
        ),
        mn.center(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Planung...", size="sm"),
                align="center",
                spacing="3",
            ),
            py="xl",
        ),
    )
