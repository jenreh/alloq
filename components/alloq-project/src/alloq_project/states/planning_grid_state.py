"""Single source of truth for planning data, edit state, and views.

Allocations live once in `cells` keyed canonically by
``"{employee_id}|{project_code}|{week_key}"``. The two pivots — employee
blocks (Grid view) and project blocks (Project view) — are computed views of
the same store. Edits flow through the editor handlers, which update the
canonical map and mark keys dirty; both pivots reflect changes atomically.
No cross-state sync is needed.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_commons.models.role import Role
from alloq_commons.repositories import (
    capacity_allocation_repo,
    capacity_repo,
    employee_repo,
    project_repo,
    role_repo,
)
from alloq_commons.services.utilization import (
    UtilizationAllocationInput,
    UtilizationService,
)
from pydantic import BaseModel

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.states import UserSession

log = logging.getLogger(__name__)


# === Constants ===

LABEL_COL_PX: int = 300
WEEK_COL_PX: int = 60
_WORK_DAYS_PER_WEEK: int = 5
ANCHOR_DATE = datetime.date(2026, 4, 27)
TIME_RANGE_WEEKS: dict[str, int] = {
    "3 Monate": 13,
    "6 Monate": 26,
    "12 Monate": 52,
}

GERMAN_MONTHS = [
    "Jan",
    "Feb",
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
]

ROLE_PALETTE: dict[str, str] = {
    "PM": "var(--mantine-color-violet-1)",
    "AIA": "var(--mantine-color-orange-1)",
    "DS": "var(--mantine-color-blue-1)",
    "AIE": "var(--mantine-color-teal-1)",
    "RE": "var(--mantine-color-pink-1)",
}

ROLE_FULL: dict[str, str] = {
    "PM": "Project Manager",
    "AIA": "AI Architect",
    "DS": "Data Scientist",
    "AIE": "AI Engineer",
    "RE": "Requirements Engineer",
}


# === Models ===


class WeekColumn(BaseModel):
    key: str
    label: str
    week_no: int = 0
    month_label: str
    work_days: float


class MonthSpan(BaseModel):
    label: str
    span: int


class GridCell(BaseModel):
    key: str = ""
    week_key: str
    value: float
    is_dirty: bool = False


class GesamtCell(BaseModel):
    week_key: str
    value: float
    bucket: str


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
    cells: list[GridCell] = []


class AbsenceRow(BaseModel):
    cells: list[GridCell] = []


class RoleBadge(BaseModel):
    code: str
    full: str
    color: str


class EmployeeBlock(BaseModel):
    id: str
    real_id: int = 0
    name: str
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
    gesamt: list[GesamtCell] = []
    heat: list[HeatCell] = []


class EmployeeAllocationRow(BaseModel):
    emp_id: str = ""
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
    employees: list[EmployeeAllocationRow] = []
    gesamt: list[ProjectGesamtCell] = []
    heat: list[HeatCell] = []


class _CapAssignment:
    """Lightweight transport for CapacityEntity rows (avoids detached ORM)."""

    __slots__ = ("employee_id", "project_id", "role_name")

    def __init__(self, employee_id: int, project_id: int, role_name: str) -> None:
        self.employee_id = employee_id
        self.project_id = project_id
        self.role_name = role_name


# === Pure helpers ===


def _heat_bucket(percent: int) -> str:
    return UtilizationService.heat_bucket(percent)


def _gesamt_bucket(value: float) -> str:
    return UtilizationService.gesamt_bucket(value)


def _project_heat_bucket(allocated: float) -> str:
    return UtilizationService.project_heat_bucket(allocated)


def _build_weeks(num_weeks: int) -> tuple[list[WeekColumn], list[MonthSpan]]:
    weeks: list[WeekColumn] = []
    for i in range(num_weeks):
        d = ANCHOR_DATE + datetime.timedelta(days=7 * i)
        weeks.append(
            WeekColumn(
                key=f"{d.year}_{d.month:02d}_{d.day:02d}",
                label=f"{d.day}.{d.month}.",
                week_no=d.isocalendar().week,
                month_label=f"{GERMAN_MONTHS[d.month - 1]} {d.year % 100}",
                work_days=5.0,
            )
        )
    spans: list[MonthSpan] = []
    for w in weeks:
        if spans and spans[-1].label == w.month_label:
            spans[-1].span += 1
        else:
            spans.append(MonthSpan(label=w.month_label, span=1))
    return weeks, spans


def _week_key_for_date(d: datetime.date) -> str:
    return f"{d.year}_{d.month:02d}_{d.day:02d}"


def _role_short(name: str) -> str:
    if not name:
        return "—"
    words = name.split()
    if len(words) >= 2:  # noqa: PLR2004
        return "".join(w[0] for w in words[:3]).upper()
    return name[:3].upper()


def _absence_days_for_week(absences: list, week_start: datetime.date) -> float:
    week_end = week_start + datetime.timedelta(days=4)
    total = 0.0
    for a in absences:
        if not (a.start_date and a.end_date):
            continue
        overlap_start = max(a.start_date, week_start)
        overlap_end = min(a.end_date, week_end)
        if overlap_start > overlap_end:
            continue
        day = overlap_start
        while day <= overlap_end:
            if day.weekday() < _WORK_DAYS_PER_WEEK:
                total += 1.0
            day += datetime.timedelta(days=1)
    return total


def _format_de(value: float) -> str:
    if value == int(value):
        return f"{int(value)}"
    return f"{value:.1f}".replace(".", ",")


def _parse_de(text: str) -> float | None:
    s = text.strip()
    if not s:
        return 0.0
    s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    if v < 0:
        return None
    return v


def _ck(emp_id: str, proj_code: str, wk_key: str) -> str:
    """Canonical cell key."""
    return f"{emp_id}|{proj_code}|{wk_key}"


def _compute_gesamt(weeks: list[WeekColumn], block: EmployeeBlock) -> list[GesamtCell]:
    cells: list[GesamtCell] = []
    for idx, week in enumerate(weeks):
        used = sum(p.cells[idx].value for p in block.projects)
        absence = block.absence.cells[idx].value if block.absence.cells else 0.0
        internal = block.internal.cells[idx].value if block.internal.cells else 0.0
        result = UtilizationService.compute_employee_gesamt(
            used_days=used,
            absence_days=absence,
            internal_days=internal,
            work_days=week.work_days,
        )
        cells.append(
            GesamtCell(week_key=week.key, value=result.free_days, bucket=result.bucket)
        )
    return cells


def _compute_heat(weeks: list[WeekColumn], block: EmployeeBlock) -> list[HeatCell]:
    cells: list[HeatCell] = []
    for idx, week in enumerate(weeks):
        used = sum(p.cells[idx].value for p in block.projects)
        absence = block.absence.cells[idx].value if block.absence.cells else 0.0
        internal = block.internal.cells[idx].value if block.internal.cells else 0.0
        result = UtilizationService.compute_employee_heat(
            used_days=used,
            absence_days=absence,
            internal_days=internal,
            work_days=week.work_days,
        )
        cells.append(
            HeatCell(
                week_key=week.key,
                percent=result.percent,
                is_absent=result.is_absent,
                bucket=result.bucket,
            )
        )
    return cells


def _compute_project_gesamt(
    weeks: list[WeekColumn], block: ProjectBlock
) -> list[ProjectGesamtCell]:
    cells: list[ProjectGesamtCell] = []
    for idx, week in enumerate(weeks):
        allocated = sum(
            e.cells[idx].value for e in block.employees if idx < len(e.cells)
        )
        _, bucket = UtilizationService.compute_project_gesamt(allocated)
        cells.append(
            ProjectGesamtCell(week_key=week.key, allocated=allocated, bucket=bucket)
        )
    return cells


def _compute_project_heat(
    weeks: list[WeekColumn], block: ProjectBlock
) -> list[HeatCell]:
    cells: list[HeatCell] = []
    n = len(block.employees)
    for idx, week in enumerate(weeks):
        allocated = sum(
            e.cells[idx].value for e in block.employees if idx < len(e.cells)
        )
        result = UtilizationService.compute_project_heat(
            allocated_days=allocated,
            num_employees=n,
            work_days=week.work_days,
        )
        cells.append(
            HeatCell(
                week_key=week.key,
                percent=result.percent,
                is_absent=False,
                bucket=result.bucket,
            )
        )
    return cells


# === Population helpers ===


def _build_employee_meta(
    available_employees: list, wks: list[str]
) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
    week_starts = [datetime.date(*(int(p) for p in k.split("_"))) for k in wks]
    emp_meta: list[dict[str, Any]] = []
    absence_map: dict[str, list[float]] = {}
    for emp in available_employees:
        eid = f"emp-{emp.id}"
        absence_map[eid] = [
            _absence_days_for_week(emp.absences, ws) for ws in week_starts
        ]
        role_badges = [
            {
                "code": _role_short(rn),
                "full": rn,
                "color": ROLE_PALETTE.get(
                    _role_short(rn), "var(--mantine-color-gray-2)"
                ),
            }
            for rn in emp.role_names
        ]
        primary = emp.role_names[0] if emp.role_names else ""
        primary_short = _role_short(primary)
        emp_meta.append(
            {
                "id": eid,
                "real_id": int(emp.id),
                "name": f"{emp.first_name} {emp.last_name}".strip(),
                "initials": (f"{emp.first_name[:1]}{emp.last_name[:1]}".upper() or "?"),
                "job_title": emp.job_title or "",
                "role_short": primary_short,
                "role_color": ROLE_PALETTE.get(
                    primary_short, "var(--mantine-color-gray-2)"
                ),
                "role_full": primary or ROLE_FULL.get(primary_short, primary_short),
                "role_badges": role_badges,
                "role_ids": list(emp.role_ids) if emp.role_ids else [],
                "internal_hours": getattr(emp, "internal_hours", 4),
                "project_ids": [],
            }
        )
    return emp_meta, absence_map


def _build_project_meta(
    available_projects: list,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    proj_meta: list[dict[str, Any]] = []
    proj_idx: dict[int, dict[str, Any]] = {}
    for p in available_projects:
        real = int(p.id)
        code = p.code or ((p.name_de or "—")[:8].upper())
        entry: dict[str, Any] = {
            "id": f"proj-{real}",
            "real_id": real,
            "code": code,
            "name": p.name_de or "—",
            "color": p.color or "var(--mantine-color-gray-5)",
            "state": getattr(p, "state", ""),
            "employee_ids": [],
        }
        proj_meta.append(entry)
        proj_idx[real] = entry
    return proj_meta, proj_idx


def _ingest_allocations(
    allocations: list[Any],
    assignments: list[_CapAssignment],
    proj_idx: dict[int, dict[str, Any]],
    wk_set: set[str],
) -> tuple[dict[str, float], dict[str, str], set[tuple[str, int]]]:
    cells: dict[str, float] = {}
    role_lookup: dict[str, str] = {}
    pairs: set[tuple[str, int]] = set()

    week_starts = {
        datetime.date(*(int(part) for part in key.split("_"))) for key in wk_set
    }
    normalized_cells = UtilizationService.compute_heatmap_allocation_cells(
        allocations=[
            UtilizationAllocationInput(
                project_id=allocation.project_id,
                employee_id=allocation.employee_id,
                week_start=allocation.week_start,
                person_days=float(allocation.person_days),
            )
            for allocation in allocations
        ],
        week_starts=week_starts,
        project_ids=set(proj_idx),
    )
    for (employee_id, project_id, week_start), person_days in normalized_cells.items():
        eid = f"emp-{employee_id}"
        wk = _week_key_for_date(week_start)
        cells[_ck(eid, proj_idx[project_id]["code"], wk)] = person_days
        pairs.add((eid, project_id))

    for allocation in allocations:
        wk = _week_key_for_date(allocation.week_start)
        if wk not in wk_set or allocation.project_id not in proj_idx:
            continue
        eid = f"emp-{allocation.employee_id}"
        pairs.add((eid, allocation.project_id))
        rn = getattr(allocation, "_cached_role_name", "")
        if rn:
            role_lookup.setdefault(f"{eid}|{allocation.project_id}", rn)
    for cap in assignments:
        if cap.project_id not in proj_idx:
            continue
        eid = f"emp-{cap.employee_id}"
        pairs.add((eid, cap.project_id))
        if cap.role_name:
            role_lookup.setdefault(f"{eid}|{cap.project_id}", cap.role_name)
    return cells, role_lookup, pairs


def _wire_pairs(
    emp_meta: list[dict[str, Any]],
    proj_idx: dict[int, dict[str, Any]],
    pairs: set[tuple[str, int]],
) -> None:
    emp_by_id = {e["id"]: e for e in emp_meta}
    for eid, real_pid in pairs:
        emp = emp_by_id.get(eid)
        proj = proj_idx.get(real_pid)
        if emp is None or proj is None:
            continue
        pid_str = f"proj-{real_pid}"
        if pid_str not in emp["project_ids"]:
            emp["project_ids"].append(pid_str)
        if eid not in proj["employee_ids"]:
            proj["employee_ids"].append(eid)


def _initial_active_cell(
    emp_meta: list[dict[str, Any]],
    proj_meta: list[dict[str, Any]],
    wks: list[str],
) -> str:
    if not wks:
        return ""
    proj_by_id = {p["id"]: p for p in proj_meta}
    for emp in emp_meta:
        if not emp["project_ids"]:
            continue
        pid = emp["project_ids"][0]
        proj = proj_by_id.get(pid)
        if proj:
            return _ck(emp["id"], proj["code"], wks[0])
    return ""


# === Focus / editor scripts ===

_FOCUS_GRID_SCRIPT = (
    "setTimeout(() => "
    "(document.getElementById('planning-grid-root') || "
    "document.getElementById('project-view-root'))?.focus("
    "{preventScroll:true}), 0)"
)

_FOCUS_EDITOR_SCRIPT = (
    "setTimeout(() => {"
    "const el = document.querySelector('.grid-editor input');"
    "if (el) { el.focus(); el.select(); }"
    "}, 0)"
)

_BLUR_EDITOR_SCRIPT = (
    "const el = document.querySelector('.grid-editor input');"
    "if (el) el.blur();"
    "setTimeout(() => "
    "(document.getElementById('planning-grid-root') || "
    "document.getElementById('project-view-root'))?.focus("
    "{preventScroll:true}), 0);"
)


# === State ===


class PlanningStore(UserSession):
    """Unified planning state.

    Single source of truth for the resource planning page:

    - Entity caches (projects/employees/roles) loaded once from the DB.
    - Canonical allocations (`cells`) keyed
      ``"{emp_id}|{proj_code}|{wk_key}"``.
    - Render metadata, edit/filter/view state, modal/collapse flags.

    The two pivots (Grid view, Project view) are computed views of the
    same store; edits update `cells` directly with no cross-state sync.
    """

    # === Entity caches ===

    available_projects: list[Project] = []
    all_projects: list[Project] = []
    available_employees: list[Employee] = []
    available_roles: list[Role] = []
    is_loading: bool = False

    # === Grid + view state ===

    weeks: list[WeekColumn] = []
    month_spans: list[MonthSpan] = []
    is_loaded: bool = False

    cells: dict[str, float] = {}
    dirty_keys: list[str] = []

    employee_meta: list[dict[str, Any]] = []
    project_meta: list[dict[str, Any]] = []
    role_lookup: dict[str, str] = {}
    absence_days: dict[str, list[float]] = {}

    view_mode: str = "Grid"
    time_range: str = "3 Monate"
    is_saving: bool = False
    active_cell: str = ""
    editing_cell: str = ""
    draft_value: str = ""
    edit_version: int = 0

    project_filter: list[str] = []
    role_filter: list[str] = []
    employee_filter: list[str] = []
    search_query: str = ""
    project_scope: bool = False
    employee_scope: bool = False

    collapsed_employees: list[str] = []
    collapsed_projects: list[str] = []

    add_project_emp_id: str = ""
    add_project_options: list[dict[str, str]] = []
    add_project_role_options: list[dict[str, str]] = []

    # === Setters ===

    @rx.event
    def set_view_mode(self, value: str) -> None:
        self.view_mode = value

    @rx.event
    def set_time_range(self, value: str) -> Any:
        self.time_range = value
        return PlanningStore.reload_with_time_range(value)

    @rx.event
    def set_project_filter(self, value: list[str]) -> None:
        self.project_filter = value

    @rx.event
    def set_role_filter(self, value: list[str]) -> None:
        self.role_filter = value

    @rx.event
    def set_employee_filter(self, value: list[str]) -> None:
        self.employee_filter = value

    @rx.event
    def set_search_query(self, value: str) -> None:
        self.search_query = value

    @rx.event
    def toggle_project_scope(self) -> None:
        self.project_scope = not self.project_scope

    @rx.event
    def toggle_employee_scope(self) -> None:
        self.employee_scope = not self.employee_scope

    @rx.event
    def set_draft(self, value: str) -> None:
        self.draft_value = value

    # === Entity-derived select options ===

    @rx.var(cache=True)
    def project_select_options(self) -> list[dict[str, str]]:
        return [
            {"value": str(p.id), "label": p.name_de or p.code}
            for p in self.all_projects
        ]

    @rx.var(cache=True)
    def employee_select_options(self) -> list[dict[str, str]]:
        return [
            {"value": str(e.id), "label": f"{e.first_name} {e.last_name}"}
            for e in self.available_employees
        ]

    @rx.var(cache=True)
    def role_select_options(self) -> list[dict[str, str]]:
        return [{"value": str(r.id), "label": r.name} for r in self.available_roles]

    # === Computed pivots ===

    def _week_keys(self) -> list[str]:
        return [w.key for w in self.weeks]

    def _cell(self, key: str, week_key: str) -> GridCell:
        return GridCell(
            key=key,
            week_key=week_key,
            value=float(self.cells.get(key, 0.0)),
            is_dirty=key in self.dirty_keys,
        )

    @rx.var(cache=True)
    def employee_blocks(self) -> list[EmployeeBlock]:
        weeks = self.weeks
        if not weeks:
            return []
        wks = self._week_keys()
        proj_idx = {p["id"]: p for p in self.project_meta}
        blocks: list[EmployeeBlock] = []
        for emp in self.employee_meta:
            emp_id = emp["id"]
            ab = self.absence_days.get(emp_id, [0.0] * len(wks))
            absence_cells = [
                GridCell(week_key=wks[i], value=ab[i] if i < len(ab) else 0.0)
                for i in range(len(wks))
            ]
            roles = [
                RoleBadge(code=r["code"], full=r["full"], color=r["color"])
                for r in emp.get("role_badges", [])
            ]
            project_rows: list[ProjectAllocationRow] = []
            for pid in emp.get("project_ids", []):
                proj = proj_idx.get(pid)
                if proj is None:
                    continue
                code = proj["code"]
                cells = [self._cell(_ck(emp_id, code, wk), wk) for wk in wks]
                rname = self.role_lookup.get(f"{emp_id}|{proj['real_id']}", "")
                rshort = _role_short(rname)
                rcolor = ROLE_PALETTE.get(rshort, "var(--mantine-color-gray-2)")
                project_rows.append(
                    ProjectAllocationRow(
                        project_id=str(proj["real_id"]),
                        real_project_id=int(proj["real_id"]),
                        emp_id=emp_id,
                        code=code,
                        name=proj["name"],
                        color=proj["color"],
                        role_name=rname,
                        role_short=rshort,
                        role_color=rcolor,
                        cells=cells,
                    )
                )
            internal_hours = emp.get("internal_hours", 4)
            internal_days = internal_hours / 8.0
            internal_cells = [
                GridCell(
                    week_key=wks[i],
                    value=max(
                        0.0,
                        min(
                            internal_days,
                            weeks[i].work_days - ab[i]
                            if i < len(ab)
                            else internal_days,
                        ),
                    ),
                )
                for i in range(len(wks))
            ]
            block = EmployeeBlock(
                id=emp_id,
                real_id=emp["real_id"],
                name=emp["name"],
                initials=emp["initials"],
                job_title=emp.get("job_title", ""),
                role=emp.get("role_short", ""),
                role_color=emp.get("role_color", ""),
                role_full=emp.get("role_full", ""),
                roles=roles,
                role_ids=emp.get("role_ids", []),
                projects=project_rows,
                absence=AbsenceRow(cells=absence_cells),
                internal=AbsenceRow(cells=internal_cells),
                internal_days=internal_days,
            )
            block.gesamt = _compute_gesamt(weeks, block)
            block.heat = _compute_heat(weeks, block)
            blocks.append(block)
        return blocks

    @rx.var(cache=True)
    def project_blocks(self) -> list[ProjectBlock]:
        weeks = self.weeks
        if not weeks:
            return []
        wks = self._week_keys()
        emp_idx = {e["id"]: e for e in self.employee_meta}
        blocks: list[ProjectBlock] = []
        for proj in self.project_meta:
            code = proj["code"]
            emp_rows: list[EmployeeAllocationRow] = []
            for emp_id in proj.get("employee_ids", []):
                emp = emp_idx.get(emp_id)
                if emp is None:
                    continue
                cells = [self._cell(_ck(emp_id, code, wk), wk) for wk in wks]
                rname = self.role_lookup.get(f"{emp_id}|{proj['real_id']}", "")
                rshort = _role_short(rname)
                rcolor = ROLE_PALETTE.get(rshort, "var(--mantine-color-gray-2)")
                emp_rows.append(
                    EmployeeAllocationRow(
                        emp_id=emp_id,
                        real_id=emp["real_id"],
                        name=emp["name"],
                        role_name=rname,
                        role_short=rshort,
                        role_color=rcolor,
                        cells=cells,
                    )
                )
            emp_rows.sort(key=lambda r: r.name)
            block = ProjectBlock(
                id=proj["id"],
                real_id=proj["real_id"],
                code=code,
                name=proj["name"],
                color=proj["color"],
                state=proj.get("state", ""),
                employees=emp_rows,
            )
            block.gesamt = _compute_project_gesamt(weeks, block)
            block.heat = _compute_project_heat(weeks, block)
            blocks.append(block)
        return blocks

    # === Filtered pivots ===

    @rx.var(cache=True)
    def filtered_employees(self) -> list[EmployeeBlock]:
        result = self.employee_blocks
        q = self.search_query.strip().lower()
        if q:
            result = [
                e for e in result if q in e.name.lower() or q in e.initials.lower()
            ]
        if self.project_filter:
            result = [
                e
                for e in result
                if any(p.project_id in self.project_filter for p in e.projects)
            ]
        if self.role_filter:
            result = [
                e
                for e in result
                if any(str(rid) in self.role_filter for rid in e.role_ids)
            ]
        if self.employee_filter:
            result = [e for e in result if str(e.real_id) in self.employee_filter]
        return result

    @rx.var(cache=True)
    def filtered_projects(self) -> list[ProjectBlock]:
        result = self.project_blocks
        if self.project_filter:
            result = [p for p in result if str(p.real_id) in self.project_filter]
        if self.role_filter:
            result = [
                p
                for p in result
                if any(
                    e.role_short in self.role_filter or e.role_name in self.role_filter
                    for e in p.employees
                )
            ]
        if self.employee_filter:
            result = [
                p
                for p in result
                if any(str(e.real_id) in self.employee_filter for e in p.employees)
            ]
        q = self.search_query.strip().lower()
        if q:
            result = [
                p
                for p in result
                if q in p.name.lower()
                or q in p.code.lower()
                or any(q in e.name.lower() for e in p.employees)
            ]
        return result

    @rx.var(cache=True)
    def employees(self) -> list[EmployeeBlock]:
        _ = self.cells  # explicit dependency for heatmap reactivity
        return self.employee_blocks

    @rx.var(cache=True)
    def projects(self) -> list[ProjectBlock]:
        return self.project_blocks

    @rx.var(cache=True)
    def has_dirty(self) -> bool:
        return len(self.dirty_keys) > 0

    @rx.var(cache=True)
    def avg_heat(self) -> list[HeatCell]:
        _ = self.cells  # explicit dependency for heatmap reactivity
        emps = self.employee_blocks
        if not emps or not self.weeks:
            return []
        out: list[HeatCell] = []
        for idx, week in enumerate(self.weeks):
            percents = [e.heat[idx].percent for e in emps if idx < len(e.heat)]
            avg = UtilizationService.compute_team_average(percents)
            out.append(
                HeatCell(
                    week_key=week.key,
                    percent=avg,
                    is_absent=False,
                    bucket=UtilizationService.heat_bucket(avg),
                )
            )
        return out

    @rx.var(cache=True)
    def current_week_key(self) -> str:
        today = datetime.datetime.now(tz=datetime.UTC).date()
        monday = today - datetime.timedelta(days=today.weekday())
        return _week_key_for_date(monday)

    @rx.var(cache=True)
    def table_width(self) -> str:
        return f"{LABEL_COL_PX + len(self.weeks) * WEEK_COL_PX}px"

    @rx.var(cache=True)
    def grid_template_columns(self) -> str:
        return f"{LABEL_COL_PX}px repeat({len(self.weeks)}, {WEEK_COL_PX}px)"

    @rx.var(cache=True)
    def project_filter_label(self) -> str:
        c = len(self.project_filter)
        return f'"Projekte ({c})"' if c > 0 else ""

    @rx.var(cache=True)
    def role_filter_label(self) -> str:
        c = len(self.role_filter)
        return f'"Rollen ({c})"' if c > 0 else ""

    @rx.var(cache=True)
    def employee_filter_label(self) -> str:
        c = len(self.employee_filter)
        return f'"MA ({c})"' if c > 0 else ""

    # === Loading ===

    async def _fetch_data(
        self, weeks: list[WeekColumn]
    ) -> tuple[list[Any], list[_CapAssignment]]:
        if not weeks:
            return [], []
        first = datetime.date(*(int(p) for p in weeks[0].key.split("_")))
        last = datetime.date(*(int(p) for p in weeks[-1].key.split("_")))
        async with get_asyncdb_session() as session:
            allocs = await capacity_allocation_repo.find_in_range(session, first, last)
            for r in allocs:
                r._cached_role_name = r.role.name if r.role else ""  # noqa: SLF001
                session.expunge(r)
            from alloq_commons.entities.capacity import CapacityEntity  # noqa: PLC0415
            from sqlmodel import select  # noqa: PLC0415

            cap_rows = await session.execute(select(CapacityEntity))
            entities = list(cap_rows.scalars().unique().all())
            assignments = [
                _CapAssignment(
                    employee_id=e.employee_id,
                    project_id=e.project_id,
                    role_name=e.role.name if e.role else "",
                )
                for e in entities
            ]
        return list(allocs), assignments

    async def _populate(self, num_weeks: int) -> None:
        weeks, spans = _build_weeks(num_weeks)
        allocations, assignments = await self._fetch_data(weeks)
        wks = [w.key for w in weeks]

        emp_meta, absence_map = _build_employee_meta(self.available_employees, wks)
        proj_meta, proj_idx = _build_project_meta(self.available_projects)
        cells, role_lookup, pairs = _ingest_allocations(
            allocations, assignments, proj_idx, set(wks)
        )
        _wire_pairs(emp_meta, proj_idx, pairs)

        self.weeks = weeks
        self.month_spans = spans
        self.cells = cells
        self.dirty_keys = []
        self.employee_meta = emp_meta
        self.project_meta = proj_meta
        self.role_lookup = role_lookup
        self.absence_days = absence_map
        self.is_loaded = True
        self.editing_cell = ""
        self.draft_value = ""
        if not self.active_cell:
            self.active_cell = _initial_active_cell(emp_meta, proj_meta, wks)

    async def _load_entities(self) -> None:
        async with get_asyncdb_session() as session:
            projects = await project_repo.find_all(session)
            all_proj = [Project(**p.to_dict()) for p in projects]
            all_proj.sort(key=lambda p: (p.name_de or p.code).lower())
            self.all_projects = all_proj
            self.available_projects = [
                p for p in all_proj if p.state != "Abgeschlossen"
            ]
            employees = await employee_repo.find_all(session)
            self.available_employees = [Employee(**e.to_dict()) for e in employees]
            self.available_employees.sort(key=lambda e: (e.last_name, e.first_name))
            roles = await role_repo.find_all(session)
            self.available_roles = [Role(**r.to_dict()) for r in roles]
            self.available_roles.sort(key=lambda r: r.name)

    @rx.event
    async def load(self) -> AsyncGenerator[Any, None]:
        """Load entity caches and populate the grid for the current time range."""
        self.is_loading = True
        yield
        await self._load_entities()
        n = TIME_RANGE_WEEKS.get(self.time_range, TIME_RANGE_WEEKS["3 Monate"])
        await self._populate(n)
        self.is_loading = False
        yield

    @rx.event
    async def reload_with_time_range(self, time_range: str) -> None:
        n = TIME_RANGE_WEEKS.get(time_range, TIME_RANGE_WEEKS["3 Monate"])
        await self._populate(n)

    # === Cell editing ===

    @rx.event
    def set_active(self, cell_key: str) -> Any:
        self.active_cell = cell_key
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def start_edit(self, cell_key: str) -> Any:
        cur = self._lookup_value(cell_key)
        self.draft_value = "" if cur == 0 else _format_de(cur)
        self.active_cell = cell_key
        self.editing_cell = cell_key
        self.edit_version += 1
        return rx.call_script(_FOCUS_EDITOR_SCRIPT)

    @rx.event
    def cancel_edit(self) -> Any:
        self.editing_cell = ""
        self.draft_value = ""
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def commit_edit(self) -> Any:
        self._commit_current()
        self.editing_cell = ""
        self.draft_value = ""
        return None

    @rx.event
    def commit_and_select_next(self, direction: str) -> Any:
        cur = self.editing_cell
        if not cur:
            return None
        self._commit_current()
        nxt = self._navigate(cur, direction)
        self.editing_cell = ""
        self.draft_value = ""
        if nxt:
            self.active_cell = nxt
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def commit_and_move(self, direction: str) -> Any:
        cur = self.editing_cell
        if not cur:
            return None
        self._commit_current()
        nxt = self._navigate(cur, direction)
        if nxt:
            cur_val = self._lookup_value(nxt)
            self.draft_value = "" if cur_val == 0 else _format_de(cur_val)
            self.active_cell = nxt
            self.editing_cell = nxt
            self.edit_version += 1
            return rx.call_script(_FOCUS_EDITOR_SCRIPT)
        self.editing_cell = ""
        self.draft_value = ""
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def handle_key(self, key: str) -> Any:
        if key == "Enter":
            return rx.call_script(_BLUR_EDITOR_SCRIPT)
        if key == "Escape":
            return self.cancel_edit()
        if key == "Tab":
            return self.commit_and_move("next")
        return None

    @rx.event
    def move_active(self, direction: str) -> None:
        if self.editing_cell or not self.active_cell:
            return
        nxt = self._navigate(self.active_cell, direction)
        if nxt:
            self.active_cell = nxt

    @rx.event
    def handle_grid_key(self, key: str) -> Any:
        if self.editing_cell or not self.active_cell:
            return None
        nav = ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight")
        edit = ("Enter", "F2")
        if key not in nav and key not in edit:
            return None
        if key == "ArrowUp":
            self.move_active("up")
        elif key == "ArrowDown":
            self.move_active("down")
        elif key == "ArrowLeft":
            self.move_active("prev")
        elif key == "ArrowRight":
            self.move_active("next")
        elif key in edit:
            return self.start_edit(self.active_cell)
        return rx.prevent_default

    # Single-store: writes already canonical. Backward-compat shim.
    @rx.event
    def sync_cell(self, cell_key: str, value: float) -> None:
        self.cells = {**self.cells, cell_key: value}
        if cell_key not in self.dirty_keys:
            self.dirty_keys = [*self.dirty_keys, cell_key]

    @rx.event
    def clear_dirty(self) -> None:
        self.dirty_keys = []

    # === Internal helpers ===

    def _commit_current(self) -> tuple[str, float] | None:
        cur = self.editing_cell
        if not cur:
            return None
        new_val = _parse_de(self.draft_value)
        if new_val is None:
            return None
        cur_val = self._lookup_value(cur)
        if new_val == cur_val:
            return None
        self.cells = {**self.cells, cur: new_val}
        if cur not in self.dirty_keys:
            self.dirty_keys = [*self.dirty_keys, cur]
        return (cur, new_val)

    def _lookup_value(self, cell_key: str) -> float:
        return float(self.cells.get(cell_key, 0.0))

    def _row_layout(self) -> list[tuple[str, str]]:
        if self.view_mode == "Projekte":
            rows: list[tuple[str, str]] = []
            for proj in self.project_meta:
                if proj["id"] in self.collapsed_projects:
                    continue
                code = proj["code"]
                rows.extend((eid, code) for eid in proj.get("employee_ids", []))
            return rows
        rows = []
        proj_idx = {p["id"]: p for p in self.project_meta}
        for emp in self.employee_meta:
            if emp["id"] in self.collapsed_employees:
                continue
            for pid in emp.get("project_ids", []):
                proj = proj_idx.get(pid)
                if proj is None:
                    continue
                rows.append((emp["id"], proj["code"]))
        return rows

    def _navigate(self, cur_key: str, direction: str) -> str:  # noqa: PLR0911
        try:
            emp_id, proj_code, week_key = cur_key.split("|")
        except ValueError:
            return ""
        wks = self._week_keys()
        rows = self._row_layout()
        if not rows or not wks:
            return ""
        try:
            week_idx = wks.index(week_key)
            row_idx = rows.index((emp_id, proj_code))
        except ValueError:
            return ""
        if direction == "next" and week_idx + 1 < len(wks):
            return _ck(emp_id, proj_code, wks[week_idx + 1])
        if direction == "prev" and week_idx > 0:
            return _ck(emp_id, proj_code, wks[week_idx - 1])
        if direction == "down" and row_idx + 1 < len(rows):
            ne, np = rows[row_idx + 1]
            return _ck(ne, np, week_key)
        if direction == "up" and row_idx > 0:
            ne, np = rows[row_idx - 1]
            return _ck(ne, np, week_key)
        return ""

    # === Collapse ===

    @rx.event
    def toggle_employee(self, emp_id: str) -> None:
        if emp_id in self.collapsed_employees:
            self.collapsed_employees = [
                e for e in self.collapsed_employees if e != emp_id
            ]
        else:
            self.collapsed_employees = [*self.collapsed_employees, emp_id]

    @rx.event
    def toggle_project(self, project_id: str) -> None:
        if project_id in self.collapsed_projects:
            self.collapsed_projects = [
                p for p in self.collapsed_projects if p != project_id
            ]
        else:
            self.collapsed_projects = [*self.collapsed_projects, project_id]

    # === Save ===

    @rx.event
    async def save_grid(self) -> AsyncGenerator[Any, None]:
        if not self.dirty_keys:
            yield rx.toast.info("Keine Änderungen.", position="top-right")
            return
        self.is_saving = True
        yield
        proj_code_to_real = {p["code"]: p["real_id"] for p in self.project_meta}
        emp_id_to_real = {e["id"]: e["real_id"] for e in self.employee_meta}
        emp_role_id: dict[str, int] = {
            e["id"]: e["role_ids"][0] for e in self.employee_meta if e.get("role_ids")
        }
        rows: list[dict] = []
        for key in self.dirty_keys:
            try:
                emp_id, proj_code, wk_key = key.split("|")
            except ValueError:
                continue
            real_eid = emp_id_to_real.get(emp_id)
            real_pid = proj_code_to_real.get(proj_code)
            role_id = emp_role_id.get(emp_id)
            if not real_eid or not real_pid or not role_id:
                continue
            try:
                y, m, d = (int(p) for p in wk_key.split("_"))
                wk = datetime.date(y, m, d)
            except ValueError:
                continue
            rows.append(
                {
                    "employee_id": real_eid,
                    "project_id": real_pid,
                    "role_id": role_id,
                    "week_start": wk,
                    "person_days": float(self.cells.get(key, 0.0)),
                }
            )
        if not rows:
            self.is_saving = False
            yield rx.toast.info("Keine Änderungen.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                await capacity_allocation_repo.batch_upsert(session, rows)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to save grid: %s", exc)
            self.is_saving = False
            yield rx.toast.error(
                f"Speichern fehlgeschlagen: {exc}", position="top-right"
            )
            return
        self.dirty_keys = []
        self.is_saving = False
        yield rx.toast.success(f"{len(rows)} Zellen gespeichert.", position="top-right")

    # === Add / remove project from employee in grid ===

    @rx.event
    async def open_add_project_for_employee(self, emp_id: str) -> None:
        self.add_project_emp_id = emp_id
        emp = next((e for e in self.employee_meta if e["id"] == emp_id), None)
        if not emp:
            return
        proj_idx = {p["id"]: p for p in self.project_meta}
        assigned_codes = {
            proj_idx[pid]["code"]
            for pid in emp.get("project_ids", [])
            if pid in proj_idx
        }
        self.add_project_options = [
            {"value": str(p.id), "label": f"{p.code} - {p.name_de}"}
            for p in self.available_projects
            if p.code not in assigned_codes
        ]
        emp_role_ids = set(emp.get("role_ids", []))
        self.add_project_role_options = [
            {"value": str(r.id), "label": r.name}
            for r in self.available_roles
            if r.id in emp_role_ids
        ]

    @rx.event
    def close_add_project_for_employee(self) -> None:
        self.add_project_emp_id = ""
        self.add_project_options = []
        self.add_project_role_options = []

    @rx.event
    async def add_project_to_employee_grid(
        self, form_data: dict
    ) -> AsyncGenerator[Any, None]:
        from alloq_commons.entities.capacity import CapacityEntity  # noqa: PLC0415

        project_id_raw = form_data.get("project_id")
        role_id_raw = form_data.get("role_id")
        if not project_id_raw or not role_id_raw:
            yield rx.toast.error(
                "Bitte Projekt und Rolle auswählen.", position="top-right"
            )
            return
        project_id = int(project_id_raw)
        role_id = int(role_id_raw)
        emp = next(
            (e for e in self.employee_meta if e["id"] == self.add_project_emp_id),
            None,
        )
        if not emp:
            yield rx.toast.error("Mitarbeiter nicht gefunden.", position="top-right")
            return
        project = next((p for p in self.available_projects if p.id == project_id), None)
        if not project or not project.start_date or not project.end_date:
            yield rx.toast.error("Projekt nicht gefunden.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                entity = CapacityEntity(
                    project_id=project_id,
                    employee_id=emp["real_id"],
                    role_id=role_id,
                    start_date=project.start_date,
                    end_date=project.end_date,
                    hours_per_week=40.0,
                )
                session.add(entity)
                await session.commit()
            self.add_project_emp_id = ""
            yield PlanningStore.load
        except Exception as e:  # noqa: BLE001
            log.error("Failed to add project: %s", e)
            yield rx.toast.error(f"Fehler: {e}", position="top-right")

    @rx.event
    async def remove_project_from_employee_grid(
        self, emp_id: str, project_id: int
    ) -> AsyncGenerator[Any, None]:
        emp = next((e for e in self.employee_meta if e["id"] == emp_id), None)
        if not emp:
            yield rx.toast.error("Mitarbeiter nicht gefunden.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                await capacity_repo.delete_by_project_and_employee(
                    session, project_id, emp["real_id"]
                )
                await capacity_allocation_repo.delete_by_project_and_employee(
                    session, project_id, emp["real_id"]
                )
            yield PlanningStore.load
            yield rx.toast.info("Projektzuweisung entfernt.", position="top-right")
        except Exception as e:  # noqa: BLE001
            log.error("Failed to remove project: %s", e)
            yield rx.toast.error(f"Fehler: {e}", position="top-right")
