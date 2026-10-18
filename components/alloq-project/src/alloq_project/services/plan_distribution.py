"""Weekly PT distribution for the 'Projekt planen' modal (pure functions)."""

import datetime as dt
import math

from alloq_commons.services.utilization import AbsencePeriod, UtilizationService

from alloq_project.services.resource_planning import week_starts

WORKDAYS_PER_WEEK = 5
PT_QUANTA_PER_WEEK = 4  # weekly steps: 0, 0.25, 0.5, 0.75, 1.0 * cap
AVAIL_EPSILON = 0.05  # week treated as unavailable below this PT threshold
REMAINING_EPSILON = 0.005  # water-fill termination threshold


def distribute(
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
    # Per-week upper bound respects ramp shape: each week i may hold at most
    # round(w_i * PT_QUANTA_PER_WEEK) quanta (capped at PT_QUANTA_PER_WEEK).
    per_week_max = [
        max(0, min(PT_QUANTA_PER_WEEK, round(w * PT_QUANTA_PER_WEEK))) for w in weights
    ]
    shape_max_q = sum(per_week_max)
    target_q = round(total_pt / quantum)
    target_q = max(0, min(target_q, shape_max_q))
    snapped = [
        max(0, min(per_week_max[i], round(raw[i] / quantum))) for i in range(weeks)
    ]
    diff = target_q - sum(snapped)
    if diff != 0:
        residuals = sorted(
            ((raw[i] / quantum - snapped[i], i) for i in range(weeks)),
            reverse=diff > 0,
        )
        for _, i in residuals:
            if diff == 0:
                break
            if diff > 0 and snapped[i] < per_week_max[i]:
                snapped[i] += 1
                diff -= 1
            elif diff < 0 and snapped[i] > 0:
                snapped[i] -= 1
                diff += 1
    return [round(s * quantum, 2) for s in snapped]


def _cap_at(weekly_avail: list[float], idx: int) -> float:
    return weekly_avail[idx] if 0 <= idx < len(weekly_avail) else 0.0


def _fill_rampup(
    result: list[float],
    remaining: float,
    ramp_up: int,
    weekly_avail: list[float],
) -> float:
    """Fractional fill in ramp-up window. Returns remaining PT."""
    for i in range(ramp_up):
        if remaining <= REMAINING_EPSILON:
            break
        cap_i = _cap_at(weekly_avail, i)
        if cap_i <= AVAIL_EPSILON:
            continue
        weight = (i + 1) / (ramp_up + 1)
        take = min(weight * cap_i, cap_i, remaining)
        result[i] = take
        remaining -= take
    return remaining


def _fill_plateau(
    result: list[float],
    remaining: float,
    ramp_up: int,
    weeks: int,
    weekly_avail: list[float],
) -> tuple[float, int]:
    """Saturate weeks left-to-right after ramp-up. Returns (remaining, last_filled)."""
    last_filled = ramp_up - 1
    for i in range(ramp_up, weeks):
        if remaining <= REMAINING_EPSILON:
            break
        cap_i = _cap_at(weekly_avail, i)
        if cap_i <= AVAIL_EPSILON:
            continue
        take = min(cap_i, remaining)
        result[i] = take
        remaining -= take
        last_filled = i
    return remaining, last_filled


def _tapered_shape(
    idx: list[int], weekly_avail: list[float], ramp_down: int
) -> list[float]:
    """PT per week in ``idx`` at full cap with the last ``ramp_down`` tapered."""
    tail_start = max(0, len(idx) - ramp_down)
    return [
        weekly_avail[i]
        * (
            1.0
            if pos < tail_start
            else (ramp_down - (pos - tail_start)) / (ramp_down + 1)
        )
        for pos, i in enumerate(idx)
    ]


def _fill_tapered(
    result: list[float],
    remaining: float,
    ramp_up: int,
    ramp_down: int,
    weekly_avail: list[float],
) -> float:
    """Fill weeks after ramp-up so the last ``ramp_down`` used weeks taper off.

    Uses the fewest weeks whose tapered shape can hold ``remaining`` and scales
    that shape down to match it exactly. Returns the PT that did not fit.
    """
    avail = [i for i in range(ramp_up, len(result)) if weekly_avail[i] > AVAIL_EPSILON]
    shape: list[float] = []
    used: list[int] = []
    for count in range(1, len(avail) + 1):
        used = avail[:count]
        shape = _tapered_shape(used, weekly_avail, ramp_down)
        if sum(shape) + REMAINING_EPSILON >= remaining:
            break
    capacity = sum(shape)
    scale = min(1.0, remaining / capacity) if capacity > 0 else 0.0
    for i, value in zip(used, shape, strict=True):
        result[i] = value * scale
    return max(0.0, remaining - capacity)


def _spill(
    result: list[float], weekly_avail: list[float], ramp_up: int, leftover: float
) -> None:
    """Put PT the ramp shape could not hold into weeks with free capacity.

    Fills from the end of the ramp-up forward, then the ramp-up weeks backward,
    so the shape stays as close to the requested ramps as capacity allows.
    """
    order = [*range(ramp_up, len(result)), *range(ramp_up - 1, -1, -1)]
    for i in order:
        if leftover <= REMAINING_EPSILON:
            return
        take = min(_cap_at(weekly_avail, i) - result[i], leftover)
        if take > REMAINING_EPSILON:
            result[i] += take
            leftover -= take


def distribute_with_avail(
    total_pt: float,
    weeks: int,
    ramp_up: int,
    ramp_down: int,
    weekly_avail: list[float],
) -> list[float]:
    """Front-load total_pt over weeks: saturate early weeks at their per-week cap.

    weekly_avail[i] = max PT week i can absorb (0 for absence / no capacity).
    Optional ramp_up: weeks 0..ramp_up-1 take fractional share of their cap.
    Plateau: each remaining week takes full cap until pt exhausted.
    Optional ramp_down: the last ramp_down used weeks taper off.
    PT the ramp shape cannot hold spills into weeks with free capacity.
    """
    if weeks <= 0 or not weekly_avail:
        return []
    ramp_up = max(0, min(ramp_up, weeks))
    ramp_down = max(0, min(ramp_down, weeks - ramp_up))
    result = [0.0] * weeks
    remaining = _fill_rampup(result, float(total_pt), ramp_up, weekly_avail)
    if ramp_down > 0:
        remaining = _fill_tapered(result, remaining, ramp_up, ramp_down, weekly_avail)
    else:
        remaining, _ = _fill_plateau(result, remaining, ramp_up, weeks, weekly_avail)
    _spill(result, weekly_avail, ramp_up, remaining)
    return [round(v, 2) for v in result]


def weeks_between(start: dt.date, end: dt.date) -> int:
    """Number of Monday-anchored weeks touched by [start, end]."""
    return len(week_starts(start, end))


def weekdays_in(week_start: dt.date, start: dt.date, end: dt.date) -> int:
    """Mon-Fri days of the week starting ``week_start`` inside [start, end]."""
    first = max(week_start, start)
    last = min(week_start + dt.timedelta(days=4), end)
    return sum(
        1
        for n in range((last - first).days + 1)
        if (first + dt.timedelta(days=n)).weekday() < WORKDAYS_PER_WEEK
    )


def default_gtk(total_pt: int, weeks: int) -> float:
    """Pick GTK so total_pt fits weeks * 5 PT/week, rounded up to .5."""
    if weeks <= 0 or total_pt <= 0:
        return 0.5
    raw = total_pt / (weeks * WORKDAYS_PER_WEEK)
    return max(0.5, min(30.0, math.ceil(raw * 2) / 2))


def week_free_days(
    week_start: dt.date,
    holidays: set[dt.date],
    workload_percent: int,
    absences: list[AbsencePeriod],
    internal_hours: int,
) -> float:
    """Work days of a week left after absences and capped internal time."""
    work_days = UtilizationService.work_days_for_week(
        week_start, holidays, workload_percent=workload_percent
    )
    absence_days = UtilizationService.absence_days_in_week(absences, week_start)
    internal_days = UtilizationService.cap_internal_days(
        internal_hours, absence_days, work_days=work_days
    )
    return work_days - absence_days - internal_days
