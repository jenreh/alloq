"""Position inclusive absence periods on the shared weekly planning timeline."""

from datetime import date, timedelta

from alloq_commons.models.employee import Employee

from alloq_project.states.planning_models import (
    WEEK_COL_PX,
    AbsenceGanttBar,
    AbsenceGanttRow,
    EmployeeBlock,
    WeekColumn,
)

GANTT_LANE_PX = 28
GANTT_PADDING_PX = 8
GANTT_MIN_ROW_PX = 56
CALENDAR_DAYS_PER_WEEK = 7


def _week_date(week: WeekColumn) -> date:
    return date.fromisoformat(week.key.replace("_", "-"))


def build_absence_gantt(
    resources: list[EmployeeBlock],
    employees: list[Employee],
    weeks: list[WeekColumn],
) -> list[AbsenceGanttRow]:
    """Show resources with overlapping absences, clipped to the displayed range."""
    if not weeks:
        return []
    horizon_start = _week_date(weeks[0])
    horizon_end = _week_date(weeks[-1]) + timedelta(days=CALENDAR_DAYS_PER_WEEK)
    px_per_day = WEEK_COL_PX / CALENDAR_DAYS_PER_WEEK
    by_id = {employee.id: employee for employee in employees}
    rows: list[AbsenceGanttRow] = []
    for resource in resources:
        employee = by_id.get(resource.real_id)
        periods = sorted(
            (
                (absence.start_date, absence.end_date)
                for absence in (employee.absences if employee else [])
                if absence.start_date is not None
                and absence.end_date is not None
                and absence.start_date <= absence.end_date
                and absence.start_date < horizon_end
                and absence.end_date >= horizon_start
            ),
        )
        if not periods:
            continue
        lane_ends: list[date] = []
        bars: list[AbsenceGanttBar] = []
        for start, end in periods:
            visible_start = max(start, horizon_start)
            visible_end = min(end + timedelta(days=1), horizon_end)
            lane = next(
                (
                    i
                    for i, lane_end in enumerate(lane_ends)
                    if lane_end <= visible_start
                ),
                len(lane_ends),
            )
            if lane == len(lane_ends):
                lane_ends.append(visible_end)
            else:
                lane_ends[lane] = visible_end
            days = (end - start).days + 1
            duration = "1 Kalendertag" if days == 1 else f"{days} Kalendertage"
            bars.append(
                AbsenceGanttBar(
                    left_px=(visible_start - horizon_start).days * px_per_day,
                    width_px=(visible_end - visible_start).days * px_per_day,
                    lane=lane,
                    label=f"{start:%d.%m.} - {end:%d.%m.}",
                    tooltip=(
                        f"{resource.name}\n{start:%d.%m.%Y} - {end:%d.%m.%Y}"
                        f"\n{duration}"
                    ),
                )
            )
        rows.append(
            AbsenceGanttRow(
                real_id=resource.real_id,
                name=resource.name,
                job_title=resource.job_title,
                bars=bars,
                height_px=max(
                    GANTT_MIN_ROW_PX,
                    len(lane_ends) * GANTT_LANE_PX + GANTT_PADDING_PX * 2,
                ),
            )
        )
    return rows
