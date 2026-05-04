import reflex as rx
from alloq_commons.components.forms import section
from alloq_commons.entities.employee import SeniorityLevel
from alloq_commons.models.employee import Absence
from alloq_team.components.employee_card import (
    _format_date_de,
    employee_grid,
)
from alloq_team.components.employee_table import (
    employee_table,
)
from alloq_team.states.team_state import EmployeeValidationState, TeamState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.components.form_inputs import hidden_field

HIGH_WORKLOAD_PERCENT = 75
WORKLOAD_LIMIT_PERCENT = 100

# --- Form Fields ---


def employee_form_fields(is_edit: bool = False) -> rx.Component:
    """Reusable form fields for employee add/edit dialogs."""

    return mn.flex(
        hidden_field(
            name="employee_id",
            default_value=rx.cond(
                TeamState.selected_employee,
                TeamState.selected_employee.id.to_string(),
                "",
            ),
        )
        if is_edit
        else rx.fragment(),
        section(
            mn.text_input(
                name="first_name",
                label="Vorname",
                default_value=EmployeeValidationState.first_name,
                on_blur=EmployeeValidationState.set_first_name,
                error=EmployeeValidationState.first_name_error,
                required=True,
                max_length=255,
                left_section=rx.icon("user", size=16),
            ),
            mn.text_input(
                name="last_name",
                label="Nachname",
                default_value=EmployeeValidationState.last_name,
                on_blur=EmployeeValidationState.set_last_name,
                error=EmployeeValidationState.last_name_error,
                required=True,
                max_length=255,
                left_section=rx.icon("user", size=16),
            ),
            mn.text_input(
                name="email",
                label="E-Mail",
                default_value=EmployeeValidationState.email,
                on_change=EmployeeValidationState.set_email,
                on_blur=EmployeeValidationState.validate_email_unique,
                error=EmployeeValidationState.email_error,
                required=False,
                max_length=255,
                left_section=rx.icon("mail", size=16),
            ),
            mn.text_input(
                name="job_title",
                label="Job-Titel (z.B. Software Engineer)",
                default_value=EmployeeValidationState.job_title,
                on_blur=EmployeeValidationState.set_job_title,
                required=False,
                max_length=255,
                left_section=rx.icon("briefcase", size=16),
            ),
            mn.text_input(
                name="location",
                label="Standort (z.B. New York, USA)",
                default_value=EmployeeValidationState.location,
                on_blur=EmployeeValidationState.set_location,
                required=False,
                max_length=255,
                left_section=rx.icon("map-pin", size=16),
            ),
            mn.select(
                name="manager_id",
                label="Vorgesetzter",
                data=TeamState.employee_select_options,
                default_value=EmployeeValidationState.manager_id,
                on_change=EmployeeValidationState.set_manager_id,
                required=False,
                clearable=True,
                searchable=True,
                left_section=rx.icon("user-check", size=16),
            ),
        ),
        section(
            mn.select(
                name="seniority",
                label="Senioritätslevel",
                data=[level.value for level in SeniorityLevel],
                default_value=EmployeeValidationState.seniority,
                on_change=EmployeeValidationState.set_seniority,
                required=True,
                clearable=False,
                searchable=False,
            ),
            mn.multi_select(
                name="role_ids",
                label="Rollen",
                data=TeamState.role_select_options,
                default_value=EmployeeValidationState.role_ids,
                on_change=EmployeeValidationState.set_role_ids,
                error=EmployeeValidationState.role_ids_error,
                required=True,
                searchable=True,
                clearable=True,
            ),
            mn.number_input(
                name="hours_per_week",
                label="Arbeitszeit (h/Woche)",
                default_value=EmployeeValidationState.hours_per_week,
                on_blur=EmployeeValidationState.set_hours_per_week,
                on_change=EmployeeValidationState.set_hours_per_week,
                error=EmployeeValidationState.hours_per_week_error,
                min=0,
                max=80,
                step=0.5,
                required=True,
                left_section=rx.icon("clock", size=16),
            ),
        ),
        direction="column",
        gap="md",
        width="100%",
    )


def _form_footer(
    submit_label: str,
    on_cancel: rx.EventHandler,
    disabled: bool | rx.Var[bool] = False,
) -> rx.Component:
    """Footer buttons for modals and drawers."""
    return mn.group(
        mn.button(
            "Abbrechen",
            variant="subtle",
            on_click=on_cancel,
            color="yellow",
        ),
        mn.button(
            submit_label,
            type="submit",
            disabled=disabled,
            loading=TeamState.is_loading,
            px="xl",
            class_name="alloq-submit-btn",
        ),
        direction="row",
        gap="md",
        justify="end",
        align="center",
        padding="16px 18px 18px",
        background="var(--alloq-surface-muted)",
        width="100%",
        flex_shrink="0",
        box_shadow="0 -3px 9px rgba(91, 76, 34, 0.12)",
        z_index="1",
    )


def _form_layout(
    content: rx.Component,
    footer: rx.Component,
    on_submit: rx.EventHandler,
    reset_on_submit: bool = False,
) -> rx.Component:
    """Standardized layout for forms inside modals or drawers."""
    return rx.form.root(
        rx.flex(
            rx.box(
                content,
                flex="1",
                min_height="0",
                width="100%",
                overflow_y="auto",
                padding="16px 18px 0",
                background="var(--alloq-surface-muted)",
            ),
            footer,
            direction="column",
            min_height="0",
            height="100%",
            width="100%",
            background="var(--alloq-surface-muted)",
        ),
        on_submit=on_submit,
        reset_on_submit=reset_on_submit,
        height="100%",
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100%",
            "minHeight": "0",
        },
    )


# --- Modals ---


def add_employee_modal() -> rx.Component:
    """Modal for adding a new employee."""
    return mn.modal(
        _form_layout(
            content=mn.flex(
                employee_form_fields(is_edit=False),
                mn.space(height="1.5rem"),
                direction="column",
                width="100%",
            ),
            footer=_form_footer(
                "Mitarbeiter speichern",
                TeamState.close_add_modal,
                disabled=EmployeeValidationState.is_form_invalid,
            ),
            on_submit=TeamState.create_employee,
            reset_on_submit=False,
        ),
        title="Mitarbeiter hinzufügen",
        opened=TeamState.add_modal_open,
        on_close=TeamState.close_add_modal,
        size="lg",
        centered=True,
        class_name="alloq-employee-detail-modal",
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


def absence_modal() -> rx.Component:
    """Modal for adding an absence period."""
    return mn.modal(
        _form_layout(
            content=mn.flex(
                section(
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
                        locale="de",
                        value_format="DD MMM YYYY",
                        w="100%",
                    ),
                ),
                mn.space(height="2rem"),
                direction="column",
                gap="md",
                width="100%",
            ),
            footer=_form_footer("Speichern", TeamState.close_absence_modal),
            on_submit=TeamState.create_absence,
            reset_on_submit=True,
        ),
        title="Abwesenheit hinzufügen",
        opened=TeamState.absence_modal_open,
        on_close=TeamState.close_absence_modal,
        size="md",
        centered=True,
        z_index=300,
        class_name="alloq-employee-detail-modal",
        overlay_props={"backgroundOpacity": 0.5, "blur": 4},
    )


# --- Detail Drawer ---


def _absence_row(absence: Absence) -> rx.Component:
    """Single absence row in the detail drawer matching the card design."""
    return mn.group(
        mn.text(
            _format_date_de(absence.start_date)
            + " bis "
            + _format_date_de(absence.end_date),
            size="0.66rem",
            ff="'Roboto Mono', monospace",
            style={
                "color": "var(--alloq-item-text)",
                "fontWeight": "400",
            },
        ),
        delete_dialog(
            title="Abwesenheit löschen",
            content=f"{absence.start_date} bis {absence.end_date}",
            on_click=lambda: TeamState.delete_absence(absence.id),
            icon_button=True,
            color="red",
            size="xs",
            variant="subtle",
        ),
        align="center",
        justify="space-between",
        gap="xs",
        style={
            "backgroundColor": "var(--alloq-surface-muted)",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    )


def employee_detail_drawer() -> rx.Component:
    """Right-side drawer showing employee details and working as update dialog."""
    return mn.drawer(
        _form_layout(
            content=mn.stack(
                employee_form_fields(is_edit=True),
                section(
                    mn.stack(
                        mn.group(
                            mn.text("Abwesenheiten", size="sm", c="dimmed", fw="500"),
                            mn.action_icon(
                                rx.icon("plus", size=14, stroke_width=2),
                                size="sm",
                                variant="subtle",
                                color="gray",
                                on_click=TeamState.open_absence_modal,
                            ),
                            align="center",
                            justify="space-between",
                        ),
                        mn.stack(
                            rx.foreach(TeamState.absences, _absence_row),
                            rx.cond(
                                TeamState.absences.length() == 0,
                                mn.group(
                                    mn.text(
                                        "Keine Abwesenheiten.",
                                        ff="'Roboto Mono', monospace",
                                        size="0.66rem",
                                        c="dimmed",
                                    ),
                                    align="center",
                                    gap="sm",
                                    style={
                                        "backgroundColor": "var(--alloq-surface-muted)",
                                        "padding": "8px 12px",
                                        "borderRadius": "6px",
                                    },
                                ),
                            ),
                            gap="3px",
                            w="100%",
                        ),
                        gap="xs",
                        w="100%",
                    ),
                ),
                mn.space(height="md"),
                gap="16px",
                key=EmployeeValidationState.form_version.to(str),
            ),
            footer=_form_footer(
                "Mitarbeiter aktualisieren",
                TeamState.close_detail_drawer,
                disabled=EmployeeValidationState.is_form_invalid,
            ),
            on_submit=TeamState.update_employee,
            reset_on_submit=False,
        ),
        title=rx.cond(
            TeamState.selected_employee,
            f"{TeamState.selected_employee.first_name} "
            f"{TeamState.selected_employee.last_name}",
            "Mitarbeiter Details",
        ),
        opened=TeamState.detail_drawer_open,
        on_close=TeamState.close_detail_drawer,
        position="right",
        size="lg",
        overlay_props={"backgroundOpacity": 0.3, "blur": 3},
        offset="15px",
        radius="md",
        class_name="alloq-employee-detail-drawer",
        with_close_button=True,
        close_on_click_outside=True,
    )


# --- Main Team Overview ---


def team_overview() -> rx.Component:
    """Complete team overview component with grid/table toggle."""
    return mn.stack(
        add_employee_modal(),
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
