"""Shared utilization calculation service.

Single source of truth for all capacity and utilization computations.
Both the planning grid heatmap and the dashboard KPI cards use this service
so that numbers always match.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

WORK_DAYS_PER_WEEK: int = 5
HOURS_PER_DAY: float = 8.0
HEAT_LOW: int = 70
HEAT_MID: int = 85
HEAT_HIGH: int = 100
PROJECT_ALLOC_MID: float = 2.0
PROJECT_ALLOC_HIGH: float = 4.0
PLANNING_ANCHOR_DATE: date = date(2026, 4, 27)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AbsencePeriod:
    """Minimal absence representation for utilization calculation."""

    start_date: date
    end_date: date


@dataclass(frozen=True)
class HeatResult:
    """Utilization result for a single employee in a single week."""

    percent: int
    bucket: str
    is_absent: bool
    available_days: float
    used_days: float


@dataclass(frozen=True)
class GesamtResult:
    """Free-days result for a single employee in a single week."""

    free_days: float
    bucket: str
    has_absence: bool


@dataclass(frozen=True)
class ProjectHeatResult:
    """Utilization result for a single project in a single week."""

    percent: int
    bucket: str
    allocated: float


@dataclass(frozen=True)
class UtilizationAllocationInput:
    """Minimal allocation input used by the heatmap calculation pipeline."""

    project_id: int
    employee_id: int
    week_start: date
    person_days: float


@dataclass(frozen=True)
class UtilizationEmployeeInput:
    """Minimal employee input used by the heatmap calculation pipeline."""

    employee_id: int
    name: str
    role_name: str
    internal_hours: int
    absences: tuple[AbsencePeriod, ...] = ()


@dataclass(frozen=True)
class WeekUtilizationResult:
    """Utilization result for one week."""

    week_label: str
    week_start: date
    used_days: float
    available_days: float
    percent: int
    bucket: str
    is_absent: bool = False


@dataclass(frozen=True)
class EmployeeUtilizationSeries:
    """Per-employee utilization series."""

    employee_id: int
    name: str
    role_name: str
    avg_percent: int
    current_week_percent: int
    current_week_is_absent: bool
    free_hours_next_4w: float
    weeks: list[WeekUtilizationResult]


@dataclass(frozen=True)
class TeamUtilizationSeries:
    """Team utilization series plus per-employee breakdown."""

    weeks: list[WeekUtilizationResult]
    employees: list[EmployeeUtilizationSeries]


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class UtilizationService:
    """Stateless service encapsulating all utilization computations.

    Every method is a classmethod so callers don't need to instantiate.
    """

    # ------------------------------------------------------------------
    # Bucket classifiers
    # ------------------------------------------------------------------

    @staticmethod
    def heat_bucket(percent: int) -> str:
        """Classify a utilization percentage into a heatmap bucket."""
        if percent < HEAT_LOW:
            return "low"
        if percent < HEAT_MID:
            return "mid"
        if percent <= HEAT_HIGH:
            return "high"
        return "over"

    @staticmethod
    def gesamt_bucket(free_days: float) -> str:
        """Classify free days into a gesamt bucket."""
        if free_days > 1.0:
            return "available"
        if free_days > 0.0:
            return "balanced"
        if free_days == 0.0:
            return "neutral"
        if free_days >= -1.0:
            return "tight"
        return "over"

    @staticmethod
    def project_heat_bucket(allocated: float) -> str:
        """Classify project allocation into a bucket."""
        if allocated <= 0:
            return "low"
        if allocated <= PROJECT_ALLOC_MID:
            return "mid"
        if allocated <= PROJECT_ALLOC_HIGH:
            return "high"
        return "over"

    # ------------------------------------------------------------------
    # Absence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def absence_days_in_week(
        absences: list[AbsencePeriod] | tuple[AbsencePeriod, ...],
        week_start: date,
    ) -> float:
        """Count absence working days overlapping a Mon-Fri week."""
        week_end = week_start + timedelta(days=4)
        total = 0.0
        for a in absences:
            overlap_start = max(a.start_date, week_start)
            overlap_end = min(a.end_date, week_end)
            if overlap_start > overlap_end:
                continue
            cur = overlap_start
            while cur <= overlap_end:
                if cur.weekday() < WORK_DAYS_PER_WEEK:
                    total += 1.0
                cur += timedelta(days=1)
        return total

    @staticmethod
    def cap_internal_days(
        internal_hours: int,
        absence_days: float,
        work_days: float = 5.0,
    ) -> float:
        """Cap internal days so they don't exceed remaining capacity."""
        internal_days = internal_hours / HOURS_PER_DAY
        return max(0.0, min(internal_days, work_days - absence_days))

    # ------------------------------------------------------------------
    # Employee-level computations (per week)
    # ------------------------------------------------------------------

    @classmethod
    def compute_employee_heat(
        cls,
        used_days: float,
        absence_days: float,
        internal_days: float,
        work_days: float = 5.0,
    ) -> HeatResult:
        """Compute heatmap percent for one employee in one week.

        This is the canonical formula used by the planning grid heatmap.
        Parameters use pre-computed values (internal already capped).
        """
        fully_absent = absence_days >= float(WORK_DAYS_PER_WEEK)
        available = max(0.0, work_days - internal_days - absence_days)

        if fully_absent:
            denom = work_days - internal_days
            pct = round((used_days / denom) * 100) if denom > 0 else 0
            bucket = "absent"
        elif available > 0:
            pct = round((used_days / available) * 100)
            bucket = cls.heat_bucket(pct)
        else:
            pct = 0
            bucket = "low"

        return HeatResult(
            percent=pct,
            bucket=bucket,
            is_absent=fully_absent,
            available_days=available,
            used_days=used_days,
        )

    @classmethod
    def compute_employee_gesamt(
        cls,
        used_days: float,
        absence_days: float,
        internal_days: float,
        work_days: float = 5.0,
    ) -> GesamtResult:
        """Compute free days for one employee in one week."""
        has_absence = absence_days > 0
        free = work_days - internal_days - used_days - absence_days
        bucket = "absent" if has_absence else cls.gesamt_bucket(free)
        return GesamtResult(free_days=free, bucket=bucket, has_absence=has_absence)

    # ------------------------------------------------------------------
    # High-level employee computation (from raw inputs)
    # ------------------------------------------------------------------

    @classmethod
    def compute_heat_from_raw(
        cls,
        used_days: float,
        internal_hours: int,
        absences: list[AbsencePeriod] | tuple[AbsencePeriod, ...],
        week_start: date,
    ) -> HeatResult:
        """Compute heatmap for one employee/week from raw absence list.

        Convenience method that computes absence_days and caps internal.
        """
        absence_days = cls.absence_days_in_week(absences, week_start)
        internal_days = cls.cap_internal_days(internal_hours, absence_days)
        return cls.compute_employee_heat(used_days, absence_days, internal_days)

    # ------------------------------------------------------------------
    # Project-level computations (per week)
    # ------------------------------------------------------------------

    @classmethod
    def compute_project_heat(
        cls,
        allocated_days: float,
        num_employees: int,
        work_days: float = 5.0,
    ) -> ProjectHeatResult:
        """Compute heatmap percent for a project in one week."""
        capacity = num_employees * work_days if num_employees else work_days
        pct = round((allocated_days / capacity) * 100) if capacity > 0 else 0
        return ProjectHeatResult(
            percent=pct,
            bucket=cls.heat_bucket(pct),
            allocated=allocated_days,
        )

    @classmethod
    def compute_project_gesamt(
        cls,
        allocated_days: float,
    ) -> tuple[float, str]:
        """Compute project gesamt (allocated + bucket)."""
        return allocated_days, cls.project_heat_bucket(allocated_days)

    # ------------------------------------------------------------------
    # Team-level aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_team_average(percents: list[int]) -> int:
        """Compute team average as mean of individual percents.

        This matches the DURCHSCHNITT row in the heatmap.
        """
        if not percents:
            return 0
        return round(sum(percents) / len(percents))

    @classmethod
    def compute_heatmap_allocation_cells(
        cls,
        allocations: list[UtilizationAllocationInput],
        week_starts: list[date] | tuple[date, ...] | set[date],
        project_ids: set[int] | None = None,
    ) -> dict[tuple[int, int, date], float]:
        """Normalize allocations exactly like the planning heatmap.

        The heatmap has one visible cell per employee, project and week. Role
        rows for that same triplet overwrite each other.
        """
        week_set = set(week_starts)
        deduped: dict[tuple[int, int, date], float] = {}
        for allocation in allocations:
            if allocation.week_start not in week_set:
                continue
            if project_ids is not None and allocation.project_id not in project_ids:
                continue
            key = (
                allocation.employee_id,
                allocation.project_id,
                allocation.week_start,
            )
            deduped[key] = allocation.person_days
        return deduped

    @classmethod
    def compute_heatmap_allocation_days(
        cls,
        allocations: list[UtilizationAllocationInput],
        week_starts: list[date] | tuple[date, ...] | set[date],
        project_ids: set[int] | None = None,
    ) -> dict[int, dict[date, float]]:
        """Aggregate normalized heatmap cells by employee and week."""
        deduped = cls.compute_heatmap_allocation_cells(
            allocations=allocations,
            week_starts=week_starts,
            project_ids=project_ids,
        )

        by_employee: dict[int, dict[date, float]] = {}
        for (employee_id, _project_id, week_start), person_days in deduped.items():
            employee_weeks = by_employee.setdefault(employee_id, {})
            employee_weeks[week_start] = (
                employee_weeks.get(week_start, 0.0) + person_days
            )
        return by_employee

    @classmethod
    def compute_team_utilization_series(
        cls,
        employees: list[UtilizationEmployeeInput],
        allocations: list[UtilizationAllocationInput],
        week_starts: list[date],
        current_week_start: date,
        free_capacity_start: date,
        free_capacity_weeks: int = 4,
        project_ids: set[int] | None = None,
    ) -> TeamUtilizationSeries:
        """Compute the same weekly team series as the planning heatmap."""
        allocation_days = cls.compute_heatmap_allocation_days(
            allocations=allocations,
            week_starts=week_starts,
            project_ids=project_ids,
        )
        free_capacity_end = free_capacity_start + timedelta(weeks=free_capacity_weeks)
        employee_series: list[EmployeeUtilizationSeries] = []

        for employee in employees:
            employee_weeks: list[WeekUtilizationResult] = []
            percents: list[int] = []
            current_week_percent = 0
            current_week_is_absent = False
            free_hours_next_4w = 0.0

            for week_start in week_starts:
                used_days = allocation_days.get(employee.employee_id, {}).get(
                    week_start,
                    0.0,
                )
                heat = cls.compute_heat_from_raw(
                    used_days=used_days,
                    internal_hours=employee.internal_hours,
                    absences=employee.absences,
                    week_start=week_start,
                )
                employee_weeks.append(
                    WeekUtilizationResult(
                        week_label=cls.week_label(week_start),
                        week_start=week_start,
                        used_days=heat.used_days,
                        available_days=heat.available_days,
                        percent=heat.percent,
                        bucket=heat.bucket,
                        is_absent=heat.is_absent,
                    )
                )
                percents.append(heat.percent)
                if week_start == current_week_start:
                    current_week_percent = heat.percent
                    current_week_is_absent = heat.is_absent
                if free_capacity_start <= week_start < free_capacity_end:
                    free_days = max(0.0, heat.available_days - used_days)
                    free_hours_next_4w += free_days * HOURS_PER_DAY

            employee_series.append(
                EmployeeUtilizationSeries(
                    employee_id=employee.employee_id,
                    name=employee.name,
                    role_name=employee.role_name,
                    avg_percent=cls.compute_team_average(percents),
                    current_week_percent=current_week_percent,
                    current_week_is_absent=current_week_is_absent,
                    free_hours_next_4w=round(free_hours_next_4w, 1),
                    weeks=employee_weeks,
                )
            )

        team_weeks: list[WeekUtilizationResult] = []
        for index, week_start in enumerate(week_starts):
            percents = [employee.weeks[index].percent for employee in employee_series]
            percent = cls.compute_team_average(percents)
            used_days = sum(
                employee.weeks[index].used_days for employee in employee_series
            )
            available_days = sum(
                employee.weeks[index].available_days for employee in employee_series
            )
            team_weeks.append(
                WeekUtilizationResult(
                    week_label=cls.week_label(week_start),
                    week_start=week_start,
                    used_days=round(used_days, 1),
                    available_days=round(available_days, 1),
                    percent=percent,
                    bucket=cls.heat_bucket(percent),
                    is_absent=False,
                )
            )

        return TeamUtilizationSeries(weeks=team_weeks, employees=employee_series)

    # ------------------------------------------------------------------
    # Date helpers
    # ------------------------------------------------------------------

    @staticmethod
    def monday_of(d: date) -> date:
        """Return the Monday of the week containing *d*."""
        return d - timedelta(days=d.weekday())

    @staticmethod
    def planning_week_starts(
        num_weeks: int,
        anchor_date: date = PLANNING_ANCHOR_DATE,
    ) -> list[date]:
        """Return week starts for the default planning heatmap range."""
        return [anchor_date + timedelta(weeks=index) for index in range(num_weeks)]

    @staticmethod
    def week_label(week_start: date) -> str:
        """Format a week start date as 'KWxx'."""
        return f"KW{week_start.isocalendar().week:02d}"


# ---------------------------------------------------------------------------
# Module-level aliases for backward compatibility
# ---------------------------------------------------------------------------

heat_bucket = UtilizationService.heat_bucket
gesamt_bucket = UtilizationService.gesamt_bucket
project_heat_bucket = UtilizationService.project_heat_bucket
absence_days_in_week = UtilizationService.absence_days_in_week
compute_week_utilization = UtilizationService.compute_heat_from_raw
compute_average_percent = UtilizationService.compute_team_average
monday_of = UtilizationService.monday_of
week_label = UtilizationService.week_label
