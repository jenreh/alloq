"""Job ``draft_chapters``: proposals for prose chapters from map and briefing.

Later runs write nothing into a chapter: a proposal waits until a person accepts
it, and protected chapters are never drafted at all (A07). The stage of the first
draft keeps its texts as revision, because nobody has written anything yet.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from alloq_offer.workshop.ai.port import (
    AiTransientError,
    AiUnavailableError,
    ChapterAi,
    ChapterRequest,
)
from alloq_offer.workshop.ai.render import map_outline, statement_line
from alloq_offer.workshop.configuration import WorkshopConfig
from alloq_offer.workshop.content.schema import TableContent, parse_content
from alloq_offer.workshop.content.text import Content, content_lines
from alloq_offer.workshop.db import SessionFactory
from alloq_offer.workshop.entities import (
    GenerationRunEntity,
    ProposalEntity,
    ProposalStatus,
    StatementEntity,
    StatementStatus,
)
from alloq_offer.workshop.export.template_package import ChapterSettings
from alloq_offer.workshop.jobs.ai_access import failure_message, job_ai
from alloq_offer.workshop.jobs.registry import (
    JobContext,
    PermanentJobError,
    TransientJobError,
    register_handler,
)
from alloq_offer.workshop.repositories import workspace_repo
from alloq_offer.workshop.services.chapter_draft import DRAFT_CHAPTERS_JOB, DRAFTABLE
from alloq_offer.workshop.services.chapters import (
    ChapterError,
    ChapterService,
    add_proposal,
    find_chapter,
    live_chapters,
    revision_of,
    settings_of,
)
from alloq_offer.workshop.services.draft_pipeline import (
    finish_initial_draft,
    is_initial,
)
from alloq_offer.workshop.services.map_apply import snapshot_map
from appkit_commons.database.session import get_asyncdb_session
from appkit_commons.registry import service_registry

logger = logging.getLogger(__name__)

AI_FAILED = "Die KI konnte keinen Vorschlag liefern. Bitte prüfen Sie die Einrichtung."
AI_BUSY = "Die KI ist gerade nicht erreichbar. Der Auftrag wird erneut versucht."
NO_BASIS = {"status": "skipped", "reason": "no map and no briefing"}


@dataclass(frozen=True)
class _Target:
    key: str
    title: str
    settings: ChapterSettings
    base_revision: int
    current_lines: list[str]
    # The columns of a table chapter; empty for text.
    columns: list[str]


@dataclass(frozen=True)
class _Basis:
    map_revision: int
    outline: str
    statements: list[str]
    targets: list[_Target]


class DraftChapters:
    """Drafts the wanted chapters one after the other and stores each result."""

    def __init__(self, ai: ChapterAi, session_factory: SessionFactory) -> None:
        self._ai = ai
        self._session_factory = session_factory

    async def run(self, ctx: JobContext) -> dict:
        initial = is_initial(ctx.payload)
        if initial:
            # The chapters may not exist yet when nobody opened the chapter tab.
            await ChapterService(self._session_factory, ctx.offer_id, "").open()
        basis = await self._load(ctx)
        if basis is None:
            return NO_BASIS
        stored = skipped = 0
        instruction = str(ctx.payload.get("instruction") or "")
        for target in basis.targets:
            request = ChapterRequest(
                title=target.title,
                guiding_question=target.settings.guiding_question,
                rules=target.settings.content_rules,
                current_lines=target.current_lines,
                instruction=instruction,
                map_outline=basis.outline,
                statements=basis.statements,
                required_info=target.settings.required_info,
                prompt_text=target.settings.prompt_text,
                columns=target.columns,
            )
            try:
                content = await self._propose(request)
            except AiTransientError as exc:
                raise TransientJobError(AI_BUSY) from exc
            except AiUnavailableError as exc:
                raise PermanentJobError(failure_message(exc, AI_FAILED)) from exc
            proposal_id = await self._store(ctx, basis, target, content)
            if proposal_id is None:
                skipped += 1
                continue
            stored += 1
            if initial:
                await self._keep(ctx, proposal_id, target.base_revision)
        async with self._session_factory() as session:
            session.add(
                GenerationRunEntity(
                    offer_id=ctx.offer_id,
                    job_id=ctx.job_id,
                    kind=DRAFT_CHAPTERS_JOB,
                    model=self._ai.model_name,
                    prompt_version=self._ai.chapter_prompt_version,
                    input_revisions={"map": basis.map_revision},
                    status="ok",
                )
            )
        logger.info(
            "Chapter drafts of offer %s: %d stored, %d skipped",
            ctx.offer_id,
            stored,
            skipped,
        )
        if initial:
            await finish_initial_draft(
                self._session_factory,
                ctx.offer_id,
                now=datetime.now(UTC),
                max_attempts=ctx.max_attempts,
            )
        return {"status": "ok", "proposals": stored, "skipped": skipped}

    async def _propose(self, request: ChapterRequest) -> Content:
        if request.columns:
            table = await self._ai.propose_table(request)
            return table.to_content(request.columns)
        return (await self._ai.propose_chapter(request)).to_content()

    async def _keep(self, ctx: JobContext, proposal_id: int, base: int) -> None:
        """Take the first draft over as revision; on a conflict it stays a proposal."""
        try:
            await ChapterService(self._session_factory, ctx.offer_id, "").accept(
                proposal_id, base
            )
        except ChapterError:
            logger.info(
                "Draft %s of offer %s kept as proposal", proposal_id, ctx.offer_id
            )

    async def _store(
        self, ctx: JobContext, basis: _Basis, target: _Target, content: Content
    ) -> int | None:
        """Keep the proposal unless the chapter changed while the model worked."""
        key = target.key
        async with self._session_factory() as session:
            try:
                chapter = await find_chapter(session, ctx.offer_id, key)
            except ChapterError:
                return None
            if chapter.protected or chapter.revision != target.base_revision:
                return None
            proposal = await add_proposal(
                session,
                offer_id=ctx.offer_id,
                chapter_key=key,
                content=content,
                base_revision=target.base_revision,
                map_revision=basis.map_revision,
                instruction=str(ctx.payload.get("instruction") or ""),
                job_id=ctx.job_id,
            )
            await session.flush()
            return proposal.id

    async def _load(self, ctx: JobContext) -> _Basis | None:
        wanted = ctx.payload.get("keys")
        async with self._session_factory() as session:
            workspace = await workspace_repo.find_by_offer(session, ctx.offer_id)
            if workspace is None:
                return None
            statements = list(
                (
                    await session.scalars(
                        select(StatementEntity)
                        .where(StatementEntity.offer_id == ctx.offer_id)
                        .order_by(StatementEntity.id)
                    )
                ).all()
            )
            if workspace.map_revision == 0 and not statements:
                return None
            snapshot = await snapshot_map(session, workspace)
            done = set(
                (
                    await session.scalars(
                        select(ProposalEntity.chapter_key).where(
                            ProposalEntity.job_id == ctx.job_id,
                            ProposalEntity.status == ProposalStatus.OPEN,
                        )
                    )
                ).all()
            )
            targets: list[_Target] = []
            for chapter in await live_chapters(session, ctx.offer_id):
                key = chapter.chapter_key
                if key in done or chapter.protected:
                    continue
                if wanted is None:
                    # Without explicit keys only text nobody wrote is drafted.
                    if chapter.chapter_type != "prose" or chapter.revision > 1:
                        continue
                elif key not in wanted or chapter.chapter_type not in DRAFTABLE:
                    continue
                current = parse_content((await revision_of(session, chapter)).content)
                targets.append(
                    _Target(
                        key,
                        chapter.title,
                        settings_of(chapter),
                        chapter.revision,
                        content_lines(current),
                        current.columns if isinstance(current, TableContent) else [],
                    )
                )
        return _Basis(
            map_revision=workspace.map_revision,
            outline=map_outline(snapshot),
            statements=[
                statement_line(s.type, s.text, s.status == StatementStatus.CONFIRMED)
                for s in statements
            ],
            targets=targets,
        )


@register_handler(DRAFT_CHAPTERS_JOB)
async def draft_chapters(ctx: JobContext) -> dict:
    config = service_registry().get(WorkshopConfig)
    return await DraftChapters(job_ai(config), get_asyncdb_session).run(ctx)
