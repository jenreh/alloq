"""Edits of the story map by a person; every edit checks and bumps the revision."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    ActivityEntity,
    MapRevisionEntity,
    Origin,
    Scope,
    SliceEntity,
    StoryEntity,
    TaskEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapters import mark_dependent_review
from alloq_offer.workshop.services.map_apply import next_story_key, snapshot_map
from alloq_offer.workshop.services.story_rules import story_problems

CONFLICT = (
    "Die Map wurde inzwischen geändert. Die aktuelle Fassung wurde geladen, "
    "bitte wiederholen Sie die Änderung."
)
NOT_FOUND = "Das Element gibt es nicht mehr."
ACTIVITY_NOT_EMPTY = "Die Aktivität enthält noch Stories. Archivieren Sie diese zuerst."
DEFAULT_TASK = "Hauptaufgabe"
INVALID_SCOPE = "Dieser Umfang ist nicht bekannt."
BLANK_TITLE = "Bitte geben Sie einen Namen ein."


class MapConflictError(RuntimeError):
    """Someone else changed the map since the editor loaded it (A08)."""


class MapEditError(ValueError):
    """The edit is not allowed; the message is German and shown to users."""


@asynccontextmanager
async def map_edit(
    session_factory: SessionFactory, offer_id: int, expected_revision: int
) -> AsyncIterator[tuple[AsyncSession, WorkspaceEntity]]:
    """A transaction on the locked workspace; a stale ``expected_revision`` fails."""
    async with session_factory() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        if workspace is None:
            raise MapEditError(NOT_FOUND)
        await session.refresh(workspace, with_for_update=True)
        if workspace.map_revision != expected_revision:
            raise MapConflictError(CONFLICT)
        yield session, workspace


async def record(session: AsyncSession, workspace: WorkspaceEntity, user: str) -> int:
    """Bump the revision and keep an immutable snapshot of the result."""
    await session.flush()
    workspace.map_revision += 1
    await mark_dependent_review(session, workspace)
    session.add(
        MapRevisionEntity(
            offer_id=workspace.offer_id,
            revision=workspace.map_revision,
            snapshot=await snapshot_map(session, workspace),
            created_by=user,
        )
    )
    return workspace.map_revision


def _title(value: str) -> str:
    title = value.strip()
    if not title:
        raise MapEditError(BLANK_TITLE)
    return title[:255]


async def _own[T: ActivityEntity | TaskEntity | StoryEntity | SliceEntity](
    session: AsyncSession, entity: type[T], offer_id: int, row_id: int
) -> T:
    row = await session.get(entity, row_id)
    if (
        row is None
        or row.offer_id != offer_id
        or getattr(row, "archived_at", None) is not None
    ):
        raise MapEditError(NOT_FOUND)
    return row


async def _next_position(
    session: AsyncSession,
    entity: type[ActivityEntity | TaskEntity | SliceEntity | StoryEntity],
    *where: object,
) -> int:
    highest = await session.scalar(select(func.max(entity.position)).where(*where))  # ty: ignore[invalid-argument-type]
    return (highest or 0) + 1


class MapEditor:
    """The edits of one person on the map of one offer; every call returns the new
    revision and fails with ``MapConflictError`` when the given one is stale."""

    def __init__(self, sessions: SessionFactory, offer_id: int, user: str) -> None:
        self._sessions = sessions
        self._offer_id = offer_id
        self._user = user

    def _edit(self, revision: int):  # noqa: ANN202
        return map_edit(self._sessions, self._offer_id, revision)

    # --- activities, tasks, slices ---------------------------------------------

    async def add_activity(self, revision: int, title: str) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            position = await _next_position(
                session, ActivityEntity, ActivityEntity.offer_id == self._offer_id
            )
            activity = ActivityEntity(
                offer_id=self._offer_id, title=name, position=position
            )
            session.add(activity)
            await session.flush()
            session.add(
                TaskEntity(
                    offer_id=self._offer_id,
                    activity_id=activity.id,
                    title=DEFAULT_TASK,
                    position=1,
                )
            )
            return await record(session, workspace, self._user)

    async def rename_activity(self, revision: int, activity_id: int, title: str) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            (
                await _own(session, ActivityEntity, self._offer_id, activity_id)
            ).title = name
            return await record(session, workspace, self._user)

    async def move_activity(self, revision: int, activity_id: int, step: int) -> int:
        """Swap an activity with its neighbour (``step`` is -1 or 1)."""
        async with self._edit(revision) as (session, workspace):
            rows = list(
                (
                    await session.scalars(
                        select(ActivityEntity)
                        .where(
                            ActivityEntity.offer_id == self._offer_id,
                            ActivityEntity.archived_at.is_(None),
                        )
                        .order_by(ActivityEntity.position, ActivityEntity.id)
                    )
                ).all()
            )
            index = next((i for i, a in enumerate(rows) if a.id == activity_id), None)
            if index is None:
                raise MapEditError(NOT_FOUND)
            target = index + step
            if 0 <= target < len(rows):
                rows[index], rows[target] = rows[target], rows[index]
                for position, row in enumerate(rows, 1):
                    row.position = position
            return await record(session, workspace, self._user)

    async def archive_activity(self, revision: int, activity_id: int) -> int:
        async with self._edit(revision) as (session, workspace):
            activity = await _own(session, ActivityEntity, self._offer_id, activity_id)
            tasks = (
                await session.scalars(
                    select(TaskEntity).where(TaskEntity.activity_id == activity_id)
                )
            ).all()
            task_ids = [task.id for task in tasks]
            used = await session.scalar(
                select(StoryEntity.id)
                .where(
                    StoryEntity.task_id.in_(task_ids),
                    StoryEntity.archived_at.is_(None),
                )
                .limit(1)
            )
            if used is not None:
                raise MapEditError(ACTIVITY_NOT_EMPTY)
            now = datetime.now(UTC)
            activity.archived_at = now
            for task in tasks:
                task.archived_at = now
            return await record(session, workspace, self._user)

    async def add_task(self, revision: int, activity_id: int, title: str) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            await _own(session, ActivityEntity, self._offer_id, activity_id)
            position = await _next_position(
                session, TaskEntity, TaskEntity.activity_id == activity_id
            )
            session.add(
                TaskEntity(
                    offer_id=self._offer_id,
                    activity_id=activity_id,
                    title=name,
                    position=position,
                )
            )
            return await record(session, workspace, self._user)

    async def add_slice(self, revision: int, title: str) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            position = await _next_position(
                session, SliceEntity, SliceEntity.offer_id == self._offer_id
            )
            session.add(
                SliceEntity(offer_id=self._offer_id, title=name, position=position)
            )
            return await record(session, workspace, self._user)

    async def rename_slice(self, revision: int, slice_id: int, title: str) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            (await _own(session, SliceEntity, self._offer_id, slice_id)).title = name
            return await record(session, workspace, self._user)

    # --- stories ----------------------------------------------------------------

    async def add_story(self, revision: int, task_id: int, slice_id: int | None) -> int:
        """A new story for the user to fill in, with scope ``offen``."""
        async with self._edit(revision) as (session, workspace):
            await _own(session, TaskEntity, self._offer_id, task_id)
            if slice_id is not None:
                await _own(session, SliceEntity, self._offer_id, slice_id)
            position = await _next_position(
                session, StoryEntity, StoryEntity.offer_id == self._offer_id
            )
            session.add(
                StoryEntity(
                    offer_id=self._offer_id,
                    key=next_story_key(workspace),
                    title="Neue Story",
                    role="Rolle",
                    goal="ein Ziel erreichen",
                    benefit="einen Nutzen zu haben",
                    scope=Scope.OPEN,
                    origin=Origin.USER,
                    task_id=task_id,
                    slice_id=slice_id,
                    position=position,
                )
            )
            return await record(session, workspace, self._user)

    async def update_story(
        self, revision: int, story_id: int, fields: dict[str, str]
    ) -> int:
        """Change title, role, goal or benefit; the simple story format must hold."""
        async with self._edit(revision) as (session, workspace):
            story = await _own(session, StoryEntity, self._offer_id, story_id)
            values = {
                name: fields.get(name, getattr(story, name)).strip()
                for name in ("title", "role", "goal", "benefit")
            }
            problems = story_problems(**values)
            if problems:
                raise MapEditError(" ".join(problems))
            if all(getattr(story, name) == value for name, value in values.items()):
                return workspace.map_revision
            for name, value in values.items():
                setattr(story, name, value)
            return await record(session, workspace, self._user)

    async def set_scope(self, revision: int, story_id: int, scope: str) -> int:
        try:
            value = Scope(scope)
        except ValueError:
            raise MapEditError(INVALID_SCOPE) from None
        async with self._edit(revision) as (session, workspace):
            story = await _own(session, StoryEntity, self._offer_id, story_id)
            if story.scope == value:
                return workspace.map_revision
            story.scope = value
            return await record(session, workspace, self._user)

    async def move_story(
        self, revision: int, story_id: int, task_id: int, slice_id: int | None
    ) -> int:
        async with self._edit(revision) as (session, workspace):
            story = await _own(session, StoryEntity, self._offer_id, story_id)
            task = await _own(session, TaskEntity, self._offer_id, task_id)
            if task.archived_at is not None:
                raise MapEditError(NOT_FOUND)
            if slice_id is not None:
                await _own(session, SliceEntity, self._offer_id, slice_id)
            story.task_id = task_id
            story.slice_id = slice_id
            return await record(session, workspace, self._user)

    async def split_story(self, revision: int, story_id: int) -> int:
        """A copy as a new story with its own key; the original stays as it is."""
        async with self._edit(revision) as (session, workspace):
            story = await _own(session, StoryEntity, self._offer_id, story_id)
            session.add(
                StoryEntity(
                    offer_id=self._offer_id,
                    key=next_story_key(workspace),
                    title=f"{story.title} (Teil 2)"[:300],
                    role=story.role,
                    goal=story.goal,
                    benefit=story.benefit,
                    scope=Scope.OPEN,
                    origin=Origin.USER,
                    task_id=story.task_id,
                    slice_id=story.slice_id,
                    position=await _next_position(
                        session, StoryEntity, StoryEntity.offer_id == self._offer_id
                    ),
                    source_refs=list(story.source_refs),
                    split_from_id=story.id,
                )
            )
            return await record(session, workspace, self._user)

    async def archive_story(self, revision: int, story_id: int) -> int:
        """Archive a story; its key is never given out again."""
        async with self._edit(revision) as (session, workspace):
            (
                await _own(session, StoryEntity, self._offer_id, story_id)
            ).archived_at = datetime.now(UTC)
            return await record(session, workspace, self._user)
