"""Chapter library in the "Angebote" administration (tab "Kapitelbausteine")."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.access import requires_offer_admin

from alloq_offer.workshop.content.editor_io import content_to_html, html_to_content
from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    MAX_CELL,
    MAX_COLUMNS,
    ContentValidationError,
    ProseContent,
    parse_content,
)
from alloq_offer.workshop.services import chapter_blocks
from alloq_offer.workshop.services.chapter_blocks import (
    MAX_ITEMS,
    BlockError,
    parse_block,
)
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

LOAD_ERROR = "Die Kapitelbausteine konnten nicht geladen werden."
SAVE_ERROR = "Der Kapitelbaustein konnte nicht gespeichert werden."
SAVED = "Der Kapitelbaustein wurde gespeichert."
DELETED = "Der Kapitelbaustein wurde gelöscht."
DELETE_ERROR = "Der Kapitelbaustein konnte nicht gelöscht werden."
BAD_COLUMNS = (
    f"Eine Tabelle hat 1 bis {MAX_COLUMNS} Spalten mit je höchstens {MAX_CELL} Zeichen."
)
TEXT_TOO_LONG = "Der Startinhalt ist zu lang."
MAX_HTML = 200_000

FORM_FIELDS = (
    "key",
    "title",
    "chapter_type",
    "level",
    "guiding_question",
    "content_rules",
    "prompt_text",
    "required_info",
    "checks",
    "active",
    "content_html",
    "columns",
    "group_by",
    "fields",
)
DEFAULT_COLUMNS = ["Punkt", "Beschreibung"]


def _start_content(form: dict[str, Any]) -> dict[str, Any]:
    """The start content of the block from the type specific fields."""
    kind = form["chapter_type"]
    if kind == "prose":
        if len(form["content_html"]) > MAX_HTML:
            raise BlockError(TEXT_TOO_LONG)
        return html_to_content(form["content_html"]).model_dump(mode="json")
    if kind == "table":
        columns = form["columns"]
        if not 0 < len(columns) <= MAX_COLUMNS or any(
            len(c) > MAX_CELL for c in columns
        ):
            raise BlockError(BAD_COLUMNS)
        return {"chapter_type": "table", "columns": columns}
    if kind == "stories":
        return {"chapter_type": "stories", "group_by": form["group_by"]}
    return {
        "chapter_type": "calc",
        "rows": [
            {"label": BOUND_FIELDS[field], "field": field}
            for field in form["fields"]
            if field in BOUND_FIELDS
        ],
    }


class BlockAdminState(rx.State):
    """Admins create, change, deactivate and delete chapter blocks."""

    blocks: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    editor_open: rx.Field[bool] = rx.field(False)
    creating: rx.Field[bool] = rx.field(False)
    # The block being edited; the key field only counts while creating.
    edit_key: rx.Field[str] = rx.field("")
    key: rx.Field[str] = rx.field("")
    title: rx.Field[str] = rx.field("")
    chapter_type: rx.Field[str] = rx.field("prose")
    level: rx.Field[str] = rx.field("1")
    guiding_question: rx.Field[str] = rx.field("")
    content_rules: rx.Field[list[str]] = rx.field(default_factory=list)
    prompt_text: rx.Field[str] = rx.field("")
    required_info: rx.Field[list[str]] = rx.field(default_factory=list)
    checks: rx.Field[list[str]] = rx.field(default_factory=list)
    active: rx.Field[bool] = rx.field(True)
    content_html: rx.Field[str] = rx.field("")
    columns: rx.Field[list[str]] = rx.field(default_factory=list)
    group_by: rx.Field[str] = rx.field("activity")
    fields: rx.Field[list[str]] = rx.field(default_factory=list)
    editor_nonce: rx.Field[int] = rx.field(0)

    @rx.var
    def used_in(self) -> list[str]:
        block = next((b for b in self.blocks if b["key"] == self.key), {})
        return block.get("used_in", [])

    @rx.event
    @requires_offer_admin
    async def load_blocks(self) -> AsyncGenerator[Any]:
        try:
            self.blocks = await chapter_blocks.list_blocks(get_asyncdb_session)
        except Exception:
            logger.exception("Loading the chapter blocks failed")
            yield rx.toast.error(LOAD_ERROR, position="top-right")

    def _fill(self, block: dict[str, Any]) -> None:
        content = parse_content(block["default_content"])
        self.key = block["key"]
        self.title = block["title"]
        self.chapter_type = block["chapter_type"]
        self.level = str(block["level"])
        self.guiding_question = block["guiding_question"]
        self.content_rules = list(block["content_rules"])
        self.prompt_text = block["prompt_text"]
        self.required_info = list(block["required_info"])
        self.checks = list(block["checks"])
        self.active = block["active"]
        self.content_html = (
            content_to_html(content) if isinstance(content, ProseContent) else ""
        )
        self.columns = list(getattr(content, "columns", DEFAULT_COLUMNS))
        self.group_by = getattr(content, "group_by", "activity")
        self.fields = [row.field for row in getattr(content, "rows", [])]
        self.editor_nonce += 1
        self.editor_open = True

    @rx.event
    def open_create(self) -> None:
        self.creating = True
        self._fill(
            {
                "key": "",
                "title": "",
                "chapter_type": "prose",
                "level": 1,
                "default_content": {"chapter_type": "prose"},
                "guiding_question": "",
                "content_rules": [],
                "prompt_text": "",
                "required_info": [],
                "checks": [],
                "active": True,
            }
        )

    @rx.event
    def open_edit(self, key: str) -> None:
        block = next((b for b in self.blocks if b["key"] == key), None)
        if block is not None:
            self.creating = False
            self.edit_key = key
            self._fill(block)

    @rx.event
    def close_editor(self) -> None:
        self.editor_open = False

    @rx.event
    def set_field(self, name: str, value: Any) -> None:
        """One form field; only known ones, with the type the field has."""
        if name not in FORM_FIELDS or (name == "key" and not self.creating):
            return
        current = getattr(self, name)
        if isinstance(current, list):
            if not isinstance(value, list):
                return
            value = [str(item) for item in value[: MAX_ITEMS + 1]]
        elif isinstance(current, bool):
            value = bool(value)
        else:
            value = str(value)
        setattr(self, name, value)

    def _form(self) -> dict[str, Any]:
        form = {name: getattr(self, name) for name in FORM_FIELDS}
        if not self.creating:
            form["key"] = self.edit_key
        return form

    @rx.event
    @requires_offer_admin
    async def save(self) -> AsyncGenerator[Any]:
        form = self._form()
        try:
            data = {
                **form,
                "level": int(form["level"]),
                "default_content": _start_content(form),
            }
            block = parse_block(data)
            await chapter_blocks.save_block(
                get_asyncdb_session, block, create=self.creating
            )
            self.blocks = await chapter_blocks.list_blocks(get_asyncdb_session)
        except ContentValidationError as exc:
            yield rx.toast.error(" ".join(exc.messages), position="top-right")
            return
        except BlockError as exc:
            yield rx.toast.error(str(exc), position="top-right")
            return
        except Exception:
            logger.exception("Saving chapter block %s failed", form["key"])
            yield rx.toast.error(SAVE_ERROR, position="top-right")
            return
        self.editor_open = False
        yield rx.toast.success(SAVED, position="top-right")

    @rx.event
    @requires_offer_admin
    async def delete(self, key: str) -> AsyncGenerator[Any]:
        try:
            await chapter_blocks.delete_block(get_asyncdb_session, key)
            self.blocks = await chapter_blocks.list_blocks(get_asyncdb_session)
        except BlockError as exc:
            yield rx.toast.error(str(exc), position="top-right")
            return
        except Exception:
            logger.exception("Deleting chapter block %s failed", key)
            yield rx.toast.error(DELETE_ERROR, position="top-right")
            return
        self.editor_open = False
        yield rx.toast.success(DELETED, position="top-right")
