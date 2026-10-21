"""Spreadsheet drafts, protected cells, navigation and save failures."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.models.price_list import PriceList, PricePosition
from alloq_commons.repositories.price_list_repository import PriceListConflict
from alloq_commons.services.price_list_templates import price_list_template
from alloq_commons.state.price_list_state import PriceListState

from appkit_user.authentication.states import LoginState

MODULE = "alloq_commons.state.price_list_state"


@pytest.fixture
def sheet_state() -> tuple[PriceListState, AsyncMock]:
    state = PriceListState()
    user = MagicMock(is_admin=True, signed_in=True)
    login = MagicMock()

    async def authenticated() -> MagicMock:
        return user

    async def signed_in() -> bool:
        return user.signed_in

    type(login).authenticated_user = property(lambda _: authenticated())
    type(login).is_authenticated = property(lambda _: signed_in())
    login.redir = AsyncMock(return_value=None)

    async def get_state(cls: type) -> MagicMock:
        assert cls is LoginState
        return login

    object.__setattr__(state, "get_state", get_state)
    state._accept(price_list_template("2025"))
    return state, user


async def drive(handler: object, *args: object) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(item) async for item in result if item is not None])
    await result
    return ""


async def test_hourly_cost_and_roles_are_visible_by_default(sheet_state: tuple) -> None:
    state, _ = sheet_state
    assert state.show_hourly
    assert state.hourly_visible
    assert state.show_roles
    assert not state.show_archived
    await drive(state.set_view, "show_hourly", False)
    await drive(state.set_view, "show_roles", False)
    assert not state.hourly_visible
    assert not state.show_roles


async def test_draft_edit_protected_cells_undo_and_discard(sheet_state: tuple) -> None:
    state, _ = sheet_state
    key = state.draft.positions[0].key
    await drive(
        state.apply_cell_changes,
        [
            {"key": f"{key}|la", "value": "Junior"},
            {"key": f"{key}|daily_cost", "value": "711.01"},
            {"key": f"{key}|minimum_daily", "value": "1"},
        ],
    )
    assert state.draft.positions[0].la == "Junior"
    assert state.draft.positions[0].cost == Decimal("711.01")
    assert state.rows[0].cell_values["minimum_daily"] == "1016.00"
    assert state.has_dirty
    await drive(state.discard)
    assert not state.has_dirty
    assert state.draft.positions[0].la == "8030"


async def test_invalid_edits_and_identity_on_save(sheet_state: tuple) -> None:
    state, _ = sheet_state
    key = state.draft.positions[0].key
    text = await drive(
        state.apply_cell_changes, [{"key": f"{key}|sales_price", "value": "-5"}]
    )
    assert "Ungültig" in text
    assert not state.has_dirty
    await drive(state.add_row)
    text = await drive(state.save)
    assert "LA" in text
    assert state.has_dirty


async def test_switch_requires_resolution_and_duplicate_is_independent(
    sheet_state: tuple,
) -> None:
    state, _ = sheet_state
    await drive(state.add_row)
    await drive(state.request_action, "template", "2026")
    assert state.pending_action == "template"
    assert len(state.draft.positions) == 8
    await drive(state.resolve_pending, "stay")
    assert not state.pending_action
    await drive(state.request_action, "template", "2026")
    await drive(state.resolve_pending, "discard")
    assert state.draft.name == "Tagessätze 2026"
    await drive(state.request_action, "duplicate", "")
    await drive(state.resolve_pending, "discard")
    assert state.draft.name.endswith("(Kopie)")


async def test_discard_new_template_returns_to_previous_list(
    sheet_state: tuple,
) -> None:
    state, _ = sheet_state
    await drive(state.request_action, "template", "2026")
    assert state.has_dirty
    assert state.draft.name == "Tagessätze 2026"
    await drive(state.discard)
    assert state.draft.name == "Tagessätze 2025"
    assert not state.has_dirty


async def test_row_operations_and_settings(sheet_state: tuple) -> None:
    state, _ = sheet_state
    first = state.draft.positions[0].key
    await drive(state.move_row, first, 1)
    assert state.draft.positions[1].key == first
    await drive(state.delete_row, first)
    assert len(state.draft.positions) == 6
    await drive(state.set_setting, "cost_basis", "hour")
    assert state.draft.positions[0].cost == Decimal("88.75")
    await drive(state.set_setting, "minimum_margin", "40,5")
    assert state.draft.minimum_margin == Decimal("40.5")
    assert "Ungültig" in await drive(state.set_setting, "hours_per_day", "0")
    await drive(state.set_setting, "target_margin", "")
    await drive(state.toggle_archive)
    assert state.draft.archived


async def test_basis_conversion_cannot_create_zero_cost(sheet_state: tuple) -> None:
    state, _ = sheet_state
    state._accept(
        PriceList(
            name="Small",
            hours_per_day="24",
            positions=[
                PricePosition(label="Position", cost="0.01"),
            ],
        )
    )
    assert "Ungültig" in await drive(state.set_setting, "cost_basis", "hour")
    assert state.draft.cost_basis == "day"
    assert state.draft.positions[0].cost == Decimal("0.01")


async def test_save_conflict_keeps_draft(sheet_state: tuple) -> None:
    state, _ = sheet_state
    await drive(state.add_row)
    state.draft.positions[-1] = PricePosition(label="Extern")

    @asynccontextmanager
    async def session() -> object:
        yield AsyncMock()

    repo = AsyncMock()
    repo.save_document.side_effect = PriceListConflict()
    with (
        patch(f"{MODULE}.get_asyncdb_session", session),
        patch(f"{MODULE}.price_list_repo", repo),
    ):
        assert "geändert" in await drive(state.save)
    assert state.has_dirty
    assert not state.is_saving


async def test_non_admin_cannot_edit_or_save(sheet_state: tuple) -> None:
    state, user = sheet_state
    user.is_admin = False
    await drive(state.add_row)
    assert len(state.draft.positions) == 7
    assert not state.has_dirty


async def test_legacy_automatic_sales_keeps_override_empty(sheet_state: tuple) -> None:
    state, _ = sheet_state
    legacy = PriceList(
        name="Bestand",
        target_margin="35",
        positions=[
            PricePosition(label="Engineer", cost="710"),
        ],
    )
    state._accept(legacy)
    assert state.rows[0].cell_values["sales_price"] == ""
    assert state.rows[0].effective_sales == "1093.00"
    key = state.draft.positions[0].key
    await drive(
        state.apply_cell_changes, [{"key": f"{key}|sales_price", "value": "1093.00"}]
    )
    assert state.draft.positions[0].sales_price == Decimal("1093")
    assert state.has_dirty
    await drive(state.apply_cell_changes, [{"key": f"{key}|sales_price", "value": ""}])
    assert not state.has_dirty


@pytest.fixture
def persistence() -> Iterator[AsyncMock]:
    @asynccontextmanager
    async def session() -> object:
        yield AsyncMock()

    repo = AsyncMock()
    saved = price_list_template("2026")
    saved.id, saved.version = 42, 1
    repo.load.return_value = saved
    repo.list_all.return_value = [saved]

    async def save(_session: object, document: PriceList) -> PriceList:
        return document.model_copy(update={"id": 43, "version": document.version + 1})

    repo.save_document.side_effect = save
    roles = AsyncMock()
    roles.find_all_paginated.return_value = [SimpleNamespace(id=1, name="Engineer")]
    with (
        patch(f"{MODULE}.get_asyncdb_session", session),
        patch(f"{MODULE}.price_list_repo", repo),
        patch(f"{MODULE}.role_repo", roles),
    ):
        yield repo


async def test_load_settings_views_and_compare(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, _ = sheet_state
    state._baseline = {}
    await drive(state.load)
    persistence.list_all.assert_awaited_once()
    assert state.selected_id == "42"
    assert state.cost_basis == "hour"
    assert state.hourly_visible
    assert not state.is_loading
    assert not state.is_archived
    assert state.list_options[0]["value"] == "42"
    assert state.role_options[0]["label"] == "Engineer"
    await drive(state.set_view, "show_roles", True)
    assert state.show_roles
    await drive(state.set_view, "draft", True)
    await drive(state.set_template, "germany")
    assert state.template_key == "germany"
    await drive(state.set_template, "bogus")
    assert state.template_key == "germany"
    await drive(state.set_compare, "42")
    assert len(state.compare_rows) == 4
    assert state.compare_name == "Tagessätze 2026"
    await drive(state.set_compare, "bogus")
    assert state.compare_rows == []
    assert state.compare_name == ""
    await drive(state.set_setting, "as_of", "2027-01-01")
    assert state.settings_values["as_of"] == "2027-01-01"
    await drive(state.set_setting, "not_a_setting", "bad")
    key = state.draft.positions[0].key
    await drive(state.set_role, key, "1")
    assert state.draft.positions[0].role_id == 1
    await drive(state.set_role, key, "unknown")
    assert state.draft.positions[0].role_id == 1
    await drive(state.set_role, key, "")
    assert state.draft.positions[0].role_id is None
    assert "2" in await drive(state.notify_rejected, 2)


async def test_save_and_switch_then_reload(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, _ = sheet_state
    await drive(state.set_setting, "name", "Modified")
    await drive(state.request_action, "select", "42")
    await drive(state.resolve_pending, "save")
    assert not state.has_dirty
    assert state.selected_id == "42"
    assert not state.pending_action
    assert persistence.save_document.await_count == 1
    await drive(state.request_action, "reload", "")
    assert persistence.load.await_count == 2
    await drive(state.request_action, "select", "42")
    assert persistence.load.await_count == 2
    await drive(state.request_action, "not_an_action", "")
    await drive(state.request_action, "new", "")
    assert state.draft.name == "Neue Preisliste"
    assert state.has_dirty


async def test_load_and_save_errors_preserve_draft(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, _ = sheet_state
    persistence.list_all.side_effect = RuntimeError("offline")
    assert "Fehler" in await drive(state.load)
    assert not state.is_loading
    await drive(state.set_setting, "name", "My changes")
    persistence.save_document.side_effect = RuntimeError("offline")
    assert "Fehler" in await drive(state.save)
    assert state.has_dirty
    assert state.draft.name == "My changes"
    assert not state.is_saving
    await drive(state.request_action, "select", "42")
    await drive(state.resolve_pending, "save")
    assert state.pending_action == "select"
    persistence.load.side_effect = PriceListConflict()
    assert "Fehler" in await drive(state.resolve_pending, "discard")
    assert state.has_dirty


async def test_reload_and_unavailable_lists(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, _ = sheet_state
    await drive(state.request_action, "reload", "")
    persistence.load.assert_not_awaited()
    persistence.load.side_effect = PriceListConflict()
    assert "verfügbar" in await drive(state.request_action, "select", "42")
    persistence.load.side_effect = RuntimeError("offline")
    assert "Fehler" in await drive(state.request_action, "select", "42")


async def test_signed_in_readers_load_and_open_lists(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, user = sheet_state
    user.is_admin = False
    state._baseline = {}
    await drive(state.load)
    assert state.selected_id == "42"
    await drive(state.set_view, "show_hourly", False)
    assert not state.show_hourly
    await drive(state.set_compare, "42")
    assert state.compare_name == "Tagessätze 2026"
    state.selected_id = ""
    await drive(state.open_list, "42")
    persistence.load.assert_awaited_once()
    assert state.selected_id == "42"
    await drive(state.open_list, "42")
    persistence.load.assert_awaited_once()
    await drive(state.save)
    persistence.save_document.assert_not_awaited()


async def test_open_list_reports_unavailable_and_failing_lists(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, _ = sheet_state
    persistence.load.side_effect = PriceListConflict()
    assert "nicht verfügbar" in await drive(state.open_list, "7")
    persistence.load.side_effect = RuntimeError("db down")
    assert "Fehler" in await drive(state.open_list, "7")
    assert "nicht verfügbar" in await drive(state.open_list, "abc")


async def test_signed_out_users_cannot_load(
    sheet_state: tuple, persistence: AsyncMock
) -> None:
    state, user = sheet_state
    user.signed_in = False
    await drive(state.load)
    await drive(state.open_list, "42")
    persistence.list_all.assert_not_awaited()
    persistence.load.assert_not_awaited()
