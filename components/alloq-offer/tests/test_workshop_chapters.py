"""Chapter service: template start, conflicts, history, proposals, review marks."""

import pytest
from alloq_offer.workshop.content.schema import (
    Paragraph,
    ProseContent,
    Run,
    StoriesContent,
)
from alloq_offer.workshop.entities import (
    ChapterEntity,
    ProposalEntity,
    ProposalStatus,
)
from alloq_offer.workshop.services import chapters
from alloq_offer.workshop.services.chapters import (
    ChapterConflictError,
    ChapterError,
    ChapterService,
    add_proposal,
    mark_dependent_review,
)
from alloq_offer.workshop.services.map_edit import MapEditor
from alloq_offer.workshop.services.workspace import open_workspace
from sqlalchemy import select

KEY = "management_summary"


def _prose(text: str) -> ProseContent:
    return ProseContent(blocks=[Paragraph(runs=[Run(text=text)])])


async def _service(db, user: str = "Anna") -> ChapterService:
    async with db.session() as session:
        await open_workspace(session, 1, user)
    service = ChapterService(db.session, 1, user)
    await service.open()
    return service


async def test_open_creates_template_chapters_once(db) -> None:
    service = await _service(db)
    views = await service.open()
    keys = [v["key"] for v in views]
    assert keys[0] == "management_summary"
    assert len(keys) == len(set(keys))
    assert all(v["revision"] == 1 for v in views)
    stories = next(v for v in views if v["type"] == "stories")
    loaded = await service.load(stories["key"])
    assert StoriesContent.model_validate(loaded["content"]).scopes == [
        "angeboten",
        "option",
    ]


async def test_open_without_workspace_is_empty(db) -> None:
    assert await ChapterService(db.session, 1, "Anna").open() == []


async def test_save_creates_revision_and_rejects_stale_editor(db) -> None:
    service = await _service(db)
    assert await service.save(KEY, 1, _prose("Erste Fassung")) == 2
    with pytest.raises(ChapterConflictError):
        await service.save(KEY, 1, _prose("Überschreibt"))
    loaded = await service.load(KEY)
    assert loaded["revision"] == 2
    assert loaded["content"]["blocks"][0]["runs"][0]["text"] == "Erste Fassung"


async def test_save_rejects_wrong_type_and_protected_chapter(db) -> None:
    service = await _service(db)
    with pytest.raises(ChapterError, match=chapters.WRONG_TYPE):
        await service.save(KEY, 1, StoriesContent())
    await service.set_protected(KEY, True)
    with pytest.raises(ChapterError, match="geschützt"):
        await service.save(KEY, 1, _prose("x"))
    await service.set_protected(KEY, False)
    assert await service.save(KEY, 1, _prose("x")) == 2


async def test_unknown_chapter(db) -> None:
    service = await _service(db)
    with pytest.raises(ChapterError, match=chapters.NOT_FOUND):
        await service.load("gibt_es_nicht")


async def test_history_lists_newest_first_with_diff_and_restores(db) -> None:
    service = await _service(db)
    await service.save(KEY, 1, _prose("Eins"))
    await service.save(KEY, 2, _prose("Zwei"))
    history = await service.history(KEY)
    assert [h["number"] for h in history] == [3, 2, 1]
    kinds = {(d["kind"], d["text"]) for d in history[0]["diff"]}
    assert ("added", "Zwei") in kinds
    assert ("removed", "Eins") in kinds
    assert await service.restore(KEY, 3, 2) == 4
    loaded = await service.load(KEY)
    assert loaded["content"]["blocks"][0]["runs"][0]["text"] == "Eins"
    with pytest.raises(ChapterConflictError):
        await service.restore(KEY, 3, 2)
    with pytest.raises(ChapterError, match=chapters.NO_REVISION):
        await service.restore(KEY, 4, 99)


async def _propose(db, base: int, text: str = "KI Text") -> int:
    async with db.session() as session:
        proposal = await add_proposal(
            session,
            offer_id=1,
            chapter_key=KEY,
            content=_prose(text),
            base_revision=base,
            map_revision=0,
            instruction="kürzen",
            job_id=None,
        )
        await session.flush()
        return proposal.id


async def test_accept_proposal_creates_ai_revision(db) -> None:
    service = await _service(db)
    proposal_id = await _propose(db, 1)
    loaded = await service.load(KEY)
    assert loaded["proposal"]["id"] == proposal_id
    assert (await service.open())[0]["proposal"]
    assert await service.accept(proposal_id, 1) == 2
    loaded = await service.load(KEY)
    assert loaded["origin"] == "KI übernommen"
    assert loaded["proposal"] is None
    with pytest.raises(ChapterError, match=chapters.NO_PROPOSAL):
        await service.accept(proposal_id, 2)


async def test_proposal_becomes_stale_when_a_person_saved(db) -> None:
    service = await _service(db)
    proposal_id = await _propose(db, 1)
    await service.save(KEY, 1, _prose("Von Hand"))
    async with db.session() as session:
        row = await session.get(ProposalEntity, proposal_id)
        assert row is not None
        assert row.status == ProposalStatus.STALE
    with pytest.raises(ChapterError, match=chapters.NO_PROPOSAL):
        await service.accept(proposal_id, 2)


async def test_stale_base_revision_is_refused_and_marked(db) -> None:
    service = await _service(db)
    proposal_id = await _propose(db, 0)
    with pytest.raises(ChapterError, match=chapters.STALE_PROPOSAL):
        await service.accept(proposal_id, 1)
    async with db.session() as session:
        row = await session.get(ProposalEntity, proposal_id)
        assert row is not None
        assert row.status == ProposalStatus.STALE


async def test_protected_chapter_refuses_proposal_and_reject_works(db) -> None:
    service = await _service(db)
    proposal_id = await _propose(db, 1)
    await service.set_protected(KEY, True)
    with pytest.raises(ChapterError, match="geschützt"):
        await service.accept(proposal_id, 1)
    await service.reject(proposal_id)
    assert (await service.load(KEY))["proposal"] is None
    with pytest.raises(ChapterError, match=chapters.NO_PROPOSAL):
        await service.reject(9999)


async def test_new_proposal_replaces_the_open_one(db) -> None:
    service = await _service(db)
    first = await _propose(db, 1, "Alt")
    second = await _propose(db, 1, "Neu")
    assert (await service.load(KEY))["proposal"]["id"] == second
    with pytest.raises(ChapterError):
        await service.accept(first, 1)


async def test_map_edit_flags_written_prose_chapters_only(db) -> None:
    service = await _service(db)
    await service.save(KEY, 1, _prose("Geschrieben"))
    editor = MapEditor(db.session, 1, "Anna")
    await editor.add_activity(0, "Bestellen")
    async with db.session() as session:
        rows = {
            c.chapter_key: c
            for c in (await session.scalars(select(ChapterEntity))).all()
        }
    assert rows[KEY].needs_review
    assert rows[KEY].review_reason == chapters.REVIEW_AFTER_MAP
    assert not rows["loesung"].needs_review
    assert not rows["user_stories"].needs_review
    # Saving the chapter again clears the mark.
    await service.save(KEY, 2, _prose("Geprüft"))
    async with db.session() as session:
        chapter = await session.scalar(
            select(ChapterEntity).where(ChapterEntity.chapter_key == KEY)
        )
        assert chapter is not None
        assert not chapter.needs_review


async def test_mark_dependent_review_accepts_a_reason(db) -> None:
    service = await _service(db)
    await service.save(KEY, 1, _prose("Geschrieben"))
    async with db.session() as session:
        workspace = await open_workspace(session, 1, "Anna")
        await mark_dependent_review(session, workspace, "Anderer Grund")
    views = await service.open()
    assert views[0]["review_reason"] == "Anderer Grund"


async def test_saving_the_same_text_creates_no_revision(db) -> None:
    service = await _service(db)
    assert await service.save(KEY, 1, ProseContent()) == 1
    assert await service.save(KEY, 1, _prose("Text")) == 2
    assert await service.save(KEY, 2, _prose("Text")) == 2
    assert len(await service.history(KEY)) == 2
