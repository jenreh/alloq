"""Database access switch of one user row (desktop app only)."""

import reflex as rx

import appkit_mantine as mn
from appkit_user.authentication.backend.models import User

from app.desktop.db_access_state import DatabaseAccessState


def database_access_button(user: User) -> rx.Component:
    granted = DatabaseAccessState.members.contains(user.email.lower())
    return mn.tooltip(
        mn.action_icon(
            rx.icon("database", size=16),
            variant="subtle",
            color=rx.cond(granted, "green", "gray"),
            loading=DatabaseAccessState.pending_email == user.email,
            # data_disabled keeps the tooltip working on the disabled button
            data_disabled=DatabaseAccessState.locked,
            aria_label="Datenbankzugriff",
            on_click=DatabaseAccessState.toggle(user.email),
        ),
        label=rx.cond(
            DatabaseAccessState.can_manage,
            rx.cond(granted, "Datenbankzugriff entziehen", "Datenbankzugriff geben"),
            rx.cond(
                granted,
                "Hat Datenbankzugriff (ändern nur mit Admin-Rechten in der Datenbank)",
                "Kein Datenbankzugriff (geben nur mit Admin-Rechten in der Datenbank)",
            ),
        ),
    )
