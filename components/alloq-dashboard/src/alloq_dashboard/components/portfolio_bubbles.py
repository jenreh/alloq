"""Card: time elapsed vs. progress per active project."""

from __future__ import annotations

from typing import Any, cast

import reflex as rx
from alloq_commons import theme
from reflex.vars import ObjectVar

import appkit_mantine as mn
from alloq_dashboard.components.portfolio_shared import MUTED_TEXT, card, empty_text
from alloq_dashboard.models import PortfolioBubble, PortfolioKpi
from alloq_dashboard.states import PortfolioState

PLOT_HEIGHT = "260px"
TICKS = (25, 50, 75)
SEPARATOR = theme.SEPARATOR
BORDER_STRONG = theme.token("border-strong")
# Diagonal from (0 %, 0 %) to (100 %, 100 %) of the plot box.
DIAGONAL_SVG = (
    "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' "
    "viewBox='0 0 100 100' preserveAspectRatio='none'><line x1='0' y1='100' "
    "x2='100' y2='0' stroke='%23B9B9C1' stroke-width='1' stroke-dasharray='3 3' "
    "vector-effect='non-scaling-stroke'/></svg>\")"
)

_FILL = {
    "green": (theme.token("positive-soft"), theme.POSITIVE),
    "yellow": (theme.token("warning-soft"), theme.WARNING),
    "red": (theme.token("negative-soft"), theme.NEGATIVE),
}


def _health(value: rx.Var[str], index: int) -> rx.Var:
    return cast(
        "rx.Var",
        rx.match(
            value,
            *((key, colors[index]) for key, colors in _FILL.items()),
            (theme.SURFACE_MUTED, BORDER_STRONG)[index],
        ),
    )


def _bubble(b: ObjectVar[PortfolioBubble]) -> rx.Component:
    style: dict[str, Any] = {
        "position": "absolute",
        "left": b.left,
        "top": b.top,
        "width": b.size,
        "height": b.size,
        "borderRadius": "50%",
        "border": "2px solid",
        "borderColor": _health(b.health, 1),
        "backgroundColor": _health(b.health, 0),
        "outline": rx.cond(b.negative_buffer, f"1.5px dashed {theme.NEGATIVE}", "none"),
        "outlineOffset": "3px",
        "cursor": "pointer",
        "padding": "0",
    }
    return rx.fragment(
        mn.tooltip(
            rx.el.button(
                type="button",
                on_click=PortfolioState.open_project(b.project_id),
                style=style,
                aria_label=b.tooltip,
            ),
            label=b.tooltip,
            with_arrow=True,
        ),
        mn.text(
            b.code,
            fz="11.5px",
            fw=600,
            c=theme.TEXT,
            style={
                "position": "absolute",
                "left": b.label_left,
                "top": b.label_top,
                "whiteSpace": "nowrap",
                "pointerEvents": "none",
            },
        ),
    )


def _grid_lines() -> list[rx.Component]:
    lines: list[rx.Component] = []
    for tick in TICKS:
        lines.append(
            mn.box(
                style={
                    "position": "absolute",
                    "left": "0",
                    "right": "0",
                    "top": f"{100 - tick}%",
                    "height": "1px",
                    "backgroundColor": SEPARATOR,
                }
            )
        )
        lines.append(
            mn.box(
                style={
                    "position": "absolute",
                    "top": "0",
                    "bottom": "0",
                    "left": f"{tick}%",
                    "width": "1px",
                    "backgroundColor": SEPARATOR,
                }
            )
        )
    return lines


def _tick(text: str, **position: str) -> rx.Component:
    return mn.text(
        text,
        fz="10.5px",
        c=theme.TEXT_MUTED,
        text_wrap="nowrap",
        w="max-content",
        style={"position": "absolute", **position},
    )


def _ticks() -> list[rx.Component]:
    labels = [_tick("0", left="-18px", bottom="-6px")]
    for tick in (*TICKS, 100):
        labels.append(
            _tick(
                f"{tick} %", right="calc(100% + 6px)", top=f"calc({100 - tick}% - 7px)"
            )
        )
        labels.append(
            _tick(f"{tick} %", left=f"calc({tick}% - 14px)", top="calc(100% + 4px)")
        )
    return labels


def _zones() -> list[rx.Component]:
    return [
        _tick("vor dem Plan", left="8px", top="6px"),
        _tick("hinter dem Plan", left="58%", bottom="8px"),
    ]


def _plot(data: ObjectVar[PortfolioKpi]) -> rx.Component:
    return mn.stack(
        mn.box(
            *_grid_lines(),
            *_ticks(),
            *_zones(),
            rx.foreach(data.bubbles, _bubble),
            style={
                "position": "relative",
                "height": PLOT_HEIGHT,
                "marginLeft": "42px",
                "marginRight": "36px",
                "marginTop": "10px",
                "borderLeft": f"1px solid {BORDER_STRONG}",
                "borderBottom": f"1px solid {BORDER_STRONG}",
                "backgroundImage": DIAGONAL_SVG,
                "backgroundSize": "100% 100%",
            },
        ),
        mn.group(
            mn.text(
                "Waagerecht: Zeit verstrichen. Senkrecht: Fortschritt.", **MUTED_TEXT
            ),
            mn.text(data.not_plotted_label, **MUTED_TEXT),
            justify="space-between",
            pt="40px",
            gap="xs",
        ),
        gap=0,
    )


def _legend_dot(
    label: str, fill: str, line: str, *, dashed: bool = False
) -> rx.Component:
    return mn.group(
        mn.box(
            style={
                "width": "10px",
                "height": "10px",
                "borderRadius": "50%",
                "backgroundColor": fill,
                "border": f"{'1.5px dashed' if dashed else '2px solid'} {line}",
                "boxSizing": "border-box",
            }
        ),
        mn.text(label, **MUTED_TEXT),
        gap=4,
        wrap="nowrap",
    )


def _legend() -> rx.Component:
    return mn.group(
        _legend_dot("im Budget", *_FILL["green"]),
        _legend_dot("bis 10 % über", *_FILL["yellow"]),
        _legend_dot("über 10 %", *_FILL["red"]),
        _legend_dot("Puffer unter 0", "transparent", theme.NEGATIVE, dashed=True),
        gap="sm",
        justify="flex-end",
    )


def portfolio_bubbles_card() -> rx.Component:
    data = PortfolioState.data.to(PortfolioKpi)
    return card(
        "Projekte: Zeit und Fortschritt",
        "Größe: Budget. Farbe: EAC zu Budget. Unter der Linie liegt ein Projekt "
        "hinter dem Plan.",
        rx.cond(
            data.bubbles.length() > 0,
            _plot(data),
            empty_text(
                "Keine aktiven Projekte. Geplante Projekte erscheinen, sobald sie "
                "starten."
            ),
        ),
        is_loading=PortfolioState.is_loading,
        aside=_legend(),
    )
