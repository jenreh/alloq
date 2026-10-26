"""Inspector on the right of the project list."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.access import CAN_EDIT, editor_only
from alloq_commons.components.formatters import de_number
from alloq_commons.components.list_view import (
    badge,
    inspector,
    inspector_section,
    key_values,
    meter,
    plain_button,
    tile,
)
from alloq_commons.components.toolbar import icon_button
from alloq_commons.models.project import Project, TeamMemberBadge
from alloq_project.components.project_parts import project_tile
from alloq_project.states.planning_grid_state import PlanningStore
from alloq_project.states.project_state import ProjectState
from reflex.vars import ObjectVar

import appkit_mantine as mn
from appkit_ui.global_states import LoadingState

MAX_TEAM = 6


def _selected() -> ObjectVar[Project]:
    return ProjectState.inspected.to(Project)


def _open(tab: str) -> list:
    return [
        LoadingState.set_is_loading(True),
        ProjectState.select_project_with_tab(_selected().id, tab),
    ]


def _heading(project: ObjectVar[Project]) -> rx.Component:
    return mn.group(
        project_tile(project, large=True),
        mn.stack(
            mn.text(project.name_de, fz="15px", fw=650, lh="1.25", line_clamp=2),
            mn.text(project.customer, fz="11.5px", c=theme.TEXT_MUTED, truncate="end"),
            gap=2,
            miw=0,
            flex="1",
        ),
        badge(project.state, ProjectState.inspected_tone),
        gap=12,
        wrap="nowrap",
        align="center",
    )


def _actions() -> rx.Component:
    return mn.group(
        editor_only(
            plain_button("Bearbeiten", _open("daten"), flex="1"),
            plain_button("Status erfassen", _open("status"), flex="1"),
            fallback=plain_button("Details", _open("status"), flex="1"),
        ),
        icon_button(
            "calendar-range",
            "In der Ressourcenplanung öffnen",
            PlanningStore.open_project(_selected().id),
        ),
        gap=8,
        wrap="nowrap",
    )


def _progress(label: str, value: rx.Var[int], color: str) -> rx.Component:
    return mn.stack(
        mn.group(
            mn.text(label, fz="12.5px"),
            mn.text(value.to(str) + " %", fz="12.5px", style=theme.NUMERIC),
            justify="space-between",
        ),
        meter(value, color),
        gap=4,
    )


def _member(member: ObjectVar[TeamMemberBadge]) -> rx.Component:
    return mn.group(
        tile(member.initials, member.color, round_=True),
        mn.text(member.name, fz="12.5px", truncate="end", flex="1", miw=0),
        mn.text(
            de_number(
                value=member.planned_pt,
                decimal_scale=2,
                minimum_fraction_digits=2,
                fixed_decimal_scale=True,
                suffix=" PT",
            ),
            fz="11.5px",
            c=theme.TEXT_MUTED,
            style=theme.NUMERIC,
            text_wrap="nowrap",
        ),
        gap=9,
        wrap="nowrap",
    )


def _team(project: ObjectVar[Project]) -> rx.Component:
    members = project.team_members.to(list[TeamMemberBadge])
    return inspector_section(
        "Team · " + members.length().to(str),
        rx.cond(
            members.length() > 0,
            mn.stack(rx.foreach(members[:MAX_TEAM], _member), gap=6),
            mn.text(
                "Noch keine Mitarbeiter zugewiesen.", fz="11.5px", c=theme.TEXT_MUTED
            ),
        ),
        rx.cond(
            members.length() > MAX_TEAM,
            mn.text(
                "und " + (members.length() - MAX_TEAM).to(str) + " weitere",
                fz="11.5px",
                c=theme.TEXT_MUTED,
            ),
            rx.fragment(),
        ),
    )


def _risks(project: ObjectVar[Project]) -> rx.Component:
    return inspector_section(
        "Risiken · " + project.risk_count.to(str),
        mn.group(
            mn.text(
                rx.match(
                    project.risk_count,
                    (0, "Keine Risiken erfasst."),
                    (1, "1 Risiko erfasst"),
                    project.risk_count.to(str) + " Risiken erfasst",
                ),
                fz="12.5px",
                c=rx.cond(project.risk_count > 0, theme.TEXT, theme.TEXT_MUTED),
                flex="1",
            ),
            plain_button("Öffnen", _open("risiken")),
            wrap="nowrap",
        ),
    )


def _pt(value: rx.Var) -> rx.Component:
    return de_number(value=value, decimal_scale=0, suffix=" PT")


def _booking_number(project: ObjectVar[Project]) -> rx.Component:
    return rx.cond(
        project.booking_number != "",
        mn.group(
            mn.text(
                project.booking_number,
                fz="inherit",
                lh="inherit",
                style=theme.NUMERIC,
                truncate="end",
                miw=0,
            ),
            mn.action_icon(
                rx.icon("copy", size=13, stroke_width=1.8),
                variant="subtle",
                color="gray",
                size=20,
                aria_label="Buchungsnummer kopieren",
                title="Buchungsnummer kopieren",
                on_click=[
                    rx.set_clipboard(project.booking_number),
                    rx.toast.success("Buchungsnummer kopiert", position="top-right"),
                ],
            ),
            gap=4,
            wrap="nowrap",
        ),
        mn.text("–", fz="inherit", lh="inherit", c=theme.TEXT_MUTED),
    )


def _date_input(project: ObjectVar[Project], field: str) -> rx.Component:
    return mn.date_input(
        value=(
            ProjectState.inspected_start_date
            if field == "start"
            else ProjectState.inspected_end_date
        ),
        on_change=lambda value: ProjectState.set_inspected_date_draft(
            project.id, field, value
        ),
        on_blur=ProjectState.save_inspected_dates(project.id),
        right_section=editor_only(
            mn.action_icon(
                rx.icon("calendar-check", size=14, stroke_width=1.8),
                variant="subtle",
                color="gray",
                size=22,
                aria_label="Heute",
                title="Heute",
                on_click=[
                    ProjectState.set_inspected_date_today(project.id, field),
                    ProjectState.save_inspected_dates(project.id),
                ],
            )
        ),
        disabled=~CAN_EDIT,
        right_section_pointer_events="all",
        clearable=False,
        locale="de",
        value_format="DD.MM.YYYY",
        size="xs",
    )


def _details(project: ObjectVar[Project]) -> rx.Component:
    return mn.stack(
        _heading(project),
        _actions(),
        inspector_section(
            "Eckdaten",
            key_values(
                (
                    "Status",
                    mn.select(
                        data=ProjectState.state_select_options,
                        value=project.state,
                        on_change=ProjectState.update_inspected_project_state(
                            project.id
                        ),
                        disabled=~CAN_EDIT,
                        clearable=False,
                        size="xs",
                    ),
                ),
                ("Kunde", project.customer),
                ("Kürzel", project.code),
                ("Buchungsnr.", _booking_number(project)),
                ("Start", _date_input(project, "start")),
                ("Ende", _date_input(project, "end")),
                ("Budget", de_number(value=project.budget, suffix=" €")),
                ("Bedarf", _pt(project.total_pt)),
                ("Geplant", _pt(project.planned_pt)),
            ),
        ),
        inspector_section(
            "Budget und Fortschritt",
            _progress("Verbraucht", project.current_spent, theme.ACCENT),
            _progress("Fortschritt", project.current_progress, theme.POSITIVE),
        ),
        _team(project),
        _risks(project),
        gap=18,
    )


def project_inspector() -> rx.Component:
    return inspector(
        rx.cond(
            ProjectState.inspected,
            _details(_selected()),
            mn.text("Kein Projekt ausgewählt.", fz="12.5px", c=theme.TEXT_MUTED),
        ),
        label="Projektdetails",
    )
