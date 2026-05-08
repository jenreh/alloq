"""Tests for dashboard aggregation services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.entities.risk import RiskMitigationStatus
from alloq_dashboard.services import aggregation


def test_project_to_row_counts_only_top_open_risks() -> None:
    entity = SimpleNamespace(
        id=1,
        code="P1",
        name_de="Projekt 1",
        state=ProjectStateEnum.ACTIVE.value,
        start_date=None,
        end_date=None,
        budget=0,
        color="#888",
        statuses=[],
        risks=[
            SimpleNamespace(
                probability=4,
                impact=4,
                mitigation_status=RiskMitigationStatus.OPEN.value,
            ),
            SimpleNamespace(
                probability=5,
                impact=3,
                mitigation_status=RiskMitigationStatus.OPEN.value,
            ),
            SimpleNamespace(
                probability=5,
                impact=5,
                mitigation_status=RiskMitigationStatus.MITIGATED.value,
            ),
        ],
    )

    row = aggregation._project_to_row(entity)

    assert row.open_risk_count == 1


@pytest.mark.asyncio
async def test_load_project_health_counts_only_top_open_risks() -> None:
    @asynccontextmanager
    async def fake_session():
        yield object()

    projects = [
        aggregation._ProjectRow(
            id=1,
            code="P1",
            name_de="Projekt 1",
            state=ProjectStateEnum.AT_RISK.value,
            start_date=None,
            end_date=None,
            budget=0,
            color="#888",
            progress=0,
            spent=0,
            open_risk_count=1,
        )
    ]
    risks = [
        aggregation._RiskRow(
            id=1,
            project_id=1,
            name="Top risk",
            severity="high",
            probability=4,
            impact=4,
            mitigation_status=RiskMitigationStatus.OPEN.value,
            owner=None,
            created_date=date(2026, 5, 5),
        ),
        aggregation._RiskRow(
            id=2,
            project_id=1,
            name="Below threshold",
            severity="high",
            probability=5,
            impact=3,
            mitigation_status=RiskMitigationStatus.OPEN.value,
            owner=None,
            created_date=date(2026, 5, 5),
        ),
        aggregation._RiskRow(
            id=3,
            project_id=1,
            name="Closed top risk",
            severity="high",
            probability=5,
            impact=5,
            mitigation_status=RiskMitigationStatus.MITIGATED.value,
            owner=None,
            created_date=date(2026, 5, 5),
        ),
    ]

    with (
        patch(
            "alloq_dashboard.services.aggregation.get_asyncdb_session",
            fake_session,
        ),
        patch(
            "alloq_dashboard.services.aggregation._load_project_rows",
            return_value=projects,
        ),
        patch(
            "alloq_dashboard.services.aggregation._load_risk_rows",
            return_value=risks,
        ),
        patch(
            "alloq_dashboard.services.aggregation._today",
            return_value=date(2026, 5, 8),
        ),
    ):
        payload = await aggregation.load_project_health()

    assert payload.at_risk_count == 1
    assert payload.total_risk_count == 1
    assert len(payload.rows) == 1
    assert payload.rows[0].risk_count == 1
    assert [point.value for point in payload.risk_trend] == [0.0, 0.0, 1.0]
