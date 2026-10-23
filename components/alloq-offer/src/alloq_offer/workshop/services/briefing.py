"""The briefing: statements by type, with the places in the sources they rest on."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    SourceBlockEntity,
    SourceEntity,
    StatementEntity,
    StatementStatus,
    StatementType,
)
from alloq_offer.workshop.extraction.models import anchor_label

TYPE_ORDER = [
    StatementType.REQUIREMENT,
    StatementType.FACT,
    StatementType.SOLUTION,
    StatementType.ASSUMPTION,
    StatementType.OPEN_POINT,
    StatementType.CONFLICT,
]


async def _ref_labels(session: AsyncSession, block_ids: set[int]) -> dict[int, str]:
    if not block_ids:
        return {}
    rows = await session.execute(
        select(SourceBlockEntity.id, SourceBlockEntity.anchor, SourceEntity.title)
        .join(SourceEntity, SourceEntity.id == SourceBlockEntity.source_id)
        .where(SourceBlockEntity.id.in_(block_ids), SourceEntity.revoked_at.is_(None))
    )
    return {
        block_id: ", ".join(filter(None, [title, anchor_label(anchor)]))
        for block_id, anchor, title in rows.all()
    }


async def load_briefing(session: AsyncSession, offer_id: int) -> list[dict[str, Any]]:
    """Statement groups in the order of ``TYPE_ORDER``; empty groups are left out."""
    statements = list(
        (
            await session.scalars(
                select(StatementEntity)
                .where(StatementEntity.offer_id == offer_id)
                .order_by(StatementEntity.id)
            )
        ).all()
    )
    labels = await _ref_labels(
        session, {ref for s in statements for ref in s.source_refs}
    )
    groups: list[dict[str, Any]] = []
    for type_ in TYPE_ORDER:
        items = [
            {
                "id": s.id,
                "text": s.text,
                "confirmed": s.status == StatementStatus.CONFIRMED,
                "recheck": s.needs_recheck,
                "confirmed_by": s.confirmed_by or "",
                "refs": [labels[r] for r in s.source_refs if r in labels],
            }
            for s in statements
            if s.type == type_
        ]
        if items:
            groups.append({"type": type_.value, "items": items})
    return groups


async def set_confirmed(
    session_factory: SessionFactory,
    offer_id: int,
    statement_id: int,
    *,
    confirmed: bool,
    user: str,
    now: datetime,
) -> bool:
    """Confirm a statement as a professional decision, or take that back.

    Only this explicit action changes the status; drafting never confirms (A17).
    """
    async with session_factory() as session:
        statement = await session.get(StatementEntity, statement_id)
        if statement is None or statement.offer_id != offer_id:
            return False
        statement.status = (
            StatementStatus.CONFIRMED if confirmed else StatementStatus.PROPOSED
        )
        statement.confirmed_by = user if confirmed else None
        statement.confirmed_at = now if confirmed else None
        if confirmed:
            statement.needs_recheck = False
        return True
