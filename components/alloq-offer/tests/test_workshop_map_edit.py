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
    SliceEntity,
    StoryEntity,
    TaskEntity,
)
from alloq_offer.workshop.services.map_apply import apply_proposed_map
from alloq_offer.workshop.services.map_edit import (
    ACTIVITY_NOT_EMPTY,
    BLANK_TITLE,
    NEW_STORY_TITLE,
    NOT_ARCHIVED,
    NOT_FOUND,
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


async def test_deleting_a_slice_keeps_its_stories_without_slice(db, editor) -> None:
    kern = (await _all(db, SliceEntity))[0]
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.move_story(1, story.id, story.task_id, kern.id)
    assert (await _all(db, StoryEntity))[0].slice_id == kern.id
    revision = await editor.delete_slice(revision, kern.id)
    assert await _all(db, SliceEntity) == []
    stories = await _all(db, StoryEntity)
    assert stories
    assert all(s.slice_id is None for s in stories)
    with pytest.raises(MapEditError):
        await editor.delete_slice(revision, kern.id)


async def _ordered_titles(db, entity) -> list[str]:  # noqa: ANN001
    rows = [r for r in await _all(db, entity) if not getattr(r, "archived_at", None)]
    return [r.title for r in sorted(rows, key=lambda r: (r.position, r.id))]


async def test_activities_and_slices_can_be_inserted_at_an_edge(db, editor) -> None:
    revision = await editor.add_activity(1, "Start", index=0)
    revision = await editor.add_activity(revision, "Mitte", index=2)
    revision = await editor.add_activity(revision, "Ende", index=99)
    assert await _ordered_titles(db, ActivityEntity) == [
        "Start",
        "Eingang",
        "Mitte",
        "Bearbeitung",
        "Ende",
    ]
    revision = await editor.add_slice(revision, "Vorab", index=0)
    await editor.add_slice(revision, "Danach", index=2)
    assert await _ordered_titles(db, SliceEntity) == ["Vorab", "Kern", "Danach"]
    assert [a.position for a in await _all(db, ActivityEntity)] == [2, 4, 1, 3, 5]


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


async def test_description_is_free_text_with_a_length_limit(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.update_story(
        1, story.id, {"description": "Zeile eins\n- Punkt"}
    )
    assert (await _all(db, StoryEntity))[0].description == "Zeile eins\n- Punkt"
    with pytest.raises(MapEditError, match="Beschreibung"):
        await editor.update_story(revision, story.id, {"description": "x" * 4001})


async def test_several_stories_change_in_one_revision(db, editor) -> None:
    first, second = await _all(db, StoryEntity)
    revision = await editor.update_stories(
        1,
        {
            first.id: {"title": "Eins", "description": "Text"},
            second.id: {"goal": "neu ordnen"},
        },
    )
    assert revision == 2
    first, second = await _all(db, StoryEntity)
    assert (first.title, first.description, second.goal) == (
        "Eins",
        "Text",
        "neu ordnen",
    )
    with pytest.raises(MapEditError):
        await editor.update_stories(revision, {first.id: {"role": ""}})
    assert await editor.update_stories(revision, {first.id: {"title": "Eins"}}) == 2


async def test_new_stories_get_fresh_keys_and_the_user_origin(db, editor) -> None:
    task = (await _all(db, TaskEntity))[0]
    await editor.add_story(1, task.id, None)
    story = (await _all(db, StoryEntity))[-1]
    assert (story.key, story.origin) == ("US-03", Origin.USER)
    assert story.title == NEW_STORY_TITLE
    assert "scope" not in story.to_dict()


async def test_a_typed_title_names_the_new_story(db, editor) -> None:
    task = (await _all(db, TaskEntity))[0]
    revision = await editor.add_story(1, task.id, None, "  Zählerstand melden ")
    await editor.add_story(revision, task.id, None, "x" * 400)
    titles = [s.title for s in await _all(db, StoryEntity)][-2:]
    assert titles == ["Zählerstand melden", "x" * 300]


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


async def test_move_story_to_another_task_and_slice(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    other_task = (await _all(db, TaskEntity))[1]
    sl = (await _all(db, SliceEntity))[0]
    assert await editor.move_story(1, story.id, other_task.id, sl.id) == 2
    moved = (await _all(db, StoryEntity))[0]
    assert (moved.task_id, moved.slice_id) == (other_task.id, sl.id)


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
        editor.update_story(revision, story.id, {"title": "x"}),
        editor.split_story(revision, story.id),
    ):
        with pytest.raises(MapEditError):
            await call
    assert await _revision(db) == revision


async def test_edits_without_a_change_keep_the_revision(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    assert await editor.update_story(1, story.id, {"title": story.title}) == 1
    assert len(await _all(db, MapRevisionEntity)) == 1


async def test_split_and_new_stories_get_distinct_positions(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.split_story(1, story.id)
    await editor.add_story(revision, story.task_id, None)
    positions = [s.position for s in await _all(db, StoryEntity)]
    assert len(set(positions)) == len(positions)


async def test_an_archived_story_returns_under_a_live_task(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    revision = await editor.archive_story(1, story.id)
    target = (await _all(db, TaskEntity))[1]
    revision = await editor.unarchive_story(revision, story.id, target.id)
    restored = (await _all(db, StoryEntity))[0]
    assert restored.archived_at is None
    assert (restored.task_id, restored.key) == (target.id, story.key)
    assert revision == 3


async def test_a_story_cannot_return_to_an_archived_task_or_twice(db, editor) -> None:
    first, second = (await _all(db, StoryEntity))[:2]
    revision = await editor.archive_story(1, first.id)
    revision = await editor.archive_story(revision, second.id)
    gone = (await _all(db, ActivityEntity))[1]
    revision = await editor.archive_activity(revision, gone.id)
    with pytest.raises(MapEditError, match=NOT_FOUND):
        await editor.unarchive_story(revision, first.id, second.task_id)
    live = (await _all(db, TaskEntity))[0]
    revision = await editor.unarchive_story(revision, first.id, live.id)
    with pytest.raises(MapEditError, match=NOT_ARCHIVED):
        await editor.unarchive_story(revision, first.id, live.id)
    assert (await _all(db, StoryEntity))[1].archived_at is not None


async def test_a_story_returns_without_the_slice_that_was_deleted(db, editor) -> None:
    story = (await _all(db, StoryEntity))[0]
    kern = (await _all(db, SliceEntity))[0]
    revision = await editor.move_story(1, story.id, story.task_id, kern.id)
    revision = await editor.archive_story(revision, story.id)
    revision = await editor.delete_slice(revision, kern.id)
    await editor.unarchive_story(revision, story.id, story.task_id)
    sliced = story
    restored = next(s for s in await _all(db, StoryEntity) if s.id == sliced.id)
    assert restored.archived_at is None
    assert restored.slice_id is None
