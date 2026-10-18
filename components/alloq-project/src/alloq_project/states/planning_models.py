"""Constants and pydantic models for the resource planning views."""

from __future__ import annotations

from pydantic import BaseModel

# === Constants ===

LABEL_COL_PX: int = 300
MIN_AVAILABLE_PT: float = 3.0
WEEK_COL_PX: int = 60
COMPACT_WEEK_COL_PX: int = 52
WEEKS_BEFORE_CURRENT = 1
TIME_RANGE_WEEKS: dict[str, int] = {
    "3 Monate": 13,
    "6 Monate": 26,
    "12 Monate": 52,
}


# === Models ===


class WeekColumn(BaseModel):
    key: str
    label: str
    week_no: int = 0
    month_label: str
    work_days: float
    is_month_start: bool = False
    is_short: bool = False
    title: str = ""
    holiday_days: list[int] = []


class MonthSpan(BaseModel):
    label: str
    span: int


class AbsenceGanttBar(BaseModel):
    absence_id: int = 0
    left_px: float
    width_px: float
    lane: int
    label: str
    side_label: str = ""
    inside: bool = False
    clipped: bool = False
    aria_label: str = ""
    period: str = ""
    work_days: int = 0
    calendar_days: int = 0
    holidays_note: str = ""
    overlap_note: str = ""


class AbsenceGanttRow(BaseModel):
    real_id: int
    name: str
    initials: str = ""
    avatar_color: str = ""
    job_title: str = ""
    bars: list[AbsenceGanttBar] = []
    height_px: int = 52
    total_days: int = 0
    next_label: str = ""


class GanttWeek(BaseModel):
    key: str
    kw: int
    label: str
    has_holiday: bool = False
    is_current: bool = False
    is_month_start: bool = False
    title: str = ""


class GanttMark(BaseModel):
    left_px: float
    title: str = ""


class CoverageCell(BaseModel):
    week_key: str
    label: str
    level: str = "ok"
    title: str = ""


class AffectedProject(BaseModel):
    name: str
    color: str = ""
    days_label: str
    weeks: str


class UpcomingAbsence(BaseModel):
    name: str
    initials: str = ""
    avatar_color: str = ""
    period: str
    relative: str
    is_running: bool = False
    projects: list[AffectedProject] = []
    status: str = "none"
    status_label: str = ""


class AbsenceGanttView(BaseModel):
    rows: list[AbsenceGanttRow] = []
    weeks: list[GanttWeek] = []
    coverage: list[CoverageCell] = []
    holidays: list[GanttMark] = []
    holiday_days: list[int] = []
    month_lines: list[int] = []
    upcoming: list[UpcomingAbsence] = []
    today_px: float = -1
    min_day: int = 0
    day_px: float = 0
    width_px: int = 0
    horizon_start: str = ""
    team_size: int = 0
    bottleneck_label: str = ""
    bottleneck_title: str = ""


class GridCell(BaseModel):
    key: str = ""
    week_key: str
    value: float
    is_dirty: bool = False
    is_repeat: bool = False
    is_default: bool = False


class GesamtCell(BaseModel):
    week_key: str
    value: float
    bucket: str
    state: str = "free"
    has_absence: bool = False
    breakdown: str = ""


class ProjectAllocationRow(BaseModel):
    project_id: str
    real_project_id: int = 0
    emp_id: str = ""
    code: str
    name: str
    color: str
    role_name: str = ""
    role_short: str = ""
    role_color: str = ""
    is_internal: bool = False
    cells: list[GridCell] = []


class AbsenceRow(BaseModel):
    cells: list[GridCell] = []


class RoleBadge(BaseModel):
    code: str
    full: str
    color: str


class RoleTotal(BaseModel):
    code: str = ""
    color: str = ""
    days: float = 0.0


class EmployeeBlock(BaseModel):
    id: str
    real_id: int = 0
    name: str
    first_name: str = ""
    last_name: str = ""
    initials: str
    avatar_color: str = ""
    job_title: str = ""
    role: str
    role_color: str
    role_full: str = ""
    roles: list[RoleBadge] = []
    role_ids: list[int] = []
    projects: list[ProjectAllocationRow] = []
    absence: AbsenceRow
    internal: AbsenceRow = AbsenceRow(cells=[])
    internal_days: float = 0.5
    hours_per_week: float = 40.0
    workload_percent: int = 100
    gesamt: list[GesamtCell] = []
    planned_days: float = 0.0
    available_days: float = 0.0


class EmployeeAllocationRow(BaseModel):
    emp_id: str = ""
    project_code: str = ""
    real_id: int = 0
    name: str = ""
    role_name: str = ""
    role_short: str = ""
    role_color: str = ""
    cells: list[GridCell] = []


class ProjectGesamtCell(BaseModel):
    week_key: str = ""
    allocated: float = 0.0
    bucket: str = "low"


class ProjectBlock(BaseModel):
    id: str = ""
    real_id: int = 0
    code: str = ""
    name: str = ""
    color: str = ""
    state: str = ""
    is_internal: bool = False
    employees: list[EmployeeAllocationRow] = []
    gesamt: list[ProjectGesamtCell] = []
    planned_days: float = 0.0
    role_totals: list[RoleTotal] = []
