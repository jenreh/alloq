import reflex as rx
from alloq_commons.components.formatters import de_number
from alloq_commons.models.employee import Employee
from alloq_team.components.employee_card import (
    _employee_initials,
)
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.styles import sticky_header_style

HIGH_WORKLOAD_PERCENT = 75
WORKLOAD_LIMIT_PERCENT = 100

TABLE_HEADER_STYLE = {
    **sticky_header_style,
    "backgroundColor": "var(--alloq-surface-solid)",
}

TABLE_STYLE = {
    "borderCollapse": "collapse",
    "borderSpacing": "0",
    "margin": "0",
    "width": "100%",
    "tableLayout": "fixed",
}

TABLE_WRAPPER_STYLE = {
    "backgroundColor": "var(--alloq-fade-bg)",
    "borderRadius": "var(--mantine-radius-sm)",
    "margin": "0",
    "overflowX": "auto",
    "overflowY": "hidden",
    "padding": "0",
}

NO_WRAP_CELL_STYLE = {
    "whiteSpace": "nowrap",
}


def _workload_color(workload_percent: int) -> str:
    """Return a Mantine color for workload severity."""
    return rx.cond(
        workload_percent > WORKLOAD_LIMIT_PERCENT,
        "red",
        rx.cond(workload_percent >= HIGH_WORKLOAD_PERCENT, "yellow", "green"),
    )


def _employee_name_cell(employee: Employee) -> rx.Component:
    """Render employee identity with avatar and short identifier."""
    return mn.group(
        _employee_initials(employee),
        mn.stack(
            mn.text(
                f"{employee.first_name} {employee.last_name}",
                size="sm",
                fw="700",
                c="var(--alloq-text)",
                lh="1.15",
            ),
            mn.text(f"{employee.job_title}", size="xs", c="dimmed", lh="1"),
            gap="2px",
        ),
        gap="md",
        align="center",
        wrap="nowrap",
    )


def _location_cell(employee: Employee) -> rx.Component:
    """Render job title as the role column from the reference table."""
    return mn.text(
        rx.cond(employee.location, employee.location, ""),
        size="sm",
        c="var(--alloq-text)",
    )


def _workload_cell(employee: Employee) -> rx.Component:
    """Render workload progress and percentage."""
    return mn.group(
        mn.progress(
            value=employee.workload_percent,
            color=_workload_color(employee.workload_percent),
            size="sm",
            radius="xl",
            w="8rem",
            bg="var(--alloq-meter-track)",
        ),
        mn.text(
            de_number(
                value=employee.workload_percent,
                suffix="%",
            ),
            size="sm",
            c=rx.cond(
                employee.workload_percent > WORKLOAD_LIMIT_PERCENT,
                "var(--mantine-color-red-7)",
                "var(--alloq-text)",
            ),
            miw="3rem",
        ),
        gap="md",
        align="center",
        wrap="nowrap",
    )


def _role_badge(role_name: str) -> rx.Component:
    """Render a compact role badge with screenshot palette colors."""
    return mn.badge(
        role_name,
        size="sm",
        variant="filled",
        radius="sm",
        fw="800",
    )


def _employee_table_row(employee: Employee) -> rx.Component:
    """Render a single employee as a table row."""
    return mn.table.tr(
        mn.table.td(_employee_name_cell(employee), width="300px", min_width="240px"),
        mn.table.td(employee.location, width="150px", min_width="120px"),
        mn.table.td(employee.seniority, width="120px", min_width="120px"),
        mn.table.td(
            mn.group(
                rx.foreach(
                    employee.role_names,
                    _role_badge,
                ),
                gap="6px",
                wrap="wrap",
            ),
        ),
        mn.table.td(
            de_number(
                value=employee.hours_per_week,
                suffix=" h/Woche",
                decimal_scale=1,
            ),
            style=NO_WRAP_CELL_STYLE,
        ),
        mn.table.td(_workload_cell(employee), style=NO_WRAP_CELL_STYLE),
        mn.table.td(
            mn.group(
                rx.icon_button(
                    rx.icon("square-pen", size=16),
                    variant="ghost",
                    on_click=TeamState.select_employee(employee.id),
                ),
                delete_dialog(
                    title="Löschen bestätigen",
                    content=f"{employee.first_name} {employee.last_name}",
                    on_click=TeamState.delete_employee(employee.id),
                    icon_button=True,
                    color="red",
                    variant="subtle",
                    size="sm",
                ),
                gap="12px",
                wrap="nowrap",
                align="center",
            ),
            width="1%",
            style={"whiteSpace": "nowrap"},
        ),
        class_name="alloq-team-table-row",
        style={"cursor": "pointer"},
        on_click=TeamState.select_employee(employee.id),
    )


def _employee_table_section(title: str, employees: rx.Var) -> rx.Component:
    """Helper to render a titled section of the employee table."""
    return rx.cond(
        employees.length() > 0,
        mn.stack(
            mn.text(
                title,
                size="lg",
                fw="700",
            ),
            mn.box(
                mn.table(
                    mn.table.thead(
                        mn.table.tr(
                            mn.table.th(
                                mn.text("Mitarbeiter", size="sm", fw="800"),
                                style=TABLE_HEADER_STYLE,
                                width="300px",
                                min_width="240px",
                            ),
                            mn.table.th(
                                mn.text("Standort", size="sm", fw="800"),
                                style=TABLE_HEADER_STYLE,
                                width="150px",
                                min_width="120px",
                            ),
                            mn.table.th(
                                mn.text("Level", size="sm", fw="800"),
                                style=TABLE_HEADER_STYLE,
                                width="120px",
                                min_width="120px",
                            ),
                            mn.table.th(
                                mn.text("Rollen", size="sm", fw="800"),
                                style=TABLE_HEADER_STYLE,
                            ),
                            mn.table.th(
                                mn.text("Stunden", size="sm", fw="800"),
                                style=TABLE_HEADER_STYLE,
                            ),
                            mn.table.th(
                                mn.text("Auslastung", size="sm", fw="800"),
                                style=TABLE_HEADER_STYLE,
                            ),
                            mn.table.th(
                                mn.text("", size="sm"), style=TABLE_HEADER_STYLE
                            ),
                        ),
                    ),
                    mn.table.tbody(
                        rx.foreach(
                            employees,
                            _employee_table_row,
                        ),
                    ),
                    sticky_header=True,
                    sticky_header_offset="0px",
                    striped=False,
                    highlight_on_hover=True,
                    highlight_on_hover_color="var(--alloq-surface-hover)",
                    w="100%",
                    style=TABLE_STYLE,
                ),
                width="100%",
                m="0",
                p="12px",
                style=TABLE_WRAPPER_STYLE,
            ),
            gap="sm",
        ),
    )


def _no_employees_table_state() -> rx.Component:
    """Empty state when no employees match the current filter (table view)."""
    return mn.center(
        mn.stack(
            mn.center(
                rx.icon("users", size=48, color="var(--mantine-color-gray-5)"),
            ),
            rx.cond(
                TeamState.search_filter != "",
                mn.text(
                    "Keine Mitarbeiter gefunden.",
                    size="lg",
                    fw="500",
                    c="gray",
                    ta="center",
                ),
                mn.stack(
                    mn.text(
                        "Noch keine Mitarbeiter vorhanden.",
                        size="lg",
                        fw="500",
                        c="gray",
                        ta="center",
                    ),
                    mn.text(
                        "Fügen Sie Ihren ersten Mitarbeiter hinzu.",
                        size="sm",
                        c="dimmed",
                        ta="center",
                    ),
                    gap="xs",
                    align="center",
                ),
            ),
            gap="md",
            align="center",
        ),
        py="4rem",
        width="100%",
    )


def employee_table() -> rx.Component:
    """Table view of all employees."""
    return rx.cond(
        TeamState.is_loading,
        mn.center(
            rx.hstack(
                rx.spinner(size="3"),
                mn.text("Lade Team...", size="sm"),
                align="center",
                spacing="3",
            ),
            py="xl",
        ),
        rx.cond(
            (TeamState.my_employees.length() == 0)
            & (TeamState.other_employees.length() == 0),
            _no_employees_table_state(),
            mn.stack(
                _employee_table_section("Meine Mitarbeiter", TeamState.my_employees),
                _employee_table_section(
                    "Weitere Mitarbeiter", TeamState.other_employees
                ),
                gap="xl",
            ),
        ),
    )
