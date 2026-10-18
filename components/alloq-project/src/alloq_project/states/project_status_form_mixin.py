"""Status form and status edit drafts of the project drawer; mixed into
`ProjectState`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import reflex as rx

if TYPE_CHECKING:
    from alloq_commons.models.project import ProjectStatus


def _clamp_percent(value: float | str) -> int:
    """Parse a percent input and clamp it to 0..100; invalid input becomes 0."""
    try:
        return max(0, min(100, int(float(value or 0))))
    except TypeError, ValueError:
        return 0


class ProjectStatusFormMixin(rx.State, mixin=True):
    """New-status form and inline edit draft for existing status entries."""

    if TYPE_CHECKING:  # Provided by ProjectState.
        statuses: list[ProjectStatus]

    # Status form input state
    status_date: rx.Field[str] = rx.field("")
    status_progress: rx.Field[int] = rx.field(0)
    status_budget_usage: rx.Field[int] = rx.field(0)
    status_notes: rx.Field[str] = rx.field("")
    status_form_version: rx.Field[int] = rx.field(0)

    # Status edit draft state (0=none, positive=editing existing)
    expanded_status_id: rx.Field[int] = rx.field(0)
    status_draft_progress: rx.Field[int] = rx.field(0)
    status_draft_budget_usage: rx.Field[int] = rx.field(0)
    status_draft_notes: rx.Field[str] = rx.field("")
    status_draft_date: rx.Field[str] = rx.field("")

    def _reset_status_form(self) -> None:
        """Clear the new-status form, defaulting the date to today."""
        self.status_date = datetime.now(tz=UTC).date().isoformat()
        self.status_progress = 0
        self.status_budget_usage = 0
        self.status_notes = ""

    def _reset_status_draft(self) -> None:
        """Close and clear the status edit draft."""
        self.expanded_status_id = 0
        self.status_draft_progress = 0
        self.status_draft_budget_usage = 0
        self.status_draft_notes = ""
        self.status_draft_date = ""

    @rx.event
    def set_status_progress(self, value: float | str) -> None:
        """Update the status progress field."""
        self.status_progress = _clamp_percent(value)

    @rx.event
    def set_status_budget_usage(self, value: float | str) -> None:
        """Update the status budget usage field."""
        self.status_budget_usage = _clamp_percent(value)

    @rx.event
    def set_status_notes(self, value: str) -> None:
        """Update the status notes field."""
        self.status_notes = value or ""

    @rx.event
    def set_status_date(self, value: str) -> None:
        """Update the status date field."""
        self.status_date = value or ""

    @rx.event
    def expand_status(self, status_id: int) -> None:
        """Toggle the inline edit form for an existing status entry."""
        if self.expanded_status_id == status_id:
            self.expanded_status_id = 0
            return
        status = next((s for s in self.statuses if s.id == status_id), None)
        if not status:
            return
        self.expanded_status_id = status_id
        self.status_draft_progress = status.progress
        self.status_draft_budget_usage = status.budget_spent
        self.status_draft_notes = status.notes
        self.status_draft_date = status.status_date

    @rx.event
    def collapse_status_edit(self) -> None:
        """Close the status edit form without saving."""
        self.expanded_status_id = 0

    @rx.event
    def set_status_draft_progress(self, value: float | str) -> None:
        """Update status draft progress field."""
        self.status_draft_progress = _clamp_percent(value)

    @rx.event
    def set_status_draft_budget_usage(self, value: float | str) -> None:
        """Update status draft budget usage field."""
        self.status_draft_budget_usage = _clamp_percent(value)

    @rx.event
    def set_status_draft_notes(self, value: str) -> None:
        """Update status draft notes field."""
        self.status_draft_notes = value or ""

    @rx.event
    def set_status_draft_date(self, value: str) -> None:
        """Update status draft date field."""
        self.status_draft_date = value or ""
