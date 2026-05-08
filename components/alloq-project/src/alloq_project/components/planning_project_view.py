"""Planning Project view: projects as top-level collapsible rows."""

from __future__ import annotations

import reflex as rx
from alloq_project.components.planning_shared import (
    CELL_BASE,
    GRID_WRAPPER_STYLE,
    LABEL_CELL_BASE,
    STICKY_LEFT_BODY,
    STICKY_LEFT_EMP_HEADER,
    STICKY_LEFT_GESAMT,
    current_week_bg,
    editable_value_cell,
    format_gesamt,
    grid_row,
    header_block,
    key_div,
)
from alloq_project.states.planning_grid_state import (
    EmployeeAllocationRow,
    PlanningStore,
    ProjectBlock,
    ProjectGesamtCell,
)

import appkit_mantine as mn

PROJ_HEADER_BG = "var(--alloq-surface-hover)"


# ---------------------------------------------------------------------------
# Project header row
# ---------------------------------------------------------------------------


def _project_header_row(proj: ProjectBlock) -> rx.Component:
    """Collapsible project header with color indicator and name."""
    is_collapsed = PlanningStore.collapsed_projects.contains(proj.id)
    return grid_row(
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
                    proj.name,
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
                "borderBottom": "1px solid var(--alloq-border-strong)",
            },
        ),
        mn.box(
            "",
            style={
                **CELL_BASE,
                "gridColumn": "2 / -1",
                "backgroundColor": PROJ_HEADER_BG,
                "borderTop": "1px solid var(--alloq-border-strong)",
                "borderBottom": "1px solid var(--alloq-border-strong)",
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


def _employee_row_view(emp: EmployeeAllocationRow) -> rx.Component:
    """One employee row within a project block."""
    return grid_row(
        _employee_label_cell(emp),
        rx.foreach(emp.cells, editable_value_cell),
    )


# ---------------------------------------------------------------------------
# Project Gesamt row
# ---------------------------------------------------------------------------


def _project_gesamt_cell(cell: ProjectGesamtCell) -> rx.Component:
    """Aggregate capacity cell at project level."""
    return mn.box(
        format_gesamt(cell.allocated),
        style={
            **CELL_BASE,
            "backgroundColor": current_week_bg(
                cell.week_key, "var(--alloq-surface-muted)"
            ),
            "color": "var(--alloq-text)",
            "fontWeight": "600",
            "fontSize": "11px",
        },
    )


def _project_gesamt_row(proj: ProjectBlock) -> rx.Component:
    """Gesamt row showing total allocated per week for a project."""
    return grid_row(
        mn.box(
            mn.text(
                "Gesamt (allokiert)",
                size="12px",
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
                header_block(),
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
