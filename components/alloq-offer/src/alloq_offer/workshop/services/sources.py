"""Add, replace and switch customer sources of an offer."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import SourceEntity, SourceKind, SourceStatus
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.repositories import source_repo
from alloq_offer.workshop.storage import BlobStore, sha256_hex
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

EXTRACT_JOB = "extract_source"
DEFAULT_TEXT_TITLE = "Eingefügter Text"
TEXT_EXTENSIONS = (
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
    ".rst",
    ".ini",
    ".srt",
    ".vtt",
)
EXTENSION_KINDS: dict[str, SourceKind] = {
    **dict.fromkeys(TEXT_EXTENSIONS, SourceKind.TXT),
    ".eml": SourceKind.EML,
    ".html": SourceKind.HTML,
    ".htm": SourceKind.HTML,
    ".docx": SourceKind.DOCX,
    ".pdf": SourceKind.PDF,
    ".pptx": SourceKind.PPTX,
    ".wav": SourceKind.AUDIO,
    ".mp3": SourceKind.AUDIO,
    ".m4a": SourceKind.AUDIO,
}
MACRO_EXTENSIONS = frozenset({".docm", ".dotm", ".pptm", ".potm", ".xlsm"})
ACCEPTED_EXTENSIONS = tuple(EXTENSION_KINDS)


class SourceRejectedError(ValueError):
    """The file is not accepted as a source; the message is shown to users."""


def classify_filename(filename: str) -> SourceKind:
    extension = PurePath(filename).suffix.lower()
    if extension in MACRO_EXTENSIONS:
        raise SourceRejectedError(
            f"Dateien mit Makros werden nicht angenommen: {filename}"
        )
    try:
        return EXTENSION_KINDS[extension]
    except KeyError:
        raise SourceRejectedError(
            f"Dieser Dateityp wird nicht unterstützt: {filename}"
        ) from None


@dataclass(frozen=True)
class AddedSource:
    source: SourceEntity
    created: bool


async def add_source(
    store: BlobStore,
    *,
    offer_id: int,
    kind: SourceKind,
    title: str,
    filename: str,
    mime: str,
    data: bytes,
    user: str,
    now: datetime,
    max_attempts: int,
    replace_versions: bool = True,
    session_factory: SessionFactory = get_asyncdb_session,
) -> AddedSource:
    """Store ``data`` as a source and queue its extraction.

    The same content twice adds nothing. A file with a known name becomes the next
    version of that source and the old version is switched off.
    """
    digest = sha256_hex(data)
    async with session_factory() as session:
        existing = await source_repo.find_by_sha(session, offer_id, digest)
        if existing is not None:
            return AddedSource(existing, created=False)
    blob_id = await store.put(data, mime)
    async with session_factory() as session:
        existing = await source_repo.find_by_sha(session, offer_id, digest)
        if existing is not None:
            return AddedSource(existing, created=False)
        previous = (
            await source_repo.find_latest_by_filename(session, offer_id, filename)
            if filename and replace_versions
            else None
        )
        source = SourceEntity(
            offer_id=offer_id,
            kind=kind,
            title=title,
            filename=filename,
            mime=mime,
            blob_id=blob_id,
            sha256=digest,
            version=previous.version + 1 if previous else 1,
            replaces_id=previous.id if previous else None,
            created_by=user,
        )
        session.add(source)
        if previous is not None:
            previous.included = False
        await session.flush()
        await queue.enqueue(
            session,
            kind=EXTRACT_JOB,
            offer_id=offer_id,
            idempotency_key=f"{EXTRACT_JOB}:{source.id}",
            payload={"source_id": source.id},
            now=now,
            max_attempts=max_attempts,
        )
        logger.info("Added %s source %s to offer %s", kind, source.id, offer_id)
        return AddedSource(source, created=True)


async def set_included(
    session_factory: SessionFactory, offer_id: int, source_id: int, included: bool
) -> bool:
    """Switch a source on or off for drafts; False when it is not in this offer."""
    async with session_factory() as session:
        source = await source_repo.find_in_offer(session, offer_id, source_id)
        if source is None or source.revoked_at is not None:
            return False
        source.included = included
        return True


async def retry_source(
    session_factory: SessionFactory,
    offer_id: int,
    source_id: int,
    *,
    now: datetime,
    max_attempts: int,
) -> bool:
    """Queue the extraction of a failed or manual source again."""
    async with session_factory() as session:
        source = await source_repo.find_in_offer(session, offer_id, source_id)
        if (
            source is None
            or source.revoked_at is not None
            or source.status not in (SourceStatus.FAILED, SourceStatus.MANUAL)
        ):
            return False
        source.status = SourceStatus.UPLOADED
        source.status_detail = ""
        await queue.enqueue(
            session,
            kind=EXTRACT_JOB,
            offer_id=offer_id,
            idempotency_key=f"{EXTRACT_JOB}:{source.id}:{int(now.timestamp() * 1000)}",
            payload={"source_id": source.id},
            now=now,
            max_attempts=max_attempts,
        )
        return True
