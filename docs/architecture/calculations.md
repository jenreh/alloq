---
title: Calculations
description: How Alloq calculates capacity, utilization, the plan distribution of the plan modal, earned value with its forecasts, free role capacity and the portfolio buffer, with the service functions that do it.
source_paths:
  - components/alloq-commons/src/alloq_commons/services/utilization.py
  - components/alloq-commons/src/alloq_commons/models/employee.py
  - components/alloq-project/src/alloq_project/services/planning_builders.py
  - components/alloq-project/src/alloq_project/services/plan_distribution.py
  - components/alloq-project/src/alloq_project/services/resource_planning.py
  - components/alloq-project/src/alloq_project/states/project_plan_state.py
  - components/alloq-project/src/alloq_project/services/forecast.py
  - components/alloq-project/src/alloq_project/states/project_state.py
  - components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py
  - components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py
  - spec/plans/dashboard-portfolio.md
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Calculations

This page explains how Alloq calculates its numbers and which functions do it. The
unit is the person day ("PT", Personentag). A week is Monday to Friday, and every
week is keyed by its Monday.

The German plan [`spec/plans/dashboard-portfolio.md`](../../spec/plans/dashboard-portfolio.md)
describes the intended rules of the portfolio. This page follows the code. Where
the code differs from the plan, the section says so.

| Topic | Main functions |
| --- | --- |
| Capacity of one person and week | `UtilizationService.work_days_for_week`, `absence_days_in_week`, `cap_internal_days` in [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) |
| Utilization | `UtilizationService.compute_employee_heat`, `compute_employee_gesamt`, `compute_team_utilization_series` |
| Plan distribution | `distribute`, `distribute_with_avail`, `week_free_days` in [`plan_distribution.py`](../../components/alloq-project/src/alloq_project/services/plan_distribution.py) |
| Earned value and forecast | `EVForecastService` in [`forecast.py`](../../components/alloq-project/src/alloq_project/services/forecast.py) |
| Free capacity per role | `load_free_capacity` in [`aggregation.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py), `Capacity` in [`resource_path.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py) |
| Portfolio buffer | `analyse_projects`, `weakest` in `resource_path.py`, `build_portfolio` in [`portfolio.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py) |

## Capacity of one person in one week

The docstring of `utilization.py` calls it the single source of truth for capacity
and utilization. The planning grid, the plan modal, the dashboard and the portfolio
use its functions.

**Workload.** The read model `Employee` derives `workload_percent` from the weekly
hours: `round(hours_per_week / 40 * 100)`, with `STANDARD_WEEKLY_HOURS = 40.0` in
[`models/employee.py`](../../components/alloq-commons/src/alloq_commons/models/employee.py).
An employee with 20 hours has a workload of 50.

**Work days.** `work_days_for_week(week_start, holiday_dates, workload_percent)`
does two steps:

1. It counts the public holidays from Monday to Friday of the week
   (`holidays_in_week`) and subtracts them from 5 (`WORK_DAYS_PER_WEEK`).
2. It scales the result by the workload (`apply_workload`):
   `max(0, work_days * workload_percent / 100)`.

**Absence days.** `absence_days_in_week` counts the days from Monday to Friday that
lie in at least one absence. Overlapping absences count a day once.

**Internal days.** `cap_internal_days(internal_hours, absence_days, work_days)`
turns the internal hours into days with 8 hours per day (`HOURS_PER_DAY`). The
result is at most `work_days - absence_days` and at least 0. The default of
`internal_hours` is 4 (see the [data model](./data-model.md#employeeentity)).

**Available days.**

```text
available = max(0, work_days - internal_days - absence_days)
```

## Utilization

### Percent per person and week

`compute_employee_heat(used_days, absence_days, internal_days, work_days)` gives
the utilization percent. `used_days` is the sum of the person days on projects in
that week.

- When the person is absent the whole week (`absence_days >= 5`), the percent is
  `round(used / (work_days - internal_days) * 100)` and the bucket is `absent`.
- When `available > 0`, the percent is `round(used / available * 100)`.
- Otherwise the percent is 0 and the bucket is `low`.

`heat_bucket` sorts the percent into buckets:

| Percent | Bucket |
| --- | --- |
| below 70 (`HEAT_LOW`) | `low` |
| 70 to below 85 (`HEAT_MID`) | `mid` |
| 85 to 100 (`HEAT_HIGH`) | `high` |
| above 100 | `over` |

`compute_heat_from_raw` does the full chain from the raw absence list.

### Free days in the planning grid

The planning grid shows a row "Gesamt (frei)" [total (free)] with the free days of
each person per week. `compute_gesamt` in
[`planning_builders.py`](../../components/alloq-project/src/alloq_project/services/planning_builders.py)
calls `compute_employee_gesamt`:

```text
free = work_days - internal_days - used_days - absence_days
```

The value is not cut at 0, so a negative value means the person is overbooked. The
tooltip text comes from `gesamt_breakdown`, e.g. "Arbeitstage 5,00 − Projekte
3,00 − Intern 0,50 − Abwesenheit 0,00 = 1,50 PT frei".

`gesamt_bucket` rounds the value to 2 decimals first, so a week that is booked
exactly stays neutral:

| Free days | Bucket |
| --- | --- |
| above 1 | `available` |
| above 0 to 1 | `balanced` |
| exactly 0 | `neutral` |
| -1 to below 0 | `tight` |
| below -1 | `over` |

A week with any absence gets the bucket `absent` instead.

`employee_summary` adds up the planned days and the free days from the current week
on. Weeks with a negative value count as 0 free days.

In the project view, the row "Gesamt (allokiert)" [total (allocated)] uses
`project_heat_bucket`: 0 or less is `low`, up to 2 is `mid`, up to 4 is `high`,
above 4 is `over`.

### Team series

`compute_team_utilization_series` builds the weekly series for a whole team. These
are the rules:

- `compute_heatmap_allocation_cells` keeps one value per employee, project and
  week. When the same person has rows in several roles on one project in one week,
  the last row wins. The docstring says this matches the visible cells of the
  planning heatmap.
- The team percent of a week is the plain average of the percents of all people
  (`compute_team_average`), not the sum of days divided by the sum of capacity.
- `free_hours_next_4w` adds `max(0, available - used) * 8` for the 4 weeks from the
  current week.

The dashboard loaders in `aggregation.py` (`load_utilization`,
`load_under_utilization`) use this series. They count only allocations of projects
that are not "Abgeschlossen" [completed]. A person counts as under used below 70
percent (`UNDER_UTIL_THRESHOLD`) and as overloaded above 100 percent
(`OVER_UTIL_THRESHOLD`) in the current week. People who are absent the whole week
are left out of both counts.

## Plan distribution in the plan modal

The modal "Projekt planen" [plan project] spreads the person days of a project over
its weeks. The state is `ProjectPlanState` in
[`project_plan_state.py`](../../components/alloq-project/src/alloq_project/states/project_plan_state.py).

### Project chart: `distribute`

The chart of the whole project uses
`distribute(total_pt, weeks, ramp_up, ramp_down, cap_per_week)`:

1. Each week gets a weight. The ramp up weeks rise as `(i + 1) / (ramp_up + 1)`,
   the middle weeks have weight 1, and the ramp down weeks fall as
   `(ramp_down - i) / (ramp_down + 1)`.
2. The value of a middle week is `total_pt / sum(weights)`, cut at
   `cap_per_week`.
3. With a cap, every week snaps to a quarter of the cap: 0, 0.25, 0.5, 0.75 or 1
   times the cap (`PT_QUANTA_PER_WEEK = 4`). Quarters are then added to or removed
   from the weeks with the largest rounding rest, so the total stays as close to
   `total_pt` as the shape allows.

The cap is `gtk_count * 5` PT per week. The modal sets `gtk_count` with the slider
"Kapazität / Wo." [capacity per week] from 0.5 to 30 GTK in steps of 0.5. The code
does not spell out GTK; the cap treats one GTK as 5 PT per week. `default_gtk`
picks `total_pt / (weeks * 5)`, rounded up to the next 0.5, between 0.5 and 30.
`effective_weeks` shortens the chart when the GTK gives more capacity than needed:
`ceil(total_pt / cap + ramp_up / 2 + ramp_down / 2)`, between 1 and the number of
project weeks.

### Per person: `distribute_with_avail`

The preview and the save use
`distribute_with_avail(total_pt, weeks, ramp_up, ramp_down, weekly_avail)` for each
selected person. `weekly_avail` is the free capacity of the person in each week
(`_weekly_avail`):

```text
free = week_free_days(...) - person days already planned on other projects
```

`week_free_days` is `work_days - absence_days - internal_days`. `_weekly_avail`
then caps a partial first or last week at the weekdays inside the project window
(`weekdays_in`), scaled by the workload. It never returns a value below 0.

The function fills the weeks in this order:

1. Ramp up weeks take `(i + 1) / (ramp_up + 1)` of their free capacity
   (`_fill_rampup`).
2. Without ramp down, the next weeks are filled to their free capacity from left to
   right until the person days are used up (`_fill_plateau`).
3. With ramp down, `_fill_tapered` uses the fewest weeks whose tapered shape can
   hold the rest. The last `ramp_down` used weeks fall off. The shape is scaled
   down to match the rest exactly.
4. Person days that do not fit go into weeks with free capacity (`_spill`), first
   from the end of the ramp up forward, then backward through the ramp up weeks.

A week with 0.05 PT free or less (`AVAIL_EPSILON`) counts as not available. When
a role has `ramp_up` or `ramp_down` set ([`RoleEntity`](./data-model.md#roleentity)),
the role is needed from the start or until the end, so `_effective_ramps_for` sets
that ramp to 0 for its people.

### Saving

`save_plan` (`@requires_editor`) calls `apply_resource_plan` in
[`resource_planning.py`](../../components/alloq-project/src/alloq_project/services/resource_planning.py)
for every planned person. For the weeks of the project window it does this:

1. It deletes the allocations of this person on this project.
2. It writes the new weekly rows with `batch_upsert`.
3. It creates the `capacities` row for project, person and role, or widens its date
   range (`_sync_capacity`).
4. It deletes `capacities` rows of other roles that have no allocation left
   (`_prune_capacities`).

Other people and weeks outside the window keep their allocations.

The "Ressourcen" [resources] tab of a project uses `plan_weekly_days` from the same
module. Each week gets the asked days per week, scaled by the weekdays of the week
inside the range, cut at the free days of the person and rounded down to 0.1.

## Earned value and forecast

`EVForecastService` in [`forecast.py`](../../components/alloq-project/src/alloq_project/services/forecast.py)
works with the budget of the project (BAC) and the status reports. A status report
holds `progress` and `budget_spent`, both in percent.

```text
EV  = budget * progress / 100          earned value
AC  = budget * budget_spent / 100      actual cost
EAC_linear   = budget * AC / EV        (budget, when EV <= 0)
EAC_additive = budget + AC - EV
```

The linear forecast assumes that the cost behavior so far goes on. The additive
forecast assumes that the variance so far happens once and the rest follows the
plan.

Where the values come from:

- `compute_status_ev` runs when a status report is saved (`add_project_status` in
  [`project_state.py`](../../components/alloq-project/src/alloq_project/states/project_state.py)).
  The values are stored on the `project_statuses` row.
- `build_summary` takes the newest status report. On the same date, the later
  created report wins (`_status_order`). `_persist_ev_summary` writes the result to
  `ev_earned_value`, `ev_actual_cost`, `ev_eac_linear` and `ev_eac_additive` on the
  project.

### Chart of a project

`build_chart_data` builds the earned value chart of a project
(`ProjectState.ev_chart_data`). It returns no points when the dates are missing,
when the end is not after the start or when the budget is 0.

**Planned value (PV).** With weekly allocations, PV follows the planned person days
(`_cumulative_pv`):

```text
week_value = budget * week_pt / total_pt
```

Weeks that ended before the date count in full. The week that holds the date counts
by elapsed days divided by 7. Before that, `_scale_allocations` cuts the person
days of each person and week at their capacity from `work_days_for_week`, so an
overbooked plan does not move PV. Without allocations, PV grows in a straight line
from 0 at the start to the budget at the end. The chart then makes PV never fall.

**Forecast curves.** After the last status report, the chart adds one point per
week up to the end. Both forecasts start at the last AC and grow in a straight line
to `EAC_linear` and `EAC_additive` at the end date. The chart series are named
"Planned Value", "Earned Value", "Actual Cost", "Prognose (linear)" and "Prognose
(additiv)".

### Portfolio budget series

`_build_weekly_forecast_series` in `aggregation.py` adds up the active projects
("Aktiv" and "Risiko") per week. For each project it uses the newest status report
up to the end of that week. When a stored value is missing it falls back:

- `actual_cost`, else `budget * budget_spent / 100`, else 0 (`_resolve_actual_cost`).
- `eac_linear`, else `actual_cost / (progress / 100)`, else `actual_cost`
  (`_resolve_eac_linear`).
- `eac_additive`, else `eac_linear` (`_resolve_eac_additive`).

`_classify_overrun` colors a project by `EAC_additive` against the budget: green
when it is within the budget, yellow up to 10 percent above
(`YELLOW_OVERRUN_RATIO = 1.10`), red above that. `load_budget_burn` returns this
series. At this commit no page renders the earned value card that shows it (see
the open questions).

## Free capacity per role

### Sidebar

The sidebar section "Freie Kapazität" [free capacity] shows `free_days` per role
from `load_free_capacity` (`RoleCapacityState`). For each role:

```text
role_available(week) = sum over the role's people of
                       max(0, available - days booked in other roles)
free_days            = max(0, sum of role_available over the weeks
                              - sum of days booked in this role over the weeks)
```

The cut at 0 applies to the total, so the days overbooked in one week are
subtracted from the free days of the other weeks. The weekly points that `load_free_capacity` also returns are
cut at 0 per week, but the sidebar does not show them.

`_role_available_days` subtracts the days a person has booked in another role, so
the time of a person with several roles is not offered twice. The section adds up
the weeks from the current week on, at most 12 (`HORIZON_WEEKS = 12`), and sorts
the roles by free days, most first. Bookings on completed projects do not count.

### Portfolio

The `Capacity` class in `resource_path.py` uses the same rule for the role
availability, but it does not cut the free days at 0:

```text
free(role, week) = role_available - role_allocated
```

A negative value means the role is overbooked. Bookings count on every project that
is not completed, also outside the chosen scope, because they use up the time of a
person. The role sums only count the people in scope. The portfolio looks 52 weeks
ahead (`LOOKAHEAD_WEEKS`) and shows 13 weeks (`HORIZON_WEEKS = 13`).

## Portfolio buffer

The dashboard `/dashboard` ("Übersicht") shows the portfolio. `build_portfolio` in
[`portfolio.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py)
puts it together.

**Scope.** The toolbar offers "Ganze Abteilung" [whole department] and "Direkt
unterstellt" [direct reports]. `apply_scope` in
[`portfolio_inputs.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py)
keeps, for "Direkt unterstellt", the employees whose `manager_id` is the employee
with the email of the signed-in user, and the projects that list this employee in
`owners`. Without such an employee, the page shows `NO_PROFILE_NOTICE`.

### Buffer of one role in one project

`_role_work` works per project and required role:

```text
remaining = max(0, required - person days booked before this week)
planned   = person days booked from this week on
gap       = max(0, remaining - planned)
```

1. The cover week is the first week in which the planned days reach
   `min(remaining, planned)` (`_planned_cover`).
2. When there is a gap, `_consume` takes free role capacity from the pool, from the
   later of this week and the project start, until the gap is covered. The cover
   week is then the later of the two weeks. When 52 weeks are not enough, the role
   is not covered.
3. `_role_line` computes `buffer = end week - cover week`, in weeks. A role that is
   not covered uses 52 as its cover week. Its reason starts with "Nicht gedeckt in
   52 Wochen." [not covered in 52 weeks] and its tone is `neg`.
4. A role with no remaining demand cannot delay the project. Its buffer is at
   least 0 and its reason is "Bedarf erfüllt." [demand met].

`analyse_projects` hands out the free capacity by end date, earliest first, so an
earlier project is staffed first. Completed projects and projects without required
capacity get no role lines.

`buffer_tone` marks a buffer below 0 as `neg` and a buffer of 0 or 1 as `warn`.

### Weakest role and reason

`weakest` picks the role line with the smallest buffer. On a tie it picks the more
severe tone, then the role name. The project shows the buffer of this role.

`_explain` gives the reason. It takes the first that applies:

1. Nobody is planned and there is a gap: "niemand eingeplant" [nobody planned],
   with the gap in PT.
2. The role is overbooked in a week from this week or the project start, whichever
   is later, up to the project end or the end of the 13 week horizon, whichever is
   earlier: "Rolle ab KW .. überbucht." [role overbooked from week ..].
3. Only one person carries the role and is absent before the project end:
   "Einzige Person für die Rolle. Abwesend ..." [only person for the role, absent].
4. The project ends within 8 weeks (`NEAR_END_WEEKS`) and a carrier is above 100
   percent in the current week.
5. Only one person carries the role: "Einzige Person für die Rolle."
6. A gap is left: "... PT ohne Plan." [PT without a plan].
7. Otherwise: "Bedarf gedeckt bis KW .." [demand covered until week ..].

### Other portfolio numbers

- **Role demand** (`role_demands`). Need is the planned days in the 13 weeks plus
  the share of the gap that falls into them. The share is the part of the remaining
  project weeks inside the 13 weeks (`_horizon_share`).
- **Bubbles** (`bubbles`). Only projects "Aktiv" or "Risiko" are drawn. The x
  position is the elapsed time in percent (`elapsed_percent`), the y position is the
  progress. The size grows with the square root of the budget. The color comes from
  `health`, which compares the EAC with the budget like `_classify_overrun`. Without
  an EAC there is no color. A negative buffer marks the bubble (`negative_buffer`).
  The EAC comes from `_latest_eac`: the project's `ev_eac_additive`, else the newest
  status report, else spent cost divided by progress.
- **Risk matrix** (`risk_matrix`). Open risks (`open`) of the projects in scope are
  counted per probability and impact, both cut to 1 to 5. `severity` is low up to a
  score of 4, medium up to 15 and high above.
- **Chains** (`chains`). Projects with a buffer below 4 weeks (`COMFORT_WEEKS`) are
  listed, at most 6. The others are named in one line.

## Tests

| Topic | Tests |
| --- | --- |
| Utilization | [`test_utilization.py`](../../components/alloq-commons/tests/test_utilization.py) |
| Plan distribution | [`test_project_plan_state.py`](../../components/alloq-project/tests/test_project_plan_state.py), e.g. `test_tail_tapers_without_spike`, `test_skips_blocked_weeks` |
| Resource tab planning | [`test_resource_planning.py`](../../components/alloq-project/tests/test_resource_planning.py) |
| Earned value | [`test_forecast.py`](../../components/alloq-project/tests/test_forecast.py), e.g. `test_eac_linear_formula`, `test_capacity_weighted_pv_at_status_date` |
| Dashboard loaders | [`test_aggregation.py`](../../components/alloq-dashboard/tests/test_aggregation.py), [`test_aggregation_utilization.py`](../../components/alloq-dashboard/tests/test_aggregation_utilization.py) |
| Portfolio and buffer | [`test_portfolio.py`](../../components/alloq-dashboard/tests/test_portfolio.py), e.g. `test_gap_without_carrier_gives_negative_buffer`, `test_earlier_project_gets_free_capacity_first` |

The stories that use these numbers are on the [story map](../features/story-map.md).

## Open questions

- The plan says gap capacity is taken "ab dieser Woche" [from this week]. The code
  starts at the later of this week and the project start (`_consume` with
  `calendar.index(project.start_date)`). The code wins here.
- The plan says the dashboard is at `/`. In the code, `/` is the planning page and
  the dashboard is at `/dashboard`. The plan also says all portfolio handlers use
  `@requires_admin`; the code uses the editor check, as on every planning page.
- The docstring of `RoleCapacityState` says "over 13 weeks", but
  `load_free_capacity` uses at most 12 weeks (`HORIZON_WEEKS = 12` in
  `aggregation.py`).
- `ProjectsOverviewState`, `ProjectHealthState`, `BudgetBurnState`,
  `UtilizationState`, `UnderUtilizationState` and `RiskState` still load their
  data, and `project_state.py` reloads `ProjectHealthState` and `RiskState`. No
  page renders their cards at this commit. It is open whether this code is meant to
  stay.
- `compute_heatmap_allocation_cells` keeps only the last role row for the same
  person, project and week. It is not checked here whether the planning grid can
  create two role rows for one person on one project in one week.
