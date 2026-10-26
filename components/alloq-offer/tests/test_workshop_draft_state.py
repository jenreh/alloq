# ruff: noqa: ARG001
"""Draft overview state, the "Entwurf" tab and the "Story Map" tab."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alloq_offer.workshop.ai.schemas import (
    ProposedActivity,
    ProposedMap,
    ProposedStory,
    ProposedTask,
)
from alloq_offer.workshop.components import (
    draft_tab,
    map_tab,
    sources_panel,
    workshop_view,
)
from alloq_offer.workshop.entities import JobEntity, JobStatus
from alloq_offer.workshop.pages import create_offer_workshop_page
from alloq_offer.workshop.services import draft_overview
from alloq_offer.workshop.services.exports import EXPORT_JOB
from alloq_offer.workshop.services.map_apply import apply_proposed_map
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import draft_state
from alloq_offer.workshop.states.draft_state import DraftState
from alloq_offer.workshop.states.sources_state import SourcesState
from alloq_offer.workshop.states.workshop_state import TAB_MAP, TABS
from sqlalchemy import event

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.draft_state"
# Was 16; every statement is a round trip to the database.
OVERVIEW_STATEMENTS = 8


@contextmanager
def _as_editor(state: DraftState, db):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else SimpleNamespace(offer_id=1)

    object.__setattr__(state, "get_state", _get_state)
    with patch(f"{MODULE}.get_asyncdb_session", db.session):
        try:
            yield
        finally:
            object.__delattr__(state, "get_state")


async def _run(handler: Any, *args: Any) -> list[Any]:
    return [i async for i in handler(*args) if i is not None]


def _story(title: str, *, skeleton: bool) -> ProposedStory:
    return ProposedStory(
        title=title,
        role="Kunde",
        goal=f"{title.lower()} erledigen",
        benefit="Zeit zu sparen",
        skeleton=skeleton,
    )


async def _with_map(db) -> DraftState:  # noqa: ANN001
    async with db.session() as session:
        workspace = await open_workspace(session, 1, "Anna")
        await apply_proposed_map(
            session,
            workspace,
            ProposedMap(
                activities=[
                    ProposedActivity(
                        title="Melden",
                        tasks=[
                            ProposedTask(
                                title="Zählerstand",
                                stories=[
                                    _story("Stand melden", skeleton=True),
                                    _story("Foto hochladen", skeleton=False),
                                ],
                            )
                        ],
                    )
                ]
            ),
            set(),
        )
    return DraftState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]


async def test_overview_counts_and_lists_open_decisions(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    with _as_editor(state, db):
        assert await _run(state.load_overview) == []
    assert (state.activities, state.stories) == (1, 2)
    assert state.map_revision == 1
    assert not state.started
    assert not state.has_draft_file
    assert state.counts[1] == {"label": "Stories", "value": "2"}
    assert [d["title"] for d in state.decisions] == ["Kalkulation bestätigen"]
    assert "Angeboten" not in {c["label"] for c in state.counts}


async def test_overview_loads_with_few_statements(db) -> None:  # noqa: ANN001
    await _with_map(db)
    statements: list[str] = []

    def _count(*args: Any) -> None:
        statements.append(args[2])

    event.listen(db.engine.sync_engine, "before_cursor_execute", _count)
    try:
        async with db.session() as session:
            overview = await draft_overview.load_overview(session, 1)
    finally:
        event.remove(db.engine.sync_engine, "before_cursor_execute", _count)
    assert (overview.activities, overview.stories) == (1, 2)
    assert len(statements) <= OVERVIEW_STATEMENTS


async def test_overview_shows_the_latest_job_of_each_stage(db) -> None:  # noqa: ANN001
    await _with_map(db)
    async with db.session() as session:
        for status in (JobStatus.FAILED, JobStatus.RUNNING):
            session.add(
                JobEntity(
                    offer_id=1,
                    kind=EXPORT_JOB,
                    status=status,
                    idempotency_key=f"export-{status}",
                    run_after=datetime.now(UTC),
                )
            )
    async with db.session() as session:
        overview = await draft_overview.load_overview(session, 1)
    statuses = {stage["label"]: stage["status"] for stage in overview.stages}
    assert statuses["Word-Entwurf"] == draft_overview.RUNNING
    assert statuses["Kapitel schreiben"] == draft_overview.OPEN
    assert overview.working


def test_draft_tab_does_not_wait_for_the_map() -> None:
    state = DraftState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    assert not state.has_map
    state.map_revision = 2
    assert state.has_map
    assert "MapState" not in draft_tab.draft_tab.__code__.co_names


def test_page_loads_the_draft_tab_first_and_slow_tabs_last() -> None:
    with patch("alloq_offer.workshop.pages.app_page") as app_page:
        create_offer_workshop_page(MagicMock())
    names = [h.fn.__name__ for h in app_page.call_args.kwargs["on_load"]]
    assert names[:3] == ["load_workshop", "load_overview", "load_sources"]
    # The checks change the blockers the draft tab lists; it refreshes after them.
    assert names[-3:] == ["load_chapters", "run_checks", "load_overview"]


async def test_a_changed_stage_refreshes_the_other_tabs(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    state.stages = [{"label": "x", "status": draft_overview.RUNNING}]
    with _as_editor(state, db):
        events = await _run(state.load_overview)
    assert events == [draft_state.REFRESH]


async def test_load_errors_show_a_toast(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    with (
        _as_editor(state, db),
        patch(f"{MODULE}.draft_overview.load_overview", side_effect=RuntimeError),
        patch(f"{MODULE}.rx.toast.error") as error,
    ):
        await _run(state.load_overview)
    error.assert_called_once_with(draft_state.LOAD_ERROR, position="top-right")


def test_map_and_draft_are_separate_tabs() -> None:
    assert {"value": TAB_MAP, "label": "Story Map"} in TABS
    assert "map_tab" in workshop_view._workshop_content.__code__.co_names  # noqa: SLF001
    draft = str(draft_tab.draft_tab())
    assert "confirm_scope" not in draft
    assert "load_overview" in draft
    assert "aq-split" in draft
    assert "map_section" not in draft_tab.__dict__
    rendered = str(map_tab.map_tab())
    assert "has_selection" in rendered
    assert "has_map" in rendered
    assert "aq-map-main" in rendered
    scope = str(workshop_view.workshop_scope())
    assert "aq-scopebar" in scope
    assert "set_map_search" in scope


def test_pipeline_progress_counts_finished_stages() -> None:
    state = DraftState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    assert state.pipeline_progress == 0
    state.stages = [
        {"label": "a", "status": draft_overview.DONE},
        {"label": "b", "status": draft_overview.RUNNING},
        {"label": "c", "status": draft_overview.OPEN},
        {"label": "d", "status": draft_overview.OPEN},
    ]
    assert state.pipeline_progress == 25  # noqa: PLR2004
    assert "pipeline_progress" in str(draft_tab.progress_card())


def test_sources_panel_shows_reading_progress() -> None:
    state = SourcesState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    assert (state.reading, state.read_progress) == (False, 0)
    state.sources = [{"working": False}, {"working": True}, {"working": True}]
    assert state.reading
    assert state.read_progress == 33  # noqa: PLR2004
    assert state.read_label == "1 von 3 Quellen gelesen"
    assert "read_progress" in str(sources_panel.sources_panel())
