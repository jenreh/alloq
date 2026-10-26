"""Job ``export_docx``: render a snapshot into the bound Word template.

The file is rendered outside any transaction, checked structurally and stored
with its manifest. A failed export never looks successful (spec 13.3); the saved
offer stays untouched, and a new export is a fresh request.
"""

import asyncio
import dataclasses
import logging
from typing import Any

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.schema import parse_content
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    DocState,
    ExportEntity,
    ExportKind,
    ExportStatus,
    SnapshotEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.export.docx_renderer import render_document
from alloq_offer.workshop.export.models import (
    ChapterInput,
    RenderContext,
    RenderError,
    ResolvedStory,
    ResolvedValue,
)
from alloq_offer.workshop.export.template_package import TemplateError
from alloq_offer.workshop.export.verify import verify_document
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    register_handler,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.exports import DOCX_MIME, EXPORT_JOB
from alloq_offer.workshop.services.templates import load_template
from alloq_offer.workshop.storage import BlobStore, DbBlobStore, sha256_hex
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

FAILED = "Der Export ist fehlgeschlagen. Bitte versuchen Sie es erneut."
MISSING = "Der Export oder sein Dokumentstand ist nicht mehr vorhanden."


def _story(data: dict[str, Any]) -> ResolvedStory:
    """A stored story; exports made before the scope was removed still carry it."""
    names = {f.name for f in dataclasses.fields(ResolvedStory)}
    return ResolvedStory(**{k: v for k, v in data.items() if k in names})


def render_inputs(snapshot: SnapshotEntity, kind: str) -> RenderContext:
    data = snapshot.content
    return RenderContext(
        cover=dict(data["cover"]),
        stories=[_story(story) for story in data["stories"]],
        values={
            name: ResolvedValue(value["text"], value["confirmed"])
            for name, value in data["values"].items()
        },
        draft=kind == ExportKind.DRAFT,
        open_points=list(data["open_points"]),
    )


def chapter_inputs(snapshot: SnapshotEntity) -> list[ChapterInput]:
    return [
        ChapterInput(c["key"], c["title"], c["level"], parse_content(c["content"]))
        for c in snapshot.content["chapters"]
    ]


def _manifest(
    export: ExportEntity, snapshot: SnapshotEntity, digest: str, size: int
) -> dict:
    return {
        "snapshot": snapshot.number,
        "map_revision": snapshot.map_revision,
        "template": f"{snapshot.template_key}@{snapshot.template_version}",
        "exporter_version": export.exporter_version,
        "kind": export.kind,
        "chapters": {c["key"]: c["revision"] for c in snapshot.content["chapters"]},
        "sha256": digest,
        "size": size,
    }


async def _fail(session_factory: SessionFactory, export_id: int, message: str) -> None:
    async with session_factory() as session:
        export = await session.get(ExportEntity, export_id)
        if export is not None and export.status != ExportStatus.READY:
            export.status = ExportStatus.FAILED
            export.error = message


class ExportDocx:
    def __init__(self, store: BlobStore, session_factory: SessionFactory) -> None:
        self._store = store
        self._session_factory = session_factory

    async def run(self, ctx: JobContext) -> dict:
        export_id = int(ctx.payload["export_id"])
        async with self._session_factory() as session:
            export = await session.get(ExportEntity, export_id)
            snapshot = (
                await session.get(SnapshotEntity, export.snapshot_id)
                if export is not None
                else None
            )
            if export is None or snapshot is None:
                raise PermanentJobError(MISSING)
            try:
                package = await load_template(
                    session, snapshot.template_key, snapshot.template_version
                )
            except TemplateError:
                package = None
            session.expunge_all()
        if package is None:
            await _fail(self._session_factory, export_id, FAILED)
            raise PermanentJobError(FAILED)
        try:
            chapters = chapter_inputs(snapshot)
            draft = export.kind == ExportKind.DRAFT
            data = await asyncio.to_thread(
                render_document, package, chapters, render_inputs(snapshot, export.kind)
            )
            verify_document(data, chapters, draft=draft)
        except (RenderError, TemplateError) as exc:
            await _fail(self._session_factory, export_id, FAILED)
            logger.warning("Export %s failed: %s", export_id, type(exc).__name__)
            raise PermanentJobError(FAILED) from exc
        blob_id = await self._store.put(data, DOCX_MIME)
        digest = sha256_hex(data)
        async with self._session_factory() as session:
            row = await session.get(ExportEntity, export_id)
            assert row is not None  # noqa: S101  # loaded above
            row.blob_id = blob_id
            row.sha256 = digest
            row.size = len(data)
            row.manifest = _manifest(export, snapshot, digest, len(data))
            row.status = ExportStatus.READY
            row.error = ""
            if export.kind == ExportKind.FINAL:
                workspace: WorkspaceEntity | None = await workspace_repo.find_by_offer(
                    session, export.offer_id
                )
                if workspace is not None:
                    workspace.doc_state = DocState.FINAL
        logger.info("Export %s stored, %d bytes", export_id, len(data))
        return {"status": "ok", "export_id": export_id}


async def _on_exhausted(ctx: JobContext) -> None:
    await _fail(get_asyncdb_session, int(ctx.payload["export_id"]), FAILED)


@register_handler(EXPORT_JOB, on_exhausted=_on_exhausted)
async def export_docx(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    store = DbBlobStore(config.max_blob_bytes)
    return await ExportDocx(store, get_asyncdb_session).run(ctx)
