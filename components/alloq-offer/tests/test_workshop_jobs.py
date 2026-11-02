import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.entities import JobEntity, JobStatus
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    TransientJobError,
    UnknownJobKindError,
    get_handler,
    register_handler,
    registered_kinds,
)
from alloq_offer.workshop.jobs.runner import JobRunner

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


async def _enqueue(db, key: str = "k1", kind: str = "demo", **over) -> int:
    async with db.session() as session:
        job = await queue.enqueue(
            session,
            kind=kind,
            offer_id=1,
            idempotency_key=key,
            now=NOW,
            **{"max_attempts": 3, **over},
        )
        await session.flush()
        return job.id


async def _job(db, job_id: int) -> JobEntity:
    async with db.session() as session:
        job = await session.get(JobEntity, job_id)
        assert job is not None
        return job


async def test_enqueue_is_idempotent(db) -> None:
    first = await _enqueue(db)
    second = await _enqueue(db)
    assert first == second


async def test_claim_leases_and_hides_job(db) -> None:
    job_id = await _enqueue(db)
    async with db.session() as session:
        claimed = await queue.claim_next(session, now=NOW, lease_seconds=60)
        assert claimed is not None
        assert (claimed.id, claimed.attempts) == (job_id, 1)
    async with db.session() as session:
        assert await queue.claim_next(session, now=NOW, lease_seconds=60) is None


async def test_claim_can_be_limited_to_one_offer(db) -> None:
    await _enqueue(db)
    async with db.session() as session:
        assert (
            await queue.claim_next(session, now=NOW, lease_seconds=60, offer_id=2)
            is None
        )
        assert (
            await queue.claim_next(session, now=NOW, lease_seconds=60, offer_id=1)
            is not None
        )


async def test_claim_respects_run_after_and_kind_filter(db) -> None:
    await _enqueue(db, "a", "later")
    async with db.session() as session:
        assert (
            await queue.claim_next(
                session, now=NOW - timedelta(minutes=1), lease_seconds=60
            )
            is None
        )
        assert (
            await queue.claim_next(session, now=NOW, lease_seconds=60, kinds=["x"])
            is None
        )


async def test_expired_lease_is_reclaimed_then_fails_when_attempts_used(db) -> None:
    job_id = await _enqueue(db, max_attempts=2)
    async with db.session() as session:
        await queue.claim_next(session, now=NOW, lease_seconds=10)
    later = NOW + timedelta(seconds=11)
    async with db.session() as session:
        again = await queue.claim_next(session, now=later, lease_seconds=10)
        assert again is not None
        assert again.attempts == 2
    async with db.session() as session:
        gone = await queue.claim_next(
            session, now=later + timedelta(seconds=11), lease_seconds=10
        )
        assert gone is None
    assert (await _job(db, job_id)).status == JobStatus.FAILED


async def test_complete_discards_result_of_lost_attempt(db) -> None:
    job_id = await _enqueue(db)
    async with db.session() as session:
        await queue.claim_next(session, now=NOW, lease_seconds=10)
    async with db.session() as session:
        await queue.claim_next(
            session, now=NOW + timedelta(seconds=11), lease_seconds=10
        )
    async with db.session() as session:
        assert not await queue.complete(session, job_id, 1, {"late": True})
        assert await queue.complete(session, job_id, 2, {"ok": True})
    job = await _job(db, job_id)
    assert (job.status, job.result) == (JobStatus.SUCCEEDED, {"ok": True})


async def test_fail_retries_with_backoff_then_gives_up(db) -> None:
    job_id = await _enqueue(db, max_attempts=2)
    for attempt in (1, 2):
        async with db.session() as session:
            await queue.claim_next(
                session, now=NOW + timedelta(hours=attempt), lease_seconds=60
            )
        async with db.session() as session:
            await queue.fail(
                session,
                job_id,
                attempt,
                error_class="Boom",
                message="x" * 5000,
                retry=True,
                now=NOW + timedelta(hours=attempt),
            )
        if attempt == 1:
            job = await _job(db, job_id)
            assert job.status == JobStatus.QUEUED
            assert job.run_after.replace(tzinfo=UTC) > NOW + timedelta(hours=1)
    job = await _job(db, job_id)
    assert job.status == JobStatus.FAILED
    assert len(job.error_message or "") == queue.ERROR_MESSAGE_LIMIT


async def test_cancelled_job_is_not_claimed_and_result_discarded(db) -> None:
    job_id = await _enqueue(db)
    async with db.session() as session:
        await queue.claim_next(session, now=NOW, lease_seconds=60)
    async with db.session() as session:
        assert await queue.cancel(session, job_id)
        assert not await queue.cancel(session, 9999)
    async with db.session() as session:
        assert not await queue.complete(session, job_id, 1, {})
        assert not await queue.heartbeat(session, job_id, 1, now=NOW, lease_seconds=60)
    assert (await _job(db, job_id)).status == JobStatus.CANCELLED


def test_backoff_grows_and_is_capped() -> None:
    assert [queue.backoff_seconds(n) for n in (1, 2, 3)] == [5, 10, 20]
    assert queue.backoff_seconds(30) == queue.MAX_BACKOFF_SECONDS


def _runner(db) -> JobRunner:
    return JobRunner(WorkshopConfig(lease_seconds=30), db.session, lambda: NOW)


async def test_runner_runs_registered_handler_and_stores_result(db) -> None:
    seen: list[JobContext] = []

    @register_handler("demo")
    async def handler(context: JobContext) -> dict:
        seen.append(context)
        return {"done": context.payload["n"]}

    job_id = await _enqueue(db, payload={"n": 7})
    assert await _runner(db).run_once()
    assert not await _runner(db).run_once()
    job = await _job(db, job_id)
    assert (job.status, job.result) == (JobStatus.SUCCEEDED, {"done": 7})
    assert seen[0].offer_id == 1
    assert "demo" in registered_kinds()
    assert get_handler("demo") is handler


async def test_runner_fails_errors_and_leaves_unknown_kinds_queued(db) -> None:
    @register_handler("explodes")
    async def explode(_context: JobContext) -> None:
        raise RuntimeError("kaputt")

    unknown = await _enqueue(db, "u", "no-such-kind")
    broken = await _enqueue(db, "b", "explodes")
    runner = _runner(db)
    while await runner.run_once():
        pass
    assert (await _job(db, unknown)).status == JobStatus.QUEUED
    job = await _job(db, broken)
    assert (job.status, job.error_class, job.error_message) == (
        JobStatus.FAILED,
        "RuntimeError",
        "",
    )
    with pytest.raises(UnknownJobKindError):
        get_handler("no-such-kind")


async def test_runner_requeues_transient_errors(db) -> None:
    @register_handler("flaky")
    async def flaky(_context: JobContext) -> None:
        raise TransientJobError("später")

    job_id = await _enqueue(db, "f", "flaky")
    await _runner(db).run_once()
    job = await _job(db, job_id)
    assert job.status == JobStatus.QUEUED
    assert job.attempts == 1


async def test_run_forever_processes_jobs_until_cancelled(db) -> None:
    done = asyncio.Event()

    @register_handler("loop")
    async def loop(_context: JobContext) -> dict:
        done.set()
        return {}

    job_id = await _enqueue(db, "l", "loop")
    runner = JobRunner(
        WorkshopConfig(poll_interval_seconds=0.01), db.session, lambda: NOW
    )
    task = asyncio.create_task(runner.run_forever())
    await asyncio.wait_for(done.wait(), timeout=5)
    finished = False
    for _ in range(100):
        finished = (await _job(db, job_id)).status == JobStatus.SUCCEEDED
        if finished:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished


async def test_exhausted_hook_runs_for_permanent_failure_but_not_for_retries(
    db,
) -> None:
    seen: list[int] = []

    async def hook(context: JobContext) -> None:
        seen.append(context.job_id)

    @register_handler("hooked-fail", on_exhausted=hook)
    async def explode(_context: JobContext) -> None:
        raise RuntimeError("kaputt")

    @register_handler("hooked-flaky", on_exhausted=hook)
    async def flaky(_context: JobContext) -> None:
        raise TransientJobError("später")

    failed = await _enqueue(db, "hf", "hooked-fail")
    await _enqueue(db, "hr", "hooked-flaky")
    runner = _runner(db)
    while await runner.run_once():
        pass
    assert seen == [failed]


async def test_exhausted_hook_runs_when_the_lease_expired_on_the_last_attempt(
    db,
) -> None:
    seen: list[int] = []

    async def hook(context: JobContext) -> None:
        seen.append(context.job_id)
        raise RuntimeError("hook broken")

    @register_handler("hooked-lease", on_exhausted=hook)
    async def never(_context: JobContext) -> None:
        return None

    job_id = await _enqueue(db, "hl", "hooked-lease", max_attempts=1)
    async with db.session() as session:
        await queue.claim_next(session, now=NOW, lease_seconds=1)
    later = NOW + timedelta(minutes=5)
    runner = JobRunner(WorkshopConfig(lease_seconds=30), db.session, lambda: later)
    assert not await runner.run_once()
    assert seen == [job_id]
    assert (await _job(db, job_id)).status == JobStatus.FAILED


async def test_runner_logs_duration_status_and_error_class_without_content(
    db, caplog: pytest.LogCaptureFixture
) -> None:
    @register_handler("telemetry")
    async def secret(_context: JobContext) -> None:
        raise TransientJobError("vertraulicher Text")

    await _enqueue(db, "t", "telemetry", payload={"geheim": "Kundendaten"})
    with caplog.at_level("INFO", logger="alloq_offer.workshop.jobs.runner"):
        await _runner(db).run_once()
    line = next(r.getMessage() for r in caplog.records if "telemetry" in r.getMessage())
    assert "retry" in line
    assert "TransientJobError" in line
    assert " s," in line
    assert "Kundendaten" not in caplog.text
    assert "vertraulicher" not in caplog.text
