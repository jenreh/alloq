"""State for the resource planning Grid view.

Stage B: dummy data with inline editing. Edits are kept in local state
(no persistence). The shapes are designed so real data can replace the
dummy fixture without rewriting the UI.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import reflex as rx
from pydantic import BaseModel

log = logging.getLogger(__name__)


LABEL_COL_PX: int = 300
WEEK_COL_PX: int = 64

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

PROJECT_PALETTE: dict[str, str] = {
    "CRM-AI": "var(--mantine-color-yellow-5)",
    "FRAUD": "var(--mantine-color-orange-6)",
    "GENAI-ASSIST": "var(--mantine-color-teal-7)",
    "NLP-LEGAL": "var(--mantine-color-pink-5)",
    "RECO": "var(--mantine-color-violet-5)",
}

ABSENCE_COLOR = "var(--mantine-color-blue-4)"

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
    code: str
    name: str
    color: str
    cells: list[GridCell] = []


class AbsenceRow(BaseModel):
    cells: list[GridCell] = []


class RoleBadge(BaseModel):
    code: str
    full: str
    color: str


class EmployeeBlock(BaseModel):
    id: str
    name: str
    initials: str
    role: str
    role_color: str
    role_full: str = ""
    roles: list[RoleBadge] = []
    projects: list[ProjectAllocationRow] = []
    absence: AbsenceRow
    gesamt: list[GesamtCell] = []
    heat: list[HeatCell] = []


_HEAT_LOW = 60
_HEAT_MID = 90
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
                label=f"{d.day}.{d.month}",
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


def _alloc(base: list[float], n: int) -> list[float]:
    """Cycle base values to fill n weeks."""
    return [base[i % len(base)] for i in range(n)]


def _cells(week_keys: list[str], values: list[float]) -> list[GridCell]:
    return [
        GridCell(week_key=k, value=v) for k, v in zip(week_keys, values, strict=True)
    ]


def _project_row(
    code: str, name: str, week_keys: list[str], values: list[float]
) -> ProjectAllocationRow:
    return ProjectAllocationRow(
        project_id=code.lower(),
        code=code,
        name=name,
        color=PROJECT_PALETTE.get(code, "var(--mantine-color-gray-5)"),
        cells=_cells(week_keys, values),
    )


def _build_employees(weeks: list[WeekColumn]) -> list[EmployeeBlock]:
    keys = [w.key for w in weeks]
    n = len(keys)
    blocks = [
        EmployeeBlock(
            id="anna-hoffmann",
            name="Anna Hoffmann",
            initials="AH",
            role="PM",
            role_color=ROLE_PALETTE["PM"],
            projects=[
                _project_row(
                    "CRM-AI",
                    "CRM-Vorhersagemodell",
                    keys,
                    _alloc([1, 1, 1.5, 1.5, 2, 1.5, 1.5, 1, 1, 1, 1, 1.5, 1.5], n),
                ),
                _project_row(
                    "FRAUD",
                    "Betrugserkennung Banking",
                    keys,
                    _alloc([0.5, 1, 1, 1.5, 1.5, 1.5, 1, 1, 0.5, 1, 1, 1, 1.5], n),
                ),
                _project_row(
                    "GENAI-ASSIST",
                    "GenAI Assistent intern",
                    keys,
                    _alloc([0.5, 0.5, 1, 1, 1.5, 1, 1, 0.5, 0.5, 0.5, 0.5, 1, 1], n),
                ),
                _project_row(
                    "NLP-LEGAL",
                    "NLP für Rechtsdokumente",
                    keys,
                    _alloc([0, 0, 0, 0, 1.5, 1, 1, 0.5, 0.5, 0.5, 0.5, 1, 1], n),
                ),
            ],
            absence=AbsenceRow(
                cells=_cells(keys, _alloc([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 5], n))
            ),
            gesamt=[],
        ),
        EmployeeBlock(
            id="marcus-weber",
            name="Marcus Weber",
            initials="MW",
            role="AIA",
            role_color=ROLE_PALETTE["AIA"],
            projects=[
                _project_row(
                    "CRM-AI",
                    "CRM-Vorhersagemodell",
                    keys,
                    _alloc(
                        [2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2, 2, 2, 2.5, 2.5, 2.5, 2.5],
                        n,
                    ),
                ),
                _project_row(
                    "FRAUD",
                    "Betrugserkennung Banking",
                    keys,
                    _alloc([1.5, 1.5, 1.5, 2, 1.5, 1.5, 1, 1, 1, 1.5, 1.5, 1.5, 2], n),
                ),
                _project_row(
                    "RECO",
                    "Empfehlungsengine Retail",
                    keys,
                    _alloc([0, 0, 0, 0, 0, 2, 1.5, 1.5, 1.5, 2, 2, 2, 2.5], n),
                ),
            ],
            absence=AbsenceRow(cells=_cells(keys, [0] * n)),
            gesamt=[],
        ),
        EmployeeBlock(
            id="lena-schulz",
            name="Lena Schulz",
            initials="LS",
            role="DS",
            role_color=ROLE_PALETTE["DS"],
            projects=[
                _project_row(
                    "CRM-AI",
                    "CRM-Vorhersagemodell",
                    keys,
                    _alloc([4, 4, 4, 3.5, 3.5, 3.5, 3, 3.5, 3.5, 4, 4, 4, 3.5], n),
                ),
            ],
            absence=AbsenceRow(
                cells=_cells(keys, _alloc([0, 0, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0], n))
            ),
            gesamt=[],
        ),
        EmployeeBlock(
            id="tobias-krueger",
            name="Tobias Krüger",
            initials="TK",
            role="AIE",
            role_color=ROLE_PALETTE["AIE"],
            projects=[
                _project_row(
                    "GENAI-ASSIST",
                    "GenAI Assistent intern",
                    keys,
                    _alloc([2, 2, 2, 2, 2.5, 2.5, 2, 2, 2, 2, 2, 2.5, 2.5], n),
                ),
                _project_row(
                    "RECO",
                    "Empfehlungsengine Retail",
                    keys,
                    _alloc([1, 1, 1.5, 1.5, 1.5, 1.5, 1, 1, 1, 1.5, 1.5, 1.5, 1.5], n),
                ),
            ],
            absence=AbsenceRow(cells=_cells(keys, [0] * n)),
            gesamt=[],
        ),
    ]
    for emp in blocks:
        if not emp.roles:
            emp.roles = [
                RoleBadge(
                    code=emp.role,
                    full=ROLE_FULL.get(emp.role, emp.role),
                    color=emp.role_color,
                )
            ]
        for proj in emp.projects:
            for cell in proj.cells:
                cell.key = f"{emp.id}|{proj.code}|{cell.week_key}"
    return blocks


_ALLOC_PATTERNS: list[list[float]] = [
    [1, 1, 1.5, 1.5, 2, 1.5, 1.5, 1, 1, 1, 1, 1.5, 1.5],
    [0.5, 1, 1, 1.5, 1.5, 1.5, 1, 1, 0.5, 1, 1, 1, 1.5],
    [0.5, 0.5, 1, 1, 1.5, 1, 1, 0.5, 0.5, 0.5, 0.5, 1, 1],
    [2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2, 2, 2, 2.5, 2.5, 2.5, 2.5],
    [1.5, 1.5, 1.5, 2, 1.5, 1.5, 1, 1, 1, 1.5, 1.5, 1.5, 2],
    [0, 0, 0, 0, 0, 2, 1.5, 1.5, 1.5, 2, 2, 2, 2.5],
    [4, 4, 4, 3.5, 3.5, 3.5, 3, 3.5, 3.5, 4, 4, 4, 3.5],
]


def _role_short(name: str) -> str:
    if not name:
        return "—"
    words = name.split()
    if len(words) >= 2:  # noqa: PLR2004
        return "".join(w[0] for w in words[:3]).upper()
    return name[:3].upper()


def _absence_days_for_week(absences: list, week_start: datetime.date) -> float:
    week_end = week_start + datetime.timedelta(days=4)
    for a in absences:
        if (
            a.start_date
            and a.end_date
            and a.start_date <= week_end
            and a.end_date >= week_start
        ):
            return 5.0
    return 0.0


def _build_employees_from_real(
    real_employees: list,
    real_projects: list,
    weeks: list[WeekColumn],
) -> list[EmployeeBlock]:
    keys = [w.key for w in weeks]
    n = len(keys)
    week_starts = [datetime.date(*(int(p) for p in w.key.split("_"))) for w in weeks]
    blocks: list[EmployeeBlock] = []
    pcount = min(3, len(real_projects))
    for emp_idx, emp in enumerate(real_employees):
        role_badges: list[RoleBadge] = []
        for rn in emp.role_names:
            short = _role_short(rn)
            color = ROLE_PALETTE.get(short, "var(--mantine-color-gray-2)")
            role_badges.append(RoleBadge(code=short, full=rn, color=color))
        role_name = emp.role_names[0] if emp.role_names else ""
        role_short = _role_short(role_name)
        role_color = ROLE_PALETTE.get(role_short, "var(--mantine-color-gray-2)")
        emp_id_str = f"emp-{emp.id}"
        projects: list[ProjectAllocationRow] = []
        if real_projects and pcount > 0:
            start = emp_idx % len(real_projects)
            chosen = [
                real_projects[(start + i) % len(real_projects)] for i in range(pcount)
            ]
            for p_idx, proj in enumerate(chosen):
                pattern = _ALLOC_PATTERNS[(emp_idx + p_idx) % len(_ALLOC_PATTERNS)]
                color = proj.color or "var(--mantine-color-gray-5)"
                projects.append(
                    ProjectAllocationRow(
                        project_id=str(proj.id),
                        code=proj.code or proj.name_de[:8].upper(),
                        name=proj.name_de or "—",
                        color=color,
                        cells=_cells(keys, _alloc(pattern, n)),
                    )
                )
        absence_vals = [_absence_days_for_week(emp.absences, ws) for ws in week_starts]
        blocks.append(
            EmployeeBlock(
                id=emp_id_str,
                name=f"{emp.first_name} {emp.last_name}".strip(),
                initials=(f"{emp.first_name[:1]}{emp.last_name[:1]}".upper() or "?"),
                role=role_short,
                role_color=role_color,
                role_full=role_name,
                roles=role_badges,
                projects=projects,
                absence=AbsenceRow(cells=_cells(keys, absence_vals)),
                gesamt=[],
                heat=[],
            )
        )
    for emp in blocks:
        for proj in emp.projects:
            for cell in proj.cells:
                cell.key = f"{emp.id}|{proj.code}|{cell.week_key}"
    return blocks


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
        absent = absence > 0
        pct = round((used / week.net_days) * 100) if week.net_days > 0 else 0
        bucket = "absent" if absent else _heat_bucket(pct)
        cells.append(
            HeatCell(week_key=week.key, percent=pct, is_absent=absent, bucket=bucket)
        )
    return cells


_FOCUS_GRID_SCRIPT = (
    "setTimeout(() => "
    "document.getElementById('planning-grid-root')?.focus({preventScroll:true}), 0)"
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

    def _load(self, num_weeks: int) -> None:
        weeks, spans = _build_weeks(num_weeks)
        employees = _build_employees(weeks)
        self._populate(weeks, spans, employees)

    def _load_real(self, num_weeks: int, real_emps: list, real_projs: list) -> None:
        weeks, spans = _build_weeks(num_weeks)
        employees = _build_employees_from_real(real_emps, real_projs, weeks)
        self._populate(weeks, spans, employees)

    @rx.event
    def load_dummy_data(self) -> None:
        self._load(TIME_RANGE_WEEKS["3 Monate"])

    @rx.event
    async def load_grid_data(self) -> None:
        from alloq_project.states.planning_state import PlanningState  # noqa: PLC0415

        planning = await self.get_state(PlanningState)
        n = TIME_RANGE_WEEKS.get(planning.time_range, TIME_RANGE_WEEKS["3 Monate"])
        if planning.available_employees:
            self._load_real(
                n, planning.available_employees, planning.available_projects
            )
        else:
            self._load(n)

    @rx.event
    async def reload_with_time_range(self, time_range: str) -> None:
        from alloq_project.states.planning_state import PlanningState  # noqa: PLC0415

        n = TIME_RANGE_WEEKS.get(time_range, TIME_RANGE_WEEKS["3 Monate"])
        planning = await self.get_state(PlanningState)
        if planning.available_employees:
            self._load_real(
                n, planning.available_employees, planning.available_projects
            )
        else:
            self._load(n)

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
