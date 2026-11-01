"""Plain text views of chapter content: prompts, previews and revision diffs."""

import difflib
from typing import Any

from alloq_offer.workshop.content.schema import (
    BOUND_FIELDS,
    AnyContent,
    BulletList,
    CalcContent,
    CodeBlock,
    Heading,
    ImageContent,
    Inline,
    OrderedList,
    Paragraph,
    ProseContent,
    Quote,
    Rule,
    TableBlock,
    TableContent,
    TaskList,
    parse_content,
    plain_text,
)

STORIES_LINE = "Stories der Story Map"
IMAGE_LINE = "Bild"

Content = AnyContent


def _row(cells: list[Inline]) -> str:
    return " | ".join(plain_text(cell) for cell in cells)


def _list_lines(
    block: BulletList | OrderedList | TaskList, depth: int = 0
) -> list[str]:
    lines: list[str] = []
    for number, item in enumerate(block.items, 1):
        if isinstance(block, OrderedList):
            marker = f"{number}."
        elif isinstance(block, TaskList):
            marker = "- [x]" if item.checked else "- [ ]"
        else:
            marker = "-"
        lines.append(f"{'  ' * depth}{marker} {plain_text(item.runs)}")
        for child in item.children:
            lines.extend(_list_lines(child, depth + 1))
    return lines


def _prose_lines(content: ProseContent) -> list[str]:
    lines: list[str] = []
    for block in content.blocks:
        if isinstance(block, Paragraph):
            lines.append(plain_text(block.runs))
        elif isinstance(block, Heading):
            lines.append(f"{'#' * block.level} {plain_text(block.runs)}")
        elif isinstance(block, BulletList | OrderedList | TaskList):
            lines.extend(_list_lines(block))
        elif isinstance(block, Quote):
            lines.extend(f"> {plain_text(p)}" for p in block.paragraphs)
        elif isinstance(block, CodeBlock):
            lines.extend(block.text.splitlines())
        elif isinstance(block, Rule):
            lines.append("---")
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
        caption = [plain_text(content.description)] if content.description else []
        return [
            " | ".join(content.columns),
            *(_row(row) for row in content.rows),
            *caption,
        ]
    if isinstance(content, ImageContent):
        return [
            f"{IMAGE_LINE}: {content.alt}" if content.alt else IMAGE_LINE,
            *([plain_text(content.description)] if content.description else []),
        ]
    if isinstance(content, CalcContent):
        return [plain_text(content.intro), *(row.label for row in content.rows)]
    return [STORIES_LINE]


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
