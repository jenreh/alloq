"""State of the portfolio overview (dashboard variant C)."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.access import requires_editor

from alloq_dashboard.models import (
    PersonDetail,
    PortfolioKpi,
    PortfolioProject,
    RiskItem,
    RoleDetail,
)
from alloq_dashboard.services import portfolio
from alloq_dashboard.services.portfolio_inputs import SCOPE_DEPARTMENT, SCOPES
from appkit_user.authentication.states import LoginState, UserSession

logger = logging.getLogger(__name__)

LOAD_ERROR_MESSAGE = "Daten konnten nicht geladen werden."
DRAWER_PROJECT = "project"
DRAWER_RISKS = "risks"
DRAWER_ROLE = "role"
DRAWER_PERSON = "person"


class PortfolioState(UserSession):
    """Portfolio payload, the chosen scope and the open drawer."""

    data: rx.Field[PortfolioKpi] = rx.field(default_factory=PortfolioKpi)
    is_loading: rx.Field[bool] = rx.field(False)
    error_message: rx.Field[str] = rx.field("")
    scope: rx.Field[str] = rx.field(SCOPE_DEPARTMENT)
    drawer: rx.Field[str] = rx.field("")
    selected_project_id: rx.Field[int] = rx.field(0)
    selected_cell: rx.Field[str] = rx.field("")
    selected_role_id: rx.Field[int] = rx.field(0)
    selected_person_id: rx.Field[int] = rx.field(0)

    @rx.var
    def selected_project(self) -> PortfolioProject:
        return next(
            (p for p in self.data.projects if p.id == self.selected_project_id),
            PortfolioProject(),
        )

    @rx.var
    def selected_role(self) -> RoleDetail:
        return next(
            (r for r in self.data.role_details if r.role_id == self.selected_role_id),
            RoleDetail(),
        )

    @rx.var
    def selected_person(self) -> PersonDetail:
        return next(
            (
                p
                for p in self.data.person_details
                if p.employee_id == self.selected_person_id
            ),
            PersonDetail(),
        )

    @rx.var
    def cell_risks(self) -> list[RiskItem]:
        return [
            r
            for r in self.data.risks
            if f"{r.probability}-{r.impact}" == self.selected_cell
        ]

    @rx.var
    def cell_title(self) -> str:
        if not self.selected_cell:
            return ""
        probability, impact = self.selected_cell.split("-")
        return f"Wahrscheinlichkeit {probability}, Auswirkung {impact}"

    async def _user_email(self) -> str | None:
        login_state = await self.get_state(LoginState)
        user = await login_state.authenticated_user
        return getattr(user, "email", None) if user else None

    @rx.event
    @requires_editor
    async def load(self) -> AsyncGenerator[Any]:
        """Load the portfolio for the current scope."""
        self.is_loading = True
        self.error_message = ""
        yield
        try:
            email = await self._user_email()
            self.data = await portfolio.load_portfolio(self.scope, email)
        except Exception:
            logger.exception("Portfolio load failed")
            self.error_message = LOAD_ERROR_MESSAGE
        finally:
            self.is_loading = False

    @rx.event
    @requires_editor
    async def set_scope(self, scope: str) -> Any:
        """Switch between the whole department and direct reports."""
        if scope not in SCOPES or scope == self.scope:
            return None
        self.scope = scope
        self.drawer = ""
        return PortfolioState.load

    @rx.event
    @requires_editor
    async def open_project(self, project_id: int) -> None:
        self.selected_project_id = project_id
        self.drawer = DRAWER_PROJECT

    @rx.event
    @requires_editor
    async def open_risk_cell(self, key: str) -> None:
        self.selected_cell = key
        self.drawer = DRAWER_RISKS

    @rx.event
    @requires_editor
    async def open_role(self, role_id: int) -> None:
        self.selected_role_id = role_id
        self.drawer = DRAWER_ROLE

    @rx.event
    @requires_editor
    async def open_person(self, employee_id: int) -> None:
        self.selected_person_id = employee_id
        self.drawer = DRAWER_PERSON

    @rx.event
    @requires_editor
    async def close_drawer(self) -> None:
        self.drawer = ""
