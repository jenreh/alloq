import reflex as rx
from alloq_team.models.employee import Employee
from alloq_team.states.team_state import TeamState

import appkit_mantine as mn


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


def _employee_initials(employee: Employee) -> rx.Component:
    """Avatar with initials."""
    return mn.indicator(
        mn.avatar(
            color="initials",
            name=f"{employee.first_name} {employee.last_name}",
            size="lg",
            radius="xl",
        ),
        inline=False,
        size=14,
        offset=5,
        position="bottom-end",
        color="green",
        with_border=True,
    )


def _card_header(employee: Employee) -> rx.Component:
    """Header containing avatar and options menu."""
    return mn.group(
        _employee_initials(employee),
        mn.action_icon(
            rx.icon("more-horizontal", size=20),
            variant="subtle",
            color="gray",
        ),
        justify="space-between",
        align="flex-start",
        w="100%",
    )


def _social_icons() -> rx.Component:
    """Group of social media icons."""
    return mn.group(
        mn.action_icon(rx.icon("twitter", size=16), variant="default", size="sm"),
        mn.action_icon(rx.icon("linkedin", size=16), variant="default", size="sm"),
        mn.action_icon(rx.icon("instagram", size=16), variant="default", size="sm"),
        gap="xs",
    )


def _profile_info(employee: Employee) -> rx.Component:
    """Employee name, seniority, job title and location."""
    return mn.stack(
        mn.text(
            f"{employee.first_name} {employee.last_name}",
            fw="700",
            size="xl",
            style={"color": "#111827"},
        ),
        mn.text(
            rx.cond(employee.job_title != "", employee.job_title, employee.seniority),
            size="md",
            c="dimmed",
            fw="500",
        ),
        mn.group(
            mn.text(
                rx.cond(employee.location != "", employee.location, "Kein Standort"),
                size="md",
                c="dimmed",
            ),
            _social_icons(),
            justify="space-between",
            w="100%",
            mt="xs",
        ),
        gap="2px",
    )


def _stat_item(label: str, value: str) -> rx.Component:
    """Individual statistic item."""
    return mn.stack(
        mn.text(label, size="xs", c="dimmed", ta="center", fw="500"),
        mn.text(value, size="lg", fw="700", ta="center", c="#111827"),
        gap="4px",
        align="center",
    )


def _stats_row(employee: Employee) -> rx.Component:
    """Row of employee statistics."""
    return mn.group(
        _stat_item("Rollen", employee.role_ids.length().to_string()),
        _stat_item("Projekte", "22"),
        _stat_item("Aktiv", "3"),
        grow=True,
        mt="lg",
        w="100%",
    )


def _productivity_indicator() -> rx.Component:
    """Productivity progress bar."""
    return mn.stack(
        mn.group(
            mn.text("Productivity:", size="xs", c="dimmed", fw="500"),
            mn.text("65%", size="xs", fw="700", style={"color": "#4b6bfb"}),
            gap="4px",
            justify="center",
        ),
        mn.progress(value=65, size="sm", radius="xl", color="#4b6bfb"),
        gap="xs",
        mt="md",
        style={"width": "100%"},
    )


def employee_card(employee: Employee) -> rx.Component:
    """Single employee card for grid view."""
    return mn.box(
        mn.card(
            mn.stack(
                _card_header(employee),
                _profile_info(employee),
                _stats_row(employee),
                _productivity_indicator(),
                align="center",
                style={"width": "100%"},
                gap="xs",
            ),
            padding="lg",
            radius="lg",
            with_border=False,
            bg="transparent",
        ),
        width="306px",
        flex="0 0 auto",
        style={
            "cursor": "pointer",
            "background_color": "rgba(255, 255, 255, 0.5)",
            "_hover": {"background_color": "rgba(255, 255, 255, 0.8)"},
            "border_radius": "var(--mantine-radius-lg)",
        },
        on_click=lambda: TeamState.select_employee(employee.id),
    )
