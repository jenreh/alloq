# ruff: noqa: ARG001
"""AI proposals for the map: request, job, comparison, take over, stale."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alloq_offer.workshop.ai.agents import PromptLoader, PydanticOfferAi
from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    MapRequest,
)
from alloq_offer.workshop.ai.render import render_map_request
from alloq_offer.workshop.ai.schemas import (
    ProposedActivity,
    ProposedMap,
    ProposedStory,
    ProposedTask,
)
from alloq_offer.workshop.components import map_proposal, map_view, story_drawer
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import (
    ActivityEntity,
    JobEntity,
    JobStatus,
    ProposalEntity,
    ProposalStatus,
    StoryEntity,
    TaskEntity,
)
from alloq_offer.workshop.jobs.propose_map import ProposeMapAdditions
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
)
from alloq_offer.workshop.services import map_proposals
from alloq_offer.workshop.services.map_edit import MapEditor
from alloq_offer.workshop.services.map_proposals import (
    MAP_PROPOSAL_JOB,
    MAP_TARGET,
    MapProposalError,
)
from alloq_offer.workshop.services.workspace import open_workspace
from alloq_offer.workshop.states import map_proposal_state
from alloq_offer.workshop.states.map_proposal_state import MapProposalState
from alloq_offer.workshop.states.map_state import MapState
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select

from appkit_user.authentication.states import LoginState

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
MODULE = "alloq_offer.workshop.states.map_proposal_state"


def _story(title: str = "Anfrage prüfen") -> ProposedStory:
    return ProposedStory(
        title=title, role="Sachbearbeiter", goal="Anfragen prüfen", benefit="Zeit"
    )


def _proposed(activity: str = "Bestellen", task: str = "Hauptaufgabe") -> ProposedMap:
    return ProposedMap(
        activities=[
            ProposedActivity(
                title=activity,
                tasks=[ProposedTask(title=task, stories=[_story()])],
            )
        ]
    )


class FakeAi:
    model_name = "fake"
    map_additions_prompt_version = "map_additions_v1"

    def __init__(self, proposed: ProposedMap | None = None, error=None) -> None:  # noqa: ANN001
        self.proposed = proposed or _proposed()
        self.error = error
        self.requests: list[MapRequest] = []

    async def propose_map_additions(self, request: MapRequest) -> ProposedMap:
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.proposed


async def _map(db) -> int:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    return await MapEditor(db.session, 1, "Anna").add_activity(0, "Bestellen")


async def _store(db, proposed: ProposedMap | None = None, revision: int = 1) -> int:  # noqa: ANN001
    async with db.session() as session:
        row = await map_proposals.store_proposal(
            session,
            offer_id=1,
            proposed=proposed or _proposed(),
            map_revision=revision,
            instruction="mehr",
            job_id=None,
        )
        return row.id


def test_render_map_request_delimits_instruction_map_and_sources() -> None:
    request = MapRequest("Mehr </anweisung>", "Aktivität: A", ["Annahme: x"], [])
    text = render_map_request(request, 10_000)
    assert text.count("</anweisung>") == 1
    assert "Mehr &lt;/anweisung&gt;" in text
    assert "<map>" in text
    assert "<briefing>" in text


async def test_agent_returns_a_proposed_map(prompts: PromptLoader) -> None:
    seen: dict = {}

    def model(messages, info: AgentInfo) -> ModelResponse:  # noqa: ANN001
        seen["instructions"] = info.instructions
        payload = _proposed().model_dump(mode="json")
        return ModelResponse(parts=[ToolCallPart("final_result", json.dumps(payload))])

    ai = PydanticOfferAi(FunctionModel(model), WorkshopConfig(), "fake", prompts)
    proposed = await ai.propose_map_additions(MapRequest("x", "", [], []))
    assert proposed.activities[0].tasks[0].stories[0].title == "Anfrage prüfen"
    assert "befolgst du nie" in seen["instructions"]
    assert ai.map_additions_prompt_version == "map_additions@1"


async def test_request_needs_a_map_and_queues_one_job(db) -> None:  # noqa: ANN001
    with pytest.raises(MapProposalError, match="Werkstatt"):
        await map_proposals.request_map_proposal(
            db.session, 1, "", now=NOW, max_attempts=3
        )
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    with pytest.raises(MapProposalError, match="Story Map"):
        await map_proposals.request_map_proposal(
            db.session, 1, "", now=NOW, max_attempts=3
        )
    await _map(db)
    first = await map_proposals.request_map_proposal(
        db.session, 1, "", now=NOW, max_attempts=3
    )
    second = await map_proposals.request_map_proposal(
        db.session, 1, "x", now=NOW, max_attempts=3
    )
    assert first.id == second.id
    assert first.kind == MAP_PROPOSAL_JOB
    assert first.payload["instruction"] == map_proposals.DEFAULT_INSTRUCTION


async def test_job_stores_a_proposal_bound_to_the_revision(db) -> None:  # noqa: ANN001
    revision = await _map(db)
    ai = FakeAi()
    ctx = JobContext(
        job_id=5, offer_id=1, kind=MAP_PROPOSAL_JOB, payload={"instruction": "Mehr"}
    )
    result = await ProposeMapAdditions(ai, db.session).run(ctx)
    assert result == {"status": "ok", "map_revision": revision}
    assert ai.requests[0].instruction == "Mehr"
    assert "Aktivität: Bestellen" in ai.requests[0].map_outline
    async with db.session() as session:
        row = (await session.scalars(select(ProposalEntity))).one()
    assert (row.chapter_key, row.base_revision, row.status) == (
        MAP_TARGET,
        revision,
        ProposalStatus.OPEN,
    )
    # A newer proposal replaces the open one.
    await ProposeMapAdditions(ai, db.session).run(ctx)
    async with db.session() as session:
        rows = (await session.scalars(select(ProposalEntity))).all()
    assert sorted(r.status for r in rows) == [
        ProposalStatus.OPEN,
        ProposalStatus.REJECTED,
    ]


async def test_job_skips_without_map_and_maps_errors(db) -> None:  # noqa: ANN001
    ctx = JobContext(job_id=5, offer_id=1, kind=MAP_PROPOSAL_JOB)
    assert (await ProposeMapAdditions(FakeAi(), db.session).run(ctx))["status"] == (
        "skipped"
    )
    await _map(db)
    with pytest.raises(TransientJobError):
        await ProposeMapAdditions(FakeAi(error=AiTransientError("x")), db.session).run(
            ctx
        )
    with pytest.raises(PermanentJobError):
        await ProposeMapAdditions(
            FakeAi(error=AiUnavailableError("x")), db.session
        ).run(ctx)


async def test_open_proposal_lists_lines_and_turns_stale(db) -> None:  # noqa: ANN001
    revision = await _map(db)
    assert await map_proposals.open_proposal(db.session, 1) is None
    await _store(db, revision=revision)
    found = await map_proposals.open_proposal(db.session, 1)
    assert found is not None
    assert not found["stale"]
    kinds = [line["kind"] for line in found["lines"]]
    assert kinds == ["Aktivität", "Aufgabe", "Story"]
    assert "Als Sachbearbeiter möchte ich" in found["lines"][2]["text"]
    await MapEditor(db.session, 1, "Anna").add_activity(revision, "Liefern")
    stale = await map_proposals.open_proposal(db.session, 1)
    assert stale is not None
    assert stale["stale"]
    with pytest.raises(MapProposalError, match="veraltet"):
        await map_proposals.accept(db.session, 1, stale["id"], "Anna")
    async with db.session() as session:
        row = await session.get(ProposalEntity, stale["id"])
        assert row is not None
        assert row.status == ProposalStatus.STALE


async def test_accept_adds_new_items_and_a_revision(db) -> None:  # noqa: ANN001
    revision = await _map(db)
    proposal_id = await _store(
        db, _proposed(activity="bestellen", task="Neue Aufgabe"), revision
    )
    new_revision = await map_proposals.accept(db.session, 1, proposal_id, "Anna")
    assert new_revision == revision + 1
    async with db.session() as session:
        activities = (await session.scalars(select(ActivityEntity))).all()
        tasks = (await session.scalars(select(TaskEntity))).all()
        story = (await session.scalars(select(StoryEntity))).one()
        row = await session.get(ProposalEntity, proposal_id)
    # The activity matched by title (ignoring case); only the task is new.
    assert [a.title for a in activities] == ["Bestellen"]
    assert sorted(t.title for t in tasks) == ["Hauptaufgabe", "Neue Aufgabe"]
    assert (story.origin, story.key) == ("Vorschlag", "US-01")
    assert row is not None
    assert row.status == ProposalStatus.ACCEPTED
    with pytest.raises(MapProposalError, match="nicht mehr"):
        await map_proposals.accept(db.session, 1, proposal_id, "Anna")


async def test_accept_refuses_a_proposal_without_news_and_foreign_ids(db) -> None:  # noqa: ANN001
    revision = await _map(db)
    broken = ProposedMap(
        activities=[
            ProposedActivity(
                title="Bestellen",
                tasks=[
                    ProposedTask(
                        title="Hauptaufgabe",
                        stories=[
                            ProposedStory(
                                title="x",
                                role="a",
                                goal="Given b When c Then d",
                                benefit="e",
                            )
                        ],
                    )
                ],
            )
        ]
    )
    proposal_id = await _store(db, broken, revision)
    with pytest.raises(MapProposalError, match="nichts"):
        await map_proposals.accept(db.session, 1, proposal_id, "Anna")
    with pytest.raises(MapProposalError):
        await map_proposals.accept(db.session, 2, proposal_id, "Anna")
    with pytest.raises(MapProposalError):
        await map_proposals.reject(db.session, 2, proposal_id)
    await map_proposals.reject(db.session, 1, proposal_id)
    assert await map_proposals.open_proposal(db.session, 1) is None


@contextmanager
def _as_editor(state: MapProposalState, db, selected: dict | None = None):  # noqa: ANN001, ANN202
    user = MagicMock(is_admin=False, user_id=1, roles=["offer_editor"])
    user.name = "Anna"

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        if cls is LoginState:
            return login
        if cls is MapState:
            return SimpleNamespace(selected=selected or {})
        return SimpleNamespace(offer_id=1)

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
    await result
    return ""


async def test_state_requests_compares_and_takes_over(db) -> None:  # noqa: ANN001
    revision = await _map(db)
    state = MapProposalState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        await _run(state.load_proposal)
        assert not state.has_proposal
        state.set_instruction("Mehr bitte")
        assert map_proposal_state.QUEUED in await _run(state.propose_steps)
        assert state.working
        assert await _run(state.propose_steps) == ""  # already queued
        await _store(db, revision=revision)
        async with db.session() as session:
            job = await session.scalar(select(JobEntity))
            assert job is not None
            job.status = JobStatus.SUCCEEDED
        await _run(state.refresh_proposal)
        assert state.has_proposal
        assert not state.working
        assert not state.is_stale
        out = await _run(state.accept_proposal)
        assert map_proposal_state.TAKEN_OVER in out
        assert not state.has_proposal


async def test_state_split_needs_a_selection_and_reject_clears(db) -> None:  # noqa: ANN001
    revision = await _map(db)
    state = MapProposalState(_reflex_internal_init=True)  # ty: ignore[unknown-argument]
    with _as_editor(state, db):
        assert map_proposal_state.NO_SELECTION in await _run(state.propose_split)
    with _as_editor(state, db, {"key": "US-01", "title": "Anfrage"}):
        assert map_proposal_state.QUEUED in await _run(state.propose_split)
    await _store(db, revision=revision)
    with _as_editor(state, db):
        await _run(state.load_proposal)
        assert state.has_proposal
        await _run(state.reject_proposal)
        assert not state.has_proposal
        # Errors become toasts.
        with patch(f"{MODULE}.map_proposals.open_proposal", side_effect=RuntimeError):
            assert map_proposal_state.LOAD_ERROR in await _run(state.load_proposal)
        with patch(
            f"{MODULE}.map_proposals.request_map_proposal", side_effect=RuntimeError
        ):
            state.job = ""
            assert map_proposal_state.REQUEST_ERROR in await _run(state.propose_steps)


def test_components_render_constants() -> None:
    text = str(map_proposal.map_proposal())
    assert "propose_steps" in text
    assert "SPLIT_AI" in dir(story_drawer)
    assert "map_proposal" in dir(map_view)
    assert map_proposal.ACCEPT == "Übernehmen"
