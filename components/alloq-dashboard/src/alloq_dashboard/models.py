"""Read models for dashboard KPI cards and drill-down drawers."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class TrendPoint(BaseModel):
    """One labelled point in a weekly trend series."""

    label: str
    week_start: date | None = None
    value: float = 0.0


class StateCount(BaseModel):
    """Project count for one state label."""

    state: str
    count: int = 0
    color: str = "#888"


class ProjectsOverviewKpi(BaseModel):
    """KPI payload for active projects overview."""

    total: int = 0
    active: int = 0
    planned: int = 0
    at_risk: int = 0
    completed: int = 0
    by_state: list[StateCount] = []
    rows: list[ProjectSummary] = []
    active_rows: list[ProjectSummary] = []


class ProjectSummary(BaseModel):
    """Compact project descriptor for drill-down lists."""

    id: int = 0
    code: str = ""
    name: str = ""
    state: str = ""
    start_date: date | None = None
    end_date: date | None = None
    days_to_end: int = 0
    progress: int = 0
    budget: int = 0
    spent: int = 0
    spent_percent: float = 0.0
    risk_count: int = 0
    color: str = "#888"
    ev_earned_value: float = 0.0
    ev_actual_cost: float = 0.0
    ev_eac_linear: float = 0.0
    ev_eac_additive: float = 0.0


class ProjectHealthKpi(BaseModel):
    """KPI payload for project-health card."""

    at_risk_count: int = 0
    healthy_count: int = 0
    total_risk_count: int = 0
    rows: list[ProjectSummary] = []
    risk_trend: list[TrendPoint] = []


class EarnedValuePoint(BaseModel):
    """One monthly data point for the Earned Value chart (3 series)."""

    label: str = ""
    budget_pct: float = 0.0
    spent_pct: float = 0.0
    progress_pct: float = 0.0


class BudgetBurnKpi(BaseModel):
    """KPI payload for budget burn card."""

    total_budget: int = 0
    total_spent: int = 0
    spent_percent: float = 0.0
    trend: list[TrendPoint] = []
    earned_value: list[EarnedValuePoint] = []
    rows: list[ProjectSummary] = []


class WeeklyUtilization(BaseModel):
    """Aggregated utilization for one week."""

    week_label: str
    week_start: date | None = None
    used_days: float = 0.0
    available_days: float = 0.0
    percent: int = 0
    bucket: str = "low"
    is_absent: bool = False


class UtilizationKpi(BaseModel):
    """KPI payload for team utilization card."""

    current_percent: int = 0
    current_bucket: str = "low"
    current_week: int = 0
    current_week_label: str = ""
    past_weeks_start_label: str = ""
    past_weeks_end_label: str = ""
    current_absent_count: int = 0
    weeks: list[WeeklyUtilization] = []
    employee_breakdown: list[EmployeeUtilization] = []


class EmployeeUtilization(BaseModel):
    """Per-employee weekly utilization payload."""

    employee_id: int = 0
    name: str = ""
    role_name: str = ""
    avg_percent: int = 0
    current_week_percent: int = 0
    current_week_is_absent: bool = False
    free_hours_next_4w: float = 0.0
    weeks: list[WeeklyUtilization] = []


class UnderUtilizationKpi(BaseModel):
    """KPI payload for under-utilization (free capacity) card."""

    affected_count: int = 0
    total_free_hours: float = 0.0
    total_employees: int = 0
    overloaded_count: int = 0
    absent_count: int = 0
    top: list[EmployeeUtilization] = []
    rows: list[EmployeeUtilization] = []


class MonthlyRoleCapacity(BaseModel):
    """Free capacity for one role in one calendar month."""

    label: str = ""
    free_percent: int = 0
    free_days: float = 0.0
    available_days: float = 0.0


class RoleCapacity(BaseModel):
    """Aggregated free capacity for one role over the horizon."""

    role_id: int = 0
    role_name: str = ""
    color: str = "#888"
    available_days: float = 0.0
    allocated_days: float = 0.0
    free_days: float = 0.0
    free_percent: int = 0
    weeks: list[TrendPoint] = []
    employee_count: int = 0
    employee_names: list[str] = []
    monthly: list[MonthlyRoleCapacity] = []


class FreeCapacityKpi(BaseModel):
    """KPI payload for free-capacity-per-role card."""

    horizon_weeks: int = 13
    rows: list[RoleCapacity] = []


class RiskItem(BaseModel):
    """Risk descriptor for drill-down list."""

    id: int = 0
    project_id: int = 0
    project_code: str = ""
    project_name: str = ""
    name: str = ""
    severity: str = ""
    probability: int = 0
    impact: int = 0
    score: int = 0
    mitigation_status: str = ""
    owner: str | None = None
    updated_at: str = ""


class RiskKpi(BaseModel):
    """KPI payload for risk surface card."""

    open_total: int = 0
    open_high: int = 0
    open_medium: int = 0
    open_low: int = 0
    top_open: list[RiskItem] = []
    trend: list[TrendPoint] = []


ProjectsOverviewKpi.model_rebuild()
ProjectHealthKpi.model_rebuild()
EarnedValuePoint.model_rebuild()
BudgetBurnKpi.model_rebuild()
UtilizationKpi.model_rebuild()
UnderUtilizationKpi.model_rebuild()
MonthlyRoleCapacity.model_rebuild()
RoleCapacity.model_rebuild()
FreeCapacityKpi.model_rebuild()
RiskKpi.model_rebuild()
