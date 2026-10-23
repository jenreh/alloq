"""Job ``propose_map_additions``: more map as a proposal, never as an edit.

The result waits as a comparison until a person takes it over. It is bound to the
map revision it was made for, so a map that changed meanwhile makes it stale (A07).
"""

import logging

from sqlalchemy import select

from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    MapAdditionAi,
    MapRequest,
)
from alloq_offer.workshop.ai.render import map_outline, statement_line
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    GenerationRunEntity,
    StatementEntity,
    StatementStatus,
)
from alloq_offer.workshop.jobs.ai_access import job_ai
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
    register_handler,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.map_apply import snapshot_map
from alloq_offer.workshop.services.map_proposals import (
    DEFAULT_INSTRUCTION,
    MAP_PROPOSAL_JOB,
    store_proposal,
)
from alloq_offer.workshop.services.source_texts import load_source_texts
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

AI_FAILED = "Die KI konnte keinen Vorschlag liefern. Bitte prüfen Sie die Einrichtung."
AI_BUSY = "Die KI ist gerade nicht erreichbar. Der Auftrag wird erneut versucht."


class ProposeMapAdditions:
    def __init__(self, ai: MapAdditionAi, session_factory: SessionFactory) -> None:
        self._ai = ai
        self._session_factory = session_factory

    async def _request(self, ctx: JobContext) -> tuple[MapRequest, int] | None:
        async with self._session_factory() as session:
            workspace = await workspace_repo.find_by_offer(session, ctx.offer_id)
            if workspace is None or workspace.map_revision == 0:
                return None
            sources, _ = await load_source_texts(session, ctx.offer_id)
            statements = (
                await session.scalars(
                    select(StatementEntity).where(
                        StatementEntity.offer_id == ctx.offer_id
                    )
                )
            ).all()
            request = MapRequest(
                instruction=str(ctx.payload.get("instruction") or DEFAULT_INSTRUCTION),
                map_outline=map_outline(await snapshot_map(session, workspace)),
                statements=[
                    statement_line(
                        s.type, s.text, s.status == StatementStatus.CONFIRMED
                    )
                    for s in statements
                ],
                sources=sources,
            )
            return request, workspace.map_revision

    async def run(self, ctx: JobContext) -> dict:
        loaded = await self._request(ctx)
        if loaded is None:
            return {"status": "skipped", "reason": "no map"}
        request, revision = loaded
        try:
            proposed = await self._ai.propose_map_additions(request)
        except AiTransientError as exc:
            raise TransientJobError(AI_BUSY) from exc
        except AiUnavailableError as exc:
            raise PermanentJobError(AI_FAILED) from exc
        async with self._session_factory() as session:
            await store_proposal(
                session,
                offer_id=ctx.offer_id,
                proposed=proposed,
                map_revision=revision,
                instruction=request.instruction,
                job_id=ctx.job_id,
            )
            session.add(
                GenerationRunEntity(
                    offer_id=ctx.offer_id,
                    job_id=ctx.job_id,
                    kind=MAP_PROPOSAL_JOB,
                    model=self._ai.model_name,
                    prompt_version=self._ai.map_additions_prompt_version,
                    input_revisions={"map": revision},
                    status="ok",
                )
            )
        logger.info("Map proposal for offer %s stored", ctx.offer_id)
        return {"status": "ok", "map_revision": revision}


@register_handler(MAP_PROPOSAL_JOB)
async def propose_map_additions(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    return await ProposeMapAdditions(job_ai(config), get_asyncdb_session).run(ctx)
