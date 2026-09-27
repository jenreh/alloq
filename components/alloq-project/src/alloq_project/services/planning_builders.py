"""Pure builders that turn planning entities into grid/pivot data."""

from __future__ import annotations

import datetime
import math
from typing import Any

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
    WeekColumn,
)

WORK_DAYS_PER_WEEK: int = 5


def anchor_date() -> datetime.date:
    """Rolling anchor: Monday of (current week - WEEKS_BEFORE_CURRENT)."""
    today = datetime.date.today()  # noqa: DTZ011
    monday = today - datetime.timedelta(days=today.weekday())
    return monday - datetime.timedelta(weeks=WEEKS_BEFORE_CURRENT)


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
            if day.weekday() < WORK_DAYS_PER_WEEK:
                total += 1.0
            day += datetime.timedelta(days=1)
    return total


def cell_key(emp_id: str, proj_code: str, wk_key: str) -> str:
    """Canonical cell key."""
    return f"{emp_id}|{proj_code}|{wk_key}"


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
        parts = key.split("|") if isinstance(key, str) else []
        if (
            len(parts) != 3  # noqa: PLR2004
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
        parts = key.split("|")
        shown = (
            len(parts) == 3  # noqa: PLR2004
            and (parts[0], parts[1]) in editable_rows
            and parts[2] in week_keys
        )
        (visible if shown else hidden)[key] = value
    return visible, hidden


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
        rn = getattr(allocation, "_cached_role_name", "")
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
