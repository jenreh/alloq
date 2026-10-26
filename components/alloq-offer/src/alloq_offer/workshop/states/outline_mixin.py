"""Outline of the Kapitel tab: order, "+ Kapitel", remove, restore, title, level.

A mixin of ``ChapterState``; the database work runs through its helpers, so the
session the tests patch stays in one module.
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.services.outline import OutlineService
from alloq_offer.workshop.states.helpers import browser_int

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
        self.blank_title = ""
        self.blank_type = "prose"
        self.library = await self._library()
        self.add_tab = TAB_LIBRARY if self.library else TAB_BLANK
        self.add_open = True

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
        return self.active_key or None

    @rx.event
    @requires_offer_editor
    async def add_block(self, block_key: str) -> AsyncGenerator[Any]:
        after = self._after()
        added, toast = await self._outline_change(
            lambda s: s.add_chapter(after, block_key=block_key), ADDED
        )
        self.add_open = not added
        yield toast

    @rx.event
    @requires_offer_editor
    async def add_blank(self) -> AsyncGenerator[Any]:
        after, kind, title = self._after(), self.blank_type, self.blank_title
        added, toast = await self._outline_change(
            lambda s: s.add_chapter(after, chapter_type=kind, title=title), ADDED
        )
        self.add_open = not added
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
        key, position = self.active_key, self.active_index + step
        _, toast = await self._outline_change(lambda s: s.move_chapter(key, position))
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
        current = next(
            (c["title"] for c in self.chapters if c["key"] == self.active_key), None
        )
        if current is None or str(title).strip() == current:
            return
        key = self.active_key
        _, toast = await self._outline_change(lambda s: s.rename_chapter(key, title))
        yield toast

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
