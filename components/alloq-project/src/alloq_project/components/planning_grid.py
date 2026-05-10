"""Planning Grid view (Stage B: CSS Grid + inline editing)."""

from __future__ import annotations

import reflex as rx
from alloq_commons.components.forms import section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from alloq_project.components.planning_shared import (
    CELL_BASE,
    CURRENT_WEEK_BG,
    EMP_HEADER_BG,
    GRID_WRAPPER_STYLE,
    LABEL_CELL_BASE,
    STICKY_LEFT_BODY,
    STICKY_LEFT_EMP_HEADER,
    STICKY_LEFT_GESAMT,
    current_week_bg,
    editable_value_cell,
    format_de,
    format_gesamt,
    grid_row,
    header_block,
    key_div,
)
from alloq_project.states.planning_grid_state import (
    EmployeeBlock,
    GesamtCell,
    GridCell,
    PlanningStore,
    ProjectAllocationRow,
)

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog

# ---------------------------------------------------------------------------
# Gesamt bucket styling (employee-specific)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Employee block
# ---------------------------------------------------------------------------


def _employee_header_row(emp: EmployeeBlock) -> rx.Component:
    is_collapsed = PlanningStore.collapsed_employees.contains(emp.id)
    return grid_row(
        mn.box(
            mn.group(
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
                        on_click=PlanningStore.toggle_employee(emp.id),
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
                mn.tooltip(
                    mn.action_icon(
                        rx.icon("plus", size=14, stroke_width=2),
                        variant="subtle",
                        color="gray",
                        size="xs",
                        on_click=PlanningStore.open_add_project_for_employee(emp.id),
                    ),
                    label="Projekt zuweisen",
                ),
                justify="space-between",
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
                project.name,
                size="sm",
                c="var(--alloq-text)",
                truncate=True,
                flex="1",
                style={"minWidth": 0},
            ),
            rx.cond(
                project.role_short != "",
                mn.badge(
                    project.role_short,
                    size="xs",
                    radius="sm",
                    variant="filled",
                    color="gray",
                    style={
                        "backgroundColor": project.role_color,
                        "color": "var(--alloq-text)",
                        "textTransform": "none",
                        "fontWeight": "700",
                        "flexShrink": "0",
                    },
                ),
                rx.fragment(),
            ),
            mn.tooltip(
                delete_dialog(
                    title="Projektzuweisung entfernen",
                    content=project.code + " — " + project.name,
                    on_click=PlanningStore.remove_project_from_employee_grid(
                        project.emp_id, project.real_project_id
                    ),
                    icon_button=True,
                    color="red",
                    size="xs",
                    variant="subtle",
                ),
                label="Projekt entfernen",
            ),
            gap="sm",
            align="center",
            justify="space-between",
            wrap="nowrap",
            w="100%",
        ),
        style={
            **LABEL_CELL_BASE,
            **STICKY_LEFT_BODY,
            "paddingLeft": "16px",
        },
    )


def _project_row_view(project: ProjectAllocationRow) -> rx.Component:
    return grid_row(
        _project_label_cell(project),
        rx.foreach(project.cells, editable_value_cell),
    )


def _absence_value_cell(cell: GridCell) -> rx.Component:
    return mn.box(
        rx.cond(
            cell.value > 0,
            mn.box(
                format_de(cell.value),
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
        style={**CELL_BASE, "backgroundColor": current_week_bg(cell.week_key)},
    )


def _absence_row(emp: EmployeeBlock) -> rx.Component:
    return grid_row(
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


def _internal_value_cell(cell: GridCell) -> rx.Component:
    return mn.box(
        rx.cond(
            cell.value > 0,
            mn.box(
                format_de(cell.value),
                style={
                    "backgroundColor": (
                        "light-dark(var(--mantine-color-orange-1), "
                        "rgba(255, 146, 43, 0.18))"
                    ),
                    "color": (
                        "light-dark(var(--mantine-color-orange-9), "
                        "var(--mantine-color-orange-3))"
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
        style={**CELL_BASE, "backgroundColor": current_week_bg(cell.week_key)},
    )


def _internal_row(emp: EmployeeBlock) -> rx.Component:
    return grid_row(
        mn.box(
            mn.group(
                mn.box(
                    style={
                        "width": "4px",
                        "height": "20px",
                        "borderRadius": "2px",
                        "backgroundColor": "var(--mantine-color-orange-4)",
                        "flexShrink": "0",
                    },
                ),
                mn.text("Interne Projekte", size="sm", c="var(--alloq-text-muted)"),
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
        rx.foreach(emp.internal.cells, _internal_value_cell),
    )


def _gesamt_value_cell(cell: GesamtCell) -> rx.Component:
    is_current = cell.week_key == PlanningStore.current_week_key
    return mn.box(
        format_gesamt(cell.value),
        style={
            **CELL_BASE,
            "backgroundColor": _gesamt_bg(cell.bucket),
            "backgroundImage": rx.cond(
                is_current,
                f"linear-gradient({CURRENT_WEEK_BG}, {CURRENT_WEEK_BG})",
                "none",
            ),
            "color": _gesamt_color(cell.bucket),
            "fontWeight": "600",
        },
    )


def _gesamt_row(emp: EmployeeBlock) -> rx.Component:
    return grid_row(
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
    is_collapsed = PlanningStore.collapsed_employees.contains(emp.id)
    return mn.box(
        _employee_header_row(emp),
        rx.cond(
            ~is_collapsed,
            mn.box(
                rx.foreach(emp.projects, _project_row_view),
                _internal_row(emp),
                _absence_row(emp),
                _gesamt_row(emp),
            ),
            rx.fragment(),
        ),
    )


# ---------------------------------------------------------------------------
# Add project modal
# ---------------------------------------------------------------------------


def _add_project_modal() -> rx.Component:
    """Modal to assign a project to an employee from the grid."""
    return mn.modal(
        modal_form_layout(
            content=mn.flex(
                section(
                    mn.select(
                        name="project_id",
                        label="Projekt",
                        data=PlanningStore.add_project_options,
                        required=True,
                        searchable=True,
                        clearable=True,
                        left_section=rx.icon("folder", size=16),
                    ),
                    mn.select(
                        name="role_id",
                        label="Rolle",
                        data=PlanningStore.add_project_role_options,
                        required=True,
                        searchable=True,
                        clearable=True,
                        left_section=rx.icon("shield", size=16),
                    ),
                ),
                mn.space(height="2rem"),
                direction="column",
                gap="md",
                width="100%",
            ),
            footer=modal_footer(
                "Zuweisen",
                PlanningStore.close_add_project_for_employee,
            ),
            on_submit=PlanningStore.add_project_to_employee_grid,
            reset_on_submit=True,
        ),
        title="Projekt zuweisen",
        opened=PlanningStore.add_project_emp_id != "",
        on_close=PlanningStore.close_add_project_for_employee,
        size="md",
        centered=True,
        z_index=300,
        class_name=MODAL_CLASS,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


# ---------------------------------------------------------------------------
# Main component
# ---------------------------------------------------------------------------


def planning_grid() -> rx.Component:
    return rx.fragment(
        _add_project_modal(),
        rx.script(src="/planning_grid_keys.js"),
        rx.cond(
            PlanningStore.is_loaded,
            key_div(
                header_block(),
                mn.box(
                    rx.foreach(PlanningStore.filtered_employees, _employee_block),
                ),
                id="planning-grid-root",
                style={
                    **GRID_WRAPPER_STYLE,
                    "outline": "none",
                },
                tab_index=0,
                on_key_down=PlanningStore.handle_grid_key,
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
        ),
    )
