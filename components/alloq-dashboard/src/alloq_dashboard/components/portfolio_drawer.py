"""Drawer of the portfolio: a project, a role, a person or one matrix cell."""

from __future__ import annotations

from typing import Any, cast

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.modal_layout import DRAWER_CLASS
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_dashboard.components.portfolio_shared import (
    MUTED_TEXT,
    empty_text,
    link_button,
    number,
    tone_badge,
    tone_color,
)
from alloq_dashboard.models import (
    PersonAbsence,
    PersonBooking,
    PersonDetail,
    PersonWeek,
    PortfolioProject,
    PortfolioRoleLine,
    RiskItem,
    RoleDetail,
    RoleGapProject,
    RolePerson,
    RoleWeek,
)
from alloq_dashboard.states import PortfolioState
from alloq_dashboard.states.portfolio_state import (
    DRAWER_PERSON,
    DRAWER_PROJECT,
    DRAWER_RISKS,
    DRAWER_ROLE,
)

ROW_LINE = f"1px solid {theme.SEPARATOR}"
TRACK = theme.token("meter-track")
VALUE_TEXT: dict[str, Any] = {"fz": "13px", "fw": 500}
CELL_TEXT: dict[str, Any] = {"fz": "12.5px", "c": theme.TEXT}
ROLE_WEEK_COLUMNS = "64px repeat(3, minmax(0, 1fr))"
PERSON_WEEK_COLUMNS = "64px minmax(0, 1fr) 96px 52px"


def _fact(label: str, value: rx.Component) -> rx.Component:
    return mn.stack(mn.text(label, **MUTED_TEXT), value, gap=2)


def _facts(p: ObjectVar[PortfolioProject]) -> rx.Component:
    return mn.simple_grid(
        _fact("Status", mn.text(p.state, fz="13px", fw=500)),
        _fact("Fortschritt", number(p.progress, suffix=" %", fz="13px", fw=500)),
        _fact(
            "Zeit verstrichen",
            number(p.elapsed_percent, suffix=" %", fz="13px", fw=500),
        ),
        _fact("Ende", mn.text(p.end_label, fz="13px", fw=500)),
        _fact("Budget", number(p.budget, suffix=" €", fz="13px", fw=500)),
        _fact(
            "EAC",
            rx.cond(
                p.eac.to(float) > 0,
                mn.group(
                    number(p.eac, suffix=" €", decimal_scale=0, fz="13px", fw=500),
                    number(
                        p.eac_delta_percent,
                        prefix="(",
                        suffix=" %)",
                        maximum_fraction_digits=1,
                        **MUTED_TEXT,
                    ),
                    gap=4,
                ),
                mn.text("Keine Prognose", fz="13px", c=theme.TEXT_MUTED),
            ),
        ),
        cols=3,
        spacing="md",
        vertical_spacing="sm",
    )


def _role_line(line: ObjectVar[PortfolioRoleLine]) -> rx.Component:
    return mn.stack(
        mn.group(
            link_button(line.role_name, PortfolioState.open_role(line.role_id)),
            tone_badge(line.buffer_label.to(str) + " W", line.buffer_tone),
            justify="space-between",
        ),
        mn.group(
            number(
                line.remaining_days,
                prefix="Rest ",
                suffix=" PT",
                maximum_fraction_digits=1,
                **MUTED_TEXT,
            ),
            number(
                line.planned_days,
                prefix="geplant ",
                suffix=" PT",
                maximum_fraction_digits=1,
                **MUTED_TEXT,
            ),
            number(
                line.gap_days,
                prefix="Lücke ",
                suffix=" PT",
                maximum_fraction_digits=1,
                **MUTED_TEXT,
            ),
            gap="md",
        ),
        rx.cond(
            line.person_id.to(int) > 0,
            link_button(
                line.person_label,
                PortfolioState.open_person(line.person_id),
                fontSize="12.5px",
                fontWeight="500",
                color=tone_color(line.tone),
            ),
            mn.text(line.person_label, fz="12.5px", c=tone_color(line.tone)),
        ),
        mn.text(line.reason, **MUTED_TEXT),
        gap=4,
        py="sm",
        style={"borderTop": ROW_LINE},
    )


def _project_body() -> rx.Component:
    p = cast("ObjectVar[PortfolioProject]", PortfolioState.selected_project)
    return mn.stack(
        _facts(p),
        mn.text("Rollen und Puffer", fz="13px", fw=650, pt="sm"),
        rx.cond(
            p.roles.length() > 0,
            mn.stack(rx.foreach(p.roles, _role_line), gap=0),
            empty_text("Für dieses Projekt ist kein Bedarf je Rolle erfasst."),
        ),
        gap="sm",
    )


def _risk(r: ObjectVar[RiskItem]) -> rx.Component:
    return mn.group(
        mn.stack(
            mn.text(r.name, fz="13px", fw=600),
            mn.text(
                r.project_code.to(str) + " " + r.project_name.to(str), **MUTED_TEXT
            ),
            gap=2,
            miw=0,
        ),
        mn.badge(
            "Score " + r.score.to_string(),
            variant="light",
            color=cast(
                "rx.Var[str]",
                rx.match(r.severity, ("high", "red"), ("medium", "yellow"), "gray"),
            ),
        ),
        justify="space-between",
        wrap="nowrap",
        py="sm",
        style={"borderTop": ROW_LINE},
    )


def _risks_body() -> rx.Component:
    return rx.cond(
        PortfolioState.cell_risks.length() > 0,
        mn.stack(rx.foreach(PortfolioState.cell_risks, _risk), gap=0),
        empty_text("Keine Risiken in diesem Feld."),
    )


def _section(title: str) -> rx.Component:
    return mn.text(title, fz="13px", fw=650, pt="md")


def _grid(columns: str, *cells: rx.Component, header: bool = False) -> rx.Component:
    return mn.box(
        *cells,
        style={
            "display": "grid",
            "gridTemplateColumns": columns,
            "columnGap": "12px",
            "alignItems": "center",
            "padding": "5px 0",
            "borderTop": "0" if header else ROW_LINE,
        },
    )


def _head(label: str, *, end: bool = True) -> rx.Component:
    return mn.text(label, **MUTED_TEXT, ta="right" if end else "left")


def _days(value: rx.Var, c: str | rx.Var = theme.TEXT) -> rx.Component:
    return mn.box(
        number(value, fz="12.5px", c=c, maximum_fraction_digits=1),
        ta="right",
    )


def _role_week(w: ObjectVar[RoleWeek]) -> rx.Component:
    return _grid(
        ROLE_WEEK_COLUMNS,
        mn.text(w.label, **CELL_TEXT),
        _days(w.available_days),
        _days(w.planned_days),
        _days(w.free_days, tone_color(w.tone)),
    )


def _role_person(person: ObjectVar[RolePerson]) -> rx.Component:
    return mn.group(
        link_button(person.name, PortfolioState.open_person(person.employee_id)),
        mn.group(
            number(
                person.planned_days,
                prefix="geplant ",
                suffix=" PT",
                maximum_fraction_digits=1,
                **MUTED_TEXT,
            ),
            tone_badge("Ø " + person.avg_percent.to_string() + " %", person.tone),
            gap="sm",
            wrap="nowrap",
        ),
        justify="space-between",
        wrap="nowrap",
        py=6,
        style={"borderTop": ROW_LINE},
    )


def _gap_project(g: ObjectVar[RoleGapProject]) -> rx.Component:
    return mn.group(
        link_button(
            g.code.to(str) + " " + g.name.to(str),
            PortfolioState.open_project(g.project_id),
        ),
        mn.group(
            number(
                g.gap_days,
                prefix="Lücke ",
                suffix=" PT",
                maximum_fraction_digits=1,
                **MUTED_TEXT,
            ),
            tone_badge(g.buffer_label.to(str) + " W", g.buffer_tone),
            gap="sm",
            wrap="nowrap",
        ),
        justify="space-between",
        wrap="nowrap",
        py=6,
        style={"borderTop": ROW_LINE},
    )


def _role_body() -> rx.Component:
    r = cast("ObjectVar[RoleDetail]", PortfolioState.selected_role)
    return mn.stack(
        mn.simple_grid(
            _fact("Personen", number(r.employee_count, **VALUE_TEXT)),
            _fact(
                "Verfügbar",
                number(
                    r.available_days,
                    suffix=" PT",
                    maximum_fraction_digits=1,
                    **VALUE_TEXT,
                ),
            ),
            _fact(
                "Geplant",
                number(
                    r.planned_days,
                    suffix=" PT",
                    maximum_fraction_digits=1,
                    **VALUE_TEXT,
                ),
            ),
            _fact(
                "Frei",
                number(
                    r.free_days,
                    suffix=" PT",
                    maximum_fraction_digits=1,
                    fz="13px",
                    fw=500,
                    c=rx.cond(r.free_days.to(float) < 0, theme.NEGATIVE, theme.TEXT),
                ),
            ),
            cols=4,
            spacing="md",
        ),
        mn.text("Summen über die nächsten 13 Wochen.", **MUTED_TEXT),
        _section("Je Woche"),
        mn.stack(
            _grid(
                ROLE_WEEK_COLUMNS,
                _head("Woche", end=False),
                _head("Verfügbar"),
                _head("Geplant"),
                _head("Frei"),
                header=True,
            ),
            rx.foreach(r.weeks, _role_week),
            gap=0,
        ),
        _section("Personen mit der Rolle"),
        rx.cond(
            r.people.length() > 0,
            mn.stack(rx.foreach(r.people, _role_person), gap=0),
            empty_text("Im gewählten Bereich hat niemand diese Rolle."),
        ),
        _section("Projekte mit Lücke"),
        rx.cond(
            r.gap_projects.length() > 0,
            mn.stack(rx.foreach(r.gap_projects, _gap_project), gap=0),
            empty_text("Kein Projekt hat für diese Rolle Bedarf ohne Plan."),
        ),
        gap="xs",
    )


def _load_bar(w: ObjectVar[PersonWeek]) -> rx.Component:
    return mn.box(
        mn.box(
            style={
                "height": "100%",
                "width": w.bar_width,
                "borderRadius": "3px",
                "backgroundColor": rx.cond(
                    w.tone == "neg", theme.NEGATIVE, theme.ACCENT
                ),
            }
        ),
        style={
            "height": "6px",
            "borderRadius": "3px",
            "backgroundColor": TRACK,
            "overflow": "hidden",
        },
        custom_attrs={"aria-hidden": "true"},
    )


def _person_week(w: ObjectVar[PersonWeek]) -> rx.Component:
    return _grid(
        PERSON_WEEK_COLUMNS,
        mn.text(w.label, **CELL_TEXT),
        rx.cond(
            w.absent,
            mn.text("abwesend", **MUTED_TEXT),
            _load_bar(w),
        ),
        mn.group(
            number(w.booked_days, maximum_fraction_digits=1, **MUTED_TEXT),
            mn.text("von", **MUTED_TEXT),
            number(
                w.available_days, suffix=" PT", maximum_fraction_digits=1, **MUTED_TEXT
            ),
            gap=3,
            wrap="nowrap",
            justify="flex-end",
        ),
        mn.box(
            number(w.percent, suffix=" %", fz="12.5px", c=tone_color(w.tone), fw=500),
            ta="right",
        ),
    )


def _absence(a: ObjectVar[PersonAbsence]) -> rx.Component:
    return mn.group(
        mn.text(a.label, **CELL_TEXT),
        mn.text(a.days.to_string() + " Arbeitstage", **MUTED_TEXT),
        justify="space-between",
        py=6,
        style={"borderTop": ROW_LINE},
    )


def _booking(b: ObjectVar[PersonBooking]) -> rx.Component:
    project = b.code.to(str) + " " + b.name.to(str)
    return mn.group(
        mn.stack(
            rx.cond(
                b.in_scope,
                link_button(project, PortfolioState.open_project(b.project_id)),
                mn.text(project, fz="13px", fw=600),
            ),
            link_button(
                b.role_name,
                PortfolioState.open_role(b.role_id),
                fontSize="12px",
                fontWeight="500",
            ),
            gap=2,
            align="flex-start",
            miw=0,
        ),
        number(b.days, suffix=" PT", maximum_fraction_digits=1, fz="12.5px"),
        justify="space-between",
        wrap="nowrap",
        py=6,
        style={"borderTop": ROW_LINE},
    )


def _person_body() -> rx.Component:
    p = cast("ObjectVar[PersonDetail]", PortfolioState.selected_person)
    return mn.stack(
        mn.simple_grid(
            _fact(
                "Rollen",
                rx.cond(
                    p.roles_label != "",
                    mn.text(p.roles_label, **VALUE_TEXT),
                    mn.text("Keine", fz="13px", c=theme.TEXT_MUTED),
                ),
            ),
            _fact(
                "Ø Auslastung",
                number(
                    p.avg_percent, suffix=" %", fz="13px", fw=500, c=tone_color(p.tone)
                ),
            ),
            _fact(
                "Abwesend", number(p.absent_days, suffix=" Arbeitstage", **VALUE_TEXT)
            ),
            cols=3,
            spacing="md",
        ),
        mn.text("Werte für die nächsten 13 Wochen.", **MUTED_TEXT),
        _section("Auslastung je Woche"),
        mn.stack(
            _grid(
                PERSON_WEEK_COLUMNS,
                _head("Woche", end=False),
                _head("Auslastung", end=False),
                _head("Gebucht"),
                _head("%"),
                header=True,
            ),
            rx.foreach(p.weeks, _person_week),
            gap=0,
        ),
        _section("Abwesenheiten"),
        rx.cond(
            p.absences.length() > 0,
            mn.stack(rx.foreach(p.absences, _absence), gap=0),
            empty_text("Keine Abwesenheit in den nächsten 13 Wochen."),
        ),
        _section("Gebucht auf"),
        rx.cond(
            p.bookings.length() > 0,
            mn.stack(rx.foreach(p.bookings, _booking), gap=0),
            empty_text("In den nächsten 13 Wochen auf kein Projekt gebucht."),
        ),
        gap="xs",
    )


def _title() -> rx.Var[str]:
    project = cast("ObjectVar[PortfolioProject]", PortfolioState.selected_project)
    role = cast("ObjectVar[RoleDetail]", PortfolioState.selected_role)
    person = cast("ObjectVar[PersonDetail]", PortfolioState.selected_person)
    return cast(
        "rx.Var[str]",
        rx.match(
            PortfolioState.drawer,
            (DRAWER_PROJECT, project.code.to(str) + " " + project.name.to(str)),
            (DRAWER_ROLE, "Rolle " + role.role_name.to(str)),
            (DRAWER_PERSON, person.name.to(str)),
            (DRAWER_RISKS, PortfolioState.cell_title),
            "Details",
        ),
    )


def portfolio_drawer() -> rx.Component:
    return mn.drawer(
        mn.box(
            rx.match(
                PortfolioState.drawer,
                (DRAWER_PROJECT, _project_body()),
                (DRAWER_ROLE, _role_body()),
                (DRAWER_PERSON, _person_body()),
                (DRAWER_RISKS, _risks_body()),
                rx.fragment(),
            ),
            class_name="alloq-modal-scroll",
        ),
        title=_title(),
        opened=PortfolioState.drawer != "",
        on_close=PortfolioState.close_drawer,
        position="right",
        size="lg",
        overlay_props={"backgroundOpacity": 0.3, "blur": 3},
        offset="15px",
        radius="md",
        class_name=DRAWER_CLASS,
        with_close_button=True,
        close_on_click_outside=True,
    )
