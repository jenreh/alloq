"""Build the fixed document state an export is made from (spec 5.6, 13.1)."""

import dataclasses
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.entities import (
    FindingDecision,
    FindingEntity,
    SnapshotEntity,
    WorkspaceEntity,
)
from alloq_offer.workshop.export.models import ResolvedStory
from alloq_offer.workshop.services.chapters import current_revisions, live_chapters
from alloq_offer.workshop.services.checks import live_stories
from alloq_offer.workshop.services.commercials import resolve_values
from alloq_offer.workshop.services.map_apply import snapshot_map
from alloq_offer.workshop.services.numbering import outline_numbers

DATE_FORMAT = "%d.%m.%Y"
QUOTE_PREFIX = "ALLOQ-"


def _cover(
    offer: OfferEntity, workspace: WorkspaceEntity, now: datetime
) -> dict[str, str]:
    validity = workspace.validity_date
    return {
        "project_title": offer.title,
        "customer_name": offer.customer,
        "customer_short": offer.customer,
        "customer_street": "",
        "customer_city": "",
        "offer_date": now.strftime(DATE_FORMAT),
        "quote_id": f"{QUOTE_PREFIX}{offer.id:05d}",
        "validity_date": validity.strftime(DATE_FORMAT) if validity else "",
    }


def _stories(snapshot: dict) -> list[dict[str, str]]:
    groups = {
        story["key"]: activity["title"]
        for activity in snapshot["activities"]
        if not activity["archived"]
        for task in activity["tasks"]
        if not task["archived"]
        for story in task["stories"]
    }
    return [
        dataclasses.asdict(
            ResolvedStory(
                key=s["key"],
                title=s["title"],
                sentence=s["sentence"],
                group=groups.get(s["key"], ""),
            )
        )
        for s in live_stories(snapshot)
    ]


async def _open_points(session: AsyncSession, offer_id: int) -> list[str]:
    rows = (
        await session.scalars(
            select(FindingEntity)
            .where(
                FindingEntity.offer_id == offer_id,
                FindingEntity.decision == FindingDecision.OPEN,
            )
            .order_by(FindingEntity.id)
        )
    ).all()
    return [row.message for row in rows]


async def build_snapshot(
    session: AsyncSession,
    workspace: WorkspaceEntity,
    offer: OfferEntity,
    *,
    user: str,
    now: datetime,
) -> SnapshotEntity:
    """Store the current chapters, stories and values as an immutable snapshot."""
    offer_id = workspace.offer_id
    rows = await live_chapters(session, offer_id)
    stored = await current_revisions(session, rows)
    numbers = outline_numbers([row.level for row in rows])
    chapters = [
        {
            "key": row.chapter_key,
            "number": number,
            "title": row.title,
            "level": row.level,
            "revision": row.revision,
            "content": stored[row.id].content,
        }
        for row, number in zip(rows, numbers, strict=True)
    ]
    number = (
        await session.scalar(
            select(func.max(SnapshotEntity.number)).where(
                SnapshotEntity.offer_id == offer_id
            )
        )
        or 0
    ) + 1
    values = {
        name: {"text": value.text, "confirmed": value.confirmed}
        for name, value in resolve_values(offer, workspace).items()
    }
    snapshot = SnapshotEntity(
        offer_id=offer_id,
        number=number,
        map_revision=workspace.map_revision,
        template_key=workspace.template_key,
        template_version=workspace.template_version,
        created_by=user,
        content={
            "cover": _cover(offer, workspace, now),
            "chapters": chapters,
            "stories": _stories(await snapshot_map(session, workspace)),
            "values": values,
            "open_points": await _open_points(session, offer_id),
        },
    )
    session.add(snapshot)
    await session.flush()
    return snapshot
