# ruff: noqa: ARG001
"""Chapters state and tab."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.workshop.components import chapters_tab
from alloq_offer.workshop.components.workshop_view import workshop_body
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.editor_io import editor_compatible, html_to_content
from alloq_offer.workshop.content.schema import ProseContent, StoriesContent
from alloq_offer.workshop.entities import JobEntity, JobStatus
from alloq_offer.workshop.services.chapters import ChapterService, add_proposal
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import chapter_state
from alloq_offer.workshop.states.chapter_state import ChapterState
from sqlalchemy import select

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.chapter_state"
KEY = "management_summary"


@contextmanager
def _as_editor(state: ChapterState, db):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=1)

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


async def _run(handler: Any, *args: Any) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


def _html(text: str) -> str:
    return f"<p>{text}</p>"


async def _loaded(db) -> ChapterState:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    state = ChapterState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        await _run(state.load_chapters)
    return state


async def test_load_selects_the_first_chapter_and_shows_the_editor(db) -> None:
    state = await _loaded(db)
    assert state.active_key == KEY
    assert state.has_active
    assert state.editable
    assert state.revision == 1
    assert state.editor_key == f"{KEY}:1"
    assert not state.drafting


async def test_load_without_workspace_stays_empty(db) -> None:
    state = ChapterState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        await _run(state.load_chapters)
    assert not state.has_active


async def test_select_projection_chapter_is_read_only(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "user_stories")
        assert not state.editable
        assert state.note == chapter_state.READ_ONLY_NOTE
        assert state.preview_lines
        await _run(state.select_chapter, "user_stories")  # no-op
        assert await _run(state.autosave, "user_stories", _html("x")) == ""
    assert state.revision == 1


async def test_autosave_creates_revisions_and_marks_the_state(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.autosave, KEY, _html("Erster Text"))
        assert (state.revision, state.save_label) == (2, chapter_state.SAVED)
        assert state.active["revision"] == 2
        await _run(state.autosave, "other", _html("ignored"))
    assert state.revision == 2


async def test_autosave_rejects_unsupported_markup(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        toast = await _run(state.autosave, KEY, "<h1>Zu groß</h1>")
    assert "Ebene 1" in toast
    assert state.save_label == chapter_state.INVALID_LABEL
    assert state.revision == 1


async def test_autosave_conflict_reloads_without_overwriting(db) -> None:
    state = await _loaded(db)
    other = ChapterService(db.session, 1, "Ben")
    await other.save(KEY, 1, html_to_content(_html("Von Ben")))
    with _as_editor(state, db):
        toast = await _run(state.autosave, KEY, _html("Spät"))
    assert "inzwischen geändert" in toast
    assert state.save_label == chapter_state.CONFLICT_LABEL
    assert state.revision == 2


async def test_protected_chapter_refuses_saves_and_locks_the_editor(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.set_protected, True)
        assert state.chapter_locked
        toast = await _run(state.autosave, KEY, _html("x"))
        assert "geschützt" in toast
        await _run(state.set_protected, False)
        assert not state.chapter_locked


async def test_history_and_restore(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.autosave, KEY, _html("Eins"))
        await _run(state.autosave, KEY, _html("Zwei"))
        await _run(state.open_history)
        assert state.history_open
        assert [h["number"] for h in state.history] == [3, 2, 1]
        await _run(state.restore, 2)
        assert state.revision == 4
        assert "Eins" in state.editor_html
        stale = await _run(state.restore, 99)
        assert "Fassung" in stale
        state.close_history()
    assert not state.history_open


async def _proposal(db, base: int) -> None:  # noqa: ANN001
    async with db.session() as session:
        await add_proposal(
            session,
            offer_id=1,
            chapter_key=KEY,
            content=ProseContent(),
            base_revision=base,
            map_revision=0,
            instruction="",
            job_id=None,
        )


async def test_accept_and_reject_proposals(db) -> None:
    state = await _loaded(db)
    await _proposal(db, 1)
    with _as_editor(state, db):
        await _run(state.load_chapters)
        assert state.has_proposal
        await _run(state.accept_proposal)
        assert (state.revision, state.origin) == (2, "KI übernommen")
        assert not state.has_proposal
    await _proposal(db, 2)
    with _as_editor(state, db):
        await _run(state.load_chapters)
        await _run(state.reject_proposal)
        assert not state.has_proposal
        assert await _run(state.accept_proposal) == ""


async def test_stale_proposal_shows_a_message_and_reloads(db) -> None:
    state = await _loaded(db)
    await _proposal(db, 0)
    with _as_editor(state, db):
        await _run(state.load_chapters)
        toast = await _run(state.accept_proposal)
    assert "veraltet" in toast
    assert not state.has_proposal


async def test_drafts_are_queued_once_and_polled(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        toast = await _run(state.draft_active, "Kürzen")
        assert chapter_state.DRAFT_QUEUED in toast
        assert state.drafting
        assert await _run(state.draft_all) == ""  # busy
        assert await _run(state.refresh_drafts) == ""
        assert state.drafting
    async with db.session() as session:
        job = (await session.scalars(select(JobEntity))).one()
        assert job.payload == {"keys": [KEY], "instruction": "Kürzen"}
        job.status = JobStatus.SUCCEEDED
    with _as_editor(state, db):
        await _run(state.refresh_drafts)
    assert not state.drafting


async def test_draft_all_and_free_instruction(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        state.set_instruction("Nenne Annahmen zuerst")
        await _run(state.draft_all)
    async with db.session() as session:
        job = (await session.scalars(select(JobEntity))).one()
        assert job.payload["keys"] is None
        assert job.payload["instruction"] == "Nenne Annahmen zuerst"


async def test_draft_for_a_projection_chapter_is_refused(db) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "verguetung")
        toast = await _run(state.draft_active, "")
    assert "keinen KI-Vorschlag" in toast


async def test_load_errors_show_a_toast(db) -> None:
    state = await _loaded(db)
    with (
        _as_editor(state, db),
        patch.object(ChapterService, "open", AsyncMock(side_effect=RuntimeError("x"))),
    ):
        assert chapter_state.LOAD_ERROR in await _run(state.load_chapters)


async def test_save_errors_show_a_toast(db) -> None:
    state = await _loaded(db)
    with (
        _as_editor(state, db),
        patch.object(ChapterService, "save", AsyncMock(side_effect=RuntimeError("x"))),
    ):
        assert chapter_state.SAVE_ERROR in await _run(state.autosave, KEY, _html("x"))


def test_components_render_constants() -> None:
    tab = str(chapters_tab.chapters_tab())
    assert "autosave" in tab
    assert "accept_proposal" in tab
    assert "refresh_drafts" in tab
    assert "chapters" in str(workshop_body())


def test_editor_compatibility() -> None:
    assert editor_compatible(ProseContent())
    assert not editor_compatible(StoriesContent())
