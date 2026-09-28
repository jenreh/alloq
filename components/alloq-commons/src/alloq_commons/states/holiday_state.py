import contextlib
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import reflex as rx

from alloq_commons.entities.public_holiday import PublicHolidayEntity
from alloq_commons.models.public_holiday import PublicHoliday, PublicHolidayCreate
from alloq_commons.repositories.public_holiday_repository import public_holiday_repo
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date:
    """Parse DD.MM.YYYY (Mantine form submission) or ISO YYYY-MM-DD."""
    date_str = date_str.strip()
    if "." in date_str:
        return datetime.strptime(date_str, "%d.%m.%Y").date()  # noqa: DTZ007
    return date.fromisoformat(date_str[:10])


def _year_range() -> range:
    """Selectable years: the previous year through two years ahead."""
    current = datetime.now(tz=UTC).year
    return range(current - 1, current + 3)


class HolidayState(rx.State):
    """State for public holiday management."""

    holidays: rx.Field[list[PublicHoliday]] = rx.field(default_factory=list)
    selected_holiday: rx.Field[PublicHoliday | None] = rx.field(None)
    is_loading: rx.Field[bool] = rx.field(False)
    selected_year: rx.Field[int] = rx.field(datetime.now(tz=UTC).year)
    _year_initialized: bool = False

    add_modal_open: rx.Field[bool] = rx.field(False)
    edit_modal_open: rx.Field[bool] = rx.field(False)
    search_filter: rx.Field[str] = rx.field("")

    @rx.var
    def selected_holiday_date_iso(self) -> str:
        """ISO date string of the selected holiday's date, or empty string."""
        if self.selected_holiday is None:
            return ""
        return self.selected_holiday.date.isoformat()

    @rx.event
    def set_search_filter(self, value: str) -> None:
        """Update the search filter."""
        self.search_filter = value

    @rx.event
    def set_selected_year(self, value: str) -> None:
        """Update the selected year filter."""
        with contextlib.suppress(ValueError, TypeError):
            self.selected_year = int(value)

    @rx.var
    def selected_year_str(self) -> str:
        """Selected year as string for the year select component."""
        return str(self.selected_year)

    @rx.var
    def filtered_holidays(self) -> list[PublicHoliday]:
        """Return holidays filtered by search text."""
        if not self.search_filter:
            return self.holidays
        search = self.search_filter.lower()
        return [h for h in self.holidays if search in h.name.lower()]

    @rx.var
    def available_years(self) -> list[str]:
        """Return the previous year plus a rolling 3 years from the current one."""
        return [str(y) for y in _year_range()]

    @rx.event
    def open_add_modal(self) -> None:
        """Open the add holiday modal."""
        self.add_modal_open = True

    @rx.event
    def close_add_modal(self) -> None:
        """Close the add holiday modal."""
        self.add_modal_open = False

    @rx.event
    def open_edit_modal(self) -> None:
        """Open the edit holiday modal."""
        self.edit_modal_open = True

    @rx.event
    def close_edit_modal(self) -> None:
        """Close the edit modal and reset selection."""
        self.edit_modal_open = False
        self.selected_holiday = None

    @rx.event
    @requires_admin
    async def select_holiday_and_open_edit(self, holiday_id: int) -> None:
        """Select a holiday by ID and open the edit modal."""
        await self._select_holiday(holiday_id)
        self.open_edit_modal()

    async def _select_holiday(self, holiday_id: int) -> None:
        """Load a holiday by ID into selected_holiday."""
        async with get_asyncdb_session() as session:
            entity = await public_holiday_repo.find_by_id(session, holiday_id)
            if entity:
                self.selected_holiday = PublicHoliday(**entity.to_dict())

    async def _load_holidays(self) -> None:
        """Internal: load holidays for the selected year."""
        async with get_asyncdb_session() as session:
            entities = await public_holiday_repo.find_by_year(
                session, self.selected_year
            )
            self.holidays = [PublicHoliday(**e.to_dict()) for e in entities]

    @rx.event
    @requires_admin
    async def load_holidays(self) -> AsyncGenerator[Any]:
        """Load holidays for the current year.

        The loading row only replaces the table on the first load; revisits
        refresh the existing rows in place to avoid a flicker.
        """
        if not self._year_initialized:
            # The class default is evaluated once at import; a long-running
            # server would otherwise start new sessions on a stale year.
            self.selected_year = datetime.now(tz=UTC).year
            self._year_initialized = True
        if not self.holidays:
            self.is_loading = True
            yield
        try:
            await self._load_holidays()
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def change_year(self, value: str) -> AsyncGenerator[Any]:
        """Change the year filter and reload."""
        self.set_selected_year(value)
        self.is_loading = True
        yield
        try:
            await self._load_holidays()
        finally:
            self.is_loading = False

    @rx.event
    @requires_admin
    async def create_holiday(self, form_data: dict) -> AsyncGenerator[Any]:
        """Create a new holiday from form submission."""
        self.is_loading = True
        yield
        try:
            date_str = form_data.get("date", "")

            holiday_data = PublicHolidayCreate(
                name=form_data.get("name", "").strip(),
                date=_parse_date(date_str),
                is_recurring=form_data.get("is_recurring") == "on",
                state_code=form_data.get("state_code", "NRW").strip() or "NRW",
            )

            async with get_asyncdb_session() as session:
                entity = PublicHolidayEntity(
                    name=holiday_data.name,
                    date=holiday_data.date,
                    is_recurring=holiday_data.is_recurring,
                    state_code=holiday_data.state_code,
                )
                await public_holiday_repo.create(session, entity)

            await self._load_holidays()
            self.close_add_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Feiertag '{holiday_data.name}' wurde erstellt.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to create holiday")
            self.is_loading = False
            yield rx.toast.error(
                "Fehler beim Erstellen des Feiertags.",
                position="top-right",
            )

    @rx.event
    @requires_admin
    async def update_holiday(self, form_data: dict) -> AsyncGenerator[Any]:
        """Update an existing holiday from form submission."""
        self.is_loading = True
        yield
        try:
            if not self.selected_holiday:
                self.is_loading = False
                yield rx.toast.error("Kein Feiertag ausgewählt.", position="top-right")
                return

            date_str = form_data.get("date", "")

            holiday_data = PublicHolidayCreate(
                name=form_data.get("name", "").strip(),
                date=_parse_date(date_str),
                is_recurring=form_data.get("is_recurring") == "on",
                state_code=form_data.get("state_code", "NRW").strip() or "NRW",
            )

            # Toasts are yielded only after the session is closed so the DB
            # connection is not held across a websocket round trip.
            async with get_asyncdb_session() as session:
                entity = await public_holiday_repo.find_by_id(
                    session, self.selected_holiday.id
                )
                if entity:
                    entity.name = holiday_data.name
                    entity.date = holiday_data.date
                    entity.is_recurring = holiday_data.is_recurring
                    entity.state_code = holiday_data.state_code
                    await public_holiday_repo.update(session, entity)
            if not entity:
                self.is_loading = False
                yield rx.toast.error("Feiertag nicht gefunden.", position="top-right")
                return

            await self._load_holidays()
            self.close_edit_modal()
            self.is_loading = False
            yield rx.toast.info(
                f"Feiertag '{holiday_data.name}' wurde aktualisiert.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to update holiday")
            self.is_loading = False
            yield rx.toast.error(
                "Fehler beim Aktualisieren des Feiertags.",
                position="top-right",
            )

    @rx.event
    @requires_admin
    async def delete_holiday(self, holiday_id: int) -> AsyncGenerator[Any]:
        """Delete a holiday by ID."""
        self.is_loading = True
        yield
        try:
            error = ""
            name = ""
            async with get_asyncdb_session() as session:
                entity = await public_holiday_repo.find_by_id(session, holiday_id)
                if not entity:
                    error = "Feiertag nicht gefunden."
                else:
                    name = entity.name
                    if not await public_holiday_repo.delete_by_id(session, holiday_id):
                        error = "Feiertag konnte nicht gelöscht werden."
            if error:
                self.is_loading = False
                yield rx.toast.error(error, position="top-right")
                return

            await self._load_holidays()
            self.is_loading = False
            yield rx.toast.info(
                f"Feiertag '{name}' wurde gelöscht.",
                position="top-right",
            )
        except Exception:
            logger.exception("Failed to delete holiday")
            self.is_loading = False
            yield rx.toast.error(
                "Fehler beim Löschen des Feiertags.",
                position="top-right",
            )
