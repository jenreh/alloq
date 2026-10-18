"""Resource-critical path: capacity per role, staffing gaps and buffer.

There are no milestones, so the critical path is derived from staffing: a
project's end date depends on the role whose remaining demand is covered last.
All functions are pure; inputs come from ``portfolio_inputs``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import NamedTuple

from alloq_commons.entities.project import ProjectStateEnum
from alloq_commons.services.utilization import (
    AbsencePeriod,
    HeatResult,
    UtilizationService,
)

from alloq_dashboard.models import (
    PersonAbsence,
    PersonBooking,
    PersonDetail,
    PersonWeek,
    PortfolioRoleLine,
    RoleDemand,
    RoleDetail,
    RoleGapProject,
    RolePerson,
    RoleWeek,
)
from alloq_dashboard.services.portfolio_inputs import (
    LOOKAHEAD_WEEKS,
    EmployeeInput,
    PortfolioInputs,
    ProjectInput,
    booking_projects,
)

HORIZON_WEEKS = 13
NEAR_END_WEEKS = 8
OVERLOAD_PERCENT = 100
MAX_CARRIER_NAMES = 2
EPS = 1e-6
TONE_NEG = "neg"
TONE_WARN = "warn"
NO_CARRIER = "niemand eingeplant"
MINUS = "\u2212"
WORK_WEEK_DAYS = 5
BAR_FULL = 80.0
"""Bar width (%) for 100 % availability; the rest shows overbooking."""
BAR_OVER_MAX = 20.0
NEED_MAX_RATIO = 1.25

_SEVERITY = {TONE_NEG: 3, TONE_WARN: 2}


def week_label(d: date) -> str:
    return f"KW {d.isocalendar().week:02d}"


def format_days(value: float) -> str:
    """German person-days: ``34`` or ``12,5``."""
    rounded = round(value, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}".replace(".", ",")


def buffer_label(weeks: int) -> str:
    return f"+{weeks}" if weeks >= 0 else f"{MINUS}{abs(weeks)}"


def buffer_tone(weeks: int) -> str:
    if weeks < 0:
        return TONE_NEG
    if weeks <= 1:
        return TONE_WARN
    return ""


@dataclass(frozen=True)
class Calendar:
    """Monday-aligned weeks from the current week on."""

    monday: date
    length: int = LOOKAHEAD_WEEKS

    @classmethod
    def for_today(cls, today: date, length: int = LOOKAHEAD_WEEKS) -> Calendar:
        return cls(monday=today - timedelta(days=today.weekday()), length=length)

    def index(self, d: date) -> int:
        """Week offset of ``d`` from this week's Monday (negative = past)."""
        return (d - timedelta(days=d.weekday()) - self.monday).days // 7

    def week(self, index: int) -> date:
        return self.monday + timedelta(weeks=index)


class Capacity:
    """Weekly availability and bookings per person and per role.

    Bookings count on every unfinished project, because they use up a person's
    time no matter which project is shown. Role sums cover only the people in
    scope (``inputs.employees``).
    """

    def __init__(self, inputs: PortfolioInputs, calendar: Calendar) -> None:
        self.calendar = calendar
        n = calendar.length
        people = inputs.all_employees or inputs.employees
        booked: dict[int, list[dict[int, float]]] = {
            e.id: [defaultdict(float) for _ in range(n)] for e in people
        }
        for project in booking_projects(inputs):
            if project.state == ProjectStateEnum.COMPLETED.value:
                continue
            for a in project.allocations:
                i = calendar.index(a.week_start)
                if a.employee_id in booked and 0 <= i < n:
                    booked[a.employee_id][i][a.role_id] += a.person_days
        self.booked = booked
        self.people = {e.id: e for e in people}
        self._heat: dict[int, list[HeatResult]] = {}
        for emp in people:
            self._fill_employee(emp, booked[emp.id], inputs.holidays)
        self.role_available: dict[int, list[float]] = defaultdict(lambda: [0.0] * n)
        self.role_allocated: dict[int, list[float]] = defaultdict(lambda: [0.0] * n)
        self.role_people: dict[int, int] = defaultdict(int)
        for emp in inputs.employees:
            weeks = booked.get(emp.id, [])
            for role_id in emp.role_ids:
                self.role_people[role_id] += 1
            for i, by_role in enumerate(weeks):
                total = sum(by_role.values())
                for role_id, days in by_role.items():
                    self.role_allocated[role_id][i] += days
                for role_id in emp.role_ids:
                    other = total - by_role.get(role_id, 0.0)
                    free = max(0.0, self.available(emp.id, i) - other)
                    self.role_available[role_id][i] += free

    def _fill_employee(
        self,
        emp: EmployeeInput,
        weeks: list[dict[int, float]],
        holidays: frozenset[date],
    ) -> None:
        absences = [AbsencePeriod(start_date=s, end_date=e) for s, e in emp.absences]
        self._heat[emp.id] = [
            UtilizationService.compute_heat_from_raw(
                used_days=sum(by_role.values()),
                internal_hours=emp.internal_hours,
                absences=absences,
                week_start=self.calendar.week(i),
                holiday_dates=holidays,
                workload_percent=emp.workload_percent,
            )
            for i, by_role in enumerate(weeks)
        ]

    def free(self, role_id: int, index: int) -> float:
        """Free days of a role; negative means overbooked (no clamping)."""
        return self.role_available[role_id][index] - self.role_allocated[role_id][index]

    def heat(self, employee_id: int, index: int = 0) -> HeatResult | None:
        weeks = self._heat.get(employee_id)
        return weeks[index] if weeks and 0 <= index < len(weeks) else None

    def percent(self, employee_id: int, index: int = 0) -> int | None:
        heat = self.heat(employee_id, index)
        return heat.percent if heat else None

    def available(self, employee_id: int, index: int) -> float:
        heat = self.heat(employee_id, index)
        return heat.available_days if heat else 0.0

    def booked_days(
        self, employee_id: int, index: int, role_id: int | None = None
    ) -> float:
        """Days booked in one week, in one role or in all of them."""
        weeks = self.booked.get(employee_id)
        if not weeks or not 0 <= index < len(weeks):
            return 0.0
        by_role = weeks[index]
        return sum(by_role.values()) if role_id is None else by_role.get(role_id, 0.0)

    def free_pool(self) -> dict[int, list[float]]:
        """Clamped free days per role and week, to hand out to staffing gaps."""
        roles = set(self.role_available) | set(self.role_allocated)
        return {
            r: [max(0.0, self.free(r, i)) for i in range(self.calendar.length)]
            for r in roles
        }


@dataclass
class _RoleWork:
    role_id: int
    required: float
    remaining: float
    planned: float
    gap: float
    cover_index: int | None
    carriers: list[int]


def _role_work(
    project: ProjectInput,
    role_id: int,
    required: float,
    calendar: Calendar,
    pool: dict[int, list[float]],
) -> _RoleWork:
    past = 0.0
    planned_by_week: dict[int, float] = defaultdict(float)
    carriers: dict[int, float] = defaultdict(float)
    for a in project.allocations:
        if a.role_id != role_id:
            continue
        i = calendar.index(a.week_start)
        if i < 0:
            past += a.person_days
        else:
            planned_by_week[i] += a.person_days
            carriers[a.employee_id] += a.person_days
    remaining = max(0.0, required - past)
    planned = sum(planned_by_week.values())
    gap = max(0.0, remaining - planned)
    cover = _planned_cover(planned_by_week, min(remaining, planned))
    if gap > EPS:
        gap_cover = _consume(pool.get(role_id), gap, calendar.index(project.start_date))
        cover = None if gap_cover is None else max(cover, gap_cover)
    return _RoleWork(
        role_id=role_id,
        required=required,
        remaining=remaining,
        planned=planned,
        gap=gap,
        cover_index=cover,
        carriers=sorted(carriers, key=lambda e: (-carriers[e], e)),
    )


def _planned_cover(planned_by_week: dict[int, float], target: float) -> int:
    """First week in which planned days reach ``target`` (0 if nothing is due)."""
    total = 0.0
    for i in sorted(planned_by_week):
        if total >= target - EPS:
            break
        total += planned_by_week[i]
        if total >= target - EPS:
            return i
    return 0


def _consume(weeks: list[float] | None, need: float, start: int) -> int | None:
    """Take free days from ``weeks`` (in place) until ``need`` is met."""
    if not weeks:
        return None
    left = need
    for i in range(max(0, start), len(weeks)):
        take = min(weeks[i], left)
        weeks[i] -= take
        left -= take
        if left <= EPS:
            return i
    return None


def _absence_in(
    emp: EmployeeInput | None, start: date, end: date
) -> tuple[date, date] | None:
    """First and last absent day of ``emp`` between ``start`` and ``end``."""
    if emp is None:
        return None
    days = [
        (max(a_start, start), min(a_end, end))
        for a_start, a_end in emp.absences
        if a_start <= end and a_end >= start
    ]
    if not days:
        return None
    return min(d[0] for d in days), max(d[1] for d in days)


class _Why(NamedTuple):
    """Person to name (and open), tone and one-sentence reason."""

    person_id: int
    person: str
    tone: str
    reason: str


@dataclass(frozen=True)
class _Context:
    project: ProjectInput
    calendar: Calendar
    capacity: Capacity
    people: dict[int, EmployeeInput]
    role_names: dict[int, str]


def _overbooked_from(ctx: _Context, role_id: int) -> date | None:
    start = max(0, ctx.calendar.index(ctx.project.start_date))
    end = min(HORIZON_WEEKS - 1, ctx.calendar.index(ctx.project.end_date))
    for i in range(start, end + 1):
        if ctx.capacity.free(role_id, i) < -EPS:
            return ctx.calendar.week(i)
    return None


def _names(ctx: _Context, ids: list[int]) -> str:
    names = [ctx.people[i].name for i in ids[:MAX_CARRIER_NAMES] if i in ctx.people]
    extra = len(ids) - MAX_CARRIER_NAMES
    label = ", ".join(names)
    return f"{label} +{extra}" if extra > 0 else label


def _carrier_issue(
    ctx: _Context, work: _RoleWork, person: str, *, single: bool
) -> _Why | None:
    """Absent single carrier, or an overloaded carrier shortly before the end."""
    if single:
        first_id = work.carriers[0]
        carrier = ctx.people.get(first_id)
        absent = _absence_in(carrier, ctx.calendar.monday, ctx.project.end_date)
        if absent:
            first, last = (week_label(d) for d in absent)
            when = f"in {first}" if first == last else f"{first} bis {last}"
            reason = f"Einzige Person für die Rolle. Abwesend {when}."
            return _Why(first_id, person, TONE_WARN, reason)
    if ctx.calendar.index(ctx.project.end_date) > NEAR_END_WEEKS:
        return None
    for emp_id in work.carriers:
        pct = ctx.capacity.percent(emp_id)
        if pct is not None and pct > OVERLOAD_PERCENT:
            end = ctx.project.end_date.strftime("%d.%m.")
            return _Why(
                emp_id,
                _names(ctx, [emp_id]),
                TONE_NEG,
                f"{pct} % ausgelastet. Das Projekt endet am {end}",
            )
    return None


def _explain(ctx: _Context, work: _RoleWork) -> _Why:
    """Person, tone and one-sentence reason for a project role."""
    gap_text = f"{format_days(work.gap)} PT ohne Plan."
    overbooked = _overbooked_from(ctx, work.role_id)
    if not work.carriers and work.gap > EPS:
        reason = gap_text
        if overbooked:
            reason += f" Die Rolle ist ab {week_label(overbooked)} überbucht."
        return _Why(0, NO_CARRIER, TONE_NEG, reason)
    first_id = work.carriers[0] if work.carriers else 0
    person = _names(ctx, work.carriers)
    if overbooked:
        reason = f"Rolle ab {week_label(overbooked)} überbucht."
        if work.gap > EPS:
            reason += " " + gap_text
        return _Why(first_id, person, TONE_NEG, reason)
    single = len(work.carriers) == 1
    issue = _carrier_issue(ctx, work, person, single=single)
    if issue:
        return issue
    if single:
        return _Why(first_id, person, TONE_WARN, "Einzige Person für die Rolle.")
    if work.gap > EPS:
        return _Why(first_id, person, "", gap_text)
    covered = ctx.calendar.week(work.cover_index or 0)
    return _Why(first_id, person, "", f"Bedarf gedeckt bis {week_label(covered)}.")


def _role_line(ctx: _Context, work: _RoleWork) -> PortfolioRoleLine:
    end_index = ctx.calendar.index(ctx.project.end_date)
    covered = work.cover_index is not None
    cover = work.cover_index if covered else ctx.calendar.length
    buffer = end_index - (cover or 0)
    person_id, person, tone, reason = _explain(ctx, work)
    if work.remaining <= EPS:
        # Nothing left to do: the role cannot delay the project.
        buffer = max(buffer, 0)
        tone, reason = "", "Bedarf erfüllt."
    if not covered:
        reason = f"Nicht gedeckt in {ctx.calendar.length} Wochen. " + reason
        tone = TONE_NEG
    return PortfolioRoleLine(
        role_id=work.role_id,
        role_name=ctx.role_names.get(work.role_id, "Rolle"),
        required_days=round(work.required, 1),
        remaining_days=round(work.remaining, 1),
        planned_days=round(work.planned, 1),
        gap_days=round(work.gap, 1),
        buffer_weeks=buffer,
        buffer_label=buffer_label(buffer),
        buffer_tone=buffer_tone(buffer),
        covered=covered,
        carriers=[ctx.people[i].name for i in work.carriers if i in ctx.people],
        person_id=person_id,
        person_label=person,
        tone=tone,
        reason=reason,
    )


def weakest(lines: list[PortfolioRoleLine]) -> PortfolioRoleLine | None:
    """Role with the smallest buffer; on a tie the more severe reason."""
    if not lines:
        return None
    return min(
        lines,
        key=lambda line: (
            line.buffer_weeks if line.buffer_weeks is not None else 0,
            -_SEVERITY.get(line.tone, 0),
            line.role_name,
        ),
    )


def analyse_projects(
    inputs: PortfolioInputs, capacity: Capacity
) -> dict[int, list[PortfolioRoleLine]]:
    """Role lines per unfinished project in scope.

    Projects get free capacity in order of their end date, so an earlier
    project is staffed first. Projects without required capacity get no lines.
    """
    calendar = capacity.calendar
    pool = capacity.free_pool()
    people = {e.id: e for e in (inputs.all_employees or inputs.employees)}
    role_names = {r.id: r.name for r in inputs.roles}
    result: dict[int, list[PortfolioRoleLine]] = {}
    projects = sorted(
        (p for p in inputs.projects if p.state != ProjectStateEnum.COMPLETED.value),
        key=lambda p: (p.end_date, p.id),
    )
    for project in projects:
        ctx = _Context(project, calendar, capacity, people, role_names)
        lines = [
            _role_line(ctx, _role_work(project, role_id, required, calendar, pool))
            for role_id, required in project.required
        ]
        result[project.id] = sorted(lines, key=lambda line: line.role_name)
    return result


def _horizon_share(project: ProjectInput, calendar: Calendar) -> float:
    """Part of the remaining project weeks that falls into the horizon."""
    start = max(0, calendar.index(project.start_date))
    end = max(start, calendar.index(project.end_date))
    inside = max(0, min(end, HORIZON_WEEKS - 1) - start + 1)
    return inside / (end - start + 1)


def _bar(value: float, available: float) -> float:
    if available <= 0:
        return BAR_FULL if value > 0 else 0.0
    return value / available * BAR_FULL


def role_demands(
    inputs: PortfolioInputs,
    capacity: Capacity,
    lines: dict[int, list[PortfolioRoleLine]],
) -> list[RoleDemand]:
    """Available, planned and needed days per role over the next 13 weeks."""
    calendar = capacity.calendar
    gap_share: dict[int, float] = defaultdict(float)
    by_id = {p.id: p for p in inputs.projects}
    for project_id, project_lines in lines.items():
        share = _horizon_share(by_id[project_id], calendar)
        for line in project_lines:
            gap_share[line.role_id] += line.gap_days * share
    horizon = range(min(HORIZON_WEEKS, calendar.length))
    rows: list[RoleDemand] = []
    for role in inputs.roles:
        available = sum(capacity.role_available[role.id][i] for i in horizon)
        planned = sum(capacity.role_allocated[role.id][i] for i in horizon)
        need = planned + gap_share.get(role.id, 0.0)
        people = capacity.role_people.get(role.id, 0)
        if people == 0 and need <= EPS:
            continue
        plan_bar = _bar(planned, available)
        rows.append(
            RoleDemand(
                role_id=role.id,
                role_name=role.name,
                employee_count=people,
                available_days=round(available, 1),
                planned_days=round(planned, 1),
                need_days=round(need, 1),
                gap_days=round(max(0.0, need - planned), 1),
                plan_width=f"{min(plan_bar, BAR_FULL):.1f}%",
                over_width=f"{min(max(plan_bar - BAR_FULL, 0.0), BAR_OVER_MAX):.1f}%",
                need_left=(
                    f"{min(_bar(need, available), BAR_FULL * NEED_MAX_RATIO):.1f}%"
                ),
                overbooked=planned > available + EPS,
            )
        )
    return sorted(rows, key=lambda r: (-r.gap_days, r.role_name))


# --------------------------------------------------------------------------
# Drawer details for a role and a person
# --------------------------------------------------------------------------


def _horizon(calendar: Calendar) -> range:
    return range(min(HORIZON_WEEKS, calendar.length))


def _load_tone(percent: int) -> str:
    return TONE_NEG if percent > OVERLOAD_PERCENT else ""


def _avg_percent(capacity: Capacity, employee_id: int, horizon: range) -> int:
    values = [capacity.percent(employee_id, i) or 0 for i in horizon]
    return round(sum(values) / len(values)) if values else 0


def _gap_projects(
    inputs: PortfolioInputs, lines: dict[int, list[PortfolioRoleLine]]
) -> dict[int, list[RoleGapProject]]:
    """Projects with unplanned demand per role, smallest buffer first."""
    by_id = {p.id: p for p in inputs.projects}
    found: dict[int, list[tuple[int, PortfolioRoleLine, ProjectInput]]] = defaultdict(
        list
    )
    for project_id, project_lines in lines.items():
        for line in project_lines:
            if line.gap_days > EPS and project_id in by_id:
                buffer = line.buffer_weeks if line.buffer_weeks is not None else 0
                found[line.role_id].append((buffer, line, by_id[project_id]))
    return {
        role_id: [
            RoleGapProject(
                project_id=project.id,
                code=project.code,
                name=project.name,
                gap_days=line.gap_days,
                buffer_label=line.buffer_label,
                buffer_tone=line.buffer_tone,
            )
            for _, line, project in sorted(rows, key=lambda r: (r[0], r[2].code))
        ]
        for role_id, rows in found.items()
    }


def _role_week(capacity: Capacity, role_id: int, index: int) -> RoleWeek:
    free = capacity.free(role_id, index)
    return RoleWeek(
        label=week_label(capacity.calendar.week(index)),
        available_days=round(capacity.role_available[role_id][index], 1),
        planned_days=round(capacity.role_allocated[role_id][index], 1),
        free_days=round(free, 1),
        tone=TONE_NEG if free < -EPS else "",
    )


def _role_person(
    capacity: Capacity, emp: EmployeeInput, role_id: int, horizon: range
) -> RolePerson:
    avg = _avg_percent(capacity, emp.id, horizon)
    planned = sum(capacity.booked_days(emp.id, i, role_id) for i in horizon)
    return RolePerson(
        employee_id=emp.id,
        name=emp.name,
        planned_days=round(planned, 1),
        avg_percent=avg,
        tone=_load_tone(avg),
    )


def role_details(
    inputs: PortfolioInputs,
    capacity: Capacity,
    lines: dict[int, list[PortfolioRoleLine]],
) -> list[RoleDetail]:
    """Weeks, people and staffing gaps of every role over the horizon."""
    horizon = _horizon(capacity.calendar)
    gaps = _gap_projects(inputs, lines)
    result: list[RoleDetail] = []
    for role in inputs.roles:
        available = sum(capacity.role_available[role.id][i] for i in horizon)
        planned = sum(capacity.role_allocated[role.id][i] for i in horizon)
        holders = sorted(
            (e for e in inputs.employees if role.id in e.role_ids),
            key=lambda e: (e.name, e.id),
        )
        result.append(
            RoleDetail(
                role_id=role.id,
                role_name=role.name,
                employee_count=len(holders),
                available_days=round(available, 1),
                planned_days=round(planned, 1),
                free_days=round(available - planned, 1),
                weeks=[_role_week(capacity, role.id, i) for i in horizon],
                people=[_role_person(capacity, e, role.id, horizon) for e in holders],
                gap_projects=gaps.get(role.id, []),
            )
        )
    return result


def _work_days(start: date, end: date, holidays: frozenset[date]) -> int:
    days = (end - start).days + 1
    return sum(
        1
        for offset in range(days)
        if (d := start + timedelta(days=offset)).weekday() < WORK_WEEK_DAYS
        and d not in holidays
    )


def _absences(
    emp: EmployeeInput, first: date, last: date, holidays: frozenset[date]
) -> list[PersonAbsence]:
    """Absences overlapping ``first``..``last``, cut to that range."""
    rows: list[PersonAbsence] = []
    for start, end in sorted(emp.absences):
        if start > last or end < first:
            continue
        begin, finish = max(start, first), min(end, last)
        label = (
            begin.strftime("%d.%m.%Y")
            if begin == finish
            else f"{begin:%d.%m.} bis {finish:%d.%m.%Y}"
        )
        rows.append(
            PersonAbsence(label=label, days=_work_days(begin, finish, holidays))
        )
    return rows


def _bookings(
    inputs: PortfolioInputs, calendar: Calendar, in_scope: set[int]
) -> dict[int, list[PersonBooking]]:
    """Days per person, project and role over the horizon, largest first."""
    horizon = _horizon(calendar)
    role_names = {r.id: r.name for r in inputs.roles}
    days: dict[tuple[int, int, int], float] = defaultdict(float)
    projects: dict[int, ProjectInput] = {}
    for project in booking_projects(inputs):
        if project.state == ProjectStateEnum.COMPLETED.value:
            continue
        projects[project.id] = project
        for a in project.allocations:
            if calendar.index(a.week_start) in horizon:
                days[a.employee_id, project.id, a.role_id] += a.person_days
    result: dict[int, list[PersonBooking]] = defaultdict(list)
    for (emp_id, project_id, role_id), value in days.items():
        if value <= EPS:
            continue
        project = projects[project_id]
        result[emp_id].append(
            PersonBooking(
                project_id=project_id,
                code=project.code,
                name=project.name,
                role_id=role_id,
                role_name=role_names.get(role_id, "Rolle"),
                days=round(value, 1),
                in_scope=project_id in in_scope,
            )
        )
    for rows in result.values():
        rows.sort(key=lambda b: (-b.days, b.code, b.role_name))
    return result


def _person_week(capacity: Capacity, emp_id: int, index: int) -> PersonWeek:
    heat = capacity.heat(emp_id, index)
    percent = heat.percent if heat else 0
    return PersonWeek(
        label=week_label(capacity.calendar.week(index)),
        booked_days=round(capacity.booked_days(emp_id, index), 1),
        available_days=round(heat.available_days, 1) if heat else 0.0,
        percent=percent,
        absent=heat.is_absent if heat else False,
        tone=_load_tone(percent),
        bar_width=f"{max(0, min(percent, 100))}%",
    )


def person_details(
    inputs: PortfolioInputs,
    capacity: Capacity,
    lines: dict[int, list[PortfolioRoleLine]],
) -> list[PersonDetail]:
    """People in scope and named carriers: load, absences and bookings."""
    calendar = capacity.calendar
    horizon = _horizon(calendar)
    ids = {e.id for e in inputs.employees} | {
        line.person_id for rows in lines.values() for line in rows if line.person_id
    }
    people = sorted(
        (capacity.people[i] for i in ids if i in capacity.people),
        key=lambda e: (e.name, e.id),
    )
    role_names = {r.id: r.name for r in inputs.roles}
    bookings = _bookings(inputs, calendar, set(lines))
    first = calendar.monday
    last = calendar.week(len(horizon)) - timedelta(days=1)
    result: list[PersonDetail] = []
    for emp in people:
        avg = _avg_percent(capacity, emp.id, horizon)
        absences = _absences(emp, first, last, inputs.holidays)
        result.append(
            PersonDetail(
                employee_id=emp.id,
                name=emp.name,
                roles_label=", ".join(
                    role_names[r] for r in emp.role_ids if r in role_names
                ),
                avg_percent=avg,
                tone=_load_tone(avg),
                absent_days=sum(a.days for a in absences),
                weeks=[_person_week(capacity, emp.id, i) for i in horizon],
                absences=absences,
                bookings=bookings.get(emp.id, []),
            )
        )
    return result
