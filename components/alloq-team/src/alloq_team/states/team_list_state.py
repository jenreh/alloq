"""Team list: utilization per person, filter, grouping and the inspector."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import reflex as rx
from alloq_commons.models.employee import Employee
from pydantic import BaseModel

from alloq_team.services.team_overview import (
    TeamAssignment,
    TeamOverview,
    TeamWeek,
    build_overview,
    load_inputs,
    week_starts,
)

logger = logging.getLogger(__name__)

FILTER_ALL = "Alle"
FILTER_MINE = "Meine"
FILTER_OVERLOADED = "Überlastet"
FILTER_FREE = "Frei"
FILTERS = [FILTER_ALL, FILTER_MINE, FILTER_OVERLOADED, FILTER_FREE]
AVATAR_COLORS = ["#5B7FD6", "#3D9A5E", "#C98C0A", "#7A5AC8", "#C2416B", "#2A93A8"]
DEFAULT_SORT_COLUMN = "name"


class TeamRow(BaseModel):
    id: int
    name: str
    subtitle: str
    initials: str
    color: str
    role: str
    hours: float
    load_percent: int = 0
    load_tone: str = "neutral"
    absent_now: bool = False
    free_days: float = 0.0
    project_count: int = 0


class TeamDetail(TeamRow):
    location: str = ""
    roles: str = ""
    workload_percent: int = 100
    weeks: list[TeamWeek] = []
    assignments: list[TeamAssignment] = []
    absences: list[str] = []


_SORT_KEYS: dict[str, Callable[[TeamDetail], str | float | int]] = {
    "name": lambda row: row.name.casefold(),
    "role": lambda row: row.role.casefold(),
    "hours": lambda row: row.hours,
    "load_percent": lambda row: row.load_percent,
    "free_days": lambda row: row.free_days,
    "project_count": lambda row: row.project_count,
}
SORT_COLUMNS = tuple(_SORT_KEYS)


def sort_team_rows(rows: list[TeamDetail], column: str, desc: bool) -> list[TeamDetail]:
    """Sort team rows by a supported column, keeping ties in name order."""
    key = _SORT_KEYS.get(column, _SORT_KEYS[DEFAULT_SORT_COLUMN])
    by_name = sorted(rows, key=lambda row: row.name.casefold())
    return sorted(by_name, key=key, reverse=desc)


def load_tone(overview: TeamOverview | None) -> str:
    if overview is None or overview.absent_now:
        return "neutral"
    if overview.overloaded:
        return "negative"
    if overview.load_percent >= 85:  # noqa: PLR2004
        return "warning"
    return "positive"


def _initials(employee: Employee) -> str:
    return (employee.first_name[:1] + employee.last_name[:1]).upper() or "?"


def _absence_text(employee: Employee) -> list[str]:
    return [
        f"{a.start_date:%d.%m.%Y} – {a.end_date:%d.%m.%Y}"
        for a in employee.absences
        if a.start_date and a.end_date
    ]


def to_detail(employee: Employee, overview: TeamOverview | None) -> TeamDetail:
    return TeamDetail(
        id=employee.id,
        name=f"{employee.first_name} {employee.last_name}".strip(),
        subtitle=employee.job_title or employee.seniority,
        initials=_initials(employee),
        color=AVATAR_COLORS[employee.id % len(AVATAR_COLORS)],
        role=employee.role_names[0] if employee.role_names else "",
        roles=", ".join(employee.role_names),
        hours=employee.hours_per_week,
        location=employee.location or "",
        workload_percent=employee.workload_percent,
        load_percent=overview.load_percent if overview else 0,
        load_tone=load_tone(overview),
        absent_now=overview.absent_now if overview else False,
        free_days=overview.free_days if overview else 0.0,
        project_count=len(overview.assignments) if overview else 0,
        weeks=overview.weeks if overview else [],
        assignments=overview.assignments if overview else [],
        absences=_absence_text(employee),
    )


def _matches(row: TeamDetail, overviews: dict[int, TeamOverview], value: str) -> bool:
    overview = overviews.get(row.id)
    if value == FILTER_OVERLOADED:
        return overview is not None and overview.overloaded
    if value == FILTER_FREE:
        return overview is not None and overview.free
    return True


class TeamListState(rx.State, mixin=True):
    """List filter, utilization, selection and inspector; mixed into `TeamState`.

    A mixin rather than a substate: its computed vars read `TeamState` vars.
    """

    if TYPE_CHECKING:  # Provided by TeamState.
        employees: list[Employee]
        my_employees: list[Employee]
        other_employees: list[Employee]

    list_filter: str = FILTER_ALL
    inspected_id: int = 0
    inspector_open: str = rx.LocalStorage("1", name="alloq_team_inspector")
    overviews: dict[int, TeamOverview] = {}
    sort_column: rx.Field[str] = rx.field(DEFAULT_SORT_COLUMN)
    sort_desc: rx.Field[bool] = rx.field(False)

    @rx.event
    def toggle_sort(self, column: str) -> None:
        """Sort by column; clicking the active column flips the direction."""
        if column not in SORT_COLUMNS:
            return
        self.sort_desc = column == self.sort_column and not self.sort_desc
        self.sort_column = column

    @rx.event
    def set_list_filter(self, value: str) -> None:
        self.list_filter = value if value in FILTERS else FILTER_ALL

    @rx.event
    def inspect(self, employee_id: int) -> None:
        self.inspected_id = employee_id

    @rx.event
    def toggle_inspector(self) -> None:
        self.inspector_open = "0" if self.inspector_open == "1" else "1"

    async def _refresh_overview(self) -> None:
        """Utilization for the next weeks; after every change of the team.

        Called by the admin-guarded `TeamState` handlers once employees,
        absences or assignments changed. A failure keeps the last figures.
        """
        weeks = week_starts(datetime.now(tz=UTC).date())
        try:
            allocations, projects, holidays = await load_inputs(weeks)
        except Exception:
            logger.exception("Failed to load team utilization")
            return
        self.overviews = build_overview(
            self.employees, allocations, projects, weeks, holidays
        )

    @rx.var
    def show_inspector(self) -> bool:
        return self.inspector_open == "1"

    def _details(self, employees: list[Employee]) -> list[TeamDetail]:
        rows = [to_detail(e, self.overviews.get(e.id)) for e in employees]
        filtered = [r for r in rows if _matches(r, self.overviews, self.list_filter)]
        return sort_team_rows(filtered, self.sort_column, self.sort_desc)

    @rx.var
    def mine_rows(self) -> list[TeamDetail]:
        return self._details(self.my_employees)

    @rx.var
    def other_rows(self) -> list[TeamDetail]:
        if self.list_filter == FILTER_MINE:
            return []
        return self._details(self.other_employees)

    @rx.var
    def row_count(self) -> int:
        return len(self.mine_rows) + len(self.other_rows)

    @rx.var
    def visible_total_free_days(self) -> float:
        return sum(row.free_days for row in (*self.mine_rows, *self.other_rows))

    @rx.var
    def inspected(self) -> TeamDetail | None:
        rows = [*self.mine_rows, *self.other_rows]
        return next((r for r in rows if r.id == self.inspected_id), None) or (
            rows[0] if rows else None
        )

    @rx.var
    def subtitle(self) -> str:
        total = len(self.employees)
        overloaded = sum(1 for o in self.overviews.values() if o.overloaded)
        free = sum(1 for o in self.overviews.values() if o.free)
        return (
            f"{total} Mitarbeiter · {overloaded} überlastet · "
            f"{free} mit freier Kapazität"
        )
