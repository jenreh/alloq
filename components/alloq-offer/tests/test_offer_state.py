"""Tests of the offers state."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_commons.entities import ProjectEntity
from alloq_commons.roles import OFFER_EDITOR_ROLE
from alloq_offer.entities import IndustryEntity, OfferEntity
from alloq_offer.models import Industry, Offer
from alloq_offer.states import offer_state
from alloq_offer.states.offer_state import OfferState, number_text

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.states.offer_state"


def _entity(offer_id: int = 1, **over: Any) -> OfferEntity:
    values: dict[str, Any] = {
        "title": "Plattform",
        "customer": "Muster AG",
        "person_days": Decimal(10),
        "risk_buffer_days": Decimal(2),
        "production_cost": Decimal(1000),
        "recommended_price": Decimal(2000),
        "key_accounter": "Anna",
        "industry_id": 2,
        "state": "Neu",
        "archived": False,
        **over,
    }
    entity = OfferEntity(**values)
    entity.id = offer_id
    return entity


def _industry() -> IndustryEntity:
    entity = IndustryEntity(name="Finanzdienstleistungen")
    entity.id = 2
    return entity


def _offer(offer_id: int = 1, **over: Any) -> Offer:
    return Offer(**_entity(offer_id, **over).to_dict())


def _persisted(_session: Any, entity: OfferEntity) -> OfferEntity:
    entity.id = 7
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
    mock.create = AsyncMock(side_effect=_persisted)
    mock.project_codes = AsyncMock(return_value={})
    industries = AsyncMock()
    industries.find_all_ordered = AsyncMock(return_value=[_industry()])
    with (
        patch(f"{MODULE}.offer_repo", mock),
        patch(f"{MODULE}.industry_repo", industries),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
        patch(f"{MODULE}.void_after_offer_edit", AsyncMock(return_value=False)),
    ):
        yield mock


@contextmanager
def _as_offer_editor(state: OfferState, *, is_admin: bool = False) -> Iterator[None]:
    roles = [] if is_admin else [OFFER_EDITOR_ROLE.name]
    user = MagicMock(is_admin=is_admin, user_id=1, roles=roles)

    async def _user() -> MagicMock:
        return user

    async def _signed_in() -> bool:
        return True

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    type(login).is_authenticated = property(lambda _self: _signed_in())
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


def _state(*offers: Offer) -> OfferState:
    state = OfferState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    state.offers = list(offers)
    state.industries = [Industry(id=2, name="Finanzdienstleistungen")]
    return state


FORM = {
    "title": "Neu",
    "customer": "Kunde",
    "key_accounter": "Bea",
    "industry_id": "2",
    "person_days": "5",
    "risk_buffer_days": "0",
    "production_cost": "100",
    "recommended_price": "200",
    "state": "Neu",
    "sent_date": "",
    "sharepoint_url": "",
}


class TestNumberText:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [(1.5, "1.5"), ("1.120,50 €", "1120.50"), ("", ""), (None, ""), ("x", "")],
    )
    def test_normalizes(self, raw: Any, expected: str) -> None:
        assert number_text(raw) == expected


class TestUiHandlers:
    def test_filter_and_sort(self) -> None:
        state = _state()
        state.set_list_filter("Unbekannt")
        assert state.list_filter == "Alle"
        state.toggle_sort("title")
        state.toggle_sort("title")
        assert state.sort_desc is True
        state.toggle_sort("nope")
        assert state.sort_column == "title"

    def test_reset_filters(self) -> None:
        state = _state()
        state.set_search_filter("acme")
        state.set_list_filter("Archiviert")
        state.reset_filters()
        assert state.search_filter == ""
        assert state.list_filter == "Alle"

    def test_modal_and_form(self) -> None:
        state = _state(_offer())
        state.open_create_modal()
        assert state.form_open
        assert state.editing_id == 0
        assert state.is_form_invalid
        state.set_form_field("person_days", "1,5")
        state.set_form_field("bogus", "x")
        assert state.form["person_days"] == "1.5"
        state.open_edit_modal(1)
        assert state.editing_id == 1
        assert state.form["title"] == "Plattform"
        assert state.form["industry_id"] == "2"
        state.open_edit_modal(99)
        assert state.editing_id == 1
        state.close_modal()
        assert not state.form_open

    def test_inspector(self) -> None:
        state = _state(_offer(1), _offer(2, title="Zweites"))
        state.inspect(2)
        assert state.inspected is not None
        assert state.inspected.id == 2
        assert state.inspected_total_days == 12.0
        assert state.inspected_margin == "50,0 %"
        state.toggle_inspector()
        assert not state.show_inspector

    def test_sent_date_draft(self) -> None:
        state = _state(_offer())
        state.inspect(1)
        state.set_inspected_sent_date(1, "2026-01-02")
        assert state.inspected_sent_date == "2026-01-02"

    def test_sent_date_today_sets_draft(self) -> None:
        state = _state(_offer())
        state.inspect(1)
        state.set_sent_date_today(1)
        assert state.inspected_sent_date == offer_state._today().isoformat()

    def test_nothing_inspected_without_selection(self) -> None:
        assert _state(_offer()).inspected is None

    def test_groups_and_archived(self) -> None:
        state = _state(_offer(1), _offer(2, archived=True, state="Versendet"))
        assert [o.id for o in state.new_rows] == [1]
        assert state.sent_rows == []
        state.set_list_filter("Archiviert")
        assert [o.id for o in state.archived_rows] == [2]
        assert state.new_rows == []
        assert state.row_count == 1
        assert state.subtitle.startswith("1 Angebote")
        assert state.total_person_days == 12.0


class TestDataHandlers:
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_load(self) -> None:
        state = _state()
        with _as_offer_editor(state):
            await _run(state.load_offers)
        assert len(state.offers) == 1
        assert state.offers[0].industry == "Finanzdienstleistungen"
        assert state.industry_options == [
            {"value": "2", "label": "Finanzdienstleistungen"}
        ]
        assert not state.is_loading

    @pytest.mark.asyncio
    async def test_load_error(self, repo: AsyncMock) -> None:
        repo.find_all_ordered.side_effect = RuntimeError("db")
        state = _state()
        with _as_offer_editor(state):
            out = await _run(state.load_offers)
        assert "geladen" in out

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_create(self) -> None:
        state = _state()
        state.open_create_modal()
        state.form = dict(FORM)
        with _as_offer_editor(state):
            out = await _run(state.create_offer, {"title": " Neu "})
        assert "angelegt" in out
        assert state.offers[0].title == "Neu"
        assert state.offers[0].industry == "Finanzdienstleistungen"
        assert not state.form_open

    @pytest.mark.asyncio
    async def test_admin_without_role_may_not_create(self, repo: AsyncMock) -> None:
        state = _state()
        state.form = dict(FORM)
        with _as_offer_editor(state, is_admin=True):
            out = await _run(state.create_offer, {"title": "Neu"})
        assert "Berechtigung" in out
        repo.create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_create_sent_sets_today(self) -> None:
        state = _state()
        state.form = {**FORM, "state": "Versendet"}
        with _as_offer_editor(state):
            await _run(state.create_offer, {})
        assert state.offers[0].sent_date is not None

    @pytest.mark.asyncio
    async def test_create_invalid(self, repo: AsyncMock) -> None:
        state = _state()
        state.form = {**FORM, "title": ""}
        with _as_offer_editor(state):
            out = await _run(state.create_offer, {})
        assert offer_state.HINT_INVALID in out
        repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_error(self, repo: AsyncMock) -> None:
        repo.create.side_effect = RuntimeError("db")
        state = _state()
        state.form = dict(FORM)
        with _as_offer_editor(state):
            out = await _run(state.create_offer, {})
        assert offer_state.ERROR_SAVE in out

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_update(self) -> None:
        state = _state(_offer())
        state.open_edit_modal(1)
        state.set_form_field("title", "Anders")
        with _as_offer_editor(state):
            out = await _run(state.update_offer, {})
        assert "aktualisiert" in out
        assert state.offers[0].title == "Anders"

    @pytest.mark.asyncio
    async def test_update_missing(self, repo: AsyncMock) -> None:
        repo.find_by_id.return_value = None
        state = _state(_offer())
        state.open_edit_modal(1)
        with _as_offer_editor(state):
            out = await _run(state.update_offer, {})
        assert offer_state.NOT_FOUND in out

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_state_change_sets_date(self) -> None:
        state = _state(_offer())
        with _as_offer_editor(state):
            out = await _run(state.update_inspected_state, 1, "Versendet")
        assert "Status gespeichert" in out
        assert state.offers[0].state == "Versendet"
        assert state.offers[0].sent_date == offer_state._today()

    @pytest.mark.asyncio
    async def test_state_change_keeps_date(self, repo: AsyncMock) -> None:
        sent = date(2026, 1, 1)
        repo.find_by_id.return_value = _entity(state="Versendet", sent_date=sent)
        state = _state(_offer(state="Versendet", sent_date=sent))
        with _as_offer_editor(state):
            await _run(state.update_inspected_state, 1, "In Bearbeitung")
        assert state.offers[0].sent_date == sent

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_state_change_invalid(self) -> None:
        state = _state(_offer())
        with _as_offer_editor(state):
            out = await _run(state.update_inspected_state, 1, "Foo")
        assert "Ungültig" in out

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_sent_date_edit(self) -> None:
        state = _state(_offer())
        state.set_inspected_sent_date(1, "2026-03-04")
        with _as_offer_editor(state):
            out = await _run(state.save_inspected_sent_date, 1)
        assert "Datum gespeichert" in out
        assert state.offers[0].sent_date == date(2026, 3, 4)
        assert state.date_draft_id == 0

    @pytest.mark.asyncio
    async def test_sent_date_edge_cases(self, repo: AsyncMock) -> None:
        state = _state(_offer())
        with _as_offer_editor(state):
            assert await _run(state.save_inspected_sent_date, 1) == ""
            state.set_inspected_sent_date(1, "kaputt")
            assert "gültiges Datum" in await _run(state.save_inspected_sent_date, 1)
            state.set_inspected_sent_date(1, "")
            assert await _run(state.save_inspected_sent_date, 1) == ""
        repo.find_by_id.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_archive_and_restore(self) -> None:
        state = _state(_offer())
        with _as_offer_editor(state):
            await _run(state.archive_offer, 1)
            assert state.offers[0].archived
            assert state.visible == []
            await _run(state.restore_offer, 1)
        assert not state.offers[0].archived

    @pytest.mark.asyncio
    async def test_persist_error(self, repo: AsyncMock) -> None:
        repo.find_by_id.side_effect = RuntimeError("db")
        state = _state(_offer())
        with _as_offer_editor(state):
            out = await _run(state.archive_offer, 1)
        assert offer_state.ERROR_SAVE in out


class TestUpdateWithoutEditId:
    async def test_update_without_editing_id_does_not_create(self) -> None:
        state = _state()
        with _as_offer_editor(state):
            out = await _run(state.update_offer, FORM)
        assert "nicht gefunden" in out


def _project_entity(code: str = "ABC") -> Any:
    entity = ProjectEntity(
        code=code,
        name_de="x",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        budget=0,
    )
    entity.id = 40
    return entity


@pytest.fixture
def projects() -> Iterator[AsyncMock]:
    mock = AsyncMock()
    mock.find_by_code = AsyncMock(return_value=None)

    async def _create(_session: Any, entity: Any) -> Any:
        entity.id = 40
        return entity

    mock.create = AsyncMock(side_effect=_create)
    with patch(f"{MODULE}.project_repo", mock):
        yield mock


class TestAcceptOffer:
    def test_open_modal_prefills_dates(self) -> None:
        state = _state(_offer())
        state.open_accept_modal(1)
        assert state.accept_open
        assert state.accept_form["code"] == ""
        assert state.accept_form["start_date"] == offer_state._today().isoformat()
        assert state.accept_form["end_date"] > state.accept_form["start_date"]
        state.set_accept_field("code", "ABC")
        state.set_accept_field("bogus", "x")
        assert state.accept_form["code"] == "ABC"
        assert not state.is_accept_invalid
        state.set_accept_field("code", " ")
        assert state.is_accept_invalid
        state.close_accept_modal()
        assert not state.accept_open

    def test_open_modal_ignores_unacceptable_offers(self) -> None:
        state = _state(_offer(project_id=3))
        state.open_accept_modal(1)
        state.open_accept_modal(99)
        assert not state.accept_open

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("projects")
    async def test_accept_creates_planned_project(
        self, repo: AsyncMock, projects: AsyncMock
    ) -> None:
        entity = _entity()
        repo.find_by_id.return_value = entity
        repo.project_codes = AsyncMock(return_value={40: "ABC"})
        state = _state(_offer())
        state.open_accept_modal(1)
        state.set_accept_field("code", " ABC ")
        with _as_offer_editor(state):
            out = await _run(state.accept_offer, {})
        assert "Projekt 'ABC'" in out
        created = projects.create.call_args.args[1]
        assert (created.code, created.state, created.budget) == ("ABC", "Geplant", 2000)
        assert entity.project_id == 40
        assert state.offers[0].project_id == 40
        assert state.offers[0].project_code == "ABC"
        assert not state.accept_open

    @pytest.mark.asyncio
    async def test_accept_rejects_taken_code(
        self, repo: AsyncMock, projects: AsyncMock
    ) -> None:
        projects.find_by_code.return_value = _project_entity()
        state = _state(_offer())
        state.open_accept_modal(1)
        state.set_accept_field("code", "ABC")
        with _as_offer_editor(state):
            out = await _run(state.accept_offer, {})
        assert "bereits vergeben" in out
        projects.create.assert_not_called()
        assert repo.find_by_id.return_value.project_id is None
        assert state.accept_open

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("projects")
    async def test_accept_rejects_bad_input(self, repo: AsyncMock) -> None:
        state = _state(_offer())
        state.open_accept_modal(1)
        with _as_offer_editor(state):
            assert offer_state.HINT_ACCEPT in await _run(state.accept_offer, {})
            state.set_accept_field("code", "ABC")
            state.set_accept_field("end_date", "2020-01-01")
            assert offer_state.HINT_ACCEPT in await _run(state.accept_offer, {})
            state.set_accept_field("end_date", "kaputt")
            assert offer_state.HINT_ACCEPT in await _run(state.accept_offer, {})
        repo.find_by_id.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("projects")
    async def test_accept_twice_creates_one_project(
        self, repo: AsyncMock, projects: AsyncMock
    ) -> None:
        repo.find_by_id.return_value = _entity(project_id=40)
        state = _state(_offer())
        state.open_accept_modal(1)
        state.set_accept_field("code", "ABC")
        with _as_offer_editor(state):
            out = await _run(state.accept_offer, {})
        assert offer_state.ALREADY_ACCEPTED in out
        projects.create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("projects")
    async def test_accept_missing_offer(self, repo: AsyncMock) -> None:
        repo.find_by_id.return_value = None
        state = _state(_offer())
        state.open_accept_modal(1)
        state.set_accept_field("code", "ABC")
        with _as_offer_editor(state):
            assert offer_state.NOT_FOUND in await _run(state.accept_offer, {})

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("repo")
    async def test_accept_error(self, projects: AsyncMock) -> None:
        projects.create.side_effect = RuntimeError("db")
        state = _state(_offer())
        state.open_accept_modal(1)
        state.set_accept_field("code", "ABC")
        with _as_offer_editor(state):
            assert offer_state.ERROR_ACCEPT in await _run(state.accept_offer, {})

    @pytest.mark.asyncio
    async def test_accept_needs_offer_editor(self, projects: AsyncMock) -> None:
        state = _state(_offer())
        state.open_accept_modal(1)
        with _as_offer_editor(state, is_admin=True):
            out = await _run(state.accept_offer, {})
        assert "Berechtigung" in out
        projects.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_without_calculation(repo: AsyncMock) -> None:
    state = _state()
    state.form = {
        **FORM,
        "person_days": "",
        "risk_buffer_days": "",
        "production_cost": "",
        "recommended_price": "",
    }
    assert not state.is_form_invalid
    with _as_offer_editor(state):
        out = await _run(state.create_offer, {})
    assert offer_state.HINT_INVALID not in out
    repo.create.assert_called_once()
