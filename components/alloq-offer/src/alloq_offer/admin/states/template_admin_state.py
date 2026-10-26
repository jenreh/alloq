"""Templates in the "Angebote" administration (tab "Vorlagen")."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_admin

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.services import chapter_blocks, template_drafts
from alloq_offer.workshop.services.template_drafts import DraftError, TemplateDraft
from alloq_offer.workshop.states.helpers import browser_int, current_user_name
from alloq_offer.workshop.storage import DbBlobStore
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

UPLOAD_ID = "template_layout_upload"
LOAD_ERROR = "Die Vorlagen konnten nicht geladen werden."
SAVE_ERROR = "Die Änderung der Vorlage konnte nicht gespeichert werden."
UPLOADED = "Das Word-Layout wurde übernommen."
PUBLISHED = "Version {} wurde veröffentlicht."
NO_FILE = "Bitte wählen Sie eine Word-Datei."

DraftAction = Callable[[TemplateDraft], Awaitable[Any]]


class TemplateAdminState(rx.State):
    """Admins edit a template's draft outline and layout and publish versions."""

    templates: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    template_id: rx.Field[int] = rx.field(0)
    outline: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    versions: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    library: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    # Bumped after every outline answer, so the sortable list drops its interim
    # order also after a failed move.
    order_version: rx.Field[int] = rx.field(0)

    @rx.var
    def template(self) -> dict[str, Any]:
        return next((t for t in self.templates if t["id"] == self.template_id), {})

    @rx.var
    def template_options(self) -> list[dict[str, str]]:
        return [{"value": str(t["id"]), "label": t["name"]} for t in self.templates]

    @rx.var
    def entry_ids(self) -> list[str]:
        return [str(entry["id"]) for entry in self.outline]

    async def _reload(self) -> None:
        self.templates = await template_drafts.list_templates(get_asyncdb_session)
        if self.templates and self.template_id not in {t["id"] for t in self.templates}:
            self.template_id = self.templates[0]["id"]
        if not self.template_id:
            return
        self.outline = await template_drafts.load_outline(
            get_asyncdb_session, self.template_id
        )
        self.versions = await template_drafts.list_versions(
            get_asyncdb_session, self.template_id
        )
        used = {entry["block_key"] for entry in self.outline}
        self.library = [
            {"value": block["key"], "label": block["title"]}
            for block in await chapter_blocks.list_blocks(get_asyncdb_session)
            if block["active"] and block["key"] not in used
        ]

    async def _load(self) -> Any | None:
        """Reload; a toast when that failed."""
        try:
            await self._reload()
        except Exception:
            logger.exception("Loading template %s failed", self.template_id)
            return rx.toast.error(LOAD_ERROR, position="top-right")
        return None

    async def _change(self, action: DraftAction, done: str = "") -> Any | None:
        """Run ``action`` and reload; ``done`` is formatted with its result."""
        try:
            result = await action(TemplateDraft(get_asyncdb_session, self.template_id))
        except DraftError as exc:
            await self._load()
            return rx.toast.error(str(exc), position="top-right")
        except Exception:
            logger.exception("Changing template %s failed", self.template_id)
            return rx.toast.error(SAVE_ERROR, position="top-right")
        failed = await self._load()
        if failed or not done:
            return failed
        return rx.toast.success(done.format(result), position="top-right")

    @rx.event
    @requires_offer_admin
    async def load_templates(self) -> AsyncGenerator[Any]:
        yield await self._load()

    @rx.event
    @requires_offer_admin
    async def select_template(self, template_id: str) -> AsyncGenerator[Any]:
        number = browser_int(template_id)
        if number is not None:
            self.template_id = number
            yield await self._load()

    @rx.event
    @requires_offer_admin
    async def add_block(self, block_key: str) -> AsyncGenerator[Any]:
        if block_key:
            yield await self._change(lambda d: d.add_block(block_key))

    @rx.event
    @requires_offer_admin
    async def remove_entry(self, entry_id: int) -> AsyncGenerator[Any]:
        number = browser_int(entry_id)
        if number is not None:
            yield await self._change(lambda d: d.remove(number))

    @rx.event
    @requires_offer_admin
    async def reorder(self, entry_id: str, index: int) -> AsyncGenerator[Any]:
        entry, position = browser_int(entry_id), browser_int(index)
        if entry is None or position is None:
            return
        toast = await self._change(lambda d: d.move(entry, position))
        self.order_version += 1
        yield toast

    def _entry(self, entry_id: object) -> dict[str, Any] | None:
        number = browser_int(entry_id)
        return next((e for e in self.outline if e["id"] == number), None)

    async def _update(self, entry: dict[str, Any], **change: Any) -> Any | None:
        """Store only the changed setting, so others' edits of the entry stay."""
        return await self._change(lambda d: d.update(entry["id"], **change))

    @rx.event
    @requires_offer_admin
    async def set_required(self, entry_id: int, value: bool) -> AsyncGenerator[Any]:
        if entry := self._entry(entry_id):
            yield await self._update(entry, required=bool(value))

    @rx.event
    @requires_offer_admin
    async def set_entry_title(self, entry_id: int, title: str) -> AsyncGenerator[Any]:
        entry = self._entry(entry_id)
        if entry and str(title).strip() != entry["title_override"]:
            yield await self._update(entry, title=str(title))

    @rx.event
    @requires_offer_admin
    async def set_entry_level(self, entry_id: int, level: str) -> AsyncGenerator[Any]:
        """``""`` keeps the block's level; ``1`` or ``2`` overrides it."""
        number = browser_int(level) if level else 0
        if (entry := self._entry(entry_id)) and number is not None:
            yield await self._update(entry, level=number)

    @rx.event
    @requires_offer_admin
    async def handle_upload(self, files: list[rx.UploadFile]) -> AsyncGenerator[Any]:
        if not files:
            yield rx.toast.error(NO_FILE, position="top-right")
            return
        file = files[0]
        config = service_registry().get(WorkshopConfig)
        store = DbBlobStore(config.max_blob_bytes, get_asyncdb_session)
        if file.size is not None and file.size > config.max_blob_bytes:
            yield rx.toast.error(template_drafts.TOO_LARGE, position="top-right")
            return
        data = await file.read()
        if len(data) > config.max_blob_bytes:
            yield rx.toast.error(template_drafts.TOO_LARGE, position="top-right")
            return
        name = file.name or ""
        yield await self._change(lambda d: d.upload_layout(store, name, data), UPLOADED)
        yield rx.clear_selected_files(UPLOAD_ID)

    @rx.event
    @requires_offer_admin
    async def publish(self) -> AsyncGenerator[Any]:
        user = await current_user_name(self)
        yield await self._change(lambda d: d.publish(user), PUBLISHED)
