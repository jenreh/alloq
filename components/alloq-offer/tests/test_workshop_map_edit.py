"""Tests of the map edits, their revision checks and snapshots."""

import pytest
from alloq_offer.workshop.ai.schemas import (
    ProposedActivity,
    ProposedMap,
    ProposedStory,
    ProposedTask,
)
from alloq_offer.workshop.entities import (
    ActivityEntity,
    MapRevisionEntity,
    Origin,
    Scope,
    SliceEntity,
    StoryEntity,
    TaskEntity,
)
from alloq_offer.workshop.services.map_apply import apply_proposed_map
from alloq_offer.workshop.services.map_edit import (
    ACTIVITY_NOT_EMPTY,
    BLANK_TITLE,
    MapConflictError,
    MapEditError,
    MapEditor,
)
from alloq_offer.workshop.services.workspace import open_workspace
from sqlalchemy import select


def _story(title: str) -> ProposedStory:
    return ProposedStory(
        title=title,
        role="Disponent",
        goal="Anfragen ordnen",
        benefit="besser zu planen",
        origin="Kunde",
        source_refs=[1],
    )


@pytest.fixture
async def editor(db) -> MapEditor:
    proposal = ProposedMap(
        activities=[
            ProposedActivity(
                title="Eingang",
                tasks=[ProposedTask(title="Prüfen", stories=[_story("Erste")])],
            ),
            ProposedActivity(
                title="Bearbeitung",
                tasks=[ProposedTask(title="Ordnen", stories=[_story("Zweite")])],
            ),
        ],
        slices=["Kern"],
    )
    async with db.session() as session:
        workspace = await open_workspace(session, 1, "Anna")
        await session.flush()
        await apply_proposed_map(session, workspace, proposal, {1})
    return MapEditor(db.session, 1, "Anna")


async def _revision(db) -> int:
    async with db.session() as session:
        return (await open_workspace(session, 1, "")).map_revision


async def _all(db, entity):  # noqa: ANN001, ANN202
    async with db.session() as session:
        return list((await session.scalars(select(entity).order_by(entity.id))).all())


async def test_every_edit_bumps_the_revision_and_keeps_a_snapshot(db, editor) -> None:
    assert await _revision(db) == 1
    assert await editor.add_activity(1, "  Abschluss ") == 2
    assert await _revision(db) == 2
    revisions = await _all(db, MapRevisionEntity)
    assert [r.revision for r in revisions] == [1, 2]
    titles = [a["title"] for a in revisions[1].snapshot["activities"]]
    assert titles == ["Eingang", "Bearbeitung", "Abschluss"]
    assert [a["title"] for a in revisions[0].snapshot["activities"]] == [
        "Eingang",
        "Bearbeitung",
    ]


async def test_stale_revision_is_refused_and_nothing_changes(db, editor) -> None:
    await editor.add_activity(1, "Neu")
    with pytest.raises(MapConflictError):
        await editor.add_activity(1, "Zweiter Versuch")
    assert await _revision(db) == 2
    assert len(await _all(db, ActivityEntity)) == 3


async def test_names_must_not_be_blank(editor) -> None:
    for call in (editor.add_activity(1, " "), editor.add_slice(1, "")):
        with pytest.raises(MapEditError, match=BLANK_TITLE):
            await call


async def test_rename_and_reorder_activities(db, editor) -> None:
    first = (await _all(db, ActivityEntity))[0]
    revision = await editor.rename_activity(1, first.id, "Anfrage")
    revision = await editor.move_activity(revision, first.id, 1)
    rows = sorted(await _all(db, ActivityEntity), key=lambda a: a.position)
    assert [a.title for a in rows] == ["Bearbeitung", "Anfrage"]
    revision = await editor.move_activity(revision, first.id, 1)
    rows = sorted(await _all(db, ActivityEntity), key=lambda a: a.position)
    assert [a.title for a in rows] == ["Bearbeitung", "Anfrage"]
    assert revision == 4


async def test_activity_with_stories_cannot_be_archived_but_an_empty_one_can(
    db, editor
) -> None:
    first = (await _all(db, ActivityEntity))[0]
    with pytest.raises(MapEditError, match=ACTIVITY_NOT_EMPTY):
        await editor.archive_activity(1, first.id)
    revision = await editor.add_activity(1, "Leer")
    leer = (await _all(db, ActivityEntity))[-1]
    revision = await editor.add_task(revision, leer.id, "Aufgabe")
    await editor.archive_activity(revision, leer.id)
    rows = await _all(db, ActivityEntity)
    assert rows[-1].archived_at is not None
    assert (await _all(db, TaskEntity))[-1].archived_at is not None


async def test_tasks_and_slices_can_be_added_and_renamed(db, editor) -> None:
    activity = (await _all(db, ActivityEntity))[0]
    revision = await editor.add_task(1, activity.id, "Neue Aufgabe")
    revision = await editor.add_slice(revision, "Erweiterung")
    slice_row = (await _all(db, SliceEntity))[-1]
    await editor.rename_slice(revision, slice_row.id, "Später")
    assert (await _all(db, TaskEntity))[-1].title == "Neue Aufgabe"
    assert (await _all(db, SliceEntity))[-1].title == "Später"
    assert (await _all(db, SliceEntity))[-1].position == 2


async def test_story_text_must_keep_the_simple_format(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.update_story(
        1, story.id, {"title": "Neu", "goal": "ordnen"}
    )
    assert (await _all(db, StoryEntity))[0].title == "Neu"
    with pytest.raises(MapEditError, match="Akzeptanzkriterien"):
        await editor.update_story(
            revision, story.id, {"benefit": "Akzeptanzkriterien erfüllen"}
        )
    with pytest.raises(MapEditError):
        await editor.update_story(revision, story.id, {"role": ""})
    assert await _revision(db) == revision


async def test_new_stories_get_fresh_keys_and_start_open(db, editor) -> None:
    task = (await _all(db, TaskEntity))[0]
    await editor.add_story(1, task.id, None)
    story = (await _all(db, StoryEntity))[-1]
    assert (story.key, story.scope, story.origin) == ("US-03", Scope.OPEN, Origin.USER)


async def test_archived_keys_are_never_reused(db, editor) -> None:
    task = (await _all(db, TaskEntity))[0]
    stories = await _all(db, StoryEntity)
    revision = await editor.archive_story(1, stories[-1].id)
    await editor.add_story(revision, task.id, None)
    keys = [s.key for s in await _all(db, StoryEntity)]
    assert keys == ["US-01", "US-02", "US-03"]
    assert (await _all(db, StoryEntity))[1].archived_at is not None


async def test_split_keeps_the_origin_link_and_gives_a_new_key(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    await editor.split_story(1, story.id)
    copy = (await _all(db, StoryEntity))[-1]
    assert copy.split_from_id == story.id
    assert copy.key == "US-03"
    assert copy.title.endswith("(Teil 2)")
    assert copy.source_refs == story.source_refs


async def test_scope_and_move(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    other_task = (await _all(db, TaskEntity))[1]
    revision = await editor.set_scope(1, story.id, "angeboten")
    sl = (await _all(db, SliceEntity))[0]
    await editor.move_story(revision, story.id, other_task.id, sl.id)
    moved = (await _all(db, StoryEntity))[0]
    assert (moved.scope, moved.task_id, moved.slice_id) == (
        Scope.OFFERED,
        other_task.id,
        sl.id,
    )
    with pytest.raises(MapEditError):
        await editor.set_scope(await _revision(db), story.id, "nope")


async def test_missing_or_foreign_rows_are_refused(db, editor) -> None:
    with pytest.raises(MapEditError):
        await editor.rename_activity(1, 999, "x")
    with pytest.raises(MapEditError):
        await editor.move_activity(1, 999, 1)
    with pytest.raises(MapEditError):
        await editor.move_story(1, 999, 1, None)
    with pytest.raises(MapEditError):
        await MapEditor(db.session, 99, "x").add_activity(0, "x")


async def test_archived_rows_cannot_be_edited_again(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.archive_story(1, story.id)
    for call in (
        editor.archive_story(revision, story.id),
        editor.set_scope(revision, story.id, "option"),
        editor.split_story(revision, story.id),
    ):
        with pytest.raises(MapEditError):
            await call
    assert await _revision(db) == revision


async def test_edits_without_a_change_keep_the_revision(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    assert await editor.update_story(1, story.id, {"title": story.title}) == 1
    assert await editor.set_scope(1, story.id, story.scope) == 1
    with pytest.raises(MapEditError, match="Umfang"):
        await editor.set_scope(1, story.id, "nope")
    assert len(await _all(db, MapRevisionEntity)) == 1


async def test_split_and_new_stories_get_distinct_positions(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.split_story(1, story.id)
    await editor.add_story(revision, story.task_id, None)
    positions = [s.position for s in await _all(db, StoryEntity)]
    assert len(set(positions)) == len(positions)
