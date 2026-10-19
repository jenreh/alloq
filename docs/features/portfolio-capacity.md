---
title: Portfolio staffing and capacity
description: How admins and project managers find staffing bottlenecks on the page "Übersicht" at /dashboard with the cards "Kritischer Ressourcenpfad" and "Kapazität je Rolle", open a role or a person in the side drawer, and read the free capacity per role in the sidebar.
story_ids: [DASH-08, DASH-09, DASH-10, DASH-11, DASH-12, DASH-15, DASH-16, DASH-13]
source_paths:
  - app/components/sidebar.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py
  - components/alloq-dashboard/src/alloq_dashboard/states/dashboard_states.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py
  - components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py
  - components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py
  - components/alloq-dashboard/src/alloq_dashboard/services/aggregation_rows.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_path.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_drawer.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_shared.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Portfolio staffing and capacity

This page covers how admins and project managers see where staffing holds up the portfolio. The stories belong to the activity "Watch the portfolio" on the [story map](./story-map.md). The first cards of the same page are on [Portfolio overview](./portfolio.md).

The page has one user task, **Check staffing and capacity**, with these sub-tasks:

- **Find staffing bottlenecks.** Read the card "Kritischer Ressourcenpfad" [critical resource path], with the buffer of each project role and the person and reason behind the weakest role.
- **Check capacity per role.** Read the card "Kapazität je Rolle" [capacity per role], open a role in the side drawer, and read the free capacity per role in the sidebar.
- **Check a person's load.** Open a person in the side drawer and see their load, absences and bookings.

All portfolio numbers come from the pure functions in `resource_path.py`, which `build_portfolio` calls once per load. The module has no milestones. It derives the critical path from staffing only, so a project's end date depends on the role whose remaining demand is covered last. The formulas for the buffer are in [portfolio buffer](../architecture/calculations.md#portfolio-buffer), and the formulas for free capacity are in [free capacity per role](../architecture/calculations.md#free-capacity-per-role). The available days of a person come from the shared utilization calculation described in [DASH-14](./planning-grid.md#dash-14).

## DASH-08 Projects with low staffing buffer {#dash-08}

A card lists the projects with less than 4 weeks of staffing buffer and names the role and person each one depends on.

As a project manager, I want to see for each tight project the role and person its end date depends on, so that I know where to act first.

Project manager · Check staffing and capacity / Find staffing bottlenecks · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** unfinished projects in scope with required capacity, **when** the card "Kritischer Ressourcenpfad" is built, **then** `chains` lists the projects whose buffer is below 4 weeks (`COMFORT_WEEKS`), sorted by buffer and then by code, at most 6 of them (`MAX_CHAINS`).
2. **Given** the card, **when** its header is drawn, **then** it shows the subtitle "Je Projekt das schwächste Glied. Sortiert nach Puffer in Wochen." [per project the weakest link, sorted by buffer in weeks] and on the right the hint "Projekt → Rolle → Person → Grund" [project, role, person, reason]. (no test)
3. **Given** a listed project, **when** its row is drawn, **then** the row shows the buffer badge "&lt;buffer&gt; W", then the pills for the project (code and name), the weakest role and the person, joined by arrows, and the reason of the weakest role below them. The person pill has the color of the role line's tone.
4. **Given** a buffer value, **when** its badge is drawn, **then** a positive buffer or 0 reads "+&lt;n&gt;" and a negative buffer uses a minus sign. The badge is red below 0 weeks, yellow at 0 or 1 week, and grey otherwise.
5. **Given** a project row, **when** the user clicks the project, role or person pill, **then** the project drawer, the role drawer or the person drawer opens. When the role line has no person id, the person pill shows "niemand eingeplant" [nobody planned] as plain text.
6. **Given** projects with 4 or more weeks of buffer, or unfinished projects with no recorded demand, **when** the card is drawn, **then** a line below the list names them, e.g. "Mit 4 Wochen Puffer oder mehr: AQ-112 +30. Ohne erfassten Bedarf: 1 Projekt." [with 4 weeks of buffer or more ... without recorded demand: 1 project].
7. **Given** that no project has less than 4 weeks of buffer, **when** the card is drawn, **then** it shows "Alle Projekte haben mindestens 4 Wochen Puffer." [all projects have at least 4 weeks of buffer]. (no test)

### Evidence

- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `chains`, `COMFORT_WEEKS`, `MAX_CHAINS`, `_project` (`weakest`, `has_buffer`), `build_portfolio`
- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `buffer_label`, `buffer_tone`, `weakest`, `NO_CARRIER`
- [portfolio_path.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_path.py): `portfolio_chains_card`, `_chain`
- [portfolio_shared.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_shared.py): `tone_badge`, `tone_color`
- Tests: [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_build_portfolio_for_the_department`, `test_format_helpers`; [test_components.py](../../components/alloq-dashboard/tests/test_components.py) `test_chain_pills_open_project_role_and_person`

## DASH-09 Buffer per project role {#dash-09}

The buffer of a project role is the number of weeks between the week its remaining demand is covered and the project end.

As a project manager, I want a buffer in weeks for each role a project needs, so that I can see how much delay the staffing can absorb.

Project manager · Check staffing and capacity / Find staffing bottlenecks · priority 2 · core · v2.0.4

### Acceptance criteria

1. **Given** a project role with required person days and bookings, **when** the role line is built, **then** the remaining demand is the required days minus the days booked before this week, the planned days are the days booked from this week on, and the gap is the remaining demand minus the planned days, never below 0.
2. **Given** a role with a gap, **when** the cover week is found, **then** `_consume` takes the gap from the role's free days week by week, from the later of this week and the project start. Unfinished projects take free days in order of their end date, the earliest first, so an earlier project is staffed first.
3. **Given** a cover week, **when** the buffer is calculated, **then** the buffer is the project's end week minus the cover week, so a role covered after the project end has a negative buffer.
4. **Given** a gap that free capacity cannot cover within 52 weeks, **when** the role line is built, **then** the line is marked as not covered, its tone is red and its reason starts with "Nicht gedeckt in 52 Wochen." [not covered in 52 weeks].
5. **Given** a role with no remaining demand, **when** the role line is built, **then** the buffer is at least 0 and the reason is "Bedarf erfüllt." [demand met], because the role cannot delay the project.
6. **Given** a project, **when** its project buffer is set, **then** it is the buffer of the weakest role. `weakest` picks the smallest buffer, then the more severe tone, then the role name. Completed projects get no role lines, and projects without required capacity get no buffer.
7. **Given** the bookings of a person, **when** role capacity is counted, **then** bookings on every unfinished project count, also outside the scope, and bookings on completed projects do not. Free capacity can go below 0 when a role is overbooked.

### Evidence

- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `Calendar`, `Capacity` (`__init__`, `free`, `free_pool`), `_role_work`, `_planned_cover`, `_consume`, `_role_line`, `weakest`, `analyse_projects`
- [portfolio_inputs.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py): `LOOKAHEAD_WEEKS`, `booking_projects`
- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `_project`, `build_portfolio`
- Tests: [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_planned_work_sets_the_cover_week`, `test_earlier_project_gets_free_capacity_first`, `test_gap_without_carrier_gives_negative_buffer`, `test_uncovered_gap_is_flagged`, `test_fulfilled_role_cannot_delay_an_overdue_project`, `test_weakest_prefers_smaller_buffer_then_severity`, `test_completed_projects_do_not_book_capacity`

## DASH-10 Person to look at and reason {#dash-10}

Each role line names the person to look at and gives a one-sentence reason, picked by fixed rules.

As a project manager, I want a short reason and a name for each weak role, so that I know whom to talk to without reading the plan.

Project manager · Check staffing and capacity / Find staffing bottlenecks · priority 3 · core · v2.0.4

`_explain` takes the first rule that applies. The order of the rules is listed in [weakest role and reason](../architecture/calculations.md#weakest-role-and-reason).

### Acceptance criteria

1. **Given** a role with a gap and nobody booked, **when** the reason is chosen, **then** the person is "niemand eingeplant", the tone is red and the reason is "&lt;n&gt; PT ohne Plan." [person days without a plan]. When the role is overbooked in a project week inside the 13 week horizon, the reason adds "Die Rolle ist ab KW &lt;nn&gt; überbucht." [the role is overbooked from week nn].
2. **Given** a role with people booked that is overbooked from a week on, **when** the reason is chosen, **then** the tone is red and the reason is "Rolle ab KW &lt;nn&gt; überbucht." [role overbooked from week nn], followed by the gap text when there is a gap.
3. **Given** a role with exactly one booked person who is absent between this week and the project end, **when** the reason is chosen, **then** the tone is yellow and the reason is "Einzige Person für die Rolle. Abwesend KW &lt;a&gt; bis KW &lt;b&gt;." [only person for the role, absent from week a to week b], or "Abwesend in KW &lt;a&gt;." for one week.
4. **Given** a project that ends within 8 weeks (`NEAR_END_WEEKS`) and a booked person above 100 % in the current week, **when** the reason is chosen, **then** the tone is red, that person is named and the reason is "&lt;pct&gt; % ausgelastet. Das Projekt endet am &lt;dd.mm.&gt;" [utilized, the project ends on].
5. **Given** a role carried by one person with no other issue, **when** the reason is chosen, **then** the tone is yellow and the reason is "Einzige Person für die Rolle." [only person for the role].
6. **Given** a role with several booked people, **when** the person label is built, **then** the people are ordered by booked days, the first two are named and the rest is shown as "+&lt;n&gt;". The reason is "&lt;n&gt; PT ohne Plan." when a gap is left, or else "Bedarf gedeckt bis KW &lt;nn&gt;." [demand covered until week nn].
7. **Given** a role line, **when** the line is built, **then** `person_id` is the id of the person to open, and 0 when nobody is booked.

### Evidence

- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `_explain`, `_carrier_issue`, `_overbooked_from`, `_absence_in`, `_names`, `_Why`, `_role_line`, `NO_CARRIER`, `NEAR_END_WEEKS`, `OVERLOAD_PERCENT`, `MAX_CARRIER_NAMES`, `week_label`, `format_days`
- Tests: [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_gap_without_carrier_gives_negative_buffer`, `test_overbooked_role_is_named_with_its_first_week`, `test_single_absent_carrier_is_a_warning`, `test_overloaded_carrier_near_the_end`, `test_planned_work_sets_the_cover_week`, `test_several_carriers_with_gap_and_covered`, `test_role_line_names_the_person_to_open`

## DASH-11 Capacity per role for 13 weeks {#dash-11}

A card shows for each role the planned days, the demand and the available days over the next 13 weeks, and the gap between them.

As a project manager, I want to compare planned work, demand and availability per role, so that I know which roles need more people.

Project manager · Check staffing and capacity / Check capacity per role · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** people in scope with roles, **when** the available days of a role are summed, **then** each person adds their available days of the week minus the days they are booked in other roles, never below 0, over the 13 weeks from this week (`HORIZON_WEEKS = 13`).
2. **Given** a project gap that runs past the 13 week horizon, **when** the demand of a role is calculated, **then** the demand is the planned days plus only the part of the gap that falls inside the horizon. The gap is spread evenly over the remaining project weeks.
3. **Given** the role rows, **when** the card "Kapazität je Rolle" is drawn, **then** roles with no people and no demand are left out and the rows are sorted by gap from large to small and then by name. Each row shows the role name, "&lt;n&gt; Pers." [persons], "Lücke &lt;n&gt; PT" [gap in person days], which is red from 15 person days (`GAP_ALERT_DAYS`), and "&lt;planned&gt; von &lt;need&gt;" [planned of need].
4. **Given** a role row, **when** its bar is drawn, **then** 80 % of the bar width stands for 100 % availability. The planned part is blue, overbooking adds a red part of up to 20 %, and a dark marker shows the demand. The card subtitle explains this with "13 Wochen. Blau: geplant. Strich: Bedarf. Grau: verfügbar." [13 weeks, blue planned, line demand, grey available].
5. **Given** the role rows, **when** the card header is drawn, **then** it shows the total "Lücke &lt;n&gt; PT" as the sum of all role gaps (`gap_total`).
6. **Given** that no role has people or demand in the scope, **when** the card is drawn, **then** it shows "Keine Rollen mit Personen im gewählten Bereich." [no roles with people in the selected scope]. (no test)

### Evidence

- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `Capacity.__init__` (`role_available`, `role_allocated`, `role_people`), `role_demands`, `_horizon_share`, `_bar`, `HORIZON_WEEKS`, `BAR_FULL`, `BAR_OVER_MAX`, `NEED_MAX_RATIO`
- [portfolio_path.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_path.py): `portfolio_roles_card`, `_role`, `_bar`, `GAP_ALERT_DAYS`
- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `build_portfolio` (`gap_total`)
- Tests: [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_bookings_in_other_roles_reduce_role_availability`, `test_role_demand_adds_gap_share_inside_horizon`, `test_role_demand_marks_overbooking_and_skips_empty_roles`, `test_build_portfolio_for_the_department`

### Open questions

- The rows of the card "Kapazität je Rolle" are not clickable. The role drawer opens only from the critical path card, the project drawer and the person drawer.

## DASH-12 Role side panel {#dash-12}

Clicking a role opens a side panel with its weekly capacity, the people who hold it and the projects with a gap in it.

As a project manager, I want to open a role and see its weeks, people and gaps, so that I can decide who could take more work.

Project manager · Check staffing and capacity / Check capacity per role · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a role pill or role link, **when** the user clicks it, **then** `PortfolioState.open_role` stores the role id and opens the drawer titled "Rolle &lt;name&gt;" [role]. The handler has `@requires_editor`.
2. **Given** the open role drawer, **when** the summary is shown, **then** it shows "Personen", "Verfügbar", "Geplant" and "Frei" [people, available, planned, free] summed over the next 13 weeks, with the note "Summen über die nächsten 13 Wochen." [sums over the next 13 weeks]. "Frei" is red when it is below 0.
3. **Given** the open role drawer, **when** the table "Je Woche" [per week] is shown, **then** it has 13 rows with the columns "Woche", "Verfügbar", "Geplant" and "Frei", and free days below 0 are red.
4. **Given** people in scope who hold the role, **when** the section "Personen mit der Rolle" [people with the role] is shown, **then** each person, sorted by name, shows "geplant &lt;n&gt; PT" [planned] in this role and the average load "Ø &lt;n&gt; %", red above 100 %. A click on the name opens the person drawer.
5. **Given** projects with unplanned demand in the role, **when** the section "Projekte mit Lücke" [projects with a gap] is shown, **then** each project with a gap above 0 is listed with "Lücke &lt;n&gt; PT" and its buffer badge, smallest buffer first and then by code. A click opens the project drawer.
6. **Given** that nobody in scope holds the role, or that no project has a gap in it, **when** the drawer is shown, **then** it shows "Im gewählten Bereich hat niemand diese Rolle." [nobody in the selected scope has this role] or "Kein Projekt hat für diese Rolle Bedarf ohne Plan." [no project has unplanned demand for this role]. (no test)

### Evidence

- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.open_role`, `PortfolioState.selected_role`, `DRAWER_ROLE`
- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `role_details`, `_role_week`, `_role_person`, `_gap_projects`, `_avg_percent`, `_load_tone`
- [portfolio_drawer.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_drawer.py): `_title`, `_role_body`, `_role_week`, `_role_person`, `_gap_project`
- Tests: [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_role_and_person_drawers`; [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_role_detail_shows_weeks_people_and_gaps`, `test_role_detail_free_days_go_negative_when_overbooked`

## DASH-15 Free capacity in the sidebar {#dash-15}

The sidebar shows the free person days of each role for the next 12 weeks to admins and project managers.

As a project manager, I want to see the free capacity per role in the sidebar on every page, so that I know who has time while I plan.

Project manager · Check staffing and capacity / Check capacity per role · priority 3 · comfort · v2.0.0

### Acceptance criteria

1. **Given** a signed-in admin or project manager, **when** any page with the sidebar is shown, **then** the sidebar shows the section "Freie Kapazität" [free capacity] and starts `RoleCapacityState.load` when it is mounted. Both are wrapped in `editor_only`, so other users see neither.
2. **Given** roles, employees and bookings, **when** the free capacity per role is calculated, **then** each member of the role adds, for each of the 12 weeks from this week, their available days minus their bookings in other roles, never below 0. The bookings in the role itself are then subtracted, and the total is never below 0.
3. **Given** public holidays and part-time employees, **when** the available days are calculated, **then** holidays and the workload percent reduce the available days through the shared utilization calculation.
4. **Given** bookings on a completed project, **when** the free capacity is calculated, **then** those bookings are not counted. (no test)
5. **Given** the role rows, **when** the section is drawn, **then** the roles are sorted by free days from high to low. (no test)
6. **Given** a role row, **when** it is drawn, **then** it shows a colored dot, the role name and the free days with one decimal and " PT".
7. **Given** that the data is loading, empty or failed, **when** the section is drawn, **then** it shows the error message in red after a failure. Otherwise it shows "Kapazität wird geladen ..." [loading capacity] while loading or before the first load, and "Keine Rollen verfügbar." [no roles available] when there are no rows. (no test)

### Evidence

- [sidebar.py](../../app/components/sidebar.py): `sidebar` (`editor_only` with `on_mount=RoleCapacityState.load`), `_capacity_section`, `_capacity_item`
- [dashboard_states.py](../../components/alloq-dashboard/src/alloq_dashboard/states/dashboard_states.py): `RoleCapacityState.load`
- [aggregation.py](../../components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py): `load_free_capacity`, `_role_available_days`, `_employee_available_days`, `_load_utilization_inputs` (`active_project_ids`), `HORIZON_WEEKS`
- [aggregation_rows.py](../../components/alloq-dashboard/src/alloq_dashboard/services/aggregation_rows.py): `_role_to_row`, `_ROLE_COLORS`
- Tests: [test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarComponent.test_renders_navigation_entries`; [test_aggregation_utilization.py](../../components/alloq-dashboard/tests/test_aggregation_utilization.py) `test_free_capacity_does_not_double_count_multi_role_employee`, `test_free_capacity_subtracts_holidays_and_workload`

### Open questions

- The sidebar uses 12 weeks (`HORIZON_WEEKS = 12` in `aggregation.py`) and all employees. The card "Kapazität je Rolle" uses 13 weeks and the chosen scope, and it does not cut free days at 0 per week. The two numbers can differ.
- The docstring of `RoleCapacityState` says 13 weeks, but `load_free_capacity` uses 12.
- `load_free_capacity` also computes monthly values and weekly points per role, but the sidebar shows only `free_days`. The old card in `capacity_card.py` that showed them is not mounted, see [Not covered](./story-map.md#not-covered).
- `RoleCapacityState` exists since v0.2.0, and the sidebar section was added in v2.0.0.

## DASH-16 Background load with cache {#dash-16}

The sidebar capacity loads in the background, checks edit rights, and is reused for 30 seconds.

As a project manager, I want the capacity numbers to load in the background and not on every page change, so that pages stay fast.

Project manager · Check staffing and capacity / Check capacity per role · priority 4 · comfort · v0.3.0 (approximate)

`RoleCapacityState.load` is a background event that runs `_CardLoadMixin._run_card_load`. The tests below exercise the shared mixin through `ProjectsOverviewState`.

### Acceptance criteria

1. **Given** a card load handler such as `RoleCapacityState.load`, **when** it runs, **then** it checks inside the state lock that the user is an admin or project manager (`_can_edit`). Otherwise it logs a warning and loads nothing.
2. **Given** a project manager, **when** a card load runs, **then** the load runs, because `can_edit` also allows the role project_manager.
3. **Given** data loaded less than 30 seconds ago (`CACHE_TTL_SECONDS`), **when** the load runs again without `force`, **then** nothing is loaded and the cached data stays. Because the sidebar starts the load on every page, this check keeps a page change from loading the data again.
4. **Given** that the loader raises an error, **when** the load runs, **then** `is_loading` goes back to false and `error_message` is "Daten konnten nicht geladen werden." [data could not be loaded], without any technical detail.
5. **Given** two loads of the same card that overlap, **when** the older one finishes last, **then** its result is discarded, because each load has a sequence number (`_load_seq`) and only the newest one is stored.

### Evidence

- [dashboard_states.py](../../components/alloq-dashboard/src/alloq_dashboard/states/dashboard_states.py): `_CardLoadMixin._run_card_load`, `_can_edit`, `_is_fresh`, `CACHE_TTL_SECONDS`, `LOAD_ERROR_MESSAGE`, `RoleCapacityState`
- [access.py](../../components/alloq-commons/src/alloq_commons/access.py): `can_edit`
- Tests: [test_dashboard_states.py](../../components/alloq-dashboard/tests/test_dashboard_states.py) `test_card_load_rejects_non_admin`, `test_card_load_runs_for_project_manager`, `test_projects_overview_load_skips_when_fresh`, `test_projects_overview_load_records_error`, `test_superseded_load_does_not_overwrite_newer_result`; [test_handler_authorization.py](../../tests/test_handler_authorization.py) `INLINE_ADMIN_CHECK`

### Open questions

- The 30 second cache exists since v0.2.0 and the shared `_CardLoadMixin` since v0.3.0. Project managers may run the load since v2.0.4. Before that it was admin only.

## DASH-13 Person side panel {#dash-13}

Clicking a person opens a side panel with their weekly load, absences and bookings for the next 13 weeks.

As a project manager, I want to open a person and see their load, absences and bookings, so that I can judge whether they can take on more work.

Project manager · Check staffing and capacity / Check a person's load · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** a person link or pill, **when** the user clicks it, **then** `PortfolioState.open_person` stores the employee id and opens the drawer with the person's name as title. The handler has `@requires_editor`.
2. **Given** the open person drawer, **when** the summary is shown, **then** it shows "Rollen" [roles] or "Keine" [none], "Ø Auslastung" [average load] in red above 100 %, and "Abwesend" [absent] as "&lt;n&gt; Arbeitstage" [work days], with the note "Werte für die nächsten 13 Wochen." [values for the next 13 weeks].
3. **Given** the open person drawer, **when** the table "Auslastung je Woche" [load per week] is shown, **then** it has 13 rows with a load bar, "&lt;booked&gt; von &lt;available&gt; PT" and the percent, red above 100 %. The bar is capped at 100 %, and a fully absent week shows "abwesend" [absent] instead of the bar.
4. **Given** a person with absences, **when** the section "Abwesenheiten" [absences] is shown, **then** only absences in the 13 weeks are listed, cut to that range. Each one is labelled "dd.mm.yyyy" or "dd.mm. bis dd.mm.yyyy" and shows the count of work days that are not weekends or public holidays.
5. **Given** a person booked on projects, **when** the section "Gebucht auf" [booked on] is shown, **then** the bookings on unfinished projects in the 13 weeks are summed per project and role and sorted by days from high to low. The project name is a link only when the project is in scope, and the role name opens the role drawer.
6. **Given** people in scope and people named in role lines, **when** the person details are built, **then** both groups get a drawer, so a named person outside the scope can still be opened.
7. **Given** a person with no absence or no booking in the 13 weeks, **when** the drawer is shown, **then** it shows "Keine Abwesenheit in den nächsten 13 Wochen." [no absence in the next 13 weeks] or "In den nächsten 13 Wochen auf kein Projekt gebucht." [not booked on any project in the next 13 weeks]. (no test)

### Evidence

- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.open_person`, `PortfolioState.selected_person`, `DRAWER_PERSON`
- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `person_details`, `_person_week`, `_absences`, `_work_days`, `_bookings`
- [portfolio_drawer.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_drawer.py): `_title`, `_person_body`, `_person_week`, `_load_bar`, `_absence`, `_booking`
- Tests: [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_role_and_person_drawers`; [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_person_detail_shows_weeks_absences_and_bookings`, `test_person_details_cover_scope_and_named_carriers`
