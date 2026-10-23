"""Job ``initial_draft``: sources to story map and briefing, then the chapters.

The first stage of the one-click draft (spec 9.1); see ``draft_pipeline``.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    OfferAi,
    SourceText,
)
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import GenerationRunEntity
from alloq_offer.workshop.jobs.ai_access import job_ai
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
    register_handler,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.draft_pipeline import queue_initial_chapters
from alloq_offer.workshop.services.map_apply import apply_briefing, apply_proposed_map
from alloq_offer.workshop.services.source_texts import load_source_texts
from alloq_offer.workshop.services.sources import INITIAL_DRAFT_JOB
from alloq_offer.workshop.services.workspace import open_workspace
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

AI_FAILED = "Die KI konnte keinen Entwurf liefern. Bitte prüfen Sie die Einrichtung."
AI_BUSY = "Die KI ist gerade nicht erreichbar. Der Auftrag wird erneut versucht."


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
            await queue_initial_chapters(
                session,
                ctx.offer_id,
                now=datetime.now(UTC),
                max_attempts=ctx.max_attempts,
            )
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
            sources, valid_ids = await load_source_texts(session, offer_id)
        return (sources, valid_ids) if sources else None


@register_handler(INITIAL_DRAFT_JOB)
async def initial_draft(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    return await InitialDraft(job_ai(config), get_asyncdb_session).run(ctx)
