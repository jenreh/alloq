from collections.abc import Callable

import reflex as rx

import appkit_mantine as mn
from alloq_commons.models.view_mode import VIEW_MODE_GRID, VIEW_MODE_TABLE


def _view_mode_button(
    icon: str,
    label: str,
    active: rx.Var[bool],
    on_click: rx.EventSpec,
) -> rx.Component:
    """Icon button with a tooltip.

    The button is wrapped in a box because its state-dependent props make
    Reflex compile it into a memoized sub-component, which cannot receive
    the ref that Mantine's tooltip attaches to its child.
    """
    return mn.tooltip(
        mn.box(
            mn.action_icon(
                rx.icon(icon, size=20),
                variant=rx.cond(active, "filled", "subtle"),
                auto_contrast=True,
                size="lg",
                radius="md",
                on_click=on_click,
            ),
            display="flex",
        ),
        label=label,
        with_arrow=True,
        position="bottom",
    )


def view_mode_toggle(
    view_mode: rx.Var[str],
    on_change: Callable[[str], rx.EventSpec],
) -> rx.Component:
    """Toggle between grid (cards) and table view."""
    return mn.group(
        _view_mode_button(
            "layout-grid",
            "Kachelansicht",
            view_mode == VIEW_MODE_GRID,
            on_change(VIEW_MODE_GRID),
        ),
        _view_mode_button(
            "list",
            "Listenansicht",
            view_mode == VIEW_MODE_TABLE,
            on_change(VIEW_MODE_TABLE),
        ),
        gap="2px",
    )
