"""Result types shared by the source parsers."""

from dataclasses import dataclass, field

KIND_PARAGRAPH = "paragraph"
KIND_TABLE = "table"
KIND_HEADER = "header"
KIND_QUOTE = "quote"
KIND_SIGNATURE = "signature"
KIND_NOTE = "note"
KIND_SPEECH = "speech"
KIND_GAP = "gap"


@dataclass(frozen=True)
class ExtractedBlock:
    """One citable piece of a source: text with the place it came from."""

    kind: str
    text: str
    anchor: dict = field(default_factory=dict)
    speaker: str | None = None

    @property
    def is_gap(self) -> bool:
        return self.kind == KIND_GAP


def gap(reason: str, anchor: dict) -> ExtractedBlock:
    """A part of the source the app could not read; ``reason`` is shown to users."""
    return ExtractedBlock(kind=KIND_GAP, text=reason, anchor=anchor)


@dataclass(frozen=True)
class Attachment:
    """A file inside a source (an e-mail attachment) that becomes a source itself."""

    filename: str
    mime: str
    data: bytes


@dataclass(frozen=True)
class ExtractionResult:
    """Everything a parser found in one source."""

    blocks: list[ExtractedBlock] = field(default_factory=list)
    title: str = ""
    attachments: list[Attachment] = field(default_factory=list)

    @property
    def text_blocks(self) -> list[ExtractedBlock]:
        return [block for block in self.blocks if not block.is_gap]

    @property
    def gaps(self) -> list[ExtractedBlock]:
        return [block for block in self.blocks if block.is_gap]


class ExtractionError(ValueError):
    """The file cannot be read at all (corrupt, encrypted, wrong type)."""


def anchor_label(anchor: dict) -> str:
    """Where in the source a block came from, in the words users know."""
    for key, label in (
        ("page", "Seite"),
        ("slide", "Folie"),
        ("table", "Tabelle"),
        ("paragraph", "Absatz"),
    ):
        if key in anchor:
            return f"{label} {anchor[key]}"
    if "start_ms" in anchor:
        seconds = anchor["start_ms"] // 1000
        return f"{seconds // 60}:{seconds % 60:02d}"
    return ""
