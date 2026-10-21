"""Tests for PortfolioState: load, scope switch and drawer."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.roles import EMPLOYEE_ROLE, PROJECT_MANAGER_ROLE
from alloq_dashboard.models import (
    PersonDetail,
    PortfolioKpi,
    PortfolioProject,
    RiskItem,
    RoleDetail,
)
from alloq_dashboard.states.portfolio_state import (
    DRAWER_PERSON,
    DRAWER_PROJECT,
    DRAWER_RISKS,
    DRAWER_ROLE,
    LOAD_ERROR_MESSAGE,
    PortfolioState,
)

from appkit_user.authentication.backend.models import User

# Allowed fakes hold the roles; the admin switch grants no planning access.
_PLANNER_ROLES = [PROJECT_MANAGER_ROLE.name, EMPLOYEE_ROLE.name]

LOADER = "alloq_dashboard.states.portfolio_state.portfolio.load_portfolio"
ADMIN = User(
    user_id=1,
    name="Katrin",
    email="katrin@example.com",
    is_admin=True,
    roles=_PLANNER_ROLES,
)
MEMBER = User(user_id=2, name="Ben", is_admin=False)


class _FakeLogin:
    def __init__(self, user: User | None) -> None:
        self._user = user

    @property
    def authenticated_user(self) -> Any:
        async def _get() -> User | None:
            return self._user

        return _get()

    async def redir(self) -> None:
        return None


def _login(user: User | None) -> Any:
    return patch.object(
        PortfolioState, "get_state", new=AsyncMock(return_value=_FakeLogin(user))
    )


@pytest.fixture
def as_admin() -> Iterator[None]:
    with _login(ADMIN):
        yield


async def _drain(handler: Any, state: PortfolioState, *args: Any) -> list[Any]:
    fn = handler.fn
    result = fn(state, *args)
    if hasattr(result, "__aiter__"):
        return [item async for item in result]
    return [await result]


@pytest.mark.usefixtures("as_admin")
async def test_load_stores_payload_for_scope_and_email() -> None:
    state = PortfolioState()
    state.scope = "team"
    loader = AsyncMock(return_value=PortfolioKpi(scope="team", gap_total=12.0))
    with patch(LOADER, new=loader):
        await _drain(PortfolioState.load, state)

    loader.assert_awaited_once_with("team", "katrin@example.com")
    assert state.data.gap_total == 12.0
    assert state.is_loading is False
    assert state.error_message == ""


@pytest.mark.usefixtures("as_admin")
async def test_load_failure_shows_message() -> None:
    state = PortfolioState()
    with patch(LOADER, new=AsyncMock(side_effect=RuntimeError("db down"))):
        await _drain(PortfolioState.load, state)

    assert state.is_loading is False
    assert state.error_message == LOAD_ERROR_MESSAGE


async def test_load_is_refused_for_non_admins() -> None:
    state = PortfolioState()
    loader = AsyncMock()
    with _login(MEMBER), patch(LOADER, new=loader):
        await _drain(PortfolioState.load, state)
    loader.assert_not_awaited()


@pytest.mark.usefixtures("as_admin")
async def test_set_scope_reloads_only_on_change() -> None:
    state = PortfolioState()
    state.drawer = DRAWER_PROJECT

    assert await _drain(PortfolioState.set_scope, state, "team") == [
        PortfolioState.load
    ]
    assert state.scope == "team"
    assert state.drawer == ""
    assert await _drain(PortfolioState.set_scope, state, "team") == [None]
    assert await _drain(PortfolioState.set_scope, state, "everyone") == [None]
    assert state.scope == "team"


@pytest.mark.usefixtures("as_admin")
async def test_drawer_selection_and_computed_vars() -> None:
    state = PortfolioState()
    state.data = PortfolioKpi(
        projects=[PortfolioProject(id=4, code="AQ-104")],
        risks=[
            RiskItem(id=1, name="A", probability=4, impact=5),
            RiskItem(id=2, name="B", probability=3, impact=3),
        ],
    )
    assert state.cell_title == ""

    await _drain(PortfolioState.open_project, state, 4)
    assert state.drawer == DRAWER_PROJECT
    assert state.selected_project.code == "AQ-104"

    await _drain(PortfolioState.open_risk_cell, state, "4-5")
    assert state.drawer == DRAWER_RISKS
    assert [r.id for r in state.cell_risks] == [1]
    assert state.cell_title == "Wahrscheinlichkeit 4, Auswirkung 5"

    await _drain(PortfolioState.close_drawer, state)
    assert state.drawer == ""
    state.selected_project_id = 99
    assert state.selected_project.code == ""


@pytest.mark.usefixtures("as_admin")
async def test_role_and_person_drawers() -> None:
    state = PortfolioState()
    state.data = PortfolioKpi(
        role_details=[RoleDetail(role_id=3, role_name="QA")],
        person_details=[PersonDetail(employee_id=7, name="Mira")],
    )

    await _drain(PortfolioState.open_role, state, 3)
    assert state.drawer == DRAWER_ROLE
    assert state.selected_role.role_name == "QA"

    await _drain(PortfolioState.open_person, state, 7)
    assert state.drawer == DRAWER_PERSON
    assert state.selected_person.name == "Mira"

    state.selected_role_id = 99
    state.selected_person_id = 99
    assert state.selected_role.role_name == ""
    assert state.selected_person.name == ""


async def test_role_and_person_drawers_are_refused_for_non_admins() -> None:
    state = PortfolioState()
    with _login(MEMBER):
        await _drain(PortfolioState.open_role, state, 3)
        await _drain(PortfolioState.open_person, state, 7)
    assert state.drawer == ""
