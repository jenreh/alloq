"""Planning Grid view (CSS Grid + Excel-like editing via ExcelGrid)."""

from __future__ import annotations

from typing import Any

import reflex as rx
from alloq_commons.access import editor_only
from alloq_commons.components.dialogs import delete_dialog
from alloq_commons.components.excel_grid import grid_row_attrs
from alloq_commons.components.formatters import de_number, match_str
from alloq_commons.components.forms import quick_project_fields, section
from alloq_commons.components.modal_layout import (
    MODAL_CLASS,
    modal_footer,
    modal_form_layout,
)
from alloq_commons.role_colors import ROLE_BADGE_TEXT_COLOR
from alloq_project.components.planning_shared import (
    CELL_BASE,
    EDIT_HINT,
    EMP_HEADER_BG,
    HOLIDAY_IMAGE,
    LABEL_CELL_BASE,
    ROW_LABEL_FONT_SIZE,
    STICKY_BLOCK_HEADER,
    STICKY_LEFT_BODY,
    STICKY_LEFT_EMP_HEADER,
    STICKY_LEFT_GESAMT,
    VIEW_COLUMN_STYLE,
    block_header_info_cell,
    current_week_bg,
    editable_value_cell,
    empty_grid_row,
    format_de,
    format_gesamt,
    grid_row,
    header_block,
    legend_footer,
    legend_item,
    planning_excel_grid,
    summary_stat,
    week_cell_style,
    week_legend_items,
)
from alloq_project.states.planning_absence_state import PlanningAbsenceState
from alloq_project.states.planning_grid_state import (
    EmployeeBlock,
    GesamtCell,
    GridCell,
    PlanningStore,
    ProjectAllocationRow,
)
from alloq_team.components.employee import absence_modal
from alloq_team.states.team_state import TeamState
from reflex.vars import ObjectVar

import appkit_mantine as mn

# ---------------------------------------------------------------------------
# Gesamt bucket styling (employee-specific)
# ---------------------------------------------------------------------------


GESAMT_OVER_BG = "light-dark(var(--mantine-color-red-0), rgba(250, 82, 82, 0.18))"
ABSENCE_HATCH = (
    "repeating-linear-gradient(135deg, var(--alloq-border-strong) 0 1px,"
    " transparent 1px 6px)"
)
ABSENCE_DOT = {
    "position": "absolute",
    "top": "4px",
    "left": "5px",
    "width": "5px",
    "height": "5px",
    "borderRadius": "50%",
    "backgroundColor": "var(--alloq-text-muted)",
}
ROW_DELETE_CLASS = "aq-row-delete"
ROW_DELETE_ON_HOVER = {
    f"& .{ROW_DELETE_CLASS}": {"opacity": "0"},
    f"&:hover .{ROW_DELETE_CLASS}, & .{ROW_DELETE_CLASS}:focus-within": {
        "opacity": "1"
    },
}


FREE_COLOR = "light-dark(var(--mantine-color-green-7), var(--mantine-color-green-3))"
OVERBOOKED_LABEL = "Überbucht"


def _gesamt_color(state: rx.Var[str]) -> rx.Var[str]:
    """Free days colour: red when overbooked, muted when full, green when free."""
    return match_str(
        state,
        (
            "over",
            "light-dark(var(--mantine-color-red-7), var(--mantine-color-red-3))",
        ),
        ("zero", "var(--alloq-text-muted)"),
        FREE_COLOR,
    )


# ---------------------------------------------------------------------------
# Employee block
# ---------------------------------------------------------------------------


def _employee_header_row(emp: ObjectVar[EmployeeBlock]) -> rx.Component:
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
                        on_click=PlanningStore.toggle_employee(emp.id),  # ty: ignore[invalid-argument-type]
                    ),
                    mn.text(
                        emp.last_name + ", " + emp.first_name,
                        size="sm",
                        fw="700",
                        c="var(--alloq-text)",
                    ),
                    gap="sm",
                    align="center",
                    wrap="nowrap",
                ),
                de_number(
                    emp.hours_per_week,
                    suffix="h/W",
                    size="xs",
                    c="var(--alloq-text-muted)",
                    fw="400",
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
        rx.cond(
            is_collapsed,
            rx.foreach(emp.gesamt, _gesamt_value_cell),
            _employee_info_cell(emp),
        ),
        style=STICKY_BLOCK_HEADER,
    )


def _employee_info_cell(emp: ObjectVar[EmployeeBlock]) -> rx.Component:
    return block_header_info_cell(
        editor_only(
            mn.group(
                mn.tooltip(
                    mn.action_icon(
                        rx.icon("plus", size=14, stroke_width=2),
                        variant="subtle",
                        color="gray",
                        size="xs",
                        aria_label="Projekt zuweisen",
                        on_click=PlanningStore.open_add_project_for_employee(  # ty: ignore[invalid-argument-type]
                            emp.id,
                        ),
                    ),
                    label="Projekt zuweisen",
                ),
                mn.tooltip(
                    mn.action_icon(
                        rx.icon("calendar-plus", size=14, stroke_width=2),
                        variant="subtle",
                        color="gray",
                        size="xs",
                        aria_label="Abwesenheit eintragen",
                        on_click=TeamState.select_employee_and_add_absence(  # ty: ignore[invalid-argument-type]
                            emp.real_id,
                        ),
                    ),
                    label="Abwesenheit eintragen",
                ),
                gap="xs",
                wrap="nowrap",
            ),
        ),
        background=EMP_HEADER_BG,
        end=[summary_stat("Frei", emp.available_days, color=FREE_COLOR)],
    )


def _project_label_cell(project: ObjectVar[ProjectAllocationRow]) -> rx.Component:
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
                size=ROW_LABEL_FONT_SIZE,
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
                    color=project.role_color,
                    c=ROLE_BADGE_TEXT_COLOR,
                    fw="700",
                ),
                rx.fragment(),
            ),
            editor_only(
                mn.box(
                    mn.tooltip(
                        delete_dialog(
                            title="Projektzuweisung entfernen",
                            content=f"{project.code} — {project.name}",
                            on_click=PlanningStore.remove_project_from_employee_grid(  # ty: ignore[invalid-argument-type]
                                project.emp_id, project.real_project_id
                            ),
                            icon_button=True,
                            color="red",
                            size="xs",
                            variant="subtle",
                        ),
                        label="Projekt entfernen",
                    ),
                    class_name=ROW_DELETE_CLASS,
                    display="flex",
                ),
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


def _project_row_view(project: ObjectVar[ProjectAllocationRow]) -> rx.Component:
    return grid_row(
        _project_label_cell(project),
        rx.foreach(project.cells, editable_value_cell),
        attrs=grid_row_attrs(f"{project.emp_id}|{project.code}", project.emp_id),
        style=ROW_DELETE_ON_HOVER,
    )


def _absence_value_cell(cell: ObjectVar[GridCell]) -> rx.Component:
    has_absence = cell.value.to(float) > 0
    return mn.box(
        rx.cond(
            has_absence,
            mn.text(
                format_de(cell.value),
                size="xs",
                c="var(--alloq-text-muted)",
            ),
            mn.text("", size="xs"),
        ),
        style={
            **CELL_BASE,
            **week_cell_style(cell.week_key),
            "color": "var(--alloq-text-muted)",
            "backgroundImage": rx.cond(
                has_absence, f"{ABSENCE_HATCH}, {HOLIDAY_IMAGE}", HOLIDAY_IMAGE
            ),
        },
    )


def _absence_row(emp: ObjectVar[EmployeeBlock]) -> rx.Component:
    return grid_row(
        mn.box(
            mn.text("Abwesenheit", size="xs", c="var(--alloq-text-muted)"),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_BODY,
                "paddingLeft": "16px",
            },
        ),
        rx.foreach(emp.absence.cells, _absence_value_cell),
    )


def _internal_value_cell(cell: ObjectVar[GridCell]) -> rx.Component:
    """Internal days, shown only where they differ from the usual value."""
    return mn.box(
        rx.cond(
            (cell.value.to(float) > 0) & ~cell.is_default,
            mn.text(
                format_de(cell.value),
                size="xs",
                c="var(--alloq-text-muted)",
            ),
            mn.text("", size="xs"),
        ),
        style={
            **CELL_BASE,
            **week_cell_style(cell.week_key),
            "color": "var(--alloq-text-muted)",
        },
    )


def _internal_row(emp: ObjectVar[EmployeeBlock]) -> rx.Component:
    return grid_row(
        mn.box(
            mn.text("Interne Projekte", size="xs", c="var(--alloq-text-muted)"),
            mn.text(
                de_number(
                    emp.internal_days,
                    decimal_scale=2,
                    fixed_decimal_scale=True,
                    prefix="· ",
                    suffix=" / Wo.",
                ),
                size="xs",
                c="var(--alloq-text-muted)",
            ),
            style={
                "gap": "4px",
                **LABEL_CELL_BASE,
                **STICKY_LEFT_BODY,
                "paddingLeft": "16px",
            },
        ),
        rx.foreach(emp.internal.cells, _internal_value_cell),
    )


def _gesamt_value_cell(cell: ObjectVar[GesamtCell]) -> rx.Component:
    """Free days; overbooking is tinted, absence weeks carry a small dot."""
    is_over = cell.state == "over"
    return mn.box(
        rx.cond(cell.has_absence, mn.box(style=ABSENCE_DOT), rx.fragment()),
        format_gesamt(cell.value),
        custom_attrs={"title": cell.breakdown},
        style={
            **CELL_BASE,
            **week_cell_style(cell.week_key),
            "position": "relative",
            "backgroundColor": rx.cond(
                is_over, GESAMT_OVER_BG, current_week_bg(cell.week_key)
            ),
            "color": _gesamt_color(cell.state),
            "fontWeight": rx.cond(is_over, "700", "500"),
        },
    )


def _gesamt_row(emp: ObjectVar[EmployeeBlock]) -> rx.Component:
    return grid_row(
        mn.box(
            mn.text("Gesamt (frei)", size="12px", fw="700", c="var(--alloq-text)"),
            style={
                **LABEL_CELL_BASE,
                **STICKY_LEFT_GESAMT,
            },
        ),
        rx.foreach(emp.gesamt, _gesamt_value_cell),
    )


def _employee_block(emp: ObjectVar[EmployeeBlock]) -> rx.Component:
    is_collapsed = PlanningStore.collapsed_employees.contains(emp.id)
    return mn.box(
        _employee_header_row(emp),
        rx.cond(
            ~is_collapsed,
            mn.box(
                rx.foreach(emp.projects, _project_row_view),
                rx.cond(
                    ~PlanningStore.hide_internal,
                    rx.fragment(_internal_row(emp), _absence_row(emp)),
                    rx.fragment(),
                ),
                _gesamt_row(emp),
            ),
            rx.fragment(),
        ),
        empty_grid_row(),
        style={"opacity": rx.cond(emp.department_highlighted, "1", "0.58")},
    )


def _employee_section_header(title: str, collapsed: rx.Var[bool]) -> rx.Component:
    return grid_row(
        mn.group(
            mn.action_icon(
                rx.cond(
                    collapsed,
                    rx.icon("chevron-right", size=16, stroke_width=2),
                    rx.icon("chevron-down", size=16, stroke_width=2),
                ),
                variant="subtle",
                color="gray",
                size="sm",
                aria_label="Weitere Abteilungen ein- oder ausklappen",
                on_click=PlanningStore.toggle_unhighlighted,
            ),
            mn.text(title, size="xs", fw="700", c="var(--alloq-text-muted)"),
            style={"gridColumn": "1 / -1"},
            gap="sm",
            align="center",
        ),
        style={
            "height": "30px",
            "borderBottom": "1px solid var(--alloq-border-strong)",
            "backgroundColor": "var(--alloq-fade-bg)",
        },
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
                        data=PlanningStore.add_project_options.to(list[dict[str, Any]]),
                        value=PlanningStore.add_project_selected,
                        on_change=PlanningStore.set_add_project_selected,
                        required=True,
                        searchable=True,
                        clearable=True,
                        left_section=rx.icon("folder", size=16),
                    ),
                    rx.cond(
                        PlanningStore.quick_create_active,
                        quick_project_fields(
                            name_value=PlanningStore.quick_project_name,
                            on_name_change=PlanningStore.set_quick_project_name,
                            code_value=PlanningStore.quick_project_code,
                            on_code_change=PlanningStore.set_quick_project_code,
                            on_create=PlanningStore.quick_create_project,
                            loading=PlanningStore.is_quick_creating,
                        ),
                        rx.fragment(),
                    ),
                    mn.select(
                        name="role_id",
                        label="Rolle",
                        data=PlanningStore.add_project_role_options.to(
                            list[dict[str, str]]
                        ),
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
# Legend
# ---------------------------------------------------------------------------


def _footer() -> rx.Component:
    return legend_footer(
        *week_legend_items(),
        legend_item(
            {
                "width": "18px",
                "height": "14px",
                "borderRadius": "3px",
                "backgroundColor": GESAMT_OVER_BG,
            },
            OVERBOOKED_LABEL,
        ),
        legend_item(
            {
                "width": "18px",
                "height": "14px",
                "backgroundImage": ABSENCE_HATCH,
                "boxShadow": "inset 0 0 0 1px var(--aq-border)",
            },
            "Abwesenheit",
        ),
        hint=EDIT_HINT,
    )


# ---------------------------------------------------------------------------
# Main component
# ---------------------------------------------------------------------------


def planning_grid() -> rx.Component:
    return rx.fragment(
        _add_project_modal(),
        absence_modal(on_submit=PlanningAbsenceState.create_absence),
        rx.cond(
            PlanningStore.is_loaded,
            mn.box(
                planning_excel_grid(
                    header_block(
                        "Mitarbeiter",
                        PlanningStore.filtered_employees.length().to_string()
                        + " Personen",
                    ),
                    mn.box(
                        rx.foreach(
                            PlanningStore.highlighted_employees, _employee_block
                        ),
                        rx.cond(
                            PlanningStore.unhighlighted_employees.length() > 0,
                            rx.fragment(
                                _employee_section_header(
                                    "Weitere Abteilungen",
                                    PlanningStore.unhighlighted_collapsed,
                                ),
                                rx.cond(
                                    ~PlanningStore.unhighlighted_collapsed,
                                    rx.foreach(
                                        PlanningStore.unhighlighted_employees,
                                        _employee_block,
                                    ),
                                    rx.fragment(),
                                ),
                            ),
                            rx.fragment(),
                        ),
                    ),
                    grid_id="planning-grid-root",
                ),
                _footer(),
                style=VIEW_COLUMN_STYLE,
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
