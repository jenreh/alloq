"""Tests for EVForecastService and capacity-weighted PV calculation."""

from datetime import date, timedelta

import pytest
from alloq_commons.models.project import CapacityAllocation, Project, ProjectStatus
from alloq_project.services.forecast import (
    EVForecastService,
    _cumulative_pv,
)

_WEEK = timedelta(days=7)


def _alloc(week_start: date, person_days: float) -> CapacityAllocation:
    return CapacityAllocation(
        id=0,
        project_id=1,
        employee_id=1,
        role_id=1,
        week_start=week_start,
        person_days=person_days,
    )


def _project(
    start: date = date(2026, 1, 5),
    end: date = date(2026, 4, 27),
    budget: float = 100_000,
) -> Project:
    return Project(
        code="TEST",
        customer="Acme",
        name_de="Test",
        start_date=start,
        end_date=end,
        budget=budget,
    )


def _status(status_date: date, progress: int, budget_spent: int) -> ProjectStatus:
    return ProjectStatus(
        project_id=1,
        status_date=status_date.isoformat(),
        progress=progress,
        budget_spent=budget_spent,
    )


class TestCumulativePv:
    """Unit tests for the _cumulative_pv helper."""

    def test_full_week_before_target(self) -> None:
        week = date(2026, 1, 5)
        allocs = [_alloc(week, 5.0)]
        total_pd = 5.0
        budget = 100.0
        # target is after the full week ends → full 5 days count
        result = _cumulative_pv(week + _WEEK, allocs, total_pd, budget)
        assert result == pytest.approx(100.0)

    def test_partial_week(self) -> None:
        week = date(2026, 1, 5)
        allocs = [_alloc(week, 7.0)]
        total_pd = 7.0
        budget = 100.0
        # target is 3.5 days into the week → 50 % of budget
        result = _cumulative_pv(week + timedelta(days=3), allocs, total_pd, budget)
        # fraction = 3/7
        expected = budget * (7.0 * 3 / 7) / total_pd
        assert result == pytest.approx(expected)

    def test_week_entirely_after_target_ignored(self) -> None:
        future_week = date(2026, 3, 2)
        allocs = [_alloc(future_week, 5.0)]
        total_pd = 5.0
        budget = 100.0
        # target is before the week starts → nothing accumulated
        result = _cumulative_pv(date(2026, 2, 1), allocs, total_pd, budget)
        assert result == pytest.approx(0.0)

    def test_two_weeks_cumulative(self) -> None:
        w1 = date(2026, 1, 5)
        w2 = w1 + _WEEK
        allocs = [_alloc(w1, 3.0), _alloc(w2, 7.0)]
        total_pd = 10.0
        budget = 100.0
        # target after both weeks → full budget
        result = _cumulative_pv(w2 + _WEEK, allocs, total_pd, budget)
        assert result == pytest.approx(100.0)

    def test_zero_total_pd_returns_zero(self) -> None:
        allocs = [_alloc(date(2026, 1, 5), 0.0)]
        assert _cumulative_pv(date(2026, 2, 1), allocs, 0.0, 100.0) == pytest.approx(
            0.0
        )


class TestBuildChartDataWithCapacity:
    """Tests for capacity-weighted PV in build_chart_data."""

    def test_returns_empty_when_no_dates(self) -> None:
        project = Project(code="X", customer="A", name_de="N", budget=100_000)
        result = EVForecastService.build_chart_data(project, [], [])
        assert result == []

    def test_fallback_to_linear_when_no_allocations(self) -> None:
        project = _project()
        total_days = (project.end_date - project.start_date).days
        mid = project.start_date + timedelta(days=total_days // 2)
        statuses = [_status(mid, 50, 50)]

        result = EVForecastService.build_chart_data(project, statuses, [])
        mid_point = next(r for r in result if r["label"] == mid.isoformat())

        # linear: pv = budget * elapsed / total
        expected_pv = project.budget * (mid - project.start_date).days / total_days
        assert mid_point["Planned Value"] == pytest.approx(expected_pv, rel=1e-4)

    def test_capacity_weighted_pv_at_status_date(self) -> None:
        start = date(2026, 1, 5)
        end = date(2026, 1, 26)  # 3 weeks exactly
        project = _project(start=start, end=end, budget=30_000)

        w1 = start
        w2 = start + _WEEK
        w3 = start + 2 * _WEEK
        allocs = [_alloc(w1, 3.0), _alloc(w2, 3.0), _alloc(w3, 3.0)]

        # Status at end of week 1 → 1/3 of planned person-days done
        statuses = [_status(w1 + _WEEK, 30, 30)]

        result = EVForecastService.build_chart_data(project, statuses, allocs)
        status_point = next(r for r in result if r["label"] == (w1 + _WEEK).isoformat())
        assert status_point["Planned Value"] == pytest.approx(10_000.0)

    def test_capacity_pv_reaches_budget_at_end(self) -> None:
        start = date(2026, 1, 5)
        end = date(2026, 1, 19)  # 2 weeks
        project = _project(start=start, end=end, budget=10_000)
        allocs = [_alloc(start, 5.0), _alloc(start + _WEEK, 5.0)]

        result = EVForecastService.build_chart_data(project, [], allocs)
        end_point = next(r for r in result if r["label"] == end.isoformat())
        assert end_point["Planned Value"] == pytest.approx(10_000.0)

    def test_forecast_curve_present_after_last_status(self) -> None:
        start = date(2026, 1, 5)
        end = date(2026, 3, 30)
        project = _project(start=start, end=end, budget=100_000)
        allocs = [_alloc(start + i * _WEEK, 5.0) for i in range(12)]

        mid = start + timedelta(weeks=4)
        statuses = [_status(mid, 40, 45)]

        result = EVForecastService.build_chart_data(project, statuses, allocs)
        labels = [r["label"] for r in result]
        # Forecast weeks must appear after the mid status
        forecast_labels = [
            lbl for lbl in labels if lbl > mid.isoformat() and lbl < end.isoformat()
        ]
        assert len(forecast_labels) > 0

    def test_forecast_lines_are_none_before_last_status(self) -> None:
        start = date(2026, 1, 5)
        end = date(2026, 3, 30)
        project = _project(start=start, end=end, budget=100_000)
        allocs = [_alloc(start + i * _WEEK, 5.0) for i in range(12)]

        mid = start + timedelta(weeks=4)
        statuses = [_status(mid, 40, 45)]

        result = EVForecastService.build_chart_data(project, statuses, allocs)
        # The start point should have no forecast lines
        start_point = next(r for r in result if r["label"] == start.isoformat())
        assert start_point["Prognose (linear)"] is None
        assert start_point["Prognose (additiv)"] is None

    def test_pv_monotonically_non_decreasing_with_capacity(self) -> None:
        """PV must never decrease regardless of allocation shape or bad data."""
        start = date(2026, 5, 4)
        end = date(2026, 7, 27)
        project = _project(start=start, end=end, budget=100_000)
        # Simulate sparse early allocations and dense late allocations
        allocs = (
            [_alloc(start + i * _WEEK, 1.0) for i in range(2)]  # sparse May
            + [_alloc(start + i * _WEEK, 10.0) for i in range(4, 12)]  # dense June-July
        )
        statuses = [
            _status(start + timedelta(weeks=1), 10, 10),
            _status(start + timedelta(weeks=3), 20, 22),
        ]

        result = EVForecastService.build_chart_data(project, statuses, allocs)
        pv_values = [
            r["Planned Value"] for r in result if r["Planned Value"] is not None
        ]

        for i in range(1, len(pv_values)):
            assert pv_values[i] >= pv_values[i - 1], (
                f"PV decreased at index {i}: {pv_values[i - 1]} → {pv_values[i]}"
            )

    def test_pv_monotonically_non_decreasing_linear_fallback(self) -> None:
        """Linear fallback PV must also be non-decreasing."""
        project = _project()
        statuses = [
            _status(project.start_date + timedelta(weeks=2), 20, 25),
            _status(project.start_date + timedelta(weeks=4), 40, 45),
        ]
        result = EVForecastService.build_chart_data(project, statuses, [])
        pv_values = [
            r["Planned Value"] for r in result if r["Planned Value"] is not None
        ]

        for i in range(1, len(pv_values)):
            assert pv_values[i] >= pv_values[i - 1]


class TestComputeStatusEv:
    """Tests for compute_status_ev (unchanged but verified)."""

    def test_basic_ev_computation(self) -> None:
        summary = EVForecastService.compute_status_ev(100_000, 50, 45)
        assert summary.budget == pytest.approx(100_000)
        assert summary.earned_value == pytest.approx(50_000)
        assert summary.actual_cost == pytest.approx(45_000)
        assert summary.has_data is True

    def test_zero_budget_returns_empty_summary(self) -> None:
        summary = EVForecastService.compute_status_ev(0, 50, 50)
        assert summary.has_data is False
        assert summary.budget == 0


class TestBuildSummary:
    """Tests for build_summary (unchanged but verified)."""

    def test_returns_last_status_values(self) -> None:
        project = _project(budget=200_000)
        statuses = [
            _status(date(2026, 2, 1), 20, 22),
            _status(date(2026, 3, 1), 50, 55),
        ]
        summary = EVForecastService.build_summary(project, statuses)
        assert summary.earned_value == pytest.approx(100_000)
        assert summary.actual_cost == pytest.approx(110_000)
        assert summary.has_data is True

    def test_no_statuses_returns_no_data(self) -> None:
        project = _project(budget=100_000)
        summary = EVForecastService.build_summary(project, [])
        assert summary.has_data is False

    def test_eac_linear_formula(self) -> None:
        # EAC_linear = BAC * AC / EV
        project = _project(budget=100_000)
        statuses = [_status(date(2026, 2, 1), 40, 50)]
        summary = EVForecastService.build_summary(project, statuses)
        # ev=40000, ac=50000 → eac = 100000 * 50000 / 40000 = 125000
        assert summary.eac_linear == pytest.approx(125_000)

    def test_eac_additive_formula(self) -> None:
        # EAC_additive = BAC + AC - EV
        project = _project(budget=100_000)
        statuses = [_status(date(2026, 2, 1), 40, 50)]
        summary = EVForecastService.build_summary(project, statuses)
        # ev=40000, ac=50000 → eac = 100000 + 50000 - 40000 = 110000
        assert summary.eac_additive == pytest.approx(110_000)
