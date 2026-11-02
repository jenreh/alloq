# ruff: noqa: ARG001
"""Export state and tab."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.workshop.components import export_tab, workshop_view
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.services.chapters import ChapterService
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import export_state
from alloq_offer.workshop.states.chapter_state import CONFLICT_LABEL, ChapterState
from alloq_offer.workshop.states.export_state import ExportState
from alloq_offer.workshop.states.workshop_state import TAB_EXPORT

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.export_state"


@contextmanager
def _as_editor(state: ExportState, db, save_label: str = ""):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        if cls is LoginState:
            return login
        if cls is ChapterState:
            return SimpleNamespace(save_label=save_label)
        return SimpleNamespace(offer_id=1)

    registry = MagicMock()
    registry.get.return_value = WorkshopConfig()
    object.__setattr__(state, "get_state", _get_state)
    with (
        patch(f"{MODULE}.get_asyncdb_session", db.session),
        patch(f"{MODULE}.service_registry", return_value=registry),
    ):
        try:
            yield
        finally:
            object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> list[Any]:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return [i async for i in result if i is not None]
    await result
    return []


async def _prepared(db) -> ExportState:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    await ChapterService(db.session, 1, "Anna").open()
    return ExportState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]


async def test_draft_request_lists_the_export(db) -> None:  # noqa: ANN001
    state = await _prepared(db)
    with _as_editor(state, db):
        await _run(state.load_exports)
        assert state.exports == []
        assert state.open_blockers == 0
        await _run(state.export_draft)
        assert state.working
        assert state.exports[0]["kind"] == "Entwurf"
        await _run(state.refresh_exports)
    assert state.reasons == []


async def test_final_request_shows_the_reasons(db) -> None:  # noqa: ANN001
    state = await _prepared(db)
    with _as_editor(state, db):
        await _run(state.export_final)
        assert state.reasons
        assert state.exports == []
        state.set_confirmed(True)
        assert state.confirmed
        await _run(state.export_final)
        assert not state.confirmed


async def test_conflict_in_the_editor_blocks_the_request(db) -> None:  # noqa: ANN001
    state = await _prepared(db)
    with _as_editor(state, db, save_label=CONFLICT_LABEL):
        await _run(state.export_draft)
    assert any("ungespeicherte" in r for r in state.reasons)


async def test_download_of_an_unfinished_export_is_refused(db) -> None:  # noqa: ANN001
    state = await _prepared(db)
    with _as_editor(state, db):
        await _run(state.export_draft)
        events = await _run(state.download_export, state.exports[0]["id"])
    assert len(events) == 1
    assert export_state.exports.NOT_READY in str(events[0])


async def test_request_failure_gives_a_toast(db) -> None:  # noqa: ANN001
    state = await _prepared(db)
    with (
        _as_editor(state, db),
        patch(f"{MODULE}.exports.request_export", side_effect=RuntimeError("x")),
    ):
        events = await _run(state.export_draft)
    assert export_state.REQUEST_ERROR in str(events[0])


def test_tab_renders_and_is_wired() -> None:
    tab = export_tab.export_tab()
    text = str(tab)
    assert "export_draft" in text
    assert "export_final" in text
    assert "on_mount" in tab.event_triggers
    assert TAB_EXPORT == "export"
    assert "export_tab" in workshop_view.__dict__
