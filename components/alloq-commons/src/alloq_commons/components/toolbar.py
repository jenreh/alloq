"""Window toolbar of the content pane and its controls (macOS style).

Title and one line of context on the left, a segmented control in the middle,
search, icon buttons and at most one blue primary button on the right. The
toolbar drags the desktop window (`DRAG`).
"""

from collections.abc import Sequence
from typing import Any

import reflex as rx
from reflex.event import EventType

import appkit_mantine as mn
from alloq_commons import theme

TOOLBAR_HEIGHT_PX = 56
DRAG: dict[str, Any] = {"data-tauri-drag-region": ""}
"""Marks an element as window title bar (Tauri drags the window from it)."""

SIDEBAR_TOGGLE_SCRIPT = "window.aqToggleSidebar && window.aqToggleSidebar()"


def sidebar_reveal_button() -> rx.Component:
    """Shows the sidebar again; visible only while it is hidden (see shell CSS)."""
    return mn.box(
        icon_button(
            "panel-left-open",
            "Seitenleiste einblenden (⌃⌘S)",
            rx.call_script(SIDEBAR_TOGGLE_SCRIPT),
        ),
        class_name="aq-sidebar-reveal",
    )


def _heading(
    title: str | rx.Var[str], subtitle: str | rx.Var[str] | None
) -> rx.Component:
    """Title and one line of context, both dragging the window."""
    return mn.stack(
        mn.title(
            title,
            order=1,
            fz="15px",
            fw=650,
            lts="-0.01em",
            lh="1.2",
            c=theme.TEXT,
            line_clamp=1,
            custom_attrs=DRAG,
        ),
        mn.text(
            subtitle,
            fz="11.5px",
            lh="1.3",
            c=theme.TEXT_MUTED,
            truncate="end",
            custom_attrs=DRAG,
        )
        if subtitle is not None
        else rx.fragment(),
        gap=1,
        miw=0,
        custom_attrs=DRAG,
    )


def window_toolbar(
    title: str | rx.Var[str],
    subtitle: str | rx.Var[str] | None = None,
    *,
    center: rx.Component | None = None,
    actions: Sequence[rx.Component] = (),
) -> rx.Component:
    """Toolbar on top of the content pane."""
    heading = _heading(title, subtitle)
    return mn.box(
        sidebar_reveal_button(),
        mn.box(heading, class_name="aq-toolbar-title", custom_attrs=DRAG),
        mn.box(
            center if center is not None else rx.fragment(),
            class_name="aq-toolbar-center",
            custom_attrs=DRAG,
        ),
        mn.group(*actions, gap=6, wrap="nowrap", class_name="aq-toolbar-actions"),
        class_name="aq-toolbar",
        custom_attrs={**DRAG, "role": "toolbar"},
    )


def scope_bar(*children: rx.Component) -> rx.Component:
    """Filter row below the toolbar."""
    return mn.box(*children, class_name="aq-scopebar")


def segmented(
    value: rx.Var[str] | str,
    on_change: EventType[str],
    data: Sequence[str | dict[str, str]],
    **props: Any,
) -> rx.Component:
    """macOS segmented control."""
    return mn.segmented_control(
        data=list(data),
        value=value,
        on_change=on_change,
        size="xs",
        radius="md",
        class_name="aq-segmented",
        **props,
    )


def toolbar_search(
    value: rx.Var[str],
    on_change: EventType[str],
    placeholder: str = "Suchen",
    width: str = "200px",
) -> rx.Component:
    """Search field for the toolbar."""
    return mn.text_input(
        placeholder=placeholder,
        left_section=rx.icon("search", size=14),
        left_section_pointer_events="none",
        value=value,
        on_change=on_change,
        size="xs",
        radius="md",
        w=width,
        class_name="aq-toolbar-search",
        custom_attrs={"type": "search", "aria-label": placeholder},
    )


def icon_button(
    icon: str | rx.Var[str],
    label: str | rx.Var[str],
    on_click: EventType[()] | None = None,
    *,
    active: rx.Var[bool] | bool = False,
    **props: Any,
) -> rx.Component:
    """Borderless 28px icon button with tooltip."""
    return mn.tooltip(
        mn.box(
            mn.action_icon(
                rx.icon(icon, size=16, stroke_width=1.8),
                variant="subtle",
                color="gray",
                size=28,
                radius="md",
                on_click=on_click,
                aria_label=label,
                class_name="aq-icon-btn",
                custom_attrs={"data-active": rx.cond(active, "true", "false")},
                **props,
            ),
            display="flex",
        ),
        label=label,
        position="bottom",
        open_delay=400,
    )


def primary_button(
    label: str, icon: str, on_click: EventType[()], **props: Any
) -> rx.Component:
    """The one blue button of a toolbar."""
    return mn.button(
        label,
        left_section=rx.icon(icon, size=15, stroke_width=2),
        size="xs",
        h=28,
        radius="md",
        on_click=on_click,
        **props,
    )
