"""Job handler ``extract_source``: read a stored source into citable blocks."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    SourceBlockEntity,
    SourceEntity,
    SourceKind,
    SourceStatus,
)
from alloq_offer.workshop.extraction import (
    ExtractionError,
    ExtractionResult,
    Transcriber,
    TranscriptionUnavailableError,
    parse_docx,
    parse_eml,
    parse_html,
    parse_pdf,
    parse_pptx,
    parse_text,
    to_result,
)
from alloq_offer.workshop.extraction.audio import AzureTranscriber
from alloq_offer.workshop.extraction.models import anchor_label
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    TransientJobError,
    register_handler,
)
from alloq_offer.workshop.repositories import source_block_repo, source_repo
from alloq_offer.workshop.services.draft_pipeline import draft_when_usable
from alloq_offer.workshop.services.sources import (
    EXTRACT_JOB,
    READABLE_STATUSES,
    SourceRejectedError,
    add_source,
    classify_filename,
)
from alloq_offer.workshop.storage import BlobStore, DbBlobStore
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

TRANSCRIPTION_FAILED = (
    "Die Transkription ist fehlgeschlagen. Bitte versuchen Sie es erneut."
)
PROCESSING_FAILED = (
    "Die Quelle konnte nicht verarbeitet werden. Bitte versuchen Sie es erneut."
)
NO_TEXT = "Es wurde kein Text gefunden. Bitte laden Sie den Inhalt als Text hoch."
RETRYABLE_STATUS = 429
SERVER_ERROR = 500

_PARSERS: dict[SourceKind, Callable[[bytes], ExtractionResult]] = {
    SourceKind.TEXT: parse_text,
    SourceKind.TXT: parse_text,
    SourceKind.HTML: parse_html,
    SourceKind.EML: parse_eml,
    SourceKind.DOCX: parse_docx,
    SourceKind.PDF: parse_pdf,
    SourceKind.PPTX: parse_pptx,
}


def _is_transient(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        return code == RETRYABLE_STATUS or code >= SERVER_ERROR
    return isinstance(error, httpx.TransportError)


class SourceExtractor:
    """Runs one extraction; parsing happens outside any database transaction."""

    def __init__(
        self,
        store: BlobStore,
        transcriber: Transcriber,
        session_factory: SessionFactory,
        max_attempts: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._transcriber = transcriber
        self._session_factory = session_factory
        self._max_attempts = max_attempts
        self._clock = clock

    async def run(self, ctx: JobContext) -> dict:
        source_id = int(ctx.payload["source_id"])
        source = await self._begin(ctx.offer_id, source_id)
        if source is None:
            return {"status": "skipped"}
        try:
            return await self._extract(ctx, source)
        except TransientJobError:
            raise
        except Exception:
            # Unknown failures must not leave the source in "in Verarbeitung".
            logger.exception("Extracting source %s failed", source_id)
            return await self._failed(
                ctx, source_id, SourceStatus.FAILED, PROCESSING_FAILED
            )

    async def _extract(self, ctx: JobContext, source: SourceEntity) -> dict:
        source_id = source.id
        if source.blob_id is None:
            return await self._failed(ctx, source_id, SourceStatus.FAILED, NO_TEXT)
        data = await self._store.get(source.blob_id)
        try:
            result = await self._parse(
                SourceKind(source.kind), data, source.filename, source.mime
            )
        except ExtractionError as exc:
            return await self._failed(ctx, source_id, SourceStatus.FAILED, str(exc))
        except TranscriptionUnavailableError as exc:
            return await self._failed(ctx, source_id, SourceStatus.MANUAL, str(exc))
        except httpx.HTTPError as exc:
            if _is_transient(exc) and ctx.attempt < ctx.max_attempts:
                raise TransientJobError(TRANSCRIPTION_FAILED) from exc
            logger.warning("Transcription of source %s failed: %s", source_id, exc)
            return await self._failed(
                ctx, source_id, SourceStatus.FAILED, TRANSCRIPTION_FAILED
            )
        del data
        notes = await self._add_attachments(ctx, result)
        status, detail = await self._store_result(
            ctx.offer_id, source_id, result, notes
        )
        if status in READABLE_STATUSES:
            await self._auto_draft(ctx.offer_id)
        return {"status": status, "detail": detail}

    async def _auto_draft(self, offer_id: int) -> None:
        """A failed follow-up must not mark the source that was read as failed."""
        try:
            await draft_when_usable(
                self._session_factory,
                offer_id,
                now=self._clock(),
                max_attempts=self._max_attempts,
            )
        except Exception:
            logger.exception("Automatic draft of offer %s failed", offer_id)

    async def _begin(self, offer_id: int, source_id: int) -> SourceEntity | None:
        async with self._session_factory() as session:
            source = await source_repo.find_in_offer(session, offer_id, source_id)
            if source is None or source.revoked_at is not None:
                return None
            source.status = SourceStatus.PROCESSING
            source.status_detail = ""
            # Expunging drops unflushed changes, so write the status first.
            await session.flush()
            session.expunge(source)
            return source

    async def _parse(
        self, kind: SourceKind, data: bytes, filename: str, mime: str
    ) -> ExtractionResult:
        if kind is SourceKind.AUDIO:
            segments = await self._transcriber.transcribe(data, filename, mime)
            return to_result(segments)
        return await asyncio.to_thread(_PARSERS[kind], data)

    async def _failed(
        self, ctx: JobContext, source_id: int, status: SourceStatus, detail: str
    ) -> dict:
        await self._finish_failed(ctx.offer_id, source_id, status, detail)
        return {"status": status, "detail": detail}

    async def _finish_failed(
        self, offer_id: int, source_id: int, status: SourceStatus, detail: str
    ) -> None:
        async with self._session_factory() as session:
            source = await source_repo.find_in_offer(session, offer_id, source_id)
            if source is not None:
                source.status = status
                source.status_detail = detail

    async def _store_result(
        self,
        offer_id: int,
        source_id: int,
        result: ExtractionResult,
        notes: str,
    ) -> tuple[SourceStatus, str]:
        status, detail = _summarize(result)
        detail = "; ".join(filter(None, [detail, notes]))
        async with self._session_factory() as session:
            source = await source_repo.find_in_offer(session, offer_id, source_id)
            if source is None or source.revoked_at is not None:
                return status, detail
            await source_block_repo.replace(
                session,
                source_id,
                [
                    SourceBlockEntity(
                        source_id=source_id,
                        seq=seq,
                        kind=block.kind,
                        anchor=block.anchor,
                        speaker=block.speaker,
                        text=block.text,
                    )
                    for seq, block in enumerate(result.blocks, 1)
                ],
            )
            source.status = status
            source.status_detail = detail
        return status, detail

    async def _add_attachments(self, ctx: JobContext, result: ExtractionResult) -> str:
        notes: list[str] = []
        for attachment in result.attachments:
            try:
                kind = classify_filename(attachment.filename)
            except SourceRejectedError as exc:
                notes.append(str(exc))
                continue
            await add_source(
                self._store,
                offer_id=ctx.offer_id,
                kind=kind,
                title=attachment.filename,
                filename=attachment.filename,
                mime=attachment.mime,
                data=attachment.data,
                user="",
                now=self._clock(),
                max_attempts=self._max_attempts,
                replace_versions=False,
                session_factory=self._session_factory,
            )
        return "; ".join(notes)


def _summarize(result: ExtractionResult) -> tuple[SourceStatus, str]:
    gaps = [
        f"{label}: {block.text}"
        if (label := anchor_label(block.anchor))
        else block.text
        for block in result.gaps
    ]
    detail = "; ".join(gaps)
    if not result.text_blocks:
        return SourceStatus.MANUAL, detail or NO_TEXT
    if gaps:
        return SourceStatus.PARTIAL, detail
    return SourceStatus.USABLE, ""


async def mark_source_failed(ctx: JobContext) -> None:
    """A source whose job failed for good must not stay in a working status."""
    async with get_asyncdb_session() as session:
        source = await source_repo.find_in_offer(
            session, ctx.offer_id, int(ctx.payload["source_id"])
        )
        if source is not None and source.status in (
            SourceStatus.UPLOADED,
            SourceStatus.PROCESSING,
        ):
            source.status = SourceStatus.FAILED
            source.status_detail = PROCESSING_FAILED


@register_handler(EXTRACT_JOB, on_exhausted=mark_source_failed)
async def extract_source(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    extractor = SourceExtractor(
        DbBlobStore(config.max_blob_bytes),
        AzureTranscriber(config.azure_openai),
        get_asyncdb_session,
        config.max_attempts,
    )
    return await extractor.run(ctx)
