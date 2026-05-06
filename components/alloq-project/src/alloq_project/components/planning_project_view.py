"""Planning Project view: projects as top-level collapsible rows."""

from __future__ import annotations

import reflex as rx
from alloq_project.components.planning_grid import (
    CELL_BASE,
    GRID_WRAPPER_STYLE,
    HEADER_BLOCK_STYLE,
    LABEL_CELL_BASE,
    ROW_HEIGHT,
    ROW_STYLE_BASE,
    STICKY_LEFT_BODY,
    STICKY_LEFT_EMP_HEADER,
    STICKY_LEFT_GESAMT,
    _format_de,
    _format_gesamt,
    _label_th,
    _month_cell,
    _week_label_cell,
    _work_days_cell,
)
from alloq_project.states.planning_grid_state import (
    EmployeeAllocationRow,
    GridCell,
    PlanningStore,
    ProjectBlock,
    ProjectGesamtCell,
)
from reflex.event import EventHandler, key_event
from reflex_components_core.el.elements.typography import Div

import appkit_mantine as mn


class _KeyDiv(Div):
    """rx.el.div subclass that supports on_key_down."""

    on_key_down: EventHandler[key_event] = None


key_div = _KeyDiv.create

# Project header row background
PROJ_HEADER_BG = "var(--alloq-surface-hover)"


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _prow(*children: rx.Component, style: dict | None = None) -> rx.Component:
    """Grid row using PlanningStore columns."""
    return mn.box(
        *children,
        style={
            **ROW_STYLE_BASE,
            "gridTemplateColumns": (PlanningStore.grid_template_columns),
            "minWidth": PlanningStore.table_width,
            "width": PlanningStore.table_width,
            **(style or {}),
        },
    )


# ---------------------------------------------------------------------------
# Header (reuses same structure as grid)
# ---------------------------------------------------------------------------


def _header_block() -> rx.Component:
    return mn.box(
        _prow(
            _label_th("Monat", accent=True),
            rx.foreach(PlanningStore.month_spans, _month_cell),
        ),
        _prow(
            _label_th("Woche"),
            rx.foreach(PlanningStore.weeks, _week_label_cell),
        ),
        _prow(
            _label_th("Arbeitstage (brutto)", last=True),
            rx.foreach(PlanningStore.weeks, _work_days_cell),
        ),
        style=HEADER_BLOCK_STYLE,
    )


# ---------------------------------------------------------------------------
# Project header row
# ---------------------------------------------------------------------------


def _project_header_row(proj: ProjectBlock) -> rx.Component:
    """Collapsible project header with color indicator and name."""
    is_collapsed = PlanningStore.collapsed_projects.contains(proj.id)
    return _prow(
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
                    on_click=PlanningStore.toggle_project(proj.id),
                ),
                mn.box(
                    style={
                        "width": "6px",
                        "height": "20px",
                        "borderRadius": "3px",
                        "backgroundColor": proj.color,
                        "flexShrink": "0",
                    },
                ),
                mn.text(
                    proj.code + " — " + proj.name,
                    size="sm",
                    fw="700",
                    c="var(--alloq-text)",
                    truncate=True,
                    flex="1",
                    style={"minWidth": 0},
                ),
                mn.badge(
                    proj.state,
                    size="xs",
                    radius="sm",
                    variant="light",
                    color="gray",
                ),
                gap="sm",
                align="center",
                wrap="nowrap",
                w="100%",
            ),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_EMP_HEADER,
                "borderTop": "1px solid var(--alloq-border-strong)",
                "borderBottom": ("1px solid var(--alloq-border-strong)"),
            },
        ),
        mn.box(
            "",
            style={
                **CELL_BASE,
                "gridColumn": "2 / -1",
                "backgroundColor": PROJ_HEADER_BG,
                "borderTop": "1px solid var(--alloq-border-strong)",
                "borderBottom": ("1px solid var(--alloq-border-strong)"),
                "borderRight": "none",
            },
        ),
    )


# ---------------------------------------------------------------------------
# Employee row (nested under project)
# ---------------------------------------------------------------------------


def _employee_label_cell(emp: EmployeeAllocationRow) -> rx.Component:
    """Label cell for an employee row under a project."""
    return mn.box(
        mn.group(
            mn.avatar(
                name=emp.name,
                color="var(--alloq-accent-strong)",
                size="xs",
                radius="xl",
            ),
            mn.text(
                emp.name,
                size="sm",
                c="var(--alloq-text)",
                truncate=True,
                flex="1",
                style={"minWidth": 0},
            ),
            rx.cond(
                emp.role_short != "",
                mn.badge(
                    emp.role_short,
                    size="xs",
                    radius="sm",
                    variant="filled",
                    color="gray",
                    style={
                        "backgroundColor": emp.role_color,
                        "color": "var(--alloq-text)",
                        "textTransform": "none",
                        "fontWeight": "700",
                        "flexShrink": "0",
                    },
                ),
                rx.fragment(),
            ),
            gap="sm",
            align="center",
            wrap="nowrap",
            w="100%",
        ),
        style={
            **LABEL_CELL_BASE,
            **STICKY_LEFT_BODY,
            "paddingLeft": "24px",
        },
    )


def _editor_input() -> rx.Component:
    """Inline editor for cell editing."""
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
                "border": ("2px solid var(--mantine-color-blue-5)"),
                "borderRadius": "0",
                "backgroundColor": "var(--alloq-surface-solid)",
                "color": "var(--alloq-text)",
            },
        },
    )


def _value_cell(cell: GridCell) -> rx.Component:
    """Editable value cell for project view."""
    is_editing = PlanningStore.editing_cell == cell.key
    is_active = PlanningStore.active_cell == cell.key
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
                            "backgroundColor": ("var(--mantine-color-orange-6)"),
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
                        "backgroundColor": ("var(--alloq-surface-hover)"),
                    },
                },
            ),
        ),
        style={
            **CELL_BASE,
            "padding": "0",
            "position": "relative",
        },
        custom_attrs={"data-active-cell": rx.cond(is_active, "true", "false")},
    )


def _employee_row_view(emp: EmployeeAllocationRow) -> rx.Component:
    """One employee row within a project block."""
    return _prow(
        _employee_label_cell(emp),
        rx.foreach(emp.cells, _value_cell),
    )


# ---------------------------------------------------------------------------
# Project Gesamt row
# ---------------------------------------------------------------------------


def _project_gesamt_cell(cell: ProjectGesamtCell) -> rx.Component:
    """Aggregate capacity cell at project level."""
    return mn.box(
        _format_gesamt(cell.allocated),
        style={
            **CELL_BASE,
            "backgroundColor": "var(--alloq-surface-muted)",
            "color": "var(--alloq-text)",
            "fontWeight": "600",
        },
    )


def _project_gesamt_row(proj: ProjectBlock) -> rx.Component:
    """Gesamt row showing total allocated per week for a project."""
    return _prow(
        mn.box(
            mn.text(
                "Gesamt (allokiert)",
                size="sm",
                fw="700",
                c="var(--alloq-text)",
            ),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_GESAMT,
                "paddingLeft": "24px",
            },
        ),
        rx.foreach(proj.gesamt, _project_gesamt_cell),
    )


# ---------------------------------------------------------------------------
# Project block (composed)
# ---------------------------------------------------------------------------


def _project_block(proj: ProjectBlock) -> rx.Component:
    """One project block with collapsible employee rows."""
    is_collapsed = PlanningStore.collapsed_projects.contains(proj.id)
    return mn.box(
        _project_header_row(proj),
        rx.cond(
            ~is_collapsed,
            mn.box(
                rx.foreach(proj.employees, _employee_row_view),
                _project_gesamt_row(proj),
            ),
            rx.fragment(),
        ),
    )


# ---------------------------------------------------------------------------
# Main component
# ---------------------------------------------------------------------------


def planning_project_view() -> rx.Component:
    """Main project-aggregated planning view component."""
    return rx.cond(
        PlanningStore.is_loaded,
        key_div(
            mn.box(
                _header_block(),
                rx.foreach(
                    PlanningStore.filtered_projects,
                    _project_block,
                ),
            ),
            id="project-view-root",
            tab_index=0,
            on_key_down=PlanningStore.handle_grid_key,
            style={
                **GRID_WRAPPER_STYLE,
                "outline": "none",
            },
        ),
        mn.center(
            rx.spinner(size="3"),
            h="300px",
        ),
    )
