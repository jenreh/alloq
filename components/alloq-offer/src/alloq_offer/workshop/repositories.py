"""Async repositories of the offer workshop."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_offer.entities import OfferEntity
from alloq_offer.workshop.entities import (
    JobEntity,
    SourceBlockEntity,
    SourceEntity,
    WorkspaceEntity,
)
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

    async def find_with_offer(
        self, session: AsyncSession, offer_id: int, *, lock: bool = False
    ) -> tuple[WorkspaceEntity, OfferEntity] | None:
        """Workspace and offer in one query; ``lock`` locks the workspace row."""
        query = (
            select(WorkspaceEntity, OfferEntity)
            .join(OfferEntity, OfferEntity.id == WorkspaceEntity.offer_id)
            .where(WorkspaceEntity.offer_id == offer_id)
        )
        if lock:
            query = query.with_for_update(of=WorkspaceEntity)
        row = (await session.execute(query)).one_or_none()
        return (row[0], row[1]) if row is not None else None


class JobRepository(BaseRepository[JobEntity, AsyncSession]):
    """Reads workshop jobs; writes go through ``workshop.jobs.queue``."""

    @property
    def model_class(self) -> type[JobEntity]:
        return JobEntity

    async def count_of_kind(
        self, session: AsyncSession, offer_id: int, kind: str
    ) -> int:
        return (
            await session.scalar(
                select(func.count())
                .select_from(JobEntity)
                .where(JobEntity.offer_id == offer_id, JobEntity.kind == kind)
            )
            or 0
        )

    async def find_latest(
        self, session: AsyncSession, offer_id: int, kind: str
    ) -> JobEntity | None:
        return await session.scalar(
            select(JobEntity)
            .where(JobEntity.offer_id == offer_id, JobEntity.kind == kind)
            .order_by(JobEntity.id.desc())
            .limit(1)
        )


class SourceRepository(BaseRepository[SourceEntity, AsyncSession]):
    """Reads the customer sources of an offer; revoked sources never show up."""

    @property
    def model_class(self) -> type[SourceEntity]:
        return SourceEntity

    async def find_in_offer(
        self, session: AsyncSession, offer_id: int, source_id: int
    ) -> SourceEntity | None:
        return await session.scalar(
            select(SourceEntity).where(
                SourceEntity.id == source_id, SourceEntity.offer_id == offer_id
            )
        )

    async def find_by_sha(
        self, session: AsyncSession, offer_id: int, sha256: str
    ) -> SourceEntity | None:
        return await session.scalar(
            select(SourceEntity)
            .where(
                SourceEntity.offer_id == offer_id,
                SourceEntity.sha256 == sha256,
                SourceEntity.revoked_at.is_(None),
            )
            .order_by(SourceEntity.id.desc())
            .limit(1)
        )

    async def find_latest_by_filename(
        self, session: AsyncSession, offer_id: int, filename: str
    ) -> SourceEntity | None:
        return await session.scalar(
            select(SourceEntity)
            .where(
                SourceEntity.offer_id == offer_id,
                SourceEntity.filename == filename,
                SourceEntity.revoked_at.is_(None),
            )
            .order_by(SourceEntity.version.desc())
            .limit(1)
        )

    async def list_current(
        self, session: AsyncSession, offer_id: int
    ) -> list[SourceEntity]:
        """Sources that are neither revoked nor replaced by a newer version."""
        rows = (
            await session.scalars(
                select(SourceEntity)
                .where(
                    SourceEntity.offer_id == offer_id,
                    SourceEntity.revoked_at.is_(None),
                )
                .order_by(SourceEntity.id)
            )
        ).all()
        replaced = {row.replaces_id for row in rows if row.replaces_id is not None}
        return [row for row in rows if row.id not in replaced]


class SourceBlockRepository(BaseRepository[SourceBlockEntity, AsyncSession]):
    """Reads and replaces the extracted blocks of a source."""

    @property
    def model_class(self) -> type[SourceBlockEntity]:
        return SourceBlockEntity

    async def list_for_source(
        self, session: AsyncSession, source_id: int
    ) -> list[SourceBlockEntity]:
        return list(
            (
                await session.scalars(
                    select(SourceBlockEntity)
                    .where(SourceBlockEntity.source_id == source_id)
                    .order_by(SourceBlockEntity.seq)
                )
            ).all()
        )

    async def replace(
        self,
        session: AsyncSession,
        source_id: int,
        blocks: list[SourceBlockEntity],
    ) -> None:
        await session.execute(
            delete(SourceBlockEntity).where(SourceBlockEntity.source_id == source_id)
        )
        session.add_all(blocks)


workspace_repo = WorkspaceRepository()
job_repo = JobRepository()
source_repo = SourceRepository()
source_block_repo = SourceBlockRepository()
