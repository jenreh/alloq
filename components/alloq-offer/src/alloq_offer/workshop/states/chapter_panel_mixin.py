"""Module edits of the selected chapter: story grouping, the table grid, values.

A mixin of ``ChapterState``; each edit stores a new revision through its
``_save_content`` helper, with the same conflict rules as a text save.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.content.editor_io import html_to_table
from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    CalcContent,
    CalcRow,
    ContentValidationError,
    StoriesContent,
    TableContent,
)
from alloq_offer.workshop.content.text import Content
from alloq_offer.workshop.export.models import NO_SLICE_VALUE
from alloq_offer.workshop.services.chapter_document import (
    free_fields as missing_fields,
)
from alloq_offer.workshop.states.helpers import browser_int

# Refused save of an editor that still shows an older revision.
STALE_EDITOR = (
    "Das Kapitel wurde inzwischen geändert. Die neue Fassung wird angezeigt; "
    "Ihre letzte Eingabe wurde nicht gespeichert."
)
GROUP_OPTIONS: list[dict[str, str]] = [
    {"value": "activity", "label": "Aktivität"},
    {"value": "slice", "label": "Umsetzungsschnitt"},
]


def _index(value: object) -> int:
    """A position from the browser; anything else is -1, which no range holds."""
    index = browser_int(value)
    return -1 if index is None else index


class ChapterPanelMixin(rx.State, mixin=True):
    """Edits that belong to the module of the selected chapter."""

    # Columns and slices of the map with story counts, as select options.
    story_options: rx.Field[dict[str, list[dict[str, str]]]] = rx.field(
        default_factory=dict
    )

    if TYPE_CHECKING:
        chapters: list[dict[str, Any]]
        active_key: str
        input_reset: int
        _content: dict[str, Any]

        async def _save_content(self, content: Content) -> Any | None: ...

        def _stale(self, key: str, mount: str) -> bool: ...

    @rx.var
    def free_fields(self) -> list[dict[str, str]]:
        """Bound values the selected calc chapter does not show yet."""
        active = next((c for c in self.chapters if c["key"] == self.active_key), {})
        return missing_fields(active.get("values", []))

    def _table(self) -> TableContent | None:
        if self._content.get("chapter_type") != "table":
            return None
        return TableContent.model_validate(self._content)

    @rx.event
    @requires_offer_editor
    async def save_table(
        self, key: str, html: str, mount: str = ""
    ) -> AsyncGenerator[Any]:
        """The table editor's grid of the selected table chapter; an editor that
        still shows an older revision is refused, like a text."""
        table = self._table()
        if table is None or key != self.active_key:
            return
        if self._stale(key, mount):
            yield rx.toast.warning(STALE_EDITOR, position="top-right")
            return
        try:
            content = html_to_table(html, table.description)
        except ContentValidationError as exc:
            yield rx.toast.warning(" ".join(exc.messages), position="top-right")
            return
        if content != table:
            yield await self._save_content(content)

    def _calc(self) -> CalcContent | None:
        if self._content.get("chapter_type") != "calc":
            return None
        return CalcContent.model_validate(self._content)

    def _stories(self) -> StoriesContent | None:
        if self._content.get("chapter_type") != "stories":
            return None
        return StoriesContent.model_validate(self._content)

    @rx.event
    @requires_offer_editor
    async def set_group_by(self, value: str) -> AsyncGenerator[Any]:
        stories = self._stories()
        if stories is None or value not in {o["value"] for o in GROUP_OPTIONS}:
            return
        yield await self._save_content(stories.model_copy(update={"group_by": value}))

    def _known(self, kind: str) -> set[str]:
        return {o["value"] for o in self.story_options.get(kind, [])}

    @rx.event
    @requires_offer_editor
    async def set_story_activities(self, values: list[str]) -> AsyncGenerator[Any]:
        """The columns a stories chapter shows; none chosen means all."""
        stories = self._stories()
        if stories is None:
            return
        known = self._known("activities")
        ids = [int(v) for v in values if v in known]
        if ids != stories.activity_ids:
            yield await self._save_content(
                stories.model_copy(update={"activity_ids": ids})
            )

    @rx.event
    @requires_offer_editor
    async def set_story_slices(self, values: list[str]) -> AsyncGenerator[Any]:
        """The slices a stories chapter shows; "none" adds stories without one."""
        stories = self._stories()
        if stories is None:
            return
        known = self._known("slices") - {NO_SLICE_VALUE}
        ids = [int(v) for v in values if v in known]
        unsliced = NO_SLICE_VALUE in values
        if (ids, unsliced) != (stories.slice_ids, stories.unsliced):
            yield await self._save_content(
                stories.model_copy(update={"slice_ids": ids, "unsliced": unsliced})
            )

    @rx.event
    @requires_offer_editor
    async def add_value(self, field: str) -> AsyncGenerator[Any]:
        calc = self._calc()
        if calc is None or field not in BOUND_FIELDS:
            return
        if any(row.field == field for row in calc.rows):
            return
        calc.rows.append(CalcRow(label=BOUND_FIELDS[field], field=field))
        yield await self._save_content(calc)

    @rx.event
    @requires_offer_editor
    async def remove_value(self, index: int) -> AsyncGenerator[Any]:
        calc = self._calc()
        if calc is None or not 0 <= _index(index) < len(calc.rows):
            return
        del calc.rows[_index(index)]
        yield await self._save_content(calc)
