import logging
from datetime import date

from sqlalchemy import Row, and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from alloq_commons.entities import CapacityAllocationEntity, RoleEntity
from appkit_commons.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)

_UPSERT_CHUNK = 1000  # rows per statement; 5 binds/row stays below asyncpg's cap
_CONFLICT_KEY = ("project_id", "employee_id", "role_id", "week_start")


class CapacityAllocationRepository(
    BaseRepository[CapacityAllocationEntity, AsyncSession]
):
    """Async repository for weekly per-employee project allocations."""

    @property
    def model_class(self) -> type[CapacityAllocationEntity]:
        return CapacityAllocationEntity

    async def find_by_project(
        self,
        session: AsyncSession,
        project_id: int,
    ) -> list[CapacityAllocationEntity]:
        """All weekly allocation rows for a project."""
        statement = (
            select(CapacityAllocationEntity)
            .where(CapacityAllocationEntity.project_id == project_id)
            .order_by(
                CapacityAllocationEntity.employee_id,
                CapacityAllocationEntity.week_start,
            )
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def find_by_project_in_range(
        self,
        session: AsyncSession,
        project_id: int,
        start: date,
        end: date,
    ) -> list[CapacityAllocationEntity]:
        """Weekly allocations for a project within an inclusive week_start range."""
        statement = (
            select(CapacityAllocationEntity)
            .where(
                CapacityAllocationEntity.project_id == project_id,
                CapacityAllocationEntity.week_start >= start,
                CapacityAllocationEntity.week_start <= end,
            )
            .order_by(
                CapacityAllocationEntity.employee_id,
                CapacityAllocationEntity.week_start,
            )
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def find_in_range(
        self,
        session: AsyncSession,
        start: date,
        end: date,
    ) -> list[CapacityAllocationEntity]:
        """All allocation rows whose week_start falls in [start, end]."""
        statement = (
            select(CapacityAllocationEntity)
            .where(
                CapacityAllocationEntity.week_start >= start,
                CapacityAllocationEntity.week_start <= end,
            )
            .order_by(
                CapacityAllocationEntity.employee_id,
                CapacityAllocationEntity.project_id,
                CapacityAllocationEntity.week_start,
            )
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def find_cells_in_range(
        self,
        session: AsyncSession,
        start: date,
        end: date,
    ) -> list[Row]:
        """Allocation columns plus role name for week_start in [start, end].

        Column-only query: no entities and no eager-loaded relationships, so
        the cost grows with the window, not with the whole history.
        """
        statement = (
            select(
                CapacityAllocationEntity.employee_id,
                CapacityAllocationEntity.project_id,
                CapacityAllocationEntity.role_id,
                CapacityAllocationEntity.week_start,
                CapacityAllocationEntity.person_days,
                RoleEntity.name.label("role_name"),
            )
            .outerjoin(RoleEntity, RoleEntity.id == CapacityAllocationEntity.role_id)
            .where(
                CapacityAllocationEntity.week_start >= start,
                CapacityAllocationEntity.week_start <= end,
            )
            .order_by(
                CapacityAllocationEntity.employee_id,
                CapacityAllocationEntity.project_id,
                CapacityAllocationEntity.week_start,
                CapacityAllocationEntity.id,
            )
        )
        result = await session.execute(statement)
        return list(result.all())

    async def find_by_employee_in_range(
        self,
        session: AsyncSession,
        employee_id: int,
        start: date,
        end: date,
    ) -> list[CapacityAllocationEntity]:
        statement = (
            select(CapacityAllocationEntity)
            .where(
                CapacityAllocationEntity.employee_id == employee_id,
                CapacityAllocationEntity.week_start >= start,
                CapacityAllocationEntity.week_start <= end,
            )
            .order_by(
                CapacityAllocationEntity.project_id,
                CapacityAllocationEntity.week_start,
            )
        )
        result = await session.execute(statement)
        return list(result.scalars().unique().all())

    async def replace_for_project_employee(
        self,
        session: AsyncSession,
        project_id: int,
        employee_id: int,
        rows: list[CapacityAllocationEntity],
    ) -> list[CapacityAllocationEntity]:
        """Replace all rows for one (project, employee) pair atomically.

        Deletes existing rows then inserts the supplied ones. Caller controls
        transaction boundaries.
        """
        await session.execute(
            delete(CapacityAllocationEntity).where(
                and_(
                    CapacityAllocationEntity.project_id == project_id,
                    CapacityAllocationEntity.employee_id == employee_id,
                )
            )
        )
        await session.flush()
        for row in rows:
            session.add(row)
        await session.flush()
        return rows

    async def delete_by_project_and_employee(
        self,
        session: AsyncSession,
        project_id: int,
        employee_id: int,
    ) -> bool:
        """Delete all allocation rows for a (project, employee) pair."""
        result = await session.execute(
            delete(CapacityAllocationEntity).where(
                and_(
                    CapacityAllocationEntity.project_id == project_id,
                    CapacityAllocationEntity.employee_id == employee_id,
                )
            )
        )
        await session.flush()
        return result.rowcount > 0

    async def delete_for_project_employee_in_range(
        self,
        session: AsyncSession,
        project_id: int,
        employee_id: int,
        start: date,
        end: date,
        *,
        role_id: int | None = None,
    ) -> int:
        """Delete a pair's rows with week_start in [start, end], optionally by role."""
        conditions = [
            CapacityAllocationEntity.project_id == project_id,
            CapacityAllocationEntity.employee_id == employee_id,
            CapacityAllocationEntity.week_start >= start,
            CapacityAllocationEntity.week_start <= end,
        ]
        if role_id is not None:
            conditions.append(CapacityAllocationEntity.role_id == role_id)
        result = await session.execute(
            delete(CapacityAllocationEntity).where(and_(*conditions))
        )
        await session.flush()
        return result.rowcount

    async def upsert_cell(
        self,
        session: AsyncSession,
        project_id: int,
        employee_id: int,
        role_id: int,
        *,
        week_start: date,
        person_days: float,
    ) -> CapacityAllocationEntity:
        """Insert or update a single weekly allocation cell."""
        statement = select(CapacityAllocationEntity).where(
            CapacityAllocationEntity.project_id == project_id,
            CapacityAllocationEntity.employee_id == employee_id,
            CapacityAllocationEntity.role_id == role_id,
            CapacityAllocationEntity.week_start == week_start,
        )
        result = await session.execute(statement)
        existing = result.scalars().first()
        if existing is not None:
            existing.person_days = person_days
            session.add(existing)
            await session.flush()
            await session.refresh(existing)
            return existing
        row = CapacityAllocationEntity(
            project_id=project_id,
            employee_id=employee_id,
            role_id=role_id,
            week_start=week_start,
            person_days=person_days,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def batch_upsert(
        self,
        session: AsyncSession,
        rows: list[dict],
    ) -> int:
        """Batch upsert allocation cells.

        Each dict must have keys: project_id, employee_id, role_id,
        week_start, person_days. Rows with the same conflict key are
        collapsed (last one wins) and written in chunks. Returns the number
        of rows upserted.
        """
        unique = list({tuple(r[k] for k in _CONFLICT_KEY): r for r in rows}.values())
        if not unique:
            return 0
        dialect_name = session.bind.dialect.name
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert  # noqa: PLC0415
        else:
            from sqlalchemy.dialects.sqlite import insert  # noqa: PLC0415
        for i in range(0, len(unique), _UPSERT_CHUNK):
            stmt = insert(CapacityAllocationEntity).values(
                unique[i : i + _UPSERT_CHUNK]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=list(_CONFLICT_KEY),
                set_={"person_days": stmt.excluded.person_days, "updated": func.now()},
            )
            await session.execute(stmt)
        return len(unique)


capacity_allocation_repo = CapacityAllocationRepository()
