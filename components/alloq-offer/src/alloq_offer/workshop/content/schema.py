"""Typed chapter content model of the offer workshop.

A chapter holds one of five content types. ``prose`` is the canonical block
tree, ``table`` a plain grid, ``stories`` only settings (the text is resolved
from the story map when rendering), ``calc`` bound commercial values and
``image`` one uploaded picture.
Anything outside this model is rejected with a German message.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic_core import ErrorDetails

BOUND_FIELDS: dict[str, str] = {
    "offer.person_days": "Personentage",
    "offer.risk_buffer_days": "Risikopuffer (Personentage)",
    "offer.production_cost": "Herstellkosten",
    "offer.recommended_price": "Empfohlener Preis",
    "workspace.currency": "Währung",
    "workspace.validity_date": "Bindefrist",
}


# Limits of a table chapter, for people and the AI alike.
MAX_TABLE_ROWS = 200
MAX_CELL = 2000
MAX_COLUMNS = 8
# Table and image chapters hang under the chapter before them: no heading, no
# number, always level 2.
ATTACHED_TYPES = frozenset({"table", "image"})
# Limits of an image chapter.
MAX_ALT = 300
MIN_IMAGE_WIDTH = 10
MAX_IMAGE_WIDTH = 100


class ContentValidationError(ValueError):
    """Chapter content violates the content model; messages are German."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages


def _new_block_id() -> str:
    return uuid.uuid4().hex[:8]


# Text colors of the editor palette, stored by name; the hex is what the editor
# writes into the HTML.
TEXT_COLORS: dict[str, str] = {
    "gray": "#6e6e73",
    "red": "#d70015",
    "orange": "#c93400",
    "green": "#248a3d",
    "blue": "#0040dd",
    "purple": "#8944ab",
}
TextColor = Literal["gray", "red", "orange", "green", "blue", "purple"]
LINK_SCHEMES = ("http://", "https://", "mailto:")
MAX_LINK = 2000
BAD_LINK = "Links brauchen eine Adresse mit http://, https:// oder mailto:."
MAX_CODE = 20000
MAX_LIST_DEPTH = 6
Align = Literal["left", "center", "right", "justify"]


class Run(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    code: bool = False
    sub: bool = False
    sup: bool = False
    highlight: bool = False
    color: TextColor | None = None
    link: str = ""

    @field_validator("link")
    @classmethod
    def _safe_link(cls, value: str) -> str:
        return safe_link(value)


def safe_link(value: str) -> str:
    """A link the document may carry; raise ``ValueError`` in German otherwise."""
    link = value.strip()
    if link and (
        not link.lower().startswith(LINK_SCHEMES)
        or len(link) > MAX_LINK
        or any(c.isspace() or ord(c) < 32 for c in link)  # noqa: PLR2004
    ):
        raise ValueError(BAD_LINK)
    return link


Inline = list[Run]


class _Block(BaseModel):
    block_id: str = Field(default_factory=_new_block_id)


class Paragraph(_Block):
    type: Literal["paragraph"] = "paragraph"
    runs: Inline = Field(default_factory=list)
    align: Align = "left"


class Heading(_Block):
    type: Literal["heading"] = "heading"
    level: Literal[3, 4] = 3
    runs: Inline = Field(default_factory=list)
    align: Align = "left"


class ListItem(BaseModel):
    """One entry of a list; ``children`` are the lists nested below it."""

    runs: Inline = Field(default_factory=list)
    checked: bool = False
    children: list[ListBlock] = Field(default_factory=list)


class _List(_Block):
    items: list[ListItem] = Field(default_factory=list)

    @field_validator("items", mode="before")
    @classmethod
    def _plain_items(cls, items: object) -> object:
        """Stored lists from before nesting hold the runs of each item directly."""
        if not isinstance(items, list):
            return items
        return [{"runs": item} if isinstance(item, list) else item for item in items]


class BulletList(_List):
    type: Literal["bullet_list"] = "bullet_list"


class OrderedList(_List):
    type: Literal["ordered_list"] = "ordered_list"


class TaskList(_List):
    type: Literal["task_list"] = "task_list"


ListBlock = Annotated[BulletList | OrderedList | TaskList, Field(discriminator="type")]
ListItem.model_rebuild()


class Quote(_Block):
    type: Literal["quote"] = "quote"
    paragraphs: list[Inline] = Field(default_factory=list)


class CodeBlock(_Block):
    type: Literal["code_block"] = "code_block"
    text: str = Field(default="", max_length=MAX_CODE)
    language: str = Field(default="", max_length=30, pattern=r"^[a-z0-9+#-]*$")


class Rule(_Block):
    type: Literal["rule"] = "rule"


class TableBlock(_Block):
    type: Literal["table"] = "table"
    header: list[Inline] = Field(min_length=1)
    rows: list[list[Inline]] = Field(default_factory=list)

    @field_validator("rows")
    @classmethod
    def _rows_match_header(
        cls, rows: list[list[Inline]], info: ValidationInfo
    ) -> list[list[Inline]]:
        _check_row_width(rows, len(info.data.get("header", [])), "die Kopfzeile")
        return rows


def _check_bound_field(value: str) -> str:
    if value not in BOUND_FIELDS:
        raise ValueError(f"Unbekannter Kalkulationswert: {value}")
    return value


BoundFieldName = Annotated[str, AfterValidator(_check_bound_field)]


def _check_row_width(rows: list[list[Inline]], width: int, what: str) -> None:
    if any(len(row) != width for row in rows):
        raise ValueError(
            f"Jede Tabellenzeile braucht genau so viele Zellen wie {what}."
        )


class BoundValue(_Block):
    type: Literal["bound_value"] = "bound_value"
    field: BoundFieldName


ProseBlock = Annotated[
    Paragraph
    | Heading
    | BulletList
    | OrderedList
    | TaskList
    | Quote
    | CodeBlock
    | Rule
    | TableBlock
    | BoundValue,
    Field(discriminator="type"),
]
# The blocks the text editor shows and writes.
EDITOR_BLOCKS = (
    Paragraph,
    Heading,
    BulletList,
    OrderedList,
    TaskList,
    Quote,
    CodeBlock,
    Rule,
)


class ProseContent(BaseModel):
    chapter_type: Literal["prose"] = "prose"
    blocks: list[ProseBlock] = Field(default_factory=list)


class TableContent(BaseModel):
    chapter_type: Literal["table"] = "table"
    columns: list[str] = Field(min_length=1)
    rows: list[list[Inline]] = Field(default_factory=list, max_length=MAX_TABLE_ROWS)
    # The optional caption below the table; table chapters have no heading.
    description: Inline = Field(default_factory=list)

    @field_validator("rows")
    @classmethod
    def _rows_match_columns(
        cls, rows: list[list[Inline]], info: ValidationInfo
    ) -> list[list[Inline]]:
        _check_row_width(rows, len(info.data.get("columns", [])), "Spalten")
        return rows


class StoriesContent(BaseModel):
    """Settings only; the live stories of the map, resolved at render time.

    Empty filters mean all stories. ``unsliced`` adds the stories without a
    slice to a slice filter. Stored content from before may still carry
    ``scopes``; it is ignored.
    """

    chapter_type: Literal["stories"] = "stories"
    group_by: Literal["activity", "slice"] = "activity"
    activity_ids: list[int] = Field(default_factory=list, max_length=200)
    slice_ids: list[int] = Field(default_factory=list, max_length=200)
    unsliced: bool = False

    def shows(self, activity_id: int, slice_id: int) -> bool:
        """Whether a story of this column and slice (0 = none) passes the filter."""
        if self.activity_ids and activity_id not in self.activity_ids:
            return False
        if not self.slice_ids and not self.unsliced:
            return True
        return slice_id in self.slice_ids or (self.unsliced and not slice_id)


class ImageContent(BaseModel):
    """An uploaded picture with alt text and an optional caption, no heading."""

    chapter_type: Literal["image"] = "image"
    blob_id: int | None = None
    alt: str = Field(default="", max_length=MAX_ALT)
    description: Inline = Field(default_factory=list)
    width: int = Field(default=MAX_IMAGE_WIDTH, ge=MIN_IMAGE_WIDTH, le=MAX_IMAGE_WIDTH)
    align: Literal["left", "center", "right"] = "center"


class CalcRow(BaseModel):
    label: str
    field: BoundFieldName


class CalcContent(BaseModel):
    chapter_type: Literal["calc"] = "calc"
    intro: Inline = Field(default_factory=list)
    rows: list[CalcRow] = Field(default_factory=list)


AnyContent = ProseContent | TableContent | StoriesContent | CalcContent | ImageContent
ChapterContent = Annotated[AnyContent, Field(discriminator="chapter_type")]

_CONTENT_ADAPTER: TypeAdapter[AnyContent] = TypeAdapter(ChapterContent)


def plain_text(runs: Inline) -> str:
    return "".join(run.text for run in runs)


def list_depth(block: BulletList | OrderedList | TaskList) -> int:
    """How deep the lists of ``block`` nest; a flat list has depth 1."""
    return 1 + max(
        (list_depth(child) for item in block.items for child in item.children),
        default=0,
    )


def parse_content(data: dict) -> AnyContent:
    """Validate raw JSON content; raise ``ContentValidationError`` in German."""
    try:
        return _CONTENT_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ContentValidationError([_german(err) for err in exc.errors()]) from exc


def _german(error: ErrorDetails) -> str:
    message = str(error.get("msg", ""))
    if message.startswith("Value error, "):
        return message.removeprefix("Value error, ")
    location = ".".join(str(part) for part in error.get("loc", ()))
    if error.get("type") == "union_tag_invalid":
        if error.get("loc") == ():
            return "Unbekannter Kapiteltyp."
        return f"Nicht unterstützter Inhaltsbaustein ({location})."
    return f"Ungültiger Inhalt ({location})."
