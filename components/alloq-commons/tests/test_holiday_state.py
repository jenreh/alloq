"""Behavior tests for HolidayState CRUD handlers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.models.public_holiday import PublicHoliday
from alloq_commons.states.holiday_state import HolidayState, _parse_date

MODULE = "alloq_commons.states.holiday_state"
FORM = {"name": " Neujahr ", "date": "01.01.2027", "is_recurring": "on"}


class _FakeLogin:
    @property
    async def authenticated_user(self) -> Any:
        return SimpleNamespace(user_id=1, is_admin=True)

    @property
    async def is_authenticated(self) -> bool:
        return True

    async def redir(self) -> None:
        return None


def _admin_state() -> HolidayState:
    state = HolidayState()
    object.__setattr__(state, "get_state", AsyncMock(return_value=_FakeLogin()))
    return state


def _session_ctx() -> Any:
    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield AsyncMock()

    return _ctx


def _entity(**data: Any) -> MagicMock:
    entity = MagicMock(**data)
    entity.to_dict.return_value = {"id": 1, "name": "Neujahr", "date": date(2027, 1, 1)}
    return entity


async def _drain(handler: Any) -> list[Any]:
    return [event async for event in handler]


def _has_text(events: list[Any], text: str) -> bool:
    return any(text in repr(event) for event in events)


@pytest.fixture
def repo() -> Any:
    repo = MagicMock()
    repo.find_by_year = AsyncMock(return_value=[_entity()])
    with (
        patch(f"{MODULE}.public_holiday_repo", repo),
        patch(f"{MODULE}.get_asyncdb_session", _session_ctx()),
    ):
        yield repo


def test_parse_date_accepts_german_and_iso() -> None:
    assert _parse_date(" 24.12.2026 ") == date(2026, 12, 24)
    assert _parse_date("2026-12-24T00:00:00") == date(2026, 12, 24)


def test_simple_setters_and_vars() -> None:
    state = HolidayState()
    state.holidays = [
        PublicHoliday(id=1, name="Neujahr", date=date(2027, 1, 1)),
        PublicHoliday(id=2, name="Ostern", date=date(2027, 3, 28)),
    ]

    state.set_search_filter("oster")
    state.set_selected_year("2030")
    state.set_selected_year("abc")
    assert [h.id for h in state.filtered_holidays] == [2]
    assert state.selected_year_str == "2030"
    assert state.selected_holiday_date_iso == ""

    state.selected_holiday = state.holidays[0]
    assert state.selected_holiday_date_iso == "2027-01-01"
    state.open_add_modal()
    state.close_add_modal()
    state.close_edit_modal()
    assert (state.add_modal_open, state.selected_holiday) == (False, None)


@pytest.mark.asyncio
async def test_select_holiday_opens_edit_modal(repo: Any) -> None:
    state = _admin_state()
    repo.find_by_id = AsyncMock(return_value=_entity())

    await state.select_holiday_and_open_edit(1)

    assert state.edit_modal_open is True
    assert state.selected_holiday is not None
    assert state.selected_holiday.name == "Neujahr"


@pytest.mark.asyncio
async def test_change_year_reloads_holidays(repo: Any) -> None:
    state = _admin_state()

    await _drain(state.change_year("2027"))

    repo.find_by_year.assert_awaited_once()
    assert repo.find_by_year.await_args.args[1] == 2027
    assert len(state.holidays) == 1
    assert state.is_loading is False


@pytest.mark.asyncio
async def test_create_holiday_persists_and_closes_modal(repo: Any) -> None:
    state = _admin_state()
    state.add_modal_open = True
    repo.create = AsyncMock()

    events = await _drain(state.create_holiday(FORM))

    entity = repo.create.call_args.args[1]
    assert (entity.name, entity.date, entity.is_recurring) == (
        "Neujahr",
        date(2027, 1, 1),
        True,
    )
    assert entity.state_code == "NRW"
    assert state.add_modal_open is False
    assert _has_text(events, "wurde erstellt")


@pytest.mark.asyncio
async def test_create_holiday_with_bad_date_shows_error(repo: Any) -> None:
    state = _admin_state()
    repo.create = AsyncMock()

    events = await _drain(state.create_holiday({**FORM, "date": "31.02.2027"}))

    repo.create.assert_not_awaited()
    assert state.is_loading is False
    assert _has_text(events, "Fehler beim Erstellen")


@pytest.mark.asyncio
@pytest.mark.usefixtures("repo")
async def test_update_without_selection_shows_error() -> None:
    state = _admin_state()

    events = await _drain(state.update_holiday(FORM))

    assert _has_text(events, "Kein Feiertag ausgewählt")


@pytest.mark.asyncio
async def test_update_holiday_applies_form(repo: Any) -> None:
    state = _admin_state()
    state.selected_holiday = PublicHoliday(id=1, name="Alt", date=date(2027, 1, 2))
    state.edit_modal_open = True
    entity = SimpleNamespace()
    repo.find_by_id = AsyncMock(return_value=entity)
    repo.update = AsyncMock()

    events = await _drain(state.update_holiday({**FORM, "state_code": " BY "}))

    repo.update.assert_awaited_once()
    assert (entity.name, entity.state_code) == ("Neujahr", "BY")
    assert state.edit_modal_open is False
    assert state.selected_holiday is None
    assert _has_text(events, "wurde aktualisiert")


@pytest.mark.asyncio
async def test_update_missing_holiday_shows_error(repo: Any) -> None:
    state = _admin_state()
    state.selected_holiday = PublicHoliday(id=1, name="Alt", date=date(2027, 1, 2))
    repo.find_by_id = AsyncMock(return_value=None)

    events = await _drain(state.update_holiday(FORM))

    assert _has_text(events, "Feiertag nicht gefunden")
    assert state.selected_holiday is not None


@pytest.mark.asyncio
async def test_update_db_error_shows_toast(repo: Any) -> None:
    state = _admin_state()
    state.selected_holiday = PublicHoliday(id=1, name="Alt", date=date(2027, 1, 2))
    repo.find_by_id = AsyncMock(side_effect=RuntimeError("down"))

    events = await _drain(state.update_holiday(FORM))

    assert state.is_loading is False
    assert _has_text(events, "Fehler beim Aktualisieren")


@pytest.mark.asyncio
async def test_delete_holiday_reloads_list(repo: Any) -> None:
    state = _admin_state()
    repo.find_by_id = AsyncMock(return_value=SimpleNamespace(name="Neujahr"))
    repo.delete_by_id = AsyncMock(return_value=True)

    events = await _drain(state.delete_holiday(1))

    repo.find_by_year.assert_awaited_once()
    assert _has_text(events, "Feiertag 'Neujahr' wurde gelöscht")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("found", "deleted", "message"),
    [
        (None, True, "Feiertag nicht gefunden"),
        (SimpleNamespace(name="X"), False, "konnte nicht gelöscht werden"),
    ],
)
async def test_delete_holiday_failures(
    repo: Any, found: Any, deleted: bool, message: str
) -> None:
    state = _admin_state()
    repo.find_by_id = AsyncMock(return_value=found)
    repo.delete_by_id = AsyncMock(return_value=deleted)

    events = await _drain(state.delete_holiday(1))

    repo.find_by_year.assert_not_awaited()
    assert _has_text(events, message)


@pytest.mark.asyncio
async def test_delete_db_error_shows_toast(repo: Any) -> None:
    state = _admin_state()
    repo.find_by_id = AsyncMock(side_effect=RuntimeError("down"))

    events = await _drain(state.delete_holiday(1))

    assert state.is_loading is False
    assert _has_text(events, "Fehler beim Löschen")
