"""Findings: run the rule checks, keep decisions and answer who blocks the output.

Findings are matched by a fingerprint, so a decision survives a new run as long as
the problem is still there. A problem that went away is marked fixed; one that
comes back opens again.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.content.schema import parse_content
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    ChapterEntity,
    FindingDecision,
    FindingEntity,
    FindingSeverity,
    FindingSource,
    SourceBlockEntity,
    SourceEntity,
    StatementEntity,
    StatementStatus,
    WorkspaceEntity,
)
from alloq_offer.workshop.export.template_package import load_template
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapters import current_revisions
from alloq_offer.workshop.services.checks import (
    ChapterFacts,
    CheckInput,
    RuleFinding,
    StatementFacts,
    run_rules,
)
from alloq_offer.workshop.services.commercials import (
    current_values,
    is_confirmed,
    void_if_changed,
)
from alloq_offer.workshop.services.map_apply import snapshot_map
from alloq_offer.workshop.services.workspace import NO_WORKSPACE

logger = logging.getLogger(__name__)

NOT_FOUND = "Der Befund gibt es nicht mehr."
REASON_NEEDED = "Bitte nennen Sie eine Begründung."
NOT_ACCEPTABLE = "Ein blockierender Befund kann nicht akzeptiert werden."
MIN_REASON = 3
DECISION_UNKNOWN = "Diese Entscheidung gibt es nicht."


class FindingError(ValueError):
    """The decision is not allowed; the message is German and shown to users."""


def fingerprint(source: FindingSource, issue: RuleFinding) -> str:
    identity = issue.key or (issue.message if source == FindingSource.AI else "")
    raw = f"{source}|{issue.rule}|{issue.target}|{identity}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def load_check_input(session: AsyncSession, offer_id: int) -> CheckInput | None:
    workspace = await workspace_repo.find_by_offer(session, offer_id)
    offer = await session.get(OfferEntity, offer_id)
    if workspace is None or offer is None:
        return None
    await void_if_changed(session, workspace, offer)
    template = load_template(workspace.template_key)
    chapters = {
        c.chapter_key: c
        for c in (
            await session.scalars(
                select(ChapterEntity).where(ChapterEntity.offer_id == offer_id)
            )
        ).all()
    }
    stored_by_chapter = await current_revisions(session, list(chapters.values()))
    facts: list[ChapterFacts] = []
    for definition in template.chapters:
        chapter = chapters.get(definition.key)
        if chapter is None:
            continue
        stored = stored_by_chapter[chapter.id]
        facts.append(
            ChapterFacts(
                key=definition.key,
                title=definition.title,
                chapter_type=definition.chapter_type,
                required=definition.required,
                content=parse_content(stored.content),
                needs_review=chapter.needs_review,
                review_reason=chapter.review_reason,
            )
        )
    statements = (
        await session.scalars(
            select(StatementEntity).where(StatementEntity.offer_id == offer_id)
        )
    ).all()
    revoked = await session.scalars(
        select(SourceBlockEntity.id)
        .join(SourceEntity, SourceEntity.id == SourceBlockEntity.source_id)
        .where(SourceEntity.offer_id == offer_id, SourceEntity.revoked_at.is_not(None))
    )
    return CheckInput(
        chapters=facts,
        snapshot=await snapshot_map(session, workspace),
        statements=[
            StatementFacts(
                s.id,
                s.type,
                s.text,
                s.status == StatementStatus.CONFIRMED,
                list(s.source_refs),
            )
            for s in statements
        ],
        days=offer.person_days,
        risk_days=offer.risk_buffer_days,
        cost=offer.production_cost,
        price=offer.recommended_price,
        price_required=workspace.price_required,
        commercials_confirmed=is_confirmed(workspace, current_values(offer, workspace)),
        map_revision=workspace.map_revision,
        revoked_block_ids=set(revoked.all()),
    )


async def _insert(session: AsyncSession, row: FindingEntity) -> None:
    """Add a finding; a concurrent run that stored the same one first wins."""
    try:
        async with session.begin_nested():
            session.add(row)
    except IntegrityError:
        logger.debug("Finding %s was stored by a concurrent run", row.fingerprint)


async def sync(
    session: AsyncSession,
    offer_id: int,
    source: FindingSource,
    issues: list[RuleFinding],
    map_revision: int,
) -> None:
    """Store ``issues`` of one source; decisions of unchanged problems are kept."""
    stored = {
        f.fingerprint: f
        for f in (
            await session.scalars(
                select(FindingEntity).where(
                    FindingEntity.offer_id == offer_id, FindingEntity.source == source
                )
            )
        ).all()
    }
    seen: set[str] = set()
    for issue in issues:
        key = fingerprint(source, issue)
        seen.add(key)
        row = stored.get(key)
        if row is None:
            await _insert(
                session,
                FindingEntity(
                    offer_id=offer_id,
                    fingerprint=key,
                    rule=issue.rule,
                    severity=issue.severity,
                    source=source,
                    target=issue.target,
                    message=issue.message,
                    map_revision=map_revision,
                ),
            )
            continue
        row.message = issue.message
        row.severity = issue.severity
        row.map_revision = map_revision
        if row.decision == FindingDecision.FIXED:
            row.decision = FindingDecision.OPEN
            row.reason = ""
    for key, row in stored.items():
        if key not in seen and row.decision != FindingDecision.FIXED:
            row.decision = FindingDecision.FIXED


async def run_checks(session_factory: SessionFactory, offer_id: int) -> int:
    """Run all rule checks; returns the number of open findings of the rules."""
    async with session_factory() as session:
        # Runs of one offer queue up here, so they never store the same finding twice.
        await session.execute(
            select(WorkspaceEntity.id)
            .where(WorkspaceEntity.offer_id == offer_id)
            .with_for_update()
        )
        data = await load_check_input(session, offer_id)
        if data is None:
            raise FindingError(NO_WORKSPACE)
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        assert workspace is not None  # noqa: S101  # load_check_input found it
        found = run_rules(data)
        await sync(session, offer_id, FindingSource.RULE, found, workspace.map_revision)
    logger.info("Checks of offer %s found %d problems", offer_id, len(found))
    return len(found)


def finding_row(row: FindingEntity) -> dict[str, Any]:
    return {
        "id": row.id,
        "rule": row.rule,
        "severity": row.severity,
        "source": row.source,
        "target": row.target,
        "message": row.message,
        "decision": row.decision,
        "reason": row.reason,
        "decided_by": row.decided_by,
        "acceptable": row.severity != FindingSeverity.BLOCKER,
    }


async def list_findings(
    session_factory: SessionFactory, offer_id: int
) -> list[dict[str, Any]]:
    """Open and accepted findings, blockers first."""
    order = {
        str(FindingSeverity.BLOCKER): 0,
        str(FindingSeverity.WARNING): 1,
        str(FindingSeverity.NOTE): 2,
    }
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(FindingEntity).where(
                    FindingEntity.offer_id == offer_id,
                    FindingEntity.decision != FindingDecision.FIXED,
                )
            )
        ).all()
    return [
        finding_row(r) for r in sorted(rows, key=lambda r: (order[r.severity], r.id))
    ]


async def open_blockers(session: AsyncSession, offer_id: int) -> list[FindingEntity]:
    """Findings that keep the final output closed."""
    return list(
        (
            await session.scalars(
                select(FindingEntity).where(
                    FindingEntity.offer_id == offer_id,
                    FindingEntity.severity == FindingSeverity.BLOCKER,
                    FindingEntity.decision == FindingDecision.OPEN,
                )
            )
        ).all()
    )


async def decide(
    session_factory: SessionFactory,
    offer_id: int,
    finding_id: int,
    decision: FindingDecision,
    *,
    reason: str,
    user: str,
    now: datetime,
) -> None:
    """Accept a finding with a reason, or open an accepted one again."""
    async with session_factory() as session:
        row = await session.get(FindingEntity, finding_id)
        if row is None or row.offer_id != offer_id:
            raise FindingError(NOT_FOUND)
        if decision == FindingDecision.ACCEPTED:
            if row.severity == FindingSeverity.BLOCKER:
                raise FindingError(NOT_ACCEPTABLE)
            if len(reason.strip()) < MIN_REASON:
                raise FindingError(REASON_NEEDED)
            row.reason = reason.strip()
            row.decided_by = user
            row.decided_at = now
            row.decision = FindingDecision.ACCEPTED
        elif decision == FindingDecision.OPEN:
            row.decision = FindingDecision.OPEN
            row.reason = ""
            row.decided_by = ""
            row.decided_at = None
        else:
            raise FindingError(DECISION_UNKNOWN)
