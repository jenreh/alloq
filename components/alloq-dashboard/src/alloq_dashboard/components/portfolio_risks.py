"""Card: open risks as a 5x5 matrix of probability and impact."""

from __future__ import annotations

from typing import cast

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_dashboard.components.portfolio_shared import (
    MUTED_TEXT,
    card,
    empty_text,
    number,
)
from alloq_dashboard.models import PortfolioKpi, RiskMatrixCell, RiskMatrixRow
from alloq_dashboard.states import PortfolioState

CELL_PX = "46px"
_BAND_TOKENS = (
    ("r1", "risk-low"),
    ("r2", "risk-medium"),
    ("r3", "risk-high"),
    ("r4", "risk-very-high"),
    ("r5", "risk-critical"),
)


def _band_color(band: rx.Var[str]) -> rx.Var:
    return cast(
        "rx.Var",
        rx.match(
            band,
            *((key, theme.token(name)) for key, name in _BAND_TOKENS),
            theme.token("risk-low"),
        ),
    )


def _axis(text: rx.Var | str) -> rx.Component:
    return mn.text(text, fz="11px", c=theme.TEXT_MUTED, ta="center")


def _cell(c: ObjectVar[RiskMatrixCell]) -> rx.Component:
    return rx.el.button(
        rx.cond(c.count.to(int) > 0, c.count.to_string(), ""),
        type="button",
        disabled=c.count.to(int) == 0,
        on_click=PortfolioState.open_risk_cell(c.key),
        aria_label="Wahrscheinlichkeit "
        + c.probability.to_string()
        + ", Auswirkung "
        + c.impact.to_string()
        + ": "
        + c.count.to_string()
        + " Risiken",
        style={
            "height": CELL_PX,
            "border": "0",
            "borderRadius": "6px",
            "backgroundColor": _band_color(c.band),
            "color": theme.TEXT,
            "fontSize": "15px",
            "fontWeight": "650",
            "fontVariantNumeric": "tabular-nums",
            "cursor": rx.cond(c.count.to(int) > 0, "pointer", "default"),
        },
    )


def _row(row: ObjectVar[RiskMatrixRow]) -> rx.Component:
    return rx.fragment(
        _axis(row.probability.to_string()),
        rx.foreach(row.cells, _cell),
    )


def _matrix(data: ObjectVar[PortfolioKpi]) -> rx.Component:
    return mn.box(
        rx.foreach(data.matrix, _row),
        mn.box(),
        *(_axis(str(i)) for i in range(1, 6)),
        style={
            "display": "grid",
            "gridTemplateColumns": f"18px repeat(5, {CELL_PX})",
            "gap": "4px",
            "alignItems": "center",
        },
    )


def _count(label: str, value: rx.Var[int], color: str) -> rx.Component:
    return mn.stack(
        mn.text(label, **MUTED_TEXT),
        number(value, fz="20px", fw=650, c=color),
        gap=0,
    )


def _severity(data: ObjectVar[PortfolioKpi]) -> rx.Component:
    return mn.stack(
        _count("Hoch, Score über 15", data.risk_high, theme.NEGATIVE),
        _count("Mittel, 5 bis 15", data.risk_medium, theme.TEXT),
        _count("Niedrig, bis 4", data.risk_low, theme.TEXT),
        mn.text("Senkrecht: Wahrscheinlichkeit. Waagerecht: Auswirkung.", **MUTED_TEXT),
        gap="sm",
        miw=0,
    )


def portfolio_risks_card() -> rx.Component:
    data = PortfolioState.data.to(PortfolioKpi)
    return card(
        "Offene Risiken",
        "Wahrscheinlichkeit mal Auswirkung, je 1 bis 5",
        rx.cond(
            data.risk_open_total > 0,
            mn.group(
                _matrix(data),
                _severity(data),
                align="flex-start",
                gap="lg",
                wrap="nowrap",
                pt="xs",
            ),
            empty_text("Keine offenen Risiken."),
        ),
        is_loading=PortfolioState.is_loading,
        aside=mn.text(data.risk_open_total.to_string() + " offen", **MUTED_TEXT),
    )
