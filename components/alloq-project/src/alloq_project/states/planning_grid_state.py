"""State for the resource planning Grid view.

Loads weekly allocations from `capacity_allocations` and renders one
project row per employee/project pair that has saved data. Edits are
kept in local state until flushed via `save_grid`.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.repositories import capacity_allocation_repo
from pydantic import BaseModel

from appkit_commons.database.session import get_asyncdb_session

log = logging.getLogger(__name__)


LABEL_COL_PX: int = 300
WEEK_COL_PX: int = 60
_WORK_DAYS_PER_WEEK: int = 5

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
ANCHOR_DATE = datetime.date(2026, 4, 27)
TIME_RANGE_WEEKS: dict[str, int] = {
    "3 Monate": 13,
    "6 Monate": 26,
    "12 Monate": 52,
}


class _CapAssignment:
    """Lightweight container for capacity assignment data.

    Avoids detached ORM issues.
    """

    __slots__ = ("employee_id", "project_id", "role_name")

    def __init__(self, employee_id: int, project_id: int, role_name: str) -> None:
        self.employee_id = employee_id
        self.project_id = project_id
        self.role_name = role_name


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


class WeekColumn(BaseModel):
    key: str
    label: str
    week_no: int = 0
    month_label: str
    work_days: float
    net_days: float


class MonthSpan(BaseModel):
    label: str
    span: int


class GridCell(BaseModel):
    key: str = ""  # composite "emp_id|proj_id|week_key"
    week_key: str
    value: float
    is_dirty: bool = False


class GesamtCell(BaseModel):
    week_key: str
    value: float
    bucket: str  # "available" | "balanced" | "neutral" | "tight" | "over" | "absent"


class HeatCell(BaseModel):
    week_key: str
    percent: int
    is_absent: bool = False
    bucket: str = "low"  # "low" | "mid" | "high" | "over" | "absent"


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
    gesamt: list[GesamtCell] = []
    heat: list[HeatCell] = []


_HEAT_LOW = 70
_HEAT_MID = 85
_HEAT_HIGH = 100


def _heat_bucket(percent: int) -> str:
    if percent < _HEAT_LOW:
        return "low"
    if percent < _HEAT_MID:
        return "mid"
    if percent <= _HEAT_HIGH:
        return "high"
    return "over"


def _gesamt_bucket(value: float) -> str:
    if value > 1.0:
        return "available"
    if value > 0.0:
        return "balanced"
    if value == 0.0:
        return "neutral"
    if value >= -1.0:
        return "tight"
    return "over"


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
                net_days=4.5,
            )
        )
    spans: list[MonthSpan] = []
    for w in weeks:
        if spans and spans[-1].label == w.month_label:
            spans[-1].span += 1
        else:
            spans.append(MonthSpan(label=w.month_label, span=1))
    return weeks, spans


def _cells(week_keys: list[str], values: list[float]) -> list[GridCell]:
    return [
        GridCell(week_key=k, value=v) for k, v in zip(week_keys, values, strict=True)
    ]


def _role_short(name: str) -> str:
    if not name:
        return "—"
    words = name.split()
    if len(words) >= 2:  # noqa: PLR2004
        return "".join(w[0] for w in words[:3]).upper()
    return name[:3].upper()


def _absence_days_for_week(absences: list, week_start: datetime.date) -> float:
    week_end = week_start + datetime.timedelta(days=4)  # Friday
    total = 0.0
    for a in absences:
        if not (a.start_date and a.end_date):
            continue
        overlap_start = max(a.start_date, week_start)
        overlap_end = min(a.end_date, week_end)
        if overlap_start > overlap_end:
            continue
        # Count Mon-Fri days in the overlap
        day = overlap_start
        while day <= overlap_end:
            if day.weekday() < _WORK_DAYS_PER_WEEK:  # 0=Mon, 4=Fri
                total += 1.0
            day += datetime.timedelta(days=1)
    return total


def _build_employees_from_real(
    real_employees: list,
    weeks: list[WeekColumn],
) -> list[EmployeeBlock]:
    keys = [w.key for w in weeks]
    week_starts = [datetime.date(*(int(p) for p in w.key.split("_"))) for w in weeks]
    blocks: list[EmployeeBlock] = []
    for emp in real_employees:
        role_badges: list[RoleBadge] = []
        for rn in emp.role_names:
            short = _role_short(rn)
            color = ROLE_PALETTE.get(short, "var(--mantine-color-gray-2)")
            role_badges.append(RoleBadge(code=short, full=rn, color=color))
        role_name = emp.role_names[0] if emp.role_names else ""
        role_short = _role_short(role_name)
        role_color = ROLE_PALETTE.get(role_short, "var(--mantine-color-gray-2)")
        emp_id_str = f"emp-{emp.id}"
        absence_vals = [_absence_days_for_week(emp.absences, ws) for ws in week_starts]
        blocks.append(
            EmployeeBlock(
                id=emp_id_str,
                real_id=int(emp.id),
                name=f"{emp.first_name} {emp.last_name}".strip(),
                initials=(f"{emp.first_name[:1]}{emp.last_name[:1]}".upper() or "?"),
                job_title=emp.job_title or "",
                role=role_short,
                role_color=role_color,
                role_full=role_name,
                roles=role_badges,
                role_ids=list(emp.role_ids) if emp.role_ids else [],
                projects=[],
                absence=AbsenceRow(cells=_cells(keys, absence_vals)),
                gesamt=[],
                heat=[],
            )
        )
    return blocks


def _week_key_for_date(d: datetime.date) -> str:
    """Return canonical 'YYYY_MM_DD' key for a week's start date."""
    return f"{d.year}_{d.month:02d}_{d.day:02d}"


def _merge_capacity_assignments(
    capacity_assignments: list[Any],
    projects_lookup: dict[int, Any],
    grouped: dict[int, dict[int, dict[str, float]]],
    role_lookup: dict[tuple[int, int], str],
) -> None:
    """Populate grouped and role_lookup from capacity assignments."""
    for cap in capacity_assignments:
        emp_id = cap.employee_id
        proj_id = cap.project_id
        if proj_id not in projects_lookup:
            continue
        grouped.setdefault(emp_id, {}).setdefault(proj_id, {})
        role_name = cap.role_name
        if role_name:
            role_lookup[(emp_id, proj_id)] = role_name


def _apply_allocations(
    blocks: list[EmployeeBlock],
    allocations: list[Any],
    projects_lookup: dict[int, Any],
    week_keys: list[str],
    capacity_assignments: list[Any] | None = None,
) -> None:
    """Replace dummy projects with allocation-derived ones for each affected employee.

    Allocations are grouped per (employee_id, project_id). Employees with no
    allocations keep their dummy data so the demo still shows full grid.

    If capacity_assignments are provided, also add empty rows for projects
    assigned via CapacityEntity that have no allocation data yet.
    """
    grouped: dict[int, dict[int, dict[str, float]]] = {}
    role_lookup: dict[tuple[int, int], str] = {}
    for a in allocations:
        wk = _week_key_for_date(a.week_start)
        if wk not in week_keys:
            continue
        grouped.setdefault(a.employee_id, {}).setdefault(a.project_id, {})[wk] = (
            a.person_days
        )
        # Track role from allocation if not already set
        if (a.employee_id, a.project_id) not in role_lookup:
            role_name = getattr(a, "_cached_role_name", "")
            if role_name:
                role_lookup[(a.employee_id, a.project_id)] = role_name

    _merge_capacity_assignments(
        capacity_assignments or [], projects_lookup, grouped, role_lookup
    )

    if not grouped:
        return
    for block in blocks:
        emp_alloc = grouped.get(block.real_id)
        if not emp_alloc:
            continue
        new_rows: list[ProjectAllocationRow] = []
        for proj_id, week_map in emp_alloc.items():
            proj = projects_lookup.get(proj_id)
            if proj is None:
                continue
            color = proj.color or "var(--mantine-color-gray-5)"
            code = proj.code or (proj.name_de[:8].upper() if proj.name_de else "—")
            cells = [
                GridCell(
                    key=f"{block.id}|{code}|{wk}",
                    week_key=wk,
                    value=float(week_map.get(wk, 0.0)),
                )
                for wk in week_keys
            ]
            r_name = role_lookup.get((block.real_id, proj_id), "")
            r_short = _role_short(r_name)
            r_color = ROLE_PALETTE.get(r_short, "var(--mantine-color-gray-2)")
            new_rows.append(
                ProjectAllocationRow(
                    project_id=str(proj_id),
                    real_project_id=int(proj_id),
                    emp_id=block.id,
                    code=code,
                    name=proj.name_de or "—",
                    color=color,
                    role_name=r_name,
                    role_short=r_short,
                    role_color=r_color,
                    cells=cells,
                )
            )
        if new_rows:
            block.projects = new_rows


def _compute_gesamt(weeks: list[WeekColumn], block: EmployeeBlock) -> list[GesamtCell]:
    cells: list[GesamtCell] = []
    for idx, week in enumerate(weeks):
        used = sum(p.cells[idx].value for p in block.projects)
        absence = block.absence.cells[idx].value if block.absence.cells else 0.0
        absent = absence > 0
        free = week.net_days - used - absence
        bucket = "absent" if absent else _gesamt_bucket(free)
        cells.append(GesamtCell(week_key=week.key, value=free, bucket=bucket))
    return cells


def _compute_heat(weeks: list[WeekColumn], block: EmployeeBlock) -> list[HeatCell]:
    cells: list[HeatCell] = []
    for idx, week in enumerate(weeks):
        used = sum(p.cells[idx].value for p in block.projects)
        absence = block.absence.cells[idx].value if block.absence.cells else 0.0
        fully_absent = absence >= float(_WORK_DAYS_PER_WEEK)
        # For partial absences, reduce available net_days by absence days
        available = max(0.0, week.net_days - absence)
        if fully_absent:
            pct = round((used / week.net_days) * 100) if week.net_days > 0 else 0
            bucket = "absent"
        elif available > 0:
            pct = round((used / available) * 100)
            bucket = _heat_bucket(pct)
        else:
            pct = 0
            bucket = "low"
        cells.append(
            HeatCell(
                week_key=week.key, percent=pct, is_absent=fully_absent, bucket=bucket
            )
        )
    return cells


_FOCUS_GRID_SCRIPT = (
    "setTimeout(() => "
    "document.getElementById('planning-grid-root')?.focus({preventScroll:true}), 0)"
)

# Scroll the active cell into view only when it is outside the visible area of
# the grid wrapper.  Uses scrollIntoViewIfNeeded (Chrome/Safari) with a manual
# fallback for Firefox so that the viewport never jumps unnecessarily.
_SCROLL_ACTIVE_INTO_VIEW_SCRIPT = (
    "setTimeout(() => {"
    "const root = document.getElementById('planning-grid-root');"
    "if (!root) return;"
    "const active = root.querySelector('[data-active-cell=\"true\"]');"
    "if (!active) return;"
    "if (active.scrollIntoViewIfNeeded) {"
    "  active.scrollIntoViewIfNeeded(false);"
    "} else {"
    "  const rr = root.getBoundingClientRect();"
    "  const ar = active.getBoundingClientRect();"
    "  if (ar.bottom > rr.bottom) root.scrollTop += ar.bottom - rr.bottom;"
    "  else if (ar.top < rr.top) root.scrollTop -= rr.top - ar.top;"
    "  if (ar.right > rr.right) root.scrollLeft += ar.right - rr.right;"
    "  else if (ar.left < rr.left) root.scrollLeft -= rr.left - ar.left;"
    "}"
    "}, 0)"
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
    "document.getElementById('planning-grid-root')?.focus({preventScroll:true}), 0);"
)


def _format_de(value: float) -> str:
    """Format a float as German decimal string ('1,5')."""
    if value == int(value):
        return f"{int(value)}"
    return f"{value:.1f}".replace(".", ",")


def _parse_de(text: str) -> float | None:
    """Parse 'german or dot' decimal string to non-negative float; None on bad input."""
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


class PlanningGridState(rx.State):
    """Planning grid state — Stage B (editable dummy data)."""

    weeks: list[WeekColumn] = []
    month_spans: list[MonthSpan] = []
    employees: list[EmployeeBlock] = []
    is_loaded: bool = False

    active_cell: str = ""
    editing_cell: str = ""
    draft_value: str = ""
    edit_version: int = 0  # bumps to force input remount on cell change

    collapsed_employees: list[str] = []

    @rx.var(cache=True)
    def table_width(self) -> str:
        return f"{LABEL_COL_PX + len(self.weeks) * WEEK_COL_PX}px"

    @rx.var(cache=True)
    def grid_template_columns(self) -> str:
        return f"{LABEL_COL_PX}px repeat({len(self.weeks)}, {WEEK_COL_PX}px)"

    @rx.var(cache=True)
    def avg_heat(self) -> list[HeatCell]:
        if not self.employees or not self.weeks:
            return []
        result: list[HeatCell] = []
        for idx, week in enumerate(self.weeks):
            percents = [
                emp.heat[idx].percent for emp in self.employees if idx < len(emp.heat)
            ]
            avg_pct = round(sum(percents) / len(percents)) if percents else 0
            result.append(
                HeatCell(
                    week_key=week.key,
                    percent=avg_pct,
                    is_absent=False,
                    bucket=_heat_bucket(avg_pct),
                )
            )
        return result

    def _populate(
        self,
        weeks: list[WeekColumn],
        spans: list[MonthSpan],
        employees: list[EmployeeBlock],
    ) -> None:
        for block in employees:
            if not block.role_full:
                block.role_full = ROLE_FULL.get(block.role, block.role)
            block.gesamt = _compute_gesamt(weeks, block)
            block.heat = _compute_heat(weeks, block)
        self.weeks = weeks
        self.month_spans = spans
        self.employees = employees
        self.is_loaded = True
        if employees and employees[0].projects and employees[0].projects[0].cells:
            self.active_cell = employees[0].projects[0].cells[0].key
        else:
            self.active_cell = ""
        self.editing_cell = ""
        self.draft_value = ""

    def _load_real(
        self,
        num_weeks: int,
        real_emps: list,
        real_projs: list,
        allocations: list[Any],
        capacity_assignments: list[Any] | None = None,
    ) -> None:
        weeks, spans = _build_weeks(num_weeks)
        employees = _build_employees_from_real(real_emps, weeks)
        projects_lookup = {int(p.id): p for p in real_projs}
        _apply_allocations(
            employees,
            allocations,
            projects_lookup,
            [w.key for w in weeks],
            capacity_assignments=capacity_assignments,
        )
        for block in employees:
            for proj in block.projects:
                for cell in proj.cells:
                    cell.key = f"{block.id}|{proj.code}|{cell.week_key}"
        self._populate(weeks, spans, employees)

    async def _fetch_allocations(self, weeks: list[WeekColumn]) -> list[Any]:
        if not weeks:
            return []
        first = datetime.date(*(int(p) for p in weeks[0].key.split("_")))
        last = datetime.date(*(int(p) for p in weeks[-1].key.split("_")))
        async with get_asyncdb_session() as session:
            results = await capacity_allocation_repo.find_in_range(session, first, last)
            # Cache role name before expunging to avoid DetachedInstanceError
            for r in results:
                r._cached_role_name = r.role.name if r.role else ""  # noqa: SLF001
                session.expunge(r)
            return results

    async def _fetch_capacity_assignments(self) -> list[Any]:
        """Fetch all CapacityEntity records as lightweight dicts."""
        async with get_asyncdb_session() as session:
            from alloq_commons.entities.capacity import CapacityEntity  # noqa: PLC0415
            from sqlmodel import select  # noqa: PLC0415

            result = await session.execute(select(CapacityEntity))
            entities = list(result.scalars().unique().all())
            # Extract data while still in session to avoid DetachedInstanceError
            return [
                _CapAssignment(
                    employee_id=e.employee_id,
                    project_id=e.project_id,
                    role_name=e.role.name if e.role else "",
                )
                for e in entities
            ]

    @rx.event
    async def load_grid_data(self) -> None:
        from alloq_project.states.planning_state import PlanningState  # noqa: PLC0415

        planning = await self.get_state(PlanningState)
        n = TIME_RANGE_WEEKS.get(planning.time_range, TIME_RANGE_WEEKS["3 Monate"])
        weeks, _spans = _build_weeks(n)
        allocations = await self._fetch_allocations(weeks)
        assignments = await self._fetch_capacity_assignments()
        self._load_real(
            n,
            planning.available_employees,
            planning.available_projects,
            allocations,
            capacity_assignments=assignments,
        )

    @rx.event
    async def reload_with_time_range(self, time_range: str) -> None:
        from alloq_project.states.planning_state import PlanningState  # noqa: PLC0415

        n = TIME_RANGE_WEEKS.get(time_range, TIME_RANGE_WEEKS["3 Monate"])
        planning = await self.get_state(PlanningState)
        weeks, _spans = _build_weeks(n)
        allocations = await self._fetch_allocations(weeks)
        assignments = await self._fetch_capacity_assignments()
        self._load_real(
            n,
            planning.available_employees,
            planning.available_projects,
            allocations,
            capacity_assignments=assignments,
        )

    @rx.event
    def toggle_employee(self, emp_id: str) -> None:
        if emp_id in self.collapsed_employees:
            self.collapsed_employees = [
                e for e in self.collapsed_employees if e != emp_id
            ]
        else:
            self.collapsed_employees = [*self.collapsed_employees, emp_id]

    @rx.event
    def set_active(self, cell_key: str) -> Any:
        self.active_cell = cell_key
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def move_active(self, direction: str) -> None:
        if self.editing_cell:
            return
        if not self.active_cell:
            return
        nxt = self._navigate(self.active_cell, direction)
        if nxt:
            self.active_cell = nxt

    @rx.event
    def start_edit(self, cell_key: str) -> Any:
        cur = self._lookup_value(cell_key)
        self.draft_value = "" if cur == 0 else _format_de(cur)
        self.active_cell = cell_key
        self.editing_cell = cell_key
        self.edit_version += 1
        return rx.call_script(_FOCUS_EDITOR_SCRIPT)

    @rx.event
    def set_draft(self, value: str) -> None:
        self.draft_value = value

    @rx.event
    def cancel_edit(self) -> Any:
        self.editing_cell = ""
        self.draft_value = ""
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def commit_edit(self) -> None:
        self._commit_current()
        self.editing_cell = ""
        self.draft_value = ""

    @rx.event
    def commit_and_select_next(self, direction: str) -> Any:
        """Commit current edit, move active to next cell, exit edit mode."""
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
        """Commit current edit, move edit to next cell (Tab behavior)."""
        cur = self.editing_cell
        if not cur:
            return None
        self._commit_current()
        next_key = self._navigate(cur, direction)
        if next_key:
            cur_val = self._lookup_value(next_key)
            self.draft_value = "" if cur_val == 0 else _format_de(cur_val)
            self.active_cell = next_key
            self.editing_cell = next_key
            self.edit_version += 1
            return rx.call_script(_FOCUS_EDITOR_SCRIPT)
        self.editing_cell = ""
        self.draft_value = ""
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def handle_key(self, key: str) -> Any:
        """Editor input on_key_down."""
        if key == "Enter":
            return rx.call_script(_BLUR_EDITOR_SCRIPT)
        if key == "Escape":
            return self.cancel_edit()
        if key == "Tab":
            return self.commit_and_move("next")
        return None

    @rx.event
    def handle_grid_key(self, key: str) -> Any:
        """Grid wrapper on_key_down. Only acts when not editing."""
        if self.editing_cell:
            return None
        if not self.active_cell:
            return None
        nav_keys = ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight")
        edit_keys = ("Enter", "F2")
        if key not in nav_keys and key not in edit_keys:
            return None
        if key == "ArrowUp":
            self.move_active("up")
        elif key == "ArrowDown":
            self.move_active("down")
        elif key == "ArrowLeft":
            self.move_active("prev")
        elif key == "ArrowRight":
            self.move_active("next")
        elif key in edit_keys:
            return self.start_edit(self.active_cell)
        return rx.prevent_default

    def _commit_current(self) -> None:
        cur = self.editing_cell
        if not cur:
            return
        new_val = _parse_de(self.draft_value)
        if new_val is None:
            return
        emp_id, proj_code, week_key = cur.split("|")
        cur_val = self._lookup_value(cur)
        if new_val == cur_val:
            return
        for emp in self.employees:
            if emp.id != emp_id:
                continue
            for proj in emp.projects:
                if proj.code != proj_code:
                    continue
                for cell in proj.cells:
                    if cell.week_key == week_key:
                        cell.value = new_val
                        cell.is_dirty = True
                        break
            emp.gesamt = _compute_gesamt(self.weeks, emp)
            emp.heat = _compute_heat(self.weeks, emp)
        self.employees = list(self.employees)

    def _lookup_value(self, cell_key: str) -> float:
        try:
            emp_id, proj_code, week_key = cell_key.split("|")
        except ValueError:
            return 0.0
        for emp in self.employees:
            if emp.id != emp_id:
                continue
            for proj in emp.projects:
                if proj.code != proj_code:
                    continue
                for cell in proj.cells:
                    if cell.week_key == week_key:
                        return cell.value
        return 0.0

    def _collect_dirty(
        self,
    ) -> list[tuple[int, int, int, datetime.date, float, EmployeeBlock, GridCell]]:
        out: list[
            tuple[int, int, int, datetime.date, float, EmployeeBlock, GridCell]
        ] = []
        for emp in self.employees:
            if not emp.real_id or not emp.role_ids:
                continue
            role_id = emp.role_ids[0]
            for proj in emp.projects:
                if not proj.real_project_id:
                    continue
                for cell in proj.cells:
                    if not cell.is_dirty:
                        continue
                    try:
                        y, m, d = (int(p) for p in cell.week_key.split("_"))
                        wk = datetime.date(y, m, d)
                    except ValueError:
                        continue
                    out.append(
                        (
                            emp.real_id,
                            proj.real_project_id,
                            role_id,
                            wk,
                            float(cell.value),
                            emp,
                            cell,
                        )
                    )
        return out

    @rx.var(cache=True)
    def has_dirty(self) -> bool:
        return any(
            cell.is_dirty
            for emp in self.employees
            for proj in emp.projects
            for cell in proj.cells
        )

    @rx.event
    async def save_grid(self) -> AsyncGenerator[Any, None]:
        """Persist edited grid cells to capacity_allocations."""
        dirty = self._collect_dirty()
        if not dirty:
            yield rx.toast.info("Keine Änderungen.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                for emp_id, proj_id, role_id, wk, pd, _emp, _cell in dirty:
                    await capacity_allocation_repo.upsert_cell(
                        session, proj_id, emp_id, role_id, wk, pd
                    )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to save grid: %s", exc)
            yield rx.toast.error(
                f"Speichern fehlgeschlagen: {exc}", position="top-right"
            )
            return
        for *_unused, cell in dirty:
            cell.is_dirty = False
        self.employees = list(self.employees)
        yield rx.toast.success(
            f"{len(dirty)} Zellen gespeichert.", position="top-right"
        )

    def _navigate(self, cur_key: str, direction: str) -> str:  # noqa: PLR0911
        try:
            emp_id, proj_code, week_key = cur_key.split("|")
        except ValueError:
            return ""
        week_keys = [w.key for w in self.weeks]
        rows: list[tuple[str, str]] = [
            (emp.id, proj.code)
            for emp in self.employees
            if emp.id not in self.collapsed_employees
            for proj in emp.projects
        ]
        if not rows:
            return ""
        try:
            week_idx = week_keys.index(week_key)
            row_idx = rows.index((emp_id, proj_code))
        except ValueError:
            return ""
        if direction == "next" and week_idx + 1 < len(week_keys):
            return f"{emp_id}|{proj_code}|{week_keys[week_idx + 1]}"
        if direction == "prev" and week_idx > 0:
            return f"{emp_id}|{proj_code}|{week_keys[week_idx - 1]}"
        if direction == "down" and row_idx + 1 < len(rows):
            ne, np = rows[row_idx + 1]
            return f"{ne}|{np}|{week_key}"
        if direction == "up" and row_idx > 0:
            ne, np = rows[row_idx - 1]
            return f"{ne}|{np}|{week_key}"
        return ""

    # --- Add / Remove project from employee in grid ---

    add_project_emp_id: str = ""
    add_project_options: list[dict[str, str]] = []
    add_project_role_options: list[dict[str, str]] = []

    @rx.event
    async def open_add_project_for_employee(self, emp_id: str) -> None:
        """Open the add-project modal for a specific employee."""
        from alloq_project.states.planning_state import PlanningState  # noqa: PLC0415

        self.add_project_emp_id = emp_id
        emp = next((e for e in self.employees if e.id == emp_id), None)
        if not emp:
            return

        planning = await self.get_state(PlanningState)
        assigned_codes = {p.code for p in emp.projects}
        self.add_project_options = [
            {"value": str(p.id), "label": f"{p.code} - {p.name_de}"}
            for p in planning.available_projects
            if p.code not in assigned_codes
        ]
        emp_role_ids = set(emp.role_ids)
        self.add_project_role_options = [
            {"value": str(r.id), "label": r.name}
            for r in planning.available_roles
            if r.id in emp_role_ids
        ]

    def close_add_project_for_employee(self) -> None:
        """Close the add-project modal."""
        self.add_project_emp_id = ""
        self.add_project_options = []
        self.add_project_role_options = []

    @rx.event
    async def add_project_to_employee_grid(
        self, form_data: dict
    ) -> AsyncGenerator[Any, None]:
        """Assign a project to an employee and reload grid."""
        from alloq_commons.entities.capacity import CapacityEntity  # noqa: PLC0415
        from alloq_project.states.planning_state import PlanningState  # noqa: PLC0415

        project_id_raw = form_data.get("project_id")
        role_id_raw = form_data.get("role_id")
        if not project_id_raw or not role_id_raw:
            yield rx.toast.error(
                "Bitte Projekt und Rolle auswählen.", position="top-right"
            )
            return

        project_id = int(project_id_raw)
        role_id = int(role_id_raw)

        emp = next((e for e in self.employees if e.id == self.add_project_emp_id), None)
        if not emp:
            yield rx.toast.error("Mitarbeiter nicht gefunden.", position="top-right")
            return

        planning = await self.get_state(PlanningState)
        project = next(
            (p for p in planning.available_projects if p.id == project_id), None
        )
        if not project or not project.start_date or not project.end_date:
            yield rx.toast.error("Projekt nicht gefunden.", position="top-right")
            return

        try:
            async with get_asyncdb_session() as session:
                entity = CapacityEntity(
                    project_id=project_id,
                    employee_id=emp.real_id,
                    role_id=role_id,
                    start_date=project.start_date,
                    end_date=project.end_date,
                    hours_per_week=40.0,
                )
                session.add(entity)
                await session.commit()
            self.add_project_emp_id = ""
            yield PlanningGridState.load_grid_data
        except Exception as e:
            log.error("Failed to add project to employee in grid: %s", e)
            yield rx.toast.error(f"Fehler: {e}", position="top-right")

    @rx.event
    async def remove_project_from_employee_grid(
        self, emp_id: str, project_id: int
    ) -> AsyncGenerator[Any, None]:
        """Remove a project assignment and all allocations for an employee."""
        from alloq_commons.repositories import (  # noqa: PLC0415
            capacity_allocation_repo,
            capacity_repo,
        )

        emp = next((e for e in self.employees if e.id == emp_id), None)
        if not emp:
            yield rx.toast.error("Mitarbeiter nicht gefunden.", position="top-right")
            return

        try:
            async with get_asyncdb_session() as session:
                # Delete capacity assignment (may not exist for allocation-only rows)
                await capacity_repo.delete_by_project_and_employee(
                    session, project_id, emp.real_id
                )
                # Delete all weekly allocation rows for this pair
                deleted_alloc = (
                    await capacity_allocation_repo.delete_by_project_and_employee(
                        session, project_id, emp.real_id
                    )
                )
            if not deleted_alloc:
                log.debug(
                    "No allocation rows found for project %d, employee %d",
                    project_id,
                    emp.real_id,
                )
            yield PlanningGridState.load_grid_data
            yield rx.toast.info("Projektzuweisung entfernt.", position="top-right")
        except Exception as e:
            log.error("Failed to remove project from employee in grid: %s", e)
            yield rx.toast.error(f"Fehler: {e}", position="top-right")
