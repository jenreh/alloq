"""Revoking a source: use is closed at once, content deleted, dependents flagged."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from alloq_offer.workshop.content.schema import Paragraph, ProseContent, Run
from alloq_offer.workshop.entities import (
    BlobEntity,
    ChapterEntity,
    FindingDecision,
    FindingEntity,
    SourceBlockEntity,
    SourceEntity,
    SourceKind,
    SourceStatus,
    StatementEntity,
    StatementStatus,
    StatementType,
)
from alloq_offer.workshop.repositories import source_repo
from alloq_offer.workshop.services import findings
from alloq_offer.workshop.services.chapters import ChapterService
from alloq_offer.workshop.services.source_revocation import (
    REVIEW_REASON,
    revoke_source,
)
from alloq_offer.workshop.services.sources import (
    SourceOriginal,
    load_blocks,
    load_original,
)
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.storage import BlobNotFoundError, DbBlobStore
from sqlalchemy import select

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
SOURCE_SHA = "b" * 64
# The seeded template layout is a blob too; the tests mean the source's blob.
SOURCE_BLOB = select(BlobEntity).where(BlobEntity.sha256 == SOURCE_SHA)


async def _source(db, *, blob: bool = True, replaces: int | None = None) -> int:  # noqa: ANN001
    async with db.session() as session:
        blob_id = None
        if blob:
            row = BlobEntity(sha256=SOURCE_SHA, size=3, mime="text/plain", data=b"abc")
            session.add(row)
            await session.flush()
            blob_id = row.id
        source = SourceEntity(
            offer_id=1,
            kind=SourceKind.TXT,
            title="Mail",
            filename="a.txt",
            sha256="a",
            status=SourceStatus.USABLE,
            blob_id=blob_id,
            replaces_id=replaces,
        )
        session.add(source)
        await session.flush()
        session.add(
            SourceBlockEntity(
                source_id=source.id, seq=1, anchor={}, kind="text", text="geheim"
            )
        )
        return source.id


async def _block_id(db, source_id: int) -> int:  # noqa: ANN001
    async with db.session() as session:
        found = await session.scalar(
            select(SourceBlockEntity.id).where(SourceBlockEntity.source_id == source_id)
        )
    assert found is not None
    return found


async def test_revoke_deletes_content_and_flags_dependents(db) -> None:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    service = ChapterService(db.session, 1, "Anna")
    await service.open()
    await service.save(
        "management_summary",
        1,
        ProseContent(blocks=[Paragraph(runs=[Run(text="Text")])]),
    )
    source_id = await _source(db)
    block_id = await _block_id(db, source_id)
    async with db.session() as session:
        session.add(
            StatementEntity(
                offer_id=1,
                type=StatementType.FACT,
                text="Belegt",
                status=StatementStatus.PROPOSED,
                source_refs=[block_id],
            )
        )

    assert await revoke_source(db.session, 1, source_id, now=NOW)

    async with db.session() as session:
        source = await session.get(SourceEntity, source_id)
        assert source is not None
        assert source.revoked_at is not None
        assert source.blob_id is None
        assert not source.included
        assert await session.scalar(select(SourceBlockEntity)) is None
        assert await session.scalar(SOURCE_BLOB) is None
        statement = await session.scalar(select(StatementEntity))
        assert statement is not None
        assert statement.needs_recheck
        chapter = await session.scalar(
            select(ChapterEntity).where(
                ChapterEntity.chapter_key == "management_summary"
            )
        )
        assert chapter is not None
        assert chapter.review_reason == REVIEW_REASON
        assert await source_repo.list_current(session, 1) == []

    await findings.run_checks(db.session, 1)
    async with db.session() as session:
        rows = (await session.scalars(select(FindingEntity))).all()
    assert any(
        r.rule == "source_revoked" and r.decision == FindingDecision.OPEN for r in rows
    )


async def test_revoke_twice_or_foreign_source_changes_nothing(db) -> None:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    source_id = await _source(db)
    assert not await revoke_source(db.session, 2, source_id, now=NOW)
    assert await revoke_source(db.session, 1, source_id, now=NOW)
    assert not await revoke_source(db.session, 1, source_id, now=NOW)
    assert not await revoke_source(db.session, 1, 999, now=NOW)


async def test_all_versions_of_a_file_are_revoked(db) -> None:  # noqa: ANN001
    older = await _source(db, blob=False)
    newer = await _source(db, blob=False, replaces=older)
    assert await revoke_source(db.session, 1, newer, now=NOW)
    async with db.session() as session:
        assert await source_repo.list_current(session, 1) == []
        rows = (await session.scalars(select(SourceEntity))).all()
    assert all(r.revoked_at is not None for r in rows)


async def test_shared_blob_stays_while_another_source_uses_it(db) -> None:  # noqa: ANN001
    first = await _source(db)
    async with db.session() as session:
        blob = await session.scalar(SOURCE_BLOB)
        assert blob is not None
        session.add(
            SourceEntity(
                offer_id=1,
                kind=SourceKind.TXT,
                title="Zweite",
                filename="b.txt",
                sha256="b",
                status=SourceStatus.USABLE,
                blob_id=blob.id,
            )
        )
    assert await revoke_source(db.session, 1, first, now=NOW)
    async with db.session() as session:
        assert await session.scalar(SOURCE_BLOB) is not None


async def test_viewer_lists_blocks_with_place_and_hides_revoked_sources(db) -> None:  # noqa: ANN001
    source_id = await _source(db)
    title, blocks = await load_blocks(db.session, 1, source_id)
    assert title == "Mail"
    assert blocks == [{"label": "", "speaker": "", "text": "geheim", "gap": False}]
    assert await load_blocks(db.session, 2, source_id) == ("", [])
    await revoke_source(db.session, 1, source_id, now=NOW)
    assert await load_blocks(db.session, 1, source_id) == ("", [])


async def test_original_of_a_document_source_is_loaded_until_revoked(db) -> None:  # noqa: ANN001
    store = DbBlobStore(1_000_000, db.session)
    source_id = await _source(db)
    async with db.session() as session:
        source = await session.get(SourceEntity, source_id)
        assert source is not None
        source.kind = SourceKind.PDF
        source.filename = "angebot.pdf"
    original = await load_original(db.session, store, 1, source_id)
    assert original == SourceOriginal(SourceKind.PDF, "angebot.pdf", b"abc")
    assert await load_original(db.session, store, 2, source_id) is None
    await revoke_source(db.session, 1, source_id, now=NOW)
    assert await load_original(db.session, store, 1, source_id) is None


async def test_original_is_none_for_text_sources_and_missing_blobs(db) -> None:  # noqa: ANN001
    store = DbBlobStore(1_000_000, db.session)
    assert await load_original(db.session, store, 1, await _source(db)) is None
    missing = AsyncMock(get=AsyncMock(side_effect=BlobNotFoundError(1)))
    source_id = await _source(db, blob=False)
    async with db.session() as session:
        source = await session.get(SourceEntity, source_id)
        assert source is not None
        source.kind = SourceKind.DOCX
    assert await load_original(db.session, missing, 1, source_id) is None
    async with db.session() as session:
        source = await session.get(SourceEntity, source_id)
        assert source is not None
        source.blob_id = 1
    assert await load_original(db.session, missing, 1, source_id) is None
