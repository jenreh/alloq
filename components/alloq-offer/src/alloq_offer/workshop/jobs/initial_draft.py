"""Job ``initial_draft``: sources to story map and briefing in one pass (spec 9.1)."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.ai.agents import create_offer_ai
from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    BlockText,
    OfferAi,
    SourceText,
)
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    GenerationRunEntity,
    SourceKind,
)
from alloq_offer.workshop.extraction.models import KIND_GAP, anchor_label
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
    register_handler,
)
from alloq_offer.workshop.repositories import (
    source_block_repo,
    source_repo,
    workspace_repo,
)
from alloq_offer.workshop.services.map_apply import apply_briefing, apply_proposed_map
from alloq_offer.workshop.services.sources import (
    INITIAL_DRAFT_JOB,
    READABLE_STATUSES,
)
from alloq_offer.workshop.services.workspace import open_workspace
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

AI_FAILED = "Die KI konnte keinen Entwurf liefern. Bitte prüfen Sie die Einrichtung."
AI_BUSY = "Die KI ist gerade nicht erreichbar. Der Auftrag wird erneut versucht."
KIND_NAMES = {
    SourceKind.EML: "E-Mail",
    SourceKind.AUDIO: "Mitschnitt",
    SourceKind.PPTX: "Folien",
}


class InitialDraft:
    """Builds the first map; an existing map is never touched by the model."""

    def __init__(self, ai: OfferAi, session_factory: SessionFactory) -> None:
        self._ai = ai
        self._session_factory = session_factory

    async def run(self, ctx: JobContext) -> dict:
        loaded = await self._load(ctx.offer_id)
        if loaded is None:
            return {"status": "skipped", "reason": "map exists or no sources"}
        sources, valid_ids = loaded
        try:
            proposed, briefing = await asyncio.gather(
                self._ai.propose_map(sources), self._ai.propose_briefing(sources)
            )
        except AiTransientError as exc:
            await self._record_run(ctx, sources, "wiederholt")
            raise TransientJobError(AI_BUSY) from exc
        except AiUnavailableError as exc:
            await self._record_run(ctx, sources, "fehlgeschlagen")
            raise PermanentJobError(AI_FAILED) from exc
        async with self._session_factory() as session:
            workspace = await open_workspace(session, ctx.offer_id, "")
            # Lock the row: a second run must wait and then see the new map.
            await session.refresh(workspace, with_for_update=True)
            if workspace.map_revision > 0:
                return {"status": "skipped", "reason": "map exists"}
            applied = await apply_proposed_map(session, workspace, proposed, valid_ids)
            statements = await apply_briefing(
                session, ctx.offer_id, briefing, valid_ids
            )
            self._add_run(session, ctx, sources, "ok")
        logger.info(
            "Initial draft of offer %s: %d stories, %d skipped",
            ctx.offer_id,
            applied.stories,
            len(applied.skipped),
        )
        return {
            "status": "ok",
            "stories": applied.stories,
            "skipped": len(applied.skipped),
            "statements": applied.statements + statements,
        }

    def _add_run(
        self,
        session: AsyncSession,
        ctx: JobContext,
        sources: list[SourceText],
        status: str,
    ) -> None:
        session.add(
            GenerationRunEntity(
                offer_id=ctx.offer_id,
                job_id=ctx.job_id,
                kind=INITIAL_DRAFT_JOB,
                model=self._ai.model_name,
                prompt_version=(
                    f"{self._ai.map_prompt_version}+{self._ai.briefing_prompt_version}"
                ),
                input_revisions={"sources": [source.id for source in sources]},
                status=status,
            )
        )

    async def _record_run(
        self, ctx: JobContext, sources: list[SourceText], status: str
    ) -> None:
        async with self._session_factory() as session:
            self._add_run(session, ctx, sources, status)

    async def _load(self, offer_id: int) -> tuple[list[SourceText], set[int]] | None:
        async with self._session_factory() as session:
            workspace = await workspace_repo.find_by_offer(session, offer_id)
            if workspace is not None and workspace.map_revision > 0:
                return None
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
        return (sources, valid_ids) if sources else None


@register_handler(INITIAL_DRAFT_JOB)
async def initial_draft(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    return await InitialDraft(create_offer_ai(config), get_asyncdb_session).run(ctx)
