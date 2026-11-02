"""Ask for the AI review: queue the job ``review_offer`` (spec 11.2)."""

from datetime import datetime

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import JobEntity
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.job_requests import enqueue_exclusive
from alloq_offer.workshop.services.workspace import NO_WORKSPACE

REVIEW_JOB = "review_offer"
NOTHING_TO_REVIEW = "Es gibt noch keine Story Map oder Kapitel zum Prüfen."


class ReviewNotPossibleError(ValueError):
    """There is nothing to review; the message is German."""


async def request_review(
    session_factory: SessionFactory,
    offer_id: int,
    *,
    now: datetime,
    max_attempts: int,
) -> JobEntity:
    async with session_factory() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        if workspace is None:
            raise ReviewNotPossibleError(NO_WORKSPACE)
        if workspace.map_revision == 0:
            raise ReviewNotPossibleError(NOTHING_TO_REVIEW)
        return await enqueue_exclusive(
            session,
            kind=REVIEW_JOB,
            offer_id=offer_id,
            payload={},
            now=now,
            max_attempts=max_attempts,
        )
