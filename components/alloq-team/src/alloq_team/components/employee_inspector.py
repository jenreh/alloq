"""Inspector on the right of the team list."""

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.list_view import (
    badge,
    inspector,
    inspector_section,
    key_values,
    plain_button,
)
from alloq_commons.components.toolbar import icon_button
from alloq_team.components.employee_parts import employee_avatar, load_label
from alloq_team.services.team_overview import TeamAssignment, TeamWeek
from alloq_team.states.team_list_state import TeamDetail
from alloq_team.states.team_state import TeamState
from reflex.vars import ObjectVar

import appkit_mantine as mn
from appkit_ui.global_states import LoadingState

FULL_PERCENT = 100


def _week_tone(week: ObjectVar[TeamWeek]) -> rx.Var[str]:
    return rx.cond(
        week.absent,
        theme.TEXT_TERTIARY,
        rx.cond(
            week.percent > FULL_PERCENT,
            theme.NEGATIVE,
            theme.POSITIVE,
        ),
    ).to(str)


def _bar(week: ObjectVar[TeamWeek]) -> rx.Component:
    height = rx.cond(week.percent > FULL_PERCENT, FULL_PERCENT, week.percent).to(int)
    return mn.tooltip(
        mn.box(
            mn.box(
                style={
                    "height": rx.cond(week.absent, FULL_PERCENT, height).to(str) + "%",
                    "minHeight": "2px",
                    "background": _week_tone(week),
                    "borderRadius": "3px",
                }
            ),
            style={
                "height": "64px",
                "display": "flex",
                "flexDirection": "column",
                "justifyContent": "flex-end",
                "background": theme.token("border"),
                "borderRadius": "3px",
                "overflow": "hidden",
            },
        ),
        label=week.label
        + ": "
        + rx.cond(week.absent, "abwesend", week.percent.to(str) + " %"),
        position="top",
    )


def _weeks(row: ObjectVar[TeamDetail]) -> rx.Component:
    weeks = row.weeks.to(list[TeamWeek])
    return inspector_section(
        "Auslastung · nächste 8 Wochen",
        mn.box(
            rx.foreach(weeks, _bar),
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(8, minmax(0, 1fr))",
                "gap": "6px",
                "alignItems": "end",
            },
            custom_attrs={"role": "img", "aria-label": "Auslastung je Woche"},
        ),
        rx.cond(
            weeks.length() > 0,
            mn.group(
                mn.text(weeks[0].label, fz="11.5px", c=theme.TEXT_MUTED),
                mn.text(weeks[-1].label, fz="11.5px", c=theme.TEXT_MUTED),
                justify="space-between",
            ),
            rx.fragment(),
        ),
    )


def _assignment(item: ObjectVar[TeamAssignment]) -> rx.Component:
    return mn.group(
        mn.box(
            w=9,
            h=9,
            mx=2,
            style={"borderRadius": "50%", "background": item.color, "flexShrink": "0"},
        ),
        mn.text(item.name, fz="12.5px", flex="1", miw=0, truncate="end"),
        mn.text(
            item.days.to(str) + " PT",
            fz="12px",
            c=theme.TEXT_MUTED,
            style=theme.NUMERIC,
        ),
        gap=9,
        wrap="nowrap",
    )


def _assignments(row: ObjectVar[TeamDetail]) -> rx.Component:
    items = row.assignments.to(list[TeamAssignment])
    return inspector_section(
        "Zuweisungen · 8 Wochen",
        rx.cond(
            items.length() > 0,
            mn.stack(rx.foreach(items, _assignment), gap=6),
            mn.text("Keine Zuweisungen.", fz="11.5px", c=theme.TEXT_MUTED),
        ),
    )


def _absences(row: ObjectVar[TeamDetail]) -> rx.Component:
    items = row.absences.to(list[str])
    return inspector_section(
        "Abwesenheiten",
        rx.cond(
            items.length() > 0,
            mn.stack(
                rx.foreach(items, lambda text: mn.text(text, fz="12.5px")),
                gap=4,
            ),
            mn.text("Keine geplant.", fz="11.5px", c=theme.TEXT_MUTED),
        ),
    )


def _heading(row: ObjectVar[TeamDetail]) -> rx.Component:
    return mn.group(
        employee_avatar(row, large=True),
        mn.stack(
            mn.text(row.name, fz="15px", fw=650, lh="1.25"),
            mn.text(row.subtitle, fz="11.5px", c=theme.TEXT_MUTED, truncate="end"),
            gap=2,
            miw=0,
            flex="1",
        ),
        badge(load_label(row), row.load_tone),
        gap=12,
        wrap="nowrap",
    )


def _actions(row: ObjectVar[TeamDetail]) -> rx.Component:
    return mn.group(
        plain_button(
            "Bearbeiten",
            [LoadingState.set_is_loading(True), TeamState.select_employee(row.id)],  # ty: ignore[invalid-argument-type]
            flex="1",
        ),
        plain_button(
            "Abwesenheit",
            TeamState.select_employee_and_add_absence(row.id),  # ty: ignore[invalid-argument-type]
            flex="1",
        ),
        icon_button(
            "calendar-range",
            "In der Ressourcenplanung öffnen",
            rx.redirect("/plan?employee=" + row.id.to(str)),
        ),
        gap=8,
        wrap="nowrap",
    )


def _details(row: ObjectVar[TeamDetail]) -> rx.Component:
    return mn.stack(
        _heading(row),
        _actions(row),
        inspector_section(
            "Stammdaten",
            key_values(
                ("Rollen", rx.cond(row.roles != "", row.roles, "–")),
                ("Standort", rx.cond(row.location != "", row.location, "–")),
                ("Abteilung", rx.cond(row.department != "", row.department, "–")),
                ("Wochenstunden", row.hours.to(str) + " h"),
                ("Stellenanteil", row.workload_percent.to(str) + " %"),
                ("Frei (8 Wochen)", row.free_days.to(str) + " PT"),
            ),
        ),
        _weeks(row),
        _assignments(row),
        _absences(row),
        gap=18,
    )


def employee_inspector() -> rx.Component:
    return inspector(
        rx.cond(
            TeamState.inspected,
            _details(TeamState.inspected.to(TeamDetail)),
            mn.text("Niemand ausgewählt.", fz="12.5px", c=theme.TEXT_MUTED),
        ),
        label="Mitarbeiterdetails",
    )
