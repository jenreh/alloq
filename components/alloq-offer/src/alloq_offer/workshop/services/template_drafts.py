"""Template drafts in admin: outline, Word layout and publishing (spec 6.1).

The draft outline points at library blocks. Publishing copies the outline with
every block setting and the layout into a new immutable version; offers that
bound an older version are not touched.
"""

import asyncio
import io
import logging
import zipfile
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import BlobEntity
from alloq_offer.workshop.export.template_package import (
    SETTINGS_FIELDS,
    TemplateError,
    TemplatePackage,
    clean_layout,
    frame_headings,
)
from alloq_offer.workshop.services.exports import DOCX_MIME
from alloq_offer.workshop.storage import BlobStore, BlobTooLargeError
from alloq_offer.workshop.template_entities import (
    ChapterBlockEntity,
    OfferTemplateChapterEntity,
    OfferTemplateEntity,
    OfferTemplateVersionEntity,
)

logger = logging.getLogger(__name__)

MAX_TITLE = 255
# A layout unpacks to at most this much, so a crafted zip cannot exhaust memory;
# XML parts are parsed several times and get the tighter limit.
MAX_UNPACKED_BYTES = 100 * 1024 * 1024
MAX_XML_PART_BYTES = 10 * 1024 * 1024
MAX_PARTS = 2000
NOT_FOUND = "Diese Vorlage gibt es nicht."
NO_ENTRY = "Diesen Eintrag der Gliederung gibt es nicht."
NO_BLOCK = "Diesen aktiven Kapitelbaustein gibt es nicht."
BLOCK_IN_OUTLINE = "Der Baustein ist schon in der Gliederung."
NOT_DOCX = "Bitte laden Sie eine Word-Datei (.docx) hoch."
TOO_LARGE = "Die Datei ist zu groß."
NO_LAYOUT = "Bitte laden Sie zuerst ein Word-Layout hoch."
EMPTY_OUTLINE = "Die Gliederung braucht mindestens ein Kapitel."
TITLE_TOO_LONG = "Die Überschrift darf höchstens 255 Zeichen haben."
BAD_LEVEL = "Ein Kapitel hat die Ebene 1 oder 2."
INVALID_DRAFT = "Die Vorlage ist so nicht gültig. Bitte prüfen Sie die Bausteine."
UNCHANGED = "Seit Version {} hat sich an der Vorlage nichts geändert."


class DraftError(ValueError):
    """The draft cannot be changed or published; the message is German."""


async def list_templates(sessions: SessionFactory) -> list[dict[str, Any]]:
    async with sessions() as session:
        rows = (
            await session.execute(
                select(
                    OfferTemplateEntity,
                    func.max(OfferTemplateVersionEntity.number),
                )
                .outerjoin(OfferTemplateVersionEntity)
                .group_by(OfferTemplateEntity.id)
                .order_by(OfferTemplateEntity.name)
            )
        ).all()
    return [{**template.to_dict(), "latest": latest or 0} for template, latest in rows]


async def _template(session: AsyncSession, template_id: int) -> OfferTemplateEntity:
    template = await session.get(OfferTemplateEntity, template_id, with_for_update=True)
    if template is None:
        raise DraftError(NOT_FOUND)
    return template


async def _entries(
    session: AsyncSession, template_id: int
) -> list[tuple[OfferTemplateChapterEntity, ChapterBlockEntity]]:
    rows = await session.execute(
        select(OfferTemplateChapterEntity, ChapterBlockEntity)
        .join(ChapterBlockEntity)
        .where(OfferTemplateChapterEntity.template_id == template_id)
        .order_by(OfferTemplateChapterEntity.position, OfferTemplateChapterEntity.id)
    )
    return [(entry, block) for entry, block in rows.all()]


def _renumber(entries: list[OfferTemplateChapterEntity]) -> None:
    for position, entry in enumerate(entries):
        entry.position = position


async def load_outline(
    sessions: SessionFactory, template_id: int
) -> list[dict[str, Any]]:
    """The draft outline with the title and level each entry will publish."""
    async with sessions() as session:
        entries = await _entries(session, template_id)
    return [
        {
            "id": entry.id,
            "block_key": block.key,
            "block_title": block.title,
            "type": block.chapter_type,
            "title": entry.title or block.title,
            "title_override": entry.title or "",
            "level": entry.level or block.level,
            "level_override": entry.level or 0,
            "required": entry.required,
            "active": block.active,
        }
        for entry, block in entries
    ]


class TemplateDraft:
    """Changes to the draft of one template; each locks the template row."""

    def __init__(self, sessions: SessionFactory, template_id: int) -> None:
        self._sessions = sessions
        self._template_id = template_id

    async def _entry(
        self, session: AsyncSession, entry_id: int
    ) -> OfferTemplateChapterEntity:
        await _template(session, self._template_id)
        entry = await session.get(OfferTemplateChapterEntity, entry_id)
        if entry is None or entry.template_id != self._template_id:
            raise DraftError(NO_ENTRY)
        return entry

    async def add_block(self, block_key: str) -> None:
        async with self._sessions() as session:
            await _template(session, self._template_id)
            block = await session.scalar(
                select(ChapterBlockEntity).where(
                    ChapterBlockEntity.key == block_key, ChapterBlockEntity.active
                )
            )
            if block is None:
                raise DraftError(NO_BLOCK)
            entries = [entry for entry, _ in await _entries(session, self._template_id)]
            if any(entry.block_id == block.id for entry in entries):
                raise DraftError(BLOCK_IN_OUTLINE)
            session.add(
                OfferTemplateChapterEntity(
                    template_id=self._template_id,
                    block_id=block.id,
                    position=len(entries),
                    required=False,
                )
            )

    async def remove(self, entry_id: int) -> None:
        async with self._sessions() as session:
            entry = await self._entry(session, entry_id)
            await session.delete(entry)
            await session.flush()
            _renumber([e for e, _ in await _entries(session, self._template_id)])

    async def move(self, entry_id: int, index: int) -> None:
        async with self._sessions() as session:
            entry = await self._entry(session, entry_id)
            entries = [
                e
                for e, _ in await _entries(session, self._template_id)
                if e.id != entry.id
            ]
            entries.insert(max(0, min(index, len(entries))), entry)
            _renumber(entries)

    async def update(
        self,
        entry_id: int,
        *,
        required: bool | None = None,
        title: str | None = None,
        level: int | None = None,
    ) -> None:
        """Change only the given settings; ``""`` and ``0`` fall back to the block."""
        name = None if title is None else title.strip()
        if name is not None and len(name) > MAX_TITLE:
            raise DraftError(TITLE_TOO_LONG)
        if level not in (None, 0, 1, 2):
            raise DraftError(BAD_LEVEL)
        async with self._sessions() as session:
            entry = await self._entry(session, entry_id)
            if required is not None:
                entry.required = required
            if name is not None:
                entry.title = name or None
            if level is not None:
                entry.level = level or None

    async def upload_layout(self, store: BlobStore, filename: str, data: bytes) -> None:
        """Check, clean and keep a Word layout; its frame headings are read off it."""
        if not filename.lower().endswith(".docx"):
            raise DraftError(NOT_DOCX)
        async with self._sessions() as session:
            await _template(session, self._template_id)
        cleaned, before, after = await asyncio.to_thread(_cleaned_layout, data)
        try:
            blob_id = await store.put(cleaned, DOCX_MIME)
        except BlobTooLargeError as exc:
            raise DraftError(TOO_LARGE) from exc
        try:
            async with self._sessions() as session:
                template = await _template(session, self._template_id)
                old_blob_id = template.draft_layout_blob_id
                template.draft_layout_blob_id = blob_id
                template.frame_before = before
                template.frame_after = after
        except Exception:
            await store.delete(blob_id)
            raise
        if old_blob_id not in (None, blob_id) and not await self._published(
            old_blob_id
        ):
            await store.delete(old_blob_id)
        logger.info("Layout of template %s replaced", self._template_id)

    async def _published(self, blob_id: int) -> bool:
        async with self._sessions() as session:
            found = await session.scalar(
                select(OfferTemplateVersionEntity.id)
                .where(OfferTemplateVersionEntity.layout_blob_id == blob_id)
                .limit(1)
            )
        return found is not None

    async def publish(self, user: str) -> int:
        """Store the draft as the next immutable version; returns its number."""
        async with self._sessions() as session:
            template = await _template(session, self._template_id)
            if template.draft_layout_blob_id is None:
                raise DraftError(NO_LAYOUT)
            entries = await _entries(session, self._template_id)
            if not entries:
                raise DraftError(EMPTY_OUTLINE)
            layout = await session.scalar(
                select(BlobEntity.data).where(
                    BlobEntity.id == template.draft_layout_blob_id
                )
            )
            payload = {
                "chapters": [_resolved(entry, block) for entry, block in entries],
                "frame_before": list(template.frame_before),
                "frame_after": list(template.frame_after),
            }
            try:
                TemplatePackage.model_validate(
                    {
                        **payload,
                        "key": template.key,
                        "version": "0",
                        "layout_bytes": layout,
                    }
                )
            except (ValidationError, TemplateError) as exc:
                logger.warning(
                    "Template %s does not validate: %s", template.key, _problem(exc)
                )
                raise DraftError(INVALID_DRAFT) from exc
            latest = await session.scalar(
                select(OfferTemplateVersionEntity)
                .where(OfferTemplateVersionEntity.template_id == template.id)
                .order_by(OfferTemplateVersionEntity.number.desc())
                .limit(1)
            )
            if (
                latest is not None
                and latest.payload == payload
                and latest.layout_blob_id == template.draft_layout_blob_id
            ):
                raise DraftError(UNCHANGED.format(latest.number))
            number = (latest.number if latest else 0) + 1
            session.add(
                OfferTemplateVersionEntity(
                    template_id=template.id,
                    number=number,
                    payload=payload,
                    layout_blob_id=template.draft_layout_blob_id,
                    published_by=user,
                )
            )
        logger.info("Template %s published as version %s", self._template_id, number)
        return number


def _resolved(
    entry: OfferTemplateChapterEntity, block: ChapterBlockEntity
) -> dict[str, Any]:
    return {
        "key": block.key,
        "title": entry.title or block.title,
        "level": entry.level or block.level,
        "required": entry.required,
        "chapter_type": block.chapter_type,
        "default_content": block.default_content,
        **{name: getattr(block, name) for name in SETTINGS_FIELDS},
    }


def _problem(exc: ValidationError | TemplateError) -> str:
    """Where validation failed, without the input values (chapter texts)."""
    if isinstance(exc, ValidationError):
        return ", ".join(".".join(map(str, e["loc"])) for e in exc.errors())
    return str(exc)


def _check_zip(data: bytes) -> None:
    """Refuse files that are no zip or would unpack to too much."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise DraftError(NOT_DOCX) from exc
    too_big_xml = any(
        p.file_size > MAX_XML_PART_BYTES
        for p in parts
        if p.filename.endswith((".xml", ".rels"))
    )
    if (
        len(parts) > MAX_PARTS
        or too_big_xml
        or sum(p.file_size for p in parts) > MAX_UNPACKED_BYTES
    ):
        raise DraftError(TOO_LARGE)


def _cleaned_layout(data: bytes) -> tuple[bytes, list[str], list[str]]:
    """The checked and cleaned layout with its frame headings (CPU bound)."""
    _check_zip(data)
    try:
        cleaned = clean_layout(data)
        before, after = frame_headings(cleaned)
    except TemplateError as exc:
        raise DraftError(str(exc)) from exc
    return cleaned, before, after


async def list_versions(
    sessions: SessionFactory, template_id: int
) -> list[dict[str, Any]]:
    """Published versions, newest first."""
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(OfferTemplateVersionEntity)
                .where(OfferTemplateVersionEntity.template_id == template_id)
                .order_by(OfferTemplateVersionEntity.number.desc())
            )
        ).all()
    return [
        {
            "number": row.number,
            "published_by": row.published_by,
            "created": row.created.strftime("%d.%m.%Y %H:%M"),
            "chapters": len(row.payload.get("chapters", [])),
        }
        for row in rows
    ]
