"""Reflex state classes powering the team-manager dashboard.

Each KPI card has its own substate of UserSession with a `data` payload, an
`is_loading` flag, and a `last_loaded` ISO timestamp used for TTL caching.
The `load` event handler is decorated `@rx.event(background=True)` so cards
fetch in parallel and never block one another.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import reflex as rx
from alloq_project.states.project_state import ProjectState

from alloq_dashboard.models import (
    BudgetBurnKpi,
    DeadlineKpi,
    FreeCapacityKpi,
    ProjectHealthKpi,
    ProjectsOverviewKpi,
    RiskKpi,
    UnderUtilizationKpi,
    UtilizationKpi,
)
from alloq_dashboard.services import aggregation
from appkit_user.authentication.states import UserSession

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 1800  # 30 minutes


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
    def load_all(self) -> list[Any]:
        """Trigger parallel background loads on every card substate."""
        return [
            ProjectState.load_projects,
            ProjectsOverviewState.load,
            ProjectHealthState.load,
            DeadlineState.load,
            BudgetBurnState.load,
            UtilizationState.load,
            UnderUtilizationState.load,
            FreeCapacityState.load,
            RiskState.load,
        ]


# --------------------------------------------------------------------------
# Card substates
# --------------------------------------------------------------------------


class ProjectsOverviewState(UserSession):
    """Card 1 — active projects overview."""

    data: ProjectsOverviewKpi = ProjectsOverviewKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_projects_overview()
        except Exception as exc:  # noqa: BLE001
            logger.exception("projects overview load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class ProjectHealthState(UserSession):
    """Card 2 — project health (at-risk projects)."""

    data: ProjectHealthKpi = ProjectHealthKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_project_health()
        except Exception as exc:  # noqa: BLE001
            logger.exception("project health load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class DeadlineState(UserSession):
    """Card 3 — deadline watch."""

    data: DeadlineKpi = DeadlineKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_deadlines()
        except Exception as exc:  # noqa: BLE001
            logger.exception("deadlines load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class BudgetBurnState(UserSession):
    """Card 4 — budget burn."""

    data: BudgetBurnKpi = BudgetBurnKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_budget_burn()
        except Exception as exc:  # noqa: BLE001
            logger.exception("budget burn load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class UtilizationState(UserSession):
    """Card 5 — team utilization."""

    data: UtilizationKpi = UtilizationKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_utilization()
        except Exception as exc:  # noqa: BLE001
            logger.exception("utilization load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class UnderUtilizationState(UserSession):
    """Card 6 — under-utilization (free hours next 4 weeks)."""

    data: UnderUtilizationKpi = UnderUtilizationKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_under_utilization()
        except Exception as exc:  # noqa: BLE001
            logger.exception("under-utilization load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class FreeCapacityState(UserSession):
    """Card 7 — free capacity per role over 13 weeks."""

    data: FreeCapacityKpi = FreeCapacityKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_free_capacity()
        except Exception as exc:  # noqa: BLE001
            logger.exception("free-capacity load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()


class RiskState(UserSession):
    """Card 8 — risk surface."""

    data: RiskKpi = RiskKpi()
    is_loading: bool = False
    last_loaded: str = ""
    error_message: str = ""

    @rx.event(background=True)
    async def load(self, *, force: bool = False) -> None:
        async with self:
            if not force and _is_fresh(self.last_loaded):
                return
            self.is_loading = True
            self.error_message = ""
        try:
            payload = await aggregation.load_risks()
        except Exception as exc:  # noqa: BLE001
            logger.exception("risks load failed")
            async with self:
                self.is_loading = False
                self.error_message = str(exc)
            return
        async with self:
            self.data = payload
            self.is_loading = False
            self.last_loaded = _ts_now()
