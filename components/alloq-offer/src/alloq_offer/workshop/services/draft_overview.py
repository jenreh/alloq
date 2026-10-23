"""What the "Entwurf" tab shows: stage progress, counts and open decisions."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.entities import (
    ActivityEntity,
    ChapterEntity,
    ExportEntity,
    ExportKind,
    ExportStatus,
    JobStatus,
    Scope,
    SourceStatus,
    StatementEntity,
    StatementStatus,
    StatementType,
    StoryEntity,
)
from alloq_offer.workshop.repositories import job_repo, source_repo, workspace_repo
from alloq_offer.workshop.services import commercials, findings
from alloq_offer.workshop.services.chapter_draft import DRAFT_CHAPTERS_JOB
from alloq_offer.workshop.services.exports import EXPORT_JOB
from alloq_offer.workshop.services.review_request import REVIEW_JOB
from alloq_offer.workshop.services.sources import INITIAL_DRAFT_JOB

DONE = "erledigt"
RUNNING = "läuft"
WAITING = "wartet"
FAILED = "fehlgeschlagen"
OPEN = "offen"
JOB_STATES: dict[str, str] = {
    JobStatus.QUEUED: WAITING,
    JobStatus.RUNNING: RUNNING,
    JobStatus.SUCCEEDED: DONE,
    JobStatus.FAILED: FAILED,
    JobStatus.CANCELLED: FAILED,
}
SOURCES_STAGE = "Quellen lesen"
JOB_STAGES: tuple[tuple[str, str], ...] = (
    ("Story Map und Briefing", INITIAL_DRAFT_JOB),
    ("Kapitel schreiben", DRAFT_CHAPTERS_JOB),
    ("KI-Prüfung", REVIEW_JOB),
    ("Word-Entwurf", EXPORT_JOB),
)
OPEN_POINT_TYPES = (StatementType.OPEN_POINT, StatementType.CONFLICT)

# Where a decision is made; the tab values of ``WorkshopState``.
DECISION_SCOPE = "scope"
TARGET_BRIEFING = "briefing"
TARGET_CHAPTERS = "chapters"


@dataclass
class Overview:
    stages: list[dict[str, str]] = field(default_factory=list)
    activities: int = 0
    stories: int = 0
    offered: int = 0
    chapters_written: int = 0
    chapters_total: int = 0
    map_revision: int = 0
    draft_export_id: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def working(self) -> bool:
        return any(stage["status"] in (RUNNING, WAITING) for stage in self.stages)


async def _sources_stage(session: AsyncSession, offer_id: int) -> str:
    rows = [s for s in await source_repo.list_current(session, offer_id) if s.included]
    if not rows:
        return OPEN
    if any(s.status in (SourceStatus.UPLOADED, SourceStatus.PROCESSING) for s in rows):
        return RUNNING
    return DONE


async def _stages(session: AsyncSession, offer_id: int) -> list[dict[str, str]]:
    stages = [
        {"label": SOURCES_STAGE, "status": await _sources_stage(session, offer_id)}
    ]
    for label, kind in JOB_STAGES:
        job = await job_repo.find_latest(session, offer_id, kind)
        status = JOB_STATES.get(job.status, OPEN) if job is not None else OPEN
        stages.append({"label": label, "status": status})
    return stages


async def _count(session: AsyncSession, entity: type, *where: object) -> int:
    return (
        await session.scalar(select(func.count()).select_from(entity).where(*where))
        or 0
    )


async def _decisions(
    session: AsyncSession, offer_id: int, skeleton_open: int
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    if skeleton_open:
        decisions.append(
            {
                "key": DECISION_SCOPE,
                "title": "Umfang bestätigen",
                "text": f"{skeleton_open} Stories des Grundgerüsts sind als Umfang "
                "vorgeschlagen. Erst nach Ihrer Bestätigung gelten sie als angeboten.",
                "action": "Umfang bestätigen",
            }
        )
    open_points = await _count(
        session,
        StatementEntity,
        StatementEntity.offer_id == offer_id,
        StatementEntity.type.in_(OPEN_POINT_TYPES),
        StatementEntity.status != StatementStatus.CONFIRMED,
    )
    if open_points:
        decisions.append(
            {
                "key": TARGET_BRIEFING,
                "title": "Offene Punkte klären",
                "text": f"{open_points} offene Punkte oder Widersprüche im Briefing.",
                "action": "Briefing öffnen",
            }
        )
    workspace = await workspace_repo.find_by_offer(session, offer_id)
    offer = await session.get(OfferEntity, offer_id)
    if (
        workspace is not None
        and offer is not None
        and workspace.price_required
        and not commercials.is_confirmed(
            workspace, commercials.current_values(offer, workspace)
        )
    ):
        decisions.append(
            {
                "key": TARGET_CHAPTERS,
                "title": "Kalkulation bestätigen",
                "text": "Preis und Aufwand sind noch nicht bestätigt.",
                "action": "Kapitel öffnen",
            }
        )
    blockers = len(await findings.open_blockers(session, offer_id))
    if blockers:
        decisions.append(
            {
                "key": TARGET_CHAPTERS,
                "title": "Blocker auflösen",
                "text": f"{blockers} Prüfergebnisse verhindern die finale Fassung.",
                "action": "Kapitel öffnen",
            }
        )
    return decisions


async def load_overview(session: AsyncSession, offer_id: int) -> Overview:
    workspace = await workspace_repo.find_by_offer(session, offer_id)
    overview = Overview(stages=await _stages(session, offer_id))
    if workspace is None:
        return overview
    live = (StoryEntity.offer_id == offer_id, StoryEntity.archived_at.is_(None))
    overview.map_revision = workspace.map_revision
    overview.activities = await _count(
        session,
        ActivityEntity,
        ActivityEntity.offer_id == offer_id,
        ActivityEntity.archived_at.is_(None),
    )
    overview.stories = await _count(session, StoryEntity, *live)
    overview.offered = await _count(
        session, StoryEntity, *live, StoryEntity.scope == Scope.OFFERED
    )
    skeleton_open = await _count(
        session,
        StoryEntity,
        *live,
        StoryEntity.skeleton.is_(True),
        StoryEntity.scope == Scope.OPEN,
    )
    overview.chapters_total = await _count(
        session, ChapterEntity, ChapterEntity.offer_id == offer_id
    )
    overview.chapters_written = await _count(
        session,
        ChapterEntity,
        ChapterEntity.offer_id == offer_id,
        ChapterEntity.revision > 1,
    )
    overview.draft_export_id = (
        await session.scalar(
            select(func.max(ExportEntity.id)).where(
                ExportEntity.offer_id == offer_id,
                ExportEntity.kind == ExportKind.DRAFT,
                ExportEntity.status == ExportStatus.READY,
            )
        )
        or 0
    )
    overview.decisions = await _decisions(session, offer_id, skeleton_open)
    return overview
