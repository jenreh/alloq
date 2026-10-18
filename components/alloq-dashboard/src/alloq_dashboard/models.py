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


class TopRiskProject(BaseModel):
    """Top budget-overrun project per week."""

    project_id: int = 0
    project_name: str = ""
    abs_delta: float = 0.0
    pct_delta: float = 0.0


class WeeklyForecastPoint(BaseModel):
    """Portfolio aggregate for one calendar week."""

    week_key: str = ""
    week_label: str = ""
    week_start: date | None = None
    week_end: date | None = None
    active_count: int = 0
    total_budget: float = 0.0
    actual_cost: float = 0.0
    earned_value: float = 0.0
    eac_linear: float = 0.0
    eac_additive: float = 0.0
    forecast_min: float = 0.0
    forecast_max: float = 0.0
    forecast_avg: float = 0.0
    forecast_band: float = 0.0
    overrun_abs: float = 0.0
    overrun_pct: float = 0.0
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    top_risks: list[TopRiskProject] = []


class BudgetBurnKpi(BaseModel):
    """KPI payload for budget burn card."""

    total_budget: int = 0
    total_spent: int = 0
    spent_percent: float = 0.0
    trend: list[TrendPoint] = []
    weekly_forecast: list[WeeklyForecastPoint] = []
    rows: list[ProjectSummary] = []
    latest_forecast: float = 0.0
    latest_budget: float = 0.0
    latest_delta_abs: float = 0.0
    latest_delta_pct: float = 0.0
    latest_risk_projects: int = 0
    latest_top_risk_name: str = ""
    latest_top_risk_delta: float = 0.0


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
    overloaded_count: int = 0
    well_utilized_count: int = 0
    under_utilized_count: int = 0
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


class PortfolioRoleLine(BaseModel):
    """One role of a project on the resource-critical path."""

    role_id: int = 0
    role_name: str = ""
    required_days: float = 0.0
    remaining_days: float = 0.0
    planned_days: float = 0.0
    gap_days: float = 0.0
    buffer_weeks: int | None = None
    buffer_label: str = ""
    buffer_tone: str = ""
    covered: bool = True
    carriers: list[str] = []
    person_id: int = 0
    person_label: str = ""
    tone: str = ""
    reason: str = ""


class PortfolioProject(BaseModel):
    """A project in scope with health, buffer and its weakest link."""

    id: int = 0
    code: str = ""
    name: str = ""
    state: str = ""
    end_label: str = ""
    progress: int = 0
    elapsed_percent: int = 0
    budget: int = 0
    eac: float = 0.0
    eac_delta_percent: float = 0.0
    health: str = ""
    has_buffer: bool = False
    buffer_weeks: int = 0
    buffer_label: str = ""
    buffer_tone: str = ""
    weakest: PortfolioRoleLine = PortfolioRoleLine()
    roles: list[PortfolioRoleLine] = []


class PortfolioBubble(BaseModel):
    """Plot position of an active project: time elapsed vs. progress."""

    project_id: int = 0
    code: str = ""
    health: str = ""
    negative_buffer: bool = False
    left: str = "0"
    top: str = "0"
    size: str = "16px"
    label_left: str = "0"
    label_top: str = "0"
    tooltip: str = ""


class RiskMatrixCell(BaseModel):
    """Open risks with one probability and impact."""

    key: str = ""
    probability: int = 0
    impact: int = 0
    score: int = 0
    band: str = "r1"
    count: int = 0


class RiskMatrixRow(BaseModel):
    """One probability row of the 5x5 risk matrix (impact 1..5)."""

    probability: int = 0
    cells: list[RiskMatrixCell] = []


class RoleDemand(BaseModel):
    """Available, planned and needed person-days of a role over the horizon."""

    role_id: int = 0
    role_name: str = ""
    employee_count: int = 0
    available_days: float = 0.0
    planned_days: float = 0.0
    need_days: float = 0.0
    gap_days: float = 0.0
    plan_width: str = "0%"
    over_width: str = "0%"
    need_left: str = "0%"
    overbooked: bool = False


class RoleWeek(BaseModel):
    """Available, planned and free days of a role in one week."""

    label: str = ""
    available_days: float = 0.0
    planned_days: float = 0.0
    free_days: float = 0.0
    tone: str = ""


class RolePerson(BaseModel):
    """A person holding a role, with days planned in it over the horizon."""

    employee_id: int = 0
    name: str = ""
    planned_days: float = 0.0
    avg_percent: int = 0
    tone: str = ""


class RoleGapProject(BaseModel):
    """A project with unplanned demand for a role."""

    project_id: int = 0
    code: str = ""
    name: str = ""
    gap_days: float = 0.0
    buffer_label: str = ""
    buffer_tone: str = ""


class RoleDetail(BaseModel):
    """Drawer content of one role over the 13-week horizon."""

    role_id: int = 0
    role_name: str = ""
    employee_count: int = 0
    available_days: float = 0.0
    planned_days: float = 0.0
    free_days: float = 0.0
    weeks: list[RoleWeek] = []
    people: list[RolePerson] = []
    gap_projects: list[RoleGapProject] = []


class PersonWeek(BaseModel):
    """Utilization of a person in one week."""

    label: str = ""
    booked_days: float = 0.0
    available_days: float = 0.0
    percent: int = 0
    absent: bool = False
    tone: str = ""
    bar_width: str = "0%"


class PersonAbsence(BaseModel):
    """An absence inside the horizon, with its work days."""

    label: str = ""
    days: int = 0


class PersonBooking(BaseModel):
    """Days a person is booked on a project in one role over the horizon."""

    project_id: int = 0
    code: str = ""
    name: str = ""
    role_id: int = 0
    role_name: str = ""
    days: float = 0.0
    in_scope: bool = False


class PersonDetail(BaseModel):
    """Drawer content of one person over the 13-week horizon."""

    employee_id: int = 0
    name: str = ""
    roles_label: str = ""
    avg_percent: int = 0
    tone: str = ""
    absent_days: int = 0
    weeks: list[PersonWeek] = []
    absences: list[PersonAbsence] = []
    bookings: list[PersonBooking] = []


class PortfolioKpi(BaseModel):
    """Payload of the portfolio overview (dashboard variant C)."""

    scope: str = "department"
    notice: str = ""
    department_employee_count: int = 0
    team_employee_count: int = 0
    projects: list[PortfolioProject] = []
    bubbles: list[PortfolioBubble] = []
    not_plotted_label: str = ""
    matrix: list[RiskMatrixRow] = []
    risks: list[RiskItem] = []
    risk_open_total: int = 0
    risk_high: int = 0
    risk_medium: int = 0
    risk_low: int = 0
    chains: list[PortfolioProject] = []
    comfortable_label: str = ""
    roles: list[RoleDemand] = []
    gap_total: float = 0.0
    role_details: list[RoleDetail] = []
    person_details: list[PersonDetail] = []


ProjectsOverviewKpi.model_rebuild()
ProjectHealthKpi.model_rebuild()
TopRiskProject.model_rebuild()
WeeklyForecastPoint.model_rebuild()
BudgetBurnKpi.model_rebuild()
UtilizationKpi.model_rebuild()
UnderUtilizationKpi.model_rebuild()
MonthlyRoleCapacity.model_rebuild()
RoleCapacity.model_rebuild()
FreeCapacityKpi.model_rebuild()
RiskKpi.model_rebuild()
