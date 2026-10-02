"""Single source of truth for planning data and views.

Allocations live once in `cells` keyed canonically by
``"{employee_id}|{project_code}|{week_key}"``. The two pivots — employee
blocks (Grid view) and project blocks (Project view) — are computed views of
the same store. Selection, navigation and in-cell editing run client-side in
the ``GridController`` component, which sends committed batches to
``apply_cell_changes``; dirtiness is tracked against the last loaded/saved
snapshot.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.entities import CapacityEntity, RoleEntity
from alloq_commons.models.employee import Employee
from alloq_commons.models.project import Project
from alloq_commons.models.role import Role
from alloq_commons.repositories import (
    capacity_allocation_repo,
    capacity_repo,
    employee_repo,
    project_repo,
    public_holiday_repo,
    role_repo,
)
from alloq_commons.services.quick_project import (
    NEW_PROJECT_OPTION,
    NEW_PROJECT_VALUE,
    QuickProjectError,
    create_quick_project,
)
from alloq_commons.services.utilization import UtilizationService
from alloq_project.services.planning_builders import (
    ROLE_PALETTE,
    CapAssignment,
    anchor_date,
    build_employee_meta,
    build_project_meta,
    build_weeks,
    cell_key,
    cell_role_ids,
    compute_gesamt,
    compute_heat,
    compute_project_gesamt,
    compute_project_heat,
    current_week_key,
    dirty_keys_for,
    edits_to_rows,
    employee_id_by_email,
    employee_summary,
    ingest_allocations,
    managed_employee_ids,
    owned_project_ids,
    parse_cell_changes,
    project_summary,
    role_short,
    sorted_projects,
    split_edits,
    wire_pairs,
)
from alloq_project.services.planning_gantt import build_absence_gantt
from alloq_project.states.planning_models import (
    LABEL_COL_PX,
    TIME_RANGE_WEEKS,
    WEEK_COL_PX,
    AbsenceGanttRow,
    AbsenceRow,
    EmployeeAllocationRow,
    EmployeeBlock,
    GesamtCell,
    GridCell,
    HeatCell,
    MonthSpan,
    ProjectAllocationRow,
    ProjectBlock,
    ProjectGesamtCell,
    RoleBadge,
    WeekColumn,
)
from sqlalchemy import select

from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.decorators import requires_admin
from appkit_user.authentication.states import UserSession

log = logging.getLogger(__name__)

__all__ = [
    "LABEL_COL_PX",
    "WEEK_COL_PX",
    "EmployeeAllocationRow",
    "EmployeeBlock",
    "GesamtCell",
    "GridCell",
    "HeatCell",
    "MonthSpan",
    "PlanningStore",
    "ProjectAllocationRow",
    "ProjectBlock",
    "ProjectGesamtCell",
    "WeekColumn",
]

GRID_VIEW = "Grid"
PROJECT_VIEW = "Projekte"
HEATMAP_VIEW = "Heatmap"


# === State ===


class PlanningStore(UserSession):
    """Shared planning entities, allocations, filters and derived views."""

    # === Entity caches ===

    available_projects: rx.Field[list[Project]] = rx.field(default_factory=list)
    all_projects: rx.Field[list[Project]] = rx.field(default_factory=list)
    available_employees: rx.Field[list[Employee]] = rx.field(default_factory=list)
    available_roles: rx.Field[list[Role]] = rx.field(default_factory=list)
    is_loading: rx.Field[bool] = rx.field(False)

    # === Grid + view state ===

    weeks: rx.Field[list[WeekColumn]] = rx.field(default_factory=list)
    month_spans: rx.Field[list[MonthSpan]] = rx.field(default_factory=list)
    holiday_dates: rx.Field[list[datetime.date]] = rx.field(default_factory=list)
    is_loaded: rx.Field[bool] = rx.field(False)

    cells: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    saved_cells: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    dirty_keys: rx.Field[list[str]] = rx.field(default_factory=list)
    # Unsaved edits whose row/week is not part of the loaded time range.
    hidden_edits: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    grid_revision: rx.Field[int] = rx.field(0)

    employee_meta: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    project_meta: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    role_lookup: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    role_id_lookup: rx.Field[dict[str, int]] = rx.field(default_factory=dict)
    # cell key -> role id of the stored row the cell shows (backend only)
    _cell_role_ids: dict[str, int] = {}
    absence_days: rx.Field[dict[str, list[float]]] = rx.field(default_factory=dict)

    view_mode: rx.Field[str] = rx.field("Grid")
    time_range: rx.Field[str] = rx.field("3 Monate")
    is_saving: rx.Field[bool] = rx.field(False)

    project_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    role_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    employee_filter: rx.Field[list[str]] = rx.field(default_factory=list)
    project_scope: rx.Field[bool] = rx.field(False)
    employee_scope: rx.Field[bool] = rx.field(False)
    current_employee_id: rx.Field[int | None] = rx.field(None)
    current_week: rx.Field[str] = rx.field("")

    collapsed_employees: rx.Field[list[str]] = rx.field(default_factory=list)
    collapsed_projects: rx.Field[list[str]] = rx.field(default_factory=list)

    add_project_emp_id: rx.Field[str] = rx.field("")
    add_project_options: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    add_project_role_options: rx.Field[list[dict[str, str]]] = rx.field(
        default_factory=list
    )
    add_project_selected: rx.Field[str] = rx.field("")
    quick_project_name: rx.Field[str] = rx.field("")
    quick_project_code: rx.Field[str] = rx.field("")
    is_quick_creating: rx.Field[bool] = rx.field(False)

    # === Setters ===

    @rx.event
    def set_add_project_selected(self, value: str) -> None:
        self.add_project_selected = value or ""

    @rx.event
    def set_quick_project_name(self, value: str) -> None:
        self.quick_project_name = value

    @rx.event
    def set_quick_project_code(self, value: str) -> None:
        self.quick_project_code = value

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
    def toggle_project_scope(self) -> Any:
        if not self.project_scope and self.current_employee_id is None:
            return self._notify_no_employee()
        self.project_scope = not self.project_scope
        return None

    @rx.event
    def toggle_employee_scope(self) -> Any:
        if not self.employee_scope and self.current_employee_id is None:
            return self._notify_no_employee()
        self.employee_scope = not self.employee_scope
        return None

    @staticmethod
    def _notify_no_employee() -> Any:
        return rx.toast.warning(
            "Ihrem Benutzer ist kein Mitarbeiter zugeordnet.", position="top-right"
        )

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

    def _cell(self, key: str, week_key: str, dirty: set[str]) -> GridCell:
        return GridCell(
            key=key,
            week_key=week_key,
            value=float(self.cells.get(key, 0.0)),
            is_dirty=key in dirty,
        )

    @rx.var(cache=True, backend=True)
    def employee_blocks(self) -> list[EmployeeBlock]:
        weeks = self.weeks
        if not weeks:
            return []
        wks = self._week_keys()
        proj_idx = {p["id"]: p for p in self.project_meta}
        role_abbrev_by_name = {r.name: r.abbreviation for r in self.available_roles}
        from_key = self.current_week_key
        dirty = set(self.dirty_keys)
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
                cells = [
                    self._cell(cell_key(emp_id, code, wk), wk, dirty) for wk in wks
                ]
                rname = self.role_lookup.get(f"{emp_id}|{proj['real_id']}", "")
                rshort = role_abbrev_by_name.get(rname) or role_short(rname)
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
            project_rows.sort(key=lambda row: row.name.lower())
            internal_hours = emp.get("internal_hours", 4)
            internal_days = internal_hours / 8.0
            wp = int(emp.get("workload_percent", 100) or 100)
            internal_cells = [
                GridCell(
                    week_key=wks[i],
                    value=UtilizationService.cap_internal_days(
                        internal_hours=internal_hours,
                        absence_days=(ab[i] if i < len(ab) else 0.0),
                        work_days=UtilizationService.apply_workload(
                            weeks[i].work_days, wp
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
                hours_per_week=emp.get("hours_per_week", 40.0),
                workload_percent=wp,
            )
            block.gesamt = compute_gesamt(weeks, block)
            block.heat = compute_heat(weeks, block)
            block.planned_days, block.available_days = employee_summary(block, from_key)
            blocks.append(block)
        return blocks

    @rx.var(cache=True, backend=True)
    def project_blocks(self) -> list[ProjectBlock]:
        weeks = self.weeks
        if not weeks:
            return []
        wks = self._week_keys()
        emp_idx = {e["id"]: e for e in self.employee_meta}
        role_abbrev_by_name = {r.name: r.abbreviation for r in self.available_roles}
        from_key = self.current_week_key
        dirty = set(self.dirty_keys)
        blocks: list[ProjectBlock] = []
        for proj in self.project_meta:
            code = proj["code"]
            emp_rows: list[EmployeeAllocationRow] = []
            for emp_id in proj.get("employee_ids", []):
                emp = emp_idx.get(emp_id)
                if emp is None:
                    continue
                cells = [
                    self._cell(cell_key(emp_id, code, wk), wk, dirty) for wk in wks
                ]
                rname = self.role_lookup.get(f"{emp_id}|{proj['real_id']}", "")
                rshort = role_abbrev_by_name.get(rname) or role_short(rname)
                rcolor = ROLE_PALETTE.get(rshort, "var(--mantine-color-gray-2)")
                emp_rows.append(
                    EmployeeAllocationRow(
                        emp_id=emp_id,
                        project_code=code,
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
            block.gesamt = compute_project_gesamt(weeks, block)
            block.heat = compute_project_heat(weeks, block)
            block.planned_days, block.role_totals = project_summary(block, from_key)
            blocks.append(block)
        return blocks

    # === Filtered pivots ===

    def _filter_employees(self, blocks: list[EmployeeBlock]) -> list[EmployeeBlock]:
        """Apply the scope toggles and the project/role/employee filters."""
        result = blocks
        if self.project_scope:
            own = owned_project_ids(self.all_projects, self.current_employee_id)
            result = [e for e in result if any(p.project_id in own for p in e.projects)]
        if self.employee_scope:
            mine = managed_employee_ids(
                self.available_employees, self.current_employee_id
            )
            result = [e for e in result if str(e.real_id) in mine]
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
    def filtered_employees(self) -> list[EmployeeBlock]:
        if self.view_mode != GRID_VIEW:
            return []
        return self._filter_employees(self.employee_blocks)

    @rx.var(cache=True)
    def filtered_projects(self) -> list[ProjectBlock]:
        if self.view_mode != PROJECT_VIEW:
            return []
        result = self.project_blocks
        if self.project_scope:
            own = owned_project_ids(self.all_projects, self.current_employee_id)
            result = [p for p in result if str(p.real_id) in own]
        if self.employee_scope:
            mine = managed_employee_ids(
                self.available_employees, self.current_employee_id
            )
            result = [
                p for p in result if any(str(e.real_id) in mine for e in p.employees)
            ]
        if self.project_filter:
            result = [p for p in result if str(p.real_id) in self.project_filter]
        if self.role_filter:
            result = [
                p
                for p in result
                if any(
                    str(self.role_id_lookup.get(f"{e.emp_id}|{p.real_id}"))
                    in self.role_filter
                    for e in p.employees
                )
            ]
        if self.employee_filter:
            result = [
                p
                for p in result
                if any(str(e.real_id) in self.employee_filter for e in p.employees)
            ]
        return result

    @rx.var(cache=True)
    def employees(self) -> list[EmployeeBlock]:
        _ = self.cells  # explicit dependency for heatmap reactivity
        if self.view_mode != HEATMAP_VIEW:
            return []
        return self._filter_employees(self.employee_blocks)

    @rx.var(cache=True)
    def absence_gantt_rows(self) -> list[AbsenceGanttRow]:
        if self.view_mode != "Abwesenheiten":
            return []
        return build_absence_gantt(
            self._filter_employees(self.employee_blocks),
            self.available_employees,
            self.weeks,
        )

    @rx.var(cache=True, backend=True)
    def projects(self) -> list[ProjectBlock]:
        return self.project_blocks

    @rx.var(cache=True)
    def has_dirty(self) -> bool:
        return len(self.dirty_keys) > 0 or len(self.hidden_edits) > 0

    @rx.var(cache=True)
    def avg_heat(self) -> list[HeatCell]:
        emps = self.employees  # same filtered population as the heatmap rows
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
        """Current week as of the last populate, so summaries match the columns."""
        return self.current_week or current_week_key()

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

    async def _fetch_holidays(self, num_weeks: int) -> set[datetime.date]:
        """Load public holidays covering the rolling planning window."""
        if num_weeks <= 0:
            return set()
        anchor = anchor_date()
        end = anchor + datetime.timedelta(days=7 * num_weeks - 1)
        async with get_asyncdb_session() as session:
            rows = await public_holiday_repo.find_by_date_range(session, anchor, end)
            return {row.date for row in rows if row.date}

    async def _fetch_data(
        self, weeks: list[WeekColumn]
    ) -> tuple[list[Any], list[CapAssignment]]:
        if not weeks:
            return [], []
        first = datetime.date(*(int(p) for p in weeks[0].key.split("_")))
        last = datetime.date(*(int(p) for p in weeks[-1].key.split("_")))
        project_ids = [int(p.id) for p in self.available_projects]
        async with get_asyncdb_session() as session:
            allocs = await capacity_allocation_repo.find_cells_in_range(
                session, first, last
            )
            cap_rows = await session.execute(
                select(
                    CapacityEntity.employee_id,
                    CapacityEntity.project_id,
                    CapacityEntity.role_id,
                    RoleEntity.name,
                )
                .outerjoin(RoleEntity, RoleEntity.id == CapacityEntity.role_id)
                .where(CapacityEntity.project_id.in_(project_ids))
            )
            assignments = [
                CapAssignment(
                    employee_id=employee_id,
                    project_id=project_id,
                    role_id=role_id,
                    role_name=role_name or "",
                )
                for employee_id, project_id, role_id, role_name in cap_rows.all()
            ]
        return list(allocs), assignments

    def _unsaved_edits(self) -> dict[str, float]:
        """All unsaved edits, including those outside the loaded range."""
        return {
            **self.hidden_edits,
            **{key: self.cells.get(key, 0.0) for key in self.dirty_keys},
        }

    async def _populate(self, num_weeks: int, *, keep_edits: bool = False) -> None:
        pending = self._unsaved_edits() if keep_edits else {}
        holiday_dates = await self._fetch_holidays(num_weeks)
        weeks, spans = build_weeks(num_weeks, holiday_dates)
        allocations, assignments = await self._fetch_data(weeks)
        wks = [w.key for w in weeks]

        role_abbrev_by_name = {r.name: r.abbreviation for r in self.available_roles}
        emp_meta, absence_map = build_employee_meta(
            self.available_employees, wks, role_abbrev_by_name
        )
        proj_meta, proj_idx = build_project_meta(self.available_projects)
        cells, role_lookup, role_id_lookup, pairs = ingest_allocations(
            allocations, assignments, proj_idx, set(wks)
        )
        wire_pairs(emp_meta, proj_idx, pairs)
        self._cell_role_ids = cell_role_ids(allocations, proj_idx, set(wks))

        self.weeks = weeks
        self.current_week = current_week_key()
        self.month_spans = spans
        self.holiday_dates = sorted(holiday_dates)
        self.saved_cells = dict(cells)
        self.grid_revision += 1
        self.employee_meta = emp_meta
        self.project_meta = proj_meta
        self.role_lookup = role_lookup
        self.role_id_lookup = role_id_lookup
        self.absence_days = absence_map
        visible, hidden = split_edits(
            pending, self._editable_rows(), {w.key for w in weeks}
        )
        self.cells = {**cells, **visible}
        self.hidden_edits = hidden
        self.dirty_keys = dirty_keys_for(self.cells, self.saved_cells)
        self.is_loaded = True

    async def _load_entities(self) -> None:
        async with get_asyncdb_session() as session:
            projects = await project_repo.find_all(session)
            all_proj = sorted_projects([Project(**p.to_dict()) for p in projects])
            self.all_projects = all_proj
            self.available_projects = [
                p for p in all_proj if p.state != "Abgeschlossen"
            ]
            employees = await employee_repo.find_all(session)
            since = anchor_date()
            self.available_employees = [
                Employee(**e.to_dict(absences_since=since)) for e in employees
            ]
            self.available_employees.sort(key=lambda e: (e.last_name, e.first_name))
            roles = await role_repo.find_all(session)
            self.available_roles = [Role(**r.to_dict()) for r in roles]
            self.available_roles.sort(key=lambda r: r.name)
        await self._resolve_current_employee()

    async def _resolve_current_employee(self) -> None:
        """Map the logged-in user to an employee for the scope toggles."""
        user = await self.authenticated_user
        email = user.email if user and user.email else ""
        self.current_employee_id = employee_id_by_email(self.available_employees, email)

    def _range_weeks(self, time_range: str | None = None) -> int:
        return TIME_RANGE_WEEKS.get(
            time_range or self.time_range, TIME_RANGE_WEEKS["3 Monate"]
        )

    @rx.event
    @requires_admin
    async def load(self) -> AsyncGenerator[Any]:
        """Load entity caches and populate the grid for the current time range."""
        self.is_loading = True
        yield
        try:
            await self._load_entities()
            await self._populate(self._range_weeks())
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to load planning data: %s", exc)
            yield rx.toast.error(
                "Planungsdaten konnten nicht geladen werden.", position="top-right"
            )
        finally:
            self.is_loading = False
        yield

    @rx.event
    @requires_admin
    async def refresh(self) -> None:
        """Reload entities and allocations, keeping unsaved grid edits."""
        await self._load_entities()
        await self._populate(self._range_weeks(), keep_edits=True)

    @rx.event
    @requires_admin
    async def reload_with_time_range(self, time_range: str) -> Any:
        """Reload for another range, carrying unsaved edits over."""
        await self._populate(self._range_weeks(time_range), keep_edits=True)
        if self.hidden_edits:
            return rx.toast.info(
                f"{len(self.hidden_edits)} ungespeicherte Änderung(en) außerhalb "
                "des Zeitraums bleiben erhalten.",
                position="top-right",
            )
        return None

    # === Cell editing ===

    def _editable_rows(self) -> set[tuple[str, str]]:
        """(emp_id, project_code) pairs that are rendered as editable rows."""
        code_by_pid = {p["id"]: p["code"] for p in self.project_meta}
        return {
            (emp["id"], code_by_pid[pid])
            for emp in self.employee_meta
            for pid in emp.get("project_ids", [])
            if pid in code_by_pid
        }

    @rx.event
    def apply_cell_changes(self, changes: list[dict[str, Any]]) -> Any:
        """Apply a batch of committed cell edits from the grid controller."""
        updates, rejected = parse_cell_changes(
            changes, self._editable_rows(), set(self._week_keys())
        )
        if updates:
            self.cells = {**self.cells, **updates}
            self.dirty_keys = dirty_keys_for(self.cells, self.saved_cells)
        if rejected:
            log.warning("Rejected %d invalid cell change(s)", rejected)
            return self.notify_rejected(rejected)
        return None

    @rx.event
    def notify_rejected(self, count: int) -> Any:
        """Tell the user that pasted cells were skipped as invalid."""
        if count <= 0:
            return None
        return rx.toast.warning(
            f"{count} ungültige Eingabe(n) ignoriert.", position="top-right"
        )

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
    @requires_admin
    async def save_grid(self) -> AsyncGenerator[Any]:
        if self.is_saving:
            return
        edits = self._unsaved_edits()
        if not edits:
            yield rx.toast.info("Keine Änderungen.", position="top-right")
            return
        self.is_saving = True
        yield
        rows = edits_to_rows(
            edits,
            self.project_meta,
            self.employee_meta,
            {**self.role_id_lookup, **self._cell_role_ids},
        )
        skipped = len(edits) - len(rows)
        if not rows:
            self.is_saving = False
            yield rx.toast.warning(
                f"{skipped} Änderung(en) konnten nicht zugeordnet werden.",
                position="top-right",
            )
            return
        try:
            async with get_asyncdb_session() as session:
                await capacity_allocation_repo.batch_upsert(
                    session, list(rows.values())
                )
                await session.commit()
        except Exception:
            log.exception("Failed to save grid")
            self.is_saving = False
            yield rx.toast.error(
                "Speichern fehlgeschlagen. Bitte erneut versuchen.",
                position="top-right",
            )
            return
        # Unmappable edits stay dirty/hidden so they are not silently lost.
        self.saved_cells = {
            **self.saved_cells,
            **{key: self.cells[key] for key in rows if key in self.cells},
        }
        self.hidden_edits = {
            k: v for k, v in self.hidden_edits.items() if k not in rows
        }
        self.dirty_keys = dirty_keys_for(self.cells, self.saved_cells)
        self.is_saving = False
        yield rx.toast.success(f"{len(rows)} Zellen gespeichert.", position="top-right")
        if skipped:
            yield rx.toast.warning(
                f"{skipped} Änderung(en) konnten nicht zugeordnet werden.",
                position="top-right",
            )

    # === Add / remove project from employee in grid ===

    @rx.var
    def quick_create_active(self) -> bool:
        """True while the inline quick-create fields should be shown."""
        return self.add_project_selected == NEW_PROJECT_VALUE

    def _rebuild_add_project_options(self) -> None:
        emp = next(
            (e for e in self.employee_meta if e["id"] == self.add_project_emp_id),
            None,
        )
        proj_idx = {p["id"]: p for p in self.project_meta}
        assigned_codes = {
            proj_idx[pid]["code"]
            for pid in (emp or {}).get("project_ids", [])
            if pid in proj_idx
        }
        self.add_project_options = [
            NEW_PROJECT_OPTION,
            *(
                {"value": str(p.id), "label": f"{p.code} - {p.name_de}"}
                for p in self.available_projects
                if p.code not in assigned_codes
            ),
        ]

    def _reset_quick_create(self) -> None:
        self.add_project_selected = ""
        self.quick_project_name = ""
        self.quick_project_code = ""
        self.is_quick_creating = False

    @rx.event
    async def open_add_project_for_employee(self, emp_id: str) -> None:
        self.add_project_emp_id = emp_id
        self._reset_quick_create()
        emp = next((e for e in self.employee_meta if e["id"] == emp_id), None)
        if not emp:
            return
        self._rebuild_add_project_options()
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
        self._reset_quick_create()

    @rx.event
    @requires_admin
    async def quick_create_project(self) -> AsyncGenerator[Any]:
        """Create a project from the inline fields and select it."""
        self.is_quick_creating = True
        yield
        try:
            async with get_asyncdb_session() as session:
                project = await create_quick_project(
                    session, self.quick_project_name, self.quick_project_code
                )
                await session.commit()
        except QuickProjectError as exc:
            self.is_quick_creating = False
            yield rx.toast.error(str(exc), position="top-right")
            return
        except Exception:
            log.exception("Failed to quick-create project")
            self.is_quick_creating = False
            yield rx.toast.error(
                "Projekt konnte nicht angelegt werden.", position="top-right"
            )
            return
        self.all_projects = sorted_projects([*self.all_projects, project])
        self.available_projects = sorted_projects([*self.available_projects, project])
        self._rebuild_add_project_options()
        self.add_project_selected = str(project.id)
        self.quick_project_name = ""
        self.quick_project_code = ""
        self.is_quick_creating = False
        yield rx.toast.success(
            f"Projekt '{project.code}' angelegt.", position="top-right"
        )

    @rx.event
    @requires_admin
    async def add_project_to_employee_grid(
        self, form_data: dict
    ) -> AsyncGenerator[Any]:
        project_id_raw = self.add_project_selected
        if project_id_raw == NEW_PROJECT_VALUE:
            yield rx.toast.error(
                "Bitte das neue Projekt zuerst anlegen.", position="top-right"
            )
            return
        try:
            project_id = int(project_id_raw)
            role_id = int(form_data.get("role_id") or "")
        except TypeError, ValueError:
            yield rx.toast.error(
                "Bitte Projekt und Rolle auswählen.", position="top-right"
            )
            return
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
                existing = await capacity_repo.find_by_project_and_employee(
                    session, project_id, emp["real_id"]
                )
                if not any(c.role_id == role_id for c in existing):
                    session.add(
                        CapacityEntity(
                            project_id=project_id,
                            employee_id=emp["real_id"],
                            role_id=role_id,
                            start_date=project.start_date,
                            end_date=project.end_date,
                            hours_per_week=40.0,
                        )
                    )
                    await session.commit()
            self.add_project_emp_id = ""
            self._reset_quick_create()
            yield PlanningStore.refresh
        except Exception:
            log.exception("Failed to add project")
            yield rx.toast.error(
                "Projekt konnte nicht zugewiesen werden.", position="top-right"
            )

    def _drop_pending_edits(self, emp_id: str, project_id: int) -> None:
        """Forget unsaved edits of a row that is being removed."""
        code = next(
            (p["code"] for p in self.project_meta if p["real_id"] == project_id), None
        )
        if code is None:
            return
        prefix = f"{emp_id}|{code}|"
        self.dirty_keys = [k for k in self.dirty_keys if not k.startswith(prefix)]
        self.hidden_edits = {
            k: v for k, v in self.hidden_edits.items() if not k.startswith(prefix)
        }

    @rx.event
    @requires_admin
    async def remove_project_from_employee_grid(
        self, emp_id: str, project_id: int
    ) -> AsyncGenerator[Any]:
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
            self._drop_pending_edits(emp_id, project_id)
            yield PlanningStore.refresh
            yield rx.toast.info("Projektzuweisung entfernt.", position="top-right")
        except Exception:
            log.exception("Failed to remove project")
            yield rx.toast.error(
                "Projektzuweisung konnte nicht entfernt werden.", position="top-right"
            )
