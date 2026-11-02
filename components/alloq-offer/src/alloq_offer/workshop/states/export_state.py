"""State of the export tab: request a Word file, follow it, download it."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import ExportKind, ExportStatus
from alloq_offer.workshop.services import exports, findings
from alloq_offer.workshop.states.chapter_state import (
    CONFLICT_LABEL,
    INVALID_LABEL,
    ChapterState,
)
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from alloq_offer.workshop.storage import DbBlobStore
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

LOAD_ERROR = "Die Exporte konnten nicht geladen werden."
REQUEST_ERROR = "Der Export konnte nicht gestartet werden."
DOWNLOAD_ERROR = "Die Datei konnte nicht geladen werden."
QUEUED = "Der Export wird erstellt."
UNSAVED_LABELS = (CONFLICT_LABEL, INVALID_LABEL)


class ExportState(rx.State):
    """Exports of the open offer and the requested output kind."""

    exports: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    reasons: rx.Field[list[str]] = rx.field(default_factory=list)
    confirmed: rx.Field[bool] = rx.field(False)
    open_blockers: rx.Field[int] = rx.field(0)

    @rx.var
    def working(self) -> bool:
        return any(row["status"] == ExportStatus.WORKING for row in self.exports)

    async def _reload(self, offer_id: int) -> None:
        self.exports = await exports.list_exports(get_asyncdb_session, offer_id)
        async with get_asyncdb_session() as session:
            self.open_blockers = len(await findings.open_blockers(session, offer_id))

    @rx.event
    @requires_offer_editor
    async def load_exports(self) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        try:
            await self._reload(offer_id)
        except Exception:
            logger.exception("Loading exports of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def refresh_exports(self) -> None:
        """Poll while a file is being made; keeps the list current."""
        offer_id = await open_offer_id(self)
        if offer_id:
            await self._reload(offer_id)

    @rx.event
    def set_confirmed(self, value: bool) -> None:
        self.confirmed = value

    async def _request(self, kind: ExportKind) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        self.reasons = []
        chapters = await self.get_state(ChapterState)
        config = service_registry().get(WorkshopConfig)
        try:
            await exports.request_export(
                get_asyncdb_session,
                offer_id,
                kind,
                user=await current_user_name(self),
                confirmed=self.confirmed,
                unsaved=chapters.save_label in UNSAVED_LABELS,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            await self._reload(offer_id)
            yield rx.toast.info(QUEUED, position="top-right")
        except exports.ExportBlockedError as exc:
            self.reasons = exc.reasons
        except Exception:
            logger.exception("Starting export of offer %s failed", offer_id)
            yield rx.toast.error(REQUEST_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def export_draft(self) -> AsyncGenerator[Any]:
        async for event in self._request(ExportKind.DRAFT):
            yield event

    @rx.event
    @requires_offer_editor
    async def export_final(self) -> AsyncGenerator[Any]:
        async for event in self._request(ExportKind.FINAL):
            yield event
        self.confirmed = False

    @rx.event
    @requires_offer_editor
    async def download_export(self, export_id: int) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return
        config = service_registry().get(WorkshopConfig)
        try:
            filename, data = await exports.load_download(
                get_asyncdb_session,
                DbBlobStore(config.max_blob_bytes),
                offer_id,
                export_id,
            )
        except exports.ExportBlockedError as exc:
            yield rx.toast.error(str(exc), position="top-right")
            return
        except Exception:
            logger.exception("Download of export %s failed", export_id)
            yield rx.toast.error(DOWNLOAD_ERROR, position="top-right")
            return
        yield rx.download(data=data, filename=filename)
