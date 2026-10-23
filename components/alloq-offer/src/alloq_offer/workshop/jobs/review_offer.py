"""Job ``review_offer``: the AI looks for gaps and contradictions (spec 11.2).

The review only adds findings. It never edits a chapter, a story or a value, and
it cannot raise a blocker: that is left to the rule checks.
"""

import logging

from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    ReviewAi,
    ReviewChapter,
    ReviewRequest,
)
from alloq_offer.workshop.ai.render import map_outline, statement_line
from alloq_offer.workshop.ai.schemas import ProposedReview
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.text import content_lines
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    FindingSeverity,
    FindingSource,
    GenerationRunEntity,
)
from alloq_offer.workshop.jobs.ai_access import job_ai
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
    register_handler,
)
from alloq_offer.workshop.services.checks import (
    CheckInput,
    RuleFinding,
    chapter_target,
    live_stories,
)
from alloq_offer.workshop.services.findings import load_check_input, sync
from alloq_offer.workshop.services.review_request import REVIEW_JOB
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

AI_FAILED = "Die KI konnte nicht prüfen. Bitte prüfen Sie die Einrichtung."
AI_BUSY = "Die KI ist gerade nicht erreichbar. Der Auftrag wird erneut versucht."
WORKSPACE = "workspace"
RULE = "ai_review"
MAX_REMARKS = 30
SEVERITIES = {
    "Warnung": FindingSeverity.WARNING,
    "Hinweis": FindingSeverity.NOTE,
}


def build_request(data: CheckInput) -> ReviewRequest:
    chapters = [
        ReviewChapter(c.key, c.title, lines)
        for c in data.chapters
        if (lines := content_lines(c.content))
    ]
    return ReviewRequest(
        map_outline=map_outline(data.snapshot),
        statements=[
            statement_line(s.type, s.text, s.confirmed) for s in data.statements
        ],
        chapters=chapters,
    )


def known_targets(data: CheckInput) -> set[str]:
    return (
        {WORKSPACE}
        | {chapter_target(c.key) for c in data.chapters}
        | {f"story:{story['key']}" for story in live_stories(data.snapshot)}
    )


def to_issues(review: ProposedReview, valid: set[str]) -> list[RuleFinding]:
    """Remarks as findings; a made-up target falls back to the whole offer."""
    return [
        RuleFinding(
            RULE,
            SEVERITIES.get(remark.severity, FindingSeverity.NOTE),
            remark.target if remark.target in valid else WORKSPACE,
            remark.message.strip(),
        )
        for remark in review.findings[:MAX_REMARKS]
        if remark.message.strip()
    ]


class ReviewOffer:
    def __init__(self, ai: ReviewAi, session_factory: SessionFactory) -> None:
        self._ai = ai
        self._session_factory = session_factory

    async def run(self, ctx: JobContext) -> dict:
        async with self._session_factory() as session:
            data = await load_check_input(session, ctx.offer_id)
        if data is None or data.map_revision == 0:
            return {"status": "skipped", "reason": "nothing to review"}
        try:
            review = await self._ai.propose_review(build_request(data))
        except AiTransientError as exc:
            raise TransientJobError(AI_BUSY) from exc
        except AiUnavailableError as exc:
            raise PermanentJobError(AI_FAILED) from exc
        issues = to_issues(review, known_targets(data))
        async with self._session_factory() as session:
            await sync(
                session, ctx.offer_id, FindingSource.AI, issues, data.map_revision
            )
            session.add(
                GenerationRunEntity(
                    offer_id=ctx.offer_id,
                    job_id=ctx.job_id,
                    kind=REVIEW_JOB,
                    model=self._ai.model_name,
                    prompt_version=self._ai.review_prompt_version,
                    input_revisions={"map": data.map_revision},
                    status="ok",
                )
            )
        logger.info("AI review of offer %s: %d findings", ctx.offer_id, len(issues))
        return {"status": "ok", "findings": len(issues)}


@register_handler(REVIEW_JOB)
async def review_offer(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    return await ReviewOffer(job_ai(config), get_asyncdb_session).run(ctx)
