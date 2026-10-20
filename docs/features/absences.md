---
title: Absences and availability
description: How project managers record and delete absences on the team page and on the planning page, and how the absence timeline shows coverage, bottlenecks and upcoming absences.
story_ids: [TEAM-12, TEAM-13, PLAN-23, PLAN-24, PLAN-25, PLAN-26, PLAN-27]
source_paths:
  - components/alloq-team/src/alloq_team/states/team_state.py
  - components/alloq-team/src/alloq_team/states/team_list_state.py
  - components/alloq-team/src/alloq_team/components/employee.py
  - components/alloq-team/src/alloq_team/components/employee_card.py
  - components/alloq-team/src/alloq_team/components/employee_inspector.py
  - components/alloq-commons/src/alloq_commons/entities/absence.py
  - components/alloq-commons/src/alloq_commons/entities/employee.py
  - components/alloq-commons/src/alloq_commons/models/employee.py
  - components/alloq-commons/src/alloq_commons/repositories/absence_repository.py
  - components/alloq-project/src/alloq_project/states/planning_absence_state.py
  - components/alloq-project/src/alloq_project/states/planning_absence_view_mixin.py
  - components/alloq-project/src/alloq_project/states/planning_grid_state.py
  - components/alloq-project/src/alloq_project/states/planning_models.py
  - components/alloq-project/src/alloq_project/services/planning_gantt.py
  - components/alloq-project/src/alloq_project/components/planning_gantt.py
  - components/alloq-project/src/alloq_project/components/absence_lane.jsx
  - components/alloq-project/src/alloq_project/components/planning_filter_row.py
  - components/alloq-project/src/alloq_project/components/planning_toolbar.py
  - components/alloq-project/src/alloq_project/components/planning_grid.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Absences and availability

This page covers how project managers record absences, e.g. vacation, and how they see who is away. The stories belong to the activity "Plan capacity" on the [story map](./story-map.md).

The page has one user task, **Track absences**, with these sub-tasks:

- **Record on the team page.** Add an absence period for an employee and delete it again.
- **Read the absence timeline.** Read the view "Abwesenheiten" [absences] on the planning page, with its coverage row and the list of upcoming absences.
- **Record on the planning page.** Add an absence from the planning page, also by dragging across days on the timeline, and delete it from its bar.

An absence is one row in `AbsenceEntity` with an employee, a first day and a last day. Both days count. Both ways to record an absence use the same dialog and the same handler, `TeamState.create_absence`, so the rules in [TEAM-12](#team-12) apply to both.

Absences and public holidays reduce the capacity of a person. The formulas are in [calculations](../architecture/calculations.md#capacity-of-one-person-in-one-week), so this page does not repeat them. Public holidays are kept on the [master data page](./master-data.md#adm-10). The team page itself is described on the [team page](./team.md), and the filters of the planning page on [planning filters and view](./planning-view.md).

Only admins and project managers can record or delete absences. The team page is open only to them, and every handler on this page has the guard `requires_editor`. On the planning page, users with the role employee can read the absence timeline but do not see the buttons to add or delete.

## TEAM-12 Record an absence {#team-12}

Record a vacation or other absence for an employee as a date range.

As a project manager, I want to record an absence period for an employee, so that the planning counts the person as not available.

Project manager · Track absences / Record on the team page · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the button "Abwesenheit" [absence] in the team inspector, the plus icon next to "Abwesenheiten" on an employee card, or the plus icon in the employee drawer, **when** the user clicks it, **then** the dialog "Abwesenheit hinzufügen" [add absence] opens with an empty range picker "Zeitraum" [period]. The picker does not allow days before today, and the first and last day may be the same day.
2. **Given** a missing, malformed or reversed date range, **when** the user clicks "Speichern" [save], **then** `create_absence` shows the toast "Bitte einen gültigen Zeitraum auswählen." [choose a valid period] and stores nothing.
3. **Given** a first day before today, **when** the user saves, **then** the toast "Abwesenheiten dürfen nicht in der Vergangenheit beginnen." [absences must not start in the past] appears and nothing is stored. The handler compares with the current UTC date. (no test)
4. **Given** a range that shares at least one day with an existing absence of the same employee, **when** the user saves, **then** the toast "Der Zeitraum überschneidet sich mit einer bestehenden Abwesenheit." [the period overlaps an existing absence] appears and nothing is stored. The check is there because overlapping absences would be counted twice in the utilization figures.
5. **Given** a valid range that does not overlap, **when** the user saves, **then** the absence is stored, the absence list of the drawer and the employee list reload, the dialog closes and the toast "Abwesenheit eingetragen." [absence recorded] appears. A one day absence is allowed.
6. **Given** no selected employee, **when** the form is submitted, **then** the toast "Kein Mitarbeiter ausgewählt." [no employee selected] appears. (no test)
7. **Given** a database error, **when** the user saves, **then** the toast "Abwesenheit konnte nicht eingetragen werden." [absence could not be recorded] appears without the error text.
8. **Given** an absence with a last day before its first day, **when** it reaches the write model or the database, **then** `AbsenceCreate` rejects it and the check constraint `ck_absences_date_range` rejects it.

### Evidence

- [team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `_parse_date_range`, `TeamState.current_date`, `TeamState.open_absence_modal`, `TeamState.close_absence_modal`, `TeamState.set_absence_date_range`, `TeamState.select_employee_and_add_absence`, `TeamState.create_absence`
- [employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `absence_modal`, `employee_detail_drawer`
- [employee_card.py](../../components/alloq-team/src/alloq_team/components/employee_card.py): `_absence_list`
- [employee_inspector.py](../../components/alloq-team/src/alloq_team/components/employee_inspector.py): `_actions`
- [absence.py](../../components/alloq-commons/src/alloq_commons/entities/absence.py): `AbsenceEntity` (`ck_absences_date_range`)
- [models/employee.py](../../components/alloq-commons/src/alloq_commons/models/employee.py): `AbsenceCreate.validate_date_range`
- [absence_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/absence_repository.py): `AbsenceRepository.find_by_employee_id`
- Tests: [test_employee.py](../../components/alloq-team/tests/test_employee.py) `test_absence_picker_allows_a_single_day_range`; [test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestCreateAbsence.test_malformed_date_toasts_instead_of_raising`, `TestCreateAbsence.test_reversed_range_is_rejected`, `TestCreateAbsence.test_overlapping_absence_is_rejected`, `TestCreateAbsence.test_creates_non_overlapping_absence`, `TestCreateAbsence.test_creates_one_day_absence`, `TestTeamStateHidesDatabaseErrors.test_toast_does_not_leak_exception_text`; [test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) `TestModelValidation.test_reversed_absence_rejected`

### Open questions

- The overlap check was added in v0.3.0 (13779e0). Absences exist since v0.2.0, so older data may still hold overlapping absences.
- The past check uses the UTC date. Shortly after midnight German time, the UTC date is still the day before, so an absence can start yesterday in local time. The timeline uses the local date for "today".

## TEAM-13 See and delete absences {#team-13}

See the absences of an employee and delete one.

As a project manager, I want to see and remove planned absences, so that the availability stays correct when plans change.

Project manager · Track absences / Record on the team page · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** an employee with absences, **when** an employee card or the team inspector shows them, **then** only absences that end today or later appear, sorted by first day. The card writes "&lt;date&gt; bis &lt;date&gt;" in German date format, and the inspector writes "dd.mm.yyyy – dd.mm.yyyy".
2. **Given** the employee drawer, **when** it opens, **then** it lists all absences of the employee from `find_by_employee_id`, sorted by first day, including absences in the past. (no test)
3. **Given** no absences, **when** a card or the drawer renders, **then** it shows "Keine Abwesenheiten." [no absences]. The inspector shows "Keine geplant." [none planned]. (no test)
4. **Given** an absence row on a card or in the drawer, **when** the user clicks its trash icon and confirms the dialog "Abwesenheit löschen" [delete absence], **then** `delete_absence` removes the absence, reloads the drawer list and the employee list, and shows the toast "Abwesenheit gelöscht." [absence deleted]. (no test for the success path)
5. **Given** a database error, **when** the user deletes an absence, **then** the toast "Abwesenheit konnte nicht gelöscht werden." [absence could not be deleted] appears without the error text.

### Evidence

- [team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState._open_employee_details`, `TeamState.delete_absence`
- [entities/employee.py](../../components/alloq-commons/src/alloq_commons/entities/employee.py): `EmployeeEntity.to_dict` (`absences_since`)
- [team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `_absence_text`
- [employee_card.py](../../components/alloq-team/src/alloq_team/components/employee_card.py): `_absence_list`
- [employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `_absence_row`, `employee_detail_drawer`
- [employee_inspector.py](../../components/alloq-team/src/alloq_team/components/employee_inspector.py): `_absences`
- Tests: [test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) `TestEmployeeAbsencesSince.test_absence_before_since_is_dropped`; [test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestTeamStateHidesDatabaseErrors.test_toast_does_not_leak_exception_text`

### Open questions

- `delete_absence` does not report an absence that does not exist. It shows the success toast whenever no error occurs.
- The drawer shows past absences, but cards and the inspector hide them. It is not clear whether this difference is intended.

## PLAN-23 Absence timeline {#plan-23}

The view "Abwesenheiten" shows every absence as a bar on a timeline with one column per day.

As a project manager, I want to see the team's absences on a timeline, so that I can plan around holidays and leave.

Project manager · Track absences / Read the absence timeline · priority 1 · core · v0.3.0

### Acceptance criteria

1. **Given** the view "Abwesenheiten" on the planning page, **when** it renders, **then** `build_absence_gantt` draws each absence as a bar from its first to its last day, cut to the shown weeks. The planning loads absences from the first shown day on, so absences in past shown weeks appear too.
2. **Given** an absence that starts before the first shown day, **when** its bar renders, **then** the label reads "seit &lt;dd.mm.&gt;" [since]. A bar that is too narrow for its label shows the label beside it as "&lt;label&gt; · &lt;n&gt; AT" [work days].
3. **Given** absences of one person that overlap, **when** the row renders, **then** they use separate lanes. An absence that starts after the previous bar ended uses the same lane again.
4. **Given** an absence that covers public holidays on weekdays, **when** its work days are counted, **then** weekends and holidays do not count, and the bar details note "1 Feiertag nicht gezählt (&lt;dd.mm.&gt;)" or "&lt;n&gt; Feiertage nicht gezählt (&lt;days&gt;)" [holidays not counted]. The details also show "Arbeitstage" [work days] and "Kalendertage" [calendar days].
5. **Given** a row, **when** it renders, **then** the right column shows the number of absent work days in the shown weeks and a label "bis &lt;dd.mm.&gt;" [until] for a running absence or "ab &lt;dd.mm.&gt;" [from] for the next one.
6. **Given** people without absences in the shown weeks, **when** the switch "Ganzes Team zeigen" [show whole team] is off, **then** they are left out. With no rows at all, the view shows "Keine Abwesenheiten für den gewählten Zeitraum und Filter." [no absences for the chosen period and filter] and a button "Ganzes Team zeigen".
7. **Given** the time range, the filters "Mitarbeiter" [employees] and "Rollen" [roles] and the scope buttons for own projects and own employees, **when** they are set, **then** they apply to the absence view. The project filter and "Nur verfügbare" [only available] do not apply, because the view has no control for them.

### Evidence

- [planning_absence_view_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_absence_view_mixin.py): `ABSENCE_VIEW`, `PlanningAbsenceViewMixin.absence_gantt`, `PlanningAbsenceViewMixin.set_absence_show_all`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore._filter_employees` (`planning_filters=False`)
- [planning_gantt.py (service)](../../components/alloq-project/src/alloq_project/services/planning_gantt.py): `build_absence_gantt`, `_Horizon`, `_periods`, `_bar`, `_lanes`, `_row`, `_next_label`, `_holidays_note`
- [planning_gantt.py (component)](../../components/alloq-project/src/alloq_project/components/planning_gantt.py): `planning_gantt`, `_row`, `_bar_details`, `_empty`
- [planning_filter_row.py](../../components/alloq-project/src/alloq_project/components/planning_filter_row.py): `absence_filter_row`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `AbsenceGanttView`, `AbsenceGanttRow`, `AbsenceGanttBar`
- Tests: [test_planning_gantt.py](../../components/alloq-project/tests/test_planning_gantt.py) `test_single_day_and_inclusive_end`, `test_wide_bars_carry_their_label_inside`, `test_clips_to_horizon_and_ignores_invalid_or_outside_periods`, `test_overlapping_periods_use_lanes_but_adjacent_periods_reuse_them`, `test_holidays_are_marked_and_not_counted`, `test_row_totals_next_absence_and_upcoming`, `test_rows_without_absences_only_with_show_all`, `test_state_view_uses_shared_filters_and_reacts_to_changes`, `test_state_view_ignores_project_and_availability_filters`, `test_changing_timeframe_and_show_all`; [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `test_load_entities_keeps_absences_in_displayed_past_weeks`

## PLAN-24 Coverage row {#plan-24}

A coverage row shows how many people are present each week and marks weeks with too few people.

As a project manager, I want to see weeks where too many people are away, so that I can avoid bottlenecks.

Project manager · Track absences / Read the absence timeline · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a shown week, **when** `_coverage` counts it, **then** the cell shows "&lt;present&gt;/&lt;team&gt;". The number present is taken from the work day with the fewest people present, and weekends and holidays are ignored. The team is every person who passes the filters, also people without a row.
2. **Given** the share of people present, **when** the level is chosen, **then** everyone present is ok, half of the team or fewer is critical, and anything between is a warning. The tooltip reads "KW &lt;n&gt;: mindestens &lt;x&gt; von &lt;y&gt; anwesend. Abwesend: &lt;names&gt;" [at least x of y present, absent] or "KW &lt;n&gt;: alle anwesend" [all present].
3. **Given** critical weeks, **when** the filter bar renders, **then** a red badge reads "1 Engpass · KW &lt;n&gt;" or "&lt;n&gt; Engpässe · ab KW &lt;n&gt;" [bottlenecks from week n]. Its tooltip lists the critical weeks with the absent names. (no test for the tooltip)
4. **Given** an absence that shares work days with absences of other people, **when** its bar details render, **then** they note "Überschneidet sich mit &lt;names&gt;." [overlaps with]. When the absence touches a critical week, they add "In KW &lt;n&gt; ist nur &lt;x&gt; von &lt;y&gt; anwesend." [in week n only x of y are present].

### Evidence

- [planning_gantt.py (service)](../../components/alloq-project/src/alloq_project/services/planning_gantt.py): `_coverage`, `_level`, `_bottleneck`, `_overlap_note`
- [planning_filter_row.py](../../components/alloq-project/src/alloq_project/components/planning_filter_row.py): `absence_filter_row`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `CoverageCell`
- Tests: [test_planning_gantt.py](../../components/alloq-project/tests/test_planning_gantt.py) `test_coverage_counts_lowest_presence_per_week`, `test_coverage_ignores_weekends_and_holidays`

## PLAN-25 Upcoming absences {#plan-25}

The list "Nächste Abwesenheiten" shows upcoming absences and whether the booked projects still fit.

As a project manager, I want to see upcoming absences with the projects they affect, so that I can react before a project runs short.

Project manager · Track absences / Read the absence timeline · priority 3 · comfort · v2.0.4

### Acceptance criteria

1. **Given** absences of the filtered people in the shown weeks that end today or later, **when** `_upcoming` builds the list "Nächste Abwesenheiten" [next absences], **then** it shows at most 6, ordered by first day and then by name. Without such absences the section is hidden.
2. **Given** an entry, **when** it renders, **then** it shows the period with its work days, e.g. "Di 06.10. – Do 08.10. · 3 AT", and a label "heute" [today], "morgen" [tomorrow], "in &lt;n&gt; Tagen" [in n days] below 14 days, "in &lt;n&gt; Wochen" [in n weeks] after that, or "läuft bis &lt;dd.mm.&gt;" [runs until] for a running absence.
3. **Given** projects that are not internal and are booked in the weeks of the absence, **when** an entry is built, **then** `_plan_impact` lists them with their person-days and weeks under "Eingeplant in diesen Wochen" [planned in these weeks]. When one week is overbooked, it says "KW &lt;n&gt; überbucht um &lt;x&gt; PT" [overbooked by x person-days]. When several weeks are overbooked, it says "KW &lt;list&gt; überbucht, bis &lt;x&gt; PT zu viel" [overbooked, up to x too many].
4. **Given** booked projects but no overbooked week, **when** the entry is built, **then** it says "Kapazität reicht" [capacity is enough]. Without booked projects it says "Keine Projekte eingeplant" [no projects planned].

### Evidence

- [planning_gantt.py (service)](../../components/alloq-project/src/alloq_project/services/planning_gantt.py): `UPCOMING_LIMIT`, `SOON_DAYS`, `_upcoming`, `_relative`, `_plan_impact`, `_affected_weeks`
- [planning_gantt.py (component)](../../components/alloq-project/src/alloq_project/components/planning_gantt.py): `_upcoming_section`, `_upcoming`, `_affected`, `_status`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `UpcomingAbsence`, `AffectedProject`
- Tests: [test_planning_gantt.py](../../components/alloq-project/tests/test_planning_gantt.py) `test_row_totals_next_absence_and_upcoming`, `test_upcoming_lists_booked_projects_and_overbooking`, `test_upcoming_without_overbooking_says_capacity_fits`

## PLAN-26 Record an absence while planning {#plan-26}

Absences can be entered from the planning page, also by dragging across days on the timeline.

As a project manager, I want to enter an absence while I plan, so that I do not have to switch to the team page.

Project manager · Track absences / Record on the planning page · priority 1 · comfort · v0.3.0

The validation and the messages are the same as in [TEAM-12](#team-12).

### Acceptance criteria

1. **Given** the view "Abwesenheiten", **when** an editor clicks the toolbar button "Abwesenheit eintragen" [enter absence], **then** `open_new_absence` opens the shared absence dialog without a selected employee. The dialog here has a required field "Mitarbeiter" [employee]. In the other views the same place holds the button "Projekt planen".
2. **Given** the open dialog with dates already chosen, **when** the user picks an employee, **then** `pick_employee` keeps the chosen dates.
3. **Given** a drag across days in the lane of an employee, **when** the drag ends, **then** `start_absence` opens the dialog for that employee with the first and last dragged day. The lane does not allow days before today, and it is disabled for users who cannot edit.
4. **Given** a dragged range that starts before today, **when** `start_absence` runs, **then** the toast "Abwesenheiten dürfen nicht in der Vergangenheit beginnen." appears and the dialog stays closed.
5. **Given** the dialog, **when** it is submitted, **then** `PlanningAbsenceState.create_absence` hands it to `TeamState.create_absence` and reloads the planning only when the dialog closed after a successful save. When the dialog is already closed, nothing is submitted.
6. **Given** the calendar icon "Abwesenheit eintragen" in an employee header of the team grid, **when** an editor clicks it, **then** the dialog opens for that employee. (no test)

### Evidence

- [planning_absence_state.py](../../components/alloq-project/src/alloq_project/states/planning_absence_state.py): `PlanningAbsenceState.open_new_absence`, `PlanningAbsenceState.pick_employee`, `PlanningAbsenceState.start_absence`, `PlanningAbsenceState.create_absence`
- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar` (`editor_only`, `primary_button("Abwesenheit eintragen", ...)`)
- [planning_gantt.py (component)](../../components/alloq-project/src/alloq_project/components/planning_gantt.py): `_AbsenceLane`, `_row`, `_employee_field`, `planning_gantt`
- [absence_lane.jsx](../../components/alloq-project/src/alloq_project/components/absence_lane.jsx): `AbsenceLane` (`minDay`, `disabled`)
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_employee_info_cell`
- [team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.select_employee_and_add_absence`, `TeamState.create_absence`
- Tests: [test_planning_absence.py](../../components/alloq-project/tests/test_planning_absence.py) `test_new_absence_starts_without_employee`, `test_picking_an_employee_keeps_the_chosen_dates`, `test_drag_opens_modal_with_employee_and_dates`, `test_drag_into_the_past_is_rejected`, `test_refresh_only_after_saved_absence`, `test_closed_absence_modal_does_not_submit`; [test_employee_read_only.py](../../components/alloq-project/tests/test_employee_read_only.py) `TestPlanningPage.test_absence_lane_has_a_disabled_flag`

## PLAN-27 Delete an absence on the timeline {#plan-27}

An absence can be deleted from its bar on the timeline.

As a project manager, I want to delete a wrong absence from the timeline, so that the free capacity is right again.

Project manager · Track absences / Record on the planning page · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** the details of an absence bar, **when** an editor clicks the trash icon "Abwesenheit löschen" and confirms the dialog, **then** `PlanningAbsenceState.delete_absence` deletes the absence through `TeamState.delete_absence` and reloads the planning. The toasts are the same as in [TEAM-13](#team-13). The planning also reloads when the delete failed.
2. **Given** a user with the role employee, **when** they open the bar details, **then** the trash icon is hidden by `editor_only` and the handler refuses the call with `requires_editor`. (no test for the hidden icon)

### Evidence

- [planning_absence_state.py](../../components/alloq-project/src/alloq_project/states/planning_absence_state.py): `PlanningAbsenceState.delete_absence`
- [planning_gantt.py (component)](../../components/alloq-project/src/alloq_project/components/planning_gantt.py): `_bar_details` (`editor_only`, `delete_dialog`)
- [team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.delete_absence`
- Tests: [test_planning_absence.py](../../components/alloq-project/tests/test_planning_absence.py) `test_delete_absence_refreshes_planning`; [tests/test_handler_authorization.py](../../tests/test_handler_authorization.py) `test_every_handler_is_admin_guarded_or_ui_only`
