---
title: Roles, rates, departments and holidays
description: How an administrator keeps the roles, departments, public holidays and daily rates that the planning and the prices use.
story_ids: [ADM-03, ADM-04, ADM-08, ADM-09, ADM-10, ADM-11, ADM-12, ADM-05, ADM-07, ADM-06]
source_paths:
  - app/pages/roles.py
  - app/pages/departments.py
  - app/pages/holidays.py
  - app/pages/daily_rates.py
  - components/alloq-commons/src/alloq_commons/state/role_states.py
  - components/alloq-commons/src/alloq_commons/state/department_states.py
  - components/alloq-commons/src/alloq_commons/states/holiday_state.py
  - components/alloq-commons/src/alloq_commons/state/daily_rate_states.py
  - components/alloq-commons/src/alloq_commons/components/role.py
  - components/alloq-commons/src/alloq_commons/components/department.py
  - components/alloq-commons/src/alloq_commons/components/public_holiday.py
  - components/alloq-commons/src/alloq_commons/components/daily_rate.py
  - components/alloq-commons/src/alloq_commons/models/role.py
  - components/alloq-commons/src/alloq_commons/models/department.py
  - components/alloq-commons/src/alloq_commons/models/public_holiday.py
  - components/alloq-commons/src/alloq_commons/models/daily_rate.py
  - components/alloq-commons/src/alloq_commons/entities/role.py
  - components/alloq-commons/src/alloq_commons/entities/department.py
  - components/alloq-commons/src/alloq_commons/entities/employee.py
  - components/alloq-commons/src/alloq_commons/entities/daily_rate.py
  - components/alloq-commons/src/alloq_commons/repositories/role_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/department_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/public_holiday_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/daily_rate_repository.py
  - components/alloq-commons/src/alloq_commons/services/daily_rate_pricing.py
  - components/alloq-commons/src/alloq_commons/services/utilization.py
  - alembic/versions/2026_05_11_public_holidays.py
  - alembic/versions/2026_09_28_fix_holiday_dates_and_default_admin.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Roles, rates, departments and holidays

This page covers the master data that an administrator keeps for the whole organisation. The planning uses the roles and the public holidays, the team uses the departments, and the daily rates page turns production cost into sales prices. The stories belong to the activity "Set up the organisation" on the [story map](./story-map.md). The other half of that activity is on the page [Users and access](./users-and-access.md).

The activity has these user tasks and sub-tasks on this page:

- **Maintain master data.** Maintain roles, maintain departments, and maintain public holidays.
- **Set daily rates.** Enter production cost, set the contribution margins, and set a manual list price.

All four pages are for administrators only. Each page factory passes `admin_only=True` and wraps its content in `requires_admin`, and every event handler that reads or writes the database has the `@requires_admin` decorator. The [security page](../architecture/security-and-access.md#access-levels) explains the access levels.

The departments slice is the worked example on the [layers page](../architecture/layers.md), so this page does not explain the layers again. The [data model](../architecture/data-model.md) lists the fields of each entity.

## ADM-03 Create roles {#adm-03}

Create the roles (skills) that employees and project staffing use.

As an administrator, I want to keep a list of roles, so that employees can be given roles and projects can ask for them.

Administrator · Maintain master data / Maintain roles · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** a signed-in admin, **when** the admin opens `/admin/roles` ("Rollen" [roles]), **then** the table lists all roles ordered by name with the columns "Name", "Beschreibung" [description], "Ramp-Up" and "Ramp-Down". The loading row "Lade Rollen..." [loading roles] only shows on the first load, and later visits refresh the rows in place.
2. **Given** the dialog "Rolle hinzufügen" [add role], opened with the button "Neue Rolle" [new role], **when** the admin enters the data, **then** "Name" is required and at most 255 characters, "Abkürzung" [abbreviation] is at most 3 characters, and "Beschreibung" is optional. The switches "Ramp-Up" and "Ramp-Down" mark a role that a project needs during its ramp-up or ramp-down.
3. **Given** a name made of spaces only, **when** the admin saves, **then** the handler trims the name, the write model `RoleCreate` rejects it, and the toast "Fehler beim Erstellen der Rolle." [error creating the role] appears.
4. **Given** a name that another role already uses, **when** the admin saves, **then** the unique index on the name refuses it and the same toast "Fehler beim Erstellen der Rolle." appears. There is no separate message for a duplicate name. (no test)
5. **Given** valid data, **when** the admin clicks "Rolle speichern" [save role], **then** the role is stored, the list reloads, the dialog closes and the toast "Rolle '&lt;name&gt;' wurde erstellt." [role created] appears.
6. **Given** text in "Rollen suchen" [search roles], **when** the table renders, **then** it shows only the roles whose name or description contains the text, ignoring case.
7. **Given** the role form, **when** the admin types, **then** the browser stops at 255 characters for the name and at 3 characters for the abbreviation.

### Evidence

- [app/pages/roles.py](../../app/pages/roles.py): `create_roles_page`
- [state/role_states.py](../../components/alloq-commons/src/alloq_commons/state/role_states.py): `RoleState.load_roles`, `RoleState.create_role`, `RoleState.open_add_modal`, `RoleState.close_add_modal`, `RoleState.set_search_filter`, `RoleState.filtered_roles`
- [components/role.py](../../components/alloq-commons/src/alloq_commons/components/role.py): `roles_table`, `add_role_modal`, `role_form_fields`, `roles_toolbar`
- [models/role.py](../../components/alloq-commons/src/alloq_commons/models/role.py): `RoleCreate`
- [entities/role.py](../../components/alloq-commons/src/alloq_commons/entities/role.py): `RoleEntity`
- [repositories/role_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/role_repository.py): `RoleRepository.find_all_paginated`
- Tests: [test_roles.py](../../components/alloq-commons/tests/test_roles.py) `TestRoleStateAsync.test_load_roles_keeps_rows_when_already_loaded`, `TestRoleCreateModel.test_max_length_name`, `TestRoleStateAsync.test_create_role_success`, `TestRoleState.test_filtered_roles_case_insensitive`, `TestRoleComponents.test_form_inputs_limit_length_in_browser`; [test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) `TestModelValidation.test_blank_role_name_rejected`

### Open questions

- The plan modal reads the flags "Ramp-Up" and "Ramp-Down" in `ProjectPlanState._effective_ramps_for`, and a flagged role gets no ramp shape. The effect belongs to [PLAN-20](./staffing.md#plan-20) and to the [plan distribution](../architecture/calculations.md#plan-distribution-in-the-plan-modal) on the calculations page, and this page only links to them.
- The table has no column for the abbreviation, although the form stores it.

## ADM-04 Change or delete a role {#adm-04}

Change or delete a role, unless projects still use it.

As an administrator, I want to rename or remove roles, so that the role list stays current.

Administrator · Maintain master data / Maintain roles · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** the edit icon of a role, **when** the admin clicks it, **then** the dialog "Rolle bearbeiten" [edit role] opens with the stored values.
2. **Given** changed values, **when** the admin clicks "Rolle aktualisieren" [update role], **then** the role is saved and the toast "Rolle '&lt;name&gt;' wurde aktualisiert." [role updated] appears. Without a selected role the toast is "Keine Rolle ausgewählt." [no role selected], and a role that was deleted in the meantime gives "Rolle nicht gefunden." [role not found].
3. **Given** the delete icon and the dialog "Löschen bestätigen" [confirm delete], **when** the admin confirms, **then** the role is deleted and the toast "Rolle wurde gelöscht." [role deleted] appears. An unknown role gives "Rolle nicht gefunden.".
4. **Given** a role that a capacity row, a required capacity or a weekly allocation uses, **when** the admin deletes it, **then** the database refuses the delete because these foreign keys use `ondelete="RESTRICT"`, and the toast "Rolle wird noch verwendet und kann nicht gelöscht werden." [role is still in use and cannot be deleted] appears. The links between employees and the role and the daily rate of the role are deleted with the role (`CASCADE`). Employees with this role as key role keep no key role (`SET NULL`). (no test)

### Evidence

- [state/role_states.py](../../components/alloq-commons/src/alloq_commons/state/role_states.py): `RoleState.select_role_and_open_edit`, `RoleState.open_edit_modal`, `RoleState.close_edit_modal`, `RoleState.update_role`, `RoleState.delete_role`
- [components/role.py](../../components/alloq-commons/src/alloq_commons/components/role.py): `edit_role_modal`, `update_role_button`, `delete_role_button`
- Foreign keys: [entities/capacity.py](../../components/alloq-commons/src/alloq_commons/entities/capacity.py), [entities/required_capacity.py](../../components/alloq-commons/src/alloq_commons/entities/required_capacity.py), [entities/capacity_allocation.py](../../components/alloq-commons/src/alloq_commons/entities/capacity_allocation.py), [entities/daily_rate.py](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py) `DailyRateEntity.role_id`, [entities/employee.py](../../components/alloq-commons/src/alloq_commons/entities/employee.py) `EmployeeEntity.key_role_id`
- Tests: [test_roles.py](../../components/alloq-commons/tests/test_roles.py) `TestRoleStateAsync.test_select_role_and_open_edit`, `TestRoleStateAsync.test_update_role_not_found`, `TestRoleStateAsync.test_delete_role_success`

### Open questions

- No test covers the message for a role that is still in use (the `IntegrityError` path).

## ADM-08 Create departments {#adm-08}

Create the departments of the organisation with a unique name and short code.

As an administrator, I want to keep a list of departments, so that employees can be put into them.

Administrator · Maintain master data / Maintain departments · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** a signed-in admin, **when** the admin opens `/admin/departments` ("Abteilungen" [departments]), **then** the table lists all departments ordered by name with the columns "Name" and "Kürzel" [abbreviation]. The loading row "Lade Abteilungen..." only shows on the first load.
2. **Given** the dialog "Abteilung hinzufügen" [add department], opened with the button "Neue Abteilung" [new department], **when** the admin saves without a name or without an abbreviation, **then** the toast "Name und Kürzel angeben." [enter name and abbreviation] appears. The name allows 255 characters and the abbreviation 10, and the browser stops typing at these limits.
3. **Given** a name or an abbreviation that another department already uses, **when** the admin saves, **then** the toast "Name oder Kürzel ist bereits vergeben." [name or abbreviation is already taken] appears.
4. **Given** valid data, **when** the admin clicks "Abteilung speichern" [save department], **then** the department is stored, the list reloads, the dialog closes and the toast "Abteilung '&lt;name&gt;' wurde erstellt." appears.
5. **Given** text in "Abteilungen suchen" [search departments], **when** the table renders, **then** it shows only the departments whose name or abbreviation contains the text, ignoring case.

### Evidence

- [app/pages/departments.py](../../app/pages/departments.py): `create_departments_page`
- [state/department_states.py](../../components/alloq-commons/src/alloq_commons/state/department_states.py): `DepartmentState.load_departments`, `DepartmentState.create_department`, `DepartmentState.open_add_modal`, `DepartmentState.close_add_modal`, `DepartmentState.set_search_filter`, `DepartmentState.filtered_departments`, `load_departments`, `DUPLICATE_MESSAGE`
- [components/department.py](../../components/alloq-commons/src/alloq_commons/components/department.py): `departments_table`, `department_form_fields`, `departments_toolbar`
- [models/department.py](../../components/alloq-commons/src/alloq_commons/models/department.py): `Department`, `DepartmentCreate`
- [entities/department.py](../../components/alloq-commons/src/alloq_commons/entities/department.py): `DepartmentEntity`
- [repositories/department_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/department_repository.py): `DepartmentRepository.find_all_paginated`
- Tests: [test_departments.py](../../components/alloq-commons/tests/test_departments.py) `TestDepartmentState.test_load`, `TestDepartmentState.test_create_rejects_missing_abbreviation`, `TestDepartmentState.test_create_duplicate_shows_message`, `TestDepartmentState.test_create`, `TestDepartmentState.test_filter_matches_name_or_abbreviation`, `TestDepartmentComponents.test_form_inputs_limit_length_in_browser`

### Open questions

- The migration `alembic/versions/2026_10_18_departments.py` turns the abbreviations that people entered before into departments. The data model page should describe it.

## ADM-09 Rename or delete a department {#adm-09}

Rename or delete a department. Its employees then have no department.

As an administrator, I want to rename or delete a department, so that the list matches the organisation.

Administrator · Maintain master data / Maintain departments · priority 2 · core · v2.0.4

### Acceptance criteria

1. **Given** the edit icon of a department, **when** the admin clicks it, changes the values and clicks "Abteilung aktualisieren" [update department], **then** the department is saved and the toast "Abteilung '&lt;name&gt;' wurde aktualisiert." appears. The same rules and messages as for creating apply.
2. **Given** no selected department, or one that was deleted in the meantime, **when** the update runs, **then** the toast "Keine Abteilung ausgewählt." [no department selected] or "Abteilung nicht gefunden." [department not found] appears.
3. **Given** the delete icon and the dialog "Löschen bestätigen", **when** the admin confirms, **then** the department is deleted and the toast "Abteilung wurde gelöscht." appears. An unknown department gives "Abteilung nicht gefunden.", and a database error gives "Fehler beim Löschen der Abteilung.".
4. **Given** employees in the deleted department, **when** the department is deleted, **then** those employees keep no department, because `EmployeeEntity.department_id` uses `ondelete="SET NULL"`. (no test)

### Evidence

- [state/department_states.py](../../components/alloq-commons/src/alloq_commons/state/department_states.py): `DepartmentState.select_department_and_open_edit`, `DepartmentState.close_edit_modal`, `DepartmentState.update_department`, `DepartmentState.delete_department`
- [components/department.py](../../components/alloq-commons/src/alloq_commons/components/department.py): `departments_table_row`, `edit_department_modal`
- [entities/employee.py](../../components/alloq-commons/src/alloq_commons/entities/employee.py): `EmployeeEntity.department_id`
- Tests: [test_departments.py](../../components/alloq-commons/tests/test_departments.py) `TestDepartmentState.test_select_and_update`, `TestDepartmentState.test_update_without_selection`, `TestDepartmentState.test_delete_unknown`

### Open questions

- A deleted department leaves its role `department_<id>` on the users who had it (see [ADM-02](./users-and-access.md#adm-02)). Nothing removes this role.

## ADM-10 Keep public holidays per year {#adm-10}

Keep the list of public holidays for each year.

As an administrator, I want to keep the public holidays for each year, so that planning does not count holidays as working days.

Administrator · Maintain master data / Maintain public holidays · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** a signed-in admin, **when** the admin opens `/admin/holidays` ("Feiertage" [public holidays]), **then** the table lists the holidays stored for the selected year, ordered by date, with the columns "Datum" [date], "Name" and "Typ" [type]. The type is "Jährlich" [yearly] for a recurring holiday and "Beweglich" [movable] for the others.
2. **Given** the year select in the toolbar, **when** the admin picks a year, **then** the list reloads for that year. The select offers the previous year, the current year and the next two years. On the first load of a session the year is set to the current year.
3. **Given** the dialog "Feiertag hinzufügen" [add holiday], opened with the button "Neuer Feiertag" [new holiday], **when** the admin saves a name, a date and the switch "Jährlich wiederkehrend (fixer Termin)" [recurs yearly, fixed date], **then** the holiday is stored with the state code "NRW" and the toast "Feiertag '&lt;name&gt;' wurde erstellt." appears. The handler reads the date as DD.MM.YYYY or as an ISO date.
4. **Given** an empty name, a name over 255 characters or a date that cannot be read, **when** the admin saves, **then** the toast "Fehler beim Erstellen des Feiertags." [error creating the holiday] appears.
5. **Given** text in "Feiertage suchen" [search holidays], **when** the table renders, **then** it shows only the holidays whose name contains the text, ignoring case.

### Evidence

- [app/pages/holidays.py](../../app/pages/holidays.py): `create_holidays_page`
- [states/holiday_state.py](../../components/alloq-commons/src/alloq_commons/states/holiday_state.py): `HolidayState.load_holidays`, `HolidayState.change_year`, `HolidayState.set_selected_year`, `HolidayState.available_years`, `HolidayState.create_holiday`, `HolidayState.open_add_modal`, `HolidayState.close_add_modal`, `HolidayState.set_search_filter`, `HolidayState.filtered_holidays`, `_parse_date`, `_year_range`
- [components/public_holiday.py](../../components/alloq-commons/src/alloq_commons/components/public_holiday.py): `holidays_table`, `holidays_table_row`, `holiday_form_fields`, `holiday_year_select`, `holidays_toolbar`
- [models/public_holiday.py](../../components/alloq-commons/src/alloq_commons/models/public_holiday.py): `PublicHoliday`, `PublicHolidayCreate`
- [entities/public_holiday.py](../../components/alloq-commons/src/alloq_commons/entities/public_holiday.py): `PublicHolidayEntity`
- [repositories/public_holiday_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/public_holiday_repository.py): `PublicHolidayRepository.find_by_year`
- Tests: [test_public_holidays.py](../../components/alloq-commons/tests/test_public_holidays.py) `TestPublicHolidayRepository.test_find_by_year`; [test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) `TestHolidayYear.test_previous_year_is_selectable`; [test_holiday_state.py](../../components/alloq-commons/tests/test_holiday_state.py) `test_create_holiday_persists_and_closes_modal`, `test_create_holiday_with_bad_date_shows_error`, `test_simple_setters_and_vars`

### Open questions

- The form has no field for the state code, so every new holiday gets "NRW". The toolbar subtitle says "Administration · NRW-Feiertage pflegen" [maintain NRW holidays].
- The list uses `find_by_year`, which returns only the rows stored for that year. A yearly holiday that is stored only for 2026 does not show in the list for 2027, although the capacity counts it in 2027 (see [ADM-12](#adm-12)).

## ADM-11 Change or delete a holiday {#adm-11}

Change or delete a public holiday.

As an administrator, I want to correct or remove a holiday, so that the capacity numbers stay right.

Administrator · Maintain master data / Maintain public holidays · priority 2 · core · v0.2.0

### Acceptance criteria

1. **Given** the edit icon of a holiday, **when** the admin clicks it, **then** the dialog "Feiertag bearbeiten" [edit holiday] opens with the stored name, date and recurrence.
2. **Given** changed values, **when** the admin clicks "Feiertag aktualisieren" [update holiday], **then** the holiday is saved and the toast "Feiertag '&lt;name&gt;' wurde aktualisiert." appears. Without a selected holiday the toast is "Kein Feiertag ausgewählt." [no holiday selected], and a holiday that was deleted in the meantime gives "Feiertag nicht gefunden." [holiday not found].
3. **Given** the delete icon and the dialog "Löschen bestätigen", **when** the admin confirms, **then** the holiday is deleted and the toast "Feiertag '&lt;name&gt;' wurde gelöscht." appears. A failure shows "Feiertag nicht gefunden.", "Feiertag konnte nicht gelöscht werden." [holiday could not be deleted] or "Fehler beim Löschen des Feiertags." [error deleting the holiday].

### Evidence

- [states/holiday_state.py](../../components/alloq-commons/src/alloq_commons/states/holiday_state.py): `HolidayState.select_holiday_and_open_edit`, `HolidayState.selected_holiday_date_iso`, `HolidayState.open_edit_modal`, `HolidayState.close_edit_modal`, `HolidayState.update_holiday`, `HolidayState.delete_holiday`
- [components/public_holiday.py](../../components/alloq-commons/src/alloq_commons/components/public_holiday.py): `edit_holiday_modal`, `_update_holiday_button`, `_delete_holiday_button`
- Tests: [test_holiday_state.py](../../components/alloq-commons/tests/test_holiday_state.py) `test_select_holiday_opens_edit_modal`, `test_update_missing_holiday_shows_error`, `test_delete_holiday_failures`

## ADM-12 Recurring holidays reduce capacity {#adm-12}

Holidays with a fixed date count every year, and all holidays reduce the working capacity.

As an administrator, I want fixed-date holidays to repeat every year and all holidays to lower capacity, so that I do not have to enter New Year again each year.

Administrator · Maintain master data / Maintain public holidays · priority 3 · core · v0.3.0

### Acceptance criteria

1. **Given** a holiday marked as yearly that is stored for another year, **when** the code reads the holidays for a date range, **then** the repository adds the holiday on the same month and day in every year of the range. It adds no second copy when a holiday with the same date and state code is already stored, and it skips 29 February in years without that day.
2. **Given** a holiday on a weekday, **when** the code computes the weekly capacity for the team list, the planning grid or the dashboard, **then** it subtracts that day from the five working days of the week. The [calculations page](../architecture/calculations.md#capacity-of-one-person-in-one-week) explains the full rule.
3. **Given** a new database, **when** the migrations run, **then** the NRW holidays of 2026 and 2027 are inserted. A later migration corrects the seeded 2026 dates of "Pfingstsonntag", "Pfingstmontag" and "Fronleichnam". (no test)

### Evidence

- [repositories/public_holiday_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/public_holiday_repository.py): `PublicHolidayRepository.find_by_date_range`, `_project_recurring`
- [services/utilization.py](../../components/alloq-commons/src/alloq_commons/services/utilization.py): `UtilizationService.holidays_in_week`, `UtilizationService.work_days_for_week`
- [alembic/versions/2026_05_11_public_holidays.py](../../alembic/versions/2026_05_11_public_holidays.py): `upgrade`
- [alembic/versions/2026_09_28_fix_holiday_dates_and_default_admin.py](../../alembic/versions/2026_09_28_fix_holiday_dates_and_default_admin.py): `HOLIDAY_DATE_FIXES`, `upgrade`
- Tests: [test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) `TestRecurringHolidays.test_recurring_holiday_projects_to_later_year`, `TestUtilizationHolidaysAndWorkload.test_holiday_reduces_capacity_like_the_grid`

### Open questions

- The data model page could mention that the first seed had wrong dates for three movable holidays in 2026, e.g. "Pfingstsonntag" on 2026-06-24 instead of 2026-05-24.

## ADM-05 Production cost and sales prices {#adm-05}

Enter the production cost per role and read the calculated sales prices.

As an administrator, I want to enter the daily production cost of each role and see the prices that follow from the margins, so that offers use consistent daily rates.

Administrator · Set daily rates / Set daily rates · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** a signed-in admin, **when** the admin opens `/admin/daily-rates` ("Tagessätze" [daily rates]), **then** the table shows one row per role, also for roles without a rate, ordered by role name. The columns are "Rolle" [role], "Herstellkosten" [production cost], "Empf. Verkaufspreis" [recommended sales price] and "Listenpreis" [list price]. Without roles the table shows "Noch keine Rollen angelegt." [no roles created yet].
2. **Given** a production cost and a margin, **when** a price is calculated, **then** the price is the cost divided by (1 minus the margin), rounded up to the next full 10 EUR. The recommended sales price uses "Mindest-DB" [minimum contribution margin], and the list price uses "DB" [contribution margin]. For example, a cost of 700 EUR gives 1000 EUR at 30 % and 1080 EUR at 35 %. The page shows this rule as a hint next to the margin inputs.
3. **Given** a priced row, **when** it renders, **then** a small text next to the recommended price and next to the list price shows the margin in euros and as a percent of that price, e.g. "DB 380 € · 35 %". The recommended price is read only.
4. **Given** a new value in "Herstellkosten", **when** the input loses focus, **then** the value is stored as whole euros. An unchanged value is not saved. A value outside 1 to 100000 shows the toast "Preise müssen zwischen 1 und 100000 € liegen." [prices must be between 1 and 100000 EUR], and the inputs show the stored values again.
5. **Given** a role whose production cost and list price are both cleared, **when** the last price is removed, **then** the daily rate row of the role is deleted.
6. **Given** a database error, **when** the page loads, **then** the toast "Fehler beim Laden der Tagessätze." [error loading the daily rates] appears. **When** a price is saved, **then** the toast "Fehler beim Speichern des Tagessatzes." [error saving the daily rate] appears and the inputs show the stored values again.
7. **Given** text in "Rollen suchen", **when** the table renders, **then** it lists only the roles whose name contains the text, ignoring case. The toolbar has no other action.

### Evidence

- [app/pages/daily_rates.py](../../app/pages/daily_rates.py): `create_daily_rates_page`
- [state/daily_rate_states.py](../../components/alloq-commons/src/alloq_commons/state/daily_rate_states.py): `DailyRateState.load_daily_rates`, `DailyRateState.save_production_cost`, `DailyRateState._save_price`, `DailyRateState.set_search_filter`, `DailyRateState.rows`, `INVALID_PRICE_MESSAGE`
- [services/daily_rate_pricing.py](../../components/alloq-commons/src/alloq_commons/services/daily_rate_pricing.py): `round_up_to_ten`, `price_for_margin`, `price_rate`
- [components/daily_rate.py](../../components/alloq-commons/src/alloq_commons/components/daily_rate.py): `daily_rates_table`, `daily_rates_table_row`, `_margin_text`, `daily_rates_toolbar`, `PRICE_HINT`, `EMPTY_TEXT`
- [models/daily_rate.py](../../components/alloq-commons/src/alloq_commons/models/daily_rate.py): `DailyRate`, `DailyRateUpdate`, `MAX_PRICE`
- [entities/daily_rate.py](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py): `DailyRateEntity`
- [repositories/daily_rate_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/daily_rate_repository.py): `DailyRateRepository.find_all_by_role_name`, `DailyRateRepository.find_by_role_id`
- Tests: [test_daily_rates.py](../../components/alloq-commons/tests/test_daily_rates.py) `TestDailyRateState.test_rows_list_every_role_with_prices`, `TestDailyRateComponents.test_table_has_price_inputs_per_role`, `TestDailyRateState.test_invalid_price_shows_message`, `TestDailyRateState.test_clearing_last_price_deletes_rate`, `TestDailyRateState.test_save_error_shows_toast`, `TestDailyRateComponents.test_toolbar_has_search_only`; [test_daily_rate_pricing.py](../../components/alloq-commons/tests/test_daily_rate_pricing.py) `test_sales_price_uses_minimal_margin_and_list_price_the_margin`

### Open questions

- No other page reads the daily rates yet. It is not clear whether project budgets will use them later.
- `price_for_margin` keeps the cost share at 1 % or more, so a margin of 100 % gives the cost times 100. The page limits the margins to 90 %, so this case does not occur through the UI.

## ADM-07 Set the contribution margins {#adm-07}

Set the two contribution margins that drive all calculated prices.

As an administrator, I want to set the minimum and the regular contribution margin once for all roles, so that every price follows the same rule.

Administrator · Set daily rates / Set daily rates · priority 2 · core · v2.0.4

### Acceptance criteria

1. **Given** no stored margins, **when** the page loads, **then** "Mindest-DB (Empf. VK)" [minimum margin for the recommended sales price] is 30 % and "DB (Listenpreis)" [margin for the list price] is 35 %.
2. **Given** the admin types a new margin, **when** the value changes, **then** the prices in the table follow the typed value right away, before it is saved.
3. **Given** a margin input loses focus, **when** both values are whole numbers from 0 to 90 and the minimum is not above the regular margin, **then** both margins are stored in the single settings row and the toast "Deckungsbeiträge gespeichert." [margins saved] appears. Unchanged values are not saved.
4. **Given** a minimum above the regular margin or a value outside 0 to 90, **when** the input loses focus, **then** the toast "Deckungsbeiträge müssen zwischen 0 und 90 % liegen, der Mindest-DB darf nicht über dem DB liegen." [margins must be between 0 and 90 %, and the minimum may not be above the margin] appears and both inputs return to the stored values.
5. **Given** a database error, **when** the margins are saved, **then** the toast "Fehler beim Speichern der Deckungsbeiträge." [error saving the margins] appears and the inputs return to the stored values.

### Evidence

- [state/daily_rate_states.py](../../components/alloq-commons/src/alloq_commons/state/daily_rate_states.py): `DailyRateState.save_margins`, `DailyRateState.set_min_margin_draft`, `DailyRateState.set_margin_draft`, `INVALID_MARGIN_MESSAGE`
- [components/daily_rate.py](../../components/alloq-commons/src/alloq_commons/components/daily_rate.py): `margin_settings`, `PRICE_HINT`
- [models/daily_rate.py](../../components/alloq-commons/src/alloq_commons/models/daily_rate.py): `DailyRateSettingsUpdate`, `MAX_CONTRIBUTION_MARGIN_PERCENT`
- [entities/daily_rate.py](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py): `DailyRateSettingsEntity`, `DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT`, `DEFAULT_CONTRIBUTION_MARGIN_PERCENT`
- [repositories/daily_rate_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/daily_rate_repository.py): `DailyRateRepository.get_margins`, `DailyRateRepository.save_margins`
- Tests: [test_daily_rates.py](../../components/alloq-commons/tests/test_daily_rates.py) `TestDailyRateRepository.test_margins_default_and_can_be_saved`, `TestDailyRateState.test_rows_follow_margin_inputs_while_typing`, `TestDailyRateState.test_save_margins`, `TestDailyRateState.test_minimum_above_margin_is_rejected`, `TestDailyRateState.test_save_margins_error`

## ADM-06 Manual list price {#adm-06}

Replace the calculated list price of a role with a manual one.

As an administrator, I want to set a manual list price for a role, so that I can publish a price that differs from the calculated one.

Administrator · Set daily rates / Set daily rates · priority 3 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a value in "Listenpreis" that differs from the calculated list price, **when** the input loses focus, **then** the value is stored as the manual list price and replaces the calculated price. Its margin text starts with "manuell" [manual].
2. **Given** a value equal to the calculated list price, **when** the input loses focus, **then** the manual price is cleared, so the list price follows the margin again.
3. **Given** a role without production cost, **when** the row is priced, **then** only a manual list price shows, with no margin text and no recommended price.

### Evidence

- [state/daily_rate_states.py](../../components/alloq-commons/src/alloq_commons/state/daily_rate_states.py): `DailyRateState.save_list_price`, `DailyRateState._new_price`
- [services/daily_rate_pricing.py](../../components/alloq-commons/src/alloq_commons/services/daily_rate_pricing.py): `price_rate`
- [components/daily_rate.py](../../components/alloq-commons/src/alloq_commons/components/daily_rate.py): `_margin_text`
- Tests: [test_daily_rates.py](../../components/alloq-commons/tests/test_daily_rates.py) `TestDailyRateState.test_manual_list_price_is_stored`, `TestDailyRateState.test_price_equal_to_calculated_clears_manual_price`; [test_daily_rate_pricing.py](../../components/alloq-commons/tests/test_daily_rate_pricing.py) `test_without_cost_only_manual_prices_show`
