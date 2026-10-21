"""Tests of the industries administration: state, components and page."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_offer.components.industry import (
    NAME_HINT,
    industries_table,
    industries_toolbar,
    industry_form_fields,
)
from alloq_offer.entities import IndustryEntity
from alloq_offer.models import Industry
from alloq_offer.states.industry_state import (
    DUPLICATE_MESSAGE,
    HINT_NAME,
    NOT_FOUND,
    IndustryState,
    in_use_message,
)
from sqlalchemy.exc import IntegrityError

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.states.industry_state"


def _entity(industry_id: int = 2, name: str = "Handel") -> IndustryEntity:
    entity = IndustryEntity(name=name)
    entity.id = industry_id
    return entity


@pytest.fixture
def repo() -> Iterator[AsyncMock]:
    session = AsyncMock()

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield session

    mock = AsyncMock()
    mock.find_all_ordered = AsyncMock(return_value=[_entity()])
    mock.find_by_id = AsyncMock(return_value=_entity())
    mock.count_offers = AsyncMock(return_value=0)
    mock.delete_by_id = AsyncMock(return_value=True)
    with (
        patch(f"{MODULE}.industry_repo", mock),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
    ):
        yield mock


@contextmanager
def _as_admin(state: IndustryState, *, is_admin: bool = True) -> Iterator[None]:
    user = MagicMock(is_admin=is_admin, user_id=1, roles=[])

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        assert cls is LoginState
        return login

    object.__setattr__(state, "get_state", _get_state)
    try:
        yield
    finally:
        object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


def _state(*industries: Industry) -> IndustryState:
    state = IndustryState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    state.industries = list(industries)
    return state


class TestUiHandlers:
    def test_search_filters_by_name(self) -> None:
        state = _state(Industry(id=1, name="Handel"), Industry(id=2, name="Energie"))
        state.set_search_filter(" hand ")
        assert [i.id for i in state.filtered_industries] == [1]

    def test_modals(self) -> None:
        state = _state(Industry(id=1, name="Handel"))
        state.open_add_modal()
        assert state.add_modal_open
        state.close_add_modal()
        assert not state.add_modal_open
        state.open_edit_modal(1)
        assert state.edit_modal_open
        assert state.selected_industry is not None
        state.close_edit_modal()
        assert state.selected_industry is None
        state.open_edit_modal(99)
        assert not state.edit_modal_open

    def test_in_use_message(self) -> None:
        assert "einem Angebot" in in_use_message(1)
        assert "3 Angeboten" in in_use_message(3)


class TestDataHandlers:
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_load(self) -> None:
        state = _state()
        with _as_admin(state):
            await _run(state.load_industries)
        assert [i.name for i in state.industries] == ["Handel"]
        assert not state.is_loading

    @pytest.mark.asyncio
    async def test_load_error(self, repo: AsyncMock) -> None:
        repo.find_all_ordered.side_effect = RuntimeError("db")
        state = _state()
        with _as_admin(state):
            out = await _run(state.load_industries)
        assert "geladen" in out

    @pytest.mark.asyncio
    async def test_non_admin_may_not_create(self, repo: AsyncMock) -> None:
        state = _state()
        with _as_admin(state, is_admin=False):
            await _run(state.create_industry, {"name": "Handel"})
        repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create(self, repo: AsyncMock) -> None:
        state = _state()
        state.open_add_modal()
        with _as_admin(state):
            out = await _run(state.create_industry, {"name": " Handel "})
        assert "angelegt" in out
        assert repo.create.call_args.args[1].name == "Handel"
        assert not state.add_modal_open
        assert len(state.industries) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("error", "message"),
        [
            (IntegrityError("x", {}, Exception()), DUPLICATE_MESSAGE),
            (RuntimeError("db"), "Fehler beim Anlegen"),
        ],
    )
    async def test_create_errors(
        self, repo: AsyncMock, error: Exception, message: str
    ) -> None:
        repo.create.side_effect = error
        state = _state()
        with _as_admin(state):
            out = await _run(state.create_industry, {"name": "Handel"})
        assert message in out

    @pytest.mark.asyncio
    async def test_create_rejects_empty_name(self, repo: AsyncMock) -> None:
        state = _state()
        with _as_admin(state):
            out = await _run(state.create_industry, {"name": "  "})
        assert HINT_NAME in out
        repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_rename(self, repo: AsyncMock) -> None:
        state = _state(Industry(id=2, name="Handel"))
        state.open_edit_modal(2)
        with _as_admin(state):
            out = await _run(state.update_industry, {"name": "Einzelhandel"})
        assert "gespeichert" in out
        assert repo.update.call_args.args[1].name == "Einzelhandel"
        assert not state.edit_modal_open

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_rename_without_selection(self) -> None:
        state = _state()
        with _as_admin(state):
            out = await _run(state.update_industry, {"name": "Handel"})
        assert NOT_FOUND in out

    @pytest.mark.asyncio
    async def test_rename_missing(self, repo: AsyncMock) -> None:
        repo.find_by_id.return_value = None
        state = _state(Industry(id=2, name="Handel"))
        state.open_edit_modal(2)
        with _as_admin(state):
            out = await _run(state.update_industry, {"name": "Handel"})
        assert NOT_FOUND in out

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("name", "error", "message"),
        [
            ("", None, HINT_NAME),
            ("Energie", IntegrityError("x", {}, Exception()), DUPLICATE_MESSAGE),
            ("Energie", RuntimeError("db"), "Fehler beim Speichern"),
        ],
    )
    async def test_rename_errors(
        self, repo: AsyncMock, name: str, error: Exception | None, message: str
    ) -> None:
        repo.update.side_effect = error
        state = _state(Industry(id=2, name="Handel"))
        state.open_edit_modal(2)
        with _as_admin(state):
            out = await _run(state.update_industry, {"name": name})
        assert message in out
        assert state.edit_modal_open

    @pytest.mark.asyncio
    async def test_delete_unused(self, repo: AsyncMock) -> None:
        state = _state(Industry(id=2, name="Handel"))
        with _as_admin(state):
            out = await _run(state.delete_industry, 2)
        assert "gelöscht" in out
        repo.delete_by_id.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_keeps_industry_in_use(self, repo: AsyncMock) -> None:
        repo.count_offers.return_value = 2
        state = _state(Industry(id=2, name="Handel"))
        with _as_admin(state):
            out = await _run(state.delete_industry, 2)
        assert in_use_message(2) in out
        repo.delete_by_id.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("deleted", "error", "message"),
        [
            (False, None, NOT_FOUND),
            (True, RuntimeError("db"), "Fehler beim Löschen"),
        ],
    )
    async def test_delete_errors(
        self,
        repo: AsyncMock,
        deleted: bool,  # noqa: FBT001
        error: Exception | None,
        message: str,
    ) -> None:
        repo.delete_by_id.return_value = deleted
        repo.delete_by_id.side_effect = error
        state = _state()
        with _as_admin(state):
            out = await _run(state.delete_industry, 2)
        assert message in out


class TestComponents:
    def test_table_has_dialogs_and_rows(self) -> None:
        rendered = str(industries_table())
        for name in ("add_modal_open", "edit_modal_open", "delete_industry"):
            assert name in rendered
        assert "filtered_industries" in rendered

    def test_form_limits_the_name(self) -> None:
        rendered = str(industry_form_fields())
        assert "maxLength" in rendered
        assert NAME_HINT

    def test_toolbar(self) -> None:
        assert len(industries_toolbar()) == 2
