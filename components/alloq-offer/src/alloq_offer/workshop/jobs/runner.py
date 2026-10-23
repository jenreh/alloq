"""Worker loop: claim a job, run the handler outside a transaction, store the result."""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import JobEntity
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
    get_exhausted_hook,
    get_handler,
    registered_kinds,
)
from appkit_commons.database.session import get_asyncdb_session

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _context(job: JobEntity) -> JobContext:
    return JobContext(
        job_id=job.id,
        offer_id=job.offer_id,
        kind=job.kind,
        payload=dict(job.payload),
        input_revisions=dict(job.input_revisions),
        attempt=job.attempts,
        max_attempts=job.max_attempts,
    )


class JobRunner:
    """Runs queued jobs; several runners (server and desktop) may share one queue."""

    def __init__(
        self,
        config: WorkshopConfig,
        session_factory: SessionFactory = get_asyncdb_session,
        clock: Clock = utc_now,
    ) -> None:
        self._config = config
        self._session_factory = session_factory
        self._clock = clock

    async def _claim(self) -> JobContext | None:
        exhausted: list[JobEntity] = []
        async with self._session_factory() as session:
            job = await queue.claim_next(
                session,
                now=self._clock(),
                lease_seconds=self._config.lease_seconds,
                kinds=registered_kinds(),
                exhausted=exhausted,
            )
            context = _context(job) if job is not None else None
            expired = [_context(item) for item in exhausted]
        for item in expired:
            await self._run_exhausted_hook(item)
        return context

    async def _run_exhausted_hook(self, context: JobContext) -> None:
        hook = get_exhausted_hook(context.kind)
        if hook is None:
            return
        try:
            await hook(context)
        except Exception:
            logger.exception("Cleanup of failed job %s failed", context.job_id)

    async def run_once(self) -> bool:
        """Run one due job to the end; False when the queue had none."""
        context = await self._claim()
        if context is None:
            return False
        await self._execute(context)
        return True

    async def run_forever(self) -> None:
        """Poll the queue with bounded concurrency until cancelled."""
        semaphore = asyncio.Semaphore(self._config.worker_concurrency)
        running: set[asyncio.Task[None]] = set()
        try:
            while True:
                await semaphore.acquire()
                context = None
                try:
                    context = await self._claim()
                except Exception:
                    logger.exception("Job polling failed")
                if context is None:
                    semaphore.release()
                    await asyncio.sleep(self._config.poll_interval_seconds)
                    continue
                task = asyncio.create_task(self._execute(context))
                running.add(task)
                task.add_done_callback(
                    lambda finished: (running.discard(finished), semaphore.release())
                )
        finally:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)

    async def _execute(self, context: JobContext) -> None:
        started = time.monotonic()
        beat = asyncio.create_task(self._heartbeat(context))
        try:
            handler = get_handler(context.kind)
            result = await handler(context)
        except TransientJobError as exc:
            await self._record_failure(context, exc, retry=True)
        except Exception as exc:
            logger.exception("Job %s (%s) failed", context.job_id, context.kind)
            await self._record_failure(context, exc, retry=False)
        else:
            async with self._session_factory() as session:
                stored = await queue.complete(
                    session, context.job_id, context.attempt, result
                )
            if not stored:
                logger.info("Result of job %s discarded", context.job_id)
            logger.info(
                "Job %s (%s) finished in %.2f s",
                context.job_id,
                context.kind,
                time.monotonic() - started,
            )
        finally:
            beat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await beat

    async def _record_failure(
        self, context: JobContext, exc: Exception, *, retry: bool
    ) -> None:
        if not retry or context.attempt >= context.max_attempts:
            await self._run_exhausted_hook(context)
        async with self._session_factory() as session:
            await queue.fail(
                session,
                context.job_id,
                context.attempt,
                error_class=type(exc).__name__,
                # Only transient errors carry a message we wrote ourselves; other
                # exceptions may quote source content, the log has the trace.
                message=(
                    str(exc)
                    if isinstance(exc, TransientJobError | PermanentJobError)
                    else ""
                ),
                retry=retry,
                now=self._clock(),
            )

    async def _heartbeat(self, context: JobContext) -> None:
        interval = max(self._config.lease_seconds / 3, 1)
        while True:
            await asyncio.sleep(interval)
            try:
                async with self._session_factory() as session:
                    owned = await queue.heartbeat(
                        session,
                        context.job_id,
                        context.attempt,
                        now=self._clock(),
                        lease_seconds=self._config.lease_seconds,
                    )
            except Exception:
                logger.exception("Heartbeat of job %s failed", context.job_id)
                continue
            if not owned:
                return
