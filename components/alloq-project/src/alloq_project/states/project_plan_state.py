"""State for the 'Projekt planen' modal."""

from __future__ import annotations

import datetime
import logging
import math
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from alloq_commons.entities import CapacityAllocationEntity
from alloq_commons.repositories import capacity_allocation_repo

from appkit_commons.database.session import get_asyncdb_session

log = logging.getLogger(__name__)


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


def _distribute(
    total_pt: float,
    weeks: int,
    ramp_up: int,
    ramp_down: int,
    cap_per_week: float | None = None,
) -> list[float]:
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
    return [round(w * plateau_value, 1) for w in weights]


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
        self.step = 1

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
        """Employees matching role filter, with selection state."""
        out: list[dict[str, Any]] = []
        for e in self.employee_pool:
            if not self._matches_filter(e["role_ids"]):
                continue
            out.append(
                {
                    "id": e["id"],
                    "name": e["name"],
                    "roles": e["roles"],
                    "seniority": e["seniority"],
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

    @rx.event
    def toggle_employee(self, eid: int) -> None:
        if eid in self.selected_employee_ids:
            self.selected_employee_ids = [
                x for x in self.selected_employee_ids if x != eid
            ]
        else:
            self.selected_employee_ids = [*self.selected_employee_ids, eid]

    @rx.event
    def set_employee_role_filter(self, value: str) -> None:
        self.employee_role_filter = value

    @rx.event
    def select_all_filtered(self) -> None:
        ids = {e["id"] for e in self.filtered_employees}
        merged = set(self.selected_employee_ids) | ids
        self.selected_employee_ids = sorted(merged)

    @rx.event
    def clear_employee_selection(self) -> None:
        self.selected_employee_ids = []

    # ---- Step 3: persistence ----

    def _pick_role_for_employee(self, role_ids: list[int]) -> int:
        """Pick role_id for an employee. Prefer one in required_role_ids."""
        if self.required_role_ids:
            for rid in role_ids:
                if rid in self.required_role_ids:
                    return rid
        return role_ids[0] if role_ids else 0

    def _project_start_monday(self) -> datetime.date | None:
        if not self.start_iso:
            return None
        try:
            d = datetime.date.fromisoformat(self.start_iso)
        except ValueError:
            return None
        return d - datetime.timedelta(days=d.weekday())

    def _build_allocation_rows(self) -> list[CapacityAllocationEntity]:
        """Materialize distribution + employee selection into DB rows."""
        try:
            project_id = int(self.selected_project_id)
        except (ValueError, TypeError):
            return []
        emp_ids = list(self.selected_employee_ids)
        if not emp_ids or not self.distribution:
            return []
        monday = self._project_start_monday()
        if monday is None:
            return []
        emp_role: dict[int, int] = {}
        for emp in self.employee_pool:
            if emp["id"] in emp_ids:
                rid = self._pick_role_for_employee(emp.get("role_ids", []))
                if rid:
                    emp_role[emp["id"]] = rid
        if not emp_role:
            return []
        n_emps = len(emp_role)
        rows: list[CapacityAllocationEntity] = []
        for w_idx, weekly_pt in enumerate(self.distribution):
            per_emp = round(weekly_pt / n_emps, 2)
            if per_emp <= 0:
                continue
            week_start = monday + datetime.timedelta(days=7 * w_idx)
            for emp_id, role_id in emp_role.items():
                rows.append(
                    CapacityAllocationEntity(
                        project_id=project_id,
                        employee_id=emp_id,
                        role_id=role_id,
                        week_start=week_start,
                        person_days=per_emp,
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
