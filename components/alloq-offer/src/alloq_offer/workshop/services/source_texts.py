"""The readable sources of an offer as prompt data."""

from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.ai.port import BlockText, SourceText
from alloq_offer.workshop.entities import SourceKind
from alloq_offer.workshop.extraction.models import KIND_GAP, anchor_label
from alloq_offer.workshop.repositories import source_block_repo, source_repo
from alloq_offer.workshop.services.sources import READABLE_STATUSES

KIND_NAMES = {
    SourceKind.EML: "E-Mail",
    SourceKind.AUDIO: "Mitschnitt",
    SourceKind.PPTX: "Folien",
}


async def load_source_texts(
    session: AsyncSession, offer_id: int
) -> tuple[list[SourceText], set[int]]:
    """Included, readable sources with their blocks and the ids a model may cite."""
    sources: list[SourceText] = []
    valid_ids: set[int] = set()
    for source in await source_repo.list_current(session, offer_id):
        if not source.included or source.status not in READABLE_STATUSES:
            continue
        blocks = await source_block_repo.list_for_source(session, source.id)
        texts = [
            BlockText(b.id, b.text, anchor_label(b.anchor), b.speaker)
            for b in blocks
            if b.kind != KIND_GAP
        ]
        valid_ids.update(block.id for block in texts)
        sources.append(
            SourceText(
                id=source.id,
                title=source.title,
                kind=KIND_NAMES.get(SourceKind(source.kind), "Dokument"),
                blocks=texts,
                gaps=[b.text for b in blocks if b.kind == KIND_GAP],
            )
        )
    return sources, valid_ids
