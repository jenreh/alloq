"""Persistent job queue: enqueue, claim with lease, finish, retry.

Own queue on purpose: jobs belong to an offer, carry idempotency keys and revision
fences, and must run on server and desktop. appkit's PGQueuer scheduler is
cron-style and does not cover that.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.entities import JobEntity, JobStatus

logger = logging.getLogger(__name__)

MAX_BACKOFF_SECONDS = 300
ERROR_MESSAGE_LIMIT = 2000


def backoff_seconds(attempts: int) -> int:
    """Delay before retry number ``attempts`` (5 s, 10 s, 20 s, ... capped)."""
    return min(5 * 2 ** max(attempts - 1, 0), MAX_BACKOFF_SECONDS)


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    offer_id: int,
    idempotency_key: str,
    now: datetime,
    max_attempts: int,
    payload: dict | None = None,
    input_revisions: dict | None = None,
) -> JobEntity:
    """Create a job, or return the existing one with the same idempotency key."""
    existing = await _by_key(session, idempotency_key)
    if existing is not None:
        return existing
    job = JobEntity(
        offer_id=offer_id,
        kind=kind,
        status=JobStatus.QUEUED,
        idempotency_key=idempotency_key,
        payload=payload or {},
        input_revisions=input_revisions or {},
        attempts=0,
        max_attempts=max_attempts,
        run_after=now,
    )
    try:
        async with session.begin_nested():
            session.add(job)
    except IntegrityError:
        # A concurrent enqueue with the same key won the race.
        found = await _by_key(session, idempotency_key)
        if found is None:
            raise
        return found
    return job


async def _by_key(session: AsyncSession, key: str) -> JobEntity | None:
    return await session.scalar(
        select(JobEntity).where(JobEntity.idempotency_key == key)
    )


async def claim_next(
    session: AsyncSession,
    *,
    now: datetime,
    lease_seconds: int,
    kinds: list[str] | None = None,
    exhausted: list[JobEntity] | None = None,
) -> JobEntity | None:
    """Lease the next runnable job.

    Runnable are queued jobs that are due and running jobs whose lease expired.
    A job that expired with no attempts left is failed instead of re-run and
    appended to ``exhausted`` when given.
    """
    while True:
        statement = (
            select(JobEntity)
            .where(
                or_(
                    and_(
                        JobEntity.status == JobStatus.QUEUED,
                        JobEntity.run_after <= now,
                    ),
                    and_(
                        JobEntity.status == JobStatus.RUNNING,
                        JobEntity.lease_until < now,
                    ),
                )
            )
            .order_by(JobEntity.run_after, JobEntity.id)
            .limit(1)
        )
        if kinds is not None:
            statement = statement.where(JobEntity.kind.in_(kinds))
        if _is_postgres(session):
            statement = statement.with_for_update(skip_locked=True)
        job = await session.scalar(statement)
        if job is None:
            return None
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED
            job.error_class = job.error_class or "LeaseExpired"
            job.lease_until = None
            await session.flush()
            logger.warning("Job %s failed after %s attempts", job.id, job.attempts)
            if exhausted is not None:
                exhausted.append(job)
            continue
        job.status = JobStatus.RUNNING
        job.attempts += 1
        job.lease_until = now + timedelta(seconds=lease_seconds)
        await session.flush()
        return job


async def heartbeat(
    session: AsyncSession,
    job_id: int,
    attempt: int,
    *,
    now: datetime,
    lease_seconds: int,
) -> bool:
    """Extend the lease; False when this attempt no longer owns the job."""
    job = await _owned(session, job_id, attempt)
    if job is None:
        return False
    job.lease_until = now + timedelta(seconds=lease_seconds)
    return True


async def complete(
    session: AsyncSession, job_id: int, attempt: int, result: dict | None
) -> bool:
    """Mark the attempt done; False (result discarded) when it lost the job."""
    job = await _owned(session, job_id, attempt)
    if job is None:
        return False
    job.status = JobStatus.SUCCEEDED
    job.result = result
    job.lease_until = None
    return True


async def fail(
    session: AsyncSession,
    job_id: int,
    attempt: int,
    *,
    error_class: str,
    message: str,
    retry: bool,
    now: datetime,
) -> bool:
    """Record a failure; requeue with backoff when ``retry`` and attempts remain."""
    job = await _owned(session, job_id, attempt)
    if job is None:
        return False
    job.error_class = error_class
    job.error_message = message[:ERROR_MESSAGE_LIMIT]
    job.lease_until = None
    if retry and job.attempts < job.max_attempts:
        job.status = JobStatus.QUEUED
        job.run_after = now + timedelta(seconds=backoff_seconds(job.attempts))
    else:
        job.status = JobStatus.FAILED
    return True


async def cancel(session: AsyncSession, job_id: int) -> bool:
    """Cancel a job that has not finished; its result will be discarded."""
    job = await session.get(JobEntity, job_id)
    if job is None or job.status in (
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    ):
        return False
    job.status = JobStatus.CANCELLED
    job.lease_until = None
    return True


async def _owned(session: AsyncSession, job_id: int, attempt: int) -> JobEntity | None:
    job = await session.get(JobEntity, job_id)
    if job is None or job.status != JobStatus.RUNNING or job.attempts != attempt:
        return None
    return job


def _is_postgres(session: AsyncSession) -> bool:
    bind = session.get_bind()
    return bind.dialect.name == "postgresql"
