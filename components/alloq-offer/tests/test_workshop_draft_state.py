# ruff: noqa: ARG001
"""Draft overview state, the "Entwurf" tab and the "Story Map" tab."""

from contextlib import contextmanager
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
from alloq_offer.workshop.entities import Scope, StoryEntity
from alloq_offer.workshop.services import draft_overview
from alloq_offer.workshop.services.map_apply import apply_proposed_map
from alloq_offer.workshop.services.map_edit import CONFLICT
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import draft_state
from alloq_offer.workshop.states.draft_state import DraftState
from alloq_offer.workshop.states.sources_state import SourcesState
from alloq_offer.workshop.states.workshop_state import TAB_MAP, TABS
from sqlalchemy import select

from appkit_user.authentication.states import LoginState

MODULE = "alloq_offer.workshop.states.draft_state"


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


async def test_overview_counts_and_offers_the_scope_decision(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    with _as_editor(state, db):
        assert await _run(state.load_overview) == []
    assert (state.activities, state.stories, state.offered) == (1, 2, 0)
    assert state.map_revision == 1
    assert not state.started
    assert not state.has_draft_file
    assert state.counts[1] == {"label": "Stories", "value": "2"}
    assert [d["title"] for d in state.decisions] == [
        "Umfang bestätigen",
        "Kalkulation bestätigen",
    ]


async def test_a_changed_stage_refreshes_the_other_tabs(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    state.stages = [{"label": "x", "status": draft_overview.RUNNING}]
    with _as_editor(state, db):
        events = await _run(state.load_overview)
    assert events == [draft_state.REFRESH]


async def test_confirm_scope_offers_only_the_skeleton_stories(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    with _as_editor(state, db):
        await _run(state.load_overview)
        events = await _run(state.confirm_scope)
    assert len(events) == 2  # toast, then the map reload  # noqa: PLR2004
    async with db.session() as session:
        scopes = {
            s.title: s.scope for s in (await session.scalars(select(StoryEntity)))
        }
    assert scopes == {"Stand melden": Scope.OFFERED, "Foto hochladen": Scope.OPEN}
    assert state.offered == 1
    assert draft_overview.DECISION_SCOPE not in {d["key"] for d in state.decisions}


async def test_confirm_scope_on_a_stale_map_changes_nothing(db) -> None:  # noqa: ANN001
    state = await _with_map(db)
    with _as_editor(state, db):
        await _run(state.load_overview)
        state.map_revision = 0
        with patch(f"{MODULE}.rx.toast.warning") as warning:
            await _run(state.confirm_scope)
    warning.assert_called_once_with(CONFLICT, position="top-right")
    assert state.offered == 0


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
    assert "confirm_scope" in draft
    assert "load_overview" in draft
    assert "aq-split" in draft
    assert "map_section" not in draft_tab.__dict__
    rendered = str(map_tab.map_tab())
    assert "has_selection" in rendered
    assert "has_map" in rendered


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
