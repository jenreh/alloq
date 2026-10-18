"""Tests for loading and mapping portfolio inputs."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from alloq_commons.entities.employee import EmployeeEntity
from alloq_commons.entities.project import ProjectEntity
from alloq_commons.entities.risk import RiskEntity
from alloq_dashboard.services import portfolio, portfolio_inputs

MODULE = "alloq_dashboard.services.portfolio_inputs"


def _status(**kwargs: Any) -> SimpleNamespace:
    values = {
        "progress": 40,
        "budget_spent": 50,
        "actual_cost": None,
        "eac_linear": None,
        "eac_additive": None,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def _project(**kwargs: Any) -> SimpleNamespace:
    values = {
        "id": 1,
        "code": "AQ-1",
        "name_de": "Portal",
        "state": "Aktiv",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "budget": 1000,
        "ev_eac_additive": None,
        "statuses": [_status()],
        "required_capacities": [
            SimpleNamespace(role_id=2, person_days=5),
            SimpleNamespace(role_id=2, person_days=3),
            SimpleNamespace(role_id=1, person_days=4),
        ],
        "owners": [SimpleNamespace(id=7)],
        "capacity_allocations": [
            SimpleNamespace(
                employee_id=3, role_id=1, week_start=date(2026, 10, 12), person_days=2
            )
        ],
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_project_to_input_merges_required_capacity() -> None:
    row = portfolio_inputs.project_to_input(cast("ProjectEntity", _project()))

    assert row.required == ((1, 4.0), (2, 8.0))
    assert row.owner_ids == (7,)
    assert row.progress == 40
    assert row.allocations[0].person_days == 2.0
    # 50 % of 1000 spent at 40 % progress.
    assert row.eac == pytest.approx(1250.0)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"ev_eac_additive": 900.0}, 900.0),
        ({"statuses": [_status(eac_additive=800.0)]}, 800.0),
        ({"statuses": [_status(eac_linear=700.0)]}, 700.0),
        ({"statuses": [_status(actual_cost=300.0, progress=50)]}, 600.0),
        ({"statuses": [_status(progress=0)]}, 0.0),
        ({"statuses": []}, 0.0),
    ],
)
def test_project_eac_fallbacks(kwargs: dict[str, Any], expected: float) -> None:
    row = portfolio_inputs.project_to_input(cast("ProjectEntity", _project(**kwargs)))
    assert row.eac == pytest.approx(expected)


def test_employee_and_risk_mapping() -> None:
    employee = SimpleNamespace(
        id=3,
        first_name="Mira",
        last_name="Schuster",
        roles=[SimpleNamespace(id=1)],
        manager_id=7,
        internal_hours=4,
        hours_per_week=20.0,
        absences=[
            SimpleNamespace(start_date=date(2026, 10, 26), end_date=date(2026, 11, 6)),
            SimpleNamespace(start_date=None, end_date=None),
        ],
    )
    row = portfolio_inputs.employee_to_input(cast("EmployeeEntity", employee))
    assert row.name == "Mira Schuster"
    assert row.workload_percent == 50
    assert row.absences == ((date(2026, 10, 26), date(2026, 11, 6)),)

    risk = SimpleNamespace(
        id=1, project_id=1, name="R", probability=7, impact=0, mitigation_status="open"
    )
    risk_row = portfolio_inputs.risk_to_input(cast("RiskEntity", risk))
    assert (risk_row.probability, risk_row.impact) == (5, 1)


def _session_with_roles() -> Any:
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalars=lambda: [SimpleNamespace(id=1, name="Backend")]
            )
        )
    )

    @asynccontextmanager
    async def _ctx() -> Any:
        yield session

    return _ctx


async def test_load_inputs_reads_everything_in_one_session() -> None:
    project = _project()
    employee = SimpleNamespace(
        id=7,
        first_name="Katrin",
        last_name="Albers",
        roles=[],
        manager_id=None,
        internal_hours=0,
        hours_per_week=40.0,
        absences=[],
    )
    with (
        patch(f"{MODULE}.get_asyncdb_session", _session_with_roles()),
        patch(
            f"{MODULE}.project_repo.find_all_paginated",
            AsyncMock(return_value=[project]),
        ),
        patch(
            f"{MODULE}.employee_repo.find_all_paginated",
            AsyncMock(return_value=[employee]),
        ),
        patch(
            f"{MODULE}.employee_repo.find_by_email", AsyncMock(return_value=employee)
        ),
        patch(f"{MODULE}.risk_repo.find_open_by_min_score", AsyncMock(return_value=[])),
        patch(
            f"{MODULE}.public_holiday_repo.find_by_date_range",
            AsyncMock(return_value=[SimpleNamespace(date=date(2026, 12, 25))]),
        ),
    ):
        data = await portfolio_inputs.load_inputs(date(2026, 10, 18), "k@a.de")

    assert data.current_employee_id == 7
    assert data.projects == data.all_projects
    assert data.roles[0].name == "Backend"
    assert data.holidays == frozenset({date(2026, 12, 25)})


async def test_load_inputs_without_email_skips_profile_lookup() -> None:
    lookup = AsyncMock()
    with (
        patch(f"{MODULE}.get_asyncdb_session", _session_with_roles()),
        patch(f"{MODULE}.project_repo.find_all_paginated", AsyncMock(return_value=[])),
        patch(f"{MODULE}.employee_repo.find_all_paginated", AsyncMock(return_value=[])),
        patch(f"{MODULE}.employee_repo.find_by_email", lookup),
        patch(f"{MODULE}.risk_repo.find_open_by_min_score", AsyncMock(return_value=[])),
        patch(
            f"{MODULE}.public_holiday_repo.find_by_date_range",
            AsyncMock(return_value=[]),
        ),
    ):
        data = await portfolio_inputs.load_inputs(date(2026, 10, 18), None)

    assert data.current_employee_id is None
    lookup.assert_not_awaited()


async def test_load_portfolio_builds_from_loaded_inputs() -> None:
    empty = portfolio_inputs.PortfolioInputs()
    with patch(
        "alloq_dashboard.services.portfolio.load_inputs",
        AsyncMock(return_value=empty),
    ) as loader:
        kpi = await portfolio.load_portfolio("team", "k@a.de")

    assert kpi.scope == "team"
    assert kpi.notice == portfolio.NO_PROFILE_NOTICE
    loader.assert_awaited_once()
    assert loader.await_args is not None
    assert loader.await_args.args[1] == "k@a.de"
