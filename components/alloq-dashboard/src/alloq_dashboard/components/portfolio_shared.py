"""Building blocks shared by the portfolio cards."""

from __future__ import annotations

from typing import Any, cast

import reflex as rx
from alloq_commons import theme
from alloq_commons.components.formatters import de_number

import appkit_mantine as mn

TONE_COLORS = {"neg": "red", "warn": "yellow"}
MUTED_TEXT: dict[str, Any] = {"fz": "11.5px", "c": theme.TEXT_MUTED}
LINK_STYLE: dict[str, Any] = {
    "border": "0",
    "padding": "0",
    "background": "transparent",
    "font": "inherit",
    "fontSize": "13px",
    "fontWeight": "600",
    "color": theme.ACCENT,
    "cursor": "pointer",
    "textAlign": "left",
    "minWidth": "0",
    "_hover": {"textDecoration": "underline"},
}


def card(
    title: str,
    subtitle: str | rx.Var[str],
    body: rx.Component,
    *,
    is_loading: rx.Var[bool],
    aside: rx.Component | None = None,
    label: str = "",
) -> rx.Component:
    """White card with a title, one line of context and a loading skeleton."""
    header = mn.group(
        mn.stack(
            mn.text(title, fz="14px", fw=650, c=theme.TEXT),
            mn.text(subtitle, **MUTED_TEXT),
            gap=2,
            miw=0,
        ),
        aside if aside is not None else rx.fragment(),
        justify="space-between",
        align="flex-start",
        wrap="nowrap",
        gap="md",
    )
    skeleton = mn.stack(
        mn.skeleton(height="14px", width="60%"),
        mn.skeleton(height="14px", width="80%"),
        mn.skeleton(height="14px", width="40%"),
        gap="sm",
        pt="md",
    )
    return mn.box(
        mn.stack(
            header,
            rx.cond(is_loading, skeleton, body),
            gap="sm",
            h="100%",
        ),
        style={**theme.CARD, "padding": "14px 16px", "minWidth": "0"},
        custom_attrs={"role": "region", "aria-label": label or title},
    )


def tone_badge(text: rx.Var[str] | str, tone: rx.Var[str]) -> rx.Component:
    """Small light badge; ``tone`` is ``neg``, ``warn`` or empty."""
    return mn.badge(
        text,
        variant="light",
        radius="xl",
        size="sm",
        color=cast(
            "rx.Var[str]",
            rx.match(tone, ("neg", "red"), ("warn", "yellow"), "gray"),
        ),
        style=theme.NUMERIC,
    )


def tone_color(tone: rx.Var[str]) -> rx.Var:
    return cast(
        "rx.Var",
        rx.match(
            tone,
            ("neg", theme.NEGATIVE),
            ("warn", theme.WARNING),
            theme.TEXT,
        ),
    )


def empty_text(message: str) -> rx.Component:
    return mn.text(message, fz="13px", c=theme.TEXT_MUTED, py="md")


def number(
    value: rx.Var | float,
    *,
    fz: str = "11.5px",
    c: str | rx.Var = theme.TEXT_MUTED,
    fw: int = 400,
    **number_format: Any,
) -> rx.Component:
    """German number; text props go on the wrapper, the formatter ignores them."""
    return mn.text(
        de_number(value, **number_format),
        fz=fz,
        c=c,
        fw=fw,
        span=True,
        text_wrap="nowrap",
        style=theme.NUMERIC,
    )


def link_button(label: rx.Var[str] | str, on_click: Any, **style: Any) -> rx.Component:
    """Text that opens a drawer; a real button for keyboard and screen readers."""
    return rx.el.button(
        label, type="button", on_click=on_click, style={**LINK_STYLE, **style}
    )
