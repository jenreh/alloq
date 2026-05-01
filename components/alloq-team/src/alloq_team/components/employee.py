import reflex as rx
from alloq_commons.entities.employee import SeniorityLevel
from alloq_team.components.employee_card import (
    _employee_initials,
    _seniority_color,
    employee_card,
)
from alloq_team.models.employee import Absence, Employee
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.components.form_inputs import hidden_field
from appkit_ui.styles import sticky_header_style

# --- Form Fields ---


def employee_form_fields(employee: Employee | None = None) -> rx.Component:
    """Reusable form fields for employee add/edit dialogs."""
    is_edit = employee is not None

    return mn.flex(
        hidden_field(
            name="employee_id",
            default_value=(
                employee.id.to_string() if is_edit else ""  # type: ignore[union-attr]
            ),
        ),
        mn.text_input(
            name="first_name",
            label="Vorname",
            default_value=employee.first_name if is_edit else "",
            required=True,
            max_length=255,
            left_section=rx.icon("user", size=16),
        ),
        mn.text_input(
            name="last_name",
            label="Nachname",
            default_value=employee.last_name if is_edit else "",
            required=True,
            max_length=255,
            left_section=rx.icon("user", size=16),
        ),
        mn.select(
            name="seniority",
            label="Senioritätslevel",
            data=[level.value for level in SeniorityLevel],
            default_value=(
                employee.seniority if is_edit else SeniorityLevel.ADVANCED.value
            ),
            required=True,
        ),
        mn.text_input(
            name="job_title",
            label="Job-Titel (z.B. Software Engineer)",
            default_value=employee.job_title if is_edit else "",
            required=False,
            max_length=255,
            left_section=rx.icon("briefcase", size=16),
        ),
        mn.text_input(
            name="location",
            label="Standort (z.B. New York, USA)",
            default_value=employee.location if is_edit else "",
            required=False,
            max_length=255,
            left_section=rx.icon("map-pin", size=16),
        ),
        mn.multi_select(
            name="role_ids",
            label="Rollen",
            data=TeamState.role_select_options,
            default_value=(employee.role_ids.to(list[str]) if is_edit else []),
            required=True,
        ),
        mn.number_input(
            name="hours_per_week",
            label="Arbeitszeit (h/Woche)",
            default_value=employee.hours_per_week if is_edit else 40.0,
            min=0,
            max=80,
            step=0.5,
            required=True,
            left_section=rx.icon("clock", size=16),
        ),
        direction="column",
        gap="md",
        width="100%",
    )


def _modal_footer(
    submit_label: str,
    on_cancel: rx.EventHandler,
) -> rx.Component:
    """Footer buttons for modals."""
    return rx.flex(
        mn.button(
            "Abbrechen",
            variant="subtle",
            on_click=on_cancel,
        ),
        mn.button(
            submit_label,
            type="submit",
            loading=TeamState.is_loading,
        ),
        direction="row",
        gap="9px",
        justify_content="end",
        padding="16px",
        border_top="1px solid var(--mantine-color-default-border)",
        background="var(--mantine-color-body)",
        width="100%",
    )


# --- Modals ---


def add_employee_modal() -> rx.Component:
    """Modal for adding a new employee."""
    return mn.modal(
        rx.form.root(
            rx.flex(
                rx.box(
                    employee_form_fields(),
                    flex="1",
                    min_height="0",
                    width="100%",
                    padding="md",
                ),
                _modal_footer("Mitarbeiter speichern", TeamState.close_add_modal),
                direction="column",
                height="100%",
                width="100%",
            ),
            on_submit=TeamState.create_employee,
            reset_on_submit=False,
            height="100%",
        ),
        title="Mitarbeiter hinzufügen",
        opened=TeamState.add_modal_open,
        on_close=TeamState.close_add_modal,
        size="md",
        centered=True,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def edit_employee_modal() -> rx.Component:
    """Modal for editing an existing employee."""
    return mn.modal(
        rx.form.root(
            rx.flex(
                rx.box(
                    employee_form_fields(employee=TeamState.selected_employee),
                    flex="1",
                    min_height="0",
                    width="100%",
                    padding="md",
                ),
                _modal_footer("Mitarbeiter aktualisieren", TeamState.close_edit_modal),
                direction="column",
                height="100%",
                width="100%",
            ),
            on_submit=TeamState.update_employee,
            reset_on_submit=False,
            height="100%",
        ),
        title="Mitarbeiter bearbeiten",
        opened=TeamState.edit_modal_open,
        on_close=TeamState.close_edit_modal,
        size="md",
        centered=True,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def absence_modal() -> rx.Component:
    """Modal for adding an absence period."""
    return mn.modal(
        rx.form.root(
            rx.flex(
                rx.box(
                    mn.flex(
                        mn.date_input(
                            label="Startdatum",
                            name="start_date",
                            placeholder="Datum wählen",
                            required=True,
                            clearable=True,
                            w="100%",
                        ),
                        mn.date_input(
                            label="Enddatum",
                            name="end_date",
                            placeholder="Datum wählen",
                            required=True,
                            clearable=True,
                            w="100%",
                        ),
                        direction="column",
                        gap="md",
                        width="100%",
                    ),
                    flex="1",
                    min_height="0",
                    width="100%",
                    padding="md",
                ),
                _modal_footer("Abwesenheit speichern", TeamState.close_absence_modal),
                direction="column",
                height="100%",
                width="100%",
            ),
            on_submit=TeamState.create_absence,
            reset_on_submit=True,
            height="100%",
        ),
        title="Abwesenheit hinzufügen",
        opened=TeamState.absence_modal_open,
        on_close=TeamState.close_absence_modal,
        size="sm",
        centered=True,
        z_index=300,
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


# --- Card View ---


def employee_grid() -> rx.Component:
    """Card grid view of all employees."""
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
        mn.flex(
            rx.foreach(
                TeamState.filtered_employees,
                employee_card,
            ),
            wrap="wrap",
            gap="md",
            direction="row",
            justify="flex-start",
        ),
    )


# --- Table View ---


def _employee_table_row(employee: Employee) -> rx.Component:
    """Render a single employee as a table row."""
    return mn.table.tr(
        mn.table.td(
            mn.group(
                _employee_initials(employee),
                mn.text(
                    f"{employee.first_name} {employee.last_name}",
                    size="sm",
                    fw="500",
                ),
                gap="sm",
                align="center",
            ),
        ),
        mn.table.td(
            rx.cond(
                employee.job_title != "",
                mn.text(employee.job_title, size="sm"),
                mn.text(employee.seniority, size="sm", c="dimmed"),
            ),
        ),
        mn.table.td(
            mn.badge(
                employee.seniority,
                color=_seniority_color(employee.seniority),
                size="xs",
                variant="light",
            ),
        ),
        mn.table.td(
            mn.group(
                rx.foreach(
                    employee.role_names,
                    lambda rn: mn.badge(
                        rn,
                        color="gray",
                        size="xs",
                        variant="outline",
                    ),
                ),
                gap="xs",
            ),
        ),
        mn.table.td(
            mn.text(f"{employee.hours_per_week} h", size="sm"),
        ),
        mn.table.td(
            mn.group(
                rx.icon_button(
                    rx.icon("square-pen", size=16),
                    variant="ghost",
                    on_click=lambda: TeamState.select_employee_and_edit(employee.id),
                ),
                delete_dialog(
                    title="Löschen bestätigen",
                    content=f"{employee.first_name} {employee.last_name}",
                    on_click=lambda: TeamState.delete_employee(employee.id),
                    icon_button=True,
                    color="red",
                ),
                gap="xs",
                wrap="nowrap",
                align="center",
            ),
            width="1%",
            style={"whiteSpace": "nowrap"},
        ),
        style={"cursor": "pointer"},
        on_click=lambda: TeamState.select_employee(employee.id),
    )


def employee_table() -> rx.Component:
    """Table view of all employees."""
    return mn.table(
        mn.table.thead(
            mn.table.tr(
                mn.table.th(mn.text("Name", size="sm", fw="700")),
                mn.table.th(mn.text("Job-Titel", size="sm", fw="700")),
                mn.table.th(mn.text("Level", size="sm", fw="700")),
                mn.table.th(mn.text("Rollen", size="sm", fw="700")),
                mn.table.th(mn.text("Stunden", size="sm", fw="700")),
                mn.table.th(mn.text("", size="sm")),
                style=sticky_header_style,
            ),
        ),
        mn.table.tbody(
            rx.cond(
                TeamState.is_loading,
                mn.table.tr(
                    mn.table.td(
                        rx.hstack(
                            rx.spinner(size="3"),
                            mn.text("Lade Team...", size="sm"),
                            align="center",
                            justify="center",
                            spacing="3",
                        ),
                        col_span=5,
                        style={"textAlign": "center"},
                    ),
                ),
                rx.foreach(
                    TeamState.filtered_employees,
                    _employee_table_row,
                ),
            ),
        ),
        highlight_on_hover=True,
        width="100%",
    )


# --- Detail Drawer ---


def _absence_row(absence: Absence) -> rx.Component:
    """Single absence row in the detail drawer."""
    return mn.group(
        mn.text(
            f"{absence.start_date} - {absence.end_date}",
            size="sm",
        ),
        delete_dialog(
            title="Abwesenheit löschen",
            content=f"{absence.start_date} - {absence.end_date}",
            on_click=lambda: TeamState.delete_absence(absence.id),
            icon_button=True,
            color="red",
            size="xs",
        ),
        justify="space-between",
        align="center",
        w="100%",
    )


def employee_detail_drawer() -> rx.Component:
    """Right-side drawer showing employee details and absences."""
    return mn.drawer(
        mn.stack(
            # Employee details section
            mn.stack(
                mn.group(
                    _employee_initials(TeamState.selected_employee),
                    mn.stack(
                        mn.text(
                            f"{TeamState.selected_employee.first_name} "
                            f"{TeamState.selected_employee.last_name}",
                            fw="700",
                            size="lg",
                        ),
                        mn.group(
                            mn.badge(
                                TeamState.selected_employee.seniority,
                                color=_seniority_color(
                                    TeamState.selected_employee.seniority
                                ),
                                size="sm",
                                variant="light",
                            ),
                            rx.foreach(
                                TeamState.selected_employee.role_names,
                                lambda rn: mn.badge(
                                    rn,
                                    color="gray",
                                    size="sm",
                                    variant="outline",
                                ),
                            ),
                            gap="xs",
                        ),
                        gap="4px",
                    ),
                    gap="md",
                    align="center",
                ),
                mn.divider(),
                mn.text(
                    f"Arbeitszeit: "
                    f"{TeamState.selected_employee.hours_per_week}"
                    f" h/Woche",
                    size="sm",
                    c="dimmed",
                ),
                gap="sm",
            ),
            # Absences section
            mn.stack(
                mn.group(
                    mn.text("Abwesenheiten", fw="600", size="sm"),
                    mn.action_icon(
                        rx.icon("plus", size=16),
                        variant="light",
                        size="sm",
                        on_click=TeamState.open_absence_modal,
                    ),
                    justify="space-between",
                    align="center",
                    w="100%",
                ),
                rx.cond(
                    TeamState.absences.length() > 0,
                    mn.stack(
                        rx.foreach(TeamState.absences, _absence_row),
                        gap="xs",
                    ),
                    mn.text(
                        "Keine Abwesenheiten eingetragen.",
                        size="sm",
                        c="dimmed",
                        fs="italic",
                    ),
                ),
                gap="sm",
            ),
            # Project assignments (read-only, future feature)
            mn.stack(
                mn.text("Projektzuordnungen", fw="600", size="sm"),
                mn.text(
                    "Noch keine Projekte zugeordnet.",
                    size="sm",
                    c="dimmed",
                    fs="italic",
                ),
                gap="sm",
            ),
            gap="xl",
        ),
        title="Mitarbeiter Details",
        opened=TeamState.detail_drawer_open,
        on_close=TeamState.close_detail_drawer,
        position="right",
        size="md",
        overlay_props={"backgroundOpacity": 0.3, "blur": 2},
    )


# --- Toolbar ---


def view_mode_toggle() -> rx.Component:
    """Toggle between grid and table view."""
    return mn.group(
        mn.action_icon(
            rx.icon("layout-grid", size=20, color="black"),
            variant=rx.cond(TeamState.view_mode == "grid", "filled", "subtle"),
            size="lg",
            radius="md",
            on_click=lambda: TeamState.set_view_mode("grid"),
        ),
        mn.action_icon(
            rx.icon("list", size=20, color="black"),
            variant=rx.cond(TeamState.view_mode == "table", "filled", "subtle"),
            size="lg",
            radius="md",
            on_click=lambda: TeamState.set_view_mode("table"),
        ),
        gap="2px",
    )


def add_employee_button() -> rx.Component:
    """Button to add a new employee."""
    return mn.action_icon(
        rx.icon("plus", size=20, color="black"),
        variant="filled",
        size="lg",
        radius="md",
        on_click=TeamState.open_add_modal,
    )


def employee_search_bar() -> rx.Component:
    """Search input for filtering employees."""
    return mn.text_input(
        placeholder="Search by name",
        left_section=rx.icon("search", size=16),
        left_section_pointer_events="none",
        value=TeamState.search_filter,
        on_change=TeamState.set_search_filter,
        size="sm",
        w="18rem",
    )


def team_toolbar() -> rx.Component:
    """Top-right team page toolbar."""
    return rx.flex(
        employee_search_bar(),
        add_employee_button(),
        mn.space(w="xs"),
        view_mode_toggle(),
        width="auto",
        gap="12px",
        align="center",
        justify="end",
        style={
            "position": "fixed",
            "top": "2.25rem",
            "right": "2rem",
            "z_index": "20",
        },
    )


# --- Main Team Overview ---


def team_overview() -> rx.Component:
    """Complete team overview component with grid/table toggle."""
    return mn.stack(
        add_employee_modal(),
        edit_employee_modal(),
        absence_modal(),
        employee_detail_drawer(),
        # Content
        rx.cond(
            TeamState.view_mode == "grid",
            employee_grid(),
            employee_table(),
        ),
        gap="md",
        width="100%",
    )
