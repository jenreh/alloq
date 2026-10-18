"""Cards: resource-critical path per project and capacity per role."""

from __future__ import annotations

from typing import Any

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_dashboard.components.portfolio_shared import (
    MUTED_TEXT,
    card,
    empty_text,
    number,
    tone_badge,
    tone_color,
)
from alloq_dashboard.models import PortfolioKpi, PortfolioProject, RoleDemand
from alloq_dashboard.states import PortfolioState

ROW_LINE = f"1px solid {theme.SEPARATOR}"
PILL: dict[str, Any] = {
    "display": "inline-flex",
    "alignItems": "center",
    "height": "22px",
    "padding": "0 8px",
    "borderRadius": "6px",
    "fontSize": "12px",
    "fontWeight": "500",
    "whiteSpace": "nowrap",
    "backgroundColor": theme.SURFACE_MUTED,
    "boxShadow": f"inset 0 0 0 1px {theme.BORDER}",
    "color": theme.TEXT,
}
PILL_BUTTON: dict[str, Any] = {
    **PILL,
    "cursor": "pointer",
    "border": "0",
    "_hover": {"boxShadow": f"inset 0 0 0 1px {theme.ACCENT}"},
}
TRACK = theme.token("meter-track")
GAP_ALERT_DAYS = 15


def _arrow() -> rx.Component:
    return mn.text("→", fz="12px", c=theme.TEXT_TERTIARY, aria_hidden="true")


def _chain(p: ObjectVar[PortfolioProject]) -> rx.Component:
    project_pill = rx.el.button(
        mn.text(p.code, ff="monospace", fz="11px", c=theme.TEXT_MUTED, span=True),
        mn.text(" " + p.name.to(str), span=True, truncate="end"),
        type="button",
        on_click=PortfolioState.open_project(p.id),
        style={**PILL_BUTTON, "gap": "4px", "minWidth": "0"},
    )
    role_pill = rx.el.button(
        p.weakest.role_name,
        type="button",
        on_click=PortfolioState.open_role(p.weakest.role_id),
        style=PILL_BUTTON,
    )
    person_color = tone_color(p.weakest.tone)
    person_pill = rx.cond(
        p.weakest.person_id.to(int) > 0,
        rx.el.button(
            p.weakest.person_label,
            type="button",
            on_click=PortfolioState.open_person(p.weakest.person_id),
            style={**PILL_BUTTON, "color": person_color},
        ),
        mn.box(p.weakest.person_label, style={**PILL, "color": person_color}),
    )
    return mn.group(
        mn.box(tone_badge(p.buffer_label.to(str) + " W", p.buffer_tone), w="52px"),
        mn.stack(
            mn.group(
                project_pill,
                _arrow(),
                role_pill,
                _arrow(),
                person_pill,
                gap=6,
                wrap="nowrap",
                miw=0,
            ),
            mn.text(p.weakest.reason, **MUTED_TEXT, truncate="end"),
            gap=3,
            miw=0,
            flex="1",
        ),
        gap="sm",
        wrap="nowrap",
        py=7,
        style={"borderTop": ROW_LINE},
    )


def portfolio_chains_card() -> rx.Component:
    data = PortfolioState.data.to(PortfolioKpi)
    body = mn.stack(
        rx.cond(
            data.chains.length() > 0,
            mn.stack(rx.foreach(data.chains, _chain), gap=0),
            empty_text("Alle Projekte haben mindestens 4 Wochen Puffer."),
        ),
        rx.cond(
            data.comfortable_label != "",
            mn.text(
                data.comfortable_label,
                **MUTED_TEXT,
                pt=8,
                style={"borderTop": ROW_LINE},
            ),
            rx.fragment(),
        ),
        gap=0,
    )
    return card(
        "Kritischer Ressourcenpfad",
        "Je Projekt das schwächste Glied. Sortiert nach Puffer in Wochen.",
        body,
        is_loading=PortfolioState.is_loading,
        aside=mn.text("Projekt → Rolle → Person → Grund", **MUTED_TEXT),
    )


def _bar(r: ObjectVar[RoleDemand]) -> rx.Component:
    base: dict[str, Any] = {"position": "absolute", "top": "3px", "height": "6px"}
    return mn.box(
        mn.box(
            style={
                **base,
                "left": "0",
                "width": "80%",
                "borderRadius": "3px",
                "backgroundColor": TRACK,
            }
        ),
        mn.box(
            style={
                **base,
                "left": "0",
                "width": r.plan_width,
                "borderRadius": "3px",
                "backgroundColor": theme.ACCENT,
            }
        ),
        mn.box(
            style={
                **base,
                "left": "80%",
                "width": r.over_width,
                "borderRadius": "0 3px 3px 0",
                "backgroundColor": theme.NEGATIVE,
            }
        ),
        mn.box(
            style={
                "position": "absolute",
                "top": "0",
                "left": r.need_left,
                "width": "2px",
                "height": "12px",
                "borderRadius": "1px",
                "backgroundColor": theme.TEXT,
            }
        ),
        style={"position": "relative", "height": "12px", "flex": "1"},
        custom_attrs={"aria-hidden": "true"},
    )


def _role(r: ObjectVar[RoleDemand]) -> rx.Component:
    gap_color = rx.cond(
        r.gap_days.to(float) >= GAP_ALERT_DAYS, theme.NEGATIVE, theme.TEXT_MUTED
    )
    return mn.stack(
        mn.group(
            mn.group(
                mn.text(r.role_name, fz="12.5px", fw=600, c=theme.TEXT),
                mn.text(r.employee_count.to_string() + " Pers.", **MUTED_TEXT),
                gap=6,
                align="baseline",
            ),
            number(
                r.gap_days,
                prefix="Lücke ",
                suffix=" PT",
                fz="12px",
                c=gap_color,
                maximum_fraction_digits=1,
            ),
            justify="space-between",
            align="baseline",
        ),
        mn.group(
            _bar(r),
            mn.group(
                number(r.planned_days, maximum_fraction_digits=1, **MUTED_TEXT),
                mn.text("von", **MUTED_TEXT),
                number(r.need_days, maximum_fraction_digits=1, **MUTED_TEXT),
                gap=3,
                wrap="nowrap",
                w="96px",
                justify="flex-end",
            ),
            gap="sm",
            wrap="nowrap",
        ),
        gap=4,
        py=6,
        style={"borderTop": ROW_LINE},
    )


def portfolio_roles_card() -> rx.Component:
    data = PortfolioState.data.to(PortfolioKpi)
    return card(
        "Kapazität je Rolle",
        "13 Wochen. Blau: geplant. Strich: Bedarf. Grau: verfügbar.",
        rx.cond(
            data.roles.length() > 0,
            mn.stack(rx.foreach(data.roles, _role), gap=0),
            empty_text("Keine Rollen mit Personen im gewählten Bereich."),
        ),
        is_loading=PortfolioState.is_loading,
        aside=number(
            data.gap_total,
            prefix="Lücke ",
            suffix=" PT",
            maximum_fraction_digits=1,
        ),
    )
