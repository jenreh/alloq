"""What the review panel shows, read in one session."""

from dataclasses import dataclass
from typing import Any

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.repositories import job_repo, workspace_repo
from alloq_offer.workshop.services import commercials, findings
from alloq_offer.workshop.services.review_request import REVIEW_JOB
from alloq_offer.workshop.services.workspace import NO_WORKSPACE


@dataclass(frozen=True)
class ReviewView:
    findings: list[dict[str, Any]]
    commercials: commercials.CommercialsView
    review_job: str


async def load_review(
    sessions: SessionFactory, offer_id: int, *, check: bool = False
) -> ReviewView:
    """Findings, calculation and the AI review job; ``check`` runs the rules first."""
    async with sessions() as session:
        waiting: set[str] | None = None
        if check:
            run = await findings.check_offer(session, offer_id)
            workspace, offer, waiting = run.workspace, run.offer, run.waiting
        else:
            found = await workspace_repo.find_with_offer(session, offer_id)
            if found is None:
                raise commercials.CommercialsError(NO_WORKSPACE)
            workspace, offer = found
            await commercials.void_if_changed(session, workspace, offer)
        rows = await findings.findings_in(session, offer_id, waiting)
        job = await job_repo.find_latest(session, offer_id, REVIEW_JOB)
        view = commercials.view_of(workspace, offer)
    return ReviewView(rows, view, job.status if job is not None else "")
