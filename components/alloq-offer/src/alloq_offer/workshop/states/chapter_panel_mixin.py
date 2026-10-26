"""Module edits of the selected chapter: story grouping, table cells, bound values.

A mixin of ``ChapterState``; each edit stores a new revision through its
``_save_content`` helper, with the same conflict rules as a text save.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

import reflex as rx
from alloq_commons.access import requires_offer_editor

from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    MAX_CELL,
    MAX_COLUMNS,
    MAX_TABLE_ROWS,
    CalcContent,
    CalcRow,
    Run,
    StoriesContent,
    TableContent,
)
from alloq_offer.workshop.content.text import Content
from alloq_offer.workshop.services.chapter_document import (
    free_fields as missing_fields,
)
from alloq_offer.workshop.states.helpers import browser_int

GROUP_OPTIONS: list[dict[str, str]] = [
    {"value": "activity", "label": "Aktivität"},
    {"value": "slice", "label": "Umsetzungsschnitt"},
]
NEW_COLUMN = "Neue Spalte"


def _cell(text: str) -> list[Run]:
    return [Run(text=str(text).strip()[:MAX_CELL])]


def _index(value: object) -> int:
    """A position from the browser; anything else is -1, which no range holds."""
    index = browser_int(value)
    return -1 if index is None else index


class ChapterPanelMixin(rx.State, mixin=True):
    """Edits that belong to the module of the selected chapter."""

    if TYPE_CHECKING:
        chapters: list[dict[str, Any]]
        active_key: str
        input_reset: int
        _content: dict[str, Any]

        async def _save_content(self, content: Content) -> Any | None: ...

    @rx.var
    def free_fields(self) -> list[dict[str, str]]:
        """Bound values the selected calc chapter does not show yet."""
        active = next((c for c in self.chapters if c["key"] == self.active_key), {})
        return missing_fields(active.get("values", []))

    @rx.var
    def can_add_column(self) -> bool:
        active = next((c for c in self.chapters if c["key"] == self.active_key), {})
        return len(active.get("columns", [])) < MAX_COLUMNS

    def _table(self) -> TableContent | None:
        if self._content.get("chapter_type") != "table":
            return None
        return TableContent.model_validate(self._content)

    def _calc(self) -> CalcContent | None:
        if self._content.get("chapter_type") != "calc":
            return None
        return CalcContent.model_validate(self._content)

    @rx.event
    @requires_offer_editor
    async def set_group_by(self, value: str) -> AsyncGenerator[Any]:
        if self._content.get("chapter_type") != "stories" or value not in {
            option["value"] for option in GROUP_OPTIONS
        }:
            return
        yield await self._save_content(StoriesContent(group_by=value))  # ty: ignore[invalid-argument-type]

    @rx.event
    @requires_offer_editor
    async def add_row(self) -> AsyncGenerator[Any]:
        table = self._table()
        if table is None or len(table.rows) >= MAX_TABLE_ROWS:
            return
        table.rows.append([_cell("") for _ in table.columns])
        yield await self._save_content(table)

    @rx.event
    @requires_offer_editor
    async def remove_row(self, index: int) -> AsyncGenerator[Any]:
        table = self._table()
        if table is None or not 0 <= _index(index) < len(table.rows):
            return
        del table.rows[_index(index)]
        yield await self._save_content(table)

    @rx.event
    @requires_offer_editor
    async def add_column(self) -> AsyncGenerator[Any]:
        table = self._table()
        if table is None or len(table.columns) >= MAX_COLUMNS:
            return
        table.columns.append(NEW_COLUMN)
        for row in table.rows:
            row.append(_cell(""))
        yield await self._save_content(table)

    @rx.event
    @requires_offer_editor
    async def rename_column(self, index: int, title: str) -> AsyncGenerator[Any]:
        table = self._table()
        name = str(title).strip()[:MAX_CELL]
        column = _index(index)
        if table is None or not 0 <= column < len(table.columns):
            return
        if not name:
            # A column keeps its name; the field shows it again.
            self.input_reset += 1
            return
        if table.columns[column] == name:
            return
        table.columns[column] = name
        yield await self._save_content(table)

    @rx.event
    @requires_offer_editor
    async def set_cell(self, row: int, column: int, text: str) -> AsyncGenerator[Any]:
        table = self._table()
        r, c = _index(row), _index(column)
        if table is None or not (
            0 <= r < len(table.rows) and 0 <= c < len(table.columns)
        ):
            return
        if (
            "".join(run.text for run in table.rows[r][c])
            == str(text).strip()[:MAX_CELL]
        ):
            return
        table.rows[r][c] = _cell(text)
        yield await self._save_content(table)

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
