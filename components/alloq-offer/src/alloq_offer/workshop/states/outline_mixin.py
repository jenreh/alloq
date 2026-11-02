"""Outline of the Kapitel tab: order, "+ Kapitel", remove, restore, title, level.

A mixin of ``ChapterState``; the database work runs through its helpers, so the
session the tests patch stays in one module.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.content.schema import ATTACHED_TYPES
from alloq_offer.workshop.services.outline import OutlineService
from alloq_offer.workshop.states.helpers import browser_int

BLOCK_ID_PREFIX = "aq-chapter-"
TAB_LIBRARY = "library"
TAB_BLANK = "blank"
ADD_TABS: list[dict[str, str]] = [
    {"value": TAB_LIBRARY, "label": "Aus Bibliothek"},
    {"value": TAB_BLANK, "label": "Leeres Kapitel"},
]
LEVEL_OPTIONS: list[dict[str, str]] = [
    {"value": "1", "label": "Kapitel"},
    {"value": "2", "label": "Unterkapitel"},
]
ADDED = "Das Kapitel wurde eingefügt."
NEW_SUBCHAPTER = "Neues Unterkapitel"
# Titles of chapters added with the "+" between two chapters.
NEW_TITLES = {
    "prose": "Neues Kapitel",
    "stories": "User Stories",
    "calc": "Kalkulation",
    "table": "",
    "image": "",
}
# Outline label of a table or image chapter without a title.
ATTACHED_LABELS = {"table": "Tabelle", "image": "Bild"}
REMOVED = "Das Kapitel wurde entfernt. Sie können es wiederherstellen."

OutlineAction = Callable[[OutlineService], Awaitable[Any]]


class OutlineMixin(rx.State, mixin=True):
    """Outline changes; every one reloads the document afterwards."""

    library: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    removed_chapters: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    add_open: rx.Field[bool] = rx.field(False)
    add_tab: rx.Field[str] = rx.field(TAB_LIBRARY)
    blank_title: rx.Field[str] = rx.field("")
    blank_type: rx.Field[str] = rx.field("prose")
    remove_open: rx.Field[bool] = rx.field(False)
    # Where "+ Kapitel" inserts: after this key ("" = first), else the selection.
    _insert_after: str | None = None
    # Main chapters whose sub chapters the outline hides; per viewer, not stored.
    collapsed: rx.Field[list[str]] = rx.field(default_factory=list)
    # Bumped by every drop, so the list drops its interim order even when the
    # move failed and the stored order did not change.
    order_version: rx.Field[int] = rx.field(0)

    if TYPE_CHECKING:
        chapters: list[dict[str, Any]]
        active_key: str

        async def _outline_change(
            self, action: OutlineAction, done: str = ""
        ) -> tuple[bool, Any]: ...

        async def _library(self) -> list[dict[str, Any]]: ...

    @rx.var
    def chapter_ids(self) -> list[str]:
        return [c["key"] for c in self.chapters]

    @rx.var
    def outline_rows(self) -> list[dict[str, Any]]:
        """Outline entries with their label, tree position and visibility."""
        rows: list[dict[str, Any]] = []
        parent = ""
        for chapter in self.chapters:
            attached = chapter["type"] in ATTACHED_TYPES
            main = chapter["level"] == 1 and not attached
            if main:
                parent = chapter["key"]
            elif rows and parent:
                rows[[r["key"] for r in rows].index(parent)]["has_children"] = True
            title = chapter["title"] or ATTACHED_LABELS.get(chapter["type"], "")
            rows.append(
                {
                    **chapter,
                    "label": title if attached else f"{chapter['number']} {title}",
                    "attached": attached,
                    "main": main,
                    "has_children": False,
                    "hidden": not main and parent in self.collapsed,
                    "first": not rows,
                }
            )
        return rows

    @rx.var
    def active_index(self) -> int:
        return next(
            (i for i, c in enumerate(self.chapters) if c["key"] == self.active_key),
            -1,
        )

    @rx.var
    def is_first(self) -> bool:
        return self.active_index <= 0

    @rx.var
    def is_last(self) -> bool:
        return self.active_index in (-1, len(self.chapters) - 1)

    @rx.var
    def has_removed(self) -> bool:
        return bool(self.removed_chapters)

    @rx.event
    @requires_offer_editor
    async def open_add(self) -> None:
        """Open "+ Kapitel" with the blocks the offer does not use yet."""
        self._insert_after = None
        await self._open_add()

    async def _open_add(self) -> None:
        self.blank_title = ""
        self.blank_type = "prose"
        self.library = await self._library()
        self.add_tab = TAB_LIBRARY if self.library else TAB_BLANK
        self.add_open = True

    @rx.event
    def toggle_collapse(self, key: str) -> None:
        if key in self.collapsed:
            self.collapsed = [k for k in self.collapsed if k != key]
        else:
            self.collapsed = [*self.collapsed, key]

    @rx.event
    def close_add(self) -> None:
        self.add_open = False

    @rx.event
    def set_add_tab(self, value: str) -> None:
        self.add_tab = value

    @rx.event
    def set_blank_title(self, value: str) -> None:
        self.blank_title = value

    @rx.event
    def set_blank_type(self, value: str) -> None:
        self.blank_type = value

    def _after(self) -> str | None:
        if self._insert_after is not None:
            return self._insert_after
        return self.active_key or None

    @rx.event
    @requires_offer_editor
    async def insert_chapter(self, after_key: str, kind: str) -> AsyncGenerator[Any]:
        """The "+" between two chapters: a chapter of ``kind`` right there.

        ``after_key`` is the chapter before the gap, "" for the top; ``kind`` is
        a chapter type, "sub" for a sub chapter or "library" for the dialog.
        """
        if kind == "library":
            self._insert_after = after_key
            await self._open_add()
            return
        if kind == "sub":
            added, toast = await self._outline_change(
                lambda s: s.add_subchapter(after_key, title=NEW_SUBCHAPTER), ADDED
            )
        elif kind in NEW_TITLES:
            title = NEW_TITLES[kind]
            added, toast = await self._outline_change(
                lambda s: s.add_chapter(after_key, chapter_type=kind, title=title),
                ADDED,
            )
        else:
            return
        yield toast
        if added:
            yield rx.scroll_to(BLOCK_ID_PREFIX + self.active_key)

    @rx.event
    @requires_offer_editor
    async def add_block(self, block_key: str) -> AsyncGenerator[Any]:
        after = self._after()
        added, toast = await self._outline_change(
            lambda s: s.add_chapter(after, block_key=block_key), ADDED
        )
        self.add_open = not added
        if added:
            self._insert_after = None
        yield toast

    @rx.event
    @requires_offer_editor
    async def add_blank(self) -> AsyncGenerator[Any]:
        after, kind, title = self._after(), self.blank_type, self.blank_title
        added, toast = await self._outline_change(
            lambda s: s.add_chapter(after, chapter_type=kind, title=title), ADDED
        )
        self.add_open = not added
        if added:
            self._insert_after = None
        yield toast

    @rx.event
    @requires_offer_editor
    async def reorder(self, key: str, index: int) -> AsyncGenerator[Any]:
        """Dropped in the outline (mouse or keyboard)."""
        position = browser_int(index)
        if position is None:
            return
        _, toast = await self._outline_change(lambda s: s.move_chapter(key, position))
        self.order_version += 1
        yield toast

    @rx.event
    @requires_offer_editor
    async def move_active(self, delta: int) -> AsyncGenerator[Any]:
        """ "Nach oben" / "Nach unten" in the panel."""
        if not self.active_key or self.active_index < 0:
            return
        step = browser_int(delta)
        if step is None:
            return
        key = self.active_key
        _, toast = await self._outline_change(lambda s: s.step_chapter(key, step))
        yield toast

    @rx.event
    @requires_offer_editor
    async def add_subchapter(self, parent_key: str) -> AsyncGenerator[Any]:
        """ "+ Unterkapitel" on an outline row: a blank text chapter below it."""
        added, toast = await self._outline_change(
            lambda s: s.add_subchapter(parent_key, title=NEW_SUBCHAPTER), ADDED
        )
        yield toast
        if added:
            yield rx.scroll_to(BLOCK_ID_PREFIX + self.active_key)

    @rx.event
    @requires_offer_editor
    async def indent_chapter(self, key: str) -> AsyncGenerator[Any]:
        _, toast = await self._outline_change(lambda s: s.indent(key))
        yield toast

    @rx.event
    @requires_offer_editor
    async def outdent_chapter(self, key: str) -> AsyncGenerator[Any]:
        _, toast = await self._outline_change(lambda s: s.outdent(key))
        yield toast

    @rx.event
    def ask_remove(self) -> None:
        self.remove_open = True

    @rx.event
    def cancel_remove(self) -> None:
        self.remove_open = False

    @rx.event
    @requires_offer_editor
    async def remove_active(self) -> AsyncGenerator[Any]:
        self.remove_open = False
        if not self.active_key:
            return
        key = self.active_key
        _, toast = await self._outline_change(lambda s: s.remove_chapter(key), REMOVED)
        yield toast

    @rx.event
    @requires_offer_editor
    async def restore_chapter(self, key: str) -> AsyncGenerator[Any]:
        _, toast = await self._outline_change(lambda s: s.restore_chapter(key))
        yield toast

    @rx.event
    @requires_offer_editor
    async def rename_active(self, title: str) -> AsyncGenerator[Any]:
        """The "Überschrift" field, stored when it loses the focus."""
        yield await self._rename(self.active_key, title)

    @rx.event
    @requires_offer_editor
    async def rename_chapter(self, key: str, title: str) -> AsyncGenerator[Any]:
        """The heading in the document, stored when it loses the focus."""
        yield await self._rename(key, title)

    async def _rename(self, key: str, title: str) -> Any:
        current = next((c["title"] for c in self.chapters if c["key"] == key), None)
        if current is None or str(title).strip() == current:
            return None
        _, toast = await self._outline_change(lambda s: s.rename_chapter(key, title))
        return toast

    @rx.event
    @requires_offer_editor
    async def set_active_level(self, level: str) -> AsyncGenerator[Any]:
        if not self.active_key:
            return
        key, number = self.active_key, browser_int(level)
        if number is None:
            return
        _, toast = await self._outline_change(lambda s: s.set_level(key, number))
        yield toast
