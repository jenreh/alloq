---
title: Maintain and track a project
description: How project managers edit and delete a project, change its status and period in the inspector, record status reports, read the earned value chart and manage risks.
story_ids: [PROJ-09, PROJ-12, PROJ-10, PROJ-11, PROJ-13, PROJ-14, PROJ-15, PROJ-16, PROJ-17]
source_paths:
  - components/alloq-project/src/alloq_project/states/project_state.py
  - components/alloq-project/src/alloq_project/states/project_list_state.py
  - components/alloq-project/src/alloq_project/states/project_status_form_mixin.py
  - components/alloq-project/src/alloq_project/states/project_risk_draft_mixin.py
  - components/alloq-project/src/alloq_project/states/project_validation_state.py
  - components/alloq-project/src/alloq_project/services/forecast.py
  - components/alloq-project/src/alloq_project/components/project_overview.py
  - components/alloq-project/src/alloq_project/components/project_inspector.py
  - components/alloq-project/src/alloq_project/components/project_table.py
  - components/alloq-project/src/alloq_project/components/project_card.py
  - components/alloq-project/src/alloq_project/components/project_status_tab.py
  - components/alloq-project/src/alloq_project/components/project_risk_tab.py
  - components/alloq-commons/src/alloq_commons/components/dialogs.py
  - components/alloq-commons/src/alloq_commons/entities/project.py
  - components/alloq-commons/src/alloq_commons/entities/status.py
  - components/alloq-commons/src/alloq_commons/entities/risk.py
  - components/alloq-commons/src/alloq_commons/models/project.py
  - components/alloq-commons/src/alloq_commons/repositories/status_repository.py
  - components/alloq-commons/src/alloq_commons/repositories/risk_repository.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Maintain and track a project

This page covers what a project manager does with a project after it exists. The stories belong to the activity "Create and track projects" on the [story map](./story-map.md).

The page has these user tasks and sub-tasks:

- **Maintain a project.** Edit the project data, delete a project, and change its status and period in the inspector.
- **Track project progress.** Record a status, correct the status history, and read the earned value chart.
- **Manage project risks.** Record a risk and read the risk matrix.

Most of this work happens in the project drawer on the page "Projekte" [projects] at `/projects`. The drawer has the tabs "Status", "Ressourcen" [resources], "Risiken" [risks] and "Daten" [data]. Creating a project and the fields of the project form are on the [projects page](./projects.md). The tab "Ressourcen" is on the [staffing page](./staffing.md). The formulas for earned value and the forecasts are in [Calculations](../architecture/calculations.md#earned-value-and-forecast).

All handlers that change data use the guard `@requires_editor`, so only admins and users with the role project_manager can call them. Users with the role employee can open the drawer and read it, as described in [PROJ-20](./projects.md#proj-20).

## PROJ-09 Project drawer with tabs {#proj-09}

A drawer with the tabs "Status", "Ressourcen", "Risiken" and "Daten" opens a project for detail work.

As a project manager, I want to open a project and edit its master data, so that the project stays correct when plans change.

Project manager · Maintain a project / Edit project data · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** a project in the list, **when** the user double-clicks its table row or clicks its card, **then** `ProjectState.select_project` loads the project with its status history (newest first), risks, capacities, required capacities, allocations and the public holidays in its period, and opens the drawer.
2. **Given** a project in the inspector, **when** an editor clicks "Bearbeiten" [edit] or "Status erfassen" [record status], **then** the drawer opens on the tab "Daten" or "Status". Users with the role employee see the button "Details" instead, and it opens the tab "Status".
3. **Given** a project id that no longer exists, **when** the drawer is opened, **then** the toast "Projekt nicht gefunden." [project not found] appears and the loading flag is reset.
4. **Given** the tab "Daten" with changed values, **when** the user clicks "Projekt aktualisieren" [update project], **then** `ProjectState.update_project` writes the fields, replaces the owners and the required capacities, closes the drawer and shows the toast "Projekt '&lt;name&gt;' aktualisiert." [project updated]. The button is disabled while `ProjectValidationState.is_form_invalid` is true.
5. **Given** form data that fails `ProjectCreate`, e.g. an end date before the start, **when** the update is sent, **then** the toast "Ungültige Projektdaten." [invalid project data] appears and the drawer stays open.
6. **Given** a project code that another project already uses, **when** the update is saved, **then** the toast "Projekt-Code bereits vergeben." [project code already taken] appears. (no test)
7. **Given** the drawer is closed, **when** `close_detail_drawer` runs, **then** it clears the loaded project data, resets the status form and both drafts, and sets the tab back to "Status". (no test)

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.select_project`, `ProjectState.select_project_with_tab`, `ProjectState.set_active_tab`, `ProjectState.update_project`, `ProjectState.close_detail_drawer`, `_newest_first`, `_project_error_message`
- [project_validation_state.py](../../components/alloq-project/src/alloq_project/states/project_validation_state.py): `ProjectValidationState.initialize`
- [project_overview.py](../../components/alloq-project/src/alloq_project/components/project_overview.py): `project_detail_drawer`
- [project_inspector.py](../../components/alloq-project/src/alloq_project/components/project_inspector.py): `_actions`, `_open`
- [project_table.py](../../components/alloq-project/src/alloq_project/components/project_table.py): `on_double_click` of the project row
- [project_card.py](../../components/alloq-project/src/alloq_project/components/project_card.py): `project_card`
- [project.py](../../components/alloq-commons/src/alloq_commons/models/project.py): `ProjectCreate`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestProjectLifecycle.test_select_project_loads_drawer`, `test_select_missing_project_shows_error`, `test_update_project_applies_form`, `test_update_invalid_form_shows_error`, `test_update_missing_project_shows_error`, `test_update_without_selection_does_nothing`

## PROJ-12 Delete a project {#proj-12}

A project manager can delete a project after a confirmation.

As a project manager, I want to delete a project that was created by mistake, so that it no longer appears in planning and reports.

Project manager · Maintain a project / Delete a project · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the card view and an editor, **when** the user clicks the delete icon of a card, **then** a confirmation dialog "Projekt löschen" [delete project] with the project name opens first. Users with the role employee do not see the icon. (no test)
2. **Given** a confirmed delete, **when** the project exists, **then** `ProjectState.delete_project` removes it, the database removes its statuses, risks, capacities, allocations and required capacities with it (`cascade="all, delete-orphan"`), the drawer closes and the toast "Projekt gelöscht." [project deleted] appears.
3. **Given** a project id that no longer exists, **when** the delete runs, **then** the toast "Projekt nicht gefunden." appears.
4. **Given** a user with the role employee, **when** they call the delete, **then** the guard refuses the call and the project stays.

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.delete_project`, `ProjectState._remove_project`
- [project_card.py](../../components/alloq-project/src/alloq_project/components/project_card.py): `project_card`
- [dialogs.py](../../components/alloq-commons/src/alloq_commons/components/dialogs.py): `delete_dialog`
- [project.py](../../components/alloq-commons/src/alloq_commons/entities/project.py): `ProjectEntity` relationships
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateAuthorization.test_admin_can_delete_project`, `test_employee_can_load_but_not_delete_projects`; [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestProjectLifecycle.test_delete_missing_project_shows_error`

### Open questions

- Deleting is only offered on the project cards of the card view, not in the table, the inspector or the drawer. Is that intended?

## PROJ-10 Change status in the inspector {#proj-10}

A project manager can change the project status in the inspector without opening the form.

As a project manager, I want to change a project's status in the inspector, so that a status change takes one click.

Project manager · Maintain a project / Change status and period in the inspector · priority 1 · comfort · v2.0.0

### Acceptance criteria

1. **Given** the select "Status" in the inspector, **when** the user picks "Geplant" [planned], "Aktiv" [active], "Risiko" [at risk] or "Abgeschlossen" [completed], **then** `update_inspected_project_state` saves the state at once, updates the list and an open drawer, and shows the toast "Status gespeichert." [status saved].
2. **Given** a value that is not one of the `ProjectStateEnum` values, **when** it is sent, **then** the toast "Ungültiger Projektstatus." [invalid project status] appears and nothing is saved.
3. **Given** a project that no longer exists, **when** the state is saved, **then** the toast "Projekt nicht gefunden." appears. (no test)
4. **Given** a user with the role employee, **when** they look at the inspector, **then** the select is disabled (`disabled=~CAN_EDIT`), and the guard refuses a direct call of the handler.

### Evidence

- [project_list_state.py](../../components/alloq-project/src/alloq_project/states/project_list_state.py): `ProjectListState.update_inspected_project_state`, `ProjectListState._apply_project_state`, `STATUS_TONES`
- [project_inspector.py](../../components/alloq-project/src/alloq_project/components/project_inspector.py): `_details`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.state_select_options`
- [project.py](../../components/alloq-commons/src/alloq_commons/entities/project.py): `ProjectStateEnum`
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateHandlers.test_update_inspected_project_state_saves_immediately`, `test_update_inspected_project_state_rejects_unknown_value`, `test_non_admin_cannot_update_inspected_project_state`

## PROJ-11 Change period in the inspector {#proj-11}

A project manager can change the project period in the inspector, and Alloq saves it when the field loses focus.

As a project manager, I want to move a project's start or end date in the inspector, so that I can adjust the period quickly.

Project manager · Maintain a project / Change status and period in the inspector · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a project without dates, **when** the inspector shows "Start" and "Ende" [end], **then** the start shows today and the end shows the start plus 5 days (`DEFAULT_PERIOD_DAYS`). (no test)
2. **Given** the start date in the inspector, **when** the user picks a start after the current end, **then** `set_inspected_date_draft` moves the end to the new start.
3. **Given** an edited date, **when** the input loses focus, **then** `save_inspected_dates` saves both dates and shows the toast "Zeitraum gespeichert." [period saved]. A period that equals the stored one is not saved again.
4. **Given** an end before the start, **when** the input loses focus, **then** the toast "Das Ende darf nicht vor dem Start liegen." [the end must not be before the start] appears and the draft is discarded.
5. **Given** a date that cannot be read, **when** the input loses focus, **then** the toast "Bitte ein gültiges Datum eingeben." [please enter a valid date] appears and the draft is discarded. (no test)
6. **Given** the button "Heute" [today] next to a date, **when** an editor clicks it, **then** the date is set to today and saved. Users with the role employee do not see the button, and both inputs are disabled.

### Evidence

- [project_list_state.py](../../components/alloq-project/src/alloq_project/states/project_list_state.py): `ProjectListState.set_inspected_date_draft`, `ProjectListState.set_inspected_date_today`, `ProjectListState.save_inspected_dates`, `ProjectListState.inspected_start_date`, `ProjectListState.inspected_end_date`, `DEFAULT_PERIOD_DAYS`
- [project_inspector.py](../../components/alloq-project/src/alloq_project/components/project_inspector.py): `_date_input`, `_details`
- Tests: [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateHandlers.test_start_after_end_moves_end_to_start`, `test_today_button_sets_draft_to_today`, `test_save_inspected_dates_saves_on_blur`, `test_save_inspected_dates_rejects_end_before_start`

## PROJ-13 Record a status {#proj-13}

The tab "Status" records the progress and the budget use of a project on a date.

As a project manager, I want to record the progress and budget use of my project, so that the project history and forecast stay up to date.

Project manager · Track project progress / Record a status · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the form "Status erfassen" [record status], **when** the drawer opens, **then** the field "Datum" [date] shows today, and "Fortschritt (%)" [progress] and "Budgetverbrauch (%)" [budget use] show 0.
2. **Given** the fields "Fortschritt (%)" and "Budgetverbrauch (%)", **when** the user enters a value, **then** `_clamp_percent` limits it to 0 to 100, and input that is not a number becomes 0.
3. **Given** a filled form, **when** the user clicks "Status erfassen", **then** `add_project_status` stores a new history entry with its earned value figures from `EVForecastService.compute_status_ev`. It then writes the new summary to the project (`_persist_ev_summary`), clears the form and shows the toast "Status gespeichert.".
4. **Given** a second click that was queued with an old form version, **when** it arrives, **then** the handler ignores it, so a double click stores only one entry.
5. **Given** a date that cannot be read, **when** the user saves, **then** the toast "Ungültiges Datum." [invalid date] appears. (no test)

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.add_project_status`, `ProjectState._persist_ev_summary`, `_status_ev_fields`
- [project_status_form_mixin.py](../../components/alloq-project/src/alloq_project/states/project_status_form_mixin.py): `_clamp_percent`, `ProjectStatusFormMixin.set_status_progress`, `set_status_budget_usage`, `set_status_notes`, `set_status_date`, `_reset_status_form`
- [project_status_tab.py](../../components/alloq-project/src/alloq_project/components/project_status_tab.py): `status_tab`, `_status_form`
- [status.py](../../components/alloq-commons/src/alloq_commons/entities/status.py): `ProjectStatusEntity`
- [status_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/status_repository.py): `ProjectStatusRepository.find_by_project_id`
- [forecast.py](../../components/alloq-project/src/alloq_project/services/forecast.py): `EVForecastService.compute_status_ev`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestStatusDraft.test_draft_setters_clamp_and_default`; [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateHandlers.test_add_status_with_current_form_version_saves`, `test_add_status_with_stale_form_version_is_ignored`; [test_project_components.py](../../components/alloq-project/tests/test_project_components.py) `TestStatusTab.test_add_status_sends_rendered_form_version`

## PROJ-14 Correct the status history {#proj-14}

A project manager can correct an entry in the status history inline or delete it.

As a project manager, I want to correct or delete a wrong status entry, so that the history and the forecast are right.

Project manager · Track project progress / Correct the status history · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** an entry under "Verlauf" [history], **when** the user clicks it, **then** `expand_status` opens an inline form with its date, progress, budget use and note. A second click closes it, and "Abbrechen" [cancel] closes it too.
2. **Given** an edited entry, **when** the user clicks "Speichern" [save], **then** `save_status_draft` updates the entry and its earned value figures, sorts the history again, refreshes the project summary and shows the toast "Status aktualisiert." [status updated].
3. **Given** an entry that no longer exists, **when** the user saves, **then** the toast "Status nicht gefunden." [status not found] appears.
4. **Given** a date that cannot be read, **when** the user saves, **then** the toast "Ungültiges Datum." appears.
5. **Given** the delete icon of an entry, **when** the user confirms the dialog "Status löschen" [delete status], **then** `delete_project_status` removes the entry, refreshes the project summary and shows the toast "Status gelöscht." [status deleted].
6. **Given** a status id that is not in the open project's history, **when** the delete is called, **then** the handler ignores it.

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.save_status_draft`, `ProjectState.delete_project_status`
- [project_status_form_mixin.py](../../components/alloq-project/src/alloq_project/states/project_status_form_mixin.py): `ProjectStatusFormMixin.expand_status`, `collapse_status_edit`, `set_status_draft_progress`, `set_status_draft_budget_usage`, `set_status_draft_notes`, `set_status_draft_date`
- [project_status_tab.py](../../components/alloq-project/src/alloq_project/components/project_status_tab.py): `_status_history`, `_history_row`, `_status_edit_form`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestStatusDraft.test_expand_status_loads_draft_and_toggles`, `test_save_updates_entity_and_local_list`, `test_save_missing_status_shows_error`, `test_save_with_invalid_date_shows_error`, `test_delete_status_removes_entry`; [test_project_state.py](../../components/alloq-project/tests/test_project_state.py) `TestProjectStateHandlers.test_delete_status_of_other_project_is_ignored`; [test_project_components.py](../../components/alloq-project/tests/test_project_components.py) `TestStatusTab.test_status_delete_requires_confirmation`

## PROJ-15 Earned value chart {#proj-15}

An earned value chart in the tab "Status" compares plan, progress and cost, and it shows two forecasts of the final cost.

As a project manager, I want to see the earned value and a cost forecast, so that I notice early when a project will cost more than its budget.

Project manager · Track project progress / Read the earned value chart · priority 1 · core · v0.2.0

The formulas are in [Calculations](../architecture/calculations.md#earned-value-and-forecast). The criteria below only describe what the user sees.

### Acceptance criteria

1. **Given** a project with status entries, **when** the tab "Status" renders, **then** the summary row shows "Budget", "Fertigstellungswert" [earned value], "Ist-Kosten" [actual cost], "Prognose linear" [linear forecast] and "Prognose additiv" [additive forecast] from the newest entry (`EVForecastService.build_summary`).
2. **Given** a status entry, **when** the forecasts are computed, **then** the linear and the additive forecast follow the formulas in Calculations. The linear forecast equals the budget when the earned value is 0 or less.
3. **Given** weekly allocations on the project, **when** the planned value curve is built, **then** it follows the planned person days and reaches the budget at the end date. Without allocations it grows in a straight line over the period.
4. **Given** allocations above a person's weekly capacity, **when** the planned value is built, **then** `_scale_allocations` cuts them to the capacity after holidays and part time. (no test)
5. **Given** a last status entry before the end date, **when** the chart is built, **then** the series "Prognose (linear)" and "Prognose (additiv)" run weekly from the last actual cost to their forecast at the end date, and they are empty before the last entry.
6. **Given** a project without start date, end date or budget, or with an end that is not after the start, **when** the tab renders, **then** the chart shows "Keine Statusdaten für das Diagramm vorhanden." [no status data for the chart].
7. **Given** two status entries on the same day, **when** the summary is built, **then** the entry created later wins.

### Evidence

- [forecast.py](../../components/alloq-project/src/alloq_project/services/forecast.py): `EVForecastService.build_chart_data`, `EVForecastService.build_summary`, `EVForecastService.compute_status_ev`, `EVForecastService.linear_eac`, `EVForecastService.additive_eac`, `_cumulative_pv`, `_scale_allocations`, `_status_order`, `EVSummary`
- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.ev_chart_data`, `ProjectState.ev_summary`, `ProjectState._persist_ev_summary`
- [project_status_tab.py](../../components/alloq-project/src/alloq_project/components/project_status_tab.py): `_ev_chart`, `_ev_summary`
- [project.py](../../components/alloq-commons/src/alloq_commons/entities/project.py): `ProjectEntity.ev_earned_value`, `ev_actual_cost`, `ev_eac_linear`, `ev_eac_additive`
- Tests: [test_forecast.py](../../components/alloq-project/tests/test_forecast.py) `TestBuildSummary.test_returns_last_status_values`, `test_eac_linear_formula`, `test_eac_additive_formula`, `test_same_day_newer_status_wins`, `test_zero_budget_returns_empty_summary`; `TestBuildChartDataWithCapacity.test_capacity_weighted_pv_at_status_date`, `test_capacity_pv_reaches_budget_at_end`, `test_fallback_to_linear_when_no_allocations`, `test_forecast_curve_present_after_last_status`, `test_forecast_lines_are_none_before_last_status`, `test_returns_empty_when_no_dates`; `TestCumulativePv.test_partial_week`; `TestComputeStatusEv.test_basic_ev_computation`

## PROJ-16 Record a risk {#proj-16}

The tab "Risiken" records the risks of a project with impact, probability, status and measures.

As a project manager, I want to record and update the risks of my project, so that the team and the dashboard know what can go wrong.

Project manager · Manage project risks / Record a risk · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** the button "Risiko hinzufügen" [add risk], **when** the user clicks it, **then** `add_project_risk` opens a blank draft with impact 3, probability 3 and the status "Offen" [open]. Nothing is stored yet.
2. **Given** the selects "Impact (1-5)" and "Probability (1-5)", **when** the user picks a value, **then** `_clamp_score` limits it to 1 to 5, and input that is not a number becomes 3. The labels of these two selects are English in the UI.
3. **Given** the select "Status", **when** it lists the mitigation states, **then** the labels are "Offen", "In Bearbeitung" [in progress] and "Geschlossen" [closed].
4. **Given** a new draft without a title, **when** the user clicks "Speichern", **then** `save_risk_draft` stores the risk as "Neues Risiko" [new risk] with the next number, reloads the risk cards on the dashboard and shows the toast "Risiko gespeichert." [risk saved].
5. **Given** an existing risk, **when** the user clicks it, edits the fields "Titel" [title], "Beschreibung" [description] or "Maßnahme" [measure] and saves, **then** the risk is updated and the toast "Risiko gespeichert." appears. A risk that no longer exists shows "Risiko nicht gefunden." [risk not found].
6. **Given** the delete icon of a risk, **when** the user confirms the dialog "Risiko löschen" [delete risk], **then** `delete_project_risk` removes it, numbers the remaining risks again from 1 and shows the toast "Risiko gelöscht." [risk deleted].

### Evidence

- [project_state.py](../../components/alloq-project/src/alloq_project/states/project_state.py): `ProjectState.save_risk_draft`, `ProjectState.delete_project_risk`, `ProjectState.update_project_risk`, `ProjectState._dashboard_risk_refresh_events`, `ProjectState._sync_selected_project_risk_count`, `_EDITABLE_RISK_FIELDS`
- [project_risk_draft_mixin.py](../../components/alloq-project/src/alloq_project/states/project_risk_draft_mixin.py): `ProjectRiskDraftMixin.add_project_risk`, `expand_risk`, `collapse_risk_edit`, `set_risk_draft_impact`, `set_risk_draft_probability`, `set_risk_draft_mitigation_status`, `sorted_risks`, `_clamp_score`, `_reset_risk_draft`
- [project_risk_tab.py](../../components/alloq-project/src/alloq_project/components/project_risk_tab.py): `risiken_tab`, `_risk_list`, `_risk_row`, `_risk_edit_form`, `_new_risk_form`
- [risk.py](../../components/alloq-commons/src/alloq_commons/entities/risk.py): `RiskEntity`, `RiskMitigationStatus`, `MITIGATION_STATUS_LABELS`
- [risk_repository.py](../../components/alloq-commons/src/alloq_commons/repositories/risk_repository.py): `RiskRepository.find_by_project_id`
- [project.py](../../components/alloq-commons/src/alloq_commons/models/project.py): `Risk`, `RiskCreate`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestRiskDraft.test_add_risk_opens_blank_draft`, `test_draft_setters_clamp_and_default`, `test_save_new_risk_appends_and_counts`, `test_save_existing_risk_updates_fields`, `test_save_missing_risk_shows_error`, `test_delete_risk_renumbers_remaining`; [test_project_components.py](../../components/alloq-project/tests/test_project_components.py) `TestRiskTab.test_risk_delete_requires_confirmation`, `test_risk_edit_form_is_keyed_by_draft_version`

### Open questions

- `ProjectState.update_project_risk` changes one field and limits scores to 1 to 5. `TestRiskDraft.test_update_risk_text_field_and_unknown_field` tests it, but no component calls it. Is it still needed?
- A new risk without a title is stored as "Neues Risiko", but an existing risk whose title is cleared is stored with an empty title. Should the edit use the same fallback?
- `RiskRepository.find_by_project_id` has no `ORDER BY`, and `select_project` numbers the risks in the order the database returns them. Can the numbers of the risks change between two openings of the drawer?
- The labels "Impact (1-5)" and "Probability (1-5)" are English, while the rest of the UI is German. Should they be "Auswirkung" and "Wahrscheinlichkeit"?

## PROJ-17 Risk matrix {#proj-17}

A 5 by 5 matrix places each risk by probability and impact and colours each cell by its score.

As a project manager, I want to see my risks in a risk matrix, so that I can tell at a glance which risks are the most serious.

Project manager · Manage project risks / Read the risk matrix · priority 1 · comfort · v0.2.0

### Acceptance criteria

1. **Given** project risks, **when** `risk_matrix_cells` builds the "Risikomatrix" [risk matrix], **then** it has 25 cells with probability 5 in the top row and impact 1 to 5 from left to right, and each cell lists the numbers of its risks.
2. **Given** a cell, **when** its score (probability times impact, 1 to 25) sets its colour, **then** `_risk_score_color` uses low up to 4, medium up to 9, high up to 15, very high up to 20 and critical above 20. (no test)
3. **Given** a stored impact outside 1 to 5, **when** the risk is read, **then** `Risk.compute_scores` limits the impact for the matrix and the score to 1 to 5. (no test)

### Evidence

- [project_risk_draft_mixin.py](../../components/alloq-project/src/alloq_project/states/project_risk_draft_mixin.py): `ProjectRiskDraftMixin.risk_matrix_cells`, `_risk_score_color`
- [project.py](../../components/alloq-commons/src/alloq_commons/models/project.py): `RiskMatrixCell`, `Risk.compute_scores`
- [project_risk_tab.py](../../components/alloq-project/src/alloq_project/components/project_risk_tab.py): `_risk_matrix`, `_matrix_cell`
- Tests: [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py) `TestRiskDraft.test_risk_matrix_places_risks_by_score`

### Open questions

- `Risk.compute_scores` limits the impact to 1 to 5 but not the probability. A stored probability outside 1 to 5 puts the risk in no matrix cell. Should the probability be limited too?
- The risk list colours the score badge with four steps (`_score_badge_color`: gray, yellow, orange, red), but the matrix uses five steps. Should both use the same steps?
