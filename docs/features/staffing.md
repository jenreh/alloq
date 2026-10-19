---
title: Staff a project
description: How project managers staff a project, either with the wizard "Projekt planen" on the planning page or person by person in the tab "Ressourcen" of the project drawer.
story_ids: [PLAN-19, PLAN-20, PLAN-21, PLAN-22, PROJ-18, PROJ-19]
source_paths:
  - components/alloq-project/src/alloq_project/components/planning_toolbar.py
  - components/alloq-project/src/alloq_project/components/project_plan_modal.py
  - components/alloq-project/src/alloq_project/states/project_plan_state.py
  - components/alloq-project/src/alloq_project/services/plan_distribution.py
  - components/alloq-project/src/alloq_project/services/resource_planning.py
  - components/alloq-project/src/alloq_project/states/project_resource_state.py
  - components/alloq-project/src/alloq_project/components/project_resource_tab.py
  - components/alloq-project/src/alloq_project/components/project_overview.py
  - components/alloq-commons/src/alloq_commons/entities/required_capacity.py
  - components/alloq-commons/src/alloq_commons/repositories/required_capacity_repository.py
  - components/alloq-commons/src/alloq_commons/entities/capacity.py
  - components/alloq-commons/src/alloq_commons/entities/capacity_allocation.py
  - components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py
  - components/alloq-commons/src/alloq_commons/services/utilization.py
  - components/alloq-commons/src/alloq_commons/access.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Staff a project

This page covers how project managers put people on a project. The stories belong to the activity "Plan capacity" on the [story map](./story-map.md).

The page has one user task, **Staff a project**, with these sub-tasks:

- **Plan with the Projekt planen wizard.** Pick a planned project, spread its effort over the weeks, choose people and save the weekly plan.
- **Plan a person in the Ressourcen tab.** Plan one person for a role, a period and a number of days per week, and change or delete planned periods.

Both ways write weekly allocations (`CapacityAllocationEntity`, person-days per project, employee, role and week) and keep one assignment row (`CapacityEntity`) per project, employee and role. Both use `apply_resource_plan`, which replaces the allocations of one person on the project inside the chosen weeks. The required person-days per role of a project are stored in `RequiredCapacityEntity`.

The wizard opens from the planning page. You change single weeks afterwards in the [planning grid](./planning-grid.md). The tab "Ressourcen" [resources] is part of the project drawer on the [project tracking page](./project-tracking.md#proj-09). The distribution formulas and the free capacity per week are in [calculations](../architecture/calculations.md#plan-distribution-in-the-plan-modal).

Admins and users with the role project_manager can plan. Users with the role employee do not see the wizard button or the planning form.

## PLAN-19 Wizard: pick a project {#plan-19}

The wizard "Projekt planen" [plan project] starts by picking a planned project.

As a project manager, I want a guided wizard to staff a new project, so that I can plan a whole project in a few steps.

Project manager · Staff a project / Plan with the Projekt planen wizard · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the button "Projekt planen" in the planning toolbar, **when** an editor clicks it, **then** `open_modal` (`@requires_editor`) opens a dialog with the steps "Projekt", "Planungsdaten" [planning data], "Mitarbeiter" [employees] and "Vorschau" [preview] on the first step and clears the search. The toolbar wraps the button in `editor_only`, so employees do not see it.
2. **Given** the first step with the search field "Projekte suchen..." [search projects], **when** the user types, **then** `visible_projects` lists only projects in the state "Geplant" [planned] whose name or code contains the text, ignoring case. Each card shows the number of team members as "&lt;n&gt; Personen" [n people] and a status badge. (no test)
3. **Given** a project card, **when** the user clicks it, **then** `select_project` takes over the project data and loads the holidays and the person-days of other projects in the project period. When the load works, the wizard moves straight to "Planungsdaten" and the title reads "Projekt planen: &lt;code&gt;".
4. **Given** that load fails, **when** the wizard prepares the next step, **then** the toast "Bestehende Planung konnte nicht geladen werden. Bitte Projekt bzw. Wochenanzahl erneut wählen." [existing planning could not be loaded, pick the project or the number of weeks again] appears and the wizard stays on the first step.
5. **Given** the first step without a picked project, **when** the user clicks "Weiter →" [next], **then** the button is disabled and `next_step` keeps the wizard on the first step. "Zurück" [back] goes one step back and "Abbrechen" [cancel] closes the dialog.

### Evidence

- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar` (`editor_only`, `primary_button("Projekt planen", ...)`)
- [project_plan_state.py](../../components/alloq-project/src/alloq_project/states/project_plan_state.py): `ProjectPlanState.open_modal`, `ProjectPlanState.close_modal`, `ProjectPlanState.set_search`, `ProjectPlanState.visible_projects`, `ProjectPlanState.select_project`, `ProjectPlanState._refresh_prior_allocations`, `ProjectPlanState._load_planned_pt_per_week`, `ProjectPlanState.next_step`, `ProjectPlanState.prev_step`, `ProjectPlanState.title`, `_PRIOR_NOT_LOADED`
- [project_plan_modal.py](../../components/alloq-project/src/alloq_project/components/project_plan_modal.py): `project_plan_modal`, `_step_project_select`, `_project_card`, `_footer`
- Tests: [test_employee_read_only.py](../../components/alloq-project/tests/test_employee_read_only.py) `TestPlanningPage.test_save_and_create_buttons_are_admin_only`; [test_project_plan_state.py](../../components/alloq-project/tests/test_project_plan_state.py) `TestNextStep.test_needs_a_project_to_leave_step_zero`, `TestNextStep.test_failed_project_load_cannot_leave_step_zero`

## PLAN-20 Wizard: spread the effort {#plan-20}

The step "Planungsdaten" spreads the total effort over the weeks with a ramp-up, a ramp-down and a weekly cap.

As a project manager, I want to set the total effort, the number of weeks, the ramps and the team size, so that I see a realistic weekly distribution before I pick people.

Project manager · Staff a project / Plan with the Projekt planen wizard · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** a picked project, **when** the step opens, **then** "PT-Bedarf gesamt" [total required person-days] is the sum of the required person-days of all roles. Without required roles it is the number of team members (at least 1) times the number of weeks (at least 1) times 4. Both ramps start at 0, and the cap "Kapazität / Wo." [capacity per week] starts at `default_gtk`. (no test)
2. **Given** the card "Wochen" [weeks], **when** the user changes the number and leaves the field, **then** `set_num_weeks` moves the end date to the Sunday of the n-th week, counted from the Monday of the start week, with at least 1 week. The ramps keep their values, and the wizard loads holidays and other projects' person-days again for the new period.
3. **Given** that reload fails, **when** the user clicks "Weiter →" or saves, **then** the toast about the existing planning from [PLAN-19](#plan-19) appears and the wizard does not go on.
4. **Given** the sliders "Ramp-up" ("sofort" [at once] to "langsam" [slow]) and "Ramp-down" ("abrupt" to "langsam"), **when** the user moves them, **then** each ramp is a whole number of weeks from 0 to the number of project weeks. The slider "Kapazität / Wo." runs from 0.5 to 30 GTK in steps of 0.5, and `set_gtk_count` rounds to 0.5 with a minimum of 0.5. "PT-Bedarf gesamt" takes whole numbers of 0 or more. (no test)
5. **Given** the chart "Wochenverteilung (PT)" [weekly distribution], **when** it is computed, **then** `distribute` spreads the total over `effective_weeks` with a cap of GTK times 5 PT per week. Each week snaps to 0, 25, 50, 75 or 100 % of the cap, and the total is kept as closely as the shape allows. The formulas are in [calculations](../architecture/calculations.md#plan-distribution-in-the-plan-modal). (no test)
6. **Given** more effort than the ramp shape can hold, **when** the chart renders, **then** it warns "Kapazität zu knapp: nur &lt;x&gt; von &lt;y&gt; PT passen in &lt;n&gt; Wochen (Cap &lt;c&gt; PT/Wo). Projekt verlängern, Ramps verkürzen oder Kapazität erhöhen." [capacity too low, extend the project, shorten the ramps or raise the capacity]. The warning shows when the total is more than 0.5 PT above `shape_capacity`. (no test)

### Evidence

- [project_plan_state.py](../../components/alloq-project/src/alloq_project/states/project_plan_state.py): `ProjectPlanState.select_project`, `ProjectPlanState.set_num_weeks`, `ProjectPlanState.set_total_pt`, `ProjectPlanState.set_ramp_up`, `ProjectPlanState.set_ramp_down`, `ProjectPlanState.set_gtk_count`, `ProjectPlanState.num_weeks`, `ProjectPlanState.effective_weeks`, `ProjectPlanState.distribution`, `ProjectPlanState.shape_capacity`, `ProjectPlanState.shortfall`, `ProjectPlanState.shortfall_msg`, `ProjectPlanState.prior_ready`
- [plan_distribution.py](../../components/alloq-project/src/alloq_project/services/plan_distribution.py): `distribute`, `default_gtk`, `WORKDAYS_PER_WEEK`, `PT_QUANTA_PER_WEEK`
- [project_plan_modal.py](../../components/alloq-project/src/alloq_project/components/project_plan_modal.py): `_step_verteilung`, `_ramp_card`, `_capacity_card`
- [required_capacity.py](../../components/alloq-commons/src/alloq_commons/entities/required_capacity.py): `RequiredCapacityEntity`
- Tests: [test_project_plan_state.py](../../components/alloq-project/tests/test_project_plan_state.py) `TestCapacity.test_set_num_weeks_keeps_ramps`, `TestCapacity.test_failed_window_extension_blocks_next_step_and_save`, `TestCapacity.test_successful_reload_makes_window_ready`, `TestModalRender.test_save_is_gated_and_weeks_commit_on_blur`

### Open questions

- `default_gtk`, `distribute` and the shortfall warning have no direct unit test.
- `set_num_weeks` keeps the ramps when the new number of weeks is smaller than a ramp. `distribute` cuts the ramps to fit, but the sliders then show a value above their maximum. Should `set_num_weeks` cut the ramps too?
- The code and the UI do not explain the unit "GTK". The cap counts one GTK as 5 PT per week.

## PLAN-21 Wizard: choose people {#plan-21}

The step "Mitarbeiter" lists people with their free capacity, and the user sets the person-days for each picked person.

As a project manager, I want to choose people and their effort for the project, so that the plan covers the required roles.

Project manager · Staff a project / Plan with the Projekt planen wizard · priority 3 · core · v0.2.0

### Acceptance criteria

1. **Given** the employee list, **when** it is built, **then** `filtered_employees` shows the people who hold at least one required role of the project. When the project has no required roles, it shows all employees. (no test)
2. **Given** a person in the list, **when** the free capacity is computed, **then** each week of the project window gets the work days left after holidays, absences, part time and internal hours, minus the person-days on other projects, and at least 0. In a partial first or last week only the work days inside the window count. The row shows the sum as "&lt;n&gt; PT" and below it "&lt;workload&gt;% · belegt &lt;other&gt; / &lt;gross&gt; PT" [booked]. The rules are in [calculations](../architecture/calculations.md#capacity-of-one-person-in-one-week).
3. **Given** a person who is picked, **when** the selection changes, **then** `toggle_employee` sets the person's planned effort to their free person-days. Unpicking the person removes the effort. (no test)
4. **Given** person-days or a percent typed for a person, **when** the value is set, **then** the person-days are rounded to 0.1 and limited to 0 up to the free person-days. A percent is limited to 0 to 100 and turned into person-days of the free capacity. (no test)
5. **Given** a person with several roles, **when** the row renders, **then** the select "Rolle" [role] offers the person's roles. Without a choice, the role is the first of the person's roles that the project requires, else the person's first role. (no test)
6. **Given** the summary, **when** it renders, **then** the cards show "Bedarf gesamt" [total demand], "Ausgewählt" [selected] and "Verfügbar im Zeitraum" [available in the period]. "Ausgewählt" turns green when it reaches the demand. Each required role shows required and assigned person-days, and counts as covered when the assigned days reach a requirement above 0. (no test)

### Evidence

- [project_plan_state.py](../../components/alloq-project/src/alloq_project/states/project_plan_state.py): `ProjectPlanState.filtered_employees`, `ProjectPlanState._matches_filter`, `ProjectPlanState._weekly_avail`, `ProjectPlanState._gross_capacity`, `ProjectPlanState._free_pt`, `ProjectPlanState.toggle_employee`, `ProjectPlanState.set_emp_planned_pt`, `ProjectPlanState.set_emp_planned_pct`, `ProjectPlanState.set_emp_role`, `ProjectPlanState._pick_role_for_employee`, `ProjectPlanState._emp_role_id`, `ProjectPlanState.required_pt_total`, `ProjectPlanState.selected_capacity_pt`, `ProjectPlanState.available_capacity_pt`, `ProjectPlanState.required_roles_display`
- [plan_distribution.py](../../components/alloq-project/src/alloq_project/services/plan_distribution.py): `week_free_days`, `weekdays_in`
- [utilization.py](../../components/alloq-commons/src/alloq_commons/services/utilization.py): `UtilizationService.work_days_for_week`, `UtilizationService.absence_days_in_week`, `UtilizationService.cap_internal_days`, `UtilizationService.apply_workload`
- [project_plan_modal.py](../../components/alloq-project/src/alloq_project/components/project_plan_modal.py): `_capacity_summary`, `project_plan_modal`
- Tests: [test_project_plan_state.py](../../components/alloq-project/tests/test_project_plan_state.py) `TestCapacity.test_partial_first_week_only_counts_days_in_window`, `TestCapacity.test_prior_load_queries_from_monday_and_loads_holidays`, `TestCapacity.test_prior_load_error_is_reported_not_treated_as_free`

### Open questions

- `set_employee_role_filter`, `select_all_filtered` and `clear_employee_selection` exist in `ProjectPlanState`, and `select_project` fills `role_options_data` for a role filter, but `project_plan_modal.py` never uses them. Are they still needed?
- `toggle_employee`, `set_emp_planned_pt`, `set_emp_planned_pct` and `required_roles_display` have no direct test.

## PLAN-22 Wizard: preview and save {#plan-22}

The step "Vorschau" shows the weekly plan per person and saves it into the planning.

As a project manager, I want to preview and save the plan, so that the weekly allocations land in the planning grid.

Project manager · Staff a project / Plan with the Projekt planen wizard · priority 4 · core · v0.2.0

### Acceptance criteria

1. **Given** picked people with person-days above 0, **when** the preview is built, **then** `preview_rows` spreads each person's effort with `distribute_with_avail` over all weeks of the project window, not only the weeks of the chart. Early weeks are filled first up to the person's free capacity. A role with the flag "Ramp-Up" or "Ramp-Down" gets no ramp at that end. A week with an absence shows the tooltip "Abwesend" [absent].
2. **Given** the preview, **when** it renders, **then** the header shows "Projekt", "Zeitraum" [period], "Mitarbeiter" with the number of people with person-days, and "Plan gesamt" [plan total]. Without any person with person-days it shows "Keine Allokationen geplant. Schritt zurück und PT setzen." [no allocations planned, go back and set person-days], and "Speichern" [save] is disabled. "Speichern" is also disabled while saving.
3. **Given** a click on "Speichern", **when** `save_plan` (`@requires_editor`) stores the plan, **then** `apply_resource_plan` replaces only the planned people's allocations on this project inside the window, with values rounded to 2 decimals. Other people, people without a role or person-days, and weeks outside the window stay as they are. The dialog closes, the toast "Plan gespeichert (&lt;n&gt; Zuweisungen)." [plan saved, n assignments] appears and the planning grid reloads with `PlanningStore.refresh`.
4. **Given** no person with planned days, **when** the user saves, **then** the toast "Keine Allokationen geplant. Bitte PT für Mitarbeiter setzen." [no allocations planned, set person-days for employees] appears and the database is not touched.
5. **Given** a database error, **when** the save fails, **then** the dialog stays open, the saving flag is reset and the toast "Speichern fehlgeschlagen. Bitte erneut versuchen." [saving failed, try again] appears.
6. **Given** a user without edit rights, **when** `save_plan` is called, **then** the guard stops it and nothing is saved.

### Evidence

- [project_plan_state.py](../../components/alloq-project/src/alloq_project/states/project_plan_state.py): `ProjectPlanState.preview_rows`, `ProjectPlanState._weekly_absent`, `ProjectPlanState._effective_ramps_for`, `ProjectPlanState.preview_emp_count`, `ProjectPlanState.preview_total_pt`, `ProjectPlanState._build_plans`, `ProjectPlanState.save_plan`
- [plan_distribution.py](../../components/alloq-project/src/alloq_project/services/plan_distribution.py): `distribute_with_avail`
- [resource_planning.py](../../components/alloq-project/src/alloq_project/services/resource_planning.py): `apply_resource_plan`, `PlanTarget`
- [project_plan_modal.py](../../components/alloq-project/src/alloq_project/components/project_plan_modal.py): `_step_preview`, `_preview_row`, `_footer`
- Tests: [test_project_plan_state.py](../../components/alloq-project/tests/test_project_plan_state.py) `TestRampDown.test_tail_tapers_without_spike`, `TestRampDown.test_conserves_pt_and_tail_is_non_increasing`, `TestRampDown.test_skips_blocked_weeks`, `TestSavePlan.test_only_selected_employees_in_window_are_replaced`, `TestSavePlan.test_empty_plan_does_not_touch_the_database`, `TestSavePlan.test_db_error_resets_saving_and_keeps_modal_open`, `TestSavePlan.test_non_admin_cannot_save`, `TestModalRender.test_save_is_gated_and_weeks_commit_on_blur`

### Open questions

- "Plan gesamt" shows the person-days the user set, not the sum of the weekly bars. When a person's free weeks cannot hold the effort, the two values differ. Which one should the header show?

## PROJ-18 Plan a person in Ressourcen {#proj-18}

The tab "Ressourcen" suggests people with free capacity for a role and plans them for a period.

As a project manager, I want to plan a person for a role, a period and a number of days per week, so that my project is staffed without overbooking anyone.

Project manager · Staff a project / Plan a person in the Ressourcen tab · priority 1 · core · v0.3.0

### Acceptance criteria

1. **Given** a project in the drawer, **when** the tab "Ressourcen" opens, **then** `load_selected` (`@requires_viewer`) loads employees, roles, holidays and allocations. The form "Ressource planen" [plan resource] starts with the project period, 3 days per week, and the first required role whose planned person-days are below its requirement. When all are covered it takes the first required role, else the first role. A load error shows the toast "Ressourcen konnten nicht geladen werden." [resources could not be loaded].
2. **Given** the form with "Rolle", "Von" [from], "Bis" [to] and "Tage pro Woche" [days per week], **when** a value is missing or wrong, **then** `form_error` shows "Bitte eine Rolle wählen." [choose a role], "Bitte Von und Bis angeben." [enter from and to] or "Von muss vor Bis liegen." [from must be before to], and the plan buttons are disabled. "Von muss vor Bis liegen." shows only when "Bis" is before "Von".
3. **Given** days per week and dates, **when** the user enters them, **then** days per week snap to steps of 0.5 between 0.5 and 5, and invalid input keeps the last value. Dates outside the project period are moved to its first or last day.
4. **Given** a valid form, **when** the list "Verfügbare Personen" [available people] is built, **then** `find_candidates` lists holders of the role whose average free days per week reach the requested days, plus people already planned on the project. Planned people come first with the badge "geplant" [planned], then the most free capacity. Each row shows "Ø &lt;n&gt; T/Wo frei" [average days per week free] and "&lt;n&gt; Wochen knapp" [n weeks tight] for weeks with too little capacity. An empty list shows "Keine verfügbaren Personen für diese Rolle im Zeitraum." [no available people for this role in the period].
5. **Given** a click on "Einplanen" [plan] for a person, **when** `assign` (`@requires_editor`) saves the plan, **then** each week gets the requested days, reduced in partial weeks, capped by the free capacity after holidays, absences, part time, internal hours and other projects, and rounded down to 0.1. `apply_resource_plan` replaces all of the person's allocations on the project in these weeks, in any role, creates or widens the assignment row and removes assignment rows of other roles that have no allocations left. The toast "&lt;name&gt; eingeplant." [name planned] appears, and the drawer and the project list get the new allocations.
6. **Given** no free capacity in the period, **when** the user plans the person, **then** the warning "Keine freie Kapazität im Zeitraum." [no free capacity in the period] appears and nothing is saved.
7. **Given** a database error, **when** the save fails, **then** the toast "Fehler beim Speichern der Planung." [error saving the plan] appears and the saving flag is reset.
8. **Given** a user with the role employee, **when** the tab renders, **then** `editor_only` hides the planning form, and `assign` and `delete_period` refuse the call.

### Evidence

- [project_overview.py](../../components/alloq-project/src/alloq_project/components/project_overview.py): tab `("ressourcen", ressourcen_tab())`
- [project_resource_state.py](../../components/alloq-project/src/alloq_project/states/project_resource_state.py): `ProjectResourceState.load_selected`, `ProjectResourceState._load`, `ProjectResourceState._default_role_id`, `ProjectResourceState.form_error`, `ProjectResourceState.set_start`, `ProjectResourceState.set_end`, `ProjectResourceState._clamp_to_project`, `ProjectResourceState.set_days_per_week`, `ProjectResourceState.sync_days_input`, `ProjectResourceState.candidates`, `ProjectResourceState.assign`, `ProjectResourceState._refresh_after_change`, `MIN_DAYS_PER_WEEK`, `MAX_DAYS_PER_WEEK`, `DEFAULT_DAYS_PER_WEEK`
- [resource_planning.py](../../components/alloq-project/src/alloq_project/services/resource_planning.py): `week_starts`, `weekly_free_days`, `plan_weekly_days`, `find_candidates`, `apply_resource_plan`, `_sync_capacity`, `_prune_capacities`
- [project_resource_tab.py](../../components/alloq-project/src/alloq_project/components/project_resource_tab.py): `ressourcen_tab`, `_plan_fields`, `_plan_section`, `_candidate_row`
- [capacity_allocation_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py): `CapacityAllocationRepository.find_by_project_in_range`, `CapacityAllocationRepository.delete_for_project_employee_in_range`, `CapacityAllocationRepository.batch_upsert`
- [capacity.py](../../components/alloq-commons/src/alloq_commons/entities/capacity.py): `CapacityEntity`; [capacity_allocation.py](../../components/alloq-commons/src/alloq_commons/entities/capacity_allocation.py): `CapacityAllocationEntity`
- Tests: [test_project_resource_state.py](../../components/alloq-project/tests/test_project_resource_state.py) `TestLoad.test_load_splits_allocations_and_sets_defaults`, `TestInputs.test_form_error_messages`, `TestInputs.test_days_per_week_clamped_to_half_steps`, `TestInputs.test_invalid_days_keep_previous_value`, `TestInputs.test_dates_clamped_to_project_range`, `TestInputs.test_candidates_and_periods`, `TestSave.test_assign_applies_plan_and_syncs_project_state`, `TestSave.test_assign_without_capacity_does_not_save`, `TestSave.test_assign_with_form_error_does_not_save`, `TestSave.test_assign_error_toasts_instead_of_raising`, `TestSave.test_non_admin_cannot_assign_or_delete`; [test_resource_planning.py](../../components/alloq-project/tests/test_resource_planning.py) `TestWeeklyFreeDays`, `TestPlanWeeklyDays`, `TestFindCandidates.test_planned_people_always_included_first`, `TestFindCandidates.test_excludes_below_threshold_and_other_roles`, `TestApplyResourcePlan.test_replaces_only_weeks_in_range_for_all_roles`, `TestApplyResourcePlan.test_prunes_capacity_of_role_without_remaining_rows`, `TestApplyResourcePlan.test_widens_existing_capacity`

### Open questions

- The toast "Ressourcen konnten nicht geladen werden." has no test.
- The form does not show why it picked the default role. Should the rule be visible to the user?

## PROJ-19 Change or delete a planned period {#proj-19}

Planned periods in the tab "Ressourcen" can be changed or deleted.

As a project manager, I want to change or delete a planned period, so that the staffing follows changes in the project.

Project manager · Staff a project / Plan a person in the Ressourcen tab · priority 2 · core · v0.3.0

### Acceptance criteria

1. **Given** weekly allocations of one person in one role, **when** the list "Geplante Ressourcen" [planned resources] is built, **then** `group_into_periods` joins consecutive weeks into one period. Each period shows the person, the role, the dates from the first Monday to the last Friday, its most common days per week as "&lt;n&gt; T/Wo" and its total as "&lt;n&gt; PT".
2. **Given** a project without planned periods, **when** the tab renders, **then** it shows "Noch keine Ressourcen geplant." [no resources planned yet]. (no test)
3. **Given** the icon "Zeitraum bearbeiten" [edit period], **when** the user clicks it, **then** `edit_period` fills the form with the period, the form title changes to "Zeitraum bearbeiten", and the buttons read "Übernehmen" [apply]. "Abbrechen" ends the edit.
4. **Given** an edited period, **when** the user clicks "Übernehmen", **then** `assign` deletes the old period first and then plans the new values.
5. **Given** the action "Zeitraum löschen" [delete period], **when** the user confirms it, **then** `delete_period` (`@requires_editor`) removes only that role's allocations in the period. It removes the assignment row when no allocation of that role is left, and the toast "Zeitraum gelöscht." [period deleted] appears. An error shows "Fehler beim Löschen des Zeitraums." [error deleting the period]. (no test for the error toast)

### Evidence

- [project_resource_state.py](../../components/alloq-project/src/alloq_project/states/project_resource_state.py): `ProjectResourceState.periods`, `ProjectResourceState.edit_period`, `ProjectResourceState.cancel_edit`, `ProjectResourceState.is_editing`, `ProjectResourceState.assign`, `ProjectResourceState.delete_period`, `ProjectResourceState._refresh_after_change`
- [resource_planning.py](../../components/alloq-project/src/alloq_project/services/resource_planning.py): `group_into_periods`, `_build_period`, `delete_resource_period`, `_prune_capacities`
- [project_resource_tab.py](../../components/alloq-project/src/alloq_project/components/project_resource_tab.py): `_planned_section`, `_period_row`, `_plan_section`, `ressourcen_tab`
- [capacity_allocation_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py): `CapacityAllocationRepository.delete_for_project_employee_in_range`
- Tests: [test_resource_planning.py](../../components/alloq-project/tests/test_resource_planning.py) `TestGroupIntoPeriods.test_groups_consecutive_weeks_per_role`, `TestDeleteResourcePeriod.test_keeps_capacity_while_rows_remain`, `TestDeleteResourcePeriod.test_removes_capacity_when_no_rows_left`, `TestDeleteInRangeRepository.test_with_and_without_role_filter`; [test_project_resource_state.py](../../components/alloq-project/tests/test_project_resource_state.py) `TestInputs.test_edit_period_fills_form_and_cancel_clears`, `TestSave.test_edit_save_deletes_old_period_first`, `TestSave.test_delete_period`, `TestSave.test_delete_unknown_period_is_noop`, `TestComponent.test_ressourcen_tab_renders`
