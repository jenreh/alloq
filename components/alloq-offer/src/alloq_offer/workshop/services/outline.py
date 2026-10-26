"""The outline of an offer: add, remove, restore, move, rename and re-level chapters.

The fixed frame of the Word layout is not part of the outline, so it can never
move. Required chapters can move but not go; removed chapters keep their
revisions, findings and proposals and can come back. Word numbers the chapter
headings through its heading styles, so the first chapter always has level 1.
"""

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.repository import german_sort_key
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import ChapterEntity, WorkspaceEntity
from alloq_offer.workshop.export.template_package import ChapterDef
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapters import (
    NOT_FOUND,
    ChapterError,
    ChapterService,
    add_chapters,
    ensure_editable,
    ensure_open,
    find_chapter,
    live_chapters,
)
from alloq_offer.workshop.template_entities import ChapterBlockEntity

logger = logging.getLogger(__name__)

NEW_KEY_PREFIX = "custom_"
MAX_TITLE = 255
MAX_CHAPTERS = 100
REQUIRED = "Pflichtkapitel können nicht entfernt werden."
NO_BLOCK = "Diesen Kapitelbaustein gibt es nicht."
BLOCK_IN_USE = "Dieser Baustein ist schon Teil des Angebots."
TITLE_NEEDED = (
    "Bitte geben Sie eine Überschrift mit höchstens 255 Zeichen in einer Zeile an."
)
UNKNOWN_TYPE = "Diesen Kapiteltyp gibt es nicht."
BAD_LEVEL = "Ein Kapitel hat die Ebene 1 oder 2."
FIRST_LEVEL = "Das erste Kapitel hat immer die Ebene 1."
TOO_MANY = "Ein Angebot hat höchstens 100 Kapitel."
RESTORED = "Das Kapitel wurde wiederhergestellt. Bitte prüfen Sie den Stand."
# The start content of a blank chapter per type.
BLANK_CONTENT: dict[str, dict[str, Any]] = {
    "prose": {},
    "table": {"columns": ["Punkt", "Beschreibung"]},
    "stories": {},
    "calc": {},
}
LEVELS = (1, 2)
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _title(text: str) -> str:
    title = text.strip()
    if not title or len(title) > MAX_TITLE or CONTROL_CHARACTERS.search(title):
        raise ChapterError(TITLE_NEEDED)
    return title


def _renumber(chapters: list[ChapterEntity]) -> None:
    """Dense positions; a chapter that moved to the top becomes level 1."""
    for position, chapter in enumerate(chapters):
        chapter.position = position
    if chapters:
        chapters[0].level = 1


class OutlineService:
    """Outline changes of one offer; each serialises on the workspace row."""

    def __init__(self, sessions: SessionFactory, offer_id: int, user: str) -> None:
        self._sessions = sessions
        self._offer_id = offer_id
        self._user = user

    async def _workspace(self, session: AsyncSession) -> WorkspaceEntity:
        workspace = await workspace_repo.find_by_offer(session, self._offer_id)
        if workspace is None:
            raise ChapterError(NOT_FOUND)
        await session.refresh(workspace, with_for_update=True)
        await ensure_open(session, self._offer_id)
        return workspace

    async def _chapter(self, session: AsyncSession, key: str) -> ChapterEntity:
        await self._workspace(session)
        chapter = await find_chapter(session, self._offer_id, key, lock=True)
        return ensure_editable(chapter)

    async def _used_blocks(self, session: AsyncSession) -> set[str]:
        """Blocks of the offer, removed chapters too: those come back by restore."""
        keys = await session.scalars(
            select(ChapterEntity.block_key).where(
                ChapterEntity.offer_id == self._offer_id,
                ChapterEntity.block_key.is_not(None),
            )
        )
        return {key for key in keys.all() if key}

    async def library(self) -> list[dict[str, Any]]:
        """Active blocks the offer does not use yet, by title."""
        async with self._sessions() as session:
            used = await self._used_blocks(session)
            blocks = (
                await session.scalars(
                    select(ChapterBlockEntity).where(ChapterBlockEntity.active)
                )
            ).all()
        return [
            {
                "key": block.key,
                "title": block.title,
                "type": block.chapter_type,
                "description": block.guiding_question,
            }
            for block in sorted(blocks, key=lambda b: german_sort_key(b.title))
            if block.key not in used
        ]

    async def removed(self) -> list[dict[str, str]]:
        """Removed chapters, last removed first."""
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(ChapterEntity)
                    .where(
                        ChapterEntity.offer_id == self._offer_id,
                        ChapterEntity.removed_at.is_not(None),
                    )
                    .order_by(ChapterEntity.removed_at.desc(), ChapterEntity.id)
                )
            ).all()
        return [{"key": row.chapter_key, "title": row.title} for row in rows]

    async def _block_definition(
        self, session: AsyncSession, key: str, block_key: str, title: str
    ) -> ChapterDef:
        block = await session.scalar(
            select(ChapterBlockEntity).where(
                ChapterBlockEntity.key == block_key, ChapterBlockEntity.active
            )
        )
        if block is None:
            raise ChapterError(NO_BLOCK)
        if block_key in await self._used_blocks(session):
            raise ChapterError(BLOCK_IN_USE)
        try:
            return ChapterDef.model_validate(
                {
                    **block.to_dict(),
                    "key": key,
                    "title": _title(title.strip() or block.title),
                }
            )
        except ValidationError as exc:
            logger.warning("Chapter block %s is invalid", block_key)
            raise ChapterError(NO_BLOCK) from exc

    @staticmethod
    def _blank_definition(
        key: str, chapter_type: str, title: str, level: int
    ) -> ChapterDef:
        if chapter_type not in BLANK_CONTENT:
            raise ChapterError(UNKNOWN_TYPE)
        return ChapterDef(
            key=key,
            title=_title(title),
            level=level,  # ty: ignore[invalid-argument-type]
            chapter_type=chapter_type,  # ty: ignore[invalid-argument-type]
            default_content=BLANK_CONTENT[chapter_type],
        )

    async def add_chapter(
        self,
        after_key: str | None,
        *,
        block_key: str | None = None,
        chapter_type: str = "",
        title: str = "",
    ) -> str:
        """Insert a library block, or else a blank chapter of ``chapter_type``.

        It goes after ``after_key``, or last without one; returns the new key.
        """
        # An older offer gets its template chapters before anything is added.
        await ChapterService(self._sessions, self._offer_id, self._user).open()
        async with self._sessions() as session:
            workspace = await self._workspace(session)
            chapters = await live_chapters(session, self._offer_id)
            if len(chapters) >= MAX_CHAPTERS:
                raise ChapterError(TOO_MANY)
            keys = [c.chapter_key for c in chapters]
            if after_key is not None and after_key not in keys:
                raise ChapterError(NOT_FOUND)
            index = len(chapters) if after_key is None else keys.index(after_key) + 1
            key = f"{NEW_KEY_PREFIX}{uuid.uuid4().hex[:8]}"
            # A blank chapter joins the level of the chapter it follows.
            level = chapters[index - 1].level if index else 1
            definition = (
                await self._block_definition(session, key, block_key, title)
                if block_key is not None
                else self._blank_definition(key, chapter_type, title, level)
            )
            [chapter] = await add_chapters(
                session,
                self._offer_id,
                [(definition, block_key)],
                workspace.map_revision,
            )
            chapters.insert(index, chapter)
            _renumber(chapters)
        logger.info("Chapter %s added to offer %s", key, self._offer_id)
        return key

    async def remove_chapter(self, key: str) -> None:
        """Take a chapter out of the outline; required chapters stay."""
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            if chapter.required:
                raise ChapterError(REQUIRED)
            chapter.removed_at = datetime.now(UTC)
            _renumber(await live_chapters(session, self._offer_id))
        logger.info("Chapter %s of offer %s removed", key, self._offer_id)

    async def restore_chapter(self, key: str) -> None:
        """Bring a removed chapter back at the end of the outline.

        Its text may have missed map changes meanwhile, so a written text chapter
        asks for a new look.
        """
        async with self._sessions() as session:
            await self._workspace(session)
            chapter = await find_chapter(
                session, self._offer_id, key, lock=True, removed=True
            )
            chapters = await live_chapters(session, self._offer_id)
            if len(chapters) >= MAX_CHAPTERS:
                raise ChapterError(TOO_MANY)
            chapter.removed_at = None
            if chapter.chapter_type == "prose" and chapter.revision > 1:
                chapter.needs_review = True
                chapter.review_reason = RESTORED
            _renumber([*chapters, chapter])
        logger.info("Chapter %s of offer %s restored", key, self._offer_id)

    async def move_chapter(self, key: str, new_index: int) -> None:
        """Put a chapter at ``new_index`` of the outline; positions stay dense."""
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            chapters = [
                c
                for c in await live_chapters(session, self._offer_id)
                if c.id != chapter.id
            ]
            chapters.insert(max(0, min(new_index, len(chapters))), chapter)
            _renumber(chapters)

    async def rename_chapter(self, key: str, title: str) -> None:
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            chapter.title = _title(title)

    async def set_level(self, key: str, level: int) -> None:
        if level not in LEVELS:
            raise ChapterError(BAD_LEVEL)
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            if level != 1 and chapter.position == 0:
                raise ChapterError(FIRST_LEVEL)
            chapter.level = level
