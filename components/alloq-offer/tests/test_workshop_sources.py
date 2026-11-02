"""Tests of the source service and the ``extract_source`` job."""

import io
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from email.message import EmailMessage
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import JobEntity, SourceKind, SourceStatus
from alloq_offer.workshop.extraction import parse_eml
from alloq_offer.workshop.extraction.audio import (
    NO_TRANSCRIBER,
    TranscriptionUnavailableError,
    TranscriptSegment,
)
from alloq_offer.workshop.jobs import extract_source as module
from alloq_offer.workshop.jobs.extract_source import (
    NO_TEXT,
    TRANSCRIPTION_FAILED,
    SourceExtractor,
)
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    TransientJobError,
    get_handler,
)
from alloq_offer.workshop.repositories import (
    job_repo,
    source_block_repo,
    source_repo,
)
from alloq_offer.workshop.services.sources import (
    EXTRACT_JOB,
    SourceRejectedError,
    add_source,
    classify_filename,
    retry_source,
    set_included,
)
from alloq_offer.workshop.storage import DbBlobStore
from docx import Document
from pypdf import PdfWriter
from sqlalchemy import select

NOW = datetime(2026, 10, 24, tzinfo=UTC)


class FakeTranscriber:
    def __init__(self, segments=None, error: Exception | None = None) -> None:
        self._segments = segments or []
        self._error = error

    async def transcribe(
        self,
        data: bytes,  # noqa: ARG002
        filename: str,  # noqa: ARG002
        mime: str,  # noqa: ARG002
    ) -> list[TranscriptSegment]:
        if self._error:
            raise self._error
        return self._segments


async def _add(db, store, data=b"Hallo", filename="a.txt", kind=SourceKind.TXT):
    return await add_source(
        store,
        offer_id=1,
        kind=kind,
        title=filename or "Text",
        filename=filename,
        mime="text/plain",
        data=data,
        user="Anna",
        now=NOW,
        max_attempts=3,
        session_factory=db.session,
    )


@pytest.fixture
def store(db) -> DbBlobStore:
    return DbBlobStore(1_000_000, db.session)


def _extractor(db, store, transcriber=None) -> SourceExtractor:
    return SourceExtractor(
        store, transcriber or FakeTranscriber(), db.session, 3, lambda: NOW
    )


def _ctx(source_id: int, attempt: int = 1) -> JobContext:
    return JobContext(
        job_id=1,
        offer_id=1,
        kind=EXTRACT_JOB,
        payload={"source_id": source_id},
        attempt=attempt,
        max_attempts=3,
    )


def test_classify_filename_maps_extensions_and_rejects_macros() -> None:
    assert classify_filename("Mail.EML") is SourceKind.EML
    assert classify_filename("a.m4a") is SourceKind.AUDIO
    for name in ("a.md", "b.CSV", "c.json", "d.yaml", "e.log"):
        assert classify_filename(name) is SourceKind.TXT
    assert classify_filename("page.html") is SourceKind.HTML
    with pytest.raises(SourceRejectedError, match="Makros"):
        classify_filename("x.docm")
    with pytest.raises(SourceRejectedError, match="nicht unterstützt"):
        classify_filename("x.exe")


async def test_add_source_stores_blob_and_queues_extraction(db, store) -> None:
    added = await _add(db, store)
    assert added.created
    async with db.session() as session:
        source = await source_repo.find_in_offer(session, 1, added.source.id)
        job = await job_repo.find_latest(session, 1, EXTRACT_JOB)
        assert source.status == SourceStatus.UPLOADED
        assert (source.version, source.replaces_id, source.included) == (1, None, True)
        assert job.payload == {"source_id": source.id}
        assert await store.get(source.blob_id) == b"Hallo"


async def test_identical_content_adds_nothing(db, store) -> None:
    first = await _add(db, store, filename="a.txt")
    second = await _add(db, store, filename="other.txt")
    assert not second.created
    assert second.source.id == first.source.id
    async with db.session() as session:
        jobs = (await session.scalars(select(JobEntity))).all()
        assert len(jobs) == 1


async def test_same_filename_with_new_content_becomes_next_version(db, store) -> None:
    first = await _add(db, store, b"v1")
    second = await _add(db, store, b"v2")
    assert second.created
    async with db.session() as session:
        old = await source_repo.find_in_offer(session, 1, first.source.id)
        new = await source_repo.find_in_offer(session, 1, second.source.id)
        assert (new.version, new.replaces_id) == (2, old.id)
        assert old.included is False
        current = await source_repo.list_current(session, 1)
        assert [s.id for s in current] == [new.id]


async def test_pasted_text_has_no_versioning(db, store) -> None:
    await _add(db, store, b"eins", filename="", kind=SourceKind.TEXT)
    second = await _add(db, store, b"zwei", filename="", kind=SourceKind.TEXT)
    assert second.source.version == 1


async def test_set_included_and_retry_are_scoped_to_the_offer(db, store) -> None:
    added = await _add(db, store)
    sid = added.source.id
    assert await set_included(db.session, 1, sid, False)
    assert not await set_included(db.session, 2, sid, True)
    assert not await retry_source(db.session, 1, sid, now=NOW, max_attempts=3)
    async with db.session() as session:
        (await source_repo.find_in_offer(session, 1, sid)).status = SourceStatus.FAILED
    assert await retry_source(db.session, 1, sid, now=NOW, max_attempts=3)
    assert not await retry_source(db.session, 2, sid, now=NOW, max_attempts=3)
    assert not await retry_source(db.session, 1, 999, now=NOW, max_attempts=3)
    async with db.session() as session:
        jobs = (await session.scalars(select(JobEntity))).all()
        assert len(jobs) == 2
        assert (await source_repo.find_in_offer(session, 1, sid)).included is False


async def test_extractor_stores_blocks_and_marks_source_usable(db, store) -> None:
    added = await _add(db, store, b"Erster.\n\nZweiter.")
    result = await _extractor(db, store).run(_ctx(added.source.id))
    assert result["status"] == SourceStatus.USABLE
    async with db.session() as session:
        source = await source_repo.find_in_offer(session, 1, added.source.id)
        blocks = await source_block_repo.list_for_source(session, source.id)
        assert source.status == SourceStatus.USABLE
        assert [(b.seq, b.text) for b in blocks] == [(1, "Erster."), (2, "Zweiter.")]
        assert blocks[0].to_dict()["anchor"] == {"paragraph": 1}


async def test_extracting_again_replaces_the_blocks(db, store) -> None:
    added = await _add(db, store, b"Eins")
    extractor = _extractor(db, store)
    await extractor.run(_ctx(added.source.id))
    await extractor.run(_ctx(added.source.id))
    async with db.session() as session:
        assert (
            len(await source_block_repo.list_for_source(session, added.source.id)) == 1
        )


async def test_empty_source_needs_manual_work(db, store) -> None:
    added = await _add(db, store, b"   ")
    result = await _extractor(db, store).run(_ctx(added.source.id))
    assert result == {"status": SourceStatus.MANUAL, "detail": NO_TEXT}


async def test_corrupt_file_fails_with_a_readable_reason(db, store) -> None:
    added = await _add(db, store, b"nope", "x.docx", SourceKind.DOCX)
    result = await _extractor(db, store).run(_ctx(added.source.id))
    assert result["status"] == SourceStatus.FAILED
    async with db.session() as session:
        source = await source_repo.find_in_offer(session, 1, added.source.id)
        assert "Word-Dokument" in source.status_detail


async def test_gaps_make_a_source_partially_usable(db, store) -> None:
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.write(buffer)
    added = await _add(db, store, buffer.getvalue(), "scan.pdf", SourceKind.PDF)
    result = await _extractor(db, store).run(_ctx(added.source.id))
    assert result["status"] == SourceStatus.MANUAL
    assert "Seite 1: OCR nötig" in result["detail"]


async def test_audio_is_transcribed_with_speaker_labels(db, store) -> None:
    added = await _add(db, store, b"RIFF", "call.wav", SourceKind.AUDIO)
    transcriber = FakeTranscriber([TranscriptSegment(0, 900, "Guten Tag", "A")])
    await _extractor(db, store, transcriber).run(_ctx(added.source.id))
    async with db.session() as session:
        (block,) = await source_block_repo.list_for_source(session, added.source.id)
        assert (block.speaker, block.anchor) == (
            "Sprecher 1",
            {"start_ms": 0, "end_ms": 900},
        )


async def test_audio_without_transcriber_needs_manual_work(db, store) -> None:
    added = await _add(db, store, b"RIFF", "call.wav", SourceKind.AUDIO)
    error = TranscriptionUnavailableError(NO_TRANSCRIBER)
    result = await _extractor(db, store, FakeTranscriber(error=error)).run(
        _ctx(added.source.id)
    )
    assert result == {"status": SourceStatus.MANUAL, "detail": NO_TRANSCRIBER}


def _timeout() -> httpx.HTTPError:
    return httpx.ReadTimeout("slow")


async def test_transient_transcription_error_is_retried_until_the_last_attempt(
    db, store
) -> None:
    added = await _add(db, store, b"RIFF", "call.wav", SourceKind.AUDIO)
    extractor = _extractor(db, store, FakeTranscriber(error=_timeout()))
    with pytest.raises(TransientJobError):
        await extractor.run(_ctx(added.source.id, attempt=1))
    result = await extractor.run(_ctx(added.source.id, attempt=3))
    assert result == {"status": SourceStatus.FAILED, "detail": TRANSCRIPTION_FAILED}


async def test_permanent_transcription_error_fails_at_once(db, store) -> None:
    added = await _add(db, store, b"RIFF", "call.wav", SourceKind.AUDIO)
    response = httpx.Response(401, request=httpx.Request("POST", "https://x"))
    error = httpx.HTTPStatusError("denied", request=response.request, response=response)
    result = await _extractor(db, store, FakeTranscriber(error=error)).run(
        _ctx(added.source.id, attempt=1)
    )
    assert result["status"] == SourceStatus.FAILED


async def test_unknown_or_revoked_source_is_skipped(db, store) -> None:
    assert await _extractor(db, store).run(_ctx(999)) == {"status": "skipped"}
    added = await _add(db, store)
    async with db.session() as session:
        (await source_repo.find_in_offer(session, 1, added.source.id)).revoked_at = NOW
    assert await _extractor(db, store).run(_ctx(added.source.id)) == {
        "status": "skipped"
    }


async def test_eml_attachments_become_sources_and_unsupported_ones_are_noted(
    db, store
) -> None:
    docx = io.BytesIO()
    document = Document()
    document.add_paragraph("Konzept")
    document.save(docx)
    message = EmailMessage()
    message["Subject"] = "Mit Anhang"
    message.set_content("Siehe Anhang.")
    message.add_attachment(
        docx.getvalue(),
        maintype="application",
        subtype="octet-stream",
        filename="k.docx",
    )
    message.add_attachment(
        b"MZ", maintype="application", subtype="octet-stream", filename="tool.exe"
    )
    added = await _add(db, store, message.as_bytes(), "mail.eml", SourceKind.EML)

    await _extractor(db, store).run(_ctx(added.source.id))

    async with db.session() as session:
        sources = await source_repo.list_current(session, 1)
        assert {s.filename for s in sources} == {"mail.eml", "k.docx"}
        mail = await source_repo.find_in_offer(session, 1, added.source.id)
        assert "tool.exe" in mail.status_detail


async def test_registered_handler_builds_the_extractor_from_config() -> None:
    registry = MagicMock(get=MagicMock(return_value=WorkshopConfig()))
    extractor = MagicMock(run=AsyncMock(return_value={"status": "x"}))
    with (
        patch.object(module, "service_registry", return_value=registry),
        patch.object(module, "SourceExtractor", return_value=extractor) as build,
    ):
        result = await get_handler(EXTRACT_JOB)(_ctx(1))
    assert result == {"status": "x"}
    assert build.call_args.args[3] == WorkshopConfig().max_attempts


async def test_unexpected_failure_does_not_leave_the_source_processing(
    db, store
) -> None:
    added = await _add(db, store)
    extractor = _extractor(db, store)
    with patch.object(extractor, "_parse", AsyncMock(side_effect=RuntimeError("boom"))):
        result = await extractor.run(_ctx(added.source.id))
    assert result["status"] == SourceStatus.FAILED
    async with db.session() as session:
        source = await source_repo.find_in_offer(session, 1, added.source.id)
        assert source.status == SourceStatus.FAILED


async def test_attachments_never_replace_a_user_upload_of_the_same_name(
    db, store
) -> None:
    mine = await _add(db, store, b"mine", "k.docx", SourceKind.DOCX)
    message = EmailMessage()
    message.set_content("x")
    message.add_attachment(
        b"other", maintype="application", subtype="octet-stream", filename="k.docx"
    )
    mail = await _add(db, store, message.as_bytes(), "m.eml", SourceKind.EML)
    await _extractor(db, store)._add_attachments(  # noqa: SLF001
        _ctx(mail.source.id), parse_eml(message.as_bytes())
    )
    async with db.session() as session:
        assert (await source_repo.find_in_offer(session, 1, mine.source.id)).included


async def test_failed_job_marks_a_working_source_failed(db, store) -> None:
    added = await _add(db, store)
    done = await _add(db, store, b"fertig", "b.txt")
    async with db.session() as session:
        (
            await source_repo.find_in_offer(session, 1, added.source.id)
        ).status = SourceStatus.PROCESSING
        (
            await source_repo.find_in_offer(session, 1, done.source.id)
        ).status = SourceStatus.USABLE

    @asynccontextmanager
    async def _session():  # noqa: ANN202
        async with db.session() as session:
            yield session

    with patch.object(module, "get_asyncdb_session", _session):
        await module.mark_source_failed(_ctx(added.source.id))
        await module.mark_source_failed(_ctx(done.source.id))
        await module.mark_source_failed(_ctx(999))

    async with db.session() as session:
        first = await source_repo.find_in_offer(session, 1, added.source.id)
        second = await source_repo.find_in_offer(session, 1, done.source.id)
        assert first.status == SourceStatus.FAILED
        assert first.status_detail == module.PROCESSING_FAILED
        assert second.status == SourceStatus.USABLE
