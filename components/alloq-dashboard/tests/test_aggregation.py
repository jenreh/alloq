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
        created=None,
        ev_earned_value=0.0,
        ev_actual_cost=0.0,
        ev_eac_linear=0.0,
        ev_eac_additive=0.0,
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
            updated_date=date(2026, 5, 5),
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
            updated_date=date(2026, 5, 5),
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
            updated_date=date(2026, 5, 5),
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


# ---------------------------------------------------------------------------
# Weekly portfolio budget forecast
# ---------------------------------------------------------------------------


def _project(
    pid: int,
    *,
    created: date,
    budget: int = 100_000,
    name: str = "P",
    state: str = ProjectStateEnum.ACTIVE.value,
) -> aggregation._ProjectRow:
    return aggregation._ProjectRow(
        id=pid,
        code=f"P{pid}",
        name_de=name,
        state=state,
        start_date=None,
        end_date=None,
        budget=budget,
        color="#888",
        progress=0,
        spent=0,
        open_risk_count=0,
        created_date=created,
    )


def _status(
    pid: int,
    status_date: date,
    *,
    progress: int = 0,
    budget_spent: int = 0,
    budget: float | None = None,
    earned_value: float | None = None,
    actual_cost: float | None = None,
    eac_linear: float | None = None,
    eac_additive: float | None = None,
) -> aggregation._StatusRow:
    return aggregation._StatusRow(
        project_id=pid,
        status_date=status_date,
        progress=progress,
        budget_spent=budget_spent,
        budget=budget,
        earned_value=earned_value,
        actual_cost=actual_cost,
        eac_linear=eac_linear,
        eac_additive=eac_additive,
    )


def test_iso_week_key_format() -> None:
    assert aggregation._iso_week_key(date(2026, 5, 11)) == "2026-W20"
    assert aggregation._iso_week_key(date(2026, 1, 5)) == "2026-W02"


def test_weekly_forecast_single_project_carry_forward() -> None:
    p = _project(1, created=date(2026, 4, 27))
    statuses = {
        1: [
            _status(
                1,
                date(2026, 5, 4),
                actual_cost=40_000,
                eac_linear=80_000,
                eac_additive=90_000,
            )
        ]
    }
    weeks = [date(2026, 4, 27), date(2026, 5, 4), date(2026, 5, 11)]
    out = aggregation._build_weekly_forecast_series([p], statuses, weeks)
    assert [pt.active_count for pt in out] == [0, 1, 1]
    assert out[1].actual_cost == 40_000
    assert out[2].actual_cost == 40_000  # carried forward
    assert out[2].forecast_min == 80_000
    assert out[2].forecast_max == 90_000


def test_weekly_forecast_skips_before_created_week() -> None:
    p = _project(1, created=date(2026, 5, 6))  # Wed, ISO week starting Mon 2026-05-04
    statuses = {
        1: [
            _status(
                1,
                date(2026, 5, 8),
                actual_cost=10_000,
                eac_linear=20_000,
                eac_additive=25_000,
            )
        ]
    }
    weeks = [date(2026, 4, 27), date(2026, 5, 4), date(2026, 5, 11)]
    out = aggregation._build_weekly_forecast_series([p], statuses, weeks)
    assert out[0].active_count == 0  # before created week
    assert out[1].active_count == 1  # created week included
    assert out[2].active_count == 1


def test_weekly_forecast_aggregates_multiple_projects() -> None:
    p1 = _project(1, created=date(2026, 1, 1), budget=100_000, name="A")
    p2 = _project(2, created=date(2026, 1, 1), budget=50_000, name="B")
    statuses = {
        1: [
            _status(
                1,
                date(2026, 5, 4),
                actual_cost=40_000,
                eac_linear=80_000,
                eac_additive=120_000,
            )
        ],
        2: [
            _status(
                2,
                date(2026, 5, 4),
                actual_cost=10_000,
                eac_linear=40_000,
                eac_additive=55_000,
            )
        ],
    }
    weeks = [date(2026, 5, 4)]
    out = aggregation._build_weekly_forecast_series([p1, p2], statuses, weeks)
    pt = out[0]
    assert pt.active_count == 2
    assert pt.total_budget == 150_000
    assert pt.actual_cost == 50_000
    assert pt.eac_linear == 120_000
    assert pt.eac_additive == 175_000
    assert pt.overrun_abs == 175_000 - 150_000


def test_weekly_forecast_excludes_project_without_status() -> None:
    p = _project(1, created=date(2026, 1, 1))
    weeks = [date(2026, 5, 4)]
    out = aggregation._build_weekly_forecast_series([p], {1: []}, weeks)
    assert out[0].active_count == 0
    assert out[0].total_budget == 0


def test_weekly_forecast_fallback_actual_cost_from_pct() -> None:
    p = _project(1, created=date(2026, 1, 1), budget=200_000)
    statuses = {1: [_status(1, date(2026, 5, 4), budget_spent=30)]}
    out = aggregation._build_weekly_forecast_series([p], statuses, [date(2026, 5, 4)])
    assert out[0].actual_cost == 60_000  # 30% of 200k


def test_weekly_forecast_fallback_eac_linear_from_progress() -> None:
    p = _project(1, created=date(2026, 1, 1), budget=100_000)
    statuses = {1: [_status(1, date(2026, 5, 4), progress=50, actual_cost=40_000)]}
    out = aggregation._build_weekly_forecast_series([p], statuses, [date(2026, 5, 4)])
    assert out[0].eac_linear == 80_000  # 40k / 0.5
    assert out[0].eac_additive == 80_000  # falls back to eac_linear


def test_weekly_forecast_classifies_overrun_bands() -> None:
    p_green = _project(1, created=date(2026, 1, 1), budget=100_000, name="G")
    p_yellow = _project(2, created=date(2026, 1, 1), budget=100_000, name="Y")
    p_red = _project(3, created=date(2026, 1, 1), budget=100_000, name="R")
    statuses = {
        1: [_status(1, date(2026, 5, 4), eac_additive=90_000, eac_linear=85_000)],
        2: [_status(2, date(2026, 5, 4), eac_additive=105_000, eac_linear=100_000)],
        3: [_status(3, date(2026, 5, 4), eac_additive=130_000, eac_linear=120_000)],
    }
    out = aggregation._build_weekly_forecast_series(
        [p_green, p_yellow, p_red], statuses, [date(2026, 5, 4)]
    )
    pt = out[0]
    assert pt.green_count == 1
    assert pt.yellow_count == 1
    assert pt.red_count == 1


def test_weekly_forecast_skips_classification_for_zero_budget() -> None:
    p = _project(1, created=date(2026, 1, 1), budget=0)
    statuses = {1: [_status(1, date(2026, 5, 4), eac_additive=10_000)]}
    out = aggregation._build_weekly_forecast_series([p], statuses, [date(2026, 5, 4)])
    pt = out[0]
    assert pt.green_count == 0
    assert pt.yellow_count == 0
    assert pt.red_count == 0


def test_weekly_forecast_top_risks_sorted_and_capped() -> None:
    projects = [
        _project(i, created=date(2026, 1, 1), budget=100_000, name=f"P{i}")
        for i in range(1, 6)
    ]
    statuses = {
        1: [_status(1, date(2026, 5, 4), eac_additive=110_000)],  # +10k
        2: [_status(2, date(2026, 5, 4), eac_additive=200_000)],  # +100k
        3: [_status(3, date(2026, 5, 4), eac_additive=150_000)],  # +50k
        4: [_status(4, date(2026, 5, 4), eac_additive=180_000)],  # +80k
        5: [_status(5, date(2026, 5, 4), eac_additive=90_000)],  # under
    }
    out = aggregation._build_weekly_forecast_series(
        projects, statuses, [date(2026, 5, 4)]
    )
    top = out[0].top_risks
    assert len(top) == 3
    assert [r.project_name for r in top] == ["P2", "P4", "P3"]
    assert top[0].abs_delta == 100_000


def test_weekly_forecast_handles_irregular_snapshots() -> None:
    p = _project(1, created=date(2026, 1, 1))
    statuses = {
        1: [
            _status(1, date(2026, 4, 20), actual_cost=10_000, eac_additive=50_000),
            _status(1, date(2026, 5, 5), actual_cost=30_000, eac_additive=70_000),
        ]
    }
    weeks = [date(2026, 4, 20), date(2026, 4, 27), date(2026, 5, 4), date(2026, 5, 11)]
    out = aggregation._build_weekly_forecast_series([p], statuses, weeks)
    assert out[0].actual_cost == 10_000
    assert out[1].actual_cost == 10_000  # carry-forward from 04-20
    assert out[2].actual_cost == 30_000  # newer snapshot picked up
    assert out[3].actual_cost == 30_000


def test_weekly_forecast_single_week_point() -> None:
    p = _project(1, created=date(2026, 5, 4))
    statuses = {
        1: [_status(1, date(2026, 5, 5), actual_cost=10_000, eac_additive=15_000)]
    }
    out = aggregation._build_weekly_forecast_series([p], statuses, [date(2026, 5, 4)])
    assert len(out) == 1
    assert out[0].active_count == 1
    assert out[0].actual_cost == 10_000


def test_weekly_forecast_empty_inputs() -> None:
    out = aggregation._build_weekly_forecast_series([], {}, [date(2026, 5, 4)])
    assert len(out) == 1
    assert out[0].active_count == 0
    assert out[0].total_budget == 0
    assert out[0].forecast_min == 0
    assert out[0].forecast_max == 0
    assert out[0].overrun_pct == 0


def test_classify_overrun_thresholds() -> None:
    assert aggregation._classify_overrun(100.0, 100.0) == "green"
    assert aggregation._classify_overrun(105.0, 100.0) == "yellow"
    assert aggregation._classify_overrun(110.0, 100.0) == "yellow"
    assert aggregation._classify_overrun(110.01, 100.0) == "red"
    assert aggregation._classify_overrun(50.0, 0) is None
