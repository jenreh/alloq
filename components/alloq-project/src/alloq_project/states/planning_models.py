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


class MonthSpan(BaseModel):
    label: str
    span: int


class AbsenceGanttBar(BaseModel):
    left_px: float
    width_px: float
    lane: int
    label: str
    tooltip: str


class AbsenceGanttRow(BaseModel):
    real_id: int
    name: str
    job_title: str = ""
    bars: list[AbsenceGanttBar] = []
    height_px: int = 56


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


class HeatCell(BaseModel):
    week_key: str
    percent: int
    is_absent: bool = False
    bucket: str = "low"


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
    heat: list[HeatCell] = []
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
    heat: list[HeatCell] = []
    planned_days: float = 0.0
    role_totals: list[RoleTotal] = []
