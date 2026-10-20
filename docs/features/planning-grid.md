---
title: Planning grid
description: How project managers plan person-days per week in the planning grid, read the free days of each person, assign projects in the grid, switch to the project view, and how employees read the plan without changing it.
story_ids: [PLAN-01, PLAN-02, PLAN-03, PLAN-08, PLAN-04, DASH-14, PLAN-05, PLAN-06, PLAN-09, PLAN-28]
source_paths:
  - app/app.py
  - components/alloq-project/src/alloq_project/pages.py
  - components/alloq-project/src/alloq_project/states/planning_grid_state.py
  - components/alloq-project/src/alloq_project/states/planning_models.py
  - components/alloq-project/src/alloq_project/services/planning_builders.py
  - components/alloq-project/src/alloq_project/services/resource_planning.py
  - components/alloq-project/src/alloq_project/components/planning_grid.py
  - components/alloq-project/src/alloq_project/components/planning_shared.py
  - components/alloq-project/src/alloq_project/components/planning_toolbar.py
  - components/alloq-project/src/alloq_project/components/planning_project_view.py
  - components/alloq-project/src/alloq_project/components/planning_filter_row.py
  - components/alloq-project/src/alloq_project/components/planning_gantt.py
  - components/alloq-commons/src/alloq_commons/components/excel_grid/excel_grid.py
  - components/alloq-commons/src/alloq_commons/components/excel_grid/excel_grid.jsx
  - components/alloq-commons/src/alloq_commons/components/excel_grid/grid_logic.js
  - components/alloq-commons/src/alloq_commons/services/utilization.py
  - components/alloq-commons/src/alloq_commons/services/quick_project.py
  - components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py
  - components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Planning grid

This page covers the planning grid, where project managers plan how many person-days each employee works on each project per week. The stories belong to the activity "Plan capacity" on the [story map](./story-map.md).

The page has one user task, **Plan week by week**, with these sub-tasks:

- **Plan in the team grid.** Open the grid, type days into week cells, save all changes in one step, and use spreadsheet keys.
- **Read free days per person.** Read the free days row of each employee. One shared service calculates free days and load for every page.
- **Assign a project to an employee.** Add a project row to an employee, or remove it.
- **Plan in the project view.** Turn the grid around so that projects are the blocks.
- **View the planning read-only.** Employees read the plan but cannot change it.

The page "Ressourcenplanung" [resource planning] lives at `/plan` and is also the home page at `/`. The time range, the filters, the density and the absence timeline are on the [planning view page](./planning-view.md). The wizard "Projekt planen" [plan project] is on the [staffing page](./staffing.md). Recording absences is on the [absences page](./absences.md). The formulas are in [calculations](../architecture/calculations.md).

Access follows the rules in `alloq_commons.access`. Admins and users with the role project_manager can edit. Users with the role employee can only read.

## PLAN-01 Team planning grid {#plan-01}

The page "Ressourcenplanung" shows the weekly person-days of every employee on every open project.

As a project manager, I want one page with the weekly plan of the whole team, so that I can see who works on what and when.

Project manager · Plan week by week / Plan in the team grid · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** a signed-in user with the role admin, project_manager or employee, **when** they open `/` or `/plan`, **then** `PlanningStore.load` (`@requires_viewer`) loads projects, employees, roles, public holidays and weekly allocations. Other users see the fallback of `viewer_only` instead of the grid.
2. **Given** the default time range "3 Monate" [3 months], **when** the page loads, **then** the grid shows 13 week columns (`TIME_RANGE_WEEKS`). The first column is the Monday of the previous week (`anchor_date`, `WEEKS_BEFORE_CURRENT` = 1).
3. **Given** projects in the state "Abgeschlossen" [completed], **when** the planning data loads, **then** `_load_entities` leaves them out of the planning rows. (no test)
4. **Given** a database error while loading, **when** the page loads, **then** the toast "Planungsdaten konnten nicht geladen werden." [planning data could not be loaded] appears and the loading flag is reset.
5. **Given** the view "Team", **when** the grid renders, **then** the employees are sorted by last name and then first name, ignoring case. Each block header reads "&lt;last name&gt;, &lt;first name&gt;". The grid header shows "Mitarbeiter" [employees] and "&lt;n&gt; Personen" [n people].

### Evidence

- [app.py](../../app/app.py): `create_planning_page(sidebar(), route="/")`, `create_planning_page(sidebar())`
- [pages.py](../../components/alloq-project/src/alloq_project/pages.py): `create_planning_page`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.load`, `PlanningStore._load_entities`, `PlanningStore._populate`, `PlanningStore._fetch_holidays`, `PlanningStore.employee_blocks`, `PlanningStore.filtered_employees`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `TIME_RANGE_WEEKS`, `WEEKS_BEFORE_CURRENT`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `anchor_date`, `build_weeks`, `build_employee_meta`, `build_project_meta`, `ingest_allocations`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `planning_grid`, `_employee_block`, `_employee_header_row`
- [capacity_allocation_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py): `CapacityAllocationRepository.find_cells_in_range`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestLoading.test_load_and_reload`, `TestSettersAndLabels.test_filtered_employees_are_sorted_by_last_name`; [test_planning_block_summary.py](../../components/alloq-project/tests/test_planning_block_summary.py) `TestCurrentWeekKey.test_is_week_after_anchor`; [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `TestLoadErrors.test_db_error_resets_loading_and_toasts`

## PLAN-02 Type days into week cells {#plan-02}

Project managers type person-days straight into the week cells of the grid.

As a project manager, I want to type person-days into a week cell, so that I can change the plan as fast as in a spreadsheet.

Project manager · Plan week by week / Plan in the team grid · priority 2 · core · v0.3.0 (approximate) · skeleton

### Acceptance criteria

1. **Given** a focused cell, **when** the user types a number, **then** the grid accepts a comma or a dot as the decimal sign and rounds to 2 decimals. An empty cell counts as 0. A negative value or text keeps the editor open with the hint "Ungültige Zahl (≥ 0)" [invalid number]. (no test for the editor hint)
2. **Given** a batch of cell edits, **when** it reaches the server, **then** `parse_cell_changes` accepts only cells of rows shown in the grid and of loaded weeks, with a finite value of 0 or more. It rounds the values to 2 decimals.
3. **Given** rejected cells in a batch, e.g. pasted text, **when** the batch is applied, **then** the warning "&lt;n&gt; ungültige Eingabe(n) ignoriert." [n invalid entries ignored] appears. A count of 0 shows nothing.
4. **Given** an edited cell, **when** its value differs from the last loaded or saved value, **then** the cell shows a small dot. Setting it back to the saved value removes the dot.
5. **Given** unsaved changes, **when** the user moves to another page in the app, **then** the dialog "Ungespeicherte Änderungen" [unsaved changes] offers "Bleiben" [stay], "Verwerfen" [discard] and "Speichern & verlassen" [save and leave]. When the user closes or reloads the tab, the browser asks first. (no test)

### Evidence

- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.apply_cell_changes`, `PlanningStore.notify_rejected`, `PlanningStore._editable_rows`, `PlanningStore.has_dirty`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `parse_cell_changes`, `split_cell_key`, `cell_key`, `dirty_keys_for`
- [planning_shared.py](../../components/alloq-project/src/alloq_project/components/planning_shared.py): `planning_excel_grid`, `editable_value_cell`
- [excel_grid.jsx](../../components/alloq-commons/src/alloq_commons/components/excel_grid/excel_grid.jsx): `ExcelGrid` (`commitEditor`, `useBlocker`, `beforeunload`)
- [grid_logic.js](../../components/alloq-commons/src/alloq_commons/components/excel_grid/grid_logic.js): `parseNumber`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestParseCellChanges.test_rejects_invalid_change`, `TestSettersAndLabels.test_notify_rejected_ignores_zero`, `TestApplyCellChanges.test_reverting_to_saved_value_clears_dirty`; [grid_logic.test.mjs](../../components/alloq-commons/tests/js/grid_logic.test.mjs) `numbers`

## PLAN-03 Save grid changes in one step {#plan-03}

Changes in the grid stay unsaved until the user saves them all at once.

As a project manager, I want to save all my grid changes at once, so that the plan is stored only when I am done.

Project manager · Plan week by week / Plan in the team grid · priority 3 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** no unsaved change, **when** the user saves, **then** the toast "Keine Änderungen." [no changes] appears.
2. **Given** unsaved changes, **when** the user clicks "Änderungen speichern (⌘S)" [save changes] or presses Cmd+S or Ctrl+S in the grid, **then** `save_grid` writes all cells in one batch with `batch_upsert`. Each cell updates the row of the role that the cell shows. The toast "&lt;n&gt; Zellen gespeichert." [n cells saved] appears.
3. **Given** changes that cannot be mapped to an employee, project and role, **when** the user saves, **then** these changes stay unsaved and the warning "&lt;n&gt; Änderung(en) konnten nicht zugeordnet werden." [n changes could not be mapped] appears.
4. **Given** a database error, **when** the save fails, **then** the changes stay marked and the toast "Speichern fehlgeschlagen. Bitte erneut versuchen." [saving failed, please try again] appears.
5. **Given** a user with the role employee, **when** the toolbar renders, **then** the save button is hidden by `editor_only`, and `save_grid` refuses the call with `@requires_editor`.

### Evidence

- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.save_grid`, `PlanningStore._unsaved_edits`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `edits_to_rows`, `cell_role_ids`
- [capacity_allocation_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py): `CapacityAllocationRepository.batch_upsert`
- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestSaveGridPaths.test_no_changes`, `TestSaveGridPaths.test_db_error_keeps_dirty`; [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `TestSaveGridRoles.test_edit_updates_the_row_the_cell_shows`, `TestSaveGridRoles.test_unmappable_edit_stays_pending`, `TestAdminGuard.test_employee_can_load_but_not_save`

## PLAN-08 Spreadsheet keys, paste, fill, undo {#plan-08}

The planning grid supports spreadsheet keys, copy and paste, fill and undo.

As a project manager, I want to move, fill, copy and undo in the grid with the keyboard, so that I can plan many weeks quickly.

Project manager · Plan week by week / Plan in the team grid · priority 4 · comfort · v0.3.0

### Acceptance criteria

1. **Given** a focused grid, **when** the user presses the arrow keys, Tab, Enter, Home, End, Page Up or Page Down, **then** the selection moves. With Shift the selection grows. Ctrl or Cmd with an arrow jumps within the data region.
2. **Given** a selection, **when** the user presses Ctrl+D or Ctrl+R (Cmd on a Mac), **then** the first row is copied down or the first column is copied to the right. Delete or Backspace clears the cells. Dragging the fill handle repeats the values into the dragged cells.
3. **Given** copied cells or a pasted text block, **when** the user pastes, **then** `planPaste` starts at the top left of the selection and clips at the grid edge. A selection that is a multiple of the copied block repeats the block. Invalid values are skipped and reported as rejected (see [PLAN-02](#plan-02)).
4. **Given** earlier edits, **when** the user presses Ctrl+Z, or Ctrl+Y or Ctrl+Shift+Z, **then** the last edit batch is undone or redone. The grid keeps up to 200 batches. (no test)

### Evidence

- [excel_grid.jsx](../../components/alloq-commons/src/alloq_commons/components/excel_grid/excel_grid.jsx): `ExcelGrid` (`onKeyDown`, `onPaste`, `history`, `applyChanges`)
- [grid_logic.js](../../components/alloq-commons/src/alloq_commons/components/excel_grid/grid_logic.js): `move`, `tabMove`, `pageMove`, `planPaste`, `planFill`, `planFillHandle`, `planClear`
- [excel_grid.py](../../components/alloq-commons/src/alloq_commons/components/excel_grid/excel_grid.py): `excel_grid`, `grid_cell_attrs`, `grid_row_attrs`
- [planning_shared.py](../../components/alloq-project/src/alloq_project/components/planning_shared.py): `planning_excel_grid`, `EDIT_HINT`
- Tests: [grid_logic.test.mjs](../../components/alloq-commons/tests/js/grid_logic.test.mjs) `move`, `tabMove / pageMove`, `clipboard`, `fill, clear and undo bookkeeping`, `fill handle`. The CI workflow runs them with `node --test`.

## PLAN-04 Free days row per employee {#plan-04}

Each employee block ends with a row of free days per week, and its header shows the planned and free total.

As a project manager, I want to see how many days each person has left per week, so that I do not overbook anyone.

Project manager · Plan week by week / Read free days per person · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** an employee week, **when** the row "Gesamt (frei)" [total free] is computed, **then** the free days are the work days minus project days, internal days and absence days. The work days are 5 minus public holidays, scaled by the workload percent of the employee. The value can be negative. The formula is in [free days in the planning grid](../architecture/calculations.md#free-days-in-the-planning-grid).
2. **Given** the internal hours of an employee, **when** the row "Interne Projekte" [internal projects] is computed, **then** the internal days are the internal hours divided by 8, capped at the work days left after absences. The row shows a value only where it differs from the usual weekly value.
3. **Given** free days below 0, exactly 0 or above 0, **when** the cell is drawn, **then** it is red on a red background, muted, or green. The footer explains the red background with "Überbucht" [overbooked]. The cell tooltip reads "Arbeitstage … − Projekte … − Intern … − Abwesenheit … = … PT frei" [work days minus projects minus internal minus absence equals free person-days].
4. **Given** the employee header, **when** it renders, **then** it shows "Geplant" [planned] and "Frei" [free] person-days from the current week on. Overbooked weeks count as 0 free days.
5. **Given** overlapping absences in one week, **when** the absence days are counted, **then** each work day counts once.

### Evidence

- [utilization.py](../../components/alloq-commons/src/alloq_commons/services/utilization.py): `UtilizationService.compute_employee_gesamt`, `UtilizationService.work_days_for_week`, `UtilizationService.apply_workload`, `UtilizationService.cap_internal_days`, `UtilizationService.absence_days_in_week`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `compute_gesamt`, `scaled_work_days`, `gesamt_state`, `gesamt_breakdown`, `employee_summary`, `absence_days_for_week`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.employee_blocks`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_gesamt_row`, `_gesamt_value_cell`, `_gesamt_color`, `_employee_info_cell`, `_internal_row`, `_absence_row`, `_footer`, `OVERBOOKED_LABEL`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestApplyCellChanges.test_updates_employee_pivot_and_gesamt`; [test_utilization.py](../../components/alloq-commons/tests/test_utilization.py) `test_heat_from_raw_caps_internal_hours_after_absence`; [test_planning_readability.py](../../components/alloq-project/tests/test_planning_readability.py) `test_gesamt_state_has_three_visual_states`; [test_planning_block_summary.py](../../components/alloq-project/tests/test_planning_block_summary.py) `TestEmployeeSummary.test_available_ignores_overbooked_weeks`; [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `test_absence_days_for_week_counts_overlapping_absences_once`

### Open questions

- `compute_employee_gesamt` also returns a bucket ("absent" or a value from `gesamt_bucket`), and `compute_project_gesamt` returns a bucket from `project_heat_bucket`. No grid component reads these buckets, because the colours come from `gesamt_state`. Are the buckets still needed?

## DASH-14 One calculation of free days and load {#dash-14}

One shared service calculates the available days and the load percent per person and week, so every page shows the same numbers.

As a project manager, I want the load of a person to be calculated the same way everywhere, so that the overview and the planning grid never disagree.

Project manager · Plan week by week / Read free days per person · priority 2 · core · v0.2.0 (approximate) · skeleton

The team, portfolio and sidebar capacity pages link to this story. The full formulas are in [capacity of one person in one week](../architecture/calculations.md#capacity-of-one-person-in-one-week) and [utilization](../architecture/calculations.md#utilization).

### Acceptance criteria

1. **Given** a week with public holidays and a part-time person, **when** the work days are calculated, **then** `work_days_for_week` takes the holidays from Monday to Friday off the 5 work days and scales the rest by the workload percent. The portfolio sets the workload percent to the weekly hours divided by 40 (`employee_to_input`).
2. **Given** overlapping absence periods, **when** the absence days of a week are counted, **then** each day from Monday to Friday that at least one absence covers counts once.
3. **Given** a person with internal hours, **when** the available days are calculated, **then** the internal hours are divided by 8 and capped at the work days left after absences. The available days are the work days minus internal days minus absence days, and never below 0.
4. **Given** booked days and available days of a week, **when** the load percent is calculated, **then** it is booked divided by available days times 100, rounded. A person with 5 or more absence days gets the bucket "absent". With 0 available days and no full absence, the percent is 0.
5. **Given** a load percent, **when** it is put in a bucket, **then** below 70 is "low", below 85 is "mid", up to 100 is "high" and above 100 is "over" (`HEAT_LOW`, `HEAT_MID`, `HEAT_HIGH`). (no test)
6. **Given** several role rows for the same person, project and week, **when** a team series is computed, **then** only one value per person, project and week counts, the same way as in the planning heatmap.
7. **Given** the portfolio capacity and the dashboard load, **when** a week of a person is calculated, **then** `Capacity._fill_employee` and `_employee_available_days` call `compute_heat_from_raw` with the booked days, internal hours, absences, public holidays and workload. `Capacity` counts bookings on all projects that are not completed.

### Evidence

- [utilization.py](../../components/alloq-commons/src/alloq_commons/services/utilization.py): `UtilizationService`, `work_days_for_week`, `holidays_in_week`, `apply_workload`, `absence_days_in_week`, `cap_internal_days`, `compute_employee_heat`, `compute_heat_from_raw`, `heat_bucket`, `compute_heatmap_allocation_cells`, `compute_team_utilization_series`, `HeatResult`
- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `Capacity._fill_employee`
- [aggregation.py](../../components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py): `_employee_available_days`
- [portfolio_inputs.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py): `employee_to_input`
- [resource_planning.py](../../components/alloq-project/src/alloq_project/services/resource_planning.py): `weekly_free_days` (used by [staffing](./staffing.md))
- Tests: [test_utilization.py](../../components/alloq-commons/tests/test_utilization.py) `test_absence_days_in_week_counts_overlapping_absences_once`, `test_heat_from_raw_caps_internal_hours_after_absence`, `test_team_utilization_matches_heatmap_cell_deduplication`; [test_aggregation_utilization.py](../../components/alloq-dashboard/tests/test_aggregation_utilization.py) `test_load_utilization_uses_holidays_and_workload_like_the_grid`, `test_load_utilization_current_week_follows_today`; [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_free_capacity_is_not_clamped_when_overbooked`

### Open questions

- The service is in the project planning area of the inventory, but the team, dashboard and portfolio code use it too. Should it move to its own area?
- Merging overlapping absences came in v0.3.0. The rest of the service exists since v0.2.0, so the release of this story is approximate.

## PLAN-05 Assign a project in the grid {#plan-05}

Project managers add a project to the block of an employee with the dialog "Projekt zuweisen" [assign project].

As a project manager, I want to assign a project and a role to an employee in the grid, so that I get a row where I can plan their days.

Project manager · Plan week by week / Assign a project to an employee · priority 1 · core · v0.2.0 · skeleton

The team page has the same action in [TEAM-14](./team.md#team-14).

### Acceptance criteria

1. **Given** the action "Projekt zuweisen" in an employee header, **when** the user opens it, **then** the list "Projekt" [project] shows the projects that are not completed and that the employee does not have yet. The list "Rolle" [role] shows only the roles of the employee.
2. **Given** the option "+ Neues Projekt anlegen" [create new project] in the project list, **when** the user picks it, **then** fields for a quick project appear. Assigning before the project is created shows the toast "Bitte das neue Projekt zuerst anlegen." [please create the new project first].
3. **Given** no project, or a role that is not a number, **when** the user clicks "Zuweisen" [assign], **then** the toast "Bitte Projekt und Rolle auswählen." [please choose project and role] appears.
4. **Given** a valid project and role, **when** the user assigns, **then** the store saves an assignment over the whole project period with 40 hours per week. It skips this when the employee already has that role on the project. The grid reloads with `refresh` and keeps unsaved edits.
5. **Given** a project without a start or end date, **when** the user assigns it, **then** the toast "Projekt nicht gefunden." [project not found] appears. (no test)

### Evidence

- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.open_add_project_for_employee`, `PlanningStore._rebuild_add_project_options`, `PlanningStore.close_add_project_for_employee`, `PlanningStore.set_add_project_selected`, `PlanningStore.quick_create_project`, `PlanningStore.add_project_to_employee_grid`, `PlanningStore.refresh`
- [quick_project.py](../../components/alloq-commons/src/alloq_commons/services/quick_project.py): `NEW_PROJECT_VALUE`
- [capacity_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py): `CapacityRepository.find_by_project_and_employee`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_add_project_modal`, `_employee_info_cell`
- Tests: [test_planning_quick_create.py](../../components/alloq-project/tests/test_planning_quick_create.py) `TestQuickCreateOptions.test_options_exclude_already_assigned_projects`, `TestAssignWithPendingQuickCreate.test_rejects_uncreated_project`; [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `TestAddProjectGuards.test_non_numeric_role_is_rejected`, `TestAddProjectGuards.test_existing_assignment_is_not_duplicated`

## PLAN-06 Remove a project row {#plan-06}

Project managers remove a project row from the block of an employee after a confirmation.

As a project manager, I want to remove a project from an employee, so that people who left a project no longer show up on it.

Project manager · Plan week by week / Assign a project to an employee · priority 2 · core · v0.2.0

The team page has the same action in [TEAM-16](./team.md#team-16).

### Acceptance criteria

1. **Given** the action "Projekt entfernen" [remove project] on a project row, **when** the user clicks it, **then** the dialog "Projektzuweisung entfernen" [remove project assignment] shows the project code and name and asks for confirmation. (no test)
2. **Given** a confirmed removal, **when** it runs, **then** all assignments and weekly allocations of that employee on that project are deleted. The unsaved edits of that row are dropped, the grid reloads and the toast "Projektzuweisung entfernt." [project assignment removed] appears.
3. **Given** a database error, **when** the removal fails, **then** the toast "Projektzuweisung konnte nicht entfernt werden." [project assignment could not be removed] appears.

### Evidence

- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.remove_project_from_employee_grid`, `PlanningStore._drop_pending_edits`
- [capacity_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py): `CapacityRepository.delete_by_project_and_employee`
- [capacity_allocation_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py): `CapacityAllocationRepository.delete_by_project_and_employee`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_project_label_cell`
- Tests: [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `TestRefreshKeepsEdits.test_remove_drops_only_that_rows_edits`; [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestRemoveProject.test_db_error_is_reported`

## PLAN-09 Project view of the grid {#plan-09}

The view "Projekte" [projects] turns the grid around, so projects are the blocks and employees are the rows.

As a project manager, I want to plan by project, so that I see who works on my project in each week.

Project manager · Plan week by week / Plan in the project view · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the view switch with "Team", "Projekte" and "Abwesenheiten" [absences], **when** the user picks "Projekte", **then** each project is a block with one row per employee, sorted by name. The row "Gesamt (allokiert)" [total allocated] sums the person-days per week.
2. **Given** projects without any planned day in the visible weeks, **when** the project view is built, **then** `without_idle_projects` hides them.
3. **Given** a project block header, **when** it renders, **then** it shows "Geplant" [planned] person-days from the current week on and a total per role abbreviation. Roles without days are left out.
4. **Given** an edit in the project view, **when** it is applied, **then** it changes the same cell as in the team view, because both views read the same `PlanningStore.cells`.

The filters of the project view are on the [planning view page](./planning-view.md).

### Evidence

- [planning_filter_row.py](../../components/alloq-project/src/alloq_project/components/planning_filter_row.py): `planning_view_switch`, `VIEW_MODES`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.set_view_mode`, `PlanningStore.project_blocks`, `PlanningStore.filtered_projects`, `PlanningStore.apply_cell_changes`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `compute_project_gesamt`, `project_summary`, `without_idle_projects`, `filter_project_blocks`
- [utilization.py](../../components/alloq-commons/src/alloq_commons/services/utilization.py): `UtilizationService.compute_project_gesamt`
- [planning_project_view.py](../../components/alloq-project/src/alloq_project/components/planning_project_view.py): `planning_project_view`, `_project_header_row`, `_project_gesamt_row`
- Tests: [test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py) `TestComputeProjectGesamt.test_multiple_employees`, `TestPlanningStoreProjectView.test_apply_cell_changes_updates_project_pivot`; [test_planning_builders_idle.py](../../components/alloq-project/tests/test_planning_builders_idle.py) `test_idle_planned_and_completed_hidden`; [test_planning_block_summary.py](../../components/alloq-project/tests/test_planning_block_summary.py) `TestProjectSummary.test_omits_roles_without_days`

## PLAN-28 Read the planning as an employee {#plan-28}

Employees can read the planning and the absence timeline, but they cannot change them.

As an employee, I want to see the planning of the team, so that I know my own weekly plan without being able to change it.

Employee · Plan week by week / View the planning read-only · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** a user with the role employee, **when** they open `/plan`, **then** the planning loads, because `load` uses `@requires_viewer`. `save_grid` uses `@requires_editor` and refuses the call.
2. **Given** the grid, **when** a user who cannot edit uses it, **then** the grid is read-only (`read_only=~CAN_EDIT`), so typing, pasting and filling do nothing.
3. **Given** the toolbar and the absence timeline, **when** a user who cannot edit views them, **then** the save button, "Projekt planen" and "Abwesenheit eintragen" [record absence] are hidden, and dragging on the timeline is turned off.

### Evidence

- [pages.py](../../components/alloq-project/src/alloq_project/pages.py): `create_planning_page`
- [planning_shared.py](../../components/alloq-project/src/alloq_project/components/planning_shared.py): `planning_excel_grid`
- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar`
- [planning_gantt.py](../../components/alloq-project/src/alloq_project/components/planning_gantt.py): `_AbsenceLane` (`disabled=~CAN_EDIT`)
- [access.py](../../components/alloq-commons/src/alloq_commons/access.py): `viewer_only`, `editor_only`, `requires_viewer`, `requires_editor`, `CAN_EDIT`
- Tests: [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py) `TestAdminGuard.test_employee_can_load_but_not_save`; [test_employee_read_only.py](../../components/alloq-project/tests/test_employee_read_only.py) `TestPlanningPage.test_grid_is_read_only_for_non_admins`, `TestPlanningPage.test_absence_lane_has_a_disabled_flag`; [test_handler_authorization.py](../../tests/test_handler_authorization.py)
