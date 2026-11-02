"""What the "Entwurf" tab shows: stage progress, counts and open decisions."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, Row, ScalarSelect, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.entities import (
    ActivityEntity,
    ChapterEntity,
    ExportEntity,
    ExportKind,
    ExportStatus,
    JobEntity,
    JobStatus,
    SourceEntity,
    SourceStatus,
    StatementEntity,
    StatementStatus,
    StatementType,
    StoryEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.repositories import workspace_repo
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
TARGET_BRIEFING = "briefing"
TARGET_CHAPTERS = "chapters"


@dataclass
class Overview:
    stages: list[dict[str, str]] = field(default_factory=list)
    activities: int = 0
    stories: int = 0
    chapters_written: int = 0
    chapters_total: int = 0
    map_revision: int = 0
    draft_export_id: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def working(self) -> bool:
        return any(stage["status"] in (RUNNING, WAITING) for stage in self.stages)


def _count(entity: type, *where: ColumnElement[bool]) -> ScalarSelect[int]:
    return select(func.count()).select_from(entity).where(*where).scalar_subquery()


def _current_sources(offer_id: int) -> tuple[ColumnElement[bool], ...]:
    """Included sources that are neither revoked nor replaced by a newer version."""
    newer = aliased(SourceEntity)
    return (
        SourceEntity.offer_id == offer_id,
        SourceEntity.revoked_at.is_(None),
        SourceEntity.included.is_(True),
        ~exists().where(
            newer.replaces_id == SourceEntity.id, newer.revoked_at.is_(None)
        ),
    )


def _latest_status(offer_id: int, kind: str) -> ScalarSelect[str]:
    return (
        select(JobEntity.status)
        .where(JobEntity.offer_id == offer_id, JobEntity.kind == kind)
        .order_by(JobEntity.id.desc())
        .limit(1)
        .scalar_subquery()
    )


async def _numbers(session: AsyncSession, offer_id: int) -> Row[Any]:
    """Stages, counts and blockers of the tab in one round trip to the database."""
    in_outline = (
        ChapterEntity.offer_id == offer_id,
        ChapterEntity.removed_at.is_(None),
    )
    sources = _current_sources(offer_id)
    return (
        await session.execute(
            select(
                _count(SourceEntity, *sources).label("sources"),
                _count(
                    SourceEntity,
                    *sources,
                    SourceEntity.status.in_(
                        (SourceStatus.UPLOADED, SourceStatus.PROCESSING)
                    ),
                ).label("sources_working"),
                *(
                    _latest_status(offer_id, kind).label(f"job_{index}")
                    for index, (_, kind) in enumerate(JOB_STAGES)
                ),
                _count(
                    ActivityEntity,
                    ActivityEntity.offer_id == offer_id,
                    ActivityEntity.archived_at.is_(None),
                ).label("activities"),
                _count(
                    StoryEntity,
                    StoryEntity.offer_id == offer_id,
                    StoryEntity.archived_at.is_(None),
                ).label("stories"),
                _count(ChapterEntity, *in_outline).label("chapters_total"),
                _count(ChapterEntity, *in_outline, ChapterEntity.revision > 1).label(
                    "chapters_written"
                ),
                select(func.max(ExportEntity.id))
                .where(
                    ExportEntity.offer_id == offer_id,
                    ExportEntity.kind == ExportKind.DRAFT,
                    ExportEntity.status == ExportStatus.READY,
                )
                .scalar_subquery()
                .label("draft_export_id"),
                _count(
                    StatementEntity,
                    StatementEntity.offer_id == offer_id,
                    StatementEntity.type.in_(OPEN_POINT_TYPES),
                    StatementEntity.status != StatementStatus.CONFIRMED,
                ).label("open_points"),
                findings.open_blocker_count(offer_id).label("blockers"),
            )
        )
    ).one()


def _stages(numbers: Row[Any]) -> list[dict[str, str]]:
    if not numbers.sources:
        sources = OPEN
    elif numbers.sources_working:
        sources = RUNNING
    else:
        sources = DONE
    stages = [{"label": SOURCES_STAGE, "status": sources}]
    for index, (label, _) in enumerate(JOB_STAGES):
        status = getattr(numbers, f"job_{index}")
        stages.append({"label": label, "status": JOB_STATES.get(status, OPEN)})
    return stages


def _decisions(
    workspace: WorkspaceEntity, offer: OfferEntity, numbers: Row[Any]
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    if numbers.open_points:
        decisions.append(
            {
                "key": TARGET_BRIEFING,
                "title": "Offene Punkte klären",
                "text": (
                    f"{numbers.open_points} offene Punkte oder Widersprüche "
                    "im Briefing."
                ),
                "action": "Briefing öffnen",
            }
        )
    if workspace.price_required and not commercials.is_confirmed(
        workspace, commercials.current_values(offer, workspace)
    ):
        decisions.append(
            {
                "key": TARGET_CHAPTERS,
                "title": "Kalkulation bestätigen",
                "text": "Preis und Aufwand sind noch nicht bestätigt.",
                "action": "Kapitel öffnen",
            }
        )
    if numbers.blockers:
        decisions.append(
            {
                "key": TARGET_CHAPTERS,
                "title": "Blocker auflösen",
                "text": (
                    f"{numbers.blockers} Prüfergebnisse verhindern die finale Fassung."
                ),
                "action": "Kapitel öffnen",
            }
        )
    return decisions


async def load_overview(session: AsyncSession, offer_id: int) -> Overview:
    """What the tab shows, in two queries."""
    numbers = await _numbers(session, offer_id)
    overview = Overview(stages=_stages(numbers))
    found = await workspace_repo.find_with_offer(session, offer_id)
    if found is None:
        return overview
    workspace, offer = found
    overview.map_revision = workspace.map_revision
    overview.activities = numbers.activities or 0
    overview.stories = numbers.stories or 0
    overview.chapters_total = numbers.chapters_total or 0
    overview.chapters_written = numbers.chapters_written or 0
    overview.draft_export_id = numbers.draft_export_id or 0
    overview.decisions = _decisions(workspace, offer, numbers)
    return overview
