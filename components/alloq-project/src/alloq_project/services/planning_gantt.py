"""Absence timeline of the planning page: bars, week coverage and summaries.

Positions use the shared weekly timeline (`WEEK_COL_PX` per week). Absence
periods are inclusive and clipped to the displayed range. Working days are
Monday to Friday without public holidays.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from alloq_commons.models.employee import Employee

from alloq_project.states.planning_models import (
    WEEK_COL_PX,
    AbsenceGanttBar,
    AbsenceGanttRow,
    AbsenceGanttView,
    AffectedProject,
    CoverageCell,
    EmployeeBlock,
    GanttMark,
    GanttWeek,
    UpcomingAbsence,
    WeekColumn,
)

DAYS_PER_WEEK = 7
SATURDAY = 5
GANTT_LANE_PX = 28
GANTT_PADDING_PX = 15
GANTT_BAR_PX = 22
GANTT_MIN_ROW_PX = 52
INSIDE_LABEL_MIN_PX = 84
UPCOMING_LIMIT = 6
SOON_DAYS = 14
WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


@dataclass(frozen=True)
class _Period:
    absence_id: int
    start: date
    end: date


@dataclass
class _Resource:
    block: EmployeeBlock
    periods: list[_Period]
    absent: set[date] = field(default_factory=set)


@dataclass(frozen=True)
class _WeekStat:
    start: date
    kw: int
    present: int
    level: str


@dataclass(frozen=True)
class _Horizon:
    start: date
    end: date  # exclusive
    holidays: frozenset[date]
    today: date

    @property
    def day_px(self) -> float:
        return WEEK_COL_PX / DAYS_PER_WEEK

    def px(self, day: date) -> float:
        return (day - self.start).days * self.day_px

    def work_days(self, start: date, end: date) -> list[date]:
        """Working days of the inclusive period, not clipped."""
        days = (start + timedelta(days=i) for i in range((end - start).days + 1))
        return [d for d in days if d.weekday() < SATURDAY and d not in self.holidays]

    def visible_work_days(self, start: date, end: date) -> set[date]:
        last = self.end - timedelta(days=1)
        if start > last or end < self.start:
            return set()
        return set(self.work_days(max(start, self.start), min(end, last)))


# === Text helpers ===


def _day(d: date) -> str:
    return f"{d:%d.%m.}"


def _range_label(start: date, end: date) -> str:
    if start == end:
        return _day(start)
    if (start.year, start.month) == (end.year, end.month):
        return f"{start:%d}.–{_day(end)}"
    return f"{_day(start)}–{_day(end)}"


def _long_day(d: date, *, year: bool = True) -> str:
    return (
        f"{WEEKDAYS[d.weekday()]} {d:%d.%m.%Y}"
        if year
        else (f"{WEEKDAYS[d.weekday()]} {_day(d)}")
    )


def _period_text(start: date, end: date, *, year: bool = True) -> str:
    if start == end:
        return _long_day(start, year=year)
    return f"{_long_day(start, year=year)} – {_long_day(end, year=year)}"


def _work_days_text(count: int) -> str:
    return "1 Arbeitstag" if count == 1 else f"{count} Arbeitstage"


def _relative(period: _Period, today: date) -> str:
    if period.start == today:
        return "heute"
    if period.start < today:
        return f"läuft bis {_day(period.end)}"
    days = (period.start - today).days
    if days == 1:
        return "morgen"
    if days < SOON_DAYS:
        return f"in {days} Tagen"
    return f"in {round(days / DAYS_PER_WEEK)} Wochen"


# === Collection ===


def _week_date(week: WeekColumn) -> date:
    return date.fromisoformat(week.key.replace("_", "-"))


def _periods(employee: Employee | None, horizon: _Horizon) -> list[_Period]:
    if employee is None:
        return []
    return sorted(
        (
            _Period(absence.id, absence.start_date, absence.end_date)
            for absence in employee.absences
            if absence.start_date is not None
            and absence.end_date is not None
            and absence.start_date <= absence.end_date
            and absence.start_date < horizon.end
            and absence.end_date >= horizon.start
        ),
        key=lambda p: (p.start, p.end),
    )


def _next_label(employee: Employee | None, today: date) -> str:
    if employee is None:
        return ""
    current = [
        a.end_date
        for a in employee.absences
        if a.start_date and a.end_date and a.start_date <= today <= a.end_date
    ]
    if current:
        return f"bis {_day(max(current))}"
    future = [
        a.start_date for a in employee.absences if a.start_date and a.start_date > today
    ]
    return f"ab {_day(min(future))}" if future else ""


# === Weeks and coverage ===


def _weeks(weeks: list[WeekColumn], horizon: _Horizon) -> list[GanttWeek]:
    out: list[GanttWeek] = []
    for week in weeks:
        start = _week_date(week)
        holidays = sorted(
            d
            for d in horizon.holidays
            if start <= d < start + timedelta(days=DAYS_PER_WEEK)
            and d.weekday() < SATURDAY
        )
        title = f"KW {week.week_no} · ab {_long_day(start)}"
        if holidays:
            title += " · Feiertag " + ", ".join(_day(d) for d in holidays)
        out.append(
            GanttWeek(
                key=week.key,
                kw=week.week_no,
                label=week.label,
                has_holiday=bool(holidays),
                is_current=start <= horizon.today < start + timedelta(days=7),
                is_month_start=week.is_month_start,
                title=title,
            )
        )
    return out


def _level(present: int, team: int) -> str:
    if present >= team:
        return "ok"
    return "neg" if present * 2 <= team else "warn"


def _coverage(
    weeks: list[WeekColumn], resources: list[_Resource], horizon: _Horizon
) -> tuple[list[CoverageCell], list[_WeekStat]]:
    team = len(resources)
    cells: list[CoverageCell] = []
    stats: list[_WeekStat] = []
    for week in weeks:
        start = _week_date(week)
        days = horizon.work_days(start, start + timedelta(days=DAYS_PER_WEEK - 1))
        absent_names = sorted(
            {r.block.name for r in resources for d in days if d in r.absent}
        )
        present = team - max(
            (sum(d in r.absent for r in resources) for d in days), default=0
        )
        level = _level(present, team) if team else "ok"
        if absent_names:
            title = (
                f"KW {week.week_no}: mindestens {present} von {team} anwesend. "
                f"Abwesend: {', '.join(absent_names)}"
            )
        else:
            title = f"KW {week.week_no}: alle anwesend"
        cells.append(
            CoverageCell(
                week_key=week.key,
                label=f"{present}/{team}" if team else "–",
                level=level,
                title=title,
            )
        )
        stats.append(_WeekStat(start, week.week_no, present, level))
    return cells, stats


def _bottleneck(cells: list[CoverageCell], stats: list[_WeekStat]) -> tuple[str, str]:
    critical = [(c, s) for c, s in zip(cells, stats, strict=True) if s.level == "neg"]
    if not critical:
        return "", ""
    first = critical[0][1].kw
    label = (
        f"1 Engpass · KW {first}"
        if len(critical) == 1
        else f"{len(critical)} Engpässe · ab KW {first}"
    )
    return label, "\n".join(c.title for c, _ in critical)


# === Bars and rows ===


def _overlap_note(
    period: _Period,
    resource: _Resource,
    resources: list[_Resource],
    stats: list[_WeekStat],
    horizon: _Horizon,
) -> str:
    days = horizon.visible_work_days(period.start, period.end)
    names = [
        other.block.name
        for other in resources
        if other is not resource and days & other.absent
    ]
    parts = [f"Überschneidet sich mit {', '.join(names)}."] if names else []
    critical = [
        s
        for s in stats
        if s.level == "neg"
        and s.start <= period.end
        and period.start < s.start + timedelta(days=DAYS_PER_WEEK)
    ]
    if critical:
        worst = min(critical, key=lambda s: s.present)
        parts.append(
            f"In KW {worst.kw} ist nur {worst.present} von {len(resources)} anwesend."
        )
    return " ".join(parts)


def _holidays_note(period: _Period, horizon: _Horizon) -> str:
    days = sorted(
        d
        for d in horizon.holidays
        if period.start <= d <= period.end and d.weekday() < SATURDAY
    )
    if not days:
        return ""
    count = "1 Feiertag" if len(days) == 1 else f"{len(days)} Feiertage"
    return f"{count} nicht gezählt ({', '.join(_day(d) for d in days)})"


def _bar(
    period: _Period,
    lane: int,
    resource: _Resource,
    context: tuple[list[_Resource], list[_WeekStat], _Horizon],
) -> AbsenceGanttBar:
    resources, stats, horizon = context
    visible_start = max(period.start, horizon.start)
    visible_end = min(period.end + timedelta(days=1), horizon.end)
    width = (visible_end - visible_start).days * horizon.day_px
    clipped = period.start < horizon.start
    work_days = len(horizon.work_days(period.start, period.end))
    label = (
        f"seit {_day(period.start)}"
        if clipped
        else _range_label(period.start, period.end)
    )
    inside = width >= INSIDE_LABEL_MIN_PX
    period_text = _period_text(period.start, period.end)
    return AbsenceGanttBar(
        absence_id=period.absence_id,
        left_px=horizon.px(visible_start),
        width_px=width,
        lane=lane,
        label=label,
        side_label="" if inside else f"{label} · {work_days} AT",
        inside=inside,
        clipped=clipped,
        aria_label=(
            f"{resource.block.name}, {period_text}, {_work_days_text(work_days)}"
        ),
        period=period_text,
        work_days=work_days,
        calendar_days=(period.end - period.start).days + 1,
        holidays_note=_holidays_note(period, horizon),
        overlap_note=_overlap_note(period, resource, resources, stats, horizon),
    )


def _lanes(periods: list[_Period], horizon: _Horizon) -> list[int]:
    """Lane per period; a lane is reused once its previous bar has ended."""
    lane_ends: list[date] = []
    lanes: list[int] = []
    for period in periods:
        start = max(period.start, horizon.start)
        lane = next(
            (i for i, end in enumerate(lane_ends) if end <= start), len(lane_ends)
        )
        end = min(period.end + timedelta(days=1), horizon.end)
        if lane == len(lane_ends):
            lane_ends.append(end)
        else:
            lane_ends[lane] = end
        lanes.append(lane)
    return lanes


def _row(
    resource: _Resource,
    employee: Employee | None,
    context: tuple[list[_Resource], list[_WeekStat], _Horizon],
) -> AbsenceGanttRow:
    horizon = context[2]
    lanes = _lanes(resource.periods, horizon)
    block = resource.block
    return AbsenceGanttRow(
        real_id=block.real_id,
        name=block.name,
        initials=block.initials,
        avatar_color=block.avatar_color,
        job_title=block.job_title,
        bars=[
            _bar(period, lane, resource, context)
            for period, lane in zip(resource.periods, lanes, strict=True)
        ],
        height_px=max(
            GANTT_MIN_ROW_PX,
            max(lanes, default=0) * GANTT_LANE_PX + GANTT_BAR_PX + GANTT_PADDING_PX * 2,
        ),
        total_days=len(resource.absent),
        next_label=_next_label(employee, horizon.today),
    )


def _pt(days: float) -> str:
    text = f"{round(days, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text.replace('.', ',')} PT"


def _affected_weeks(period: _Period, weeks: list[WeekColumn]) -> list[int]:
    """Indexes of the displayed weeks the period touches."""
    return [
        i
        for i, week in enumerate(weeks)
        if _week_date(week) <= period.end
        and period.start < _week_date(week) + timedelta(days=DAYS_PER_WEEK)
    ]


def _kw_list(weeks: list[WeekColumn], indexes: list[int]) -> str:
    return "KW " + ", ".join(str(weeks[i].week_no) for i in indexes)


def _plan_impact(
    period: _Period, block: EmployeeBlock, weeks: list[WeekColumn]
) -> tuple[list[AffectedProject], str, str]:
    """Projects booked in the absence weeks and whether those weeks overflow."""
    indexes = _affected_weeks(period, weeks)
    projects: list[AffectedProject] = []
    for project in block.projects:
        if project.is_internal:
            continue
        booked = [
            i for i in indexes if i < len(project.cells) and project.cells[i].value > 0
        ]
        if booked:
            projects.append(
                AffectedProject(
                    name=project.name or project.code,
                    color=project.color,
                    days_label=_pt(sum(project.cells[i].value for i in booked)),
                    weeks=_kw_list(weeks, booked),
                )
            )
    over = [
        i for i in indexes if i < len(block.gesamt) and block.gesamt[i].state == "over"
    ]
    if over:
        worst = -min(block.gesamt[i].value for i in over)
        text = (
            f"{_kw_list(weeks, over)} überbucht um {_pt(worst)}"
            if len(over) == 1
            else f"{_kw_list(weeks, over)} überbucht, bis {_pt(worst)} zu viel"
        )
        return projects, "neg", text
    if projects:
        return projects, "ok", "Kapazität reicht"
    return projects, "none", "Keine Projekte eingeplant"


def _upcoming(
    resources: list[_Resource], horizon: _Horizon, weeks: list[WeekColumn]
) -> list[UpcomingAbsence]:
    today = horizon.today
    items = sorted(
        (
            (period, r.block)
            for r in resources
            for period in r.periods
            if period.end >= today
        ),
        key=lambda item: (item[0].start, item[1].name),
    )[:UPCOMING_LIMIT]
    out: list[UpcomingAbsence] = []
    for period, block in items:
        projects, status, status_label = _plan_impact(period, block, weeks)
        out.append(
            UpcomingAbsence(
                name=block.name,
                initials=block.initials,
                avatar_color=block.avatar_color,
                period=(
                    f"{_period_text(period.start, period.end, year=False)} · "
                    f"{len(horizon.work_days(period.start, period.end))} AT"
                ),
                relative=_relative(period, today),
                is_running=period.start <= today,
                projects=projects,
                status=status,
                status_label=status_label,
            )
        )
    return out


# === Entry point ===


def build_absence_gantt(
    resources: list[EmployeeBlock],
    employees: list[Employee],
    weeks: list[WeekColumn],
    *,
    holidays: Iterable[date] | None = None,
    today: date | None = None,
    show_all: bool = False,
) -> AbsenceGanttView:
    """Absence timeline of the filtered resources over the displayed weeks."""
    if not weeks:
        return AbsenceGanttView()
    start = _week_date(weeks[0])
    horizon = _Horizon(
        start=start,
        end=_week_date(weeks[-1]) + timedelta(days=DAYS_PER_WEEK),
        holidays=frozenset(holidays or ()),
        today=today or date.today(),  # noqa: DTZ011
    )
    by_id = {employee.id: employee for employee in employees}
    collected = [
        _Resource(block, _periods(by_id.get(block.real_id), horizon))
        for block in resources
    ]
    for resource in collected:
        for period in resource.periods:
            resource.absent |= horizon.visible_work_days(period.start, period.end)

    coverage, stats = _coverage(weeks, collected, horizon)
    context = (collected, stats, horizon)
    rows = [
        _row(resource, by_id.get(resource.block.real_id), context)
        for resource in collected
        if resource.periods or show_all
    ]
    holiday_days = sorted(
        (d - start).days
        for d in horizon.holidays
        if start <= d < horizon.end and d.weekday() < SATURDAY
    )
    total = sum(row.total_days for row in rows)
    bottleneck, bottleneck_title = _bottleneck(coverage, stats)
    days_total = (horizon.end - start).days
    today_index = (horizon.today - start).days
    return AbsenceGanttView(
        rows=rows,
        weeks=_weeks(weeks, horizon),
        coverage=coverage,
        holidays=[
            GanttMark(
                left_px=i * horizon.day_px,
                title=f"Feiertag {_long_day(start + timedelta(days=i))}",
            )
            for i in holiday_days
        ],
        holiday_days=holiday_days,
        month_lines=[
            i * WEEK_COL_PX for i, week in enumerate(weeks) if week.is_month_start
        ],
        upcoming=_upcoming(collected, horizon, weeks),
        today_px=(
            (today_index + 0.5) * horizon.day_px
            if 0 <= today_index < days_total
            else -1
        ),
        min_day=min(max(today_index, 0), days_total),
        day_px=horizon.day_px,
        width_px=len(weeks) * WEEK_COL_PX,
        horizon_start=start.isoformat(),
        team_size=len(collected),
        total_days=total,
        total_label=(
            f"{_work_days_text(total)} abwesend"
            if total
            else "Keine Abwesenheiten im Zeitraum"
        ),
        bottleneck_label=bottleneck,
        bottleneck_title=bottleneck_title,
    )
