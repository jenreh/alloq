import reflex as rx
from alloq_commons.components.formatters import format_date_de
from alloq_commons.models.employee import Employee
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog
from appkit_ui.global_states import LoadingState


def _seniority_color(seniority: str) -> str:
    """Map seniority to badge color."""
    return rx.match(
        seniority,
        ("Advanced", "blue"),
        ("Senior", "grape"),
        ("Professional", "cyan"),
        ("Expert", "orange"),
        "gray",
    )


def _card_header(
    employee: Employee, section_key: str, is_expanded: rx.Var[bool]
) -> rx.Component:
    """Header: avatar on left, two rows (name+actions, job title) on right."""
    return mn.group(
        _employee_initials(employee),
        mn.stack(
            mn.group(
                mn.text(
                    f"{employee.first_name} {employee.last_name}",
                    size="md",
                    truncate=True,
                    flex="1",
                    style={"minWidth": 0},
                ),
                mn.group(
                    mn.box(
                        delete_dialog(
                            title="Mitarbeiter löschen",
                            content=f"{employee.first_name} {employee.last_name}",
                            on_click=TeamState.delete_employee(employee.id),
                            icon_button=True,
                            color="red",
                            variant="subtle",
                        ),
                        on_click=rx.stop_propagation,
                    ),
                    mn.action_icon(
                        rx.cond(
                            is_expanded,
                            rx.icon("chevron-up", size=18, stroke_width=1.5),
                            rx.icon("chevron-down", size=18, stroke_width=1.5),
                        ),
                        variant="subtle",
                        color="gray",
                        on_click=[
                            rx.stop_propagation,
                            TeamState.toggle_section_expanded(section_key),
                        ],
                    ),
                    gap="0",
                    align="center",
                    wrap="nowrap",
                ),
                justify="space-between",
                align="center",
                w="100%",
                wrap="nowrap",
                gap="md",
            ),
            mn.text(
                rx.cond(employee.job_title, employee.job_title, employee.seniority),
                size="sm",
                c="gray",
                truncate=True,
            ),
            gap="2px",
            flex="1",
            style={"minWidth": 0},
        ),
        align="flex-start",
        w="100%",
        wrap="nowrap",
        gap="md",
    )


def _employee_initials(employee: Employee) -> rx.Component:
    """Avatar with initials."""
    return mn.avatar(
        name=f"{employee.first_name} {employee.last_name}",
        color="var(--alloq-accent-strong)",
        size="md",
        radius="xl",
    )


def _role_tags(employee: Employee) -> rx.Component:
    """Show roles as skills tags."""
    return mn.stack(
        mn.text("Rollen", size="sm", c="dimmed", fw="500"),
        mn.group(
            rx.foreach(
                employee.role_names,
                lambda r: mn.badge(
                    r,
                    variant="light",
                    # color="yellow",
                    size="sm",
                    radius="sm",
                    style={
                        "textTransform": "none",
                        "fontWeight": "normal",
                        "backgroundColor": "var(--alloq-tag-bg)",
                    },
                ),
            ),
            gap="3px",
        ),
        gap="sm",
        w="100%",
    )


def _absence_list(employee: Employee) -> rx.Component:
    """Abwesenheiten als Liste mit farbigen Indikatoren."""
    return mn.stack(
        mn.group(
            mn.text("Abwesenheiten", size="sm", c="dimmed", fw="500"),
            mn.action_icon(
                rx.icon("plus", size=14, stroke_width=2),
                size="sm",
                variant="subtle",
                color="gray",
                on_click=[
                    rx.stop_propagation,
                    TeamState.select_employee_and_add_absence(employee.id),
                ],
            ),
            align="center",
            justify="space-between",
        ),
        mn.stack(
            rx.foreach(
                employee.absences,
                lambda absence: mn.group(
                    mn.text(
                        format_date_de(absence.start_date)
                        + " bis "
                        + format_date_de(absence.end_date),
                        size="0.66rem",
                        ff="'Roboto Mono', monospace",
                        style={
                            "color": "var(--alloq-item-text)",
                            "fontWeight": "400",
                        },
                    ),
                    mn.box(
                        delete_dialog(
                            title="Abwesenheit löschen",
                            content=f"{absence.start_date} bis {absence.end_date}",
                            on_click=TeamState.delete_absence(absence.id),
                            icon_button=True,
                            color="gray",
                            size="14px",
                            variant="subtle",
                        ),
                        on_click=rx.stop_propagation,
                    ),
                    align="center",
                    justify="space-between",
                    gap="xs",
                    style={
                        "backgroundColor": "var(--alloq-item-bg)",
                        "padding": "8px 12px",
                        "borderRadius": "6px",
                    },
                ),
            ),
            rx.cond(
                employee.absences.length() == 0,
                mn.group(
                    mn.text(
                        "Keine Abwesenheiten.",
                        ff="'Roboto Mono', monospace",
                        size="0.66rem",
                        c="dimmed",
                        align="center",
                    ),
                    gap="sm",
                    align="center",
                    style={
                        "backgroundColor": "var(--alloq-item-bg)",
                        "padding": "8px 12px",
                        "borderRadius": "6px",
                        "minHeight": "40px",
                    },
                ),
            ),
            gap="3px",
            w="100%",
        ),
        gap="xs",
        w="100%",
    )


def _productivity_indicator() -> rx.Component:
    """Productivity progress bar."""
    return mn.stack(
        mn.group(
            mn.text("verplant: ", size="xs", c="dimmed"),
            mn.text("65%", size="xs", fw="600"),
            mn.text(" (4w)", size="xs", c="dimmed"),
            gap="4px",
            justify="start",
        ),
        mn.progress(
            value=65, size="sm", radius="xl", color="var(--alloq-accent-strong)"
        ),
        gap="xs",
        mt="xs",
        style={"width": "100%"},
    )


def employee_card(employee: Employee, section_key: str) -> rx.Component:
    """Single employee card for grid view."""
    is_expanded = TeamState.expanded_sections.contains(section_key)
    return mn.box(
        mn.card(
            mn.stack(
                _card_header(employee, section_key, is_expanded),
                rx.cond(
                    is_expanded,
                    mn.stack(
                        _role_tags(employee),
                        _absence_list(employee),
                        gap="sm",
                        w="100%",
                    ),
                ),
                align="center",
                style={"width": "100%"},
                gap="sm",
            ),
            padding="lg",
            radius="lg",
            with_border=False,
            bg="transparent",
        ),
        width="306px",
        flex="0 0 auto",
        style={
            "background_color": "var(--alloq-fade-bg)",
            "cursor": rx.cond(LoadingState.is_loading, "wait", "pointer"),
            "_hover": {
                "background_color": rx.cond(
                    LoadingState.is_loading,
                    "var(--alloq-fade-bg)",
                    "var(--alloq-fade-bg-hover)",
                ),
                "cursor": rx.cond(LoadingState.is_loading, "wait", "pointer"),
            },
            "border_radius": "var(--mantine-radius-lg)",
        },
        on_click=[
            LoadingState.set_is_loading(True),
            TeamState.select_employee(employee.id),
        ],
    )


def _employee_section(title: str, employees: rx.Var, section_key: str) -> rx.Component:
    """Helper to render a titled section of employee cards."""
    return rx.cond(
        employees.length() > 0,
        mn.stack(
            mn.text(
                title,
                size="lg",
                fw="700",
            ),
            mn.flex(
                rx.foreach(
                    employees,
                    lambda employee: employee_card(employee, section_key),
                ),
                wrap="wrap",
                gap="md",
                direction="row",
                justify="flex-start",
                align="flex-start",
            ),
            gap="sm",
        ),
    )


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
        mn.stack(
            _employee_section("Meine Mitarbeiter", TeamState.my_employees, "my"),
            _employee_section(
                "Weitere Mitarbeiter", TeamState.other_employees, "other"
            ),
            gap="xl",
        ),
    )
