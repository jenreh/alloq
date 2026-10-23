from datetime import UTC, datetime

from alloq_offer.workshop.entities import DocState
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.repositories import job_repo, workspace_repo
from alloq_offer.workshop.services.workspace import open_workspace


async def test_open_workspace_creates_once_with_template_binding(db) -> None:
    async with db.session() as session:
        first = await open_workspace(session, 1, "Anna")
        await session.flush()
        first_id = first.id
    async with db.session() as session:
        second = await open_workspace(session, 1, "Bea")
        assert second.id == first_id
        assert second.created_by == "Anna"
        assert second.template_key == "quo_v1"
        assert second.template_version.startswith("quo_v1")
        assert second.doc_state == DocState.DRAFT
        assert (second.map_revision, second.story_seq) == (0, 0)
        assert second.to_dict()["offer_id"] == 1


async def test_find_by_offer_returns_none_without_workspace(db) -> None:
    async with db.session() as session:
        assert await workspace_repo.find_by_offer(session, 1) is None


async def test_find_latest_job_per_kind(db) -> None:
    now = datetime(2026, 10, 23, tzinfo=UTC)
    async with db.session() as session:
        for key in ("a", "b"):
            await queue.enqueue(
                session,
                kind="x",
                offer_id=1,
                idempotency_key=key,
                now=now,
                max_attempts=3,
            )
        await session.flush()
        latest = await job_repo.find_latest(session, 1, "x")
        assert latest is not None
        assert latest.idempotency_key == "b"
        assert await job_repo.find_latest(session, 1, "other") is None
        assert latest.to_dict()["kind"] == "x"
