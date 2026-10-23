"""Sidebar data: project, employee and offer counters."""

import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.access import requires_editor
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.entities.project import ProjectEntity, ProjectStateEnum
from alloq_offer.entities import OfferEntity, OfferStateEnum
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.states import UserSession

logger = logging.getLogger(__name__)

REFRESH_SECONDS = 30.0
"""Data younger than this is kept on navigation; the sidebar reloads on mount."""


async def count_open_projects(session: AsyncSession) -> int:
    """Projects that are not completed (the "Projekte" badge)."""
    statement = (
        select(func.count())
        .select_from(ProjectEntity)
        .where(ProjectEntity.state != ProjectStateEnum.COMPLETED.value)
    )
    return int((await session.execute(statement)).scalar_one())


async def count_employees(session: AsyncSession) -> int:
    """All employees (the "Team" badge)."""
    statement = select(func.count()).select_from(EmployeeEntity)
    return int((await session.execute(statement)).scalar_one())


async def count_open_offers(session: AsyncSession) -> int:
    """Offers that are not sent yet (the "Angebote" badge)."""
    statement = (
        select(func.count())
        .select_from(OfferEntity)
        .where(OfferEntity.state != OfferStateEnum.SENT.value)
    )
    return int((await session.execute(statement)).scalar_one())


class SidebarState(UserSession):
    project_count: int = 0
    employee_count: int = 0
    offer_count: int = 0
    _loaded_at: float = 0.0

    @rx.event
    @requires_editor
    async def load(self) -> AsyncGenerator[Any]:
        if time.monotonic() - self._loaded_at < REFRESH_SECONDS:
            return
        async with get_asyncdb_session() as session:
            self.project_count = await count_open_projects(session)
            self.employee_count = await count_employees(session)
            self.offer_count = await count_open_offers(session)
        self._loaded_at = time.monotonic()
        logger.debug(
            "Sidebar loaded: %d projects, %d employees, %d offers",
            self.project_count,
            self.employee_count,
            self.offer_count,
        )
        yield

    @rx.event
    def invalidate(self) -> None:
        """Reload on the next mount, e.g. after a project was created."""
        self._loaded_at = 0.0
