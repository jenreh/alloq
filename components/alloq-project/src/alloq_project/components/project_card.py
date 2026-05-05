import reflex as rx
from alloq_commons.models.project import Project, TeamMemberBadge
from alloq_project.states.project_state import ProjectState

import appkit_mantine as mn
from appkit_ui.components.dialogs import delete_dialog


def _format_date_de(date_var: rx.Var) -> rx.Var[str]:
    """Format YYYY-MM-DD to DD.MM.YYYY."""
    parts = date_var.to(str).split("-")
    month_name = rx.match(
        parts[1],
        ("01", "Jan"),
        ("02", "Feb"),
        ("03", "März"),
        ("04", "Apr"),
        ("05", "Mai"),
        ("06", "Juni"),
        ("07", "Juli"),
        ("08", "Aug"),
        ("09", "Sep"),
        ("10", "Okt"),
        ("11", "Nov"),
        ("12", "Dez"),
        "",
    )
    return f"{parts[2]}. {month_name} {parts[0]}"


def _status_color(state: rx.Var[str]) -> rx.Var[str]:
    """Return the project status badge color."""
    return rx.match(
        state,
        ("Geplant", "gray"),
        ("Aktiv", "green"),
        ("Risiko", "red"),
        ("Abgeschlossen", "blue"),
        "gray",
    )


def _project_initials(project: Project) -> rx.Component:
    """Render project customer avatar."""
    customer_display = rx.cond(project.customer != "", project.customer, project.code)
    return mn.avatar(
        name=customer_display,
        color="white",
        size="lg",
        radius="md",
        style={
            "backgroundColor": project.color,
            "color": "white",
            "fontWeight": "800",
        },
    )


def _metric(label: str, value: str | rx.Var | rx.Component) -> rx.Component:
    """Render a project metric label/value pair."""
    return mn.stack(
        mn.text(label, size="0.65rem", fw="800", c="dimmed"),
        mn.text(value, size="sm", fw="800", c="var(--alloq-text)"),
        gap="2px",
    )


def _team_initial(member: TeamMemberBadge) -> rx.Component:
    """Render one team member initial badge with a tooltip showing the full name."""
    return mn.tooltip(
        mn.avatar(
            member.initials,
            size="md",
            radius="xl",
            color="var(--alloq-accent-strong)",
        ),
        label=member.name,
    )


def project_card(project: Project) -> rx.Component:
    """Single project card for the overview grid."""
    customer_display = rx.cond(project.customer != "", project.customer, project.code)
    return mn.box(
        mn.card(
            mn.stack(
                mn.group(
                    _project_initials(project),
                    mn.stack(
                        mn.group(
                            mn.text(
                                project.name_de,
                                size="md",
                                fw="800",
                                c="var(--alloq-text)",
                                truncate=True,
                                style={"flex": 1},
                            ),
                            mn.group(
                                mn.badge(
                                    project.state,
                                    color=_status_color(project.state),
                                    variant="light",
                                    radius="xl",
                                    size="md",
                                    left_section=mn.text("●", size="8px"),
                                    style={
                                        "textTransform": "none",
                                        "fontWeight": "700",
                                    },
                                ),
                                mn.box(
                                    delete_dialog(
                                        title="Projekt löschen",
                                        content=project.name_de,
                                        on_click=ProjectState.delete_project(
                                            project.id
                                        ),
                                        icon_button=True,
                                        color="red",
                                        variant="subtle",
                                    ),
                                    on_click=rx.stop_propagation,
                                ),
                                gap="xs",
                                align="center",
                                wrap="nowrap",
                            ),
                            justify="space-between",
                            align="center",
                            wrap="nowrap",
                            w="100%",
                        ),
                        mn.text(
                            customer_display
                            + " \u00b7 "
                            + _format_date_de(project.start_date)
                            + " \u2192 "
                            + _format_date_de(project.end_date),
                            size="xs",
                            c="dimmed",
                            truncate=True,
                        ),
                        gap="2px",
                        style={"minWidth": 0, "flex": 1},
                    ),
                    gap="md",
                    wrap="nowrap",
                    align="flex-start",
                    w="100%",
                ),
                mn.group(
                    _metric(
                        "BUDGET",
                        mn.number_formatter(
                            value=project.budget,
                            thousand_separator=".",
                            decimal_separator=",",
                            suffix=" €",
                        ),
                    ),
                    _metric(
                        "VERBRAUCHT",
                        mn.number_formatter(value=project.current_spent, suffix="%"),
                    ),
                    _metric(
                        "FORTSCHRITT",
                        mn.number_formatter(value=project.current_progress, suffix="%"),
                    ),
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
                        mn.avatar.group(
                            rx.foreach(project.team_members, _team_initial),
                        ),
                        mn.text(
                            project.team_initials.length().to_string() + " Mitarbeiter",
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
        width="420px",
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
