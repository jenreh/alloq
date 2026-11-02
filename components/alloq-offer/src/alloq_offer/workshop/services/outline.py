"""The outline of an offer: add, remove, restore, move, rename and re-level chapters.

The fixed frame of the Word layout is not part of the outline, so it can never
move. Required chapters can move but not go; removed chapters keep their
revisions, findings and proposals and can come back. Word numbers the chapter
headings through its heading styles, so the first chapter always has level 1.

A main chapter and its sub chapters form a group that moves as one. Table and
image chapters are attached: always level 2, no heading, never first.
"""

import logging
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.repository import german_sort_key
from alloq_offer.workshop.content.schema import ATTACHED_TYPES
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
NEEDS_PARENT = (
    "Tabellen und Bilder stehen immer unter einem Kapitel und nie an erster Stelle."
)
TOO_MANY = "Ein Angebot hat höchstens 100 Kapitel."
RESTORED = "Das Kapitel wurde wiederhergestellt. Bitte prüfen Sie den Stand."
# The start content of a blank chapter per type.
BLANK_CONTENT: dict[str, dict[str, Any]] = {
    "prose": {},
    "table": {"columns": ["Punkt", "Beschreibung"]},
    "stories": {},
    "calc": {},
    "image": {},
}
LEVELS = (1, 2)
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _title(text: str, *, optional: bool = False) -> str:
    title = text.strip()
    if not title and optional:
        return ""
    if not title or len(title) > MAX_TITLE or CONTROL_CHARACTERS.search(title):
        raise ChapterError(TITLE_NEEDED)
    return title


def _attached(chapter: ChapterEntity) -> bool:
    return chapter.chapter_type in ATTACHED_TYPES


def _is_main(chapter: ChapterEntity) -> bool:
    return chapter.level == 1 and not _attached(chapter)


def _units(
    chapters: list[ChapterEntity], starts: Callable[[ChapterEntity], bool]
) -> list[list[ChapterEntity]]:
    """Consecutive runs of chapters; a new run begins where ``starts`` holds."""
    units: list[list[ChapterEntity]] = []
    for chapter in chapters:
        if starts(chapter) or not units:
            units.append([chapter])
        else:
            units[-1].append(chapter)
    return units


def _unit_rule(chapter: ChapterEntity) -> Callable[[ChapterEntity], bool]:
    """A main chapter moves with its sub chapters, a sub chapter with its
    attached tables and images, an attached chapter alone."""
    if _attached(chapter):
        return lambda _: True
    if chapter.level == 1:
        return _is_main
    return lambda c: not _attached(c)


def _group(chapters: list[ChapterEntity], chapter: ChapterEntity) -> int:
    """Index after the last chapter that moves with ``chapter``."""
    start = chapters.index(chapter)
    starts = _unit_rule(chapter)
    end = start + 1
    while end < len(chapters) and not starts(chapters[end]):
        end += 1
    return end


def _renumber(chapters: list[ChapterEntity]) -> None:
    """Dense positions; a chapter that moved to the top becomes level 1.

    Attached chapters need a chapter before them. One that is already first
    (stored before this rule) stays, so the outline can still change.
    """
    if chapters and _attached(chapters[0]) and chapters[0].position != 0:
        raise ChapterError(NEEDS_PARENT)
    for position, chapter in enumerate(chapters):
        chapter.position = position
        if _attached(chapter):
            chapter.level = 2
    if chapters and not _attached(chapters[0]):
        chapters[0].level = 1


async def removed_chapters(
    session: AsyncSession, offer_id: int
) -> list[dict[str, str]]:
    """Removed chapters, last removed first."""
    rows = (
        await session.scalars(
            select(ChapterEntity)
            .where(
                ChapterEntity.offer_id == offer_id,
                ChapterEntity.removed_at.is_not(None),
            )
            .order_by(ChapterEntity.removed_at.desc(), ChapterEntity.id)
        )
    ).all()
    return [{"key": row.chapter_key, "title": row.title} for row in rows]


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
            return await removed_chapters(session, self._offer_id)

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
            attached = block.chapter_type in ATTACHED_TYPES
            definition = ChapterDef.model_validate(
                {
                    **block.to_dict(),
                    "key": key,
                    "title": _title(title.strip() or block.title, optional=attached),
                }
            )
        except ValidationError as exc:
            logger.warning("Chapter block %s is invalid", block_key)
            raise ChapterError(NO_BLOCK) from exc
        return definition.model_copy(update={"level": 2}) if attached else definition

    @staticmethod
    def _blank_definition(
        key: str, chapter_type: str, title: str, level: int
    ) -> ChapterDef:
        if chapter_type not in BLANK_CONTENT:
            raise ChapterError(UNKNOWN_TYPE)
        attached = chapter_type in ATTACHED_TYPES
        return ChapterDef(
            key=key,
            title=_title(title, optional=attached),
            level=2 if attached else level,
            chapter_type=chapter_type,
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

        It goes after ``after_key``, first for ``""``, or last without one;
        returns the new key. A blank chapter joins the level of the chapter it
        follows.
        """

        def place(chapters: list[ChapterEntity]) -> tuple[int, int | None]:
            if after_key == "":
                return 0, 1
            keys = [c.chapter_key for c in chapters]
            if after_key is not None and after_key not in keys:
                raise ChapterError(NOT_FOUND)
            index = len(chapters) if after_key is None else keys.index(after_key) + 1
            if not index:
                return 0, 1
            # Right before a sub chapter, a new chapter is a sub chapter too, so
            # it does not take over the sub chapters of the one before it.
            follows = chapters[index] if index < len(chapters) else None
            before_sub = follows is not None and not _is_main(follows)
            return index, 2 if before_sub else chapters[index - 1].level

        return await self._add(place, block_key, chapter_type, title)

    async def add_subchapter(
        self, parent_key: str, *, chapter_type: str = "prose", title: str = ""
    ) -> str:
        """A blank level-2 chapter after the last sub chapter of ``parent_key``."""

        def place(chapters: list[ChapterEntity]) -> tuple[int, int | None]:
            parent = next((c for c in chapters if c.chapter_key == parent_key), None)
            if parent is None:
                raise ChapterError(NOT_FOUND)
            return _group(chapters, parent), 2

        return await self._add(place, None, chapter_type, title)

    async def _add(
        self,
        place: Callable[[list[ChapterEntity]], tuple[int, int | None]],
        block_key: str | None,
        chapter_type: str,
        title: str,
    ) -> str:
        # An older offer gets its template chapters before anything is added.
        await ChapterService(self._sessions, self._offer_id, self._user).open()
        async with self._sessions() as session:
            workspace = await self._workspace(session)
            chapters = await live_chapters(session, self._offer_id)
            if len(chapters) >= MAX_CHAPTERS:
                raise ChapterError(TOO_MANY)
            index, level = place(chapters)
            if index == 0 and chapter_type in ATTACHED_TYPES:
                raise ChapterError(NEEDS_PARENT)
            key = f"{NEW_KEY_PREFIX}{uuid.uuid4().hex[:8]}"
            definition = (
                await self._block_definition(session, key, block_key, title)
                if block_key is not None
                else self._blank_definition(key, chapter_type, title, level or 1)
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
        """Drop a chapter at ``new_index`` of the outline, its group with it.

        ``new_index`` is where the chapter alone would end up. A main chapter
        dropped inside another group lands after that group.
        """
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            chapters = await live_chapters(session, self._offer_id)
            start = chapters.index(chapter)
            end = _group(chapters, chapter)
            group, rest = chapters[start:end], chapters[:start] + chapters[end:]
            if start < new_index < end:
                return
            target = new_index - len(group) + 1 if new_index >= end else new_index
            target = max(0, min(target, len(rest)))
            starts = _unit_rule(chapter)
            while target < len(rest) and target and not starts(rest[target]):
                target += 1
            _renumber(rest[:target] + group + rest[target:])

    async def step_chapter(self, key: str, delta: int) -> None:
        """Swap a chapter's group with the neighbouring one ("Nach oben/unten")."""
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            units = _units(
                await live_chapters(session, self._offer_id), _unit_rule(chapter)
            )
            index = next(i for i, unit in enumerate(units) if unit[0] is chapter)
            other = index + (1 if delta > 0 else -1)
            if not 0 <= other < len(units):
                return
            units[index], units[other] = units[other], units[index]
            _renumber([c for unit in units for c in unit])

    async def rename_chapter(self, key: str, title: str) -> None:
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            chapter.title = _title(title, optional=_attached(chapter))

    async def set_level(self, key: str, level: int) -> None:
        if level not in LEVELS:
            raise ChapterError(BAD_LEVEL)
        async with self._sessions() as session:
            chapter = await self._chapter(session, key)
            if _attached(chapter):
                if level == 1:
                    raise ChapterError(NEEDS_PARENT)
                return
            if level != 1 and chapter.position == 0:
                raise ChapterError(FIRST_LEVEL)
            chapter.level = level

    async def indent(self, key: str) -> None:
        """Make a chapter a sub chapter of the one before it."""
        await self.set_level(key, 2)

    async def outdent(self, key: str) -> None:
        """Make a sub chapter a main chapter."""
        await self.set_level(key, 1)
