"""State of the sources panel: list, upload, pasted text and retry."""

import base64
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import (
    JobStatus,
    SourceEntity,
    SourceKind,
    SourceStatus,
)
from alloq_offer.workshop.repositories import job_repo, source_repo, workspace_repo
from alloq_offer.workshop.services import sources as source_service
from alloq_offer.workshop.services.source_revocation import revoke_source
from alloq_offer.workshop.services.sources import (
    READABLE_STATUSES,
    SourceOriginal,
    SourceRejectedError,
)
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from alloq_offer.workshop.storage import BlobTooLargeError, DbBlobStore
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

UPLOAD_ID = "source_upload"
KIND_LABELS: dict[str, str] = {
    SourceKind.TEXT: "Text",
    SourceKind.TXT: "Text",
    SourceKind.HTML: "HTML",
    SourceKind.EML: "E-Mail",
    SourceKind.DOCX: "Dokument",
    SourceKind.PDF: "PDF",
    SourceKind.PPTX: "Folien",
    SourceKind.AUDIO: "Audio",
}
WORKING = (SourceStatus.UPLOADED, SourceStatus.PROCESSING)
RETRYABLE = (SourceStatus.FAILED, SourceStatus.MANUAL)
LOAD_ERROR = "Die Quellen konnten nicht geladen werden."
ADD_ERROR = "Die Quelle konnte nicht hinzugefügt werden."
RETRY_ERROR = "Die Quelle konnte nicht erneut gestartet werden."
REVOKED = "Die Quelle wurde zurückgezogen und ihr Inhalt gelöscht."
REVOKE_ERROR = "Die Quelle konnte nicht zurückgezogen werden."
SAVE_ERROR = "Die Änderung konnte nicht gespeichert werden."
EMPTY_TEXT = "Bitte geben Sie einen Text ein."
DRAFT_QUEUED = "Der Entwurf wird erzeugt."
DRAFT_ERROR = "Der Entwurf konnte nicht gestartet werden."
DRAFT_STATUS: dict[str, str] = {
    JobStatus.QUEUED: "Der Entwurf wartet auf die Bearbeitung.",
    JobStatus.RUNNING: "Der Entwurf wird gerade erzeugt.",
    JobStatus.FAILED: "Der Entwurf ist fehlgeschlagen. Sie können es erneut versuchen.",
}
TOO_LARGE = "Die Datei ist zu groß: "
# Files reach the viewer as base64 over the state socket; past this, don't.
PREVIEW_LIMIT = 30 * 1024 * 1024
TOO_LARGE_TO_SHOW = (
    "Die Datei ist zu groß für die Vorschau. Der gelesene Text bleibt verfügbar."
)
VIEWER_TAB_ORIGINAL = "original"
VIEWER_TAB_TEXT = "text"
KNOWN = "Diese Quelle gibt es schon: "


def source_row(source: SourceEntity) -> dict[str, Any]:
    """The values the sources list shows for one source."""
    kind = KIND_LABELS.get(source.kind, source.kind)
    summary = f"{kind} · {source.status}"
    if source.status_detail:
        summary += f" · {source.status_detail}"
    return {
        "id": source.id,
        "name": source.title,
        "summary": summary,
        "included": source.included,
        "usable": source.status in READABLE_STATUSES,
        "ok": source.status in (*READABLE_STATUSES, *WORKING),
        "working": source.status in WORKING,
        "retryable": source.status in RETRYABLE,
    }


class SourcesState(rx.State):
    """Customer sources of the open offer."""

    sources: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    paste_open: rx.Field[bool] = rx.field(False)
    viewer_open: rx.Field[bool] = rx.field(False)
    viewer_title: rx.Field[str] = rx.field("")
    viewer_blocks: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    viewer_kind: rx.Field[str] = rx.field("")
    viewer_file: rx.Field[str] = rx.field("")
    viewer_encoded: rx.Field[str] = rx.field("")
    viewer_note: rx.Field[str] = rx.field("")
    viewer_tab: rx.Field[str] = rx.field(VIEWER_TAB_TEXT)
    draft_job: rx.Field[str] = rx.field("")
    draft_error: rx.Field[str] = rx.field("")
    has_map: rx.Field[bool] = rx.field(False)

    @rx.var
    def included_count(self) -> int:
        return sum(1 for row in self.sources if row["included"] and row["usable"])

    @rx.var
    def draft_working(self) -> bool:
        return self.draft_job in (JobStatus.QUEUED, JobStatus.RUNNING)

    @rx.var
    def draft_message(self) -> str:
        if self.draft_job == JobStatus.FAILED and self.draft_error:
            return f"Der Entwurf ist fehlgeschlagen. {self.draft_error}"
        return DRAFT_STATUS.get(self.draft_job, "")

    @rx.var
    def can_generate(self) -> bool:
        return self.included_count > 0 and not self.has_map and not self.draft_working

    @rx.var
    def generate_label(self) -> str:
        noun = "Quelle" if self.included_count == 1 else "Quellen"
        return f"Entwurf aus {self.included_count} {noun} erzeugen"

    @rx.var
    def has_working(self) -> bool:
        return self.draft_working or any(row["working"] for row in self.sources)

    @rx.var
    def is_empty(self) -> bool:
        return not self.sources

    @rx.var
    def reading(self) -> bool:
        return any(row["working"] for row in self.sources)

    @rx.var
    def read_progress(self) -> int:
        """Share of the listed sources that are read, in percent."""
        if not self.sources:
            return 0
        done = sum(not row["working"] for row in self.sources)
        return round(100 * done / len(self.sources))

    @rx.var
    def read_label(self) -> str:
        done = sum(not row["working"] for row in self.sources)
        return f"{done} von {len(self.sources)} Quellen gelesen"

    async def _offer_id(self) -> int:
        return await open_offer_id(self)

    async def _user_name(self) -> str:
        return await current_user_name(self)

    async def _reload(self, offer_id: int) -> None:
        async with get_asyncdb_session() as session:
            rows = await source_repo.list_current(session, offer_id)
            self.sources = [source_row(row) for row in rows]
            workspace = await workspace_repo.find_by_offer(session, offer_id)
            self.has_map = workspace is not None and workspace.map_revision > 0
            job = await job_repo.find_latest(
                session, offer_id, source_service.INITIAL_DRAFT_JOB
            )
            self.draft_job = job.status if job is not None else ""
            self.draft_error = (job.error_message or "") if job is not None else ""

    @rx.event
    def open_paste(self) -> None:
        self.paste_open = True

    @rx.event
    def close_paste(self) -> None:
        self.paste_open = False

    @rx.event
    def close_viewer(self) -> None:
        self.viewer_open = False
        # Release the file instead of keeping megabytes in the state.
        self.viewer_encoded = ""

    @rx.event
    def set_viewer_tab(self, tab: str | None) -> None:
        self.viewer_tab = tab or VIEWER_TAB_TEXT

    def _show_original(self, original: SourceOriginal | None) -> None:
        self.viewer_kind = original.kind if original else ""
        self.viewer_file = original.filename if original else ""
        too_large = original is not None and len(original.data) > PREVIEW_LIMIT
        self.viewer_note = TOO_LARGE_TO_SHOW if too_large else ""
        self.viewer_encoded = (
            base64.b64encode(original.data).decode("ascii")
            if original and not too_large
            else ""
        )
        self.viewer_tab = VIEWER_TAB_ORIGINAL if original else VIEWER_TAB_TEXT

    @rx.event
    @requires_offer_editor
    async def open_viewer(self, source_id: int) -> AsyncGenerator[Any]:
        """Show the uploaded file and the extracted blocks of a source."""
        offer_id = await self._offer_id()
        config = service_registry().get(WorkshopConfig)
        try:
            title, blocks = await source_service.load_blocks(
                get_asyncdb_session, offer_id, source_id
            )
            original = await source_service.load_original(
                get_asyncdb_session,
                DbBlobStore(config.max_blob_bytes),
                offer_id,
                source_id,
            )
        except Exception:
            logger.exception("Loading blocks of source %s failed", source_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")
            return
        self.viewer_title = title
        self.viewer_blocks = blocks
        self._show_original(original)
        self.viewer_open = True

    @rx.event
    @requires_offer_editor
    async def load_sources(self) -> AsyncGenerator[Any]:
        """Load the sources; also called while a source is still being read."""
        offer_id = await self._offer_id()
        if not offer_id:
            return
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading sources of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def generate_draft(self) -> AsyncGenerator[Any]:
        """Queue the first draft from the included sources."""
        offer_id = await self._offer_id()
        if not offer_id or not self.can_generate:
            return
        config = service_registry().get(WorkshopConfig)
        try:
            await source_service.request_initial_draft(
                get_asyncdb_session,
                offer_id,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            await self._reload(offer_id)
            yield rx.toast.info(DRAFT_QUEUED, position="top-right")
        except source_service.DraftNotPossibleError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Queueing the draft of offer %s failed", offer_id)
            yield rx.toast.error(DRAFT_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def toggle_source(
        self, source_id: int, included: bool
    ) -> AsyncGenerator[Any]:
        """Take a source into or out of the next draft."""
        offer_id = await self._offer_id()
        try:
            await source_service.set_included(
                get_asyncdb_session, offer_id, source_id, included
            )
            await self._reload(offer_id)
        except Exception:
            logger.exception("Switching source %s failed", source_id)
            yield rx.toast.error(SAVE_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def revoke_source(self, source_id: int) -> AsyncGenerator[Any]:
        """Withdraw a source: its content is deleted, dependents are flagged."""
        offer_id = await self._offer_id()
        try:
            await revoke_source(
                get_asyncdb_session, offer_id, source_id, now=datetime.now(UTC)
            )
            await self._reload(offer_id)
            yield rx.toast.info(REVOKED, position="top-right")
        except Exception:
            logger.exception("Revoking source %s failed", source_id)
            yield rx.toast.error(REVOKE_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def retry_source(self, source_id: int) -> AsyncGenerator[Any]:
        """Read a failed source again."""
        offer_id = await self._offer_id()
        config = service_registry().get(WorkshopConfig)
        try:
            await source_service.retry_source(
                get_asyncdb_session,
                offer_id,
                source_id,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            await self._reload(offer_id)
        except Exception:
            logger.exception("Retrying source %s failed", source_id)
            yield rx.toast.error(RETRY_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def handle_upload(self, files: list[rx.UploadFile]) -> AsyncGenerator[Any]:
        """Add dropped files as sources; rejected files are named in a toast."""
        offer_id = await self._offer_id()
        if not offer_id:
            return
        config = service_registry().get(WorkshopConfig)
        store = DbBlobStore(config.max_blob_bytes)
        user = await self._user_name()
        for file in files:
            name = file.name or "Datei"
            try:
                kind = source_service.classify_filename(name)
                if file.size is not None and file.size > config.max_blob_bytes:
                    raise BlobTooLargeError(file.size)
                added = await source_service.add_source(
                    store,
                    offer_id=offer_id,
                    kind=kind,
                    title=name,
                    filename=name,
                    mime=file.content_type or "application/octet-stream",
                    data=await file.read(),
                    user=user,
                    now=datetime.now(UTC),
                    max_attempts=config.max_attempts,
                )
                if not added.created:
                    yield rx.toast.info(KNOWN + name, position="top-right")
            except SourceRejectedError as exc:
                yield rx.toast.error(str(exc), position="top-right")
            except BlobTooLargeError:
                yield rx.toast.error(TOO_LARGE + name, position="top-right")
            except Exception:
                logger.exception(
                    "Adding an uploaded source to offer %s failed", offer_id
                )
                yield rx.toast.error(ADD_ERROR, position="top-right")
        await self._reload(offer_id)
        yield rx.clear_selected_files(UPLOAD_ID)

    @rx.event
    @requires_offer_editor
    async def add_pasted_text(self, form: dict[str, Any]) -> AsyncGenerator[Any]:
        """Add pasted text as a source."""
        text = str(form.get("text", "")).strip()
        if not text:
            yield rx.toast.error(EMPTY_TEXT, position="top-right")
            return
        offer_id = await self._offer_id()
        config = service_registry().get(WorkshopConfig)
        title = str(form.get("title", "")).strip() or source_service.DEFAULT_TEXT_TITLE
        try:
            added = await source_service.add_source(
                DbBlobStore(config.max_blob_bytes),
                offer_id=offer_id,
                kind=SourceKind.TEXT,
                title=title[:255],
                filename="",
                mime="text/plain",
                data=text.encode(),
                user=await self._user_name(),
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            await self._reload(offer_id)
            self.paste_open = False
            if not added.created:
                yield rx.toast.info(KNOWN + added.source.title, position="top-right")
        except BlobTooLargeError:
            yield rx.toast.error(TOO_LARGE + title, position="top-right")
        except Exception:
            logger.exception("Adding pasted text to offer %s failed", offer_id)
            yield rx.toast.error(ADD_ERROR, position="top-right")
