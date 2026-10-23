"""Chapters of an offer: revisions, conflicts and AI proposals (spec 5.5, 10.2-10.4).

A chapter's text lives in immutable revisions. A save names the revision the person
saw; if somebody saved in between, nothing is overwritten (A08). AI texts only ever
arrive as proposals that a person accepts.
"""

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.content.schema import ProseContent, parse_content
from alloq_offer.workshop.content.text import Content, diff_lines, stored_lines
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    ChapterEntity,
    ChapterOrigin,
    ChapterRevisionEntity,
    ProposalEntity,
    ProposalStatus,
    WorkspaceEntity,
)
from alloq_offer.workshop.export.template_package import (
    ChapterDef,
    TemplatePackage,
    load_template,
)
from alloq_offer.workshop.repositories import workspace_repo

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


def default_content(definition: ChapterDef) -> Content:
    """The empty content a chapter starts with, from the template defaults."""
    return parse_content(
        {"chapter_type": definition.chapter_type, **definition.defaults}
    )


def _template(workspace: WorkspaceEntity) -> TemplatePackage:
    return load_template(workspace.template_key)


async def mark_dependent_review(
    session: AsyncSession, workspace: WorkspaceEntity, reason: str = REVIEW_AFTER_MAP
) -> None:
    """Flag written prose chapters after a map change (A09, A27).

    Chapters that still hold the template text have nothing to review, and
    projections (stories, calc) follow the map by themselves.
    """
    prose = [c.key for c in _template(workspace).chapters if c.chapter_type == "prose"]
    await session.execute(
        update(ChapterEntity)
        .where(
            ChapterEntity.offer_id == workspace.offer_id,
            ChapterEntity.chapter_key.in_(prose),
            ChapterEntity.revision > 1,
        )
        .values(needs_review=True, review_reason=reason)
    )


async def find_chapter(
    session: AsyncSession, offer_id: int, key: str, *, lock: bool = False
) -> ChapterEntity:
    query = select(ChapterEntity).where(
        ChapterEntity.offer_id == offer_id, ChapterEntity.chapter_key == key
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
        """Create missing chapters from the template and list them in order."""
        async with self._sessions() as session:
            workspace = await workspace_repo.find_by_offer(session, self._offer_id)
            if workspace is None:
                return []
            template = _template(workspace)
            existing = await self._chapters(session)
            if len(existing) < len(template.chapters):
                # Only creating chapters needs the lock that serialises with map edits.
                await session.refresh(workspace, with_for_update=True)
                existing = await self._chapters(session)
                await self._create_missing(session, workspace, template, existing)
            pending = {p.chapter_key for p in await self._open_proposals(session)}
            return [
                _view(definition, existing[definition.key], definition.key in pending)
                for definition in template.chapters
            ]

    async def _chapters(self, session: AsyncSession) -> dict[str, ChapterEntity]:
        rows = await session.scalars(
            select(ChapterEntity).where(ChapterEntity.offer_id == self._offer_id)
        )
        return {c.chapter_key: c for c in rows.all()}

    async def _create_missing(
        self,
        session: AsyncSession,
        workspace: WorkspaceEntity,
        template: TemplatePackage,
        existing: dict[str, ChapterEntity],
    ) -> None:
        for definition in template.chapters:
            if definition.key in existing:
                continue
            chapter = ChapterEntity(
                offer_id=self._offer_id, chapter_key=definition.key, revision=0
            )
            session.add(chapter)
            await session.flush()
            _add_revision(
                session,
                chapter,
                default_content(definition),
                origin=ChapterOrigin.TEMPLATE,
                author="",
                map_revision=workspace.map_revision,
            )
            existing[definition.key] = chapter

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
            self._check(chapter, workspace, content)
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
            await self._stale_proposals(session, key, number)
            return number

    def _check(
        self, chapter: ChapterEntity, workspace: WorkspaceEntity, content: Content
    ) -> None:
        if chapter.protected:
            raise ChapterError(PROTECTED)
        if (
            _template(workspace).chapter(chapter.chapter_key).chapter_type
            != content.chapter_type
        ):
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
            self._check(chapter, workspace, content)
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
            chapter, workspace = await self._locked(
                session, proposal.chapter_key, expected
            )
            if proposal.status != ProposalStatus.OPEN:
                raise ChapterError(NO_PROPOSAL)
            if proposal.base_revision == chapter.revision:
                content = parse_content(proposal.content)
                self._check(chapter, workspace, content)
                proposal.status = ProposalStatus.ACCEPTED
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


def _view(definition: ChapterDef, chapter: ChapterEntity, proposal: bool) -> dict:
    return {
        "key": definition.key,
        "title": definition.title,
        "level": definition.level,
        "type": definition.chapter_type,
        "required": definition.required,
        "revision": chapter.revision,
        "protected": chapter.protected,
        "needs_review": chapter.needs_review,
        "review_reason": chapter.review_reason,
        "proposal": proposal,
        "guiding_question": definition.guiding_question,
        "rules": definition.content_rules,
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
