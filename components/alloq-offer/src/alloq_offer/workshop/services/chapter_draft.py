"""Ask for chapter drafts: queue the job ``draft_chapters`` (spec 9.4)."""

from datetime import datetime

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import JobEntity, JobStatus
from alloq_offer.workshop.export.template_package import load_template
from alloq_offer.workshop.jobs import queue
from alloq_offer.workshop.repositories import job_repo, workspace_repo

DRAFT_CHAPTERS_JOB = "draft_chapters"
NO_WORKSPACE = "Zu diesem Angebot gibt es noch keine Werkstatt."
NOT_DRAFTABLE = "Für dieses Kapitel gibt es keinen KI-Vorschlag."
NOTHING_TO_DRAFT_FROM = "Es gibt noch keine Story Map und kein Briefing als Grundlage."


class ChapterDraftError(ValueError):
    """Nothing can be drafted; the message is German and shown to users."""


async def request_chapter_draft(
    session_factory: SessionFactory,
    offer_id: int,
    *,
    keys: list[str] | None,
    instruction: str,
    now: datetime,
    max_attempts: int,
) -> JobEntity:
    """Queue a draft. ``keys`` None means every prose chapter nobody has written yet.

    Waiting or running drafts of the offer are not doubled: the key counts the
    drafts, so two clicks at once meet in the same queue entry.
    """
    async with session_factory() as session:
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        if workspace is None:
            raise ChapterDraftError(NO_WORKSPACE)
        template = load_template(workspace.template_key)
        for key in keys or []:
            if template.chapter(key).chapter_type != "prose":
                raise ChapterDraftError(NOT_DRAFTABLE)
        latest = await job_repo.find_latest(session, offer_id, DRAFT_CHAPTERS_JOB)
        if latest is not None and latest.status in (
            JobStatus.QUEUED,
            JobStatus.RUNNING,
        ):
            return latest
        number = await job_repo.count_of_kind(session, offer_id, DRAFT_CHAPTERS_JOB)
        return await queue.enqueue(
            session,
            kind=DRAFT_CHAPTERS_JOB,
            offer_id=offer_id,
            idempotency_key=f"{DRAFT_CHAPTERS_JOB}:{offer_id}:{number + 1}",
            payload={"keys": keys, "instruction": instruction.strip()[:2000]},
            now=now,
            max_attempts=max_attempts,
        )
