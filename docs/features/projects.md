---
title: Find and create projects
description: How people open the project list, filter, sort and inspect projects, and how project managers create a project with the full form or with the quick create.
story_ids: [PROJ-01, PROJ-04, PROJ-20, PROJ-02, PROJ-03, PROJ-05, PROJ-06, PROJ-07, PROJ-08, PROJ-21]
source_paths:
  - components/alloq-project/src/alloq_project/pages.py
  - components/alloq-project/src/alloq_project/states/project_state.py
  - components/alloq-project/src/alloq_project/states/project_list_state.py
  - components/alloq-project/src/alloq_project/states/project_validation_state.py
  - components/alloq-project/src/alloq_project/states/planning_grid_state.py
  - components/alloq-project/src/alloq_project/services/project_sorting.py
  - components/alloq-project/src/alloq_project/components/project_overview.py
  - components/alloq-project/src/alloq_project/components/project_toolbar.py
  - components/alloq-project/src/alloq_project/components/project_table.py
  - components/alloq-project/src/alloq_project/components/project_inspector.py
  - components/alloq-project/src/alloq_project/components/project_card.py
  - components/alloq-project/src/alloq_project/components/project_form.py
  - components/alloq-project/src/alloq_project/components/planning_grid.py
  - components/alloq-team/src/alloq_team/states/team_state.py
  - components/alloq-team/src/alloq_team/components/employee.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-commons/src/alloq_commons/models/project.py
  - components/alloq-commons/src/alloq_commons/models/view_mode.py
  - components/alloq-commons/src/alloq_commons/services/quick_project.py
  - components/alloq-commons/src/alloq_commons/components/forms.py
  - components/alloq-commons/src/alloq_commons/repositories/project_repository.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Find and create projects

This page covers how people find a project in Alloq and how project managers create a new one. The stories belong to the activity "Create and track projects" on the [story map](./story-map.md).

The page has these user tasks and sub-tasks:

- **Find a project.** Open the project overview, view projects read-only, filter and search the list, and inspect a project.
- **Create a project.** Fill in the project form, set the required capacity per role, and create a project quickly while you assign it to an employee.

The page "Projekte" [projects] lives at `/projects`. Changing a project after it exists, recording a status and managing risks are on the [project tracking page](./project-tracking.md). Assigning people to a project is on the [staffing page](./staffing.md). The fields of a project and their columns are in the [data model](../architecture/data-model.md).

Access follows the rules in `alloq_commons.access`. Admins and users with the role project_manager can edit. Users with the role employee can only read.

## PROJ-01 Project list {#proj-01}

The page "Projekte" lists every project with its status and effort.

As a project manager, I want to open one page that lists all projects, so that I can find the project I need to work on.

Project manager · Find a project / Open the project overview · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** a signed-in user with the role admin, project_manager or employee, **when** they open `/projects`, **then** `ProjectState.load_projects` loads all projects in pages of 200 (`_PROJECT_PAGE_SIZE`) until a page comes back short, and sorts them by German name.
2. **Given** a user without any of these roles, **when** they open `/projects`, **then** the guard `@requires_viewer` refuses the handler with the toast "Sie haben keine Berechtigung für diese Aktion." [you are not allowed to do this], and the page shows "Sie haben nicht die notwendigen Berechtigungen, um auf diese Seite zuzugreifen." [you do not have the rights to open this page] instead of the list.
3. **Given** the database holds no projects, **when** the list renders, **then** it shows "Noch keine Projekte vorhanden." [no projects yet] and "Erstellen Sie Ihr erstes Projekt." [create your first project]. (no test)
4. **Given** projects are loaded, **when** the toolbar renders, **then** the subtitle reads "&lt;n&gt; Projekte · &lt;a&gt; aktiv · &lt;r&gt; gefährdet". The active count includes the states "Aktiv" [active] and "Risiko" [at risk]. The at risk count includes only "Risiko".

### Evidence

- [pages.py](../../components/alloq-project/src/alloq_project/pages.py): `create_projects_overview_page`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.load_projects`, `ProjectState._load_projects`, `_PROJECT_PAGE_SIZE`
- [project_list_state.py](../../components/alloq-project/src/alloq_project/states/project_list_state.py): `ProjectListState.subtitle`
- [project_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/project_repository.py): `ProjectRepository.find_all_with_stats`, `ProjectRepository.find_all_paginated`
- [project_overview.py](../../components/alloq-project/src/alloq_project/components/project_overview.py): `project_overview`, `_no_projects_state`
- [project_table.py](../../components/alloq-project/src/alloq_project/components/project_table.py): `project_table`
- [access.py](../../components/alloq-commons/src/alloq_commons/access.py): `viewer_only`, `no_access`, `requires_viewer`
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateHandlers.test_load_projects_pages_past_repository_limit`, `TestProjectStateAuthorization.test_non_admin_cannot_load_projects`; [test_project_list.py](../../components/alloq-project/tests/test_project_list.py) `test_subtitle_counts_active_and_at_risk`

### Open questions

- The page filters the search text in the state (`filtered_projects`). `ProjectRepository.find_all_paginated` also takes a `search` argument, but the page never passes it. Is the argument still needed?

## PROJ-04 Table or cards {#proj-04}

The project page shows projects as a table or as cards, and the browser remembers the choice.

As a project manager, I want to switch between the table and the card view, so that I can read projects in the layout I prefer.

Project manager · Find a project / Open the project overview · priority 2 · comfort · v0.3.0

### Acceptance criteria

1. **Given** the view toggle in the toolbar, **when** the user picks a mode, **then** `ProjectState.set_view_mode` accepts only the modes "grid" and "table" from `VIEW_MODES` and ignores any other value.
2. **Given** a first visit, **when** the page opens, **then** the table view shows. The browser keeps the chosen mode in the local storage key "alloq_projects_view".
3. **Given** the card view, **when** a card shows its team, **then** it shows at most 4 avatars (`MAX_TEAM_AVATARS`) and one more avatar "+N" for the rest.
4. **Given** the card view, **when** it renders, **then** it shows only the groups "Meine Projekte" [my projects] and "Weitere Projekte" [other projects]. The search text applies, but the filter segments of [PROJ-02](#proj-02) and the inspector do not. With a search text and no match, the view shows "Keine Projekte gefunden." [no projects found]. (no test)

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.set_view_mode`, `ProjectState.view_mode`
- [view_mode.py](../../components/alloq-commons/src/alloq_commons/models/view_mode.py): `VIEW_MODES`, `VIEW_MODE_TABLE`
- [project_overview.py](../../components/alloq-project/src/alloq_project/components/project_overview.py): `project_overview`, `project_grid`, `_no_projects_state`
- [project_card.py](../../components/alloq-project/src/alloq_project/components/project_card.py): `project_card`, `team_avatars`, `MAX_TEAM_AVATARS`
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectState.test_set_view_mode_ignores_unknown_mode`, `TestProjectState.test_view_mode_defaults_to_list`; [test_project_components.py](../../components/alloq-project/tests/test_project_components.py) `TestProjectCard.test_card_caps_team_avatars`

### Open questions

- The card view ignores the filter segments "Alle", "Meine", "Aktiv", "Geplant" and "Risiko", although they stay visible in the toolbar. Is that intended?

## PROJ-20 Read projects as an employee {#proj-20}

Employees can open and read projects, but they cannot change them.

As an employee, I want to read the projects and their details, so that I know what I work on without risk of changing anything.

Employee · Find a project / View projects read-only · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** a user with the role employee, **when** they open `/projects`, **then** the list loads, because `load_projects` uses `@requires_viewer`. Handlers that change data, e.g. `create_project` and `delete_project`, use `@requires_editor` and refuse the call.
2. **Given** the project drawer, **when** a user who cannot edit opens it, **then** all tabs sit inside a disabled fieldset (`disabled=~CAN_EDIT`), so every input and button is read-only.
3. **Given** the inspector, **when** a user who cannot edit views it, **then** the buttons "Bearbeiten" [edit] and "Status erfassen" [record status] are replaced by one button "Details". (no test)
4. **Given** the toolbar, **when** a user who cannot edit views it, **then** the button "Projekt anlegen" [create project] is hidden by `editor_only`.

### Evidence

- [pages.py](../../components/alloq-project/src/alloq_project/pages.py): `create_projects_overview_page`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.load_projects`, `ProjectState.create_project`, `ProjectState.delete_project`
- [project_overview.py](../../components/alloq-project/src/alloq_project/components/project_overview.py): `project_detail_drawer`, `READ_ONLY_FIELDSET`
- [project_inspector.py](../../components/alloq-project/src/alloq_project/components/project_inspector.py): `_actions`
- [project_toolbar.py](../../components/alloq-project/src/alloq_project/components/project_toolbar.py): `project_toolbar`
- [access.py](../../components/alloq-commons/src/alloq_commons/access.py): `viewer_only`, `editor_only`, `requires_viewer`, `requires_editor`, `CAN_EDIT`
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateAuthorization.test_employee_can_load_but_not_delete_projects`; [test_employee_read_only.py](../../components/alloq-project/tests/test_employee_read_only.py) `TestProjectsPage.test_drawer_tabs_are_disabled_for_non_admins`, `TestProjectsPage.test_create_button_is_admin_only`; [tests/test_handler_authorization.py](../../tests/test_handler_authorization.py)

## PROJ-02 Group, filter and search projects {#proj-02}

The project table is split into groups, and the user can narrow it with filter segments and a search box.

As a project manager, I want to filter and search the project list, so that I only see the projects that matter to me right now.

Project manager · Find a project / Filter and search the list · priority 1 · comfort · v2.0.0 (approximate)

### Acceptance criteria

1. **Given** the project table, **when** it renders, **then** projects appear in these groups, and a group without rows is left out:
   - "Meine Projekte" [my projects] holds running projects where the current user is an owner.
   - "Weitere Projekte" [other projects] holds the other running projects.
   - "Geplant" [planned] holds projects in the state "Geplant".
   - "Interne Projekte" [internal projects] holds internal projects that are not planned or completed.
   - "Abgeschlossen" [completed] holds projects in the state "Abgeschlossen".
2. **Given** the filter segments "Alle" [all], "Meine" [mine], "Aktiv", "Geplant" and "Risiko", **when** the user picks "Meine", **then** every group shows only projects owned by the current user, and "Weitere Projekte" is empty. A state segment shows only projects in that state. An unknown filter value falls back to "Alle".
3. **Given** the search field "Projekt oder Kunde" [project or customer], **when** the user types, **then** the list keeps only projects whose code, customer or German name contains the text, ignoring case.
4. **Given** a filter that matches no project, **when** the table renders, **then** it shows "Keine Projekte mit diesem Filter." [no projects with this filter].
5. **Given** any filter, **when** the table renders, **then** the footer row "Summe" [total] adds up the required person-days ("PT") of the visible rows only.

### Evidence

- [project_list_state.py](../../components/alloq-project/src/alloq_project/states/project_list_state.py): `FILTERS`, `ProjectListState.set_list_filter`, `_rows_where`, `_is_internal`, `ProjectListState.mine_rows`, `ProjectListState.other_rows`, `ProjectListState.planned_rows`, `ProjectListState.internal_rows`, `ProjectListState.closed_rows`, `ProjectListState.visible_total_pt`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.set_search_filter`, `ProjectState.filtered_projects`, `ProjectState.my_projects`, `ProjectState.other_projects`
- [project_toolbar.py](../../components/alloq-project/src/alloq_project/components/project_toolbar.py): `project_filter`, `project_toolbar`
- [project_table.py](../../components/alloq-project/src/alloq_project/components/project_table.py): `project_list`, `_group`, `_total_row`
- Tests: [test_project_list.py](../../components/alloq-project/tests/test_project_list.py) `TestFilter.test_internal_projects_get_their_own_group_unless_planned`, `TestFilter.test_mine_hides_other_projects`, `TestFilter.test_visible_total_pt_sums_only_visible_projects`; [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectState.test_filtered_projects_by_customer_search`

### Open questions

- `ProjectState.status_filter` is read by `filtered_projects` and by the empty state, but no handler sets it, so it is always "all". Is it left over from an older filter?

## PROJ-03 Sort the project table {#proj-03}

The user clicks a column header to sort the project table by that column.

As a project manager, I want to sort the project table by a column, so that I can compare projects by status, period, effort or risk.

Project manager · Find a project / Filter and search the list · priority 2 · comfort · v0.3.0

### Acceptance criteria

1. **Given** the table headers "Projekt" [project], "Status", "Zeitraum" [period], "Bedarf" [required effort], "Verbraucht" [budget used] and "Risiken" [risks], **when** the user clicks a header, **then** the table sorts by that column in ascending order. A second click on the active column flips the direction. `ProjectState.toggle_sort` ignores a column that is not in `SORT_COLUMNS`.
2. **Given** a sort by status, **when** the projects are sorted, **then** the order follows the life cycle "Geplant", "Aktiv", "Risiko", "Abgeschlossen".
3. **Given** projects without a value for the sort column, e.g. no start date, **when** they are sorted in either direction, **then** they always come last. Projects with the same value keep the ascending name order.
4. **Given** a first visit, **when** the table renders, **then** it is sorted by name (`DEFAULT_SORT_COLUMN`), ignoring case. (no test)

### Evidence

- [project_sorting.py](../../components/alloq-project/src/alloq_project/services/project_sorting.py): `sort_projects`, `_STATE_ORDER`, `SORT_COLUMNS`, `DEFAULT_SORT_COLUMN`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.toggle_sort`, `ProjectState.filtered_projects`
- [project_table.py](../../components/alloq-project/src/alloq_project/components/project_table.py): `COLUMNS`, `project_list`
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectState.test_toggle_sort_same_column_flips_direction`; [test_project_sorting.py](../../components/alloq-project/tests/test_project_sorting.py) `TestSortProjects.test_state_uses_lifecycle_order`, `TestSortProjects.test_missing_start_date_sorts_last_descending`

## PROJ-05 Project inspector {#proj-05}

A side panel next to the project table shows the key facts of the selected project.

As a project manager, I want to see the details of a project next to the list, so that I can check it without opening a dialog.

Project manager · Find a project / Inspect a project · priority 1 · comfort · v2.0.0

### Acceptance criteria

1. **Given** the table view, **when** the user clicks a row, **then** the inspector "Projektdetails" [project details] shows that project. A double click opens the project drawer, which the [project tracking page](./project-tracking.md) describes.
2. **Given** no row is selected, or the selected row is hidden by a filter, **when** the inspector renders, **then** it shows the first visible row. With no visible rows it shows "Kein Projekt ausgewählt." [no project selected].
3. **Given** the inspector button in the toolbar, **when** the user clicks it, **then** the inspector is shown or hidden. The browser keeps the choice in the local storage key "alloq_projects_inspector".
4. **Given** a project with planned team members, **when** the inspector renders the section "Team", **then** it lists up to 6 members (`MAX_TEAM`) with their planned person-days and adds "und N weitere" [and N more]. Without members it shows "Noch keine Mitarbeiter zugewiesen." [no employees assigned yet].
5. **Given** a project with a booking number, **when** the user clicks "Buchungsnummer kopieren" [copy booking number], **then** the number is copied to the clipboard and the toast "Buchungsnummer kopiert" [booking number copied] appears.

### Evidence

- [project_list_state.py](../../components/alloq-project/src/alloq_project/states/project_list_state.py): `ProjectListState.inspect`, `ProjectListState.toggle_inspector`, `ProjectListState.inspected`, `ProjectListState.show_inspector`
- [project_table.py](../../components/alloq-project/src/alloq_project/components/project_table.py): `_row`, `project_table`
- [project_inspector.py](../../components/alloq-project/src/alloq_project/components/project_inspector.py): `project_inspector`, `_details`, `_team`, `MAX_TEAM`, `_booking_number`, `_actions`
- Tests: [test_project_list.py](../../components/alloq-project/tests/test_project_list.py) `TestInspector.test_selection_outside_filter_falls_back`, `TestInspector.test_toggle_inspector`, `test_inspector_shows_team_member_planned_capacity`, `test_inspector_copies_booking_number_to_clipboard`

Changing the status and the period in the inspector is part of [maintaining a project](./project-tracking.md).

## PROJ-06 Create a project {#proj-06}

A project manager creates a project with a form that holds its master data.

As a project manager, I want to create a project with its code, name, period, budget and owners, so that the team can plan capacity on it.

Project manager · Create a project / Fill in the project form · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** a user with the role admin or project_manager, **when** they click "Projekt anlegen" [create project], **then** the dialog "Neues Projekt" [new project] opens. All fields are empty, the status is "Geplant" and the colour is the default "#F7C948". Every role input under "Benötigte Rollen" starts at 0.
2. **Given** a user with the role employee, **when** the toolbar renders, **then** the button "Projekt anlegen" is hidden, and `create_project` refuses the call through `@requires_editor`.
3. **Given** a valid form, **when** the user clicks "Projekt speichern" [save project], **then** the project is stored with its owners, its required capacity rows and a first status entry for today with 0 % progress and 0 % budget used. The dialog closes and the toast "Projekt '&lt;code&gt;' erstellt." [project created] appears.
4. **Given** a code that another project already uses, **when** the user saves, **then** the toast "Projekt-Code bereits vergeben." [project code already taken] appears without database text.
5. **Given** form data that the model `ProjectCreate` rejects, **when** the user saves, **then** the toast "Ungültige Projektdaten." [invalid project data] appears. Other errors show "Fehler beim Erstellen des Projekts." [error while creating the project]. (no test)
6. **Given** a colour value that is not a hex code of the form "#RRGGBB", **when** the form is submitted, **then** the colour falls back to "#F7C948".

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.open_add_modal`, `ProjectState.close_add_modal`, `ProjectState.create_project`, `ProjectState._project_create_from_form`, `_project_error_message`, `_HEX_COLOR`
- [project_validation_state.py](../../components/alloq-project/src/alloq_project/states/project_validation_state.py): `ProjectValidationState.initialize`, `DEFAULT_PROJECT_COLOR`, `PROJECT_COLORS`
- [project_overview.py](../../components/alloq-project/src/alloq_project/components/project_overview.py): `add_project_modal`
- [project_form.py](../../components/alloq-project/src/alloq_project/components/project_form.py): `project_form_fields`, `form_footer`
- [project_toolbar.py](../../components/alloq-project/src/alloq_project/components/project_toolbar.py): `project_toolbar`
- [models/project.py](../../components/alloq-commons/src/alloq_commons/models/project.py): `ProjectCreate`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestProjectValidationInitialize.test_add_mode_resets_fields_and_zeroes_roles`, `TestProjectLifecycle.test_create_project_persists_owners_and_capacities`; [test_employee_read_only.py](../../components/alloq-project/tests/test_employee_read_only.py) `TestProjectsPage.test_create_button_is_admin_only`; [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateHandlers.test_duplicate_code_shows_friendly_error_without_sql`, `TestProjectStateHandlers.test_invalid_form_color_falls_back_to_default`

## PROJ-07 Validate the project form {#proj-07}

The project form checks the required fields and limits while the user fills it in.

As a project manager, I want the form to tell me what is missing or wrong, so that I can only save a complete project.

Project manager · Create a project / Fill in the project form · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** the field "Projekt-Code" [project code] or "Name" is empty, **when** the field loses focus, **then** the form shows "Projekt-Code ist erforderlich." [project code is required] or "Name (DE) ist erforderlich." [name is required].
2. **Given** the date fields "Start" and "Ende" [end], **when** one is missing or the end is before the start, **then** the form shows "Start und Ende sind erforderlich." [start and end are required] or "Ende darf nicht vor Start liegen." [end must not be before start]. The button "Projekt speichern" stays disabled while `is_form_invalid` is true.
3. **Given** a budget typed in German format, e.g. "1.234,56", **when** the field loses focus, **then** the value is read as 1235, rounded half up. A negative budget shows "Budget darf nicht negativ sein." [budget must not be negative].
4. **Given** the text inputs, **when** the user types, **then** the browser stops at 255 characters for "Name" and "Kunde" [customer], 5 for "Projekt-Code" and 50 for "Buchungsnummer" [booking number].

### Evidence

- [project_validation_state.py](../../components/alloq-project/src/alloq_project/states/project_validation_state.py): `ProjectValidationState.set_code`, `ProjectValidationState.set_name_de`, `ProjectValidationState.set_budget`, `ProjectValidationState.validate_code`, `ProjectValidationState.validate_name_de`, `ProjectValidationState.validate_dates`, `ProjectValidationState.validate_budget`, `ProjectValidationState.has_errors`, `ProjectValidationState.is_form_valid`, `ProjectValidationState.is_form_invalid`, `_parse_localized_int`
- [project_form.py](../../components/alloq-project/src/alloq_project/components/project_form.py): `project_form_fields`
- [models/project.py](../../components/alloq-commons/src/alloq_commons/models/project.py): `ProjectCreate`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestProjectValidationSetters.test_required_field_setters_validate`; [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectValidationState.test_invalid_date_range`, `TestParseLocalizedInt.test_decimals_round_half_up`; [test_project_components.py](../../components/alloq-project/tests/test_project_components.py) `TestProjectForm.test_text_inputs_limit_length_in_browser`

### Open questions

- The form limits the code to 5 characters in the browser, but `ProjectCreate.code` and the database column allow 50. Which limit is intended?

## PROJ-08 Required days per role {#proj-08}

The project form asks for the person-days that each role needs.

As a project manager, I want to enter the required person-days per role, so that planning shows how much staffing the project still needs.

Project manager · Create a project / Set required capacity per role · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the section "Benötigte Rollen" [required roles] with one input "Personentage" [person-days] per role, **when** the user enters values, **then** the heading shows the total as "(&lt;n&gt; PT Gesamt)" [n person-days in total].
2. **Given** a role input that is empty, not a number, or 0 or less, **when** the form is saved, **then** no required capacity row is stored for that role.
3. **Given** a stored project, **when** the project is read, **then** its required effort "Bedarf" is the sum of the person-days of all roles (`Project.compute_total_pt`).

### Evidence

- [project_validation_state.py](../../components/alloq-project/src/alloq_project/states/project_validation_state.py): `ProjectValidationState.set_role_capacity`, `ProjectValidationState.total_capacity`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState._required_capacities_from_form`
- [project_form.py](../../components/alloq-project/src/alloq_project/components/project_form.py): `_required_capacity_fields`, `_required_capacity_input`
- [models/project.py](../../components/alloq-commons/src/alloq_commons/models/project.py): `RequiredCapacityCreate`, `Project.compute_total_pt`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestProjectValidationSetters.test_budget_and_capacity_parsing`, `TestProjectLifecycle.test_create_project_persists_owners_and_capacities`; [test_projects.py](../../components/alloq-commons/tests/test_projects.py) `TestProjectModels.test_project_total_pt_sums_required_capacities`

## PROJ-21 Quick-create a project {#proj-21}

A project manager creates a missing project from only a name and a short code while assigning work.

As a project manager, I want to create a project with only a name and a code while I assign it to someone, so that I do not have to leave the planning page or the team page.

Project manager · Create a project / Quick-create while assigning · priority 1 · comfort · v0.3.0

The same quick create runs in two places. Both dialogs are called "Projekt zuweisen" [assign project]. One is in the planning grid (`PlanningStore`), and the other is on the team page (`TeamState`). Both call the shared service `create_quick_project`.

### Acceptance criteria

1. **Given** the select "Projekt" in the dialog "Projekt zuweisen", **when** it opens, **then** its first entry is "+ Neues Projekt anlegen" [create new project]. The projects follow in the groups "Aktiv", "Geplant" and "Abgeschlossen", and empty groups are left out. Projects the employee already has are not offered.
2. **Given** the planning grid, **when** the select is built, **then** it offers no completed projects, so the group "Abgeschlossen" only appears on the team page. (no test)
3. **Given** the user picks "+ Neues Projekt anlegen", **when** the select changes, **then** the inline fields "Projektname" [project name] and "Kürzel" [code] and the button "Anlegen" [create] appear.
4. **Given** an empty name or code, **when** the user clicks "Anlegen", **then** the toast "Bitte einen Projektnamen eingeben." [please enter a project name] or "Bitte ein Projektkürzel eingeben." [please enter a project code] appears, and the input is kept.
5. **Given** a code longer than 5 characters (`MAX_CODE_LENGTH`) or a code in use, **when** the user clicks "Anlegen", **then** the toast "Projektkürzel darf höchstens 5 Zeichen haben." [code may have at most 5 characters] or "Projektkürzel '&lt;code&gt;' ist bereits vergeben." [code already taken] appears.
6. **Given** valid input, **when** the project is created, **then** it starts today, ends 90 days later (`PLACEHOLDER_DURATION_DAYS`), has budget 0 and has no status or capacity rows. The dialog selects it in "Projekt", the inline fields clear and the toast "Projekt '&lt;code&gt;' angelegt." [project created] appears.
7. **Given** a database error, **when** the user clicks "Anlegen", **then** the toast "Projekt konnte nicht angelegt werden." [project could not be created] appears without the error text.
8. **Given** "+ Neues Projekt anlegen" is still selected, **when** the user submits the dialog, **then** the toast "Bitte das neue Projekt zuerst anlegen." [please create the new project first] appears and nothing is assigned.

### Evidence

- [quick_project.py](../../components/alloq-commons/src/alloq_commons/services/quick_project.py): `create_quick_project`, `grouped_project_options`, `QuickProjectError`, `NEW_PROJECT_OPTION`, `NEW_PROJECT_VALUE`, `STATE_GROUPS`, `MAX_CODE_LENGTH`, `PLACEHOLDER_DURATION_DAYS`
- [forms.py](../../components/alloq-commons/src/alloq_commons/components/forms.py): `quick_project_fields`
- [planning_grid_state.py](../../components/alloq-project/src/alloq_project/states/planning_grid_state.py): `PlanningStore.quick_create_project`, `PlanningStore.quick_create_active`, `PlanningStore._rebuild_add_project_options`, `PlanningStore.add_project_to_employee_grid`, `PlanningStore.set_quick_project_name`, `PlanningStore.set_quick_project_code`
- [planning_grid.py](../../components/alloq-project/src/alloq_project/components/planning_grid.py): `_add_project_modal`
- [team_state.py](../../components/alloq-team/src/alloq_team/states/team_state.py): `TeamState.quick_create_project`, `TeamState.quick_create_active`, `TeamState.unassigned_project_options`, `TeamState.assign_project_to_employee`
- [employee.py](../../components/alloq-team/src/alloq_team/components/employee.py): the dialog "Projekt zuweisen"
- Tests: [test_planning_quick_create.py](../../components/alloq-project/tests/test_planning_quick_create.py) `TestGroupedProjectOptions.test_groups_ordered_with_completed_last`, `TestQuickCreateOptions.test_options_lead_with_create_entry`, `TestQuickCreateOptions.test_options_exclude_already_assigned_projects`, `TestQuickCreateOptions.test_quick_create_active_tracks_selection`, `TestQuickCreateProject.test_keeps_input_when_rejected`, `TestQuickCreateProject.test_selects_created_project`, `TestAssignWithPendingQuickCreate.test_rejects_uncreated_project`; [test_quick_project.py](../../components/alloq-commons/tests/test_quick_project.py) `TestCreateQuickProject.test_rejects_blank_name`, `test_rejects_blank_code`, `test_rejects_overlong_code`, `test_rejects_duplicate_code`, `test_creates_no_status_or_capacity_rows`; [test_team_state.py](../../components/alloq-team/tests/test_team_state.py) `TestTeamStateHidesDatabaseErrors.test_toast_does_not_leak_exception_text`

### Open questions

- The planning grid offers only projects that are not completed, but the team page offers completed projects too. Should both dialogs offer the same projects?
