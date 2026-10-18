"""State for the 'Projekt planen' modal."""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import AsyncGenerator
from typing import Any, TypedDict

import reflex as rx
from alloq_commons.access import requires_editor
from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.models.project import Project
from alloq_commons.repositories import capacity_allocation_repo, public_holiday_repo
from alloq_commons.services.utilization import (
    AbsencePeriod,
    UtilizationService,
)
from alloq_project.services.plan_distribution import (
    WORKDAYS_PER_WEEK,
    default_gtk,
    distribute,
    distribute_with_avail,
    week_free_days,
    weekdays_in,
    weeks_between,
)
from alloq_project.services.resource_planning import (
    PlanTarget,
    apply_resource_plan,
    week_starts,
)

from appkit_commons.database.session import get_asyncdb_session

log = logging.getLogger(__name__)


class _BarData(TypedDict):
    pt: str
    h_pct: str
    absent: bool


class _PreviewRow(TypedDict):
    id: int
    name: str
    role: str
    avatar_color: str
    planned_label: str
    weekly_total: str
    weekly_max: str
    bars: list[_BarData]


GERMAN_MONTHS_LONG = [
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


_PRIOR_NOT_LOADED = (
    "Bestehende Planung konnte nicht geladen werden. "
    "Bitte Projekt bzw. Wochenanzahl erneut wählen."
)


def _absence_periods(emp: dict[str, Any]) -> list[AbsencePeriod]:
    """Absence periods of a pool employee snapshot (ISO strings -> dates)."""
    return [
        AbsencePeriod(
            start_date=dt.date.fromisoformat(a["start"]),
            end_date=dt.date.fromisoformat(a["end"]),
        )
        for a in emp.get("absences", [])
        if a.get("start") and a.get("end")
    ]


def _weeks_from_iso(start: str, end: str) -> int:
    """Weeks touched by an ISO date range; 0 when a date is missing or invalid."""
    try:
        return weeks_between(dt.date.fromisoformat(start), dt.date.fromisoformat(end))
    except ValueError:
        return 0


class ProjectPlanState(rx.State):
    """Multi-step planning modal state."""

    is_open: rx.Field[bool] = rx.field(False)
    is_saving: rx.Field[bool] = rx.field(False)
    # 0=project select, 1=Verteilung, 2=Mitarbeiter, 3=Vorschau
    step: rx.Field[int] = rx.field(0)

    # Step 0: project selection
    search: rx.Field[str] = rx.field("")
    project_pool: rx.Field[list[Project]] = rx.field(default_factory=list)
    selected_project_id: rx.Field[str] = rx.field("")
    selected_project_code: rx.Field[str] = rx.field("")
    selected_project_name: rx.Field[str] = rx.field("")
    selected_project_color: rx.Field[str] = rx.field("var(--mantine-color-yellow-5)")
    start_iso: rx.Field[str] = rx.field("")  # YYYY-MM-DD
    end_iso: rx.Field[str] = rx.field("")

    # Step 1: distribution
    total_pt: rx.Field[int] = rx.field(100)
    ramp_up: rx.Field[int] = rx.field(0)
    ramp_down: rx.Field[int] = rx.field(0)
    gtk_count: rx.Field[float] = rx.field(5.0)

    # Step 2: employees
    required_role_ids: rx.Field[list[int]] = rx.field(default_factory=list)
    selected_employee_ids: rx.Field[list[int]] = rx.field(default_factory=list)
    employee_role_filter: rx.Field[str] = rx.field("all")  # "all" | role_id as str
    # Snapshots from PlanningStore
    employee_pool: rx.Field[list[dict[str, Any]]] = rx.field(default_factory=list)
    role_options_data: rx.Field[list[dict[str, str]]] = rx.field(default_factory=list)
    holiday_dates: rx.Field[list[dt.date]] = rx.field(default_factory=list)
    # role_id, role_name, person_days
    required_capacity_snapshot: rx.Field[list[dict[str, Any]]] = rx.field(
        default_factory=list
    )
    # employee_id (str) -> already-planned PT in project timeframe (excl. this project)
    planned_pt_by_employee: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    # employee_id (str) -> {week_iso: pt} prior allocations (excl. this project)
    planned_pt_by_employee_week: rx.Field[dict[str, dict[str, float]]] = rx.field(
        default_factory=dict
    )
    # _prior_key() of the window the prior-allocation snapshot was loaded for
    prior_loaded_for: rx.Field[str] = rx.field("")
    # employee_id (str) -> PT user wants to plan for this project
    planned_by_employee: rx.Field[dict[str, float]] = rx.field(default_factory=dict)
    # employee_id (str) -> chosen role_id for this project
    role_by_employee: rx.Field[dict[str, int]] = rx.field(default_factory=dict)
    # role_id (str) -> role name lookup
    role_name_by_id: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    # role_id (str) -> {"ramp_up": bool, "ramp_down": bool}
    # ramp_up=True  -> role IS needed during ramp-up phase (durchgehend ab Start)
    # ramp_up=False -> role ramps up gradually with the project
    role_ramps_by_id: rx.Field[dict[str, dict[str, bool]]] = rx.field(
        default_factory=dict
    )

    @rx.var(cache=True)
    def num_weeks(self) -> int:
        return _weeks_from_iso(self.start_iso, self.end_iso)

    @rx.var(cache=True)
    def effective_weeks(self) -> int:
        """Weeks actually used. Shortens if GTK provides surplus capacity."""
        nw = self.num_weeks
        if nw == 0:
            return 0
        cap = self.gtk_count * WORKDAYS_PER_WEEK
        if cap <= 0:
            return nw
        needed = math.ceil(self.total_pt / cap + self.ramp_up / 2 + self.ramp_down / 2)
        return max(1, min(nw, needed))

    @rx.var(cache=True)
    def cap_value(self) -> float:
        """Cap PT/week."""
        return self.gtk_count * WORKDAYS_PER_WEEK

    @rx.var(cache=True)
    def cap_label(self) -> str:
        cv = self.cap_value
        return f"= {cv:.1f} PT/Wo." if cv > 0 else ""

    @rx.var(cache=True)
    def distribution(self) -> list[float]:
        return distribute(
            float(self.total_pt),
            self.effective_weeks,
            self.ramp_up,
            self.ramp_down,
            cap_per_week=self.gtk_count * WORKDAYS_PER_WEEK,
        )

    @rx.var(cache=True)
    def distribution_max(self) -> float:
        d = self.distribution
        return max(d) if d else 1.0

    @rx.var(cache=True)
    def chart_max(self) -> float:
        """Y-axis max: max of distribution or cap, whichever larger."""
        cap = self.gtk_count * WORKDAYS_PER_WEEK
        return max(self.distribution_max, cap, 1.0)

    @rx.var(cache=True)
    def distribution_sum(self) -> float:
        return round(sum(self.distribution), 1)

    @rx.var(cache=True)
    def distribution_gtk(self) -> float:
        """Average GTK across weeks based on max usage."""
        if self.distribution_max == 0:
            return 0.0
        return round(self.distribution_max / WORKDAYS_PER_WEEK, 1)

    @rx.var(cache=True)
    def shape_capacity(self) -> float:
        """Max PT this ramp shape fits given effective_weeks and cap."""
        weeks = self.effective_weeks
        if weeks <= 0 or self.cap_value <= 0:
            return 0.0
        r = min(self.ramp_up, weeks)
        d = min(self.ramp_down, max(0, weeks - r))
        sum_weights = max(0.0, weeks - r / 2.0 - d / 2.0)
        return round(self.cap_value * sum_weights, 1)

    @rx.var(cache=True)
    def shortfall(self) -> bool:
        return float(self.total_pt) > self.shape_capacity + 0.5

    @rx.var(cache=True)
    def shortfall_msg(self) -> str:
        return (
            f"Kapazität zu knapp: nur {self.shape_capacity:.0f} von "
            f"{self.total_pt} PT passen in {self.effective_weeks} Wochen "
            f"(Cap {self.cap_value:.1f} PT/Wo). "
            "Projekt verlängern, Ramps verkürzen oder Kapazität erhöhen."
        )

    @rx.var(cache=True)
    def cap_height_pct(self) -> float:
        """Cap line position in chart as % of chart height."""
        if self.cap_value <= 0 or self.chart_max == 0:
            return 0.0
        return min(100.0, (self.cap_value / self.chart_max) * 100.0)

    @rx.var(cache=True)
    def date_range_label(self) -> str:
        if not self.start_iso or not self.end_iso:
            return "—"
        try:
            s = dt.date.fromisoformat(self.start_iso)
            e = dt.date.fromisoformat(self.end_iso)
        except ValueError:
            return "—"
        sf = f"{s.day:02d}. {GERMAN_MONTHS_LONG[s.month - 1]} {s.year}"
        ef = f"{e.day:02d}. {GERMAN_MONTHS_LONG[e.month - 1]} {e.year}"
        return f"{sf} → {ef}"

    @rx.var(cache=True)
    def month_segments(self) -> list[dict[str, str]]:
        """Returns [{'label': 'Apr 26', 'span': '3'}] per month for chart."""
        if not self.start_iso or self.effective_weeks == 0:
            return []
        try:
            start = dt.date.fromisoformat(self.start_iso)
        except ValueError:
            return []
        segs: list[dict[str, str]] = []
        for i in range(self.effective_weeks):
            d = start + dt.timedelta(days=7 * i)
            label = f"{GERMAN_MONTHS_LONG[d.month - 1]} {d.year % 100}"
            if segs and segs[-1]["label"] == label:
                segs[-1]["span"] = str(int(segs[-1]["span"]) + 1)
            else:
                segs.append({"label": label, "span": "1"})
        return segs

    @rx.var(cache=True)
    def title(self) -> str:
        if self.selected_project_code:
            return f"Projekt planen: {self.selected_project_code}"
        return "Projekt planen"

    @rx.event
    @requires_editor
    async def open_modal(self) -> None:
        from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
            PlanningStore,
        )

        planning = await self.get_state(PlanningStore)
        self.project_pool = list(planning.available_projects)
        self.is_open = True
        self.step = 0
        self.search = ""

    @rx.event
    def close_modal(self) -> None:
        self.is_open = False

    @rx.event
    def set_search(self, value: str) -> None:
        self.search = value

    @rx.var(cache=True)
    def visible_projects(self) -> list[Project]:
        """Projects with state 'Geplant' filtered by case-insensitive search."""
        needle = self.search.strip().lower()
        return [
            p
            for p in self.project_pool
            if p.state == ProjectStateEnum.PLANNED
            and (
                not needle
                or needle in (p.name_de or "").lower()
                or needle in (p.code or "").lower()
            )
        ]

    @rx.event
    @requires_editor
    async def select_project(self, pid: int) -> Any:
        from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
            PlanningStore,
        )

        planning = await self.get_state(PlanningStore)
        proj = next((p for p in planning.available_projects if p.id == pid), None)
        if not proj:
            return None
        self.selected_project_id = str(proj.id)
        self.selected_project_code = proj.code or ""
        self.selected_project_name = proj.name_de or ""
        self.selected_project_color = proj.color or "var(--mantine-color-yellow-5)"
        self.start_iso = proj.start_date.isoformat() if proj.start_date else ""
        self.end_iso = proj.end_date.isoformat() if proj.end_date else ""
        team_count = max(len(proj.team_initials), 1)
        weeks = self.num_weeks_from(self.start_iso, self.end_iso)
        pt_from_roles = sum(rc.person_days for rc in proj.required_capacities)
        self.total_pt = pt_from_roles or team_count * max(weeks, 1) * 4
        self.ramp_up = 0
        self.ramp_down = 0
        self.gtk_count = default_gtk(self.total_pt, weeks)
        self.required_role_ids = sorted(
            {rc.role_id for rc in proj.required_capacities if rc.role_id}
        )
        self.selected_employee_ids = []
        self.employee_role_filter = "all"
        self.employee_pool = [
            {
                "id": e.id,
                "name": f"{e.first_name} {e.last_name}".strip(),
                "roles": ", ".join(e.role_names),
                "avatar_color": e.avatar_color,
                "role_ids": list(e.role_ids),
                "seniority": e.seniority or "",
                "workload_percent": int(e.workload_percent or 100),
                "internal_hours": int(e.internal_hours or 0),
                "absences": [
                    {
                        "start": a.start_date.isoformat() if a.start_date else "",
                        "end": a.end_date.isoformat() if a.end_date else "",
                    }
                    for a in (e.absences or [])
                    if a.start_date and a.end_date
                ],
            }
            for e in planning.available_employees
        ]
        opts: list[dict[str, str]] = [{"value": "all", "label": "Alle"}]
        opts.extend(
            {"value": str(r.id), "label": r.name}
            for r in planning.available_roles
            if not self.required_role_ids or r.id in self.required_role_ids
        )
        self.role_options_data = opts
        self.required_capacity_snapshot = [
            {
                "role_id": rc.role_id,
                "role_name": rc.role_name or "",
                "person_days": int(rc.person_days),
            }
            for rc in proj.required_capacities
            if rc.role_id
        ]
        self.planned_by_employee = {}
        self.role_by_employee = {}
        self.role_name_by_id = {str(r.id): r.name for r in planning.available_roles}
        self.role_ramps_by_id = {
            str(r.id): {"ramp_up": bool(r.ramp_up), "ramp_down": bool(r.ramp_down)}
            for r in planning.available_roles
        }
        if error := await self._refresh_prior_allocations():
            return error
        self.step = 1
        return None

    async def _load_planned_pt_per_week(
        self,
        project_id: int,
        start: dt.date | None,
        end: dt.date | None,
    ) -> dict[str, dict[str, float]]:
        """Prior PT per employee per week in [start, end], excluding current project.

        Returns {employee_id_str: {week_iso: pt}}. week_iso is the Monday ISO date.
        Also loads the public holidays of the window into ``holiday_dates``.
        """
        weeks = week_starts(start, end) if start and end else []
        if not weeks or not end:
            return {}
        out: dict[str, dict[str, float]] = {}
        async with get_asyncdb_session() as session:
            holidays = await public_holiday_repo.find_by_date_range(
                session, weeks[0], end
            )
            self.holiday_dates = sorted(h.date for h in holidays if h.date)
            rows = await capacity_allocation_repo.find_in_range(session, weeks[0], end)
            for r in rows:
                if r.project_id == project_id or r.week_start is None:
                    continue
                bucket = out.setdefault(str(r.employee_id), {})
                wk = r.week_start.isoformat()
                bucket[wk] = bucket.get(wk, 0.0) + float(r.person_days or 0.0)
        return out

    @rx.event
    def num_weeks_from(self, start: str, end: str) -> int:
        return _weeks_from_iso(start, end)

    def _prior_key(self) -> str:
        return f"{self.selected_project_id}|{self.start_iso}|{self.end_iso}"

    @rx.var
    def prior_ready(self) -> bool:
        """True when the prior-allocation snapshot matches the current window."""
        return bool(self.prior_loaded_for) and self.prior_loaded_for == (
            self._prior_key()
        )

    @rx.event
    def next_step(self) -> Any:
        if self.step == 0 and not self.selected_project_id:
            return None
        if not self.prior_ready:
            return rx.toast.error(_PRIOR_NOT_LOADED, position="top-right")
        if self.step < 3:  # noqa: PLR2004
            self.step += 1
        return None

    @rx.event
    def prev_step(self) -> None:
        if self.step > 0:
            self.step -= 1

    async def _refresh_prior_allocations(self) -> Any:
        """Re-fetch prior allocations and holidays for [start_iso, end_iso].

        Returns an error toast when the data cannot be loaded, so capacity is
        never computed from an empty (all free) snapshot.
        """
        if not self.selected_project_id or not self.start_iso or not self.end_iso:
            return None
        try:
            pid = int(self.selected_project_id)
            s = dt.date.fromisoformat(self.start_iso)
            e = dt.date.fromisoformat(self.end_iso)
        except ValueError, TypeError:
            return None
        try:
            by_week = await self._load_planned_pt_per_week(pid, s, e)
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to load existing allocations: %s", exc)
            self.prior_loaded_for = ""
            return rx.toast.error(_PRIOR_NOT_LOADED, position="top-right")
        self.prior_loaded_for = self._prior_key()
        self.planned_pt_by_employee_week = by_week
        self.planned_pt_by_employee = {
            eid: round(sum(week_map.values()), 2) for eid, week_map in by_week.items()
        }
        return None

    @rx.event
    @requires_editor
    async def set_num_weeks(self, value: float | str) -> Any:
        """Edit week count by moving end_iso to the Sunday of the n-th week."""
        try:
            n = int(float(value))
        except ValueError, TypeError:
            return None
        monday = self._project_start_monday()
        if monday is None:
            return None
        self.end_iso = (monday + dt.timedelta(days=7 * max(1, n) - 1)).isoformat()
        return await self._refresh_prior_allocations()

    @rx.event
    def set_total_pt(self, value: int | str) -> None:
        try:
            v = int(value) if value != "" else 0
        except ValueError, TypeError:
            return
        self.total_pt = max(0, v)

    @rx.event
    def set_ramp_up(self, value: float | str) -> None:
        try:
            v = int(float(value))
        except ValueError, TypeError:
            return
        self.ramp_up = max(0, min(v, self.num_weeks))

    @rx.event
    def set_ramp_down(self, value: float | str) -> None:
        try:
            v = int(float(value))
        except ValueError, TypeError:
            return
        self.ramp_down = max(0, min(v, self.num_weeks))

    @rx.event
    def set_gtk_count(self, value: float | str) -> None:
        try:
            v = float(value)
        except ValueError, TypeError:
            return
        self.gtk_count = max(0.5, round(v * 2) / 2)

    # ---- Step 2: employees ----

    def _matches_filter(self, role_ids: list[int]) -> bool:
        if self.employee_role_filter == "all":
            if not self.required_role_ids:
                return True
            return any(rid in self.required_role_ids for rid in role_ids)
        try:
            target = int(self.employee_role_filter)
        except ValueError:
            return True
        return target in role_ids

    @rx.var(cache=True)
    def filtered_employees(self) -> list[dict[str, Any]]:
        """Employees matching role filter, with selection state and capacity labels."""
        weeks_starts = self._project_weeks()
        out: list[dict[str, Any]] = []
        for e in self.employee_pool:
            if not self._matches_filter(e["role_ids"]):
                continue
            wp = int(e.get("workload_percent", 100))
            gross = self._gross_capacity(e, weeks_starts)
            planned_other = float(self.planned_pt_by_employee.get(str(e["id"]), 0.0))
            net = self._free_pt(e, weeks_starts)
            available_label = f"{net:g} PT".replace(".", ",")
            sub_label = f"{wp}% · belegt {planned_other:g} / {gross:g} PT".replace(
                ".", ","
            )
            plan_pt = float(self.planned_by_employee.get(str(e["id"]), 0.0))
            plan_pct = round((plan_pt / net) * 100, 0) if net > 0 else 0.0
            role_id = self._emp_role_id(e)
            out.append(
                {
                    "id": e["id"],
                    "name": e["name"],
                    "roles": e["roles"],
                    "avatar_color": e.get("avatar_color", ""),
                    "seniority": e["seniority"],
                    "available_label": available_label,
                    "sub_label": sub_label,
                    "available_pt": net,
                    "planned_pt": plan_pt,
                    "planned_pct": int(plan_pct),
                    "role_value": str(role_id) if role_id else "",
                    "role_options": self._emp_role_options(e.get("role_ids", [])),
                    "selected": e["id"] in self.selected_employee_ids,
                }
            )
        return out

    @rx.var(cache=True)
    def selected_count(self) -> int:
        return len(self.selected_employee_ids)

    @rx.var(cache=True)
    def filtered_count(self) -> int:
        return len(self.filtered_employees)

    def _project_weeks(self) -> list[dt.date]:
        """Mon-anchored week starts spanning the project window."""
        if not self.start_iso:
            return []
        try:
            s = dt.date.fromisoformat(self.start_iso)
        except ValueError:
            return []
        monday = s - dt.timedelta(days=s.weekday())
        return [monday + dt.timedelta(weeks=i) for i in range(self.num_weeks)]

    def _weekly_avail(
        self, emp: dict[str, Any], weeks_starts: list[dt.date]
    ) -> list[float]:
        """Per-week PT free for this project.

        weekly_avail[i] = work_days_per_week - absence_days - capped_internal
        - prior_allocations_in_other_projects[week], floored at 0.
        work_days_per_week scales by workload_percent. Internal hours capped
        against remaining capacity after absence.
        """
        if not weeks_starts:
            return []
        absences = _absence_periods(emp)
        internal_hours = int(emp.get("internal_hours", 0))
        wp = int(emp.get("workload_percent", 100))
        holidays = set(self.holiday_dates)
        prior_by_week = self.planned_pt_by_employee_week.get(str(emp["id"]), {})
        window = self._window()
        out: list[float] = []
        for ws in weeks_starts:
            prior = float(prior_by_week.get(ws.isoformat(), 0.0))
            free = week_free_days(ws, holidays, wp, absences, internal_hours) - prior
            if window is not None:  # partial first/last week: only days in window
                in_window = weekdays_in(ws, *window)
                free = min(free, UtilizationService.apply_workload(in_window, wp))
            out.append(max(0.0, free))
        return out

    def _weekly_absent(
        self, emp: dict[str, Any], weeks_starts: list[dt.date]
    ) -> list[bool]:
        """Per-week absence flag (true if any absence overlaps the week)."""
        if not weeks_starts:
            return []
        absences = _absence_periods(emp)
        return [
            UtilizationService.absence_days_in_week(absences, ws) > 0
            for ws in weeks_starts
        ]

    def _gross_capacity(
        self, emp: dict[str, Any], weeks_starts: list[dt.date]
    ) -> float:
        """Gross capacity over project window (absence+internal subtracted)."""
        if not weeks_starts:
            return 0.0
        absences = _absence_periods(emp)
        internal_hours = int(emp.get("internal_hours", 0))
        wp = int(emp.get("workload_percent", 100))
        holidays = set(self.holiday_dates)
        total = sum(
            max(0.0, week_free_days(ws, holidays, wp, absences, internal_hours))
            for ws in weeks_starts
        )
        return round(total, 1)

    def _free_pt(self, emp: dict[str, Any], weeks_starts: list[dt.date]) -> float:
        """Free PT this project may use: capacity minus prior other-project alloc."""
        return round(sum(self._weekly_avail(emp, weeks_starts)), 1)

    @rx.var(cache=True)
    def available_capacity_pt(self) -> float:
        """Net PT (gross minus already-planned) across the pool over project weeks."""
        weeks_starts = self._project_weeks()
        if not weeks_starts:
            return 0.0
        return round(sum(self._free_pt(e, weeks_starts) for e in self.employee_pool), 1)

    @rx.var(cache=True)
    def selected_capacity_pt(self) -> float:
        """Sum of user-planned PT across selected employees."""
        sel = {str(eid) for eid in self.selected_employee_ids}
        return round(sum(v for k, v in self.planned_by_employee.items() if k in sel), 1)

    @rx.var(cache=True)
    def required_pt_total(self) -> int:
        """Sum of required PT across roles. Falls back to total_pt if empty."""
        if not self.required_capacity_snapshot:
            return self.total_pt
        return sum(int(r["person_days"]) for r in self.required_capacity_snapshot)

    @rx.var(cache=True)
    def required_roles_display(self) -> list[dict[str, str]]:
        """Per-role required vs assigned PT for selected employees."""
        weeks = self.num_weeks
        sel = set(self.selected_employee_ids)
        role_assigned: dict[int, float] = {}
        if weeks > 0 and sel:
            for e in self.employee_pool:
                if e["id"] not in sel:
                    continue
                rid = self._emp_role_id(e)
                if not rid:
                    continue
                pt = float(self.planned_by_employee.get(str(e["id"]), 0.0))
                role_assigned[rid] = role_assigned.get(rid, 0.0) + pt
        rows: list[dict[str, str]] = []
        for rc in self.required_capacity_snapshot:
            rid = int(rc["role_id"])
            req = int(rc["person_days"])
            assigned = round(role_assigned.get(rid, 0.0), 1)
            rows.append(
                {
                    "role_id": str(rid),
                    "role_name": str(rc["role_name"]),
                    "required_pt": str(req),
                    "assigned_pt": str(assigned),
                    "covered": "true" if 0 < req <= assigned else "false",
                }
            )
        return rows

    def _available_pt_for(self, eid: int) -> float:
        weeks_starts = self._project_weeks()
        if not weeks_starts:
            return 0.0
        emp = next((e for e in self.employee_pool if e["id"] == eid), None)
        if emp is None:
            return 0.0
        return self._free_pt(emp, weeks_starts)

    @rx.var(cache=True)
    def preview_rows(self) -> list[_PreviewRow]:
        """Per-employee planned distribution for the preview step.

        Spans the full project window (num_weeks), not the project-chart
        effective_weeks. Each employee distributes their planned PT across
        the whole window, capped per-week by their own free capacity.
        """
        weeks = self.num_weeks
        rows: list[_PreviewRow] = []
        if weeks <= 0:
            return rows
        role_label: dict[int, str] = {
            int(r["role_id"]): str(r["role_name"])
            for r in self.required_capacity_snapshot
        }
        for opt in self.role_options_data:
            try:
                role_label.setdefault(int(opt["value"]), opt["label"])
            except ValueError, TypeError:
                continue
        sel = set(self.selected_employee_ids)
        weeks_starts = self._project_weeks()
        for emp in self.employee_pool:
            eid = emp["id"]
            if eid not in sel:
                continue
            pt = float(self.planned_by_employee.get(str(eid), 0.0))
            if pt <= 0:
                continue
            rid = self._emp_role_id(emp)
            eff_up, eff_down = self._effective_ramps_for(emp)
            weekly_caps = self._weekly_avail(emp, weeks_starts)
            absent_flags = self._weekly_absent(emp, weeks_starts)
            weekly = distribute_with_avail(pt, weeks, eff_up, eff_down, weekly_caps)
            wmax = max(weekly) if weekly else 0.0
            bars: list[_BarData] = [
                {
                    "pt": f"{v:g}",
                    "h_pct": f"{(v / wmax * 100) if wmax > 0 else 0:.1f}",
                    "absent": absent_flags[i] if i < len(absent_flags) else False,
                }
                for i, v in enumerate(weekly)
            ]
            rows.append(
                _PreviewRow(
                    id=int(eid),
                    name=str(emp["name"]),
                    role=role_label.get(rid, ""),
                    avatar_color=str(emp.get("avatar_color", "")),
                    planned_label=f"{pt:g} PT",
                    weekly_total=f"{sum(weekly):g} PT",
                    weekly_max=f"{wmax:g}",
                    bars=bars,
                )
            )
        return rows

    @rx.var(cache=True)
    def preview_total_pt(self) -> float:
        return self.selected_capacity_pt

    @rx.var(cache=True)
    def preview_emp_count(self) -> int:
        sel = set(self.selected_employee_ids)
        return sum(
            1 for k, v in self.planned_by_employee.items() if v > 0 and int(k) in sel
        )

    @rx.event
    def toggle_employee(self, eid: int) -> None:
        key = str(eid)
        if eid in self.selected_employee_ids:
            self.selected_employee_ids = [
                x for x in self.selected_employee_ids if x != eid
            ]
            self.planned_by_employee = {
                k: v for k, v in self.planned_by_employee.items() if k != key
            }
        else:
            self.selected_employee_ids = [*self.selected_employee_ids, eid]
            if key not in self.planned_by_employee:
                self.planned_by_employee = {
                    **self.planned_by_employee,
                    key: self._available_pt_for(eid),
                }

    @rx.event
    def set_emp_planned_pt(self, eid: int, value: float | str) -> None:
        try:
            v = float(value) if value != "" else 0.0
        except ValueError, TypeError:
            return
        cap = self._available_pt_for(eid)
        v = max(0.0, min(round(v, 1), cap))
        self.planned_by_employee = {**self.planned_by_employee, str(eid): v}

    @rx.event
    def set_emp_planned_pct(self, eid: int, value: float | str) -> None:
        try:
            pct = float(value) if value != "" else 0.0
        except ValueError, TypeError:
            return
        pct = max(0.0, min(pct, 100.0))
        cap = self._available_pt_for(eid)
        pt = round(cap * pct / 100, 1)
        self.planned_by_employee = {**self.planned_by_employee, str(eid): pt}

    @rx.event
    def set_employee_role_filter(self, value: str) -> None:
        self.employee_role_filter = value

    @rx.event
    def select_all_filtered(self) -> None:
        ids = {e["id"] for e in self.filtered_employees}
        merged = set(self.selected_employee_ids) | ids
        self.selected_employee_ids = sorted(merged)
        plans = dict(self.planned_by_employee)
        for eid in ids:
            key = str(eid)
            if key not in plans:
                plans[key] = self._available_pt_for(eid)
        self.planned_by_employee = plans

    @rx.event
    def clear_employee_selection(self) -> None:
        self.selected_employee_ids = []
        self.planned_by_employee = {}

    # ---- Step 3: persistence ----

    def _pick_role_for_employee(self, role_ids: list[int]) -> int:
        """Pick role_id for an employee. Prefer one in required_role_ids."""
        if self.required_role_ids:
            for rid in role_ids:
                if rid in self.required_role_ids:
                    return rid
        return role_ids[0] if role_ids else 0

    def _emp_role_id(self, emp: dict[str, Any]) -> int:
        """Selected role_id (override or auto-picked default)."""
        chosen = self.role_by_employee.get(str(emp["id"]))
        if chosen and chosen in emp.get("role_ids", []):
            return chosen
        return self._pick_role_for_employee(emp.get("role_ids", []))

    def _emp_role_options(self, role_ids: list[int]) -> list[dict[str, str]]:
        return [
            {"value": str(rid), "label": self.role_name_by_id.get(str(rid), str(rid))}
            for rid in role_ids
            if self.role_name_by_id.get(str(rid))
        ]

    def _effective_ramps_for(self, emp: dict[str, Any]) -> tuple[int, int]:
        """Per-employee ramp shape. Role.ramp_up=True means the role is needed
        during ramp-up (durchgehend ab Start) -> no ramp-up shape for that emp.
        """
        rid = self._emp_role_id(emp)
        flags = self.role_ramps_by_id.get(str(rid), {})
        eff_up = 0 if flags.get("ramp_up") else self.ramp_up
        eff_down = 0 if flags.get("ramp_down") else self.ramp_down
        return eff_up, eff_down

    @rx.event
    def set_emp_role(self, eid: int, value: str) -> None:
        try:
            rid = int(value)
        except ValueError, TypeError:
            return
        self.role_by_employee = {**self.role_by_employee, str(eid): rid}

    def _window(self) -> tuple[dt.date, dt.date] | None:
        try:
            return (
                dt.date.fromisoformat(self.start_iso),
                dt.date.fromisoformat(self.end_iso),
            )
        except ValueError:
            return None

    def _project_start_monday(self) -> dt.date | None:
        if not self.start_iso:
            return None
        try:
            d = dt.date.fromisoformat(self.start_iso)
        except ValueError:
            return None
        return d - dt.timedelta(days=d.weekday())

    def _build_plans(
        self,
    ) -> list[tuple[PlanTarget, list[tuple[dt.date, float]]]]:
        """Per selected employee: target and weekly PT (> 0) using the ramp shape.

        Employees without a role or without any planned week are left out, so
        their existing allocations stay untouched on save.
        """
        try:
            project_id = int(self.selected_project_id)
        except ValueError, TypeError:
            return []
        weeks_starts = self._project_weeks()
        selected = set(self.selected_employee_ids)
        plans: list[tuple[PlanTarget, list[tuple[dt.date, float]]]] = []
        for emp in self.employee_pool:
            role_id = self._emp_role_id(emp)
            pt = float(self.planned_by_employee.get(str(emp["id"]), 0.0))
            if emp["id"] not in selected or not role_id or pt <= 0:
                continue
            eff_up, eff_down = self._effective_ramps_for(emp)
            weekly = distribute_with_avail(
                pt,
                len(weeks_starts),
                eff_up,
                eff_down,
                self._weekly_avail(emp, weeks_starts),
            )
            days = [
                (week, round(value, 2))
                for week, value in zip(weeks_starts, weekly, strict=True)
                if value > 0
            ]
            if days:
                plans.append((PlanTarget(project_id, int(emp["id"]), role_id), days))
        return plans

    @rx.event
    @requires_editor
    async def save_plan(self) -> AsyncGenerator[Any]:
        """Persist the plan and close the modal.

        Only the planned employees' allocations on this project inside the
        planning window are replaced (as in the Ressourcen tab); other
        employees and weeks outside the window are kept.
        """
        if self.is_saving:
            return
        window = self._window()
        if not self.selected_project_id or window is None:
            yield rx.toast.error("Kein Projekt ausgewählt.", position="top-right")
            return
        if not self.prior_ready:
            yield rx.toast.error(_PRIOR_NOT_LOADED, position="top-right")
            return
        plans = self._build_plans()
        if not plans:
            yield rx.toast.error(
                "Keine Allokationen geplant. Bitte PT für Mitarbeiter setzen.",
                position="top-right",
            )
            return
        self.is_saving = True
        yield
        try:
            async with get_asyncdb_session() as session:
                for target, days in plans:
                    await apply_resource_plan(session, target, *window, days)
                await session.commit()
        except Exception:
            log.exception("Failed to persist plan")
            yield rx.toast.error(
                "Speichern fehlgeschlagen. Bitte erneut versuchen.",
                position="top-right",
            )
            return
        finally:
            self.is_saving = False
        self.is_open = False
        count = sum(len(days) for _, days in plans)
        yield rx.toast.success(
            f"Plan gespeichert ({count} Zuweisungen).", position="top-right"
        )
        from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
            PlanningStore,
        )

        yield PlanningStore.refresh
