"""Typed chapter content model of the offer workshop.

A chapter holds one of four content types. ``prose`` is the canonical block
tree, ``table`` a plain grid, ``stories`` only settings (the text is resolved
from the story map when rendering) and ``calc`` bound commercial values.
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


class ContentValidationError(ValueError):
    """Chapter content violates the content model; messages are German."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages


def _new_block_id() -> str:
    return uuid.uuid4().hex[:8]


class Run(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False


Inline = list[Run]


class _Block(BaseModel):
    block_id: str = Field(default_factory=_new_block_id)


class Paragraph(_Block):
    type: Literal["paragraph"] = "paragraph"
    runs: Inline = Field(default_factory=list)


class Heading(_Block):
    type: Literal["heading"] = "heading"
    level: Literal[3, 4] = 3
    runs: Inline = Field(default_factory=list)


class BulletList(_Block):
    type: Literal["bullet_list"] = "bullet_list"
    items: list[Inline] = Field(default_factory=list)


class OrderedList(_Block):
    type: Literal["ordered_list"] = "ordered_list"
    items: list[Inline] = Field(default_factory=list)


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
    Paragraph | Heading | BulletList | OrderedList | TableBlock | BoundValue,
    Field(discriminator="type"),
]


class ProseContent(BaseModel):
    chapter_type: Literal["prose"] = "prose"
    blocks: list[ProseBlock] = Field(default_factory=list)


class TableContent(BaseModel):
    chapter_type: Literal["table"] = "table"
    columns: list[str] = Field(min_length=1)
    rows: list[list[Inline]] = Field(default_factory=list)

    @field_validator("rows")
    @classmethod
    def _rows_match_columns(
        cls, rows: list[list[Inline]], info: ValidationInfo
    ) -> list[list[Inline]]:
        _check_row_width(rows, len(info.data.get("columns", [])), "Spalten")
        return rows


class StoriesContent(BaseModel):
    """Settings only; all live stories of the map revision, resolved at render time.

    Stored content from before may still carry ``scopes``; it is ignored.
    """

    chapter_type: Literal["stories"] = "stories"
    group_by: Literal["activity", "slice"] = "activity"


class CalcRow(BaseModel):
    label: str
    field: BoundFieldName


class CalcContent(BaseModel):
    chapter_type: Literal["calc"] = "calc"
    intro: Inline = Field(default_factory=list)
    rows: list[CalcRow] = Field(default_factory=list)


ChapterContent = Annotated[
    ProseContent | TableContent | StoriesContent | CalcContent,
    Field(discriminator="chapter_type"),
]

_CONTENT_ADAPTER: TypeAdapter[
    ProseContent | TableContent | StoriesContent | CalcContent
] = TypeAdapter(ChapterContent)


def plain_text(runs: Inline) -> str:
    return "".join(run.text for run in runs)


def parse_content(
    data: dict,
) -> ProseContent | TableContent | StoriesContent | CalcContent:
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
