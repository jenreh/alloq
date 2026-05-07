"""Shared constants and small widgets used across dashboard components."""

from __future__ import annotations

import reflex as rx

ROW_STYLE: dict[str, str] = {
    "padding": "8px 12px",
    "borderRadius": "6px",
    "backgroundColor": "var(--alloq-surface-muted)",
}


def severity_badge_color(severity: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        severity,
        ("high", "red"),
        ("Hoch", "red"),
        ("medium", "yellow"),
        ("Mittel", "yellow"),
        ("low", "green"),
        ("Niedrig", "green"),
        "gray",
    )


def status_badge_color(status: rx.Var[str]) -> rx.Var[str]:
    return rx.match(
        status,
        ("open", "red"),
        ("Offen", "red"),
        ("in_progress", "yellow"),
        ("In Bearbeitung", "yellow"),
        ("done", "green"),
        ("Erledigt", "green"),
        "gray",
    )
