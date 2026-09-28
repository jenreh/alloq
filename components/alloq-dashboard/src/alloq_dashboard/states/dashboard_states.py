"""Reflex state classes powering the team-manager dashboard.

Each KPI card has its own substate of UserSession with a `data` payload, an
`is_loading` flag, and a `last_loaded` ISO timestamp used for TTL caching.
The `load` event handler is decorated `@rx.event(background=True)` so cards
fetch in parallel and never block one another.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import reflex as rx
from alloq_project.states.project_state import ProjectState

from alloq_dashboard.models import (
    BudgetBurnKpi,
    FreeCapacityKpi,
    ProjectHealthKpi,
    ProjectsOverviewKpi,
    RiskKpi,
    UnderUtilizationKpi,
    UtilizationKpi,
)
from alloq_dashboard.services import aggregation
from appkit_user.authentication.decorators import requires_admin
from appkit_user.authentication.states import LoginState, UserSession

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30  # 30 seconds
LOAD_ERROR_MESSAGE = "Daten konnten nicht geladen werden."


def _ts_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _is_fresh(last_loaded: str) -> bool:
    if not last_loaded:
        return False
    try:
        ts = datetime.fromisoformat(last_loaded)
    except ValueError:
        return False
    return datetime.now(tz=UTC) - ts < timedelta(seconds=CACHE_TTL_SECONDS)


async def _is_admin(state: Any, action: str) -> bool:
    """Server-side admin check for background handlers.

    Must be called inside ``async with state`` — a background StateProxy only
    allows ``get_state`` while it holds the lock.
    """
    login_state = await state.get_state(LoginState)
    user = await login_state.authenticated_user
    if user is not None and user.is_admin:
        return True
    logger.warning(
        "Denied dashboard load '%s' for user_id=%s",
        action,
        user.user_id if user else None,
    )
    return False


class _CardLoadMixin:
    """Shared TTL-cached, admin-guarded load lifecycle for card substates.

    Plain Python mixin (not a Reflex state), so it adds no substate; each card
    declares its own ``data``/``is_loading``/``last_loaded``/``error_message``
    vars and the ``_load_seq`` backend var.
    """

    async def _run_card_load(
        self,
        loader: Callable[[], Awaitable[Any]],
        action: str,
        *,
        force: bool,
    ) -> None:
        """Run ``loader``; a sequence number discards superseded results."""
        async with self:
            if not await _is_admin(self, action):
                return
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
            self._load_seq += 1
            seq = self._load_seq
        try:
            payload = await loader()
        except Exception:
            logger.exception("%s load failed", action)
            async with self:
                if seq == self._load_seq:
                    self.is_loading = False
                    self.error_message = LOAD_ERROR_MESSAGE
            return
        async with self:
            if seq != self._load_seq:
                logger.debug("Discarding superseded %s load", action)
                return
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


# --------------------------------------------------------------------------
# Parent state — drill-down drawer + parallel-load orchestration
# --------------------------------------------------------------------------


class DashboardState(UserSession):
    """Parent state owning the drill-down drawer."""

    drill_down: str = ""
    error_message: str = ""

    @rx.event
    def open_drill_down(self, key: str) -> None:
        self.drill_down = key

    @rx.event
    def close_drill_down(self) -> None:
        self.drill_down = ""

    @rx.event
    @requires_admin
    async def load_all(self) -> list[Any]:
        """Trigger parallel background loads on every card substate."""
        return [
            ProjectState.load_projects,
            ProjectsOverviewState.load,
            ProjectHealthState.load,
            BudgetBurnState.load,
            UtilizationState.load,
            UnderUtilizationState.load,
            RoleCapacityState.load,
            RiskState.load,
        ]


# --------------------------------------------------------------------------
# Card substates
# --------------------------------------------------------------------------


class ProjectsOverviewState(_CardLoadMixin, UserSession):
    """Card 1 — active projects overview."""

    data: ProjectsOverviewKpi = ProjectsOverviewKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(
            aggregation.load_projects_overview, "projects overview", force=force
        )


class ProjectHealthState(_CardLoadMixin, UserSession):
    """Card 2 — project health (at-risk projects)."""

    data: ProjectHealthKpi = ProjectHealthKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(
            aggregation.load_project_health, "project health", force=force
        )


class BudgetBurnState(_CardLoadMixin, UserSession):
    """Card 4 — budget burn."""

    data: BudgetBurnKpi = BudgetBurnKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(
            aggregation.load_budget_burn, "budget burn", force=force
        )


class UtilizationState(_CardLoadMixin, UserSession):
    """Card 5 — team utilization."""

    data: UtilizationKpi = UtilizationKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(
            aggregation.load_utilization, "utilization", force=force
        )


class UnderUtilizationState(_CardLoadMixin, UserSession):
    """Card 6 — under-utilization (free hours next 4 weeks)."""

    data: UnderUtilizationKpi = UnderUtilizationKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(
            aggregation.load_under_utilization, "under-utilization", force=force
        )


class RoleCapacityState(_CardLoadMixin, UserSession):
    """Card 7 — free capacity per role over 13 weeks."""

    data: FreeCapacityKpi = FreeCapacityKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(
            aggregation.load_free_capacity, "free-capacity", force=force
        )


class RiskState(_CardLoadMixin, UserSession):
    """Card 8 — risk surface."""

    data: RiskKpi = RiskKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""
    _load_seq: int = 0

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        await self._run_card_load(aggregation.load_risks, "risks", force=force)
