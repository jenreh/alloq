---
title: Planning filters and view
description: How project managers choose the planning window, filter the planning by people, projects, roles, availability and scope, open the planning prefiltered from other pages, and adjust how the grid looks, with the settings the browser remembers.
story_ids: [PLAN-07, PLAN-10, PLAN-11, PLAN-12, PLAN-13, PLAN-18, PLAN-14, PLAN-15, PLAN-16, PLAN-17]
source_paths:
  - components/alloq-project/src/alloq_project/pages.py
  - components/alloq-project/src/alloq_project/states/planning_grid_state.py
  - components/alloq-project/src/alloq_project/states/planning_filter_mixin.py
  - components/alloq-project/src/alloq_project/states/planning_display_mixin.py
  - components/alloq-project/src/alloq_project/states/planning_absence_view_mixin.py
  - components/alloq-project/src/alloq_project/states/planning_models.py
  - components/alloq-project/src/alloq_project/services/planning_builders.py
  - components/alloq-project/src/alloq_project/services/planning_view_settings.py
  - components/alloq-project/src/alloq_project/components/planning_filter_row.py
  - components/alloq-project/src/alloq_project/components/planning_toolbar.py
  - components/alloq-project/src/alloq_project/components/planning_grid.py
  - components/alloq-project/src/alloq_project/components/planning_project_view.py
  - components/alloq-project/src/alloq_project/components/planning_shared.py
  - components/alloq-project/src/alloq_project/components/project_inspector.py
  - components/alloq-team/src/alloq_team/components/employee_inspector.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Planning filters and view

This page covers how a project manager shapes the page "Ressourcenplanung" [resource planning] at `/plan`. The stories belong to the activity "Plan capacity" on the [story map](./story-map.md).

The page has one user task, **Shape the planning view**, with these sub-tasks:

- **Choose the planning window.** Show 3, 6 or 12 months of weeks.
- **Filter the planning.** Narrow the rows by employee, project, role, free capacity and internal work. Limit the rows to your own projects or your own team. Open the planning already filtered from another page.
- **Adjust the planning view.** Collapse blocks, switch to compact rows, keep these settings in the browser, and read week headers, holidays and the legend.

The planning page has three views. The user picks one in the switch at the top of the page. The views are:

- **"Team"** (internal value `Grid`). Employees are the blocks and their projects are the rows. Editing cells is on the [planning grid page](./planning-grid.md).
- **"Projekte"** [projects]. Projects are the blocks and their employees are the rows. The project view is also on the [planning grid page](./planning-grid.md#plan-09).
- **"Abwesenheiten"** [absences]. A timeline of absences with its own filter row. It is on the [absences page](./absences.md).

The team view and the project view share one filter row (`planning_filter_row`). The absence view uses `absence_filter_row`, which has only the time range, "Mitarbeiter" [employees], "Rollen" [roles] and its own switch. All filters live in `PlanningFilterMixin`, and the row density lives in `PlanningDisplayState`. Both are mixins of `PlanningStore`.

## PLAN-07 Planning window of 3, 6 or 12 months {#plan-07}

The planning window can be 3, 6 or 12 months, and unsaved edits survive a change of the window.

As a project manager, I want to switch the planning window, so that I can plan further ahead without losing edits.

Project manager · Shape the planning view / Choose the planning window · priority 1 · comfort · v0.2.0

### Acceptance criteria

1. **Given** the time range control with "3 Monate" [3 months] as the default, **when** the user picks "3 Monate", "6 Monate" or "12 Monate", **then** `set_time_range` reloads the grid with 13, 26 or 52 weeks (`TIME_RANGE_WEEKS`). An unknown value falls back to 13 weeks.
2. **Given** unsaved edits in weeks that the new window no longer shows, **when** the window changes, **then** `reload_with_time_range` keeps the edits and shows the toast "&lt;n&gt; ungespeicherte Änderung(en) außerhalb des Zeitraums bleiben erhalten." [n unsaved changes outside the time range are kept]. A later save still writes them.
3. **Given** a page load, **when** the grid opens, **then** it starts without unsaved edits.

### Evidence

- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.set_time_range`, `PlanningStore.reload_with_time_range`, `PlanningStore._range_weeks`, `PlanningStore.load`, `PlanningStore._populate`, `PlanningStore.hidden_edits`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `TIME_RANGE_WEEKS`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `split_edits`
- [planning_filter_row.py](../../components/alloq-project/src/alloq_project/components/planning_filter_row.py): `planning_filter_row`, `absence_filter_row`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestSettersAndLabels.test_set_time_range_triggers_reload`; [test_planning_time_range_edits.py](../../components/alloq-project/tests/test_planning_time_range_edits.py) `TestTimeRangeKeepsEdits.test_save_includes_hidden_edits`, `TestTimeRangeKeepsEdits.test_page_load_still_starts_clean`

## PLAN-10 Filter by employee, project, role {#plan-10}

The planning can be narrowed to chosen employees, projects and roles.

As a project manager, I want to filter the planning by employee, project and role, so that I only see the rows I am planning.

Project manager · Shape the planning view / Filter the planning · priority 1 · comfort · v0.2.0 (approximate)

### Acceptance criteria

1. **Given** the multi-selects "Mitarbeiter", "Projekte" and "Rollen" in the team view, **when** the user picks values, **then** `_filter_employees` keeps only employees that are chosen, that have a chosen project, or that have a chosen role. Each filter with values narrows the result further, so the filters combine.
2. **Given** the same filters in the project view, **when** the user picks a role, **then** `filter_project_blocks` keeps only projects where a listed employee has that role.
3. **Given** a multi-select with chosen values, **when** it is collapsed, **then** it shows a count such as "Projekte (2)", "Rollen (1)" or "MA (3)". With no values it shows nothing extra.

### Evidence

- [planning_filter_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_filter_mixin.py): `PlanningFilterMixin.set_project_filter`, `PlanningFilterMixin.set_role_filter`, `PlanningFilterMixin.set_employee_filter`, `PlanningFilterMixin.project_filter_label`, `PlanningFilterMixin.role_filter_label`, `PlanningFilterMixin.employee_filter_label`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore._filter_employees`, `PlanningStore.filtered_employees`, `PlanningStore.filtered_projects`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `filter_project_blocks`
- [planning_filter_row.py](../../components/alloq-project/src/alloq_project/components/planning_filter_row.py): `planning_filter_row`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestSettersAndLabels.test_filtered_employees_by_filters`, `TestSettersAndLabels.test_empty_filter_labels_and_dimensions`; [test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py) `TestPlanningStoreProjectView.test_filtered_projects_by_role`

## PLAN-11 Only available people {#plan-11}

The switch "Nur verfügbare" [only available] keeps only people who still have more than 3 free person-days.

As a project manager, I want to see only people with free capacity, so that I find someone for new work quickly.

Project manager · Shape the planning view / Filter the planning · priority 2 · comfort · v0.4.3

### Acceptance criteria

1. **Given** the switch "Nur verfügbare", off by default, **when** the user turns it on, **then** only employees whose free days from the current week on are more than 3.0 remain (`MIN_AVAILABLE_PT`). An employee with exactly 3.0 free days is left out.
2. **Given** the switch in the project view, **when** it is on, **then** each project block keeps only available employees and its totals are calculated again. Projects without any available employee disappear.
3. **Given** the view "Abwesenheiten", **when** the switch was turned on before, **then** the absence view ignores it, because it calls `_filter_employees` with `planning_filters=False`.

### Evidence

- [planning_filter_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_filter_mixin.py): `PlanningFilterMixin.set_available_only`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore._filter_employees`, `PlanningStore.filtered_projects`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `MIN_AVAILABLE_PT`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `employee_summary`, `filter_project_blocks`
- [planning_absence_view_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_absence_view_mixin.py): `PlanningAbsenceViewMixin.absence_gantt`
- Tests: [test_planning_availability_filter.py](../../components/alloq-project/tests/test_planning_availability_filter.py) `test_three_person_days_is_a_strict_threshold`, `test_project_view_filters_resources_and_recomputes_totals`, `test_absence_view_ignores_availability_filter`

## PLAN-12 Hide internal and absence rows {#plan-12}

The switch "Interne & Abwesenheit ausblenden" [hide internal and absence] hides internal projects and the absence and internal rows.

As a project manager, I want to hide internal work, so that the grid shows only customer projects.

Project manager · Shape the planning view / Filter the planning · priority 3 · comfort · v2.0.4

### Acceptance criteria

1. **Given** the switch "Interne & Abwesenheit ausblenden", off by default, **when** the user turns it on in the team view, **then** the rows of internal projects and the rows "Interne Projekte" [internal projects] and "Abwesenheit" [absence] are hidden.
2. **Given** hidden internal rows, **when** the totals are shown, **then** the free days and planned days still include the internal work, because `without_internal_projects` only removes rows and keeps the totals.
3. **Given** the project view, **when** the switch is on, **then** the blocks of internal projects are hidden.

### Evidence

- [planning_filter_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_filter_mixin.py): `PlanningFilterMixin.set_hide_internal`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.filtered_employees`, `PlanningStore.filtered_projects`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `without_internal_projects`, `build_project_meta`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_employee_block`
- [project.py](../../components/alloq-commons/src/alloq_commons/entities/project.py): `ProjectEntity.is_internal`
- Tests: [test_planning_hide_internal.py](../../components/alloq-project/tests/test_planning_hide_internal.py) `test_employee_block_hides_internal_and_absence_rows`, `test_hiding_keeps_totals_of_internal_work`, `test_hides_internal_project_blocks_in_project_view`

## PLAN-13 My projects, my team {#plan-13}

Two toolbar buttons limit the planning to the projects the user owns or to the people who report to the user.

As a project manager, I want to see only my projects or my direct reports, so that I focus on the people and projects I am responsible for.

Project manager · Shape the planning view / Filter the planning · priority 4 · comfort · v0.2.0

### Acceptance criteria

1. **Given** the button with the tooltip "Alle Projekte – klicken für eigene" [all projects, click for own], **when** the user turns it on, **then** only projects where the signed-in user is an owner are shown, in the team view and in the project view. The tooltip changes to "Nur eigene Projekte – klicken für alle" [only own projects, click for all].
2. **Given** the button with the tooltip "Alle Mitarbeiter – klicken für eigene" [all employees, click for own], **when** the user turns it on in the team view, **then** only employees whose manager is the signed-in user are shown.
3. **Given** the button for own employees in the project view, **when** it is on, **then** only projects with at least one direct report of the user remain. (no test)
4. **Given** a signed-in user whose email matches no employee, **when** they turn a scope on, **then** the warning "Ihrem Benutzer ist kein Mitarbeiter zugeordnet." [no employee is linked to your user] appears and the scope stays off. An active scope can always be turned off.

### Evidence

- [planning_filter_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_filter_mixin.py): `PlanningFilterMixin.toggle_project_scope`, `PlanningFilterMixin.toggle_employee_scope`, `PlanningFilterMixin._notify_no_employee`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore._resolve_current_employee`, `PlanningStore._filter_employees`, `PlanningStore.filtered_projects`
- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `owned_project_ids`, `managed_employee_ids`, `employee_id_by_email`
- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar`
- Tests: [test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py) `TestPlanningStoreProjectView.test_filtered_projects_by_project_scope`; [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestSettersAndLabels.test_filtered_employees_by_employee_scope`, `TestSettersAndLabels.test_scope_without_current_employee_is_refused`

## PLAN-18 Open the planning prefiltered {#plan-18}

Other pages open the planning already filtered to one project or one employee.

As a project manager, I want to jump from a project or an employee straight into the planning, so that I land on the rows I need.

Project manager · Shape the planning view / Filter the planning · priority 5 · comfort · v2.0.4

### Acceptance criteria

1. **Given** the button "In der Ressourcenplanung öffnen" [open in resource planning] in the project inspector, **when** the user clicks it, **then** `open_project` clears all planning filters, switches to the view "Projekte" with only that project, and redirects to `/plan`.
2. **Given** a link to `/plan?employee=<id>`, e.g. the button "In der Ressourcenplanung öffnen" in the employee inspector of the team page, **when** the page loads, **then** `_focus_employee_from_url` clears the other filters and the team view shows only that employee. The parameter is removed from the address, so a later reload keeps the user's own filters. A value that is not a number is ignored.
3. **Given** filters cleared by such a jump, **when** the stored view settings are applied, **then** the scopes stay off and that state is stored in the browser.

### Evidence

- [planning_filter_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_filter_mixin.py): `PlanningFilterMixin.open_project`, `PlanningFilterMixin._focus_employee_from_url`, `PlanningFilterMixin._clear_filters`, `EMPLOYEE_PARAM`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.load`, `PlanningStore.apply_view_settings`
- [project_inspector.py](../../components/alloq-project/src/alloq_project/components/project_inspector.py): `_actions`
- [employee_inspector.py](../../components/alloq-team/src/alloq_team/components/employee_inspector.py): `rx.redirect("/plan?employee=" ...)`
- Tests: [test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py) `TestPlanningStoreProjectView.test_open_project_shows_only_that_project`, `TestPlanningStoreProjectView.test_employee_param_shows_only_that_employee`; [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestBrowserStoredToolbar.test_apply_after_cleared_filters_stores_scopes_off`

## PLAN-14 Collapse blocks {#plan-14}

Employee and project blocks can be collapsed one by one or all at once.

As a project manager, I want to collapse blocks, so that I can compare many people on one screen.

Project manager · Shape the planning view / Adjust the planning view · priority 1 · comfort · v0.2.0

### Acceptance criteria

1. **Given** an employee or project block, **when** the user clicks its arrow, **then** the block collapses or expands. A collapsed employee header shows the free days per week.
2. **Given** the toolbar button "Alle einklappen" [collapse all], **when** the user clicks it, **then** all blocks collapse and the button turns into "Alle ausklappen" [expand all]. A second click expands everything.
3. **Given** blocks that are partly collapsed, **when** the user clicks "Alle einklappen", **then** all blocks collapse.
4. **Given** the view "Abwesenheiten", **when** the toolbar renders, **then** the collapse button is hidden. It shows only in the views "Team" and "Projekte". (no test)

### Evidence

- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.toggle_employee`, `PlanningStore.toggle_project`, `PlanningStore.toggle_all_sections`, `PlanningStore.all_sections_collapsed`, `PlanningStore._sync_collapse_saved`
- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_employee_header_row`, `_employee_block`
- [planning_project_view.py](../../components/alloq-project/src/alloq_project/components/planning_project_view.py): `planning_project_view`
- Tests: [test_planning_readability.py](../../components/alloq-project/tests/test_planning_readability.py) `test_collapsed_employee_header_shows_gesamt_cells`; [test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py) `TestPlanningStoreProjectView.test_toggle_all_sections_collapses_then_expands_everything`, `TestPlanningStoreProjectView.test_toggle_all_sections_collapses_mixed_state`; [test_planning_toolbar.py](../../components/alloq-project/tests/test_planning_toolbar.py) `test_section_toggle_icon_tracks_collapsed_state`

## PLAN-15 Compact rows {#plan-15}

A toolbar button switches the grid between normal and compact rows.

As a project manager, I want compact rows, so that more weeks and people fit on the screen.

Project manager · Shape the planning view / Adjust the planning view · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** the density button in the views "Team" and "Projekte", **when** the user clicks it, **then** `toggle_grid_density` switches between "normal" and "kompakt" [compact]. The tooltip reads "Normale Zeilen – klicken für kompakte Höhe" [normal rows, click for compact height] or "Kompakte Zeilen – klicken für normale Höhe" [compact rows, click for normal height].
2. **Given** compact density, **when** the columns are laid out, **then** the week columns are 52 px wide instead of 60 px, next to a label column of 300 px.

### Evidence

- [planning_display_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_display_mixin.py): `PlanningDisplayState.toggle_grid_density`, `PlanningDisplayState.week_col_px`, `PlanningDisplayState.table_width`, `PlanningDisplayState.grid_template_columns`, `NORMAL`, `COMPACT`
- [planning_models.py](../../components/alloq-project/src/alloq_project/states/planning_models.py): `COMPACT_WEEK_COL_PX`, `WEEK_COL_PX`, `LABEL_COL_PX`
- [planning_toolbar.py](../../components/alloq-project/src/alloq_project/components/planning_toolbar.py): `planning_toolbar`
- Tests: [test_planning_readability.py](../../components/alloq-project/tests/test_planning_readability.py) `test_density_toggles_between_normal_and_compact`, `test_compact_density_narrows_week_columns`; [test_planning_toolbar.py](../../components/alloq-project/tests/test_planning_toolbar.py) `test_density_toggle_switches_row_height`

## PLAN-16 Remember view settings {#plan-16}

The browser remembers the row density, "collapse all" and the two scope buttons of the planning page.

As a project manager, I want the planning page to open with my last view settings, so that I do not set them again every time.

Project manager · Shape the planning view / Adjust the planning view · priority 3 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a change of the density or a scope, **when** it happens, **then** `_store_view_settings` writes the four flags `compact`, `collapsed`, `project_scope` and `employee_scope` as JSON to the localStorage key "alloq_planning_view". The page writes the key with a script and does not use `rx.LocalStorage`.
2. **Given** a click on a single block arrow or on "Alle einklappen", **when** it changes whether all blocks are collapsed, **then** `_sync_collapse_saved` stores the new `collapsed` flag. A click that does not change this stores nothing.
3. **Given** a page load, **when** `load` finishes, **then** it reads the key with `READ_SCRIPT` and `apply_view_settings` applies the density and, with `collapsed`, collapses all blocks. Missing, unreadable or blocked storage counts as all off.
4. **Given** stored scopes but no employee linked to the user, **when** the settings are applied, **then** the scopes stay off.

### Evidence

- [planning_view_settings.py](../../components/alloq-project/src/alloq_project/services/planning_view_settings.py): `STORAGE_KEY`, `READ_SCRIPT`, `ViewSettings`, `parse_view_settings`, `view_settings_script`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.load`, `PlanningStore.apply_view_settings`, `PlanningStore._store_view_settings`, `PlanningStore._sync_collapse_saved`
- [planning_display_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_display_mixin.py): `PlanningDisplayState.toggle_grid_density`
- Tests: [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py) `TestBrowserStoredToolbar.test_single_sections_store_only_a_changed_collapse`, `TestBrowserStoredToolbar.test_load_reads_the_browser_settings`, `TestBrowserStoredToolbar.test_apply_restores_settings`, `TestBrowserStoredToolbar.test_apply_keeps_scopes_off_without_employee`; [test_planning_view_settings.py](../../components/alloq-project/tests/test_planning_view_settings.py) `test_parse_reads_flags`, `test_parse_treats_unreadable_values_as_off`, `test_script_round_trips_through_json`, `test_read_script_survives_blocked_storage`

## PLAN-17 Readable week headers and holidays {#plan-17}

The grid marks week starts, holidays, repeated values and the usual internal value, so the grid is easy to read.

As a project manager, I want the grid to mark holidays, the current week and changes in the plan, so that I can read it quickly.

Project manager · Shape the planning view / Adjust the planning view · priority 4 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a week column, **when** its header tooltip is built, **then** it reads "KW &lt;n&gt; · ab &lt;weekday&gt; &lt;dd.mm.yyyy&gt;" [calendar week n, from weekday date]. For public holidays in that week it adds " · Feiertag &lt;dd.mm.&gt;" [holiday].
2. **Given** a public holiday from Monday to Friday, **when** the week cell is drawn, **then** one band per holiday day is drawn across the cell. The week has fewer than 5 work days and is marked as short (`is_short`).
3. **Given** a value above zero that equals the value of the week before, **when** the cell is drawn, **then** it is shown in a muted colour, so only changes stand out.
4. **Given** the row "Interne Projekte", **when** a week holds the usual internal value, **then** the value is hidden, so only deviations show.
5. **Given** the footer legend of the team view, **when** it renders, **then** it explains "Aktuelle Woche" [current week], "Feiertag" [holiday], "Wie Vorwoche" [same as previous week], "Ungespeichert" [unsaved], "Überbucht" [overbooked] and "Abwesenheit" [absence], with the hint "Tippen zum Bearbeiten · ⌘S speichert" [type to edit, ⌘S saves]. The project view legend has the same items without "Überbucht" and "Abwesenheit".

### Evidence

- [planning_builders.py](../../components/alloq-project/src/alloq_project/services/planning_builders.py): `week_title`, `build_weeks`, `mark_repeats`, `mark_defaults`
- [planning_display_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_display_mixin.py): `holiday_bands`, `PlanningDisplayState.holiday_backgrounds`, `PlanningDisplayState.month_start_keys`
- [planning_shared.py](../../components/alloq-project/src/alloq_project/components/planning_shared.py): `week_legend_items`, `legend_footer`, `EDIT_HINT`, `editable_value_cell`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_footer`, `_internal_row`, `OVERBOOKED_LABEL`
- Tests: [test_planning_readability.py](../../components/alloq-project/tests/test_planning_readability.py) `test_week_title_names_start_day_and_holidays`, `test_holiday_bands_draw_one_plain_band_per_day`, `test_mark_repeats_flags_values_equal_to_the_previous_week`, `test_internal_row_hides_the_usual_value`; [test_planning_legend.py](../../components/alloq-project/tests/test_planning_legend.py) `test_team_view_legend_explains_cell_styles`, `test_project_view_legend_explains_cell_styles`
