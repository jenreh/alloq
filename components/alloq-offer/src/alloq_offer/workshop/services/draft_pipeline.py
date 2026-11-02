"""The one-click first draft as a chain of jobs (plan phase 3, spec 9.1).

``initial_draft`` builds map and briefing, then queues the chapter stage. The
chapter stage stores its texts as revisions and queues the AI review and the
Word draft. Each stage is its own job, so a failed stage is retried alone and
the stages before it stay saved.
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import ExportKind, JobEntity
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services import exports, map_proposals, sources
from alloq_offer.workshop.services.chapter_draft import DRAFT_CHAPTERS_JOB
from alloq_offer.workshop.services.job_requests import enqueue_exclusive
from alloq_offer.workshop.services.review_request import (
    ReviewNotPossibleError,
    request_review,
)

logger = logging.getLogger(__name__)

INITIAL = "initial"


def is_initial(payload: dict) -> bool:
    return bool(payload.get(INITIAL))


async def queue_initial_chapters(
    session: AsyncSession, offer_id: int, *, now: datetime, max_attempts: int
) -> JobEntity:
    """Stage ``chapters``: draft every prose chapter and keep it as revision."""
    return await enqueue_exclusive(
        session,
        kind=DRAFT_CHAPTERS_JOB,
        offer_id=offer_id,
        payload={"keys": None, "instruction": "", INITIAL: True},
        now=now,
        max_attempts=max_attempts,
    )


async def finish_initial_draft(
    session_factory: SessionFactory, offer_id: int, *, now: datetime, max_attempts: int
) -> None:
    """Stages ``checks`` and ``word_draft``: AI review and the first Word file.

    The export runs the rule checks on the state it fixes. A stage that cannot
    start is logged and skipped, so the chapters stay saved.
    """
    try:
        await request_review(
            session_factory, offer_id, now=now, max_attempts=max_attempts
        )
    except ReviewNotPossibleError:
        logger.info("Initial review of offer %s skipped", offer_id)
    try:
        await exports.request_export(
            session_factory,
            offer_id,
            ExportKind.DRAFT,
            user="",
            confirmed=False,
            unsaved=False,
            now=now,
            max_attempts=max_attempts,
        )
    except exports.ExportBlockedError:
        logger.warning("Initial Word draft of offer %s could not start", offer_id)


async def draft_when_usable(
    session_factory: SessionFactory, offer_id: int, *, now: datetime, max_attempts: int
) -> str:
    """Setting "Automatisch entwerfen": a usable source starts the next step.

    Without a map the first draft is queued; with a map only a proposal is made,
    so nothing written is overwritten. Returns the queued job kind or "".
    """
    async with session_factory() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        if workspace is None or not workspace.auto_draft:
            return ""
        has_map = workspace.map_revision > 0
    try:
        if has_map:
            job = await map_proposals.request_map_proposal(
                session_factory, offer_id, "", now=now, max_attempts=max_attempts
            )
        else:
            job = await sources.request_initial_draft(
                session_factory, offer_id, now=now, max_attempts=max_attempts
            )
    except map_proposals.MapProposalError, sources.DraftNotPossibleError:
        return ""
    return job.kind
