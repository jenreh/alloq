"""State of the chapters tab: list, editor, history and AI proposals (spec 10)."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.editor_io import (
    content_to_html,
    editor_compatible,
    html_to_content,
)
from alloq_offer.workshop.content.schema import ContentValidationError, parse_content
from alloq_offer.workshop.content.text import content_lines
from alloq_offer.workshop.entities import JobStatus
from alloq_offer.workshop.repositories import job_repo
from alloq_offer.workshop.services.chapter_draft import (
    DRAFT_CHAPTERS_JOB,
    ChapterDraftError,
    request_chapter_draft,
)
from alloq_offer.workshop.services.chapters import (
    ChapterConflictError,
    ChapterError,
    ChapterService,
)
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

LOAD_ERROR = "Die Kapitel konnten nicht geladen werden."
SAVE_ERROR = "Die Änderung konnte nicht gespeichert werden."
DRAFT_ERROR = "Der Vorschlag konnte nicht angefordert werden."
DRAFT_QUEUED = "Die KI bereitet Vorschläge vor."
SAVED = "Gespeichert"
CONFLICT_LABEL = "Nicht gespeichert: das Kapitel wurde geändert"
INVALID_LABEL = "Nicht gespeichert: nicht erlaubter Inhalt"
READ_ONLY_NOTE = (
    "Dieses Kapitel wird aus der Story Map oder der Kalkulation gebildet und hier "
    "nicht von Hand bearbeitet."
)
UNSUPPORTED_NOTE = (
    "Dieses Kapitel enthält Bausteine, die der Editor nicht bearbeiten kann."
)
SHORTEN = "Kürze den Text, ohne Aussagen zu streichen."
TECHNICAL = "Formuliere den Text technischer und genauer."
WORKING = (JobStatus.QUEUED, JobStatus.RUNNING)


class ChapterState(rx.State):
    """The chapters of the open offer and the one being edited."""

    chapters: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    active_key: rx.Field[str] = rx.field("")
    revision: rx.Field[int] = rx.field(0)
    editor_html: rx.Field[str] = rx.field("")
    editor_nonce: rx.Field[int] = rx.field(0)
    preview_lines: rx.Field[list[str]] = rx.field(default_factory=list)
    editable: rx.Field[bool] = rx.field(False)
    note: rx.Field[str] = rx.field("")
    origin: rx.Field[str] = rx.field("")
    proposal: rx.Field[dict[str, Any]] = rx.field(default_factory=dict)
    history: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    history_open: rx.Field[bool] = rx.field(False)
    save_label: rx.Field[str] = rx.field("")
    instruction: rx.Field[str] = rx.field("")
    draft_job: rx.Field[str] = rx.field("")

    @rx.var
    def active(self) -> dict[str, Any]:
        return next((c for c in self.chapters if c["key"] == self.active_key), {})

    @rx.var
    def has_active(self) -> bool:
        return bool(self.active)

    @rx.var
    def has_proposal(self) -> bool:
        return bool(self.proposal)

    @rx.var
    def editor_key(self) -> str:
        return f"{self.active_key}:{self.editor_nonce}"

    @rx.var
    def drafting(self) -> bool:
        return self.draft_job in WORKING

    @rx.var
    def status_line(self) -> str:
        parts = [f"Revision {self.revision}", self.origin, self.save_label]
        return " · ".join(part for part in parts if part)

    @rx.var
    def chapter_locked(self) -> bool:
        return bool(self.active.get("protected", False))

    async def _service(self) -> ChapterService | None:
        offer_id = await open_offer_id(self)
        if not offer_id:
            return None
        return ChapterService(
            get_asyncdb_session, offer_id, await current_user_name(self)
        )

    async def _load_active(self, service: ChapterService) -> None:
        loaded = await service.load(self.active_key)
        content = parse_content(loaded["content"])
        self.revision = loaded["revision"]
        self.origin = loaded["origin"]
        self.proposal = loaded["proposal"] or {}
        self.editable = editor_compatible(content)
        self.editor_html = content_to_html(content) if self.editable else ""  # ty: ignore[invalid-argument-type]
        self.preview_lines = [] if self.editable else content_lines(content)
        kind = self.active.get("type", "prose")
        self.note = (
            ""
            if self.editable
            else (UNSUPPORTED_NOTE if kind == "prose" else READ_ONLY_NOTE)
        )
        self.editor_nonce += 1
        self.save_label = ""

    async def _reload(self, service: ChapterService, offer_id: int) -> None:
        self.chapters = await service.open()
        if self.chapters and self.active_key not in {c["key"] for c in self.chapters}:
            self.active_key = self.chapters[0]["key"]
        if self.active_key:
            await self._load_active(service)
        async with get_asyncdb_session() as session:
            job = await job_repo.find_latest(session, offer_id, DRAFT_CHAPTERS_JOB)
        self.draft_job = job.status if job is not None else ""

    @rx.event
    @requires_offer_editor
    async def load_chapters(self) -> AsyncGenerator[Any]:
        """Load the chapters; creates them from the template on first use."""
        service = await self._service()
        if service is None:
            return
        offer_id = await open_offer_id(self)
        try:
            await self._reload(service, offer_id)
        except Exception:
            logger.exception("Loading the chapters of offer %s failed", offer_id)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def refresh_drafts(self) -> AsyncGenerator[Any]:
        """Poll while the AI works; reloads once, when the job has finished."""
        service = await self._service()
        if service is None:
            return
        offer_id = await open_offer_id(self)
        before = self.draft_job
        async with get_asyncdb_session() as session:
            job = await job_repo.find_latest(session, offer_id, DRAFT_CHAPTERS_JOB)
        status = job.status if job is not None else ""
        if status in WORKING:
            return
        self.draft_job = status
        if before in WORKING:
            try:
                await self._reload(service, offer_id)
            except Exception:
                logger.exception("Reloading chapters of offer %s failed", offer_id)
                yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def select_chapter(self, key: str) -> AsyncGenerator[Any]:
        service = await self._service()
        if service is None or key == self.active_key:
            return
        self.active_key = key
        self.history_open = False
        try:
            await self._load_active(service)
        except Exception:
            logger.exception("Loading chapter %s failed", key)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def autosave(self, key: str, html: str) -> AsyncGenerator[Any]:
        """Save the editor text as a new revision; stale editors never overwrite."""
        service = await self._service()
        if service is None or key != self.active_key or not self.editable:
            return
        try:
            content = html_to_content(html)
        except ContentValidationError as exc:
            self.save_label = INVALID_LABEL
            yield rx.toast.warning(" ".join(exc.messages), position="top-right")
            return
        try:
            self.revision = await service.save(key, self.revision, content)
            self.save_label = SAVED
            self._touch(key, self.revision)
        except ChapterConflictError as exc:
            await self._reload(service, await open_offer_id(self))
            self.save_label = CONFLICT_LABEL
            yield rx.toast.warning(str(exc), position="top-right")
        except ChapterError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Saving chapter %s failed", key)
            yield rx.toast.error(SAVE_ERROR, position="top-right")

    def _touch(self, key: str, revision: int) -> None:
        """Mirror a saved revision in the list without re-reading it."""
        self.chapters = [
            {**c, "revision": revision, "needs_review": False, "review_reason": ""}
            if c["key"] == key
            else c
            for c in self.chapters
        ]

    @rx.event
    @requires_offer_editor
    async def set_protected(self, value: bool) -> AsyncGenerator[Any]:
        service = await self._service()
        if service is None or not self.active_key:
            return
        try:
            await service.set_protected(self.active_key, value)
            self.chapters = await service.open()
        except ChapterError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Protecting chapter %s failed", self.active_key)
            yield rx.toast.error(SAVE_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def open_history(self) -> AsyncGenerator[Any]:
        service = await self._service()
        if service is None or not self.active_key:
            return
        try:
            self.history = await service.history(self.active_key)
            self.history_open = True
        except Exception:
            logger.exception("Loading history of %s failed", self.active_key)
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    def close_history(self) -> None:
        self.history_open = False

    @rx.event
    @requires_offer_editor
    async def restore(self, number: int) -> AsyncGenerator[Any]:
        toast = await self._change(
            lambda s: s.restore(self.active_key, self.revision, number), reopen=True
        )
        if toast:
            yield toast

    @rx.event
    @requires_offer_editor
    async def accept_proposal(self) -> AsyncGenerator[Any]:
        if not self.proposal:
            return
        proposal_id = int(self.proposal["id"])
        toast = await self._change(lambda s: s.accept(proposal_id, self.revision))
        if toast:
            yield toast

    @rx.event
    @requires_offer_editor
    async def reject_proposal(self) -> AsyncGenerator[Any]:
        if not self.proposal:
            return
        proposal_id = int(self.proposal["id"])
        toast = await self._change(lambda s: s.reject(proposal_id))
        if toast:
            yield toast

    async def _change(self, action: Any, *, reopen: bool = False) -> Any | None:
        service = await self._service()
        if service is None:
            return None
        offer_id = await open_offer_id(self)
        try:
            await action(service)
        except ChapterConflictError as exc:
            await self._reload(service, offer_id)
            return rx.toast.warning(str(exc), position="top-right")
        except ChapterError as exc:
            await self._reload(service, offer_id)
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Changing chapter %s failed", self.active_key)
            return rx.toast.error(SAVE_ERROR, position="top-right")
        await self._reload(service, offer_id)
        if reopen:
            self.history = await service.history(self.active_key)
        return None

    @rx.event
    def set_instruction(self, value: str) -> None:
        self.instruction = value

    @rx.event
    @requires_offer_editor
    async def draft_active(self, instruction: str) -> AsyncGenerator[Any]:
        """Ask for a proposal for the open chapter (the free text wins if empty)."""
        if not self.active_key:
            return
        async for event in self._queue_draft([self.active_key], instruction):
            yield event

    @rx.event
    @requires_offer_editor
    async def draft_all(self) -> AsyncGenerator[Any]:
        """Ask for proposals for every prose chapter nobody has written yet."""
        async for event in self._queue_draft(None, ""):
            yield event

    async def _queue_draft(
        self, keys: list[str] | None, instruction: str
    ) -> AsyncGenerator[Any]:
        offer_id = await open_offer_id(self)
        if not offer_id or self.drafting:
            return
        config = service_registry().get(WorkshopConfig)
        try:
            await request_chapter_draft(
                get_asyncdb_session,
                offer_id,
                keys=keys,
                instruction=instruction or self.instruction,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            self.draft_job = JobStatus.QUEUED
            yield rx.toast.info(DRAFT_QUEUED, position="top-right")
        except ChapterDraftError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Queueing chapter drafts of offer %s failed", offer_id)
            yield rx.toast.error(DRAFT_ERROR, position="top-right")
