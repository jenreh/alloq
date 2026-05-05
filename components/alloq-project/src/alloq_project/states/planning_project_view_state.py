"""State for the resource planning Project view.

Pivots weekly allocations by project (top-level) → employees (nested).
Same data as the Grid view but aggregated per project.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.repositories import capacity_allocation_repo
from alloq_project.states.planning_grid_state import (
    LABEL_COL_PX,
    ROLE_PALETTE,
    TIME_RANGE_WEEKS,
    WEEK_COL_PX,
    GridCell,
    HeatCell,
    MonthSpan,
    WeekColumn,
    _build_weeks,
    _CapAssignment,
    _format_de,
    _heat_bucket,
    _parse_de,
    _role_short,
    _week_key_for_date,
)
from pydantic import BaseModel

from appkit_commons.database.session import get_asyncdb_session

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class EmployeeAllocationRow(BaseModel):
    """One employee's allocations under a single project."""

    emp_id: str = ""
    real_id: int = 0
    name: str = ""
    role_name: str = ""
    role_short: str = ""
    role_color: str = ""
    cells: list[GridCell] = []


class ProjectGesamtCell(BaseModel):
    """Aggregate capacity metric for one week at the project level."""

    week_key: str = ""
    allocated: float = 0.0
    bucket: str = "low"


class ProjectBlock(BaseModel):
    """Top-level block for one project in the project view."""

    id: str = ""
    real_id: int = 0
    code: str = ""
    name: str = ""
    color: str = ""
    state: str = ""
    employees: list[EmployeeAllocationRow] = []
    gesamt: list[ProjectGesamtCell] = []
    heat: list[HeatCell] = []


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _project_heat_bucket(allocated: float) -> str:
    """Bucket for project-level allocation (higher = busier)."""
    if allocated <= 0:
        return "low"
    if allocated <= 2.0:  # noqa: PLR2004
        return "mid"
    if allocated <= 4.0:  # noqa: PLR2004
        return "high"
    return "over"


def _build_project_blocks(
    real_projects: list,
    allocations: list[Any],
    capacity_assignments: list[Any],
    week_keys: list[str],
    real_employees: list,
) -> list[ProjectBlock]:
    """Build ProjectBlock list from DB data, pivoted by project."""
    projects_lookup = {int(p.id): p for p in real_projects}
    employees_lookup = {int(e.id): e for e in real_employees}

    # Group allocations: {project_id: {employee_id: {week_key: days}}}
    grouped: dict[int, dict[int, dict[str, float]]] = {}
    role_lookup: dict[tuple[int, int], str] = {}

    for a in allocations:
        wk = _week_key_for_date(a.week_start)
        if wk not in week_keys:
            continue
        proj_id = a.project_id
        emp_id = a.employee_id
        grouped.setdefault(proj_id, {}).setdefault(emp_id, {})[wk] = a.person_days
        if (emp_id, proj_id) not in role_lookup:
            role_name = getattr(a, "_cached_role_name", "")
            if role_name:
                role_lookup[(emp_id, proj_id)] = role_name

    # Also include capacity assignments (employee/project pairs with no
    # allocations yet)
    for cap in capacity_assignments:
        proj_id = cap.project_id
        emp_id = cap.employee_id
        if proj_id not in projects_lookup:
            continue
        grouped.setdefault(proj_id, {}).setdefault(emp_id, {})
        if cap.role_name:
            role_lookup[(emp_id, proj_id)] = cap.role_name

    # Build blocks for each project that has at least one employee
    blocks: list[ProjectBlock] = []
    for proj in real_projects:
        proj_id = int(proj.id)
        emp_map = grouped.get(proj_id)
        if not emp_map:
            continue
        code = proj.code or (proj.name_de[:8].upper() if proj.name_de else "—")
        color = proj.color or "var(--mantine-color-gray-5)"

        emp_rows: list[EmployeeAllocationRow] = []
        for emp_id, week_map in emp_map.items():
            emp = employees_lookup.get(emp_id)
            if emp is None:
                continue
            emp_name = f"{emp.first_name} {emp.last_name}".strip()
            r_name = role_lookup.get((emp_id, proj_id), "")
            r_short = _role_short(r_name)
            r_color = ROLE_PALETTE.get(r_short, "var(--mantine-color-gray-2)")
            cells = [
                GridCell(
                    key=f"emp-{emp_id}|{code}|{wk}",
                    week_key=wk,
                    value=float(week_map.get(wk, 0.0)),
                )
                for wk in week_keys
            ]
            emp_rows.append(
                EmployeeAllocationRow(
                    emp_id=f"emp-{emp_id}",
                    real_id=emp_id,
                    name=emp_name,
                    role_name=r_name,
                    role_short=r_short,
                    role_color=r_color,
                    cells=cells,
                )
            )
        # Sort employees alphabetically
        emp_rows.sort(key=lambda r: r.name)

        blocks.append(
            ProjectBlock(
                id=f"proj-{proj_id}",
                real_id=proj_id,
                code=code,
                name=proj.name_de or "—",
                color=color,
                state=getattr(proj, "state", ""),
                employees=emp_rows,
                gesamt=[],
                heat=[],
            )
        )
    return blocks


def _compute_project_gesamt(
    weeks: list[WeekColumn],
    block: ProjectBlock,
) -> list[ProjectGesamtCell]:
    """Compute per-week allocated total for a project."""
    cells: list[ProjectGesamtCell] = []
    for idx, week in enumerate(weeks):
        allocated = sum(
            emp.cells[idx].value for emp in block.employees if idx < len(emp.cells)
        )
        bucket = _project_heat_bucket(allocated)
        cells.append(
            ProjectGesamtCell(
                week_key=week.key,
                allocated=allocated,
                bucket=bucket,
            )
        )
    return cells


def _compute_project_heat(
    weeks: list[WeekColumn],
    block: ProjectBlock,
) -> list[HeatCell]:
    """Compute per-week utilization heat for a project."""
    cells: list[HeatCell] = []
    n_emps = len(block.employees)
    for idx, week in enumerate(weeks):
        allocated = sum(
            emp.cells[idx].value for emp in block.employees if idx < len(emp.cells)
        )
        # Percent: allocated vs. available capacity (employees x net_days)
        capacity = n_emps * week.net_days if n_emps else week.net_days
        pct = round((allocated / capacity) * 100) if capacity > 0 else 0
        bucket = _heat_bucket(pct)
        cells.append(
            HeatCell(
                week_key=week.key,
                percent=pct,
                is_absent=False,
                bucket=bucket,
            )
        )
    return cells


# ---------------------------------------------------------------------------
# Focus / editor scripts (reuse grid scripts)
# ---------------------------------------------------------------------------

_FOCUS_GRID_SCRIPT = (
    "setTimeout(() => "
    "document.getElementById('project-view-root')?.focus("
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
    "document.getElementById('project-view-root')?.focus("
    "{preventScroll:true}), 0);"
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class PlanningProjectViewState(rx.State):
    """Planning project view state — projects as top-level rows."""

    weeks: list[WeekColumn] = []
    month_spans: list[MonthSpan] = []
    projects: list[ProjectBlock] = []
    is_loaded: bool = False

    # Collapse state
    collapsed_projects: list[str] = []

    # Filter state (mirrors PlanningGridState for independent use)
    project_filter: list[str] = []
    role_filter: list[str] = []
    employee_filter: list[str] = []
    search_query: str = ""

    # Editing state
    active_cell: str = ""
    editing_cell: str = ""
    draft_value: str = ""
    edit_version: int = 0

    # --- Setters ---

    def set_project_filter(self, value: list[str]) -> None:
        self.project_filter = value

    def set_role_filter(self, value: list[str]) -> None:
        self.role_filter = value

    def set_employee_filter(self, value: list[str]) -> None:
        self.employee_filter = value

    def set_search_query(self, value: str) -> None:
        self.search_query = value

    # --- Computed vars ---

    @rx.var(cache=True)
    def filtered_projects(self) -> list[ProjectBlock]:
        """Return projects filtered by active filters."""
        result = self.projects

        if self.project_filter:
            result = [p for p in result if str(p.real_id) in self.project_filter]

        if self.role_filter:
            result = [
                p
                for p in result
                if any(
                    emp.role_short in self.role_filter
                    or emp.role_name in self.role_filter
                    for emp in p.employees
                )
            ]

        if self.employee_filter:
            result = [
                p
                for p in result
                if any(str(emp.real_id) in self.employee_filter for emp in p.employees)
            ]

        if self.search_query.strip():
            q = self.search_query.strip().lower()
            result = [
                p
                for p in result
                if q in p.name.lower()
                or q in p.code.lower()
                or any(q in emp.name.lower() for emp in p.employees)
            ]

        return result

    @rx.var(cache=True)
    def project_filter_label(self) -> str:
        count = len(self.project_filter)
        return f'"Projekte ({count})"' if count > 0 else ""

    @rx.var(cache=True)
    def role_filter_label(self) -> str:
        count = len(self.role_filter)
        return f'"Rollen ({count})"' if count > 0 else ""

    @rx.var(cache=True)
    def employee_filter_label(self) -> str:
        count = len(self.employee_filter)
        return f'"MA ({count})"' if count > 0 else ""

    @rx.var(cache=True)
    def table_width(self) -> str:
        return f"{LABEL_COL_PX + len(self.weeks) * WEEK_COL_PX}px"

    @rx.var(cache=True)
    def grid_template_columns(self) -> str:
        return f"{LABEL_COL_PX}px repeat({len(self.weeks)}, {WEEK_COL_PX}px)"

    # --- Data loading ---

    def _populate(
        self,
        weeks: list[WeekColumn],
        spans: list[MonthSpan],
        blocks: list[ProjectBlock],
    ) -> None:
        for block in blocks:
            block.gesamt = _compute_project_gesamt(weeks, block)
            block.heat = _compute_project_heat(weeks, block)
        self.weeks = weeks
        self.month_spans = spans
        self.projects = blocks
        self.is_loaded = True
        self.active_cell = ""
        self.editing_cell = ""
        self.draft_value = ""

    async def _fetch_allocations(self, weeks: list[WeekColumn]) -> list[Any]:
        if not weeks:
            return []
        first = datetime.date(*(int(p) for p in weeks[0].key.split("_")))
        last = datetime.date(*(int(p) for p in weeks[-1].key.split("_")))
        async with get_asyncdb_session() as session:
            results = await capacity_allocation_repo.find_in_range(session, first, last)
            for r in results:
                r._cached_role_name = (  # noqa: SLF001
                    r.role.name if r.role else ""
                )
                session.expunge(r)
            return results

    async def _fetch_capacity_assignments(self) -> list[_CapAssignment]:
        """Fetch all CapacityEntity records."""
        async with get_asyncdb_session() as session:
            from alloq_commons.entities.capacity import (  # noqa: PLC0415
                CapacityEntity,
            )
            from sqlmodel import select  # noqa: PLC0415

            result = await session.execute(select(CapacityEntity))
            entities = list(result.scalars().unique().all())
            return [
                _CapAssignment(
                    employee_id=e.employee_id,
                    project_id=e.project_id,
                    role_name=e.role.name if e.role else "",
                )
                for e in entities
            ]

    @rx.event
    async def load_project_view_data(self) -> None:
        """Load and build project-pivoted grid data."""
        from alloq_project.states.planning_state import (  # noqa: PLC0415
            PlanningState,
        )

        planning = await self.get_state(PlanningState)
        n = TIME_RANGE_WEEKS.get(planning.time_range, TIME_RANGE_WEEKS["3 Monate"])
        weeks, spans = _build_weeks(n)
        allocations = await self._fetch_allocations(weeks)
        assignments = await self._fetch_capacity_assignments()

        blocks = _build_project_blocks(
            planning.available_projects,
            allocations,
            assignments,
            [w.key for w in weeks],
            planning.available_employees,
        )
        self._populate(weeks, spans, blocks)

    @rx.event
    async def reload_with_time_range(self, time_range: str) -> None:
        """Reload project view with a new time range."""
        from alloq_project.states.planning_state import (  # noqa: PLC0415
            PlanningState,
        )

        n = TIME_RANGE_WEEKS.get(time_range, TIME_RANGE_WEEKS["3 Monate"])
        planning = await self.get_state(PlanningState)
        weeks, spans = _build_weeks(n)
        allocations = await self._fetch_allocations(weeks)
        assignments = await self._fetch_capacity_assignments()

        blocks = _build_project_blocks(
            planning.available_projects,
            allocations,
            assignments,
            [w.key for w in weeks],
            planning.available_employees,
        )
        self._populate(weeks, spans, blocks)

    # --- Collapse / Expand ---

    @rx.event
    def toggle_project(self, project_id: str) -> None:
        if project_id in self.collapsed_projects:
            self.collapsed_projects = [
                p for p in self.collapsed_projects if p != project_id
            ]
        else:
            self.collapsed_projects = [*self.collapsed_projects, project_id]

    # --- Cell editing ---

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
    def set_draft(self, value: str) -> None:
        self.draft_value = value

    @rx.event
    def cancel_edit(self) -> Any:
        self.editing_cell = ""
        self.draft_value = ""
        return rx.call_script(_FOCUS_GRID_SCRIPT)

    @rx.event
    def commit_edit(self) -> Any:
        change = self._commit_current()
        self.editing_cell = ""
        self.draft_value = ""
        if change:
            from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
                PlanningGridState,
            )

            return PlanningGridState.sync_cell(*change)
        return None

    @rx.event
    def commit_and_select_next(self, direction: str) -> Any:
        """Commit current edit, move active to next cell."""
        cur = self.editing_cell
        if not cur:
            return None
        change = self._commit_current()
        nxt = self._navigate(cur, direction)
        self.editing_cell = ""
        self.draft_value = ""
        if nxt:
            self.active_cell = nxt
        events: list[Any] = [rx.call_script(_FOCUS_GRID_SCRIPT)]
        if change:
            from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
                PlanningGridState,
            )

            events.append(PlanningGridState.sync_cell(*change))
        return events

    @rx.event
    def commit_and_move(self, direction: str) -> Any:
        """Commit current edit, move edit to next cell (Tab)."""
        cur = self.editing_cell
        if not cur:
            return None
        change = self._commit_current()
        next_key = self._navigate(cur, direction)
        if next_key:
            cur_val = self._lookup_value(next_key)
            self.draft_value = "" if cur_val == 0 else _format_de(cur_val)
            self.active_cell = next_key
            self.editing_cell = next_key
            self.edit_version += 1
            events: list[Any] = [rx.call_script(_FOCUS_EDITOR_SCRIPT)]
            if change:
                from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
                    PlanningGridState,
                )

                events.append(PlanningGridState.sync_cell(*change))
            return events
        self.editing_cell = ""
        self.draft_value = ""
        events = [rx.call_script(_FOCUS_GRID_SCRIPT)]
        if change:
            from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
                PlanningGridState,
            )

            events.append(PlanningGridState.sync_cell(*change))
        return events

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
        """Grid wrapper on_key_down."""
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

    @rx.event
    def move_active(self, direction: str) -> None:
        if self.editing_cell:
            return
        if not self.active_cell:
            return
        nxt = self._navigate(self.active_cell, direction)
        if nxt:
            self.active_cell = nxt

    # --- Internal helpers ---

    def _commit_current(self) -> tuple[str, float] | None:
        """Commit draft value; return (cell_key, new_val) if changed."""
        cur = self.editing_cell
        if not cur:
            return None
        new_val = _parse_de(self.draft_value)
        if new_val is None:
            return None
        emp_id, proj_code, week_key = cur.split("|")
        cur_val = self._lookup_value(cur)
        if new_val == cur_val:
            return None
        for proj in self.projects:
            if proj.code != proj_code:
                continue
            for emp in proj.employees:
                if emp.emp_id != emp_id:
                    continue
                for cell in emp.cells:
                    if cell.week_key == week_key:
                        cell.value = new_val
                        cell.is_dirty = True
                        break
            proj.gesamt = _compute_project_gesamt(self.weeks, proj)
            proj.heat = _compute_project_heat(self.weeks, proj)
        self.projects = list(self.projects)
        return (cur, new_val)

    @rx.event
    def sync_cell(self, cell_key: str, value: float) -> None:
        """Apply a cell change from the grid view (cross-state sync)."""
        try:
            emp_id, proj_code, week_key = cell_key.split("|")
        except ValueError:
            return
        for proj in self.projects:
            if proj.code != proj_code:
                continue
            for emp in proj.employees:
                if emp.emp_id != emp_id:
                    continue
                for cell in emp.cells:
                    if cell.week_key == week_key:
                        cell.value = value
                        cell.is_dirty = True
                        break
            proj.gesamt = _compute_project_gesamt(self.weeks, proj)
            proj.heat = _compute_project_heat(self.weeks, proj)
        self.projects = list(self.projects)

    def _lookup_value(self, cell_key: str) -> float:
        try:
            emp_id, proj_code, week_key = cell_key.split("|")
        except ValueError:
            return 0.0
        for proj in self.projects:
            if proj.code != proj_code:
                continue
            for emp in proj.employees:
                if emp.emp_id != emp_id:
                    continue
                for cell in emp.cells:
                    if cell.week_key == week_key:
                        return cell.value
        return 0.0

    def _navigate(  # noqa: PLR0911
        self, cur_key: str, direction: str
    ) -> str:
        try:
            emp_id, proj_code, week_key = cur_key.split("|")
        except ValueError:
            return ""
        week_keys = [w.key for w in self.weeks]
        # Build flat row list: (emp_id, proj_code) for visible projects
        rows: list[tuple[str, str]] = [
            (emp.emp_id, proj.code)
            for proj in self.projects
            if proj.id not in self.collapsed_projects
            for emp in proj.employees
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

    def _collect_dirty(
        self,
    ) -> list[tuple[int, int, str, datetime.date, float, GridCell]]:
        out: list[tuple[int, int, str, datetime.date, float, GridCell]] = []
        for proj in self.projects:
            for emp in proj.employees:
                for cell in emp.cells:
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
                            proj.real_id,
                            emp.role_name,
                            wk,
                            float(cell.value),
                            cell,
                        )
                    )
        return out

    @rx.var(cache=True)
    def has_dirty(self) -> bool:
        return any(
            cell.is_dirty
            for proj in self.projects
            for emp in proj.employees
            for cell in emp.cells
        )

    @rx.event
    async def save_grid(self) -> AsyncGenerator[Any, None]:
        """Persist edited cells to capacity_allocations."""
        dirty = self._collect_dirty()
        if not dirty:
            yield rx.toast.info("Keine Änderungen.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                for emp_id, proj_id, _role, wk, pd, _cell in dirty:
                    # Lookup role_id from first role
                    # For now use 0; proper lookup needed
                    await capacity_allocation_repo.upsert_cell(
                        session, proj_id, emp_id, 0, wk, pd
                    )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to save project view: %s", exc)
            yield rx.toast.error(
                f"Speichern fehlgeschlagen: {exc}",
                position="top-right",
            )
            return
        for *_unused, cell in dirty:
            cell.is_dirty = False
        self.projects = list(self.projects)
        from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
            PlanningGridState,
        )

        yield PlanningGridState.clear_dirty()
        yield rx.toast.success(
            f"{len(dirty)} Zellen gespeichert.",
            position="top-right",
        )

    @rx.event
    def clear_dirty(self) -> None:
        """Clear all dirty flags (called after sibling state saves)."""
        for proj in self.projects:
            for emp in proj.employees:
                for cell in emp.cells:
                    cell.is_dirty = False
        self.projects = list(self.projects)
