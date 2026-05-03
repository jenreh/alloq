import reflex as rx
from alloq_commons.components.forms import section
from alloq_commons.models.role import Role
from alloq_project.states.project_state import (
    PROJECT_COLORS,
    ProjectState,
    ProjectValidationState,
)

import appkit_mantine as mn
from appkit_ui.components.form_inputs import hidden_field


def project_form_fields() -> rx.Component:
    """Reusable project form fields for the add dialog."""
    return mn.flex(
        section(
            mn.text_input(
                name="name_de",
                label="Name",
                placeholder="z.B. ML-Ops Plattform",
                default_value=ProjectValidationState.name_de,
                on_blur=ProjectValidationState.set_name_de,
                error=ProjectValidationState.name_de_error,
                required=True,
                max_length=255,
            ),
            mn.text_input(
                name="code",
                label="Projekt-Code",
                placeholder="z.B. ML-OPS",
                default_value=ProjectValidationState.code,
                on_blur=ProjectValidationState.set_code,
                error=ProjectValidationState.code_error,
                required=True,
                max_length=5,
                custom_attrs={"maxLength": 5},
                w="10rem",
            ),
            mn.multi_select(
                name="owner_ids",
                label="Projekt-Owner",
                data=ProjectState.employee_select_options,
                default_value=ProjectValidationState.owner_ids,
                on_change=ProjectValidationState.set_owner_ids,
                clearable=True,
                searchable=True,
                placeholder="Owner(s) auswählen",
            ),
        ),
        section(
            mn.simple_grid(
                mn.number_input(
                    name="budget",
                    label="Budget (€)",
                    default_value=ProjectValidationState.budget,
                    on_change=ProjectValidationState.set_budget,
                    error=ProjectValidationState.budget_error,
                    min=0,
                    step=10000,
                    required=True,
                    thousand_separator=".",
                    decimal_separator=",",
                ),
                mn.select(
                    name="state",
                    label="Status",
                    data=ProjectState.state_select_options,
                    default_value=ProjectValidationState.state,
                    on_change=ProjectValidationState.set_state,
                    required=True,
                    clearable=False,
                ),
                mn.date_input(
                    name="start_date",
                    label="Start",
                    value=ProjectValidationState.start_date,
                    on_change=ProjectValidationState.set_start_date,
                    error=ProjectValidationState.date_error,
                    required=True,
                    clearable=True,
                    locale="de",
                    value_format="DD MMM YYYY",
                    left_section=rx.icon("calendar", size=16),
                ),
                mn.date_input(
                    name="end_date",
                    label="Ende",
                    value=ProjectValidationState.end_date,
                    on_change=ProjectValidationState.set_end_date,
                    error=ProjectValidationState.date_error,
                    required=True,
                    clearable=True,
                    locale="de",
                    value_format="DD MMM YYYY",
                    left_section=rx.icon("calendar", size=16),
                ),
                cols=2,
                spacing="md",
                w="100%",
            ),
        ),
        _required_capacity_fields(),
        _color_picker(),
        direction="column",
        gap="xs",
        width="100%",
    )


def _color_picker() -> rx.Component:
    """Render a compact color picker with predefined project colors."""
    return section(
        mn.stack(
            mn.text("Farbe", size="sm", fw="700", c="dimmed"),
            mn.group(
                rx.foreach(PROJECT_COLORS, _color_swatch),
                gap="8px",
                wrap="wrap",
            ),
            hidden_field(
                name="color",
                default_value=ProjectValidationState.color,
            ),
            gap="xs",
            w="100%",
        ),
    )


def _color_swatch(color: str) -> rx.Component:
    """Render one selectable color swatch."""
    return mn.box(
        w="42px",
        h="42px",
        bg=color,
        on_click=lambda: ProjectValidationState.set_color(color),
        style={
            "borderRadius": "var(--mantine-radius-md)",
            "cursor": "pointer",
            "border": rx.cond(
                ProjectValidationState.color == color,
                "4px solid var(--alloq-text)",
                "3px solid rgba(255, 255, 255, 0.9)",
            ),
            "boxShadow": "0 0 0 1px rgba(91, 76, 34, 0.18)",
        },
    )


def _required_capacity_fields() -> rx.Component:
    """Render person-day inputs for all configured roles."""
    return section(
        mn.stack(
            mn.group(
                mn.text("Benötigte Rollen", size="sm", fw="700", c="dimmed"),
                mn.text(
                    f"({ProjectValidationState.total_capacity} PT Gesamt)",
                    size="xs",
                    c="dimmed",
                ),
                justify="space-between",
                w="100%",
            ),
            mn.simple_grid(
                rx.foreach(ProjectState.available_roles, _required_capacity_input),
                cols=3,
                spacing="md",
                w="100%",
            ),
            gap="xs",
            w="100%",
        ),
    )


def _required_capacity_input(role: Role) -> rx.Component:
    """Render a person-day input for a single role."""
    return mn.box(
        mn.stack(
            mn.group(
                mn.text(role.name, size="xs", fw="700", c="dimmed", truncate=True),
                gap="6px",
                wrap="nowrap",
            ),
            mn.number_input(
                name="required_capacity_" + role.id.to_string(),
                placeholder="Personentage",
                default_value=ProjectValidationState.role_capacities[
                    role.id.to_string()
                ],
                on_change=lambda v: ProjectValidationState.set_role_capacity(
                    role.id.to_string(), v
                ),
                min=0,
                start_value=5,
                step=5,
                w="100%",
                decimal_precision=0,
                decimal_separator=",",
                thousand_separator=".",
                # right_section=mn.text(" PT ", size="xs", c="dimmed"),
            ),
            gap="xs",
        ),
        p="0px",
    )


def form_footer(
    submit_label: str,
    on_cancel: rx.EventHandler,
    disabled: bool | rx.Var[bool] = False,
) -> rx.Component:
    """Footer buttons for project forms."""
    return mn.group(
        mn.button("Abbrechen", variant="subtle", on_click=on_cancel, color="yellow"),
        mn.button(
            submit_label,
            type="submit",
            disabled=disabled,
            loading=ProjectState.is_loading,
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


def form_layout(
    content: rx.Component,
    footer: rx.Component,
    on_submit: rx.EventHandler,
) -> rx.Component:
    """Standardized project form layout."""
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
        reset_on_submit=False,
        height="100%",
        style={
            "display": "flex",
            "flexDirection": "column",
            "height": "100%",
            "minHeight": "0",
        },
    )
