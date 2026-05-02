import reflex as rx
from alloq_commons.models.project import Project
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog


def _status_label(project: Project) -> rx.Var[str]:
    """Return the project status label."""
    return rx.cond(
        project.risk_count > 0,
        "Risiko",
        rx.cond(project.current_progress > 0, "Aktiv", "Geplant"),
    )


def _status_color(project: Project) -> rx.Var[str]:
    """Return the project status badge color."""
    return rx.cond(
        project.risk_count > 0,
        "red",
        rx.cond(project.current_progress > 0, "green", "gray"),
    )


def _project_initials(project: Project) -> rx.Component:
    """Render project code avatar."""
    return mn.avatar(
        name=project.code,
        color="white",
        size="lg",
        radius="md",
        style={
            "backgroundColor": project.color,
            "color": "white",
            "fontWeight": "800",
        },
    )


def _metric(label: str, value: str | rx.Var[str]) -> rx.Component:
    """Render a project metric label/value pair."""
    return mn.stack(
        mn.text(label, size="0.65rem", fw="800", c="dimmed"),
        mn.text(value, size="sm", fw="800", c="var(--alloq-text)"),
        gap="2px",
    )


def _team_initial(initial: str) -> rx.Component:
    """Render one team member initial badge."""
    return mn.avatar(
        initial,
        size="xs",
        radius="xl",
        color="var(--alloq-accent-strong)",
    )


def project_card(project: Project) -> rx.Component:
    """Single project card for the overview grid."""
    return mn.box(
        mn.card(
            mn.stack(
                mn.group(
                    mn.group(
                        _project_initials(project),
                        mn.stack(
                            mn.text(
                                project.name_de,
                                size="md",
                                fw="800",
                                c="var(--alloq-text)",
                                truncate=True,
                            ),
                            mn.text(
                                project.code,
                                size="xs",
                                c="dimmed",
                                truncate=True,
                            ),
                            gap="2px",
                            style={"minWidth": 0},
                        ),
                        gap="md",
                        wrap="nowrap",
                        style={"minWidth": 0},
                    ),
                    mn.group(
                        mn.badge(
                            _status_label(project),
                            color=_status_color(project),
                            variant="light",
                            radius="xl",
                            size="sm",
                        ),
                        mn.box(
                            delete_dialog(
                                title="Projekt löschen",
                                content=project.name_de,
                                on_click=ProjectState.delete_project(project.id),
                                icon_button=True,
                                color="red",
                                variant="subtle",
                            ),
                            on_click=rx.stop_propagation,
                        ),
                        gap="xs",
                        align="flex-start",
                        wrap="nowrap",
                    ),
                    justify="space-between",
                    align="flex-start",
                    wrap="nowrap",
                    w="100%",
                ),
                mn.group(
                    _metric("BUDGET", project.budget.to_string() + " €"),
                    _metric("VERBRAUCHT", project.current_spent.to_string() + "%"),
                    _metric("FORTSCHRITT", project.current_progress.to_string() + "%"),
                    justify="space-between",
                    w="100%",
                ),
                mn.progress(
                    value=project.current_progress,
                    color=rx.cond(project.risk_count > 0, "red", project.color),
                    size="sm",
                    radius="xl",
                    bg="var(--alloq-meter-track)",
                    w="100%",
                ),
                mn.group(
                    mn.group(
                        rx.foreach(project.team_initials, _team_initial),
                        mn.text(
                            project.team_count.to_string() + " Mitarbeiter",
                            size="xs",
                            c="dimmed",
                            ml="xs",
                        ),
                        gap="2px",
                        wrap="nowrap",
                    ),
                    rx.cond(
                        project.risk_count > 0,
                        mn.group(
                            rx.icon("triangle-alert", size=14),
                            mn.text(
                                project.risk_count.to_string() + " Risiken",
                                size="xs",
                                fw="700",
                                c="var(--mantine-color-red-7)",
                            ),
                            gap="4px",
                        ),
                        mn.text("", size="xs"),
                    ),
                    justify="space-between",
                    align="center",
                    w="100%",
                ),
                gap="md",
            ),
            padding="lg",
            radius="lg",
            with_border=False,
            bg="transparent",
        ),
        width="306px",
        flex="0 0 auto",
        style={
            "backgroundColor": "var(--alloq-fade-bg)",
            "_hover": {
                "backgroundColor": "var(--alloq-fade-bg-hover)",
                "cursor": "pointer",
            },
            "borderRadius": "var(--mantine-radius-lg)",
            "minHeight": "198px",
        },
        on_click=ProjectState.select_project(project.id),
    )
