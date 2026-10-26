"""Word exports: validate the output kind, fix the document state, queue the job.

A draft is always possible. A final version needs no open blocker, confirmed
commercial values when the offer requires a price, and the person's confirmation
of the whole state (spec 11.3). Reasons are collected, so users see all of them.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import ExportEntity, ExportKind, ExportStatus
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services import findings
from alloq_offer.workshop.services.export_snapshot import (
    build_snapshot,
)
from alloq_offer.workshop.services.templates import template_exists
from alloq_offer.workshop.services.workspace import NO_WORKSPACE
from alloq_offer.workshop.storage import BlobStore, sha256_hex

logger = logging.getLogger(__name__)

EXPORT_JOB = "export_docx"
EXPORTER_VERSION = "1"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
UNSAVED = (
    "Es gibt ungespeicherte Änderungen. Bitte warten Sie, bis alles gespeichert ist."
)
NOT_CONFIRMED = "Bitte bestätigen Sie den gesamten Stand für die finale Fassung."
UNREVIEWED_PREFIX = "Pflichtkapitel noch zu prüfen: "
BLOCKER_PREFIX = "Offener Blocker: "
NOT_READY = "Dieser Export ist nicht verfügbar."
CHECKSUM_MISMATCH = "Die gespeicherte Datei stimmt nicht mit ihrer Prüfsumme überein."
TEMPLATE_MISSING = "Die Vorlage dieses Angebots ist nicht mehr verfügbar."


class ExportBlockedError(ValueError):
    """The export cannot start; ``reasons`` are German sentences for users."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__(" ".join(reasons))
        self.reasons = reasons


def filename_for(offer: OfferEntity, kind: ExportKind, number: int) -> str:
    safe = "".join(c if c.isalnum() else "-" for c in offer.title).strip("-")
    label = "Entwurf" if kind == ExportKind.DRAFT else "Final"
    return f"Angebot-{safe or offer.id}-{label}-{number}.docx"


async def request_export(
    session_factory: SessionFactory,
    offer_id: int,
    kind: ExportKind,
    *,
    user: str,
    confirmed: bool,
    unsaved: bool,
    now: datetime,
    max_attempts: int,
) -> ExportEntity:
    """Fix the current state in a snapshot and queue the Word job."""
    if unsaved:
        raise ExportBlockedError([UNSAVED])
    # Checks run on the state that is exported, so open points are current.
    try:
        await findings.run_checks(session_factory, offer_id)
    except findings.FindingError as exc:
        raise ExportBlockedError([str(exc)]) from exc
    async with session_factory() as session:
        data = await findings.load_check_input(session, offer_id)
        offer = await session.get(OfferEntity, offer_id)
        if data is None or offer is None:
            raise ExportBlockedError([NO_WORKSPACE])
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        assert workspace is not None  # noqa: S101  # load_check_input found it
        if not await template_exists(
            session, workspace.template_key, workspace.template_version
        ):
            raise ExportBlockedError([TEMPLATE_MISSING])
        if kind == ExportKind.FINAL:
            reasons = [
                BLOCKER_PREFIX + row.message
                for row in await findings.open_blockers(session, offer_id)
            ]
            reasons.extend(
                f"{UNREVIEWED_PREFIX}{c.title}"
                for c in data.chapters
                if c.required and c.needs_review
            )
            if not confirmed:
                reasons.append(NOT_CONFIRMED)
            if reasons:
                raise ExportBlockedError(reasons)
        snapshot = await build_snapshot(session, workspace, offer, user=user, now=now)
        export = ExportEntity(
            offer_id=offer_id,
            snapshot_id=snapshot.id,
            kind=kind,
            status=ExportStatus.WORKING,
            template_version=snapshot.template_version,
            exporter_version=EXPORTER_VERSION,
            filename=filename_for(offer, kind, snapshot.number),
            created_by=user,
        )
        session.add(export)
        await session.flush()
        await queue.enqueue(
            session,
            kind=EXPORT_JOB,
            offer_id=offer_id,
            idempotency_key=f"{EXPORT_JOB}:{export.id}",
            payload={"export_id": export.id},
            now=now,
            max_attempts=max_attempts,
        )
        logger.info("Export %s (%s) of offer %s queued", export.id, kind, offer_id)
        return export


def export_row(row: ExportEntity) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "filename": row.filename,
        "error": row.error,
        "created_by": row.created_by,
        "created": row.created.strftime("%d.%m.%Y %H:%M"),
        "template_version": row.template_version,
        "ready": row.status == ExportStatus.READY,
        "failed": row.status == ExportStatus.FAILED,
    }


async def list_exports(
    session_factory: SessionFactory, offer_id: int
) -> list[dict[str, Any]]:
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(ExportEntity)
                .where(ExportEntity.offer_id == offer_id)
                .order_by(ExportEntity.id.desc())
            )
        ).all()
    return [export_row(r) for r in rows]


async def load_download(
    session_factory: SessionFactory, store: BlobStore, offer_id: int, export_id: int
) -> tuple[str, bytes]:
    """The stored bytes of a finished export of this offer, exactly as saved."""
    async with session_factory() as session:
        row = await session.get(ExportEntity, export_id)
        if (
            row is None
            or row.offer_id != offer_id
            or row.status != ExportStatus.READY
            or row.blob_id is None
        ):
            raise ExportBlockedError([NOT_READY])
        blob_id, digest, filename = row.blob_id, row.sha256, row.filename
    data = await store.get(blob_id)
    if sha256_hex(data) != digest:
        raise ExportBlockedError([CHECKSUM_MISMATCH])
    return filename, data
