"""Earned Value forecasting for project status charts.

Computes PV/EV/AC series and two cost-at-completion forecasts (EAC):

- Linear (CPI-based): assumes the past cost behavior continues.
  EAC_linear = BAC * AC / EV
- Additive (one-time variance): assumes the cost variance is a one-off
  and future spend follows the plan.
  EAC_additive = BAC + AC - EV

Forecast values are projected weekly from the last status entry to the
project end date so the chart shows continuous forecast curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from alloq_commons.models.project import CapacityAllocation, Project, ProjectStatus
from pydantic import BaseModel

_WEEK = timedelta(days=7)


class EVSummary(BaseModel):
    """Final EV figures and EAC forecasts at the latest status."""

    budget: float = 0
    actual_cost: float = 0
    earned_value: float = 0
    eac_linear: float = 0
    eac_additive: float = 0
    has_data: bool = False


@dataclass(slots=True)
class EVChartPoint:
    """One data point of the Earned Value chart."""

    label: str
    planned_value: float | None = None
    earned_value: float | None = None
    actual_cost: float | None = None
    forecast_linear: float | None = None
    forecast_additive: float | None = None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "Planned Value": _round2(self.planned_value),
            "Earned Value": _round2(self.earned_value),
            "Actual Cost": _round2(self.actual_cost),
            "Prognose (linear)": _round2(self.forecast_linear),
            "Prognose (additiv)": _round2(self.forecast_additive),
        }


def _round2(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _cumulative_pv(
    target: date,
    allocations: list[CapacityAllocation],
    total_pd: float,
    budget: float,
) -> float:
    """Return cumulative Planned Value up to *target* date.

    For each week:
        week_value = budget * (week_pt / total_pt)   # proportional budget share
        pv        += week_value                       # running cumulative

    Weeks fully completed before *target* are counted in full.
    The week that contains *target* is pro-rated by elapsed days / 7.
    Weeks starting after *target* are skipped.
    """
    if total_pd <= 0:
        return 0.0
    pv = 0.0
    for alloc in allocations:
        if alloc.week_start is None:
            continue
        pd = max(0.0, alloc.person_days)
        week_value = budget * pd / total_pd  # this week's proportional budget share
        week_end = alloc.week_start + _WEEK
        if week_end <= target:
            pv += week_value  # full week elapsed
        elif alloc.week_start < target:
            fraction = (target - alloc.week_start).days / 7
            pv += week_value * fraction  # partial week
    return pv


class EVForecastService:
    """Compute Earned Value chart series and EAC forecasts."""

    @staticmethod
    def linear_eac(budget: float, earned_value: float, actual_cost: float) -> float:
        """EAC = BAC * AC / EV (CPI extrapolation)."""
        if earned_value <= 0:
            return float(budget)
        return budget * actual_cost / earned_value

    @staticmethod
    def additive_eac(budget: float, earned_value: float, actual_cost: float) -> float:
        """EAC = BAC + AC - EV (one-time variance assumption)."""
        return float(budget) + actual_cost - earned_value

    @classmethod
    def compute_status_ev(
        cls,
        project_budget: float,
        progress: int,
        budget_spent: int,
    ) -> EVSummary:
        """Compute EV snapshot for a single status entry."""
        budget = float(project_budget or 0)
        if budget == 0:
            return EVSummary(budget=budget)
        ev = budget * progress / 100
        ac = budget * budget_spent / 100
        return EVSummary(
            budget=round(budget, 2),
            earned_value=round(ev, 2),
            actual_cost=round(ac, 2),
            eac_linear=round(cls.linear_eac(budget, ev, ac), 2),
            eac_additive=round(cls.additive_eac(budget, ev, ac), 2),
            has_data=True,
        )

    @classmethod
    def build_chart_data(
        cls,
        project: Project,
        statuses: list[ProjectStatus],
        capacity_allocations: list[CapacityAllocation] | None = None,
    ) -> list[dict]:
        """Build PV/EV/AC + weekly forecast curves for the EV chart.

        When *capacity_allocations* are provided the Planned Value curve is
        derived from the cumulative planned person-days (capacity-weighted
        S-curve).  If no allocations are available the method falls back to
        linear interpolation over the project duration.
        """
        if not project.start_date or not project.end_date:
            return []
        start = project.start_date
        end = project.end_date
        budget = project.budget or 0
        if end <= start or budget == 0:
            return []
        total_days = (end - start).days

        allocs = capacity_allocations or []
        total_pd = sum(a.person_days for a in allocs if a.week_start is not None)
        use_capacity = total_pd > 0

        def _pv(d: date) -> float:
            if use_capacity:
                return _cumulative_pv(d, allocs, total_pd, float(budget))
            day_offset = (d - start).days
            return float(budget) * day_offset / total_days

        sorted_statuses = sorted(
            (s for s in statuses if s.status_date),
            key=lambda s: s.status_date,
        )

        points: list[EVChartPoint] = [
            EVChartPoint(
                label=start.isoformat(),
                planned_value=0,
                earned_value=0,
                actual_cost=0,
            )
        ]

        last_date: date | None = None
        ac_last = 0.0
        eac_linear = float(budget)
        eac_additive = float(budget)

        for i, status in enumerate(sorted_statuses):
            status_date = date.fromisoformat(status.status_date[:10])
            pv = _pv(status_date)
            ev = budget * status.progress / 100
            ac = budget * status.budget_spent / 100
            is_last = i == len(sorted_statuses) - 1
            points.append(
                EVChartPoint(
                    label=status.status_date,
                    planned_value=pv,
                    earned_value=ev,
                    actual_cost=ac,
                    forecast_linear=ac if is_last else None,
                    forecast_additive=ac if is_last else None,
                )
            )
            if is_last:
                last_date = status_date
                ac_last = ac
                eac_linear = cls.linear_eac(budget, ev, ac)
                eac_additive = cls.additive_eac(budget, ev, ac)

        if last_date and last_date < end:
            forecast_span = (end - last_date).days
            week = last_date + _WEEK
            while week < end:
                progress = (week - last_date).days / forecast_span
                points.append(
                    EVChartPoint(
                        label=week.isoformat(),
                        planned_value=_pv(week),
                        forecast_linear=ac_last + (eac_linear - ac_last) * progress,
                        forecast_additive=ac_last + (eac_additive - ac_last) * progress,
                    )
                )
                week += _WEEK

        points.append(
            EVChartPoint(
                label=end.isoformat(),
                planned_value=float(budget),
                forecast_linear=eac_linear if last_date else None,
                forecast_additive=eac_additive if last_date else None,
            )
        )

        points.sort(key=lambda p: p.label)

        # Guarantee PV is monotonically non-decreasing regardless of data quality.
        pv_running_max = 0.0
        for point in points:
            if point.planned_value is not None:
                pv_running_max = max(pv_running_max, point.planned_value)
                point.planned_value = pv_running_max

        return [point.to_dict() for point in points]

    @classmethod
    def build_summary(
        cls,
        project: Project,
        statuses: list[ProjectStatus],
    ) -> EVSummary:
        """Return final AC/EV and EAC forecasts at the latest status."""
        budget = float(project.budget or 0)
        sorted_statuses = sorted(
            (s for s in statuses if s.status_date),
            key=lambda s: s.status_date,
        )
        if not sorted_statuses or budget == 0:
            return EVSummary(budget=budget)
        last = sorted_statuses[-1]
        ev = budget * last.progress / 100
        ac = budget * last.budget_spent / 100
        return EVSummary(
            budget=round(budget, 2),
            actual_cost=round(ac, 2),
            earned_value=round(ev, 2),
            eac_linear=round(cls.linear_eac(budget, ev, ac), 2),
            eac_additive=round(cls.additive_eac(budget, ev, ac), 2),
            has_data=True,
        )
