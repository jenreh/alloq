"""AI proposals for the map: more steps or a split story, always as a comparison.

A proposal is bound to the map revision it was made for. Once the map moved on, it
is marked stale and cannot be taken over (A07). Taking over adds new activities,
tasks and stories with scope ``offen``; nothing existing is changed.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.ai.schemas import ProposedMap
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    ActivityEntity,
    JobEntity,
    ProposalEntity,
    ProposalStatus,
    SourceBlockEntity,
    SourceEntity,
    StoryEntity,
    TaskEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.job_requests import enqueue_exclusive
from alloq_offer.workshop.services.map_apply import new_story
from alloq_offer.workshop.services.map_edit import (
    MapConflictError,
    _next_position,
    map_edit,
    record,
)
from alloq_offer.workshop.services.story_rules import story_problems, story_sentence
from alloq_offer.workshop.services.workspace import NO_WORKSPACE

logger = logging.getLogger(__name__)

MAP_PROPOSAL_JOB = "propose_map_additions"
MAP_TARGET = "@map"
DEFAULT_INSTRUCTION = (
    "Schlage fehlende Prozessschritte vor: Aktivitäten, Aufgaben und Stories, "
    "die in den Quellen oder im Briefing vorkommen, aber in der Map fehlen."
)
SPLIT_INSTRUCTION = (
    "Teile die Story {key} „{title}“ in kleinere Stories auf, die einzeln "
    "angeboten werden können."
)
NO_MAP = "Es gibt noch keine Story Map, die ergänzt werden könnte."
NO_PROPOSAL = "Diesen Vorschlag gibt es nicht mehr."
STALE = "Die Map wurde inzwischen geändert. Der Vorschlag ist veraltet."
NOTHING_NEW = "Der Vorschlag enthält nichts, was nicht schon in der Map steht."


class MapProposalError(ValueError):
    """The proposal cannot be requested or taken over; the message is German."""


async def request_map_proposal(
    session_factory: SessionFactory,
    offer_id: int,
    instruction: str,
    *,
    now: datetime,
    max_attempts: int,
) -> JobEntity:
    """Queue the AI job; one waiting or running map job per offer."""
    async with session_factory() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        if workspace is None:
            raise MapProposalError(NO_WORKSPACE)
        if workspace.map_revision == 0:
            raise MapProposalError(NO_MAP)
        return await enqueue_exclusive(
            session,
            kind=MAP_PROPOSAL_JOB,
            offer_id=offer_id,
            payload={"instruction": instruction.strip() or DEFAULT_INSTRUCTION},
            now=now,
            max_attempts=max_attempts,
        )


async def store_proposal(
    session: AsyncSession,
    *,
    offer_id: int,
    proposed: ProposedMap,
    map_revision: int,
    instruction: str,
    job_id: int | None,
) -> ProposalEntity:
    """Keep the newest proposal; an older open one is replaced."""
    for old in (
        await session.scalars(
            select(ProposalEntity).where(
                ProposalEntity.offer_id == offer_id,
                ProposalEntity.chapter_key == MAP_TARGET,
                ProposalEntity.status == ProposalStatus.OPEN,
            )
        )
    ).all():
        old.status = ProposalStatus.REJECTED
    row = ProposalEntity(
        offer_id=offer_id,
        chapter_key=MAP_TARGET,
        job_id=job_id,
        content=proposed.model_dump(mode="json"),
        base_revision=map_revision,
        map_revision=map_revision,
        instruction=instruction,
    )
    session.add(row)
    await session.flush()
    return row


def _preview(proposed: ProposedMap) -> list[dict[str, str]]:
    """Flat lines for the comparison: activity, task or story with its sentence."""
    lines: list[dict[str, str]] = []
    for activity in proposed.activities:
        lines.append({"kind": "Aktivität", "text": activity.title})
        for task in activity.tasks:
            lines.append({"kind": "Aufgabe", "text": task.title})
            lines.extend(
                {
                    "kind": "Story",
                    "text": f"{story.title}: "
                    f"{story_sentence(story.role, story.goal, story.benefit)}",
                }
                for story in task.stories
            )
    return lines


async def open_proposal(
    session_factory: SessionFactory, offer_id: int
) -> dict[str, Any] | None:
    """The newest open proposal; one for an older map revision is marked stale."""
    async with session_factory() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        row = await session.scalar(
            select(ProposalEntity)
            .where(
                ProposalEntity.offer_id == offer_id,
                ProposalEntity.chapter_key == MAP_TARGET,
                ProposalEntity.status.in_([ProposalStatus.OPEN, ProposalStatus.STALE]),
            )
            .order_by(ProposalEntity.id.desc())
            .limit(1)
        )
        if row is None or workspace is None:
            return None
        if (
            row.status == ProposalStatus.OPEN
            and row.base_revision != workspace.map_revision
        ):
            row.status = ProposalStatus.STALE
        return {
            "id": row.id,
            "instruction": row.instruction,
            "stale": row.status == ProposalStatus.STALE,
            "lines": _preview(ProposedMap.model_validate(row.content)),
        }


async def _match[T: (ActivityEntity, TaskEntity)](
    session: AsyncSession, entity: type[T], title: str, *where: ColumnElement[bool]
) -> T | None:
    wanted = title.strip().casefold()
    rows = (await session.scalars(select(entity).where(*where))).all()
    return next(
        (r for r in rows if r.archived_at is None and r.title.casefold() == wanted),
        None,
    )


async def _citable_block_ids(session: AsyncSession, offer_id: int) -> set[int]:
    return set(
        (
            await session.scalars(
                select(SourceBlockEntity.id)
                .join(SourceEntity, SourceEntity.id == SourceBlockEntity.source_id)
                .where(
                    SourceEntity.offer_id == offer_id,
                    SourceEntity.revoked_at.is_(None),
                )
            )
        ).all()
    )


async def _add_to_map(
    session: AsyncSession,
    workspace: WorkspaceEntity,
    proposed: ProposedMap,
) -> int:
    """Add what is new; existing activities and tasks are matched by title."""
    offer_id = workspace.offer_id
    valid_ids = await _citable_block_ids(session, offer_id)
    added = 0
    for activity in proposed.activities:
        activity_row = await _match(
            session, ActivityEntity, activity.title, ActivityEntity.offer_id == offer_id
        )
        if activity_row is None:
            activity_row = ActivityEntity(
                offer_id=offer_id,
                title=activity.title.strip(),
                position=await _next_position(
                    session, ActivityEntity, ActivityEntity.offer_id == offer_id
                ),
            )
            session.add(activity_row)
            await session.flush()
            added += 1
        for task in activity.tasks:
            task_row = await _match(
                session,
                TaskEntity,
                task.title,
                TaskEntity.activity_id == activity_row.id,
            )
            if task_row is None:
                task_row = TaskEntity(
                    offer_id=offer_id,
                    activity_id=activity_row.id,
                    title=task.title.strip(),
                    position=await _next_position(
                        session, TaskEntity, TaskEntity.activity_id == activity_row.id
                    ),
                )
                session.add(task_row)
                await session.flush()
                added += 1
            for story in task.stories:
                if story_problems(story.title, story.role, story.goal, story.benefit):
                    continue
                session.add(
                    new_story(
                        workspace,
                        story,
                        task_id=task_row.id,
                        slice_id=None,
                        position=await _next_position(
                            session, StoryEntity, StoryEntity.offer_id == offer_id
                        ),
                        valid_block_ids=valid_ids,
                    )
                )
                await session.flush()
                added += 1
    return added


async def accept(
    session_factory: SessionFactory, offer_id: int, proposal_id: int, user: str
) -> int:
    """Take over a proposal as a new map revision; returns the revision."""
    async with session_factory() as session:
        row = await session.get(ProposalEntity, proposal_id)
        if (
            row is None
            or row.offer_id != offer_id
            or row.chapter_key != MAP_TARGET
            or row.status not in (ProposalStatus.OPEN, ProposalStatus.STALE)
        ):
            raise MapProposalError(NO_PROPOSAL)
        if row.status == ProposalStatus.STALE:
            raise MapProposalError(STALE)
        base = row.base_revision
        proposed = ProposedMap.model_validate(row.content)
    try:
        async with map_edit(session_factory, offer_id, base) as (session, workspace):
            if await _add_to_map(session, workspace, proposed) == 0:
                raise MapProposalError(NOTHING_NEW)
            revision = await record(session, workspace, user)
            stored = await session.get(ProposalEntity, proposal_id)
            assert stored is not None  # noqa: S101  # read above
            stored.status = ProposalStatus.ACCEPTED
    except MapConflictError as exc:
        async with session_factory() as session:
            stale = await session.get(ProposalEntity, proposal_id)
            if stale is not None:
                stale.status = ProposalStatus.STALE
        raise MapProposalError(STALE) from exc
    logger.info("Map proposal %s of offer %s taken over", proposal_id, offer_id)
    return revision


async def reject(
    session_factory: SessionFactory, offer_id: int, proposal_id: int
) -> None:
    async with session_factory() as session:
        row = await session.get(ProposalEntity, proposal_id)
        if (
            row is None
            or row.offer_id != offer_id
            or row.chapter_key != MAP_TARGET
            or row.status not in (ProposalStatus.OPEN, ProposalStatus.STALE)
        ):
            raise MapProposalError(NO_PROPOSAL)
        row.status = ProposalStatus.REJECTED
