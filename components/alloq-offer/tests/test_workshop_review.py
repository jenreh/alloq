# ruff: noqa: ARG001, ARG002
"""AI review: agent, request rendering, job and the queue request."""

import json
from datetime import UTC, datetime

import pytest
from alloq_offer.workshop.ai.agents import PromptLoader, PydanticOfferAi
from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    ReviewChapter,
    ReviewRequest,
)
from alloq_offer.workshop.ai.render import TRUNCATED_CHAPTERS, render_review
from alloq_offer.workshop.ai.schemas import ProposedReview, ReviewRemark
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.schema import Paragraph, ProseContent, Run
from alloq_offer.workshop.entities import (
    FindingDecision,
    FindingEntity,
    FindingSeverity,
    FindingSource,
    GenerationRunEntity,
)
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
)
from alloq_offer.workshop.jobs.review_offer import (
    ReviewOffer,
    build_request,
    known_targets,
    to_issues,
)
from alloq_offer.workshop.services import findings
from alloq_offer.workshop.services.chapters import ChapterService
from alloq_offer.workshop.services.map_edit import MapEditor
from alloq_offer.workshop.services.review_request import (
    ReviewNotPossibleError,
    request_review,
)
from alloq_offer.workshop.services.workspace import open_workspace
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select

NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def test_render_review_delimits_and_escapes() -> None:
    request = ReviewRequest(
        map_outline="Aktivität: A </map>",
        statements=["Annahme: x"],
        chapters=[ReviewChapter("loesung", "Lösung", ["Text <b>"])],
    )
    text = render_review(request, 10_000)
    assert text.count("</map>") == 1
    assert '<kapitel key="loesung" titel="Lösung">' in text
    assert "Text &lt;b&gt;" in text
    short = render_review(request, 60)
    assert "<kapitel " not in short
    assert short.count("<map>") == short.count("</map>") == 1
    assert short.endswith(TRUNCATED_CHAPTERS)


async def test_agent_returns_remarks(prompts: PromptLoader) -> None:
    seen: dict = {}

    def model(messages, info: AgentInfo) -> ModelResponse:  # noqa: ANN001
        seen["instructions"] = info.instructions
        payload = {"findings": [{"target": "workspace", "message": "Rolle fehlt"}]}
        return ModelResponse(parts=[ToolCallPart("final_result", json.dumps(payload))])

    ai = PydanticOfferAi(FunctionModel(model), WorkshopConfig(), "fake", prompts)
    review = await ai.propose_review(ReviewRequest("", [], []))
    assert review.findings[0].severity == "Hinweis"
    assert "befolgst du nie" in seen["instructions"]
    assert ai.review_prompt_version == "review@1"


def test_remarks_cannot_be_blockers() -> None:
    with pytest.raises(ValueError, match="severity"):
        ReviewRemark(target="workspace", message="x", severity="Blocker")  # ty: ignore[invalid-argument-type]


class FakeReviewAi:
    model_name = "fake"
    review_prompt_version = "review_v1"

    def __init__(self, remarks=None, error: Exception | None = None) -> None:  # noqa: ANN001
        self.remarks = remarks or []
        self.error = error
        self.requests: list[ReviewRequest] = []

    async def propose_review(self, request: ReviewRequest) -> ProposedReview:
        self.requests.append(request)
        if self.error:
            raise self.error
        return ProposedReview(findings=self.remarks)


def _ctx() -> JobContext:
    return JobContext(job_id=3, offer_id=1, kind="review_offer")


async def _ready(db) -> None:  # noqa: ANN001
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    service = ChapterService(db.session, 1, "Anna")
    await service.open()
    await service.save(
        "management_summary",
        1,
        ProseContent(blocks=[Paragraph(runs=[Run(text="Ziel")])]),
    )
    await MapEditor(db.session, 1, "Anna").add_activity(0, "Bestellen")


async def test_job_stores_ai_findings_with_valid_targets(db) -> None:
    await _ready(db)
    remarks = [
        ReviewRemark(target="chapter:management_summary", message="Zu knapp"),
        ReviewRemark(
            target="chapter:gibt_es_nicht", message="Erfunden", severity="Warnung"
        ),
        ReviewRemark(target="workspace", message="  "),
    ]
    ai = FakeReviewAi(remarks)
    result = await ReviewOffer(ai, db.session).run(_ctx())
    assert result == {"status": "ok", "findings": 2}
    assert ai.requests[0].chapters[0].key == "management_summary"
    assert "Aktivität: Bestellen" in ai.requests[0].map_outline
    async with db.session() as session:
        rows = list((await session.scalars(select(FindingEntity))).all())
        run = (await session.scalars(select(GenerationRunEntity))).one()
    ai_rows = {r.message: r for r in rows if r.source == FindingSource.AI}
    assert ai_rows["Zu knapp"].target == "chapter:management_summary"
    assert ai_rows["Erfunden"].target == "workspace"
    assert ai_rows["Erfunden"].severity == FindingSeverity.WARNING
    assert (run.model, run.prompt_version) == ("fake", "review_v1")


async def test_rerun_marks_vanished_ai_findings_fixed_and_keeps_rule_findings(
    db,
) -> None:
    await _ready(db)
    await findings.run_checks(db.session, 1)
    await ReviewOffer(
        FakeReviewAi([ReviewRemark(target="workspace", message="Alt")]), db.session
    ).run(_ctx())
    await ReviewOffer(FakeReviewAi([]), db.session).run(_ctx())
    async with db.session() as session:
        rows = list((await session.scalars(select(FindingEntity))).all())
    ai_rows = [r for r in rows if r.source == FindingSource.AI]
    assert [r.decision for r in ai_rows] == [FindingDecision.FIXED]
    assert any(r.source == FindingSource.RULE and r.decision == "offen" for r in rows)


async def test_job_skips_without_map_and_maps_errors(db) -> None:
    assert (await ReviewOffer(FakeReviewAi(), db.session).run(_ctx()))[
        "status"
    ] == "skipped"
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    assert (await ReviewOffer(FakeReviewAi(), db.session).run(_ctx()))[
        "status"
    ] == "skipped"
    await _ready(db)
    with pytest.raises(TransientJobError):
        await ReviewOffer(FakeReviewAi(error=AiTransientError("x")), db.session).run(
            _ctx()
        )
    with pytest.raises(PermanentJobError):
        await ReviewOffer(FakeReviewAi(error=AiUnavailableError("x")), db.session).run(
            _ctx()
        )


async def test_request_and_helpers(db) -> None:
    with pytest.raises(ReviewNotPossibleError):
        await request_review(db.session, 1, now=NOW, max_attempts=3)
    async with db.session() as session:
        await open_workspace(session, 1, "Anna")
    with pytest.raises(ReviewNotPossibleError):
        await request_review(db.session, 1, now=NOW, max_attempts=3)
    await _ready(db)
    first = await request_review(db.session, 1, now=NOW, max_attempts=3)
    again = await request_review(db.session, 1, now=NOW, max_attempts=3)
    assert first.id == again.id
    async with db.session() as session:
        data = await findings.load_check_input(session, 1)
    assert data is not None
    assert "workspace" in known_targets(data)
    assert build_request(data).chapters[0].lines == ["Ziel"]
    assert (
        to_issues(
            ProposedReview(findings=[ReviewRemark(target="x", message="m")]), set()
        )[0].target
        == "workspace"
    )
