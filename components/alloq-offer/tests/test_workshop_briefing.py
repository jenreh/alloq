"""Tests of the briefing service, state and tab."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.workshop.components.briefing_tab import CONFIRM, EMPTY, briefing_tab
from alloq_offer.workshop.entities import (
    SourceBlockEntity,
    SourceEntity,
    StatementEntity,
    StatementStatus,
    StatementType,
)
from alloq_offer.workshop.services.briefing import load_briefing, set_confirmed
from alloq_offer.workshop.states import briefing_state
from alloq_offer.workshop.states.briefing_state import BriefingState
from sqlalchemy import select

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.briefing_state"
NOW = datetime(2026, 10, 25, tzinfo=UTC)


async def _seed(db) -> list[int]:  # noqa: ANN001
    async with db.session() as session:
        source = SourceEntity(
            offer_id=1, kind="eml", title="Anfrage.eml", sha256="a", status="nutzbar"
        )
        session.add(source)
        await session.flush()
        block = SourceBlockEntity(
            source_id=source.id, seq=1, kind="paragraph", anchor={"page": 3}, text="x"
        )
        revoked = SourceEntity(
            offer_id=1,
            kind="txt",
            title="Weg",
            sha256="b",
            status="nutzbar",
            revoked_at=NOW,
        )
        session.add_all([block, revoked])
        await session.flush()
        gone = SourceBlockEntity(
            source_id=revoked.id, seq=1, kind="paragraph", anchor={}, text="y"
        )
        session.add(gone)
        await session.flush()
        for type_, text, refs in (
            (StatementType.CONFLICT, "A und B widersprechen sich", [block.id, gone.id]),
            (StatementType.REQUIREMENT, "Schneller", [block.id]),
            (StatementType.ASSUMPTION, "Zugriff", []),
        ):
            session.add(
                StatementEntity(
                    offer_id=1,
                    type=type_,
                    text=text,
                    source_refs=refs,
                    needs_recheck=type_ == StatementType.REQUIREMENT and not refs,
                )
            )
        await session.flush()
        return [block.id]


async def test_briefing_groups_follow_the_fixed_type_order(db) -> None:
    await _seed(db)
    async with db.session() as session:
        groups = await load_briefing(session, 1)
    assert [g["type"] for g in groups] == [
        "Kundenanforderung",
        "Annahme",
        "Widerspruch",
    ]
    conflict = groups[2]["items"][0]
    assert conflict["refs"] == ["Anfrage.eml, Seite 3"]
    assert groups[1]["items"][0]["refs"] == []
    assert not conflict["confirmed"]


async def test_empty_briefing_has_no_groups(db) -> None:
    async with db.session() as session:
        assert await load_briefing(session, 1) == []


async def test_confirming_is_explicit_and_can_be_withdrawn(db) -> None:
    await _seed(db)
    async with db.session() as session:
        statement = (await session.scalars(select(StatementEntity))).first()
        statement.needs_recheck = True
        statement_id = statement.id
    assert await set_confirmed(
        db.session, 1, statement_id, confirmed=True, user="Anna", now=NOW
    )
    async with db.session() as session:
        row = await session.get(StatementEntity, statement_id)
        assert (row.status, row.confirmed_by, row.needs_recheck) == (
            StatementStatus.CONFIRMED,
            "Anna",
            False,
        )
    assert await set_confirmed(
        db.session, 1, statement_id, confirmed=False, user="Anna", now=NOW
    )
    async with db.session() as session:
        row = await session.get(StatementEntity, statement_id)
        assert (row.status, row.confirmed_by, row.confirmed_at) == (
            StatementStatus.PROPOSED,
            None,
            None,
        )


async def test_confirming_a_foreign_or_missing_statement_does_nothing(db) -> None:
    await _seed(db)
    async with db.session() as session:
        statement_id = (await session.scalars(select(StatementEntity))).first().id
    for offer_id, sid in ((2, statement_id), (1, 999)):
        assert not await set_confirmed(
            db.session, offer_id, sid, confirmed=True, user="A", now=NOW
        )


@contextmanager
def _as_editor(state: BriefingState, db, offer_id: int = 1):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=offer_id)

    object.__setattr__(state, "get_state", _get_state)
    with patch(f"{MODULE}.get_asyncdb_session", db.session):
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


def _state() -> BriefingState:
    return BriefingState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]


async def test_state_loads_and_confirms(db) -> None:
    await _seed(db)
    state = _state()
    with _as_editor(state, db):
        await _run(state.load_briefing)
        assert not state.is_empty
        item_id = state.groups[0]["items"][0]["id"]
        await _run(state.confirm, item_id, True)
    assert state.groups[0]["items"][0]["confirmed"]


async def test_state_without_offer_and_on_errors(db) -> None:
    state = _state()
    with _as_editor(state, db, offer_id=0):
        await _run(state.load_briefing)
    assert state.is_empty
    with (
        _as_editor(state, db),
        patch(f"{MODULE}.load_briefing", AsyncMock(side_effect=RuntimeError)),
    ):
        assert briefing_state.LOAD_ERROR in await _run(state.load_briefing)
        assert briefing_state.SAVE_ERROR in await _run(state.confirm, 1, True)
    with _as_editor(state, db):
        assert briefing_state.NOT_FOUND in await _run(state.confirm, 999, True)
    with _as_editor(state, db, offer_id=0):
        assert await _run(state.confirm, 1, True) == ""


def test_tab_renders_constants() -> None:
    tab = str(briefing_tab())
    assert "is_empty" in tab
    assert EMPTY
    assert CONFIRM
