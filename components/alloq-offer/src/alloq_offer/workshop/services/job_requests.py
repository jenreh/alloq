"""Queue one job of a kind per offer at a time."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.entities import JobEntity, JobStatus
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.repositories import job_repo


async def enqueue_exclusive(
    session: AsyncSession,
    *,
    kind: str,
    offer_id: int,
    payload: dict,
    now: datetime,
    max_attempts: int,
) -> JobEntity:
    """A waiting or running job of this kind is returned instead of queuing another.

    The key counts the jobs of the kind, so two clicks at once meet in the same
    queue entry.
    """
    latest = await job_repo.find_latest(session, offer_id, kind)
    if latest is not None and latest.status in (JobStatus.QUEUED, JobStatus.RUNNING):
        return latest
    number = await job_repo.count_of_kind(session, offer_id, kind)
    return await queue.enqueue(
        session,
        kind=kind,
        offer_id=offer_id,
        idempotency_key=f"{kind}:{offer_id}:{number + 1}",
        payload=payload,
        now=now,
        max_attempts=max_attempts,
    )
