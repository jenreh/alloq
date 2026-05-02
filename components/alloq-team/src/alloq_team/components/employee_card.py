import reflex as rx
from alloq_team.models.employee import Employee
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog


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


class EmployeeCardState(rx.ComponentState):
    """Local state for employee card expansion."""

    is_expanded: bool = False

    def toggle(self) -> None:
        self.is_expanded = not self.is_expanded

    @classmethod
    def get_component(cls, employee: Employee, **props) -> rx.Component:
        """Single employee card for grid view."""
        return mn.box(
            mn.card(
                mn.stack(
                    cls._card_header(employee),
                    _productivity_indicator(),
                    rx.cond(
                        cls.is_expanded,
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
                "_hover": {
                    "background_color": "var(--alloq-fade-bg-hover)",
                    "cursor": "pointer",
                },
                "border_radius": "var(--mantine-radius-lg)",
            },
            on_click=TeamState.select_employee_and_edit(employee.id),
            **props,
        )

    @classmethod
    def _card_header(cls, employee: Employee) -> rx.Component:
        """Header containing avatar, name, job title, and actions."""
        return mn.group(
            _employee_initials(employee),
            mn.stack(
                mn.text(
                    f"{employee.first_name} {employee.last_name}",
                    size="md",
                    truncate=True,
                ),
                mn.text(
                    rx.cond(employee.job_title, employee.job_title, employee.seniority),
                    size="sm",
                    c="gray",
                    truncate=True,
                ),
                gap="2px",
                flex="1",
                mt="2px",
                style={"minWidth": 0},
            ),
            # Actions (Delete and Expand/Collapse)
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
                        cls.is_expanded,
                        rx.icon("chevron-up", size=18, stroke_width=1.5),
                        rx.icon("chevron-down", size=18, stroke_width=1.5),
                    ),
                    variant="subtle",
                    color="gray",
                    on_click=[rx.stop_propagation, cls.toggle],
                ),
                gap="0",
                align="flex-start",
                wrap="nowrap",
            ),
            justify="space-between",
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


def _format_date_de(date_var: rx.Var) -> rx.Var[str]:
    """Format YYYY-MM-DD to DD.MM.YYYY."""
    parts = date_var.to(str).split("-")
    return parts[2] + "." + parts[1] + "." + parts[0]


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
                    align="center",
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
                    ),
                    align="center",
                    gap="sm",
                    style={
                        "backgroundColor": "var(--alloq-item-bg)",
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
    )


def _productivity_indicator() -> rx.Component:
    """Productivity progress bar."""
    return mn.stack(
        mn.group(
            mn.text("Kapazität:", size="xs", c="dimmed", fw="500"),
            mn.text("65%", size="xs", fw="700"),
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


def employee_card(employee: Employee) -> rx.Component:
    """Single employee card for grid view."""
    return EmployeeCardState.create(employee=employee)


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
            align="flex-start",
        ),
    )
