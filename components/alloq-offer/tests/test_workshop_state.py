"""Tests of the workshop page state, components and wiring."""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.components import draft_tab
from alloq_offer.workshop.components.workshop_view import workshop_body, workshop_tabs
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.pages import WORKSHOP_ROUTE, create_offer_workshop_page
from alloq_offer.workshop.states import workshop_state
from alloq_offer.workshop.states.workshop_state import (
    LOAD_ERROR,
    TAB_EXPORT,
    WorkshopState,
)
from alloq_offer.workshop.worker import offer_workshop_worker

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.workshop_state"


def _offer() -> OfferEntity:
    entity = OfferEntity(
        title="Plattform",
        customer="Muster AG",
        person_days=Decimal(10),
        risk_buffer_days=Decimal(1),
        production_cost=Decimal(1000),
        recommended_price=Decimal(2000),
        key_accounter="Anna",
        industry_id=1,
        state="Neu",
    )
    entity.id = 5
    return entity


def _workspace(auto_draft: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        template_key="quo_v1", doc_state="Entwurf", auto_draft=auto_draft
    )


@pytest.fixture
def repo() -> Generator[AsyncMock]:
    @asynccontextmanager
    async def _ctx() -> AsyncGenerator[Any]:
        yield AsyncMock()

    offers = AsyncMock()
    offers.find_by_id = AsyncMock(return_value=_offer())
    with (
        patch(f"{MODULE}.offer_repo", offers),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
        patch.object(WorkshopState, "_route_offer_id", lambda _self: 5),
    ):
        yield offers


@contextmanager
def _as_offer_editor(state: WorkshopState) -> Generator[None]:
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"], name="Anna")
    user.name = "Anna"

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


def _state() -> WorkshopState:
    return WorkshopState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]


@pytest.mark.usefixtures("repo")
async def test_load_workshop_fills_header_and_workspace() -> None:
    state = _state()
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.open_workspace", AsyncMock(return_value=_workspace(True))),
    ):
        await _run(state.load_workshop)
    assert state.loaded
    assert (state.offer_id, state.offer_title) == (5, "Plattform")
    assert state.auto_draft
    assert state.subtitle == "Muster AG · Vorlage QUO V1 · Entwurf"


async def test_load_workshop_unknown_offer(repo: AsyncMock) -> None:
    repo.find_by_id = AsyncMock(return_value=None)
    state = _state()
    with _as_offer_editor(state):
        await _run(state.load_workshop)
    assert state.not_found
    assert not state.loaded
    assert state.subtitle == ""


@pytest.mark.usefixtures("repo")
async def test_load_workshop_reports_errors() -> None:
    state = _state()
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.open_workspace", AsyncMock(side_effect=RuntimeError("x"))),
    ):
        toast = await _run(state.load_workshop)
    assert LOAD_ERROR in toast
    assert not state.loaded


@pytest.mark.usefixtures("repo")
async def test_set_auto_draft_persists() -> None:
    state = _state()
    state.loaded = True
    workspace = _workspace()
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.open_workspace", AsyncMock(return_value=workspace)),
    ):
        await _run(state.set_auto_draft, True)
    assert state.auto_draft
    assert workspace.auto_draft


@pytest.mark.usefixtures("repo")
async def test_set_auto_draft_reports_errors() -> None:
    state = _state()
    state.loaded = True
    with (
        _as_offer_editor(state),
        patch(f"{MODULE}.open_workspace", AsyncMock(side_effect=RuntimeError("x"))),
    ):
        toast = await _run(state.set_auto_draft, True)
    assert workshop_state.SAVE_ERROR in toast
    assert not state.auto_draft


def test_set_tab_and_route_param() -> None:
    state = _state()
    state.set_tab(TAB_EXPORT)
    assert state.active_tab == TAB_EXPORT


def test_route_offer_id_parses_param() -> None:
    state = _state()
    for params, expected in (({"offer_id": "12"}, 12), ({"offer_id": "x"}, 0), ({}, 0)):
        router = SimpleNamespace(page=SimpleNamespace(params=params))
        with patch.object(WorkshopState, "router", router, create=True):
            assert state._route_offer_id() == expected  # noqa: SLF001


def test_components_render_constants() -> None:
    card = str(draft_tab.start_card())
    assert "set_auto_draft" in card
    assert "set_tab" in str(workshop_tabs())
    body = str(workshop_body())
    assert "not_found" in body
    assert "active_tab" in body


def test_page_route_and_registration() -> None:
    assert WORKSHOP_ROUTE == "/offers/[offer_id]/werkstatt"
    page = create_offer_workshop_page(MagicMock())
    assert page is not None


async def test_worker_exits_when_disabled() -> None:
    registry = MagicMock()
    registry.get.return_value = WorkshopConfig(worker_enabled=False)
    with patch("alloq_offer.workshop.worker.service_registry", return_value=registry):
        await offer_workshop_worker()


async def test_worker_runs_runner_when_enabled() -> None:
    registry = MagicMock()
    registry.get.return_value = WorkshopConfig(worker_enabled=True)
    runner = MagicMock()
    runner.run_forever = AsyncMock()
    with (
        patch("alloq_offer.workshop.worker.service_registry", return_value=registry),
        patch("alloq_offer.workshop.worker.JobRunner", return_value=runner),
    ):
        await offer_workshop_worker()
    runner.run_forever.assert_awaited_once()


async def test_set_auto_draft_ignored_before_load() -> None:
    state = _state()
    with _as_offer_editor(state):
        await _run(state.set_auto_draft, True)
    assert not state.auto_draft
