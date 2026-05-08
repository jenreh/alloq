"""Shared dashboard UI helpers reusable across modules."""

from __future__ import annotations

import reflex as rx

import appkit_mantine as mn

ROW_STYLE: dict[str, str] = {
    "padding": "8px 12px",
    "borderRadius": "6px",
    "backgroundColor": "var(--alloq-surface-muted)",
}


def big_number(value: rx.Var, suffix: str = "") -> rx.Component:
    """Render a large KPI number with optional suffix."""
    return mn.group(
        mn.text(
            value.to_string(),
            size="2.25rem",
            fw="700",
            c="var(--alloq-text)",
            style={"lineHeight": "1.0"},
        ),
        rx.cond(
            suffix != "",
            mn.text(suffix, size="md", c="var(--alloq-text-muted)"),
            rx.fragment(),
        ),
        gap="xs",
        align="baseline",
    )
