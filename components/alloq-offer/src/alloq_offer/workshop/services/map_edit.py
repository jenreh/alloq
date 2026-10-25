"""Edits of the story map by a person; every edit checks and bumps the revision."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    ActivityEntity,
    MapRevisionEntity,
    Origin,
    SliceEntity,
    StoryEntity,
    TaskEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.services.chapters import mark_dependent_review
from alloq_offer.workshop.services.map_apply import next_story_key, snapshot_map
from alloq_offer.workshop.services.story_rules import (
    MAX_DESCRIPTION_LENGTH,
    STORY_FIELDS,
    story_problems,
)

CONFLICT = (
    "Die Map wurde inzwischen geändert. Die aktuelle Fassung wurde geladen, "
    "bitte wiederholen Sie die Änderung."
)
NOT_FOUND = "Das Element gibt es nicht mehr."
NOT_ARCHIVED = "Die Story ist nicht archiviert."
ACTIVITY_NOT_EMPTY = "Die Aktivität enthält noch Stories. Archivieren Sie diese zuerst."
DEFAULT_TASK = "Hauptaufgabe"
BLANK_TITLE = "Bitte geben Sie einen Namen ein."
DESCRIPTION_TOO_LONG = "Die Beschreibung ist zu lang."
NEW_STORY_TITLE = "Neue Story"
SNAPSHOT_KEY = "map_snapshot"
"""``Session.info`` key under which ``record`` leaves the snapshot it stored."""


class MapConflictError(RuntimeError):
    """Someone else changed the map since the editor loaded it (A08)."""


class MapEditError(ValueError):
    """The edit is not allowed; the message is German and shown to users."""


@asynccontextmanager
async def map_edit(
    session_factory: SessionFactory, offer_id: int, expected_revision: int
) -> AsyncIterator[tuple[AsyncSession, WorkspaceEntity]]:
    """A transaction on the locked workspace; a stale ``expected_revision`` fails.

    The lock and the load are one query, so an edit needs no second round trip.
    """
    async with session_factory() as session:
        workspace = await session.scalar(
            select(WorkspaceEntity)
            .where(WorkspaceEntity.offer_id == offer_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if workspace is None:
            raise MapEditError(NOT_FOUND)
        if workspace.map_revision != expected_revision:
            raise MapConflictError(CONFLICT)
        yield session, workspace


async def record(session: AsyncSession, workspace: WorkspaceEntity, user: str) -> int:
    """Bump the revision and keep an immutable snapshot of the result."""
    await session.flush()
    workspace.map_revision += 1
    await mark_dependent_review(session, workspace)
    snapshot = await snapshot_map(session, workspace)
    session.info[SNAPSHOT_KEY] = snapshot
    session.add(
        MapRevisionEntity(
            offer_id=workspace.offer_id,
            revision=workspace.map_revision,
            snapshot=snapshot,
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


async def _insert[T: ActivityEntity | SliceEntity](
    session: AsyncSession, row: T, index: int | None, *where: object
) -> T:
    """Add ``row`` at ``index`` among the rows matching ``where`` (end when None)."""
    entity = type(row)
    rows = list(
        (
            await session.scalars(
                select(entity).where(*where).order_by(entity.position, entity.id)  # ty: ignore[invalid-argument-type]
            )
        ).all()
    )
    rows.insert(len(rows) if index is None else max(index, 0), row)
    for position, item in enumerate(rows, 1):
        item.position = position
    session.add(row)
    await session.flush()
    return row


def _apply_story_text(story: StoryEntity, fields: dict[str, str]) -> bool:
    """Set title, role, goal, benefit and description; True when one changed."""
    values = {
        name: fields.get(name, getattr(story, name)).strip()
        for name in (*STORY_FIELDS, "description")
    }
    problems = story_problems(*(values[name] for name in STORY_FIELDS))
    if len(values["description"]) > MAX_DESCRIPTION_LENGTH:
        problems.append(DESCRIPTION_TOO_LONG)
    if problems:
        raise MapEditError(" ".join(problems))
    changed = False
    for name, value in values.items():
        if getattr(story, name) != value:
            setattr(story, name, value)
            changed = True
    return changed


class MapEditor:
    """The edits of one person on the map of one offer; every call returns the new
    revision and fails with ``MapConflictError`` when the given one is stale."""

    def __init__(self, sessions: SessionFactory, offer_id: int, user: str) -> None:
        self._sessions = sessions
        self._offer_id = offer_id
        self._user = user
        self.snapshot: dict | None = None
        """Map after the last edit that changed it, so callers need no reload."""

    @asynccontextmanager
    async def _edit(
        self, revision: int
    ) -> AsyncIterator[tuple[AsyncSession, WorkspaceEntity]]:
        self.snapshot = None
        async with map_edit(self._sessions, self._offer_id, revision) as edit:
            yield edit
            self.snapshot = edit[0].info.get(SNAPSHOT_KEY)

    # --- activities, tasks, slices ---------------------------------------------

    async def add_activity(
        self, revision: int, title: str, index: int | None = None
    ) -> int:
        """A new activity with one task, at ``index`` among the live ones."""
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            activity = await _insert(
                session,
                ActivityEntity(offer_id=self._offer_id, title=name),
                index,
                ActivityEntity.offer_id == self._offer_id,
                ActivityEntity.archived_at.is_(None),
            )
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

    async def add_slice(
        self, revision: int, title: str, index: int | None = None
    ) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            await _insert(
                session,
                SliceEntity(offer_id=self._offer_id, title=name),
                index,
                SliceEntity.offer_id == self._offer_id,
            )
            return await record(session, workspace, self._user)

    async def rename_slice(self, revision: int, slice_id: int, title: str) -> int:
        name = _title(title)
        async with self._edit(revision) as (session, workspace):
            (await _own(session, SliceEntity, self._offer_id, slice_id)).title = name
            return await record(session, workspace, self._user)

    async def delete_slice(self, revision: int, slice_id: int) -> int:
        """Remove a slice; its stories stay and fall back to "no slice"."""
        async with self._edit(revision) as (session, workspace):
            row = await _own(session, SliceEntity, self._offer_id, slice_id)
            await session.execute(
                update(StoryEntity)
                .where(StoryEntity.slice_id == slice_id)
                .values(slice_id=None)
            )
            await session.delete(row)
            return await record(session, workspace, self._user)

    # --- stories ----------------------------------------------------------------

    async def add_story(
        self, revision: int, task_id: int, slice_id: int | None, title: str = ""
    ) -> int:
        """A new story for the user to fill in; without a title it is "Neue Story"."""
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
                    title=title.strip()[:300] or NEW_STORY_TITLE,
                    role="Rolle",
                    goal="ein Ziel erreichen",
                    benefit="einen Nutzen zu haben",
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
        """Change the text of one story; the simple story format must hold."""
        return await self.update_stories(revision, {story_id: fields})

    async def update_stories(
        self, revision: int, changes: dict[int, dict[str, str]]
    ) -> int:
        """Change the text of several stories in one revision (list editing)."""
        async with self._edit(revision) as (session, workspace):
            changed = False
            for story_id, fields in changes.items():
                story = await _own(session, StoryEntity, self._offer_id, story_id)
                changed = _apply_story_text(story, fields) or changed
            if not changed:
                return workspace.map_revision
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

    async def unarchive_story(self, revision: int, story_id: int, task_id: int) -> int:
        """Bring an archived story back under a live task; its key stays."""
        async with self._edit(revision) as (session, workspace):
            story = await session.get(StoryEntity, story_id)
            if story is None or story.offer_id != self._offer_id:
                raise MapEditError(NOT_FOUND)
            if story.archived_at is None:
                raise MapEditError(NOT_ARCHIVED)
            await _own(session, TaskEntity, self._offer_id, task_id)
            story.task_id = task_id
            story.archived_at = None
            return await record(session, workspace, self._user)
