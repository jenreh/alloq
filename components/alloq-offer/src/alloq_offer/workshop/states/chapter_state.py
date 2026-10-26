"""State of the Kapitel tab: the offer as one document (spec 10).

The outline and the module edits live in mixins; the database helpers they use
stay here, next to the session the tests patch.
"""

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
from alloq_offer.workshop.content.schema import (
    ContentValidationError,
    TableContent,
    parse_content,
)
from alloq_offer.workshop.content.text import Content
from alloq_offer.workshop.entities import JobStatus
from alloq_offer.workshop.repositories import job_repo
from alloq_offer.workshop.services.chapter_document import load_document, render_block
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
from alloq_offer.workshop.services.outline import OutlineService
from alloq_offer.workshop.states.chapter_panel_mixin import ChapterPanelMixin
from alloq_offer.workshop.states.helpers import current_user_name, open_offer_id
from alloq_offer.workshop.states.outline_mixin import OutlineAction, OutlineMixin
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
UNSUPPORTED_NOTE = (
    "Dieses Kapitel enthält Bausteine, die der Editor nicht bearbeiten kann."
)
SHORTEN = "Kürze den Text, ohne Aussagen zu streichen."
TECHNICAL = "Formuliere den Text technischer und genauer."
WORKING = (JobStatus.QUEUED, JobStatus.RUNNING)
BLOCK_ID_PREFIX = "aq-chapter-"


class ChapterState(OutlineMixin, ChapterPanelMixin, rx.State):
    """The chapters of the open offer and the one being edited."""

    chapters: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    frame_before: rx.Field[list[str]] = rx.field(default_factory=list)
    frame_after: rx.Field[list[str]] = rx.field(default_factory=list)
    # Stored content of the selected chapter, for the module edits.
    _content: dict[str, Any] = {}  # noqa: RUF012
    active_key: rx.Field[str] = rx.field("")
    revision: rx.Field[int] = rx.field(0)
    editor_html: rx.Field[str] = rx.field("")
    editor_nonce: rx.Field[int] = rx.field(0)
    editable: rx.Field[bool] = rx.field(False)
    note: rx.Field[str] = rx.field("")
    origin: rx.Field[str] = rx.field("")
    proposal: rx.Field[dict[str, Any]] = rx.field(default_factory=dict)
    history: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    history_open: rx.Field[bool] = rx.field(False)
    save_label: rx.Field[str] = rx.field("")
    instruction: rx.Field[str] = rx.field("")
    draft_job: rx.Field[str] = rx.field("")
    instruction_open: rx.Field[bool] = rx.field(False)
    # Bumped when a save or change failed, so uncontrolled inputs show the
    # stored text again.
    input_reset: rx.Field[int] = rx.field(0)
    # Chapter and revision the mounted editor shows.
    _editor_for: str = ""

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

    @staticmethod
    def _outline_for(service: ChapterService) -> OutlineService:
        return OutlineService(get_asyncdb_session, service.offer_id, service.user)

    async def _library(self) -> list[dict[str, Any]]:
        service = await self._service()
        if service is None:
            return []
        try:
            return await self._outline_for(service).library()
        except Exception:
            logger.exception("Loading the chapter library failed")
            return []

    async def _outline_change(
        self, action: OutlineAction, done: str = ""
    ) -> tuple[bool, Any]:
        """Run an outline change and reload; ``(changed, toast)``."""
        service = await self._service()
        if service is None:
            return False, None
        try:
            result = await action(self._outline_for(service))
        except ChapterError as exc:
            self.input_reset += 1
            await self._reload(service)
            return False, rx.toast.error(str(exc), position="top-right")
        except Exception:
            self.input_reset += 1
            logger.exception(
                "Changing the outline of offer %s failed", service.offer_id
            )
            return False, rx.toast.error(SAVE_ERROR, position="top-right")
        if isinstance(result, str):
            self.active_key = result
        await self._reload(service)
        return True, rx.toast.success(done, position="top-right") if done else None

    async def _save(
        self, service: ChapterService, key: str, revision: int, content: Content
    ) -> tuple[int | None, Any]:
        """Store a revision; ``(new revision, None)`` or ``(None, toast)``."""
        try:
            return await service.save(key, revision, content), None
        except ChapterConflictError as exc:
            await self._reload(service)
            failed = rx.toast.warning(str(exc), position="top-right")
            self.save_label = CONFLICT_LABEL
        except ChapterError as exc:
            failed = rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Saving chapter %s failed", key)
            failed = rx.toast.error(SAVE_ERROR, position="top-right")
        # Uncontrolled inputs show the stored text again.
        self.input_reset += 1
        return None, failed

    async def _save_content(self, content: Content) -> Any | None:
        """Store a module edit of the selected chapter as a new revision."""
        service = await self._service()
        if service is None or not self.active_key:
            return None
        key = self.active_key
        revision, failed = await self._save(service, key, self.revision, content)
        if revision is None:
            return failed
        self.save_label = SAVED
        if isinstance(content, TableContent):
            # A table needs neither the map nor the values to show itself.
            self.revision = revision
            self._content = content.model_dump(mode="json")
            self._touch(key, revision, render_block(content, (), {}))
        else:
            await self._reload(service)
        return None

    async def _load_active(self, service: ChapterService) -> None:
        self._show_active(await service.load(self.active_key))

    def _show_active(self, loaded: dict[str, Any]) -> None:
        self._content = loaded["content"]
        content = parse_content(loaded["content"])
        self.revision = loaded["revision"]
        self.origin = loaded["origin"]
        self.proposal = loaded["proposal"] or {}
        self.editable = editor_compatible(content)
        self.editor_html = content_to_html(content) if self.editable else ""
        prose = self.active.get("type", "prose") == "prose"
        self.note = UNSUPPORTED_NOTE if prose and not self.editable else ""
        # Only another chapter or revision remounts the editor; a reload while
        # somebody types keeps the cursor.
        shown = f"{self.active_key}:{self.revision}"
        if shown != self._editor_for:
            self._editor_for = shown
            self.editor_nonce += 1
        self.save_label = ""

    async def _reload(
        self, service: ChapterService, *, select_first: bool = False
    ) -> None:
        """Document, frame and removed chapters; the selection stays if it can."""
        document = await load_document(
            get_asyncdb_session, service.offer_id, service.user
        )
        if document is None:
            return
        self.chapters = document.chapters
        self.frame_before = document.frame_before
        self.frame_after = document.frame_after
        self.removed_chapters = document.removed
        keys = [c["key"] for c in self.chapters]
        if self.active_key not in keys:
            # A removed chapter leaves nothing selected; a new page starts at 1.
            self.active_key = keys[0] if select_first and keys else ""
        if self.active_key:
            self._show_active(document.details[self.active_key])
        self.draft_job = document.draft_job

    @rx.event
    @requires_offer_editor
    async def load_chapters(self) -> AsyncGenerator[Any]:
        """Load the chapters; creates them from the template on first use."""
        service = await self._service()
        if service is None:
            return
        try:
            await self._reload(service, select_first=True)
        except Exception:
            logger.exception(
                "Loading the chapters of offer %s failed", service.offer_id
            )
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def refresh_drafts(self) -> AsyncGenerator[Any]:
        """Poll while the AI works; reloads once, when the job has finished."""
        service = await self._service()
        if service is None:
            return
        offer_id = service.offer_id
        before = self.draft_job
        async with get_asyncdb_session() as session:
            job = await job_repo.find_latest(session, offer_id, DRAFT_CHAPTERS_JOB)
        status = job.status if job is not None else ""
        if status in WORKING:
            return
        self.draft_job = status
        if before in WORKING:
            try:
                await self._reload(service)
            except Exception:
                logger.exception("Reloading chapters of offer %s failed", offer_id)
                yield rx.toast.error(LOAD_ERROR, position="top-right")

    @rx.event
    @requires_offer_editor
    async def select_chapter(self, key: str) -> AsyncGenerator[Any]:
        """A click on a block makes it the one being edited."""
        yield await self._select(key)

    async def _select(self, key: str) -> Any | None:
        service = await self._service()
        if service is None or key == self.active_key:
            return None
        self.active_key = key
        self.history_open = False
        try:
            await self._load_active(service)
        except Exception:
            # Module edits must never save the previous chapter's content here.
            self.active_key = ""
            self._content = {}
            logger.exception("Loading chapter %s failed", key)
            return rx.toast.error(LOAD_ERROR, position="top-right")
        return None

    @rx.event
    @requires_offer_editor
    async def jump_to(self, key: str) -> AsyncGenerator[Any]:
        """Click in the outline: select the chapter and scroll the document to it."""
        yield await self._select(key)
        yield rx.scroll_to(f"{BLOCK_ID_PREFIX}{key}")

    @rx.event
    def clear_selection(self) -> None:
        """A click on the page around the blocks ends the editing."""
        self.active_key = ""
        self.history_open = False

    @rx.event
    @requires_offer_editor
    async def autosave(self, key: str, html: str) -> AsyncGenerator[Any]:
        """Save a text chapter's editor content; stale editors never overwrite.

        The text belongs to ``key`` even when another chapter was selected in
        the meantime, so the last words typed are never lost.
        """
        service = await self._service()
        chapter = next((c for c in self.chapters if c["key"] == key), None)
        if service is None or chapter is None or chapter["type"] != "prose":
            return
        if key == self.active_key and not self.editable:
            return
        try:
            content = html_to_content(html)
        except ContentValidationError as exc:
            self.save_label = INVALID_LABEL
            yield rx.toast.warning(" ".join(exc.messages), position="top-right")
            return
        revision, failed = await self._save(service, key, chapter["revision"], content)
        if revision is None:
            yield failed
            return
        self.save_label = SAVED
        if key == self.active_key:
            self.revision = revision
            self._content = content.model_dump(mode="json")
            self._editor_for = f"{key}:{revision}"
        self._touch(key, revision, {"html": content_to_html(content)})

    def _touch(self, key: str, revision: int, shown: dict[str, Any]) -> None:
        """Mirror a saved block in the document without re-reading it."""
        saved = {"revision": revision, "needs_review": False, "review_reason": ""}
        self.chapters = [
            {**c, **saved, **shown} if c["key"] == key else c for c in self.chapters
        ]

    @rx.event
    @requires_offer_editor
    async def set_protected(self, value: bool) -> AsyncGenerator[Any]:
        service = await self._service()
        if service is None or not self.active_key:
            return
        try:
            await service.set_protected(self.active_key, value)
            await self._reload(service)
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
        try:
            await action(service)
        except ChapterConflictError as exc:
            await self._reload(service)
            return rx.toast.warning(str(exc), position="top-right")
        except ChapterError as exc:
            await self._reload(service)
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Changing chapter %s failed", self.active_key)
            return rx.toast.error(SAVE_ERROR, position="top-right")
        await self._reload(service)
        if reopen:
            self.history = await service.history(self.active_key)
        return None

    @rx.event
    def set_instruction(self, value: str) -> None:
        self.instruction = value

    @rx.event
    def open_instruction(self) -> None:
        self.instruction_open = True

    @rx.event
    def close_instruction(self) -> None:
        self.instruction_open = False

    @rx.event
    @requires_offer_editor
    async def draft_active(self, instruction: str) -> AsyncGenerator[Any]:
        """Ask for a proposal for the open chapter with exactly this instruction."""
        self.instruction_open = False
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
                instruction=instruction,
                now=datetime.now(UTC),
                max_attempts=config.max_attempts,
            )
            self.draft_job = JobStatus.QUEUED
            # The free text was for this request; the next one starts empty.
            self.instruction = ""
            yield rx.toast.info(DRAFT_QUEUED, position="top-right")
        except ChapterDraftError as exc:
            yield rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Queueing chapter drafts of offer %s failed", offer_id)
            yield rx.toast.error(DRAFT_ERROR, position="top-right")
