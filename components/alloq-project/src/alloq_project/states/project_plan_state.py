"""State for the 'Projekt planen' modal."""

from __future__ import annotations

import datetime
import logging
import math
from collections.abc import AsyncGenerator
from typing import Any, TypedDict

import reflex as rx
from alloq_commons.entities import CapacityAllocationEntity
from alloq_commons.repositories import capacity_allocation_repo

from appkit_commons.database.session import get_asyncdb_session

log = logging.getLogger(__name__)


class _BarData(TypedDict):
    pt: str
    h_pct: str


class _PreviewRow(TypedDict):
    id: int
    name: str
    role: str
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

WORKDAYS_PER_WEEK = 5
PT_QUANTA_PER_WEEK = 4  # weekly steps: 0, 0.25, 0.5, 0.75, 1.0 * cap


def _distribute(
    total_pt: float,
    weeks: int,
    ramp_up: int,
    ramp_down: int,
    cap_per_week: float | None = None,
) -> list[float]:
    """Distribute total PT over weeks following ramp shape.

    If ``cap_per_week`` is provided, each weekly value snaps to one of the
    allowed steps {0, 0.25, 0.5, 0.75, 1.0} * cap_per_week (quantum = cap/4).
    Total PT is preserved as closely as possible by greedily adding/removing
    quanta from weeks with the largest positive/negative fractional residual.
    """
    if weeks <= 0:
        return []
    ramp_up = max(0, min(ramp_up, weeks))
    ramp_down = max(0, min(ramp_down, weeks - ramp_up))
    plateau = max(weeks - ramp_up - ramp_down, 0)
    weights: list[float] = []
    weights.extend((i + 1) / (ramp_up + 1) for i in range(ramp_up))
    weights.extend(1.0 for _ in range(plateau))
    weights.extend((ramp_down - i) / (ramp_down + 1) for i in range(ramp_down))
    if not weights:
        return []
    total_w = sum(weights)
    plateau_value = total_pt / total_w if total_w else 0.0
    if cap_per_week is not None and plateau_value > cap_per_week:
        plateau_value = cap_per_week
    raw = [w * plateau_value for w in weights]
    if cap_per_week is None or cap_per_week <= 0:
        return [round(v, 2) for v in raw]
    quantum = cap_per_week / PT_QUANTA_PER_WEEK
    if quantum <= 0:
        return [0.0] * weeks
    target_q = round(total_pt / quantum)
    target_q = max(0, min(target_q, weeks * PT_QUANTA_PER_WEEK))
    snapped = [max(0, min(PT_QUANTA_PER_WEEK, round(v / quantum))) for v in raw]
    diff = target_q - sum(snapped)
    if diff != 0:
        residuals = sorted(
            ((raw[i] / quantum - snapped[i], i) for i in range(weeks)),
            reverse=diff > 0,
        )
        for _, i in residuals:
            if diff == 0:
                break
            if diff > 0 and snapped[i] < PT_QUANTA_PER_WEEK:
                snapped[i] += 1
                diff -= 1
            elif diff < 0 and snapped[i] > 0:
                snapped[i] -= 1
                diff += 1
    return [round(s * quantum, 2) for s in snapped]


def _weeks_between(start: datetime.date, end: datetime.date) -> int:
    if end < start:
        return 0
    return (end - start).days // 7 + 1


def _default_gtk(total_pt: int, weeks: int) -> float:
    """Pick GTK so total_pt fits weeks * 5 PT/week, rounded up to .5."""
    if weeks <= 0 or total_pt <= 0:
        return 0.5
    raw = total_pt / (weeks * WORKDAYS_PER_WEEK)
    return max(0.5, min(30.0, math.ceil(raw * 2) / 2))


class ProjectPlanState(rx.State):
    """Multi-step planning modal state."""

    is_open: bool = False
    step: int = 0  # 0=project select, 1=Verteilung, 2=Mitarbeiter, 3=Vorschau

    # Step 0: project selection
    search: str = ""
    selected_project_id: str = ""
    selected_project_code: str = ""
    selected_project_name: str = ""
    selected_project_color: str = "var(--mantine-color-yellow-5)"
    start_iso: str = ""  # YYYY-MM-DD
    end_iso: str = ""

    # Step 1: distribution
    total_pt: int = 100
    ramp_up: int = 0
    ramp_down: int = 0
    gtk_count: float = 5.0

    # Step 2: employees
    required_role_ids: list[int] = []
    selected_employee_ids: list[int] = []
    employee_role_filter: str = "all"  # "all" | role_id as str
    employee_pool: list[dict[str, Any]] = []  # snapshot from PlanningState
    role_options_data: list[dict[str, str]] = []  # snapshot from PlanningState
    # role_id, role_name, person_days
    required_capacity_snapshot: list[dict[str, Any]] = []
    # employee_id (str) -> already-planned PT in project timeframe (excl. this project)
    planned_pt_by_employee: dict[str, float] = {}
    # employee_id (str) -> PT user wants to plan for this project
    planned_by_employee: dict[str, float] = {}
    # employee_id (str) -> chosen role_id for this project
    role_by_employee: dict[str, int] = {}
    # role_id (str) -> role name lookup
    role_name_by_id: dict[str, str] = {}

    @rx.var(cache=True)
    def num_weeks(self) -> int:
        if not self.start_iso or not self.end_iso:
            return 0
        try:
            s = datetime.date.fromisoformat(self.start_iso)
            e = datetime.date.fromisoformat(self.end_iso)
        except ValueError:
            return 0
        return _weeks_between(s, e)

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
        return _distribute(
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
    def shortfall(self) -> bool:
        return self.distribution_sum < float(self.total_pt) - 0.5

    @rx.var(cache=True)
    def shortfall_msg(self) -> str:
        return (
            f"Kapazität zu knapp: nur {self.distribution_sum:.0f} von "
            f"{self.total_pt} PT passen. Projekt verlängern oder Limit erhöhen."
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
            s = datetime.date.fromisoformat(self.start_iso)
            e = datetime.date.fromisoformat(self.end_iso)
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
            start = datetime.date.fromisoformat(self.start_iso)
        except ValueError:
            return []
        segs: list[dict[str, str]] = []
        for i in range(self.effective_weeks):
            d = start + datetime.timedelta(days=7 * i)
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
    def open_modal(self) -> None:
        self.is_open = True
        self.step = 0
        self.search = ""

    @rx.event
    def close_modal(self) -> None:
        self.is_open = False

    @rx.event
    def set_search(self, value: str) -> None:
        self.search = value

    @rx.event
    async def select_project(self, pid: int) -> None:
        from alloq_project.states.planning_state import (  # noqa: PLC0415
            PlanningState,
        )

        planning = await self.get_state(PlanningState)
        proj = next((p for p in planning.available_projects if p.id == pid), None)
        if not proj:
            return
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
        self.gtk_count = _default_gtk(self.total_pt, weeks)
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
                "role_ids": list(e.role_ids),
                "seniority": e.seniority or "",
                "workload_percent": int(e.workload_percent or 100),
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
        self.planned_pt_by_employee = await self._load_planned_pt(
            proj.id, proj.start_date, proj.end_date
        )
        self.planned_by_employee = {}
        self.role_by_employee = {}
        self.role_name_by_id = {str(r.id): r.name for r in planning.available_roles}
        self.step = 1

    async def _load_planned_pt(
        self,
        project_id: int,
        start: datetime.date | None,
        end: datetime.date | None,
    ) -> dict[str, float]:
        """Sum prior PT per employee in [start, end], excluding current project."""
        if not start or not end:
            return {}
        totals: dict[str, float] = {}
        try:
            async with get_asyncdb_session() as session:
                rows = await capacity_allocation_repo.find_in_range(session, start, end)
                for r in rows:
                    if r.project_id == project_id:
                        continue
                    key = str(r.employee_id)
                    totals[key] = totals.get(key, 0.0) + float(r.person_days or 0.0)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load existing allocations: %s", exc)
            return {}
        return totals

    def num_weeks_from(self, start: str, end: str) -> int:
        try:
            s = datetime.date.fromisoformat(start)
            e = datetime.date.fromisoformat(end)
        except ValueError:
            return 0
        return _weeks_between(s, e)

    @rx.event
    def next_step(self) -> None:
        if self.step < 3:  # noqa: PLR2004
            self.step += 1

    @rx.event
    def prev_step(self) -> None:
        if self.step > 0:
            self.step -= 1

    @rx.event
    def set_num_weeks(self, value: float | str) -> None:
        """Edit week count by adjusting end_iso from start_iso."""
        try:
            n = int(float(value))
        except (ValueError, TypeError):
            return
        n = max(1, n)
        if not self.start_iso:
            return
        try:
            s = datetime.date.fromisoformat(self.start_iso)
        except ValueError:
            return
        self.end_iso = (s + datetime.timedelta(days=7 * n - 1)).isoformat()
        self.ramp_up = min(self.ramp_up, n)
        self.ramp_down = min(self.ramp_down, n)

    @rx.event
    def set_total_pt(self, value: int | str) -> None:
        try:
            v = int(value) if value != "" else 0
        except (ValueError, TypeError):
            return
        self.total_pt = max(0, v)

    @rx.event
    def set_ramp_up(self, value: float | str) -> None:
        try:
            v = int(float(value))
        except (ValueError, TypeError):
            return
        self.ramp_up = max(0, min(v, self.num_weeks))

    @rx.event
    def set_ramp_down(self, value: float | str) -> None:
        try:
            v = int(float(value))
        except (ValueError, TypeError):
            return
        self.ramp_down = max(0, min(v, self.num_weeks))

    @rx.event
    def set_gtk_count(self, value: float | str) -> None:
        try:
            v = float(value)
        except (ValueError, TypeError):
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
        weeks = self.num_weeks
        out: list[dict[str, Any]] = []
        for e in self.employee_pool:
            if not self._matches_filter(e["role_ids"]):
                continue
            wp = int(e.get("workload_percent", 100))
            gross = round(weeks * WORKDAYS_PER_WEEK * (wp / 100), 1)
            planned_other = float(self.planned_pt_by_employee.get(str(e["id"]), 0.0))
            net = max(0.0, round(gross - planned_other, 1))
            available_label = f"{net:g} PT"
            sub_label = f"{wp}% · belegt {planned_other:g} / {gross:g} PT"
            plan_pt = float(self.planned_by_employee.get(str(e["id"]), 0.0))
            plan_pct = round((plan_pt / net) * 100, 0) if net > 0 else 0.0
            role_id = self._emp_role_id(e)
            out.append(
                {
                    "id": e["id"],
                    "name": e["name"],
                    "roles": e["roles"],
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

    def _net_pt_for(self, e: dict[str, Any], weeks: int) -> float:
        wp = int(e.get("workload_percent", 100))
        gross = weeks * WORKDAYS_PER_WEEK * (wp / 100)
        planned = float(self.planned_pt_by_employee.get(str(e["id"]), 0.0))
        return max(0.0, gross - planned)

    @rx.var(cache=True)
    def available_capacity_pt(self) -> float:
        """Net PT (gross minus already-planned) across the pool over project weeks."""
        weeks = self.num_weeks
        if weeks <= 0:
            return 0.0
        return round(sum(self._net_pt_for(e, weeks) for e in self.employee_pool), 1)

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
        weeks = self.num_weeks
        if weeks <= 0:
            return 0.0
        emp = next((e for e in self.employee_pool if e["id"] == eid), None)
        if emp is None:
            return 0.0
        wp = int(emp.get("workload_percent", 100))
        gross = weeks * WORKDAYS_PER_WEEK * (wp / 100)
        prior = float(self.planned_pt_by_employee.get(str(eid), 0.0))
        return max(0.0, round(gross - prior, 1))

    @rx.var(cache=True)
    def preview_rows(self) -> list[_PreviewRow]:
        """Per-employee planned distribution for the preview step."""
        weeks = self.effective_weeks
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
            except (ValueError, TypeError):
                continue
        sel = set(self.selected_employee_ids)
        for emp in self.employee_pool:
            eid = emp["id"]
            if eid not in sel:
                continue
            pt = float(self.planned_by_employee.get(str(eid), 0.0))
            if pt <= 0:
                continue
            rid = self._emp_role_id(emp)
            wp = int(emp.get("workload_percent", 100))
            cap_per_week = WORKDAYS_PER_WEEK * (wp / 100)
            weekly = _distribute(
                pt, weeks, self.ramp_up, self.ramp_down, cap_per_week=cap_per_week
            )
            wmax = max(weekly) if weekly else 0.0
            bars: list[_BarData] = [
                {
                    "pt": f"{v:g}",
                    "h_pct": f"{(v / wmax * 100) if wmax > 0 else 0:.1f}",
                }
                for v in weekly
            ]
            rows.append(
                _PreviewRow(
                    id=int(eid),
                    name=str(emp["name"]),
                    role=role_label.get(rid, ""),
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
        except (ValueError, TypeError):
            return
        cap = self._available_pt_for(eid)
        v = max(0.0, min(round(v, 1), cap))
        self.planned_by_employee = {**self.planned_by_employee, str(eid): v}

    @rx.event
    def set_emp_planned_pct(self, eid: int, value: float | str) -> None:
        try:
            pct = float(value) if value != "" else 0.0
        except (ValueError, TypeError):
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

    @rx.event
    def set_emp_role(self, eid: int, value: str) -> None:
        try:
            rid = int(value)
        except (ValueError, TypeError):
            return
        self.role_by_employee = {**self.role_by_employee, str(eid): rid}

    def _project_start_monday(self) -> datetime.date | None:
        if not self.start_iso:
            return None
        try:
            d = datetime.date.fromisoformat(self.start_iso)
        except ValueError:
            return None
        return d - datetime.timedelta(days=d.weekday())

    def _build_allocation_rows(self) -> list[CapacityAllocationEntity]:
        """Materialize per-employee planned PT into weekly rows using ramp shape."""
        try:
            project_id = int(self.selected_project_id)
        except (ValueError, TypeError):
            return []
        emp_ids = list(self.selected_employee_ids)
        if not emp_ids:
            return []
        monday = self._project_start_monday()
        if monday is None:
            return []
        emp_role: dict[int, int] = {}
        for emp in self.employee_pool:
            if emp["id"] in emp_ids:
                rid = self._emp_role_id(emp)
                if rid:
                    emp_role[emp["id"]] = rid
        if not emp_role:
            return []
        weeks = self.effective_weeks
        rows: list[CapacityAllocationEntity] = []
        for emp_id, role_id in emp_role.items():
            pt = float(self.planned_by_employee.get(str(emp_id), 0.0))
            if pt <= 0 or weeks <= 0:
                continue
            emp = next((e for e in self.employee_pool if e["id"] == emp_id), None)
            wp = int(emp.get("workload_percent", 100)) if emp else 100
            cap_per_week = WORKDAYS_PER_WEEK * (wp / 100)
            weekly = _distribute(
                pt, weeks, self.ramp_up, self.ramp_down, cap_per_week=cap_per_week
            )
            for w_idx, w_pt in enumerate(weekly):
                if w_pt <= 0:
                    continue
                rows.append(
                    CapacityAllocationEntity(
                        project_id=project_id,
                        employee_id=emp_id,
                        role_id=role_id,
                        week_start=monday + datetime.timedelta(days=7 * w_idx),
                        person_days=round(w_pt, 2),
                    )
                )
        return rows

    @rx.event
    async def save_plan(self) -> AsyncGenerator[Any, None]:
        """Persist the plan as weekly capacity_allocations and close the modal."""
        if not self.selected_project_id:
            yield rx.toast.error("Kein Projekt ausgewählt.", position="top-right")
            return
        if not self.selected_employee_ids:
            yield rx.toast.error(
                "Bitte mindestens einen Mitarbeiter wählen.", position="top-right"
            )
            return
        rows = self._build_allocation_rows()
        try:
            project_id = int(self.selected_project_id)
        except (ValueError, TypeError):
            yield rx.toast.error("Ungültige Projekt-ID.", position="top-right")
            return
        try:
            async with get_asyncdb_session() as session:
                await capacity_allocation_repo.replace_for_project(
                    session, project_id, rows
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to persist plan: %s", exc)
            yield rx.toast.error(
                f"Speichern fehlgeschlagen: {exc}", position="top-right"
            )
            return
        self.is_open = False
        yield rx.toast.success(
            f"Plan gespeichert ({len(rows)} Zuweisungen).",
            position="top-right",
        )
        from alloq_project.states.planning_grid_state import (  # noqa: PLC0415
            PlanningGridState,
        )

        yield PlanningGridState.load_grid_data

    _ = Any  # mark Any used
