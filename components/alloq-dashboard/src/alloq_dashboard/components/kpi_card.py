"""Generic KPI card wrapper with skeleton-while-loading support."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn

CARD_STYLE = {
    "backgroundColor": "var(--alloq-fade-bg)",
    "borderRadius": "var(--mantine-radius-md)",
    "padding": "1.25rem",
    "minHeight": "260px",
    "transition": "background-color 120ms ease",
    "_hover": {
        "backgroundColor": "var(--alloq-fade-bg-hover)",
        "cursor": "pointer",
    },
}


def _skeleton_body() -> rx.Component:
    return mn.stack(
        mn.skeleton(height="2rem", width="60%"),
        mn.skeleton(height="1rem", width="40%"),
        gap="md",
        w="100%",
    )


def kpi_card(
    title: str,
    body: rx.Component,
    *,
    is_loading: rx.Var[bool],
    on_open: rx.EventHandler | None = None,
    icon: str | None = None,
    accent_color: str | None = None,
    error_message: rx.Var[str] | None = None,
    compact: bool = False,
    background_color: str | None = None,
) -> rx.Component:
    """Render a card with title, body, and optional drill-down click."""
    header_children: list[rx.Component] = []
    if icon:
        header_children.append(
            rx.icon(icon, size=16, color=accent_color or "var(--alloq-text-muted)"),
        )
    header_children.append(
        mn.text(
            title,
            size="sm",
            fw="600",
            c="var(--alloq-text-muted)",
            style={"letterSpacing": "0.02em", "textTransform": "uppercase"},
        ),
    )
    header = mn.group(*header_children, gap="xs", align="center")

    error_block = (
        rx.cond(
            error_message != "",
            mn.text(error_message, size="xs", c="red"),
            rx.fragment(),
        )
        if error_message is not None
        else rx.fragment()
    )

    content = mn.stack(
        header,
        rx.cond(is_loading, _skeleton_body(), body),
        error_block,
        gap="md",
        w="100%",
    )

    style = dict(CARD_STYLE)
    if compact:
        style["minHeight"] = "auto"
        style["padding"] = "1rem"
    if background_color:
        style["backgroundColor"] = background_color
        style["_hover"] = {"backgroundColor": background_color, "cursor": "pointer"}
    if on_open is None:
        bg = style.get("backgroundColor", "var(--alloq-surface-solid)")
        style["_hover"] = {"backgroundColor": bg}
        style["cursor"] = "default"

    return mn.box(content, on_click=on_open, style=style)
