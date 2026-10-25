# ruff: noqa: ARG001
"""Tests of the map view model, the map state and its components."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_offer.workshop.ai.schemas import (
    ProposedActivity,
    ProposedMap,
    ProposedStory,
    ProposedTask,
)
from alloq_offer.workshop.components import (
    archive_dialog,
    map_list,
    map_view,
    story_drawer,
)
from alloq_offer.workshop.components.draft_tab import draft_tab
from alloq_offer.workshop.services.map_apply import apply_proposed_map, snapshot_map
from alloq_offer.workshop.services.map_edit import MapEditor
from alloq_offer.workshop.services.map_view import (
    NO_SLICE_TITLE,
    build_view,
    filter_rows,
)
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import map_state
from alloq_offer.workshop.states.map_state import (
    PICK_TASK,
    RESTORED,
    SAVE_ERROR,
    MapState,
)

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.map_state"


def _story(title: str, **over: Any) -> ProposedStory:
    return ProposedStory(
        title=title,
        role="Disponent",
        goal="Anfragen ordnen",
        benefit="besser zu planen",
        origin="Kunde",
        source_refs=[1],
        **over,
    )


@pytest.fixture
async def seeded(db) -> None:
    proposal = ProposedMap(
        activities=[
            ProposedActivity(
                title="Eingang",
                tasks=[
                    ProposedTask(
                        title="Prüfen",
                        stories=[_story("Erste", slice="Kern", skeleton=True)],
                    )
                ],
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


@contextmanager
def _as_editor(state: MapState, db, offer_id: int = 1):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=offer_id)

    object.__setattr__(state, "get_state", _get_state)
    with patch(f"{MODULE}.get_asyncdb_session", db.session):
        try:
            yield
        finally:
            object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""


def _state() -> MapState:
    return MapState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]


async def _loaded(db) -> MapState:  # noqa: ANN001
    state = _state()
    with _as_editor(state, db):
        await _run(state.load_map)
    return state


# --- the view model -----------------------------------------------------------


async def test_view_puts_stories_in_activity_columns_and_slice_rows(db, seeded) -> None:
    async with db.session() as session:
        workspace = await open_workspace(session, 1, "")
        view = build_view(await snapshot_map(session, workspace))
    assert [c["title"] for c in view["columns"]] == ["Eingang", "Bearbeitung"]
    assert [(c["first"], c["last"]) for c in view["columns"]] == [
        (True, False),
        (False, True),
    ]
    assert [r["title"] for r in view["rows"]] == ["Kern", NO_SLICE_TITLE]
    kern, none = view["rows"]
    assert [s["title"] for s in kern["cells"][0]["stories"]] == ["Erste"]
    assert kern["cells"][0]["stories"][0]["skeleton"]
    assert [s["title"] for s in none["cells"][1]["stories"]] == ["Zweite"]
    assert kern["cells"][1]["stories"] == []
    assert view["story_count"] == 2
    first = view["stories"][str(kern["cells"][0]["stories"][0]["id"])]
    assert (first["role"], first["slice_id"]) == ("Disponent", str(kern["slice_id"]))
    assert first["refs"] == "1 Quellenstellen"
    assert [o["label"] for o in view["task_options"]] == [
        "Eingang · Prüfen",
        "Bearbeitung · Ordnen",
    ]
    assert view["slice_options"][0]["label"] == NO_SLICE_TITLE


async def test_archived_activities_and_stories_leave_the_view(db, seeded) -> None:
    editor = MapEditor(db.session, 1, "Anna")
    state = await _loaded(db)
    story_id = int(next(iter(state.stories)))
    revision = await editor.archive_story(state.revision, story_id)
    async with db.session() as session:
        view = build_view(
            await snapshot_map(session, await open_workspace(session, 1, ""))
        )
    assert view["story_count"] == 1
    assert revision == 2


async def test_archived_stories_are_listed_with_their_place(db, seeded) -> None:
    state = await _loaded(db)
    story_id = int(next(iter(state.stories)))
    await MapEditor(db.session, 1, "Anna").archive_story(state.revision, story_id)
    async with db.session() as session:
        view = build_view(
            await snapshot_map(session, await open_workspace(session, 1, ""))
        )
    assert [(s["id"], s["where"]) for s in view["archived"]] == [
        (story_id, "Eingang · Prüfen")
    ]


def _filter_rows() -> list[dict[str, Any]]:
    def story(key: str, title: str, *, skeleton: bool) -> dict[str, Any]:
        return {"key": key, "title": title, "skeleton": skeleton}

    return [
        {
            "slice_id": 1,
            "cells": [
                {"stories": [story("S-1", "Anfrage erfassen", skeleton=True)]},
                {"stories": [story("S-2", "Termin buchen", skeleton=False)]},
            ],
        },
        {
            "slice_id": 0,
            "cells": [
                {"stories": []},
                {"stories": [story("S-3", "Bericht", skeleton=False)]},
            ],
        },
    ]


def _titles(rows: list[dict[str, Any]]) -> list[list[str]]:
    return [[s["title"] for c in r["cells"] for s in c["stories"]] for r in rows]


def test_filter_rows_without_filters_keeps_every_story() -> None:
    rows = _filter_rows()
    assert _titles(filter_rows(rows)) == _titles(rows)
    assert [r["count_label"] for r in filter_rows(rows)] == ["2 Stories", "1 Story"]


def test_filter_rows_by_text_skeleton_and_slice() -> None:
    rows = _filter_rows()
    assert _titles(filter_rows(rows, search=" termin ")) == [["Termin buchen"], []]
    assert _titles(filter_rows(rows, search="s-3")) == [[], ["Bericht"]]
    skeleton = filter_rows(rows, skeleton_only=True)
    assert _titles(skeleton) == [["Anfrage erfassen"], []]
    assert [r["count_label"] for r in skeleton] == ["1 Story", "0 Stories"]
    only_none = filter_rows(rows, slice_ids=["0"])
    assert [r["slice_id"] for r in only_none] == [0]
    assert len(only_none[0]["cells"]) == 2


# --- the state ---------------------------------------------------------------


async def test_load_fills_the_grid_and_summary(db, seeded) -> None:
    state = await _loaded(db)
    assert state.has_map
    assert state.summary == "2 Aktivitäten · 2 Stories · Revision 1"
    first, second = (c["id"] for c in state.columns)
    assert state.grid_template == (
        f"var(--grid-col-{first}, 230px) var(--grid-col-{second}, 230px)"
    )
    assert [r["count_label"] for r in state.rows] == ["1 Story", "1 Story"]
    assert not state.has_selection


async def test_filters_narrow_the_visible_rows(db, seeded) -> None:
    state = await _loaded(db)
    assert _titles(state.visible_rows) == _titles(state.rows)
    assert not state.is_filtered
    state.set_map_search("zweite")
    assert state.is_filtered
    assert _titles(state.visible_rows) == [[], ["Zweite"]]
    state.set_map_search("")
    state.set_skeleton_only(True)
    assert _titles(state.visible_rows) == [["Erste"], []]
    state.set_skeleton_only(False)
    assert state.slice_filter_label == ""
    state.set_slice_filter([str(state.rows[0]["slice_id"])])
    assert state.slice_filter_label == '"Schnitte (1)"'
    assert [r["title"] for r in state.visible_rows] == ["Kern"]
    state.reset_filters()
    assert not state.is_filtered
    assert _titles(state.visible_rows) == _titles(state.rows)
    kern = str(state.rows[0]["slice_id"])
    state.toggle_slice(int(kern))
    assert state.collapsed_slices == [kern]
    state.toggle_slice(int(kern))
    assert state.collapsed_slices == []


async def test_load_does_nothing_without_a_workspace_or_offer(db) -> None:
    state = _state()
    with _as_editor(state, db):
        await _run(state.load_map)
    assert not state.has_map
    with _as_editor(state, db, offer_id=0):
        await _run(state.load_map)
    assert state.columns == []


async def test_load_reports_failures(db) -> None:
    state = _state()
    with (
        _as_editor(state, db),
        patch(
            f"{MODULE}.workspace_repo.find_by_offer",
            AsyncMock(side_effect=RuntimeError),
        ),
    ):
        assert map_state.LOAD_ERROR in await _run(state.load_map)


async def test_selecting_a_story_shows_its_sentence(db, seeded) -> None:
    state = await _loaded(db)
    story_id = int(next(iter(state.stories)))
    state.select_story(999)
    assert not state.has_selection
    state.select_story(story_id)
    assert state.has_selection
    assert state.selected["sentence"] == (
        "Als Disponent möchte ich Anfragen ordnen, um besser zu planen."
    )
    state.close_story()
    assert state.selected == {}


async def test_the_story_drawer_width_can_be_toggled(db, seeded) -> None:
    state = await _loaded(db)
    assert not state.drawer_wide
    state.toggle_drawer_width()
    assert state.drawer_wide
    state.toggle_drawer_width()
    assert not state.drawer_wide


async def test_a_selection_that_disappeared_is_cleared_on_reload(db, seeded) -> None:
    state = await _loaded(db)
    state.selected_id = "999"
    with _as_editor(state, db):
        await _run(state.load_map)
    assert state.selected_id == ""


async def test_adding_an_activity_reloads_the_map(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.add_activity, {"title": "Abschluss"})
    assert [c["title"] for c in state.columns][-1] == "Abschluss"
    assert state.revision == 2


async def test_the_edge_popup_inserts_at_its_position_and_closes(db, seeded) -> None:
    state = await _loaded(db)
    assert [c["index"] for c in state.columns] == [0, 1]
    assert [r["index"] for r in state.rows] == [0, 1]
    state.open_insert("activity:1")
    assert state.insert_at == "activity:1"
    with _as_editor(state, db):
        # The popup form sends only the name; the edge comes from insert_at.
        await _run(state.submit_insert, {"title": "Mitte"})
        assert state.insert_at == ""
        state.open_insert("slice:0")
        await _run(state.submit_insert, {"title": "Vorab"})
        state.open_insert("slice:0")
        assert "Namen" in await _run(state.submit_insert, {"title": " "})
    assert state.insert_at == "slice:0"
    state.close_insert()
    assert state.insert_at == ""
    assert [c["title"] for c in state.columns] == ["Eingang", "Mitte", "Bearbeitung"]
    assert [r["title"] for r in state.rows][:2] == ["Vorab", "Kern"]


async def test_submit_insert_needs_an_open_popup(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        for edge in ("", "activity", "activity:x", "story:0"):
            state.insert_at = edge
            assert await _run(state.submit_insert, {"title": "Neu"}) == ""
    assert state.revision == 1
    assert len(state.columns) == 2


async def test_a_stale_revision_gives_a_warning_and_the_current_map(db, seeded) -> None:
    state = await _loaded(db)
    state.revision = 0
    with _as_editor(state, db):
        toast = await _run(state.add_activity, {"title": "Neu"})
    assert "inzwischen geändert" in toast
    assert state.revision == 1
    assert len(state.columns) == 2


async def test_rejected_and_failing_edits_show_a_toast(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        assert "Namen" in await _run(state.add_activity, {"title": " "})
        with patch.object(MapEditor, "add_slice", AsyncMock(side_effect=RuntimeError)):
            assert SAVE_ERROR in await _run(state.add_slice, {"title": "x"})


async def test_edits_without_an_open_offer_do_nothing(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db, offer_id=0):
        assert await _run(state.add_activity, {"title": "x"}) == ""
    assert len(state.columns) == 2


async def test_activity_edits(db, seeded) -> None:
    state = await _loaded(db)
    first = state.columns[0]["id"]
    with _as_editor(state, db):
        await _run(state.rename_activity, first, "An\nfrage ")
        await _run(state.move_activity, first, 1)
        assert "Stories" in await _run(state.archive_activity, first)
        await _run(state.add_slice, {"title": "Später"})
        slice_id = state.rows[1]["slice_id"]
        await _run(state.rename_slice, slice_id, "Zweite Version")
        await _run(state.delete_slice, slice_id)
    assert [c["title"] for c in state.columns] == ["Bearbeitung", "An frage"]
    assert [r["title"] for r in state.rows][:2] == ["Kern", NO_SLICE_TITLE]


async def test_story_edits_through_the_drawer(db, seeded) -> None:
    state = await _loaded(db)
    story_id = int(next(iter(state.stories)))
    state.select_story(story_id)
    with _as_editor(state, db):
        form = {
            "title": "Um\nbenannt",
            "benefit": "besser\n zu planen",
            "description": "Mehr\ndazu",
        }
        assert map_state.SAVED in await _run(state.save_story, form)
        assert state.selected["title"] == "Um benannt"
        assert state.selected["benefit"] == "besser zu planen"
        assert state.selected["description"] == "Mehr\ndazu"
        form = {"title": "Umbenannt", "description": "Mehr dazu"}
        await _run(state.save_story, form)
        revision = state.revision
        await _run(state.save_story, form)
        assert state.revision == revision
        assert "Akzeptanzkriterien" in await _run(
            state.save_story, {"goal": "x mit Akzeptanzkriterien"}
        )
        other_task = state.task_options[1]["value"]
        await _run(state.place_story, other_task, "0")
        await _run(state.split_selected)
        await _run(state.archive_selected)
    story = state.stories.get(str(story_id))
    assert story is None
    assert not state.has_selection
    assert state.story_count == 2


async def test_list_rows_follow_the_activity_order_and_filters(db, seeded) -> None:
    state = await _loaded(db)
    assert [(r["activity"], r["title"]) for r in state.list_rows] == [
        ("Eingang", "Erste"),
        ("Bearbeitung", "Zweite"),
    ]
    assert state.list_rows[0]["story"].startswith("Als Disponent")
    state.set_map_search("zweite")
    assert [r["title"] for r in state.list_rows] == ["Zweite"]
    state.set_view("list")
    assert state.view == "list"
    state.set_view("unbekannt")
    assert state.view == "list"


async def test_list_edits_save_title_sentence_and_description(db, seeded) -> None:
    state = await _loaded(db)
    first, second = (str(r["id"]) for r in state.list_rows)
    with _as_editor(state, db):
        toast = await _run(
            state.apply_list_changes,
            [
                {"key": f"{first}|title", "value": "Erste neu"},
                {"key": f"{first}|description", "value": "Details"},
                {
                    "key": f"{second}|story",
                    "value": "Als Kunde möchte ich zahlen, um fertig zu sein.",
                },
                {"key": f"{second}|story", "value": "kein Satz"},
                {"key": "x|title", "value": "kaputt"},
                {"key": f"{first}|activity", "value": "nicht editierbar"},
            ],
        )
    assert "2" in toast
    assert state.revision == 2
    assert state.stories[first]["title"] == "Erste neu"
    assert state.stories[first]["description"] == "Details"
    assert state.stories[second]["role"] == "Kunde"
    with _as_editor(state, db):
        assert await _run(state.apply_list_changes, []) == ""
        assert "Feld" in await _run(
            state.apply_list_changes, [{"key": f"{first}|title", "value": " "}]
        )
    assert map_state.REJECTED_FORMAT.format(count=3) in str(state.notify_rejected(3))


async def test_story_handlers_ignore_calls_without_a_selection(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        for handler, args in (
            (state.save_story, ({"title": "x"},)),
            (state.place_story, ("1", "0")),
            (state.split_selected, ()),
            (state.archive_selected, ()),
        ):
            assert await _run(handler, *args) == ""
    assert state.revision == 1


async def test_adding_a_story_needs_a_task(db, seeded) -> None:
    state = await _loaded(db)
    cell = state.rows[0]["cells"][1]
    with _as_editor(state, db):
        for bad in ({}, {"task_id": "0"}, {"task_id": "x", "slice_id": "1"}):
            assert map_state.NO_TASK in await _run(state.add_story, bad)
        form = {
            "title": "Schnell erfasst",
            "task_id": str(cell["task_id"]),
            "slice_id": str(state.rows[0]["slice_id"]),
        }
        await _run(state.add_story, form)
        no_slice = {"title": "", "task_id": str(cell["task_id"]), "slice_id": "0"}
        await _run(state.add_story, no_slice)
    assert state.story_count == 4
    titles = {s["title"]: s["slice_id"] for s in state.stories.values()}
    assert titles["Schnell erfasst"] == str(state.rows[0]["slice_id"])
    assert titles["Neue Story"] == "0"


# --- components --------------------------------------------------------------


async def test_an_archived_story_is_restored_under_a_chosen_task(db, seeded) -> None:
    state = await _loaded(db)
    story_id = int(next(iter(state.stories)))
    with _as_editor(state, db):
        state.select_story(story_id)
        await _run(state.archive_selected)
        assert state.archive_label == "Archiv (1)"
        state.open_archive()
        assert state.archive_open
        assert [r["task"] for r in state.archived_rows] == [
            state.task_options[0]["value"]
        ]
        state.set_restore_task(story_id, "")
        assert PICK_TASK in await _run(state.restore_story, story_id)
        state.set_restore_task(story_id, state.task_options[1]["value"])
        assert RESTORED in await _run(state.restore_story, story_id)
    assert str(story_id) in state.stories
    assert state.archived == []
    assert state.restore_tasks == {}


async def test_the_old_task_is_no_default_when_it_is_gone(db, seeded) -> None:
    state = await _loaded(db)
    entry = {"id": 5, "task_id": "999", "key": "K", "title": "T", "where": "A · B"}
    state.archived = [entry]
    assert [r["task"] for r in state.archived_rows] == [""]
    state.set_archive_search("zzz")
    assert state.archived_rows == []
    state.set_archive_search(" a · b")
    assert len(state.archived_rows) == 1
    state.close_archive()
    assert (state.archive_open, state.archive_search) == (False, "")


async def test_restoring_an_unknown_story_does_nothing(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        assert await _run(state.restore_story, 99) == ""


def test_archive_button_and_dialog_render() -> None:
    assert "archive_label" in str(map_view.map_filter_row())
    dialog = str(archive_dialog.archive_dialog())
    assert "restore_story" in dialog
    assert "archived_rows" in dialog
    assert "set_restore_task" in dialog
    assert "set_archive_search" in dialog
    assert archive_dialog.EMPTY.split()[0] in dialog
    assert "archive_open" in str(map_view.map_section())


def test_map_and_drawer_render_constants() -> None:
    section = str(map_view.map_section())
    assert "aq-map-plus-head" not in section
    assert "tasks" not in section
    assert "meta" not in section
    assert '["scope"]' not in section
    assert "grid_template" in section
    assert "visible_rows" in section
    assert "aq-map-head" in section
    assert "aq-clamp-edit" in section
    assert "aq-map-band" in section
    assert "toggle_slice" in section
    assert "data-col-resize" in section
    assert "ColumnResize" in section
    assert "aq-story-card" in section
    assert "aq-add-story" in section
    assert '"task_id"' in section
    assert "aq-map-label" not in section
    assert "aq-clamp-view" in section
    assert "aq-map-footer" in section
    assert "aq-map-plus-x" in section
    assert "aq-map-plus-inline" in section
    assert "aq-map-plus-xl" in section
    assert "insert_at" in section
    assert map_view.CANCEL in section
    bar = str(map_view.map_filter_row())
    assert map_view.SEARCH_PLACEHOLDER in bar
    assert map_view.SKELETON_ONLY in bar
    assert "summary" in bar
    drawer = str(story_drawer.story_drawer())
    assert story_drawer.SPLIT in drawer
    assert story_drawer.SAVE in drawer
    assert "aq-insp-head" in drawer
    assert "aq-insp-foot" in drawer
    assert '["sentence"]' not in drawer
    assert "set_scope" not in drawer
    assert drawer.count("Textarea") >= 3
    assert '"description"' in drawer
    assert "archive_selected" in drawer
    assert "set_view" in bar
    assert "story-list-grid" in section
    rows = str(map_list.story_list())
    assert "apply_list_changes" in rows
    assert "resizeKey" in rows
    assert "data-col-resize" in rows
    assert "--grid-col-description" in map_list.TEMPLATE
    assert "data-read-only" in rows
    assert map_list.LIST_COLUMNS[2][1] in rows
    assert "has_map" in str(draft_tab())
