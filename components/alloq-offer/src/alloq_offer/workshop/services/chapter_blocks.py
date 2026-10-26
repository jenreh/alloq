"""The chapter library: reusable blocks with start content, AI settings and checks.

A block in use by a template draft is deactivated instead of deleted; offers
and published versions keep their own copies of its settings.
"""

import logging
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from alloq_offer.repository import german_sort_key
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.export.template_package import ChapterDef, ChapterType
from alloq_offer.workshop.services.checks import CHAPTER_CHECKS
from alloq_offer.workshop.template_entities import (
    ChapterBlockEntity,
    OfferTemplateChapterEntity,
    OfferTemplateEntity,
)

logger = logging.getLogger(__name__)

KEY_PATTERN = r"^[a-z][a-z0-9_]{1,49}$"
MAX_ITEMS = 20
NOT_FOUND = "Diesen Kapitelbaustein gibt es nicht."
DUPLICATE = "Diesen Schlüssel gibt es schon."
IN_USE = (
    "Der Baustein wird in einer Vorlage verwendet. Deaktivieren Sie ihn stattdessen."
)
FIELD_LABELS = {
    "key": "Schlüssel (Kleinbuchstaben, Ziffern und _, 2 bis 50 Zeichen)",
    "title": "Titel (höchstens 255 Zeichen)",
    "chapter_type": "Kapiteltyp",
    "level": "Ebene",
    "default_content": "Startinhalt",
    "guiding_question": "Leitfrage (höchstens 2000 Zeichen)",
    "content_rules": "Regeln (höchstens 20, je 500 Zeichen)",
    "prompt_text": "Prompt-Ergänzung (höchstens 4000 Zeichen)",
    "required_info": "Pflichtangaben (höchstens 20, je 200 Zeichen)",
    "checks": "Prüfungen",
}

Rule = Annotated[str, Field(max_length=500)]
Info = Annotated[str, Field(max_length=200)]


class BlockError(ValueError):
    """The block cannot be stored; the message is German and shown to admins."""


class BlockInput(BaseModel):
    """What an admin enters for a block."""

    model_config = ConfigDict(str_strip_whitespace=True)

    key: str = Field(pattern=KEY_PATTERN)
    title: str = Field(min_length=1, max_length=255)
    chapter_type: ChapterType
    level: Literal[1, 2] = 1
    default_content: dict[str, Any] = Field(default_factory=dict)
    guiding_question: str = Field(default="", max_length=2000)
    content_rules: list[Rule] = Field(default_factory=list, max_length=MAX_ITEMS)
    prompt_text: str = Field(default="", max_length=4000)
    required_info: list[Info] = Field(default_factory=list, max_length=MAX_ITEMS)
    checks: list[str] = Field(default_factory=list)
    active: bool = True

    @field_validator("content_rules", "required_info", mode="before")
    @classmethod
    def _no_empty_items(cls, value: object) -> object:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("checks")
    @classmethod
    def _known_checks(cls, value: list[str]) -> list[str]:
        if not set(value) <= set(CHAPTER_CHECKS):
            raise ValueError("unknown check")
        return list(dict.fromkeys(value))


def parse_block(data: dict[str, Any]) -> BlockInput:
    """Validate admin input; the content must fit the chapter type."""
    try:
        block = BlockInput.model_validate(data)
        ChapterDef.model_validate(block.model_dump())
    except ValidationError as exc:
        field = str(exc.errors()[0]["loc"][0]) if exc.errors()[0]["loc"] else ""
        label = FIELD_LABELS.get(field, FIELD_LABELS["default_content"])
        raise BlockError(f"Bitte prüfen Sie: {label}.") from exc
    return block


def _row(block: ChapterBlockEntity, used_in: list[str]) -> dict[str, Any]:
    return {**block.to_dict(), "used_in": used_in}


async def list_blocks(sessions: SessionFactory) -> list[dict[str, Any]]:
    """All blocks by title, each with the templates whose draft uses it."""
    async with sessions() as session:
        blocks = (await session.scalars(select(ChapterBlockEntity))).all()
        usage = (
            await session.execute(
                select(OfferTemplateChapterEntity.block_id, OfferTemplateEntity.name)
                .join(OfferTemplateEntity)
                .order_by(OfferTemplateEntity.name)
            )
        ).all()
    used: dict[int, list[str]] = {}
    for block_id, name in usage:
        used.setdefault(block_id, []).append(name)
    return [
        _row(block, used.get(block.id, []))
        for block in sorted(blocks, key=lambda b: german_sort_key(b.title))
    ]


async def save_block(
    sessions: SessionFactory, block: BlockInput, *, create: bool
) -> None:
    """Create a block or change one; the key of a block never changes."""
    values = block.model_dump()
    try:
        async with sessions() as session:
            if create:
                session.add(ChapterBlockEntity(**values))
                await session.flush()
            else:
                row = await session.scalar(
                    select(ChapterBlockEntity).where(
                        ChapterBlockEntity.key == block.key
                    )
                )
                if row is None:
                    raise BlockError(NOT_FOUND)
                for name, value in values.items():
                    setattr(row, name, value)
    except IntegrityError as exc:
        raise BlockError(DUPLICATE) from exc
    logger.info("Chapter block %s %s", block.key, "created" if create else "changed")


async def delete_block(sessions: SessionFactory, key: str) -> None:
    """Delete an unused block; a block in a template draft stays."""
    try:
        async with sessions() as session:
            row = await session.scalar(
                select(ChapterBlockEntity).where(ChapterBlockEntity.key == key)
            )
            if row is None:
                raise BlockError(NOT_FOUND)
            used = await session.scalar(
                select(OfferTemplateChapterEntity.id)
                .where(OfferTemplateChapterEntity.block_id == row.id)
                .limit(1)
            )
            if used is not None:
                raise BlockError(IN_USE)
            await session.delete(row)
    except IntegrityError as exc:  # added to a draft meanwhile
        raise BlockError(IN_USE) from exc
    logger.info("Chapter block %s deleted", key)
