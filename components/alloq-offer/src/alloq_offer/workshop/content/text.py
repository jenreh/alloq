"""Plain text views of chapter content: prompts, previews and revision diffs."""

import difflib
from typing import Any

from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    BulletList,
    CalcContent,
    Heading,
    Inline,
    OrderedList,
    Paragraph,
    ProseContent,
    StoriesContent,
    TableBlock,
    TableContent,
    parse_content,
    plain_text,
)

Content = ProseContent | TableContent | StoriesContent | CalcContent


def _row(cells: list[Inline]) -> str:
    return " | ".join(plain_text(cell) for cell in cells)


def _prose_lines(content: ProseContent) -> list[str]:
    lines: list[str] = []
    for block in content.blocks:
        if isinstance(block, Paragraph):
            lines.append(plain_text(block.runs))
        elif isinstance(block, Heading):
            lines.append(f"{'#' * block.level} {plain_text(block.runs)}")
        elif isinstance(block, BulletList):
            lines.extend(f"- {plain_text(item)}" for item in block.items)
        elif isinstance(block, OrderedList):
            lines.extend(
                f"{number}. {plain_text(item)}"
                for number, item in enumerate(block.items, 1)
            )
        elif isinstance(block, TableBlock):
            lines.append(_row(block.header))
            lines.extend(_row(row) for row in block.rows)
        else:
            lines.append(f"«{BOUND_FIELDS[block.field]}»")
    return [line for line in lines if line.strip()]


def content_lines(content: Content) -> list[str]:
    """One line per paragraph, list item or table row."""
    if isinstance(content, ProseContent):
        return _prose_lines(content)
    if isinstance(content, TableContent):
        return [" | ".join(content.columns), *(_row(row) for row in content.rows)]
    if isinstance(content, CalcContent):
        return [plain_text(content.intro), *(row.label for row in content.rows)]
    return [f"Stories: {', '.join(content.scopes)}"]


def stored_lines(data: dict[str, Any]) -> list[str]:
    return content_lines(parse_content(data))


def diff_lines(old: list[str], new: list[str]) -> list[dict[str, str]]:
    """Line diff as ``{"kind": "same|added|removed", "text": ...}`` entries."""
    kinds = {" ": "same", "+": "added", "-": "removed"}
    return [
        {"kind": kinds[entry[0]], "text": entry[2:]}
        for entry in difflib.ndiff(old, new)
        if entry[0] in kinds
    ]
