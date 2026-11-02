"""Withdraw a source: block its use at once, delete its content, flag dependents.

Spec 15: a revoked or deleted source is closed for further use immediately. What
was derived from it stays visible but marked, and the stored blob and extracted
blocks are removed. Findings point at the dangling references afterwards.
"""

import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    BlobEntity,
    ExportEntity,
    SourceBlockEntity,
    SourceEntity,
    StatementEntity,
)
from alloq_offer.workshop.repositories import source_repo, workspace_repo
from alloq_offer.workshop.services.chapters import mark_dependent_review

logger = logging.getLogger(__name__)

REVIEW_REASON = "Eine Quelle wurde zurückgezogen."


async def _version_chain(
    session: AsyncSession, offer_id: int, source_id: int
) -> list[SourceEntity]:
    """The source with all older and newer versions of the same file."""
    rows = list(
        (
            await session.scalars(
                select(SourceEntity).where(SourceEntity.offer_id == offer_id)
            )
        ).all()
    )
    by_id = {row.id: row for row in rows}
    neighbours: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        if row.replaces_id is not None:
            neighbours[row.id].add(row.replaces_id)
            neighbours[row.replaces_id].add(row.id)
    chain: set[int] = set()
    todo = [source_id] if source_id in by_id else []
    while todo:
        current = todo.pop()
        if current not in chain:
            chain.add(current)
            todo.extend(neighbours[current])
    return [by_id[i] for i in chain]


async def _drop_blob_if_unused(session: AsyncSession, blob_id: int) -> None:
    # Blobs are shared by content hash, so an export may hold the same bytes.
    still_used = 0
    for entity in (SourceEntity, ExportEntity):
        still_used += (
            await session.scalar(
                select(func.count())
                .select_from(entity)
                .where(entity.blob_id == blob_id)
            )
            or 0
        )
    if not still_used:
        await session.execute(delete(BlobEntity).where(BlobEntity.id == blob_id))


async def revoke_source(
    session_factory: SessionFactory, offer_id: int, source_id: int, *, now: datetime
) -> bool:
    """Revoke a source and its older versions; False when it is not in this offer."""
    async with session_factory() as session:
        if await source_repo.find_in_offer(session, offer_id, source_id) is None:
            return False
        sources = await _version_chain(session, offer_id, source_id)
        live = [s for s in sources if s.revoked_at is None]
        if not live:
            return False
        source_ids = [s.id for s in live]
        block_ids = set(
            (
                await session.scalars(
                    select(SourceBlockEntity.id).where(
                        SourceBlockEntity.source_id.in_(source_ids)
                    )
                )
            ).all()
        )
        blob_ids = {s.blob_id for s in live if s.blob_id is not None}
        for source in live:
            source.revoked_at = now
            source.included = False
            source.blob_id = None
        await session.execute(
            delete(SourceBlockEntity).where(SourceBlockEntity.source_id.in_(source_ids))
        )
        await session.flush()
        for blob_id in blob_ids:
            await _drop_blob_if_unused(session, blob_id)
        for statement in (
            await session.scalars(
                select(StatementEntity).where(StatementEntity.offer_id == offer_id)
            )
        ).all():
            if block_ids & set(statement.source_refs):
                statement.needs_recheck = True
        workspace = await workspace_repo.find_by_offer(session, offer_id)
        if workspace is not None:
            await mark_dependent_review(session, workspace, REVIEW_REASON)
        logger.info("Revoked %d source versions of offer %s", len(live), offer_id)
        return True
