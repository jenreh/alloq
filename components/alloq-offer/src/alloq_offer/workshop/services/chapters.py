"""Chapters of an offer: revisions, conflicts and AI proposals (spec 5.5, 10.2-10.4).

A chapter's text lives in immutable revisions. A save names the revision the person
saw; if somebody saved in between, nothing is overwritten (A08). AI texts only ever
arrive as proposals that a person accepts.
"""

import logging
from typing import Any

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.content.schema import ProseContent, parse_content
from alloq_offer.workshop.content.text import Content, diff_lines, stored_lines
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    ChapterEntity,
    ChapterOrigin,
    ChapterRevisionEntity,
    FindingDecision,
    FindingEntity,
    ProposalEntity,
    ProposalStatus,
    WorkspaceEntity,
)
from alloq_offer.workshop.export.template_package import (
    ChapterDef,
    ChapterSettings,
    TemplatePackage,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.templates import load_template

logger = logging.getLogger(__name__)

CONFLICT = (
    "Das Kapitel wurde inzwischen geändert. Die aktuelle Fassung wurde geladen, "
    "bitte wiederholen Sie die Änderung."
)
NOT_FOUND = "Das Kapitel gibt es nicht."
PROTECTED = "Das Kapitel ist geschützt. Heben Sie den Schutz auf, um es zu ändern."
WRONG_TYPE = "Dieser Inhalt passt nicht zum Typ des Kapitels."
NO_PROPOSAL = "Der Vorschlag gibt es nicht mehr."
STALE_PROPOSAL = (
    "Der Vorschlag ist veraltet, weil das Kapitel inzwischen geändert wurde."
)
REVIEW_AFTER_MAP = "Die Story Map hat sich seit dem Verfassen geändert."
NO_REVISION = "Diese Fassung gibt es nicht."


class ChapterConflictError(RuntimeError):
    """Somebody saved the chapter since this editor loaded it (A08)."""


class ChapterError(ValueError):
    """The change is not allowed; the message is German and shown to users."""


def settings_of(chapter: ChapterEntity) -> ChapterSettings:
    return ChapterSettings.model_validate(chapter.settings)


async def live_chapters(session: AsyncSession, offer_id: int) -> list[ChapterEntity]:
    """The chapters of the offer's outline in order; removed ones are left out."""
    rows = await session.scalars(
        select(ChapterEntity)
        .where(ChapterEntity.offer_id == offer_id, ChapterEntity.removed_at.is_(None))
        .order_by(ChapterEntity.position, ChapterEntity.id)
    )
    return list(rows.all())


async def create_chapters(
    session: AsyncSession, offer_id: int, template: TemplatePackage, map_revision: int
) -> None:
    """Copy the template outline into the offer, each with its start content."""
    await add_chapters(
        session,
        offer_id,
        [(definition, definition.key) for definition in template.chapters],
        map_revision,
    )


async def add_chapters(
    session: AsyncSession,
    offer_id: int,
    entries: list[tuple[ChapterDef, str | None]],
    map_revision: int,
    first_position: int = 0,
) -> list[ChapterEntity]:
    """New chapters from definitions and their origin block, starting at revision 1."""
    chapters = [
        ChapterEntity(
            offer_id=offer_id,
            chapter_key=definition.key,
            revision=0,
            position=first_position + index,
            title=definition.title,
            chapter_type=definition.chapter_type,
            level=definition.level,
            required=definition.required,
            block_key=block_key,
            settings=definition.settings().model_dump(),
        )
        for index, (definition, block_key) in enumerate(entries)
    ]
    session.add_all(chapters)
    await session.flush()
    for chapter, (definition, _) in zip(chapters, entries, strict=True):
        _add_revision(
            session,
            chapter,
            definition.content(),
            origin=ChapterOrigin.TEMPLATE,
            author="",
            map_revision=map_revision,
        )
    return chapters


async def mark_chapters_review(
    session: AsyncSession, offer_id: int, keys: list[str], reason: str
) -> None:
    """Flag the chapters with ``keys`` for a new look."""
    if not keys:
        return
    await session.execute(
        update(ChapterEntity)
        .where(
            ChapterEntity.offer_id == offer_id,
            ChapterEntity.chapter_key.in_(keys),
            ChapterEntity.removed_at.is_(None),
        )
        .values(needs_review=True, review_reason=reason)
    )


async def mark_dependent_review(
    session: AsyncSession, workspace: WorkspaceEntity, reason: str = REVIEW_AFTER_MAP
) -> None:
    """Flag written prose chapters after a map change (A09, A27).

    Chapters that still hold the template text have nothing to review, and
    projections (stories, calc) follow the map by themselves.
    """
    await session.execute(
        update(ChapterEntity)
        .where(
            ChapterEntity.offer_id == workspace.offer_id,
            ChapterEntity.chapter_type == "prose",
            ChapterEntity.revision > 1,
            ChapterEntity.removed_at.is_(None),
        )
        .values(needs_review=True, review_reason=reason)
    )


async def find_chapter(
    session: AsyncSession, offer_id: int, key: str, *, lock: bool = False
) -> ChapterEntity:
    query = select(ChapterEntity).where(
        ChapterEntity.offer_id == offer_id,
        ChapterEntity.chapter_key == key,
        ChapterEntity.removed_at.is_(None),
    )
    chapter = await session.scalar(query.with_for_update() if lock else query)
    if chapter is None:
        raise ChapterError(NOT_FOUND)
    return chapter


async def revision_of(
    session: AsyncSession, chapter: ChapterEntity, number: int | None = None
) -> ChapterRevisionEntity:
    revision = await session.scalar(
        select(ChapterRevisionEntity).where(
            ChapterRevisionEntity.chapter_id == chapter.id,
            ChapterRevisionEntity.number == (number or chapter.revision),
        )
    )
    if revision is None:
        raise ChapterError(NO_REVISION)
    return revision


def _without_block_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_block_ids(v) for k, v in value.items() if k != "block_id"}
    if isinstance(value, list):
        return [_without_block_ids(v) for v in value]
    return value


def _unchanged(stored: dict, content: Content) -> bool:
    """The editor re-sends its text on mount; that is no new revision."""
    return _without_block_ids(stored) == _without_block_ids(
        content.model_dump(mode="json")
    )


async def current_revisions(
    session: AsyncSession, chapters: list[ChapterEntity]
) -> dict[int, ChapterRevisionEntity]:
    """The current revision of every chapter in one query, keyed by chapter id."""
    if not chapters:
        return {}
    rows = await session.scalars(
        select(ChapterRevisionEntity).where(
            tuple_(ChapterRevisionEntity.chapter_id, ChapterRevisionEntity.number).in_(
                [(c.id, c.revision) for c in chapters]
            )
        )
    )
    return {row.chapter_id: row for row in rows.all()}


async def reopen_accepted(session: AsyncSession, offer_id: int, key: str) -> None:
    """A changed text voids earlier decisions on its findings (spec 11.4, A15)."""
    await session.execute(
        update(FindingEntity)
        .where(
            FindingEntity.offer_id == offer_id,
            FindingEntity.target == f"chapter:{key}",
            FindingEntity.decision == FindingDecision.ACCEPTED,
        )
        .values(
            decision=FindingDecision.OPEN, reason="", decided_by="", decided_at=None
        )
    )


def _add_revision(
    session: AsyncSession,
    chapter: ChapterEntity,
    content: Content,
    *,
    origin: ChapterOrigin,
    author: str,
    map_revision: int,
) -> int:
    chapter.revision += 1
    chapter.needs_review = False
    chapter.review_reason = ""
    session.add(
        ChapterRevisionEntity(
            chapter_id=chapter.id,
            number=chapter.revision,
            content=content.model_dump(mode="json"),
            map_revision=map_revision,
            origin=origin,
            author=author,
        )
    )
    return chapter.revision


class ChapterService:
    """The chapters of one offer as one person works on them."""

    def __init__(self, sessions: SessionFactory, offer_id: int, user: str) -> None:
        self._sessions = sessions
        self._offer_id = offer_id
        self._user = user

    async def _locked(
        self, session: AsyncSession, key: str, expected: int | None
    ) -> tuple[ChapterEntity, WorkspaceEntity]:
        workspace = await workspace_repo.find_by_offer(session, self._offer_id)
        if workspace is None:
            raise ChapterError(NOT_FOUND)
        chapter = await find_chapter(session, self._offer_id, key, lock=True)
        if expected is not None and chapter.revision != expected:
            raise ChapterConflictError(CONFLICT)
        return chapter, workspace

    async def open(self) -> list[dict[str, Any]]:
        """The outline in order; an offer without chapters gets them first."""
        async with self._sessions() as session:
            workspace = await workspace_repo.find_by_offer(session, self._offer_id)
            if workspace is None:
                return []
            chapters = await live_chapters(session, self._offer_id)
            if not chapters and not await self._has_chapters(session):
                # Only creating chapters needs the lock that serialises with map edits.
                await session.refresh(workspace, with_for_update=True)
                if not await self._has_chapters(session):
                    template = await load_template(
                        session, workspace.template_key, workspace.template_version
                    )
                    await create_chapters(
                        session, self._offer_id, template, workspace.map_revision
                    )
                chapters = await live_chapters(session, self._offer_id)
            pending = {p.chapter_key for p in await self._open_proposals(session)}
            return [_view(c, c.chapter_key in pending) for c in chapters]

    async def _has_chapters(self, session: AsyncSession) -> bool:
        found = await session.scalar(
            select(ChapterEntity.id)
            .where(ChapterEntity.offer_id == self._offer_id)
            .limit(1)
        )
        return found is not None

    async def _open_proposals(self, session: AsyncSession) -> list[ProposalEntity]:
        return list(
            (
                await session.scalars(
                    select(ProposalEntity)
                    .where(
                        ProposalEntity.offer_id == self._offer_id,
                        ProposalEntity.status == ProposalStatus.OPEN,
                    )
                    .order_by(ProposalEntity.id)
                )
            ).all()
        )

    async def load(self, key: str) -> dict[str, Any]:
        """Revision, content and open proposal of a chapter."""
        async with self._sessions() as session:
            chapter = await find_chapter(session, self._offer_id, key)
            current = await revision_of(session, chapter)
            proposal = next(
                (
                    p
                    for p in reversed(await self._open_proposals(session))
                    if p.chapter_key == key
                ),
                None,
            )
            return {
                "revision": chapter.revision,
                "content": current.content,
                "origin": current.origin,
                "proposal": _proposal_dict(proposal, current.content)
                if proposal
                else None,
            }

    async def save(self, key: str, expected: int, content: Content) -> int:
        """Store a person's text as a new revision; ``expected`` must be current."""
        async with self._sessions() as session:
            chapter, workspace = await self._locked(session, key, expected)
            self._check(chapter, content)
            if _unchanged((await revision_of(session, chapter)).content, content):
                return chapter.revision
            number = _add_revision(
                session,
                chapter,
                content,
                origin=ChapterOrigin.MANUAL,
                author=self._user,
                map_revision=workspace.map_revision,
            )
            await reopen_accepted(session, self._offer_id, key)
            await self._stale_proposals(session, key, number)
            return number

    def _check(self, chapter: ChapterEntity, content: Content) -> None:
        if chapter.protected:
            raise ChapterError(PROTECTED)
        if chapter.chapter_type != content.chapter_type:
            raise ChapterError(WRONG_TYPE)

    async def _stale_proposals(
        self, session: AsyncSession, key: str, revision: int
    ) -> None:
        await session.execute(
            update(ProposalEntity)
            .where(
                ProposalEntity.offer_id == self._offer_id,
                ProposalEntity.chapter_key == key,
                ProposalEntity.status == ProposalStatus.OPEN,
                ProposalEntity.base_revision != revision,
            )
            .values(status=ProposalStatus.STALE)
        )

    async def history(self, key: str) -> list[dict[str, Any]]:
        """Revisions newest first, each with its line diff to the one before."""
        async with self._sessions() as session:
            chapter = await find_chapter(session, self._offer_id, key)
            rows = list(
                (
                    await session.scalars(
                        select(ChapterRevisionEntity)
                        .where(ChapterRevisionEntity.chapter_id == chapter.id)
                        .order_by(ChapterRevisionEntity.number)
                    )
                ).all()
            )
        before: list[str] = []
        entries: list[dict[str, Any]] = []
        for row in rows:
            lines = stored_lines(row.content)
            entries.append(
                {
                    "number": row.number,
                    "origin": row.origin,
                    "author": row.author,
                    "created": row.created.strftime("%d.%m.%Y %H:%M"),
                    "map_revision": row.map_revision,
                    "diff": diff_lines(before, lines),
                }
            )
            before = lines
        return entries[::-1]

    async def restore(self, key: str, expected: int, number: int) -> int:
        """Make an older text the newest revision; history is never rewritten."""
        async with self._sessions() as session:
            chapter, workspace = await self._locked(session, key, expected)
            old = await revision_of(session, chapter, number)
            content = parse_content(old.content)
            self._check(chapter, content)
            await reopen_accepted(session, self._offer_id, key)
            return _add_revision(
                session,
                chapter,
                content,
                origin=ChapterOrigin.MANUAL,
                author=self._user,
                map_revision=workspace.map_revision,
            )

    async def set_protected(self, key: str, protected: bool) -> None:
        async with self._sessions() as session:
            chapter, _ = await self._locked(session, key, None)
            chapter.protected = protected

    async def accept(self, proposal_id: int, expected: int) -> int:
        """Take over a proposal as a new revision; it confirms no decision (A17)."""
        async with self._sessions() as session:
            proposal = await session.get(ProposalEntity, proposal_id)
            if proposal is None or proposal.offer_id != self._offer_id:
                raise ChapterError(NO_PROPOSAL)
            chapter, _ = await self._locked(session, proposal.chapter_key, expected)
            if proposal.status != ProposalStatus.OPEN:
                raise ChapterError(NO_PROPOSAL)
            if proposal.base_revision == chapter.revision:
                content = parse_content(proposal.content)
                self._check(chapter, content)
                proposal.status = ProposalStatus.ACCEPTED
                await reopen_accepted(session, self._offer_id, proposal.chapter_key)
                return _add_revision(
                    session,
                    chapter,
                    content,
                    origin=ChapterOrigin.AI,
                    author=self._user,
                    map_revision=proposal.map_revision,
                )
            # Leave the context normally so the new status is committed.
            proposal.status = ProposalStatus.STALE
        raise ChapterError(STALE_PROPOSAL)

    async def reject(self, proposal_id: int) -> None:
        async with self._sessions() as session:
            proposal = await session.get(ProposalEntity, proposal_id)
            if proposal is None or proposal.offer_id != self._offer_id:
                raise ChapterError(NO_PROPOSAL)
            if proposal.status == ProposalStatus.OPEN:
                proposal.status = ProposalStatus.REJECTED


def _view(chapter: ChapterEntity, proposal: bool) -> dict:
    settings = settings_of(chapter)
    return {
        "key": chapter.chapter_key,
        "title": chapter.title,
        "level": chapter.level,
        "type": chapter.chapter_type,
        "required": chapter.required,
        "revision": chapter.revision,
        "protected": chapter.protected,
        "needs_review": chapter.needs_review,
        "review_reason": chapter.review_reason,
        "proposal": proposal,
        "guiding_question": settings.guiding_question,
        "rules": settings.content_rules,
    }


def _proposal_dict(proposal: ProposalEntity, current: dict) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "instruction": proposal.instruction,
        "map_revision": proposal.map_revision,
        "diff": diff_lines(stored_lines(current), stored_lines(proposal.content)),
    }


async def add_proposal(
    session: AsyncSession,
    *,
    offer_id: int,
    chapter_key: str,
    content: ProseContent,
    base_revision: int,
    map_revision: int,
    instruction: str,
    job_id: int | None,
) -> ProposalEntity:
    """Store a suggestion; older open ones for the chapter are replaced."""
    await session.execute(
        update(ProposalEntity)
        .where(
            ProposalEntity.offer_id == offer_id,
            ProposalEntity.chapter_key == chapter_key,
            ProposalEntity.status == ProposalStatus.OPEN,
        )
        .values(status=ProposalStatus.STALE)
    )
    proposal = ProposalEntity(
        offer_id=offer_id,
        chapter_key=chapter_key,
        job_id=job_id,
        content=content.model_dump(mode="json"),
        base_revision=base_revision,
        map_revision=map_revision,
        instruction=instruction,
    )
    session.add(proposal)
    return proposal
