"""Sticky-bottom legend for the planning Grid view."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn

LEGEND_ITEMS: list[tuple[str, str]] = [
    ("< 40% Verfügbar", "var(--mantine-color-green-1)"),
    ("40-70% Verplant", "var(--mantine-color-green-0)"),
    ("70-95% Knapp", "var(--mantine-color-yellow-1)"),
    ("95-100% Voll", "var(--mantine-color-orange-1)"),
    ("> 100% Überlastet", "var(--mantine-color-red-2)"),
    ("Abwesend", "var(--mantine-color-blue-1)"),
]


def _legend_item(label: str, color: str) -> rx.Component:
    return mn.group(
        mn.box(
            style={
                "width": "14px",
                "height": "14px",
                "borderRadius": "3px",
                "backgroundColor": color,
                "border": "1px solid var(--alloq-border)",
            },
        ),
        mn.text(label, size="xs", c="var(--alloq-text-muted)"),
        gap="6px",
        align="center",
        wrap="nowrap",
    )


def planning_legend() -> rx.Component:
    """Sticks to the bottom of the page scroll container."""
    return mn.group(
        *[_legend_item(label, color) for label, color in LEGEND_ITEMS],
        gap="lg",
        align="center",
        wrap="nowrap",
        style={
            "position": "sticky",
            "bottom": "0",
            "zIndex": "30",
            "marginLeft": "-2rem",
            "marginRight": "-2rem",
            "marginTop": "auto",
            "padding": "10px 2rem",
            "backgroundColor": "var(--alloq-surface-solid)",
            "borderTop": "1px solid var(--alloq-border)",
            "boxShadow": "0 -2px 6px rgba(0, 0, 0, 0.04)",
        },
    )
