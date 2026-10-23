"""Async repositories of the offer workshop."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.workshop.entities import JobEntity, WorkspaceEntity
from appkit_commons.database.base_repository import BaseRepository


class WorkspaceRepository(BaseRepository[WorkspaceEntity, AsyncSession]):
    """Reads and writes the workshop workspace of an offer."""

    @property
    def model_class(self) -> type[WorkspaceEntity]:
        return WorkspaceEntity

    async def find_by_offer(
        self, session: AsyncSession, offer_id: int
    ) -> WorkspaceEntity | None:
        return await session.scalar(
            select(WorkspaceEntity).where(WorkspaceEntity.offer_id == offer_id)
        )


class JobRepository(BaseRepository[JobEntity, AsyncSession]):
    """Reads workshop jobs; writes go through ``workshop.jobs.queue``."""

    @property
    def model_class(self) -> type[JobEntity]:
        return JobEntity

    async def find_latest(
        self, session: AsyncSession, offer_id: int, kind: str
    ) -> JobEntity | None:
        return await session.scalar(
            select(JobEntity)
            .where(JobEntity.offer_id == offer_id, JobEntity.kind == kind)
            .order_by(JobEntity.id.desc())
            .limit(1)
        )


workspace_repo = WorkspaceRepository()
job_repo = JobRepository()
