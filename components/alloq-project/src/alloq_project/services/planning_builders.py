"""Pure builders that turn planning entities into grid/pivot data."""

from __future__ import annotations

import datetime
import math
from typing import Any

from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_commons.services.utilization import (
    UtilizationAllocationInput,
    UtilizationService,
)

from alloq_project.states.planning_models import (
    WEEKS_BEFORE_CURRENT,
    EmployeeBlock,
    GesamtCell,
    HeatCell,
    MonthSpan,
    ProjectBlock,
    ProjectGesamtCell,
    RoleTotal,
    WeekColumn,
)

WORK_DAYS_PER_WEEK: int = 5


def anchor_date() -> datetime.date:
    """Rolling anchor: Monday of (current week - WEEKS_BEFORE_CURRENT)."""
    today = datetime.date.today()  # noqa: DTZ011
    monday = today - datetime.timedelta(days=today.weekday())
    return monday - datetime.timedelta(weeks=WEEKS_BEFORE_CURRENT)


def current_week_key() -> str:
    """Week key of the Monday of the current week (same clock as the anchor)."""
    monday = anchor_date() + datetime.timedelta(weeks=WEEKS_BEFORE_CURRENT)
    return week_key_for_date(monday)


def employee_id_by_email(employees: list[Employee], email: str) -> int | None:
    """Id of the employee whose email matches (case-insensitive), if any."""
    wanted = email.strip().casefold()
    if not wanted:
        return None
    return next(
        (e.id for e in employees if (e.email or "").strip().casefold() == wanted),
        None,
    )


def owned_project_ids(projects: list[Project], employee_id: int | None) -> set[str]:
    """Ids (as str) of projects the employee is an owner of."""
    if employee_id is None:
        return set()
    return {str(p.id) for p in projects if employee_id in p.owner_ids}


def managed_employee_ids(employees: list[Employee], manager_id: int | None) -> set[str]:
    """Ids (as str) of employees reporting to the given manager."""
    if manager_id is None:
        return set()
    return {str(e.id) for e in employees if e.manager_id == manager_id}


def sorted_projects(projects: list[Project]) -> list[Project]:
    """Sort projects by display name, case-insensitive."""
    return sorted(projects, key=lambda p: (p.name_de or p.code).lower())


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


class CapAssignment:
    """Lightweight transport for CapacityEntity rows (avoids detached ORM)."""

    __slots__ = ("employee_id", "project_id", "role_id", "role_name")

    def __init__(
        self, employee_id: int, project_id: int, role_id: int | None, role_name: str
    ) -> None:
        self.employee_id = employee_id
        self.project_id = project_id
        self.role_id = role_id
        self.role_name = role_name


# === Pure helpers ===


def project_heat_bucket(allocated: float) -> str:
    return UtilizationService.project_heat_bucket(allocated)


def build_weeks(
    num_weeks: int,
    holiday_dates: set[datetime.date] | None = None,
) -> tuple[list[WeekColumn], list[MonthSpan]]:
    holidays = holiday_dates or set()
    weeks: list[WeekColumn] = []
    anchor = anchor_date()
    for i in range(num_weeks):
        d = anchor + datetime.timedelta(days=7 * i)
        work_days = UtilizationService.work_days_for_week(
            d, holidays, workload_percent=100, base_work_days=float(WORK_DAYS_PER_WEEK)
        )
        weeks.append(
            WeekColumn(
                key=f"{d.year}_{d.month:02d}_{d.day:02d}",
                label=f"{d.day}.{d.month}.",
                week_no=d.isocalendar().week,
                month_label=f"{GERMAN_MONTHS[d.month - 1]} {d.year % 100}",
                work_days=work_days,
            )
        )
    spans: list[MonthSpan] = []
    for w in weeks:
        if spans and spans[-1].label == w.month_label:
            spans[-1].span += 1
        else:
            spans.append(MonthSpan(label=w.month_label, span=1))
    return weeks, spans


def week_key_for_date(d: datetime.date) -> str:
    return f"{d.year}_{d.month:02d}_{d.day:02d}"


def role_short(name: str) -> str:
    if not name:
        return "—"
    words = name.split()
    if len(words) >= 2:  # noqa: PLR2004
        return "".join(w[0] for w in words[:3]).upper()
    return name[:3].upper()


def absence_days_for_week(absences: list, week_start: datetime.date) -> float:
    dated = [a for a in absences if a.start_date and a.end_date]
    return UtilizationService.absence_days_in_week(dated, week_start)


def cell_key(emp_id: str, proj_code: str, wk_key: str) -> str:
    """Canonical cell key."""
    return f"{emp_id}|{proj_code}|{wk_key}"


def split_cell_key(key: str) -> tuple[str, str, str] | None:
    """Split a cell key into (emp_id, project_code, week_key).

    Employee ids and week keys never contain ``|``, project codes may, so the
    code is everything between the first and the last separator.
    """
    first, sep, rest = key.partition("|")
    code, sep2, week = rest.rpartition("|")
    if not (sep and sep2 and first and code and week):
        return None
    return first, code, week


def parse_cell_changes(
    changes: list[dict[str, Any]],
    editable_rows: set[tuple[str, str]],
    week_keys: set[str],
) -> tuple[dict[str, float], int]:
    """Validate a batch of client cell edits.

    Returns the accepted ``{cell_key: value}`` updates and the number of
    rejected changes (unknown row/week, malformed key, non-finite or
    negative value). Values are rounded to two decimals.
    """
    updates: dict[str, float] = {}
    rejected = 0
    for change in changes:
        key = change.get("key") if isinstance(change, dict) else None
        value = change.get("value") if isinstance(change, dict) else None
        parts = split_cell_key(key) if isinstance(key, str) else None
        if (
            parts is None
            or not isinstance(key, str)
            or (parts[0], parts[1]) not in editable_rows
            or parts[2] not in week_keys
            or isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value < 0
        ):
            rejected += 1
            continue
        updates[key] = round(float(value), 2)
    return updates, rejected


def split_edits(
    edits: dict[str, float],
    editable_rows: set[tuple[str, str]],
    week_keys: set[str],
) -> tuple[dict[str, float], dict[str, float]]:
    """Split unsaved edits into those shown in the loaded grid and the rest."""
    visible: dict[str, float] = {}
    hidden: dict[str, float] = {}
    for key, value in edits.items():
        parts = split_cell_key(key)
        shown = (
            parts is not None
            and (parts[0], parts[1]) in editable_rows
            and parts[2] in week_keys
        )
        (visible if shown else hidden)[key] = value
    return visible, hidden


def edits_to_rows(
    edits: dict[str, float],
    project_meta: list[dict[str, Any]],
    employee_meta: list[dict[str, Any]],
    role_ids: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """Map unsaved edits to allocation rows by cell key.

    ``role_ids`` holds the role per cell key (the stored row the cell shows)
    and per ``"{emp_id}|{project_id}"`` pair; the cell role wins, so editing a
    cell updates that row instead of adding a second role's row for the week.
    The employee's first role is the last fallback. Edits that cannot be
    mapped (unknown row, no role, malformed key) are left out.
    """
    proj_code_to_real = {p["code"]: p["real_id"] for p in project_meta}
    emp_id_to_real = {e["id"]: e["real_id"] for e in employee_meta}
    emp_role_id = {
        e["id"]: e["role_ids"][0] for e in employee_meta if e.get("role_ids")
    }
    rows: dict[str, dict[str, Any]] = {}
    for key, value in edits.items():
        parts = split_cell_key(key)
        if parts is None:
            continue
        emp_id, proj_code, wk_key = parts
        real_eid = emp_id_to_real.get(emp_id)
        real_pid = proj_code_to_real.get(proj_code)
        role_id = (
            role_ids.get(key)
            or role_ids.get(f"{emp_id}|{real_pid}")
            or emp_role_id.get(emp_id)
        )
        if not real_eid or not real_pid or not role_id:
            continue
        try:
            week = datetime.date(*(int(p) for p in wk_key.split("_")))
        except TypeError, ValueError:
            continue
        rows[key] = {
            "employee_id": real_eid,
            "project_id": real_pid,
            "role_id": role_id,
            "week_start": week,
            "person_days": float(value),
        }
    return rows


def dirty_keys_for(cells: dict[str, float], saved: dict[str, float]) -> list[str]:
    """Keys whose current value differs from the last loaded/saved snapshot."""
    return sorted(key for key, value in cells.items() if value != saved.get(key, 0.0))


def scaled_work_days(week: WeekColumn, workload_percent: int) -> float:
    """Apply workload percentage to a week's holiday-adjusted work days."""
    return UtilizationService.apply_workload(week.work_days, workload_percent)


def compute_gesamt(weeks: list[WeekColumn], block: EmployeeBlock) -> list[GesamtCell]:
    cells: list[GesamtCell] = []
    for idx, week in enumerate(weeks):
        used = sum(p.cells[idx].value for p in block.projects)
        absence = block.absence.cells[idx].value if block.absence.cells else 0.0
        internal = block.internal.cells[idx].value if block.internal.cells else 0.0
        result = UtilizationService.compute_employee_gesamt(
            used_days=used,
            absence_days=absence,
            internal_days=internal,
            work_days=scaled_work_days(week, block.workload_percent),
        )
        cells.append(
            GesamtCell(week_key=week.key, value=result.free_days, bucket=result.bucket)
        )
    return cells


def compute_heat(weeks: list[WeekColumn], block: EmployeeBlock) -> list[HeatCell]:
    cells: list[HeatCell] = []
    for idx, week in enumerate(weeks):
        used = sum(p.cells[idx].value for p in block.projects)
        absence = block.absence.cells[idx].value if block.absence.cells else 0.0
        internal = block.internal.cells[idx].value if block.internal.cells else 0.0
        result = UtilizationService.compute_employee_heat(
            used_days=used,
            absence_days=absence,
            internal_days=internal,
            work_days=scaled_work_days(week, block.workload_percent),
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


def compute_project_gesamt(
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


def compute_project_heat(
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


def employee_summary(block: EmployeeBlock, from_key: str) -> tuple[float, float]:
    """Planned and available person-days from ``from_key`` onward.

    Planned sums all project cells; available sums the free days of weeks
    that still have capacity (overbooked weeks count as zero).
    """
    planned = sum(
        cell.value
        for project in block.projects
        for cell in project.cells
        if cell.week_key >= from_key
    )
    available = sum(
        max(cell.value, 0.0) for cell in block.gesamt if cell.week_key >= from_key
    )
    return round(planned, 2), round(available, 2)


def filter_project_blocks(
    blocks: list[ProjectBlock],
    weeks: list[WeekColumn],
    from_key: str,
    *,
    project_ids: list[str],
    role_ids: list[str],
    employee_ids: list[str],
    role_id_lookup: dict[str, int],
    available_employee_ids: set[str] | None = None,
) -> list[ProjectBlock]:
    """Filter projects and rebuild totals when availability limits their rows."""
    result = blocks
    if available_employee_ids is not None:
        result = []
        for block in blocks:
            employees = [
                employee
                for employee in block.employees
                if employee.emp_id in available_employee_ids
            ]
            if not employees:
                continue
            filtered = block.model_copy(update={"employees": employees})
            filtered.gesamt = compute_project_gesamt(weeks, filtered)
            filtered.heat = compute_project_heat(weeks, filtered)
            filtered.planned_days, filtered.role_totals = project_summary(
                filtered, from_key
            )
            result.append(filtered)
    if project_ids:
        result = [p for p in result if str(p.real_id) in project_ids]
    if role_ids:
        result = [
            p
            for p in result
            if any(
                str(role_id_lookup.get(f"{e.emp_id}|{p.real_id}")) in role_ids
                for e in p.employees
            )
        ]
    if employee_ids:
        result = [
            p
            for p in result
            if any(str(e.real_id) in employee_ids for e in p.employees)
        ]
    return result


def project_summary(
    block: ProjectBlock, from_key: str
) -> tuple[float, list[RoleTotal]]:
    """Planned person-days from ``from_key`` onward, in total and per role."""
    totals: dict[tuple[str, str], RoleTotal] = {}
    for emp in block.employees:
        days = sum(c.value for c in emp.cells if c.week_key >= from_key)
        entry = totals.setdefault(
            (emp.role_short, emp.role_name),
            RoleTotal(code=emp.role_short, color=emp.role_color),
        )
        entry.days += days
    roles = [
        RoleTotal(code=totals[k].code, color=totals[k].color, days=round(r.days, 2))
        for k, r in sorted(totals.items())
        if round(r.days, 2) > 0
    ]
    return round(sum(r.days for r in totals.values()), 2), roles


# === Population helpers ===


def build_employee_meta(
    available_employees: list,
    wks: list[str],
    role_abbrev_by_name: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[float]]]:
    _abbrev = role_abbrev_by_name or {}

    def _abbrev_for(name: str) -> str:
        return _abbrev.get(name) or role_short(name)

    week_starts = [datetime.date(*(int(p) for p in k.split("_"))) for k in wks]
    emp_meta: list[dict[str, Any]] = []
    absence_map: dict[str, list[float]] = {}
    for emp in available_employees:
        eid = f"emp-{emp.id}"
        absence_map[eid] = [
            absence_days_for_week(emp.absences, ws) for ws in week_starts
        ]
        role_badges = [
            {
                "code": _abbrev_for(rn),
                "full": rn,
                "color": ROLE_PALETTE.get(
                    _abbrev_for(rn), "var(--mantine-color-gray-2)"
                ),
            }
            for rn in emp.role_names
        ]
        primary = emp.role_names[0] if emp.role_names else ""
        primary_short = _abbrev_for(primary)
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
                "hours_per_week": float(getattr(emp, "hours_per_week", 40.0) or 40.0),
                "workload_percent": int(getattr(emp, "workload_percent", 100) or 100),
                "project_ids": [],
            }
        )
    return emp_meta, absence_map


def build_project_meta(
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


def ingest_allocations(
    allocations: list[Any],
    assignments: list[CapAssignment],
    proj_idx: dict[int, dict[str, Any]],
    wk_set: set[str],
) -> tuple[dict[str, float], dict[str, str], dict[str, int], set[tuple[str, int]]]:
    cells: dict[str, float] = {}
    role_lookup: dict[str, str] = {}
    role_id_lookup: dict[str, int] = {}
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
        wk = week_key_for_date(week_start)
        cells[cell_key(eid, proj_idx[project_id]["code"], wk)] = person_days
        pairs.add((eid, project_id))

    for allocation in allocations:
        wk = week_key_for_date(allocation.week_start)
        if wk not in wk_set or allocation.project_id not in proj_idx:
            continue
        eid = f"emp-{allocation.employee_id}"
        pairs.add((eid, allocation.project_id))
        pair_key = f"{eid}|{allocation.project_id}"
        rn = getattr(allocation, "role_name", "")
        if rn:
            role_lookup.setdefault(pair_key, rn)
        if allocation.role_id:
            role_id_lookup.setdefault(pair_key, allocation.role_id)
    for cap in assignments:
        if cap.project_id not in proj_idx:
            continue
        eid = f"emp-{cap.employee_id}"
        pairs.add((eid, cap.project_id))
        pair_key = f"{eid}|{cap.project_id}"
        if cap.role_name:
            role_lookup.setdefault(pair_key, cap.role_name)
        if cap.role_id:
            role_id_lookup.setdefault(pair_key, cap.role_id)
    return cells, role_lookup, role_id_lookup, pairs


def cell_role_ids(
    allocations: list[Any],
    proj_idx: dict[int, dict[str, Any]],
    wk_set: set[str],
) -> dict[str, int]:
    """Role id of the allocation row each visible cell shows.

    Mirrors the heatmap normalization (the last row of an employee, project and
    week wins), so saving a cell updates that row instead of adding another
    role's row for the same week.
    """
    roles: dict[str, int] = {}
    for allocation in allocations:
        wk = week_key_for_date(allocation.week_start)
        if wk not in wk_set or allocation.project_id not in proj_idx:
            continue
        if allocation.role_id:
            code = proj_idx[allocation.project_id]["code"]
            roles[cell_key(f"emp-{allocation.employee_id}", code, wk)] = int(
                allocation.role_id
            )
    return roles


def wire_pairs(
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
