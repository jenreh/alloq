import reflex as rx
from alloq_commons.entities.employee import SeniorityLevel
from alloq_team.components.employee_card import (
    _employee_initials,
    _seniority_color,
    employee_grid,
)
from alloq_team.components.employee_table import (
    employee_table,
)
from alloq_team.models.employee import Absence, Employee
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.components.form_inputs import hidden_field

HIGH_WORKLOAD_PERCENT = 75
WORKLOAD_LIMIT_PERCENT = 100

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
                        mn.date_picker_input(
                            label="Zeitraum",
                            name="date_range",
                            type="range",
                            placeholder="Zeitraum wählen",
                            min_date=TeamState.current_date,
                            value=TeamState.absence_date_range,
                            on_change=TeamState.set_absence_date_range,
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


# --- Main Team Overview ---


def team_overview() -> rx.Component:
    """Complete team overview component with grid/table toggle."""
    return mn.stack(
        add_employee_modal(),
        edit_employee_modal(),
        absence_modal(),
        employee_detail_drawer(),
        rx.cond(
            TeamState.view_mode == "grid",
            employee_grid(),
            employee_table(),
        ),
        gap="md",
        width="100%",
    )
