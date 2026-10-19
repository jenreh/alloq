---
title: Team
description: How project managers open the team page, read the load and free days of each person, and add, change, delete and staff employees.
story_ids: [TEAM-01, TEAM-02, TEAM-06, TEAM-03, TEAM-04, TEAM-05, TEAM-07, TEAM-08, TEAM-09, TEAM-11, TEAM-10, TEAM-14, TEAM-16]
source_paths:
  - components/alloq-team/src/alloq_team/pages.py
  - components/alloq-team/src/alloq_team/states/team_state.py
  - components/alloq-team/src/alloq_team/states/team_list_state.py
  - components/alloq-team/src/alloq_team/states/employee_form.py
  - components/alloq-team/src/alloq_team/services/team_overview.py
  - components/alloq-team/src/alloq_team/components/employee.py
  - components/alloq-team/src/alloq_team/components/employee_card.py
  - components/alloq-team/src/alloq_team/components/employee_inspector.py
  - components/alloq-team/src/alloq_team/components/employee_parts.py
  - components/alloq-team/src/alloq_team/components/employee_table.py
  - components/alloq-team/src/alloq_team/components/toolbar.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-commons/src/alloq_commons/role_colors.py
  - components/alloq-commons/src/alloq_commons/models/view_mode.py
  - components/alloq-commons/src/alloq_commons/models/department.py
  - components/alloq-commons/src/alloq_commons/entities/employee.py
  - components/alloq-commons/src/alloq_commons/repositories/employee_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py
  - components/alloq-commons/src/alloq_commons/entities/absence.py
  - components/alloq-commons/src/alloq_commons/entities/capacity.py
  - components/alloq-commons/src/alloq_commons/entities/capacity_allocation.py
  - components/alloq-commons/src/alloq_commons/services/quick_project.py
  - components/alloq-commons/src/alloq_commons/services/utilization.py
  - components/alloq-project/src/alloq_project/states/planning_filter_mixin.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Team

This page covers the team page at `/team`. A project manager opens the page to see who is on the team, how busy each person is over the next eight weeks, and who has free days. The project manager also adds and changes employees there and assigns projects to them. The stories belong to the activity "Set up the team" on the [story map](./story-map.md).

The activity has these user tasks and sub-tasks on this page:

- **Get to know the team.** View the team, and find a person.
- **Maintain employees.** Add an employee, and change an employee.
- **Staff an employee on projects.** Assign a project to an employee and remove it again.

Absences are also recorded on the team page. Their stories are on the [absences page](./absences.md). The load and free days use the same calculation as the planning grid. The formulas are in [calculations](../architecture/calculations.md#team-series), so this page does not repeat them.

Only admins and project managers can open the team page. Every handler of `TeamState` that reads or writes data has the guard `requires_editor`.

## TEAM-01 Open the team page {#team-01}

A project manager opens the team page and sees every employee with the team figures in the toolbar.

As a project manager, I want to open the team page and see all employees, so that I know who I can plan with.

Project manager · Get to know the team / View the team · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** a signed-in admin or project manager, **when** they open `/team`, **then** the page shows the team overview. Any other signed-in user sees "Sie haben nicht die notwendigen Berechtigungen, um auf diese Seite zuzugreifen." [you do not have the rights to open this page]. (no test)
2. **Given** a signed-in user without edit rights, **when** `TeamState.load_employees` or another guarded team handler runs, **then** the handler stops with the toast "Sie haben keine Berechtigung für diese Aktion." [you have no permission for this action] and no repository is called.
3. **Given** employees in the database, **when** the page loads, **then** up to 1000 employees (`LIST_LIMIT`) are loaded, sorted by last name and first name. All roles and departments are loaded for the form fields.
4. **Given** the team is loaded, **when** the toolbar renders, **then** the subtitle reads "&lt;n&gt; Mitarbeiter · &lt;x&gt; überlastet · &lt;y&gt; mit freier Kapazität" [employees, overloaded, with free capacity].
5. **Given** the list view and no employees loaded yet, **when** loading is still running, **then** a small loader replaces the list. The card view shows "Lade Team..." [loading team] instead. (no test)

### Evidence

- [components/alloq-team/src/alloq_team/pages.py](../../components/alloq-team/src/alloq_team/pages.py): `create_team_overview_page`
- [components/alloq-commons/src/alloq_commons/access.py](../../components/alloq-commons/src/alloq_commons/access.py): `editor_only`, `no_access`, `NO_ACCESS_MSG`, `requires_editor`, `_NOT_AUTHORIZED_MSG`
- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `LIST_LIMIT`, `TeamState.load_employees`, `TeamState._load_employees`, `TeamState._load_available_roles`
- [components/alloq-commons/src/alloq_commons/repositories/employee_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/employee_repository.py): `EmployeeRepository.find_all_paginated`
- [components/alloq-team/src/alloq_team/states/team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `TeamListState.subtitle`
- [components/alloq-team/src/alloq_team/components/employee_table.py](../../components/alloq-team/src/alloq_team/components/employee_table.py): `employee_table`; [employee_card.py](../../components/alloq-team/src/alloq_team/components/employee_card.py): `employee_grid`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestTeamStateAuthorization.test_non_admin_is_rejected`, `TestCreateEmployee.test_loads_employees_with_explicit_limit`; [components/alloq-team/tests/test_team_list.py](../../components/alloq-team/tests/test_team_list.py) `TestTeamListState.test_subtitle`

### Open questions

- Project managers can open `/team` since v2.0.4 (commit 62ed8ab). Before that the page was for admins only. The map shows v0.2.0 for the page itself.

## TEAM-02 Load and free days for eight weeks {#team-02}

A project manager sees the planned load and the free days of each person for the next eight weeks.

As a project manager, I want to see the planned load and free days of each person for the next eight weeks, so that I can spot who is overloaded and who has room.

Project manager · Get to know the team / View the team · priority 2 · core · v2.0.0

### Acceptance criteria

1. **Given** any day of a week, **when** the team figures are computed, **then** the horizon is 8 weeks (`WEEKS`) and starts with the Monday of the current week.
2. **Given** weekly allocations of an employee, **when** the load is computed, **then** a fully booked week is 100 percent. The load in the list is the rounded average of the 8 weekly percents.
3. **Given** allocations on a project in the state completed, **when** the figures are computed, **then** these allocations do not count. The project days of each open project are summed, and the projects are sorted by days, largest first.
4. **Given** an average load above 100 percent (`OVERLOADED_PERCENT`), **when** the overview is built, **then** the person counts as overloaded. One overbooked week alone does not make the person overloaded.
5. **Given** more than 2.0 free person days over the horizon (`FREE_DAYS_MIN`), **when** the overview is built, **then** the person counts as free. Free days are the free hours of the 8 weeks divided by the hours of one work day, rounded to one decimal.
6. **Given** a load figure, **when** the row is colored, **then** a person absent in the current week is neutral, an overloaded person is negative, 85 percent or more is a warning, and everything else is positive. An absent person shows "abwesend" [absent] instead of a percent.
7. **Given** public holidays inside the horizon, **when** the inputs are loaded, **then** the holidays from the first Monday to the Friday of the last week go into the capacity calculation.
8. **Given** loading the inputs fails, **when** the team list refreshes, **then** the last figures stay on screen and the error is logged.

### Evidence

- [components/alloq-team/src/alloq_team/services/team_overview.py](../../components/alloq-team/src/alloq_team/services/team_overview.py): `WEEKS`, `OVERLOADED_PERCENT`, `FREE_DAYS_MIN`, `week_starts`, `build_overview`, `_to_overview`, `_assignments`, `_open_projects`, `load_inputs`, `TeamOverview`
- [components/alloq-team/src/alloq_team/states/team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `load_tone`, `to_detail`, `TeamListState._refresh_overview`
- [components/alloq-team/src/alloq_team/components/employee_parts.py](../../components/alloq-team/src/alloq_team/components/employee_parts.py): `load_label`
- [components/alloq-commons/src/alloq_commons/services/utilization.py](../../components/alloq-commons/src/alloq_commons/services/utilization.py): `UtilizationService.compute_team_utilization_series`, `UtilizationService.compute_team_average`
- Tests: [components/alloq-team/tests/test_team_list.py](../../components/alloq-team/tests/test_team_list.py) `TestBuildOverview.test_week_starts_begin_on_monday`, `test_load_percent_is_the_average_over_all_weeks`, `test_assignments_sum_days_per_project`, `test_overload_in_one_week_only_is_not_overloaded`, `test_full_week_is_100_percent`; `TestDetail.test_load_tone`; `TestLoadInputs.test_maps_rows`; `TestRefreshOverview.test_error_keeps_the_last_figures`

### Open questions

- `_to_overview` reads `EmployeeUtilizationSeries.free_hours_next_4w`, but `build_overview` passes `free_capacity_weeks=8`. The value covers 8 weeks, which matches the column "Frei 8 W.". The field name suggests 4 weeks.

## TEAM-06 List or cards {#team-06}

A project manager switches the team page between a list and cards, and expands the cards to see roles and absences.

As a project manager, I want to switch between a list and a card view, so that I can choose a compact or a visual view of the team.

Project manager · Get to know the team / View the team · priority 3 · comfort · v0.2.0

### Acceptance criteria

1. **Given** the view switch in the toolbar, **when** the user picks a mode, **then** only "grid" and "table" are accepted. The default is "table", and the browser keeps the choice under the key `alloq_team_view`.
2. **Given** the card view, **when** the user clicks the chevron on a card, **then** all cards of that section ("Meine Mitarbeiter" or "Weitere Mitarbeiter") expand or collapse together. Expanded cards show "Rollen" [roles] and "Abwesenheiten" [absences]. (no test)
3. **Given** the card view without matching employees, **when** a search text is set, **then** it shows "Keine Mitarbeiter gefunden." [no employees found]. Without search text it shows "Noch keine Mitarbeiter vorhanden." and "Fügen Sie Ihren ersten Mitarbeiter hinzu." [no employees yet, add your first one]. (no test)
4. **Given** a role name, **when** a role badge renders, **then** the badge gets a pastel color from the role name, ignoring case. **Given** an employee, **when** the avatar renders, **then** its color follows the id of the employee's key role.

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.view_mode`, `TeamState.set_view_mode`, `TeamState.toggle_section_expanded`
- [components/alloq-commons/src/alloq_commons/models/view_mode.py](../../components/alloq-commons/src/alloq_commons/models/view_mode.py): `VIEW_MODES`
- [components/alloq-team/src/alloq_team/components/employee_card.py](../../components/alloq-team/src/alloq_team/components/employee_card.py): `employee_grid`, `employee_card`, `_card_header`, `_role_tags`, `_no_employees_state`
- [components/alloq-team/src/alloq_team/components/employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `team_overview`
- [components/alloq-commons/src/alloq_commons/role_colors.py](../../components/alloq-commons/src/alloq_commons/role_colors.py): `role_color`, `role_color_var`, `role_avatar_color`
- Tests: [components/alloq-commons/tests/test_employees.py](../../components/alloq-commons/tests/test_employees.py) `TestTeamState.test_set_view_mode_switches_and_ignores_unknown`; [components/alloq-commons/tests/test_role_colors.py](../../components/alloq-commons/tests/test_role_colors.py) `test_employee_avatar_color_follows_key_role`

### Open questions

- The card view uses `my_employees` and `other_employees`, so the filter segments "Überlastet", "Frei" and "Meine" do not apply to cards. Only the search applies. Is this intended?
- The color helpers in `role_colors.py` came in v2.0.4 (commit ce34dd2). The cards exist since v0.2.0.

## TEAM-03 Direct reports, filter and search {#team-03}

The list shows the direct reports of the signed-in person first, and the project manager can filter or search it.

As a project manager, I want to see my direct reports first and filter the list by load, so that I find the right person quickly.

Project manager · Get to know the team / Find a person · priority 1 · comfort · v2.0.0

### Acceptance criteria

1. **Given** the email of the signed-in user matches an employee, **when** the list renders, **then** employees whose manager is that employee appear under "Meine Mitarbeiter" [my employees]. All others appear under "Weitere Mitarbeiter" [other employees]. Without a matching employee, everyone is under "Weitere Mitarbeiter".
2. **Given** the filter segments "Alle", "Meine", "Überlastet" and "Frei" [all, mine, overloaded, free], **when** the user picks one, **then** "Überlastet" keeps overloaded people, "Frei" keeps people with free capacity, and "Meine" hides the second group. An unknown value falls back to "Alle".
3. **Given** text in the search field "Name oder Rolle" [name or role], **when** the list or the cards render, **then** only employees whose first name, last name or one of their role names contains the text, ignoring case, are shown. (no test)
4. **Given** no row matches the filter, **when** the list renders, **then** it shows "Keine Mitarbeiter mit diesem Filter." [no employees with this filter]. (no test)

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.load_employees`, `TeamState.filtered_employees`, `TeamState.my_employees`, `TeamState.other_employees`, `TeamState.set_search_filter`
- [components/alloq-team/src/alloq_team/states/team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `FILTERS`, `_matches`, `TeamListState.set_list_filter`, `TeamListState.mine_rows`, `TeamListState.other_rows`
- [components/alloq-team/src/alloq_team/components/toolbar.py](../../components/alloq-team/src/alloq_team/components/toolbar.py): `team_filter`, `team_toolbar`
- [components/alloq-team/src/alloq_team/components/employee_table.py](../../components/alloq-team/src/alloq_team/components/employee_table.py): `employee_list`, `_group`
- Tests: [components/alloq-team/tests/test_team_list.py](../../components/alloq-team/tests/test_team_list.py) `TestTeamListState.test_groups`, `test_filters`

### Open questions

- The two groups exist since v0.2.0 (`my_employees`). The filter segments came with v2.0.0. Should this be one story or two?

## TEAM-04 Sort the team list {#team-04}

A project manager sorts the team list by a column and reads the total of free days.

As a project manager, I want to sort the team list and see the sum of free days, so that I can compare people and judge the free capacity of the visible team.

Project manager · Get to know the team / Find a person · priority 2 · comfort · v2.0.0

### Acceptance criteria

1. **Given** the columns "Name", "Rolle", "h/W", "Auslastung 8 W.", "Frei 8 W." and "Projekte" [name, role, hours per week, load over 8 weeks, free days over 8 weeks, projects], **when** the user clicks a column header, **then** the list sorts by that column in ascending order. A second click on the same column sorts in descending order. An unknown column is ignored.
2. **Given** rows with the same sort value, **when** the list sorts, **then** these rows stay in name order. The sort applies inside each group.
3. **Given** the page opens, **when** the list renders, **then** it is sorted by name in ascending order.
4. **Given** a filter is active, **when** the footer row "Summe" [total] renders, **then** it shows the sum of free person days of the visible rows only, with one decimal and the suffix " PT" [person days].

### Evidence

- [components/alloq-team/src/alloq_team/states/team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `DEFAULT_SORT_COLUMN`, `SORT_COLUMNS`, `sort_team_rows`, `TeamListState.toggle_sort`, `TeamListState.visible_total_free_days`
- [components/alloq-team/src/alloq_team/components/employee_table.py](../../components/alloq-team/src/alloq_team/components/employee_table.py): `COLUMNS`, `_total_row`, `employee_list`
- Tests: [components/alloq-team/tests/test_team_list.py](../../components/alloq-team/tests/test_team_list.py) `TestTeamListState.test_sort_defaults_and_toggles`, `test_sorting_is_applied_within_each_group`, `test_visible_total_free_days_sums_visible_rows`; [components/alloq-team/tests/test_team_sorting.py](../../components/alloq-team/tests/test_team_sorting.py) `test_sort_contract`

## TEAM-05 Team inspector {#team-05}

A project manager selects a person in the list and reads the details in the inspector on the right.

As a project manager, I want to read the details of one person next to the list, so that I can check load, projects and absences without leaving the page.

Project manager · Get to know the team / Find a person · priority 3 · comfort · v2.0.0

### Acceptance criteria

1. **Given** the list has rows, **when** nobody was clicked yet, **then** the inspector shows the first visible row. A click on a row shows that row instead.
2. **Given** the toolbar button "Inspektor ein- oder ausblenden" [show or hide inspector], **when** the user clicks it, **then** the inspector hides or shows. The browser keeps the choice under the key `alloq_team_inspector`.
3. **Given** a selected person, **when** the inspector renders, **then** it shows the sections "Stammdaten" [master data], "Auslastung · nächste 8 Wochen" [load over the next 8 weeks] as bars, "Zuweisungen · 8 Wochen" [assignments over 8 weeks] and "Abwesenheiten" [absences]. Empty sections show "Keine Zuweisungen." [no assignments] and "Keine geplant." [none planned]. (no test)
4. **Given** the list is empty, **when** the inspector renders, **then** it shows "Niemand ausgewählt." [nobody selected]. (no test)
5. **Given** the inspector button "In der Ressourcenplanung öffnen" [open in resource planning], **when** the user clicks it, **then** the app opens `/plan?employee=<id>`. The planning grid clears its other filters, shows only that employee and removes the parameter from the address. The grid is described on the [planning grid page](./planning-grid.md).

### Evidence

- [components/alloq-team/src/alloq_team/states/team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `TeamDetail`, `TeamListState.inspect`, `TeamListState.inspected`, `TeamListState.toggle_inspector`, `TeamListState.show_inspector`
- [components/alloq-team/src/alloq_team/components/employee_inspector.py](../../components/alloq-team/src/alloq_team/components/employee_inspector.py): `employee_inspector`, `_details`, `_weeks`, `_assignments`, `_absences`, `_actions`
- [components/alloq-team/src/alloq_team/components/toolbar.py](../../components/alloq-team/src/alloq_team/components/toolbar.py): `team_toolbar`
- [components/alloq-project/src/alloq_project/states/planning_filter_mixin.py](../../components/alloq-project/src/alloq_project/states/planning_filter_mixin.py): `EMPLOYEE_PARAM`, `PlanningFilterMixin._focus_employee_from_url`
- Tests: [components/alloq-team/tests/test_team_list.py](../../components/alloq-team/tests/test_team_list.py) `TestTeamListState.test_inspector_selection`; [components/alloq-project/tests/test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py) `TestPlanningStoreProjectView.test_employee_param_shows_only_that_employee`

### Open questions

- The jump to `/plan?employee=` came in v2.0.4 (commit 02021a3), later than the inspector itself.

## TEAM-07 Add an employee {#team-07}

A project manager adds a new employee with a name, a key role, weekly hours and optional details.

As a project manager, I want to add an employee with a key role and weekly hours, so that I can plan the person on projects.

Project manager · Maintain employees / Add an employee · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** the toolbar button "Mitarbeiter anlegen" [add employee], **when** the user clicks it, **then** the dialog "Mitarbeiter hinzufügen" opens with an empty form. The form starts with the seniority "Advanced", 40.0 hours per week and 4 internal hours, and an earlier selected employee is cleared.
2. **Given** a form with a key role "Schlüsselrolle" and further roles "Weitere Rollen", **when** the form is saved, **then** the key role is always stored as one of the roles and comes first in the role list of the employee.
3. **Given** the field "Interne Projekte (h/Woche)" [internal projects, hours per week] is empty, **when** the form is saved, **then** the internal hours are stored as 0.
4. **Given** a valid form, **when** the user clicks "Mitarbeiter speichern" [save employee], **then** the employee is created, the list reloads, the dialog closes and the toast "Mitarbeiter '&lt;first name&gt; &lt;last name&gt;' erstellt." [created] appears.
5. **Given** the database rejects the insert, **when** the form is saved, **then** the toast "Mitarbeiter konnte nicht erstellt werden." [could not create the employee] appears without the text of the database error.

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.open_add_modal`, `TeamState.close_add_modal`, `TeamState.create_employee`, `_employee_columns`, `EmployeeValidationState.initialize`
- [components/alloq-team/src/alloq_team/states/employee_form.py](../../components/alloq-team/src/alloq_team/states/employee_form.py): `employee_from_form`
- [components/alloq-team/src/alloq_team/components/employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `add_employee_modal`, `employee_form_fields`
- [components/alloq-commons/src/alloq_commons/repositories/employee_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/employee_repository.py): `EmployeeRepository.set_roles`
- [components/alloq-commons/src/alloq_commons/entities/employee.py](../../components/alloq-commons/src/alloq_commons/entities/employee.py): `EmployeeEntity.to_dict`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestEmployeeSelectOptions.test_open_add_modal_clears_stale_selection`, `TestCreateEmployee.test_empty_internal_hours_does_not_crash`, `TestCreateEmployee.test_stores_selected_department`, `TestTeamStateHidesDatabaseErrors.test_toast_does_not_leak_exception_text`; [components/alloq-commons/tests/test_employees.py](../../components/alloq-commons/tests/test_employees.py) `TestEmployeeEntity.test_to_dict_lists_key_role_first`

### Open questions

- The key role is required since v2.0.4 (commit ce34dd2). Employees exist since v0.2.0. Roles must exist first, see [master data](./master-data.md).

## TEAM-08 Validate the employee form {#team-08}

The employee form shows clear messages while the user fills it in, and it saves only a valid form.

As a project manager, I want the employee form to check my input while I type, so that I do not save wrong or duplicate data.

Project manager · Maintain employees / Add an employee · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** an empty "Vorname" or "Nachname" [first name, last name], **when** the field loses focus, **then** it shows "Vorname darf nicht leer sein." or "Nachname darf nicht leer sein." [must not be empty]. (no test)
2. **Given** the key role is cleared, **when** the field "Schlüsselrolle" changes, **then** it shows "Schlüsselrolle ist erforderlich." [key role is required]. The new key role is removed from "Weitere Rollen". (no test)
3. **Given** a value in "Arbeitszeit (h/Woche)" [working hours per week], **when** the value changes, **then** an empty value shows "Geben Sie die Arbeitszeit an." [enter the working hours], a value below 0 or above 80 shows "Muss zwischen 0 und 80 liegen." and text shows "Muss eine gültige Zahl sein." [must be a valid number]. (no test)
4. **Given** a value in "Interne Projekte (h/Woche)", **when** the value changes, **then** a negative value shows "Muss >= 0 sein." and a fraction or text shows "Muss eine ganze Zahl sein." [must be a whole number]. An empty value is allowed. (no test)
5. **Given** a value in "E-Mail", **when** the value changes, **then** an address without "@" shows "Bitte eine gültige E-Mail-Adresse eingeben." [enter a valid email address]. (no test)
6. **Given** an address that another employee uses, **when** the field loses focus, **then** it shows "Diese E-Mail ist bereits vergeben." [this email is already taken]. The employee being edited is not counted. (no test)
7. **Given** a user without edit rights, **when** the uniqueness check runs, **then** the repository is not called and no error is shown.
8. **Given** any error, a missing first name, last name or key role, or hours outside 0 to 80, **when** the form renders, **then** the save button stays disabled. (no test)
9. **Given** the five text fields of the form, **when** the user types, **then** the browser stops at 255 characters.

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `EmployeeValidationState.set_first_name`, `validate_first_name`, `validate_last_name`, `set_key_role_id`, `validate_key_role_id`, `validate_hours_per_week`, `validate_internal_hours`, `validate_email`, `validate_email_unique`, `has_errors`, `is_form_valid`, `is_form_invalid`, `_EMAIL_FORMAT_ERROR`
- [components/alloq-team/src/alloq_team/components/employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `employee_form_fields`, `add_employee_modal`
- [components/alloq-commons/src/alloq_commons/repositories/employee_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/employee_repository.py): `EmployeeRepository.find_by_email`
- [components/alloq-commons/src/alloq_commons/entities/employee.py](../../components/alloq-commons/src/alloq_commons/entities/employee.py): `EmployeeEntity.email`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestTeamStateAuthorization.test_email_uniqueness_check_requires_admin`; [components/alloq-team/tests/test_employee.py](../../components/alloq-team/tests/test_employee.py) `test_employee_text_inputs_limit_length_in_browser`

### Open questions

- The live validation handlers of `EmployeeValidationState` have no direct unit tests.
- The column `email` is unique in the database. A duplicate that gets past the check on blur ends in the general error toast of the save.

## TEAM-09 Edit an employee {#team-09}

A project manager opens an employee in the side drawer and changes the details.

As a project manager, I want to edit an employee's details, so that the planning uses current hours, roles and reporting lines.

Project manager · Maintain employees / Change an employee · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** a row in the list, a card, or the inspector button "Bearbeiten" [edit], **when** the user double-clicks the row, clicks the card or clicks the button, **then** the drawer opens with the employee's name as title. The form holds the stored values, including the department, and the drawer lists the absences and projects of the employee.
2. **Given** the employee was deleted in the meantime or loading fails, **when** the drawer should open, **then** the toast "Mitarbeiter nicht gefunden." [employee not found] or "Fehler beim Laden des Mitarbeiters." [error loading the employee] appears and the global loading bar stops.
3. **Given** the field "Vorgesetzter" [manager], **when** it shows its options, **then** the employee being edited is not offered. Saving the employee as their own manager is refused with "Ein Mitarbeiter kann nicht sein eigener Vorgesetzter sein." [an employee cannot be their own manager].
4. **Given** a changed form, **when** the user clicks "Mitarbeiter aktualisieren" [update employee], **then** the employee is saved and the list stays sorted by last name and first name. The figures refresh, the drawer closes and the toast "Mitarbeiter '&lt;name&gt;' aktualisiert." [updated] appears.
5. **Given** no employee is selected, **when** the update runs, **then** the toast "Kein Mitarbeiter ausgewählt." [no employee selected] appears. (no test)

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.select_employee`, `TeamState._open_employee_details`, `TeamState.employee_select_options`, `TeamState.update_employee`, `TeamState._upsert_employee`, `TeamState.close_detail_drawer`
- [components/alloq-team/src/alloq_team/components/employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `employee_detail_drawer`
- [components/alloq-team/src/alloq_team/components/employee_table.py](../../components/alloq-team/src/alloq_team/components/employee_table.py): `_row`; [employee_card.py](../../components/alloq-team/src/alloq_team/components/employee_card.py): `employee_card`; [employee_inspector.py](../../components/alloq-team/src/alloq_team/components/employee_inspector.py): `_actions`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestEmployeeFormDepartment.test_edit_prefills_department`, `TestSelectEmployee.test_missing_employee_resets_loading_and_toasts`, `TestUpdateEmployee.test_rejects_self_as_manager`; [components/alloq-commons/tests/test_employees.py](../../components/alloq-commons/tests/test_employees.py) `TestTeamState.test_upsert_employee_replaces_and_sorts`

## TEAM-11 Delete an employee {#team-11}

A project manager deletes an employee from the card view after a confirmation.

As a project manager, I want to delete an employee who left, so that the person no longer appears in planning.

Project manager · Maintain employees / Change an employee · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** the card view, **when** the user clicks the trash icon on a card and confirms the dialog "Mitarbeiter löschen" [delete employee], **then** the employee is deleted, the list reloads, the drawer closes and the toast "Mitarbeiter gelöscht." [employee deleted] appears.
2. **Given** the employee no longer exists, **when** the delete runs, **then** the toast "Mitarbeiter nicht gefunden." appears. (no test)
3. **Given** an employee with absences, capacity rows and weekly allocations, **when** the employee is deleted, **then** the database deletes these rows too. Employees who reported to the person no longer have a manager. (no test)

### Evidence

- [components/alloq-team/src/alloq_team/components/employee_card.py](../../components/alloq-team/src/alloq_team/components/employee_card.py): `_card_header`
- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.delete_employee`
- [components/alloq-commons/src/alloq_commons/entities/employee.py](../../components/alloq-commons/src/alloq_commons/entities/employee.py): `EmployeeEntity.manager_id` (`ondelete="SET NULL"`); [absence.py](../../components/alloq-commons/src/alloq_commons/entities/absence.py), [capacity.py](../../components/alloq-commons/src/alloq_commons/entities/capacity.py), [capacity_allocation.py](../../components/alloq-commons/src/alloq_commons/entities/capacity_allocation.py): `employee_id` (`ondelete="CASCADE"`)
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestTeamStateAuthorization.test_admin_can_delete_employee`

### Open questions

- Only the card view offers delete. The list, the inspector and the drawer have no delete button. Is this intended?

## TEAM-10 Put an employee into a department {#team-10}

A project manager puts an employee into a department.

As a project manager, I want to put each employee into a department, so that I can see which unit a person belongs to.

Project manager · Maintain employees / Change an employee · priority 3 · comfort · v2.0.4

### Acceptance criteria

1. **Given** departments exist, **when** the field "Abteilung" [department] shows its options, **then** each option reads "&lt;name&gt; (&lt;abbreviation&gt;)". Departments are kept on the [master data page](./master-data.md).
2. **Given** exactly one department exists, **when** the add dialog opens, **then** that department is preselected. With no department or several departments the field stays empty.
3. **Given** an employee with a department, **when** the user clears the field and saves, **then** the employee has no department any more.
4. **Given** a selected employee, **when** the inspector shows "Stammdaten", **then** the row "Abteilung" shows the department label, or a single dash when there is none.

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.department_select_options`, `TeamState.open_add_modal`, `EmployeeValidationState.set_department_id`
- [components/alloq-team/src/alloq_team/states/employee_form.py](../../components/alloq-team/src/alloq_team/states/employee_form.py): `default_department_id`, `employee_from_form`
- [components/alloq-commons/src/alloq_commons/models/department.py](../../components/alloq-commons/src/alloq_commons/models/department.py): `Department.label`
- [components/alloq-team/src/alloq_team/states/team_list_state.py](../../components/alloq-team/src/alloq_team/states/team_list_state.py): `to_detail`; [employee_inspector.py](../../components/alloq-team/src/alloq_team/components/employee_inspector.py): `_details`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestEmployeeFormDepartment.test_select_options_show_name_and_abbreviation`, `TestEmployeeFormDepartment.test_no_default_unless_exactly_one`, `TestUpdateEmployee.test_clearing_department_removes_it`; [components/alloq-team/tests/test_team_list.py](../../components/alloq-team/tests/test_team_list.py) `TestDetail.test_to_detail`

## TEAM-14 Assign a project from the team page {#team-14}

A project manager assigns a project to an employee in one of the employee's roles, from the employee drawer.

As a project manager, I want to assign a project to an employee with one of the employee's roles, so that the person shows up as staffed on that project.

Project manager · Staff an employee on projects / Staff an employee on projects · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the plus icon next to "Projekte" [projects] in the drawer, **when** the user clicks it, **then** the dialog "Projekt zuweisen" [assign project] opens and loads the projects only then. The list leaves out projects already assigned to the employee. It starts with the entry "+ Neues Projekt anlegen" [create a new project] and groups the projects as "Aktiv", "Geplant" and "Abgeschlossen" [active, planned, completed]. The new project entry is described in [PROJ-21](./projects.md#proj-21).
2. **Given** the field "Rolle" [role], **when** it shows its options, **then** only roles the employee holds are offered. (no test)
3. **Given** no project, no role, or the new project entry still selected, **when** the user clicks "Zuweisen" [assign], **then** the toast "Bitte ein Projekt auswählen.", "Bitte eine Rolle auswählen." or "Bitte das neue Projekt zuerst anlegen." [select a project, select a role, create the new project first] appears. A project without a start or end date gives "Projekt nicht gefunden." [project not found]. (no test)
4. **Given** a project and a role, **when** the user assigns, **then** a capacity row is created from the start to the end date of the project with the weekly hours of the employee. The project list in the drawer reloads, the dialog closes and the toast "Projekt zugewiesen." [project assigned] appears.
5. **Given** the employee already has this project in the same role, **when** the user assigns again, **then** no row is added and the toast "Projekt ist mit dieser Rolle bereits zugewiesen." [already assigned in this role] appears.

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.open_add_project_modal`, `TeamState.close_add_project_modal`, `TeamState.set_add_project_selected`, `TeamState.unassigned_project_options`, `TeamState.employee_role_select_options`, `TeamState.assign_project_to_employee`, `TeamState._load_employee_capacities`
- [components/alloq-team/src/alloq_team/components/employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `add_project_modal`, `employee_detail_drawer`
- [components/alloq-commons/src/alloq_commons/services/quick_project.py](../../components/alloq-commons/src/alloq_commons/services/quick_project.py): `NEW_PROJECT_OPTION`, `STATE_GROUPS`, `grouped_project_options`
- [components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py): `CapacityRepository.find_by_project_and_employee`, `CapacityRepository.find_by_employee_id`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestOpenAddProjectModal.test_loads_projects_lazily`, `TestAssignProjectToEmployee.test_other_role_is_inserted`, `TestAssignProjectToEmployee.test_same_role_twice_does_not_insert_duplicate`

### Open questions

- The assignment creates a capacity row but no weekly allocations, so the load in [TEAM-02](#team-02) does not change. The drawer shows "Keine Projekte zugewiesen." [no projects assigned] when there are no capacity rows. How capacity rows and weekly allocations relate is described on the [staffing page](./staffing.md).

## TEAM-16 Remove a project from an employee {#team-16}

A project manager removes a project from an employee, including the planned weekly days.

As a project manager, I want to remove a project assignment from an employee, so that the person no longer counts as planned on it.

Project manager · Staff an employee on projects / Staff an employee on projects · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** a project row in the drawer, **when** the user clicks its trash icon and confirms "Projektzuweisung entfernen" [remove project assignment], **then** all capacity rows and all weekly allocations of that project for the employee are deleted in the same transaction.
2. **Given** weekly allocations without a capacity row, **when** the user removes the project, **then** the allocations are removed anyway.
3. **Given** nothing was deleted, **when** the removal ends, **then** the toast "Zuweisung nicht gefunden." [assignment not found] appears. Otherwise the project list and the figures refresh and the toast "Projektzuweisung entfernt." [project assignment removed] appears. (no test)

### Evidence

- [components/alloq-team/src/alloq_team/states/team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.remove_project_from_employee`
- [components/alloq-team/src/alloq_team/components/employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): `_project_row`
- [components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_repository.py): `CapacityRepository.delete_by_project_and_employee`
- [components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/capacity_allocation_repository.py): `CapacityAllocationRepository.delete_by_project_and_employee`
- Tests: [components/alloq-team/tests/test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestRemoveProjectFromEmployee.test_also_deletes_weekly_allocations`, `TestRemoveProjectFromEmployee.test_orphaned_allocations_are_removed_without_capacity_row`
