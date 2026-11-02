"""Turn a proposed map and briefing into stored rows and a map revision."""

import copy
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.ai.schemas import (
    ProposedBriefing,
    ProposedMap,
    ProposedStory,
)
from alloq_offer.workshop.entities import (
    ActivityEntity,
    MapRevisionEntity,
    Origin,
    SliceEntity,
    StatementEntity,
    StatementType,
    StoryEntity,
    TaskEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.services.chapters import mark_dependent_review
from alloq_offer.workshop.services.story_rules import story_problems, story_sentence

logger = logging.getLogger(__name__)

KEY_PREFIX = "US-"
EVIDENCE_TYPES = (StatementType.REQUIREMENT, StatementType.FACT)
SNAPSHOT_CACHE_SIZE = 64

# Every change of the map rows bumps ``map_revision``, so a snapshot of one
# revision never changes. Keyed by (offer id, map revision).
_snapshots: dict[tuple[int, int], dict] = {}


@dataclass
class ApplyResult:
    stories: int = 0
    statements: int = 0
    skipped: list[str] = field(default_factory=list)


def next_story_key(workspace: WorkspaceEntity) -> str:
    """The next story key; the counter only grows, so keys are never reused."""
    workspace.story_seq += 1
    return f"{KEY_PREFIX}{workspace.story_seq:02d}"


def _known_refs(refs: list[int], valid_block_ids: set[int]) -> list[int]:
    """Refs that point at a real block; invented ones are dropped."""
    kept = [ref for ref in dict.fromkeys(refs) if ref in valid_block_ids]
    if len(kept) < len(set(refs)):
        logger.warning("Dropped %d unknown source refs", len(set(refs)) - len(kept))
    return kept


def new_story(
    workspace: WorkspaceEntity,
    story: ProposedStory,
    *,
    task_id: int,
    slice_id: int | None,
    position: int,
    valid_block_ids: set[int],
) -> StoryEntity:
    """A stored story from a proposal: app key and checked origin."""
    refs = _known_refs(story.source_refs, valid_block_ids)
    return StoryEntity(
        offer_id=workspace.offer_id,
        key=next_story_key(workspace),
        title=story.title.strip(),
        role=story.role.strip(),
        goal=story.goal.strip(),
        benefit=story.benefit.strip(),
        # Without a surviving source ref the wish is not verifiable.
        origin=(
            Origin.CUSTOMER
            if story.origin == Origin.CUSTOMER and refs
            else Origin.PROPOSAL
        ),
        task_id=task_id,
        slice_id=slice_id,
        skeleton=story.skeleton,
        position=position,
        source_refs=refs,
    )


async def apply_proposed_map(
    session: AsyncSession,
    workspace: WorkspaceEntity,
    proposed: ProposedMap,
    valid_block_ids: set[int],
) -> ApplyResult:
    """Store an initial map. The app assigns the keys; the model never does."""
    result = ApplyResult()
    offer_id = workspace.offer_id
    if proposed.vision and not workspace.vision:
        workspace.vision = proposed.vision
    if proposed.roles and not workspace.roles:
        workspace.roles = list(dict.fromkeys(proposed.roles))

    slices: dict[str, SliceEntity] = {}
    for position, title in enumerate(dict.fromkeys(proposed.slices), 1):
        slices[title] = SliceEntity(offer_id=offer_id, title=title, position=position)
        session.add(slices[title])
    await session.flush()

    story_position = 0
    for a_pos, activity in enumerate(proposed.activities, 1):
        activity_row = ActivityEntity(
            offer_id=offer_id, title=activity.title, position=a_pos
        )
        session.add(activity_row)
        await session.flush()
        for t_pos, task in enumerate(activity.tasks, 1):
            task_row = TaskEntity(
                offer_id=offer_id,
                activity_id=activity_row.id,
                title=task.title,
                position=t_pos,
            )
            session.add(task_row)
            await session.flush()
            for story in task.stories:
                if story_problems(story.title, story.role, story.goal, story.benefit):
                    result.skipped.append(story.title)
                    continue
                story_position += 1
                slice_row = slices.get(story.slice or "")
                session.add(
                    new_story(
                        workspace,
                        story,
                        task_id=task_row.id,
                        slice_id=slice_row.id if slice_row else None,
                        position=story_position,
                        valid_block_ids=valid_block_ids,
                    )
                )
                result.stories += 1

    points = [
        (StatementType.OPEN_POINT, q.text, q.source_refs)
        for q in proposed.open_questions
    ] + [(StatementType.CONFLICT, c.text, c.source_refs) for c in proposed.conflicts]
    for type_, text, refs in points:
        _add_statement(
            session, offer_id, type_, text, _known_refs(refs, valid_block_ids)
        )
        result.statements += 1
    for title in result.skipped:
        _add_statement(
            session,
            offer_id,
            StatementType.OPEN_POINT,
            f"Die Story „{title}“ wurde nicht übernommen, weil sie nicht "
            "dem einfachen Story-Format entspricht.",
            [],
        )
        result.statements += 1
    await session.flush()
    workspace.map_revision += 1
    await mark_dependent_review(session, workspace)
    session.add(
        MapRevisionEntity(
            offer_id=offer_id,
            revision=workspace.map_revision,
            snapshot=await snapshot_map(session, workspace),
            created_by=workspace.created_by,
        )
    )
    return result


async def apply_briefing(
    session: AsyncSession,
    offer_id: int,
    briefing: ProposedBriefing,
    valid_block_ids: set[int],
) -> int:
    """Store briefing statements; they stay proposals until a person confirms."""
    for statement in briefing.statements:
        _add_statement(
            session,
            offer_id,
            statement.type,
            statement.text,
            _known_refs(statement.source_refs, valid_block_ids),
        )
    return len(briefing.statements)


def _add_statement(
    session: AsyncSession,
    offer_id: int,
    type_: StatementType,
    text: str,
    refs: list[int],
) -> None:
    session.add(
        StatementEntity(
            offer_id=offer_id,
            type=type_,
            text=text,
            source_refs=refs,
            # An evidence claim without evidence needs a second look.
            needs_recheck=type_ in EVIDENCE_TYPES and not refs,
        )
    )


async def snapshot_map(session: AsyncSession, workspace: WorkspaceEntity) -> dict:
    """Immutable JSON of the map as it stands; stories carry their sentence."""
    offer_id = workspace.offer_id

    async def _rows[T](entity: type[T], position: object) -> list[T]:
        statement = select(entity).where(
            getattr(entity, "offer_id") == offer_id  # noqa: B009
        )
        ordered = statement.order_by(position, getattr(entity, "id"))  # noqa: B009
        return list((await session.scalars(ordered)).all())

    activities = await _rows(ActivityEntity, ActivityEntity.position)
    tasks = await _rows(TaskEntity, TaskEntity.position)
    stories = await _rows(StoryEntity, StoryEntity.position)
    slices = await _rows(SliceEntity, SliceEntity.position)
    stories_of: dict[int | None, list[dict]] = {}
    for story in stories:
        stories_of.setdefault(story.task_id, []).append(_story_dict(story))
    tasks_of: dict[int, list[TaskEntity]] = {}
    for task in tasks:
        tasks_of.setdefault(task.activity_id, []).append(task)
    return {
        "vision": workspace.vision,
        "roles": list(workspace.roles),
        "slices": [{"id": s.id, "title": s.title} for s in slices],
        "activities": [
            {
                "id": a.id,
                "title": a.title,
                "archived": a.archived_at is not None,
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "archived": t.archived_at is not None,
                        "stories": stories_of.get(t.id, []),
                    }
                    for t in tasks_of.get(a.id, [])
                ],
            }
            for a in activities
        ],
        "unassigned": stories_of.get(None, []),
    }


async def current_snapshot(session: AsyncSession, workspace: WorkspaceEntity) -> dict:
    """``snapshot_map`` for readers; a revision read before is not loaded again.

    Writers keep calling ``snapshot_map``: their revision is not committed yet.
    """
    key = (workspace.offer_id, workspace.map_revision)
    if key not in _snapshots:
        if len(_snapshots) >= SNAPSHOT_CACHE_SIZE:
            del _snapshots[next(iter(_snapshots))]
        _snapshots[key] = await snapshot_map(session, workspace)
    return copy.deepcopy(_snapshots[key])


def clear_snapshot_cache() -> None:
    _snapshots.clear()


def _story_dict(story: StoryEntity) -> dict:
    return {
        "id": story.id,
        "key": story.key,
        "title": story.title,
        "role": story.role,
        "goal": story.goal,
        "benefit": story.benefit,
        "sentence": story_sentence(story.role, story.goal, story.benefit),
        "description": story.description,
        "origin": story.origin,
        "slice_id": story.slice_id,
        "skeleton": story.skeleton,
        "source_refs": story.source_refs,
        "archived": story.archived_at is not None,
    }
