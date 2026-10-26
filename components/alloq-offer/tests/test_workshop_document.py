# ruff: noqa: ARG001
"""Kapitel tab as a document: render data, outline and module handlers, components."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.workshop.ai.schemas import ProposedTable
from alloq_offer.workshop.components import chapters_tab
from alloq_offer.workshop.components.chapters import (
    dialogs,
    document,
    labels,
    outline,
    panel,
)
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.schema import (
    MAX_CELL,
    MAX_TABLE_ROWS,
    CalcContent,
    CalcRow,
    ProseContent,
    Run,
    StoriesContent,
    TableContent,
)
from alloq_offer.workshop.export.models import ResolvedStory, ResolvedValue
from alloq_offer.workshop.services.chapter_document import (
    free_fields,
    load_document,
    render_block,
)
from alloq_offer.workshop.services.chapters import CONFLICT, ChapterService
from alloq_offer.workshop.services.outline import REQUIRED, TITLE_NEEDED, OutlineService
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import chapter_state, outline_mixin
from alloq_offer.workshop.states.chapter_state import ChapterState
from alloq_offer.workshop.template_entities import ChapterBlockEntity

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.chapter_state"
DOCUMENT_STATEMENTS = 6


def _u(text: str) -> str:
    """How ``str(component)`` writes a German text."""
    return json.dumps(text)[1:-1]


def _shows(text: str, event: str) -> bool:
    return text in event or _u(text) in event


@contextmanager
def _as_editor(state: ChapterState, db):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=1)

    registry = MagicMock()
    registry.get.return_value = WorkshopConfig()
    object.__setattr__(state, "get_state", _get_state)
    with (
        patch(f"{MODULE}.get_asyncdb_session", db.session),
        patch(f"{MODULE}.service_registry", return_value=registry),
    ):
        try:
            yield
        finally:
            object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> str:
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    result = await result
    return "" if result is None else str(result)


async def _loaded(db) -> ChapterState:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    state = ChapterState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        await _run(state.load_chapters)
    return state


def _keys(state: ChapterState) -> list[str]:
    return [c["key"] for c in state.chapters]


# --- render data ---------------------------------------------------------------


def test_render_block_per_type() -> None:
    stories = [
        ResolvedStory(
            "US-01", "Erfassen", "Als A möchte ich b, um c.", "Aufnehmen", ""
        ),
        ResolvedStory("US-02", "Prüfen", "Als A möchte ich d, um e.", "", "Erster", 1),
        ResolvedStory("US-03", "Planen", "Als A möchte ich f, um g.", "", "Zweiter", 2),
        ResolvedStory("US-04", "Melden", "Als A möchte ich h, um i.", "", "Vorher", 0),
    ]
    values = {"offer.person_days": ResolvedValue("10 PT", confirmed=False)}
    prose = render_block(
        ProseContent.model_validate(
            {"blocks": [{"type": "paragraph", "runs": [{"text": "A < B"}]}]}
        ),
        stories,
        values,
    )
    assert prose == {"html": "<p>A &lt; B</p>"}
    table = render_block(
        TableContent(columns=["A", "B"], rows=[[[Run(text="1")], [Run(text="2")]]]),
        stories,
        values,
    )
    assert table == {"columns": ["A", "B"], "rows": [["1", "2"]]}
    calc = render_block(
        CalcContent(rows=[CalcRow(label="Tage", field="offer.person_days")]),
        stories,
        values,
    )
    assert calc["values"][0]["value"] == "10 PT [nicht bestätigt]"
    by_activity = render_block(StoriesContent(), stories, values)
    assert [g["title"] for g in by_activity["groups"]] == [
        "Aufnehmen",
        "Ohne Zuordnung",
    ]
    by_slice = render_block(StoriesContent(group_by="slice"), stories, values)
    assert [g["title"] for g in by_slice["groups"]] == [
        "Vorher",
        "Erster",
        "Zweiter",
        "Ohne Zuordnung",
    ]
    assert free_fields(calc["values"])[0]["value"] == "offer.risk_buffer_days"


async def test_load_document_has_frame_and_blocks(db) -> None:  # noqa: ANN001
    assert await load_document(db.session, 1, "Anna") is None
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    loaded = await load_document(db.session, 1, "Anna")
    assert loaded is not None
    assert loaded.frame_before == ["Rechtlicher Hinweis", "Inhaltsverzeichnis"]
    assert loaded.frame_after[-1] == "Unterschriften"
    by_key = {c["key"]: c for c in loaded.chapters}
    assert by_key["management_summary"]["html"] == ""
    assert by_key["mitwirkung"]["columns"] == [
        "Mitwirkung",
        "Verantwortlich",
        "Zeitpunkt",
    ]
    assert by_key["verguetung"]["values"][0]["label"] == "Personentage"
    assert by_key["user_stories"]["groups"] == []
    assert by_key["user_stories"]["number"] == "2.1"


async def test_load_document_brings_everything_the_tab_needs_in_one_session(
    db,  # noqa: ANN001
) -> None:
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    service = ChapterService(db.session, 1, "Anna")
    await service.open()
    await OutlineService(db.session, 1, "Anna").remove_chapter("annahmen_risiken")
    await load_document(db.session, 1, "Anna")  # fills the template and map caches
    with db.round_trips() as trips:
        loaded = await load_document(db.session, 1, "Anna")
    # Was 5 sessions with 19 statements.
    assert (trips.sessions, trips.statements) == (1, DOCUMENT_STATEMENTS)
    assert loaded is not None
    assert loaded.removed == [
        {"key": "annahmen_risiken", "title": "Annahmen und Risiken"}
    ]
    assert loaded.draft_job == ""
    assert loaded.details["laufzeit"] == await service.load("laufzeit")
    assert "annahmen_risiken" not in loaded.details


# --- state ---------------------------------------------------------------------


async def test_load_fills_the_document_and_selection(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    assert state.frame_after[0] == "Rechtliche Bestimmungen"
    assert state.active_key == "management_summary"
    assert state.is_first
    assert not state.is_last
    assert state.chapter_ids == _keys(state)
    state.clear_selection()
    assert (state.active_key, state.has_active) == ("", False)
    with _as_editor(state, db):
        events = await _run(state.jump_to, "laufzeit")
    assert state.active_key == "laufzeit"
    assert chapter_state.BLOCK_ID_PREFIX + "laufzeit" in events


async def test_autosave_updates_the_block_html(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.autosave, "management_summary", "<p>Neu</p>")
    block = next(c for c in state.chapters if c["key"] == "management_summary")
    assert block["html"] == "<p>Neu</p>"


async def test_reorder_and_move_buttons(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.reorder, "verguetung", 0)
        assert _keys(state)[0] == "verguetung"
        await _run(state.select_chapter, "verguetung")
        await _run(state.move_active, 1)
        assert _keys(state)[1] == "verguetung"
        state.clear_selection()
        assert await _run(state.move_active, 1) == ""


async def test_add_dialog_inserts_blocks_and_blank_chapters(db) -> None:  # noqa: ANN001
    async with db.session() as session:
        session.add(
            ChapterBlockEntity(
                key="datenschutz",
                title="Datenschutz",
                chapter_type="prose",
                default_content={"chapter_type": "prose"},
                guiding_question="Wie schützen wir Daten?",
            )
        )
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.open_add)
        assert state.add_open
        assert state.add_tab == outline_mixin.TAB_LIBRARY
        assert [b["key"] for b in state.library] == ["datenschutz"]
        toast = await _run(state.add_block, "datenschutz")
        assert _shows(outline_mixin.ADDED, toast)
        assert not state.add_open
        assert _keys(state)[1] == state.active_key
        await _run(state.open_add)
        assert state.add_tab == outline_mixin.TAB_BLANK
        state.set_add_tab(outline_mixin.TAB_BLANK)
        state.set_blank_title("Glossar")
        state.set_blank_type("table")
        await _run(state.add_blank)
        assert state.active["title"] == "Glossar"
        assert state.active["type"] == "table"
        await _run(state.open_add)
        state.set_blank_title("   ")
        toast = await _run(state.add_blank)
        assert _shows(TITLE_NEEDED, toast)
        assert state.add_open
        state.close_add()
    assert not state.add_open


async def test_remove_confirm_and_restore(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "leistungen")
        state.ask_remove()
        assert state.remove_open
        state.cancel_remove()
        assert not state.remove_open
        state.ask_remove()
        await _run(state.remove_active)
        assert not state.remove_open
        assert "leistungen" not in _keys(state)
        assert state.has_removed
        assert state.active_key == ""
        await _run(state.restore_chapter, "leistungen")
        assert _keys(state)[-1] == "leistungen"
        assert not state.has_removed
        await _run(state.select_chapter, "management_summary")
        toast = await _run(state.remove_active)
    assert _shows(REQUIRED, toast)


async def test_rename_and_level(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "loesung")
        assert await _run(state.rename_active, "Angebotene Lösung") == ""
        await _run(state.rename_active, "Unsere Lösung")
        assert state.active["title"] == "Unsere Lösung"
        await _run(state.set_active_level, "1")
        assert state.active["level"] == 1
        assert state.active["number"] == "3"


async def test_outline_errors_show_a_toast(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with (
        _as_editor(state, db),
        patch.object(
            OutlineService, "move_chapter", AsyncMock(side_effect=RuntimeError("x"))
        ),
    ):
        toast = await _run(state.reorder, "laufzeit", 0)
    assert _shows(chapter_state.SAVE_ERROR, toast)
    with (
        _as_editor(state, db),
        patch.object(OutlineService, "library", AsyncMock(side_effect=RuntimeError)),
    ):
        await _run(state.open_add)
    assert state.library == []


async def test_story_grouping_is_stored(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "user_stories")
        await _run(state.set_group_by, "unbekannt")
        assert state.revision == 1
        await _run(state.set_group_by, "slice")
        assert state.active["group_by"] == "slice"
        assert state.revision == 2
        await _run(state.add_row)  # not a table: nothing happens
    assert state.revision == 2


async def test_table_edits(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "mitwirkung")
        await _run(state.add_row)
        assert state.active["rows"] == [["", "", ""]]
        await _run(state.set_cell, 0, 1, " Kunde ")
        assert state.active["rows"][0][1] == "Kunde"
        revision = state.revision
        await _run(state.set_cell, 0, 1, "Kunde")
        await _run(state.set_cell, 5, 1, "x")
        assert state.revision == revision
        await _run(state.add_column)
        assert state.active["columns"][-1] == "Neue Spalte"
        await _run(state.rename_column, 3, "Hinweis")
        await _run(state.rename_column, 3, "  ")
        assert state.active["columns"][-1] == "Hinweis"
        await _run(state.remove_row, 0)
        assert state.active["rows"] == []
        await _run(state.remove_row, 3)
        assert state.save_label == chapter_state.SAVED


async def test_value_edits(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "verguetung")
        assert [f["value"] for f in state.free_fields] == [
            "workspace.currency",
            "workspace.validity_date",
        ]
        await _run(state.add_value, "workspace.validity_date")
        assert state.active["values"][-1]["label"] == "Bindefrist"
        await _run(state.add_value, "workspace.validity_date")
        await _run(state.add_value, "offer.gibt_es_nicht")
        assert len(state.active["values"]) == 5
        await _run(state.remove_value, 0)
        assert state.active["values"][0]["label"] == "Risikopuffer (Personentage)"
        await _run(state.remove_value, 9)
    assert len(state.active["values"]) == 4


async def test_module_edit_conflict_reloads(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "mitwirkung")
    await ChapterService(db.session, 1, "Ben").save(
        "mitwirkung", 1, TableContent(columns=["A"])
    )
    with _as_editor(state, db):
        toast = await _run(state.add_row)
    assert _shows(CONFLICT, toast)
    assert state.save_label == chapter_state.CONFLICT_LABEL
    assert state.active["columns"] == ["A"]


# --- components ----------------------------------------------------------------


def test_tab_renders_outline_document_panel_and_dialogs() -> None:
    tab = str(chapters_tab.chapters_tab())
    for handler in (
        "reorder",
        "jump_to",
        "open_add",
        "add_block",
        "add_blank",
        "remove_active",
        "restore_chapter",
        "rename_active",
        "set_active_level",
        "move_active",
        "autosave",
        "accept_proposal",
        "refresh_drafts",
        "clear_selection",
    ):
        assert handler in tab, handler
    assert "SortableList" in tab
    assert "ChapterEditor" in tab
    assert _u(labels.FRAME_NOTE) in tab
    assert _u(outline.TITLE) in tab
    assert _u(document.ADD_CHAPTER) in tab
    assert _u(panel.REMOVE) in tab
    assert _u(dialogs.ADD_TITLE) in tab
    assert _u(dialogs.REMOVE_TITLE) in tab


def test_each_module_has_its_toolbar() -> None:
    page = str(document.document())
    for handler in (
        "draft_active",
        "add_row",
        "add_column",
        "set_cell",
        "rename_column",
        "set_group_by",
        "add_value",
        "remove_value",
    ):
        assert handler in page, handler
    assert "aq-doc-float" in page


async def test_browser_values_that_are_no_numbers_change_nothing(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    keys = _keys(state)
    with _as_editor(state, db):
        assert await _run(state.reorder, "laufzeit", "oben") == ""
        assert await _run(state.set_active_level, "x") == ""
        await _run(state.select_chapter, "mitwirkung")
        await _run(state.remove_row, "eins")
        await _run(state.set_cell, None, 0, "x")
    assert _keys(state) == keys
    assert state.revision == 1


async def test_tables_have_a_row_limit(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    full = TableContent(
        columns=["A"], rows=[[[Run(text="x")]] for _ in range(MAX_TABLE_ROWS)]
    )
    await ChapterService(db.session, 1, "Ben").save("mitwirkung", 1, full)
    with _as_editor(state, db):
        await _run(state.load_chapters)
        await _run(state.select_chapter, "mitwirkung")
        await _run(state.add_row)
    assert state.revision == 2
    assert len(state.active["rows"]) == MAX_TABLE_ROWS


async def test_a_failed_load_leaves_nothing_selected(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with (
        _as_editor(state, db),
        patch.object(ChapterService, "load", AsyncMock(side_effect=RuntimeError)),
    ):
        toast = await _run(state.select_chapter, "mitwirkung")
    assert _shows(chapter_state.LOAD_ERROR, toast)
    assert state.active_key == ""
    with _as_editor(state, db):
        assert await _run(state.add_row) == ""


def test_table_proposals_keep_the_cell_and_row_limits() -> None:
    proposed = ProposedTable(rows=[["x" * (MAX_CELL + 5)]] * (MAX_TABLE_ROWS + 3))
    content = proposed.to_content(["A"])
    assert len(content.rows) == MAX_TABLE_ROWS
    assert len(content.rows[0][0][0].text) == MAX_CELL


async def test_text_typed_before_the_selection_moved_is_saved(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    with _as_editor(state, db):
        await _run(state.select_chapter, "laufzeit")
        # The debounced save of the first chapter arrives after the click.
        await _run(state.autosave, "management_summary", "<p>Spät</p>")
    block = next(c for c in state.chapters if c["key"] == "management_summary")
    assert (block["revision"], block["html"]) == (2, "<p>Spät</p>")
    assert state.active_key == "laufzeit"
    assert state.revision == 1
    with _as_editor(state, db):
        assert await _run(state.autosave, "verguetung", "<p>x</p>") == ""


async def test_a_reload_keeps_the_editor_mounted(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    nonce = state.editor_nonce
    with _as_editor(state, db):
        await _run(state.autosave, "management_summary", "<p>Eins</p>")
        await _run(state.reorder, "laufzeit", 0)
    assert state.editor_nonce == nonce
    await ChapterService(db.session, 1, "Ben").save(
        "management_summary",
        2,
        ProseContent.model_validate(
            {"blocks": [{"type": "paragraph", "runs": [{"text": "Ben"}]}]}
        ),
    )
    with _as_editor(state, db):
        await _run(state.load_chapters)
    assert state.editor_nonce == nonce + 1
    assert state.order_version == 1


async def test_failed_edits_refresh_the_inputs(db) -> None:  # noqa: ANN001
    state = await _loaded(db)
    reset = state.input_reset
    with _as_editor(state, db):
        await _run(state.select_chapter, "mitwirkung")
        await _run(state.rename_column, 0, "  ")
        assert state.input_reset == reset + 1
        await _run(state.select_chapter, "loesung")
        await _run(state.rename_active, "")
        assert state.input_reset == reset + 2
        await _run(state.select_chapter, "mitwirkung")
        assert state.can_add_column
        for _ in range(5):
            await _run(state.add_column)
        assert not state.can_add_column


def test_blank_chapter_types_carry_the_plan_names() -> None:
    names = [option["label"] for option in labels.TYPE_OPTIONS]
    assert names == ["Text", "Tabelle", "User Stories", "Werte"]
