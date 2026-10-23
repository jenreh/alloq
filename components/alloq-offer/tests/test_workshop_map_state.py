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
from alloq_offer.workshop.components import map_view, story_drawer
from alloq_offer.workshop.components.draft_tab import draft_tab
from alloq_offer.workshop.services.map_apply import apply_proposed_map, snapshot_map
from alloq_offer.workshop.services.map_edit import MapEditor
from alloq_offer.workshop.services.map_view import NO_SLICE_TITLE, build_view
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import map_state
from alloq_offer.workshop.states.map_state import SAVE_ERROR, MapState

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


# --- the state ---------------------------------------------------------------


async def test_load_fills_the_grid_and_summary(db, seeded) -> None:
    state = await _loaded(db)
    assert state.has_map
    assert state.summary == "2 Aktivitäten · 2 Stories · Revision 1"
    assert state.grid_template == "200px repeat(2, minmax(230px, 1fr))"
    assert state.grid_min_width == "660px"
    assert not state.has_selection


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
        await _run(state.rename_activity, first, "Anfrage")
        await _run(state.move_activity, first, 1)
        assert "Stories" in await _run(state.archive_activity, first)
        await _run(state.add_slice, {"title": "Später"})
        slice_id = state.rows[1]["slice_id"]
        await _run(state.rename_slice, slice_id, "Zweite Version")
    assert [c["title"] for c in state.columns] == ["Bearbeitung", "Anfrage"]
    assert [r["title"] for r in state.rows][:2] == ["Kern", "Zweite Version"]


async def test_story_edits_through_the_drawer(db, seeded) -> None:
    state = await _loaded(db)
    story_id = int(next(iter(state.stories)))
    state.select_story(story_id)
    with _as_editor(state, db):
        await _run(state.save_story_field, "title", "Umbenannt")
        revision = state.revision
        await _run(state.save_story_field, "title", "Umbenannt")
        assert state.revision == revision
        assert "Akzeptanzkriterien" in await _run(
            state.save_story_field, "goal", "x mit Akzeptanzkriterien"
        )
        await _run(state.set_scope, "angeboten")
        await _run(state.set_scope, "unbekannt")
        other_task = state.task_options[1]["value"]
        await _run(state.place_story, other_task, "0")
        await _run(state.split_selected)
        await _run(state.archive_selected)
    story = state.stories.get(str(story_id))
    assert story is None
    assert not state.has_selection
    assert state.story_count == 2


async def test_story_handlers_ignore_calls_without_a_selection(db, seeded) -> None:
    state = await _loaded(db)
    with _as_editor(state, db):
        for handler, args in (
            (state.save_story_field, ("title", "x")),
            (state.set_scope, ("angeboten",)),
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
        assert map_state.NO_TASK in await _run(state.add_story, 0, 0)
        await _run(state.add_story, cell["task_id"], state.rows[0]["slice_id"])
    assert state.story_count == 3


# --- components --------------------------------------------------------------


def test_map_and_drawer_render_constants() -> None:
    section = str(map_view.map_section())
    assert map_view.MAP_TITLE in section
    assert map_view.CORNER_LABELS[1] in section
    assert "grid_template" in section
    assert story_drawer.SPLIT in str(story_drawer.story_drawer())
    assert "has_map" in str(draft_tab())
