"""Plain text and pasted text."""

import re
from html.parser import HTMLParser

from alloq_offer.workshop.extraction.models import (
    KIND_PARAGRAPH,
    ExtractedBlock,
    ExtractionResult,
)

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def decode_text(data: bytes) -> str:
    """UTF-8 first; legacy Windows files fall back to cp1252."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def split_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = (part.strip() for part in _PARAGRAPH_BREAK.split(normalized))
    return [part for part in parts if part]


def parse_text(data: bytes) -> ExtractionResult:
    blocks = [
        ExtractedBlock(KIND_PARAGRAPH, paragraph, {"paragraph": index})
        for index, paragraph in enumerate(split_paragraphs(decode_text(data)), 1)
    ]
    return ExtractionResult(blocks=blocks)


class _TextOnly(HTMLParser):
    _SKIPPED = frozenset({"script", "style", "head"})
    _BLOCKS = frozenset(
        {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        if tag in self._SKIPPED:
            self._skip += 1
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIPPED:
            self._skip = max(self._skip - 1, 0)
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    stripper = _TextOnly()
    stripper.feed(html)
    return "".join(stripper.parts)


def parse_html(data: bytes) -> ExtractionResult:
    return parse_text(html_to_text(decode_text(data)).encode())
