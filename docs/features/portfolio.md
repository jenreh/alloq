---
title: Portfolio overview
description: How admins and project managers check the health of all projects on the page "Übersicht" at /dashboard, with the scope switch, the chart of time and progress, the risk grid and the side drawer.
story_ids: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07]
source_paths:
  - app/app.py
  - app/components/sidebar.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-dashboard/src/alloq_dashboard/pages.py
  - components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py
  - components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py
  - components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py
  - components/alloq-dashboard/src/alloq_dashboard/components/dashboard_grid.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_bubbles.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_risks.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_drawer.py
  - components/alloq-dashboard/src/alloq_dashboard/components/portfolio_shared.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Portfolio overview

This page covers how admins and project managers check the health of all projects in one place. The stories belong to the activity "Watch the portfolio" on the [story map](./story-map.md).

The page has one user task, **Check project health**, with these sub-tasks:

- **Open the overview.** Open the page, see when it is still loading or failed, and switch between the whole department and your direct reports.
- **Check schedule and budget.** Read the chart of time passed against progress, and open one project in the side drawer.
- **Review open risks.** Read the grid of open risks by probability and impact, and list the risks of one cell.

Since v2.0.4 the page "Übersicht" [overview] at `/dashboard` shows only the portfolio. It has four cards, a side drawer on the right and the scope switch "Ganze Abteilung" [whole department] / "Direkt unterstellt" [direct reports] in the toolbar. This page describes the cards "Projekte: Zeit und Fortschritt" and "Offene Risiken". The cards "Kritischer Ressourcenpfad" and "Kapazität je Rolle", the buffer per role and the role and person drawers are on [Portfolio staffing and capacity](./portfolio-capacity.md).

The older KPI cards and their drill-down drawer are still in the code, but no page shows them. They are listed under [Not covered](./story-map.md#not-covered) on the story map.

`PortfolioState.load` reads everything in one database session (`load_inputs`) and builds the payload with the pure function `build_portfolio`. The formulas for the earned value, the EAC (estimate at completion, the expected total cost), the bubbles and the risk matrix are in [calculations](../architecture/calculations.md#other-portfolio-numbers) and [earned value and forecast](../architecture/calculations.md#earned-value-and-forecast).

## DASH-01 Open the portfolio overview {#dash-01}

Admins and project managers open the portfolio overview at `/dashboard`. Employees see a message that they lack the rights.

As a project manager, I want to open one overview page for the whole portfolio, so that I can see how projects, risks and capacity stand without opening each project.

Project manager · Check project health / Open the overview · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** a signed-in admin or project manager, **when** the user opens `/dashboard`, **then** the page "Übersicht" runs `PortfolioState.load` on load and shows the four cards "Projekte: Zeit und Fortschritt", "Offene Risiken", "Kritischer Ressourcenpfad" and "Kapazität je Rolle", and the portfolio drawer.
2. **Given** a signed-in user with only the role employee, **when** the user opens `/dashboard`, **then** `editor_only` shows the text "Sie haben nicht die notwendigen Berechtigungen, um auf diese Seite zuzugreifen." [you do not have the rights to open this page] instead of the cards.
3. **Given** a user who is neither admin nor project manager, **when** the browser sends the event `PortfolioState.load` anyway, **then** the server loads no portfolio data, because the handler has `@requires_editor`.
4. **Given** a user without editor rights, **when** the sidebar is drawn, **then** the entry "Übersicht" for `/dashboard` is hidden, because only `/plan` and `/projects` are in `VIEWER_ROUTES`.
5. **Given** a signed-in user, **when** the toolbar is drawn, **then** it greets the user with "Willkommen zurück, &lt;name&gt;!" [welcome back], or with "Willkommen zurück!" when the user has no name.

### Evidence

- [pages.py](../../components/alloq-dashboard/src/alloq_dashboard/pages.py): `create_dashboard_page` (`on_load`, `editor_only`, `no_access`), `_greeting`
- [app.py](../../app/app.py): `create_dashboard_page(sidebar(), route="/dashboard")`. The planning page is registered at `/`.
- [access.py](../../components/alloq-commons/src/alloq_commons/access.py): `editor_only`, `no_access`, `NO_ACCESS_MSG`, `requires_editor`, `can_edit`
- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.load`
- [dashboard_grid.py](../../components/alloq-dashboard/src/alloq_dashboard/components/dashboard_grid.py): `dashboard_grid`
- [sidebar.py](../../app/components/sidebar.py): `PLANNING_ITEMS`, `_guarded_nav_item`, `VIEWER_ROUTES`
- Tests: [test_components.py](../../components/alloq-dashboard/tests/test_components.py) `test_dashboard_grid_renders_the_four_portfolio_cards`, `test_greeting_uses_authenticated_user_name`; [test_access.py](../../components/alloq-commons/tests/test_access.py) `TestRenderGuards.test_no_access_explains_the_missing_rights`; [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_load_is_refused_for_non_admins`; [test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarComponent.test_employees_see_only_planning_and_projects`

## DASH-02 Placeholders and load error {#dash-02}

While the portfolio loads, each card shows a placeholder. If the load fails, the page shows one short error message.

As a project manager, I want to see when the overview is still loading or could not load, so that I do not read empty cards as real numbers.

Project manager · Check project health / Open the overview · priority 2 · core · v2.0.4

### Acceptance criteria

1. **Given** the open overview, **when** `PortfolioState.load` starts, **then** it sets `is_loading` to true and clears the old error message before it fetches the data. While `is_loading` is true, each card shows three grey skeleton lines instead of its content.
2. **Given** that the database or the calculation raises an error, **when** `PortfolioState.load` runs, **then** `error_message` is "Daten konnten nicht geladen werden." [data could not be loaded], `is_loading` goes back to false, and the page shows this text in a red alert above the cards.
3. **Given** a load, **when** `load_inputs` reads the data, **then** it reads up to 1000 projects and up to 1000 employees (`MAX_ROWS`), all roles ordered by name, all risks with the mitigation status "open", and the public holidays from the Monday of this week for 52 weeks (`LOOKAHEAD_WEEKS`).

### Evidence

- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.load`, `LOAD_ERROR_MESSAGE`
- [portfolio_shared.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_shared.py): `card` (skeleton while `is_loading`)
- [dashboard_grid.py](../../components/alloq-dashboard/src/alloq_dashboard/components/dashboard_grid.py): `_notices`, `dashboard_grid`
- [portfolio_inputs.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py): `load_inputs`, `MAX_ROWS`, `LOOKAHEAD_WEEKS`
- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `load_portfolio`
- Tests: [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_load_stores_payload_for_scope_and_email`, `test_load_failure_shows_message`; [test_components.py](../../components/alloq-dashboard/tests/test_components.py) `test_dashboard_grid_renders_the_four_portfolio_cards`; [test_portfolio_inputs.py](../../components/alloq-dashboard/tests/test_portfolio_inputs.py) `test_load_inputs_reads_everything_in_one_session`

### Open questions

- `MAX_ROWS` limits the load to 1000 projects and 1000 employees. Nothing tells the user when more rows exist.
- The overview does not reload by itself after a risk or a booking changes. It reloads only on page load and on a scope change.

## DASH-03 Department or my scope {#dash-03}

A switch in the toolbar shows either the whole department or only the people and projects of the signed-in manager.

As a project manager, I want to switch between the whole department and my direct reports, so that I can focus on the people and projects I am responsible for.

Project manager · Check project health / Open the overview · priority 3 · comfort · v2.0.4

### Acceptance criteria

1. **Given** the open overview, **when** the user looks at the toolbar, **then** a segmented control offers "Ganze Abteilung" and "Direkt unterstellt", and "Ganze Abteilung" is selected at first. The control has the screen reader label "Bereich" [scope].
2. **Given** the scope "Ganze Abteilung", **when** the user picks "Direkt unterstellt", **then** `set_scope` stores the new scope, closes any open drawer and loads the portfolio again. Picking the same scope or an unknown value does nothing.
3. **Given** the scope "Direkt unterstellt" and a signed-in user whose email belongs to an employee, **when** the portfolio is built, **then** `apply_scope` keeps only the employees whose manager is that employee and only the projects that this employee owns. The manager is not in the list of people.
4. **Given** the scope "Direkt unterstellt" and no employee for the signed-in email, **when** the portfolio is built, **then** the scope is empty and a blue notice says "Zu Ihrer Anmeldung gibt es kein Mitarbeiterprofil. Der Bereich „Direkt unterstellt“ bleibt deshalb leer." [there is no employee profile for your sign-in, so the scope stays empty].
5. **Given** the scope "Direkt unterstellt", a known employee, no direct reports and no owned projects, **when** the portfolio is built, **then** a blue notice says "Ihnen ist niemand direkt unterstellt, und Sie verantworten keine Projekte." [nobody reports to you directly and you own no projects].
6. **Given** the scope "Direkt unterstellt", **when** a direct report is also booked on a project outside the scope, **then** that booking still uses up the person's time, because `Capacity` counts the bookings on all projects that are not "Abgeschlossen" [completed].

### Evidence

- [dashboard_grid.py](../../components/alloq-dashboard/src/alloq_dashboard/components/dashboard_grid.py): `scope_control`, `SCOPE_OPTIONS`, `_notices`
- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.scope`, `PortfolioState.set_scope`
- [portfolio_inputs.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py): `SCOPE_DEPARTMENT`, `SCOPE_TEAM`, `SCOPES`, `apply_scope`, `team_employee_ids`, `booking_projects`, `load_inputs` (`employee_repo.find_by_email`)
- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `build_portfolio`, `_notice`, `NO_PROFILE_NOTICE`, `EMPTY_TEAM_NOTICE`
- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `Capacity.__init__`
- Tests: [test_components.py](../../components/alloq-dashboard/tests/test_components.py) `test_scope_control_switches_scope`; [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_set_scope_reloads_only_on_change`; [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_team_scope_keeps_direct_reports_and_owned_projects`, `test_build_portfolio_notices_and_unknown_scope`, `test_build_portfolio_for_direct_reports`

### Open questions

- `PortfolioKpi` has `department_employee_count` and `team_employee_count`, but no component shows them.
- In the scope "Direkt unterstellt" the manager is not in the list of people. Confirm that this is intended.

## DASH-04 Schedule and budget chart {#dash-04}

A chart places each running project by time passed and progress. The size shows the budget, and the color shows the cost forecast against the budget.

As a project manager, I want to see all running projects in one chart of time passed against progress, so that I can spot projects that are behind plan or over budget.

Project manager · Check project health / Check schedule and budget · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** projects in scope with the states "Aktiv" [active], "Risiko" [at risk], "Geplant" [planned] and "Abgeschlossen", **when** the card "Projekte: Zeit und Fortschritt" [projects: time and progress] is drawn, **then** only "Aktiv" and "Risiko" projects get a bubble. A line under the chart names the rest, e.g. "Nicht im Diagramm: 1 geplantes Projekt (AQ-118) und 1 abgeschlossenes." [not in the chart: 1 planned project and 1 completed].
2. **Given** a plotted project, **when** its bubble is placed, **then** the horizontal position is the time passed between start and end date in percent, limited to 0 to 100, or 100 when the end is not after the start. The vertical position is the progress of the newest status report. A dashed diagonal splits the chart into "vor dem Plan" [ahead of plan] and "hinter dem Plan" [behind plan].
3. **Given** plotted projects with budgets, **when** the bubble size is computed, **then** the diameter is 18 px plus 42 px times the square root of the budget divided by the largest plotted budget, rounded to whole pixels.
4. **Given** a project with an EAC and a budget, **when** the bubble color is chosen, **then** `health` gives green when the EAC is at most the budget, yellow when it is at most 10 % over, red above that, and no color (grey) when the EAC or the budget is 0. The legend reads "im Budget" [within budget], "bis 10 % über" [up to 10 % over] and "über 10 %" [over 10 %].
5. **Given** a project, **when** `_latest_eac` reads its EAC, **then** it takes `ev_eac_additive` of the project. Without it, it takes `eac_additive`, then `eac_linear` of the newest status report. Without both, it divides the spent cost by the progress, where the spent cost is `actual_cost` or else the budget times `budget_spent` percent. Without spent cost or progress the EAC is 0.
6. **Given** a plotted project whose weakest role has a buffer below 0 weeks, **when** its bubble is drawn, **then** the bubble gets a dashed red ring, shown in the legend as "Puffer unter 0" [buffer below 0]. The buffer is explained on [Portfolio staffing and capacity](./portfolio-capacity.md).
7. **Given** a plotted project, **when** the user points at its bubble, **then** a tooltip shows "&lt;code&gt; &lt;name&gt;: &lt;x&gt; % Zeit, &lt;y&gt; % Fortschritt, Budget &lt;budget&gt; €", with a dot as the thousands separator, e.g. "Budget 720.000 €". A click on the bubble opens the project drawer ([DASH-05](#dash-05)).
8. **Given** no project in scope is "Aktiv" or "Risiko", **when** the card is drawn, **then** it shows "Keine aktiven Projekte. Geplante Projekte erscheinen, sobald sie starten." [no active projects, planned projects appear once they start]. (no test)
9. **Given** a bubble with more than 85 % time passed, **when** its code label is placed, **then** the label moves to the left side of the bubble so that it stays inside the chart.

### Evidence

- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `bubbles`, `elapsed_percent`, `health`, `not_plotted_label`, `_thousands`, `_PLOTTED_STATES`, `YELLOW_OVERRUN_RATIO`, `BUBBLE_MIN_PX`, `BUBBLE_GROWTH_PX`, `LABEL_FLIP_PERCENT`
- [portfolio_inputs.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py): `project_to_input`, `_latest_eac`
- [portfolio_bubbles.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_bubbles.py): `portfolio_bubbles_card`, `_plot`, `_zones`, `_bubble`, `_legend`, `_health`
- Tests: [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_build_portfolio_for_the_department`, `test_health_and_elapsed`, `test_bubble_label_flips_near_the_right_edge`; [test_portfolio_inputs.py](../../components/alloq-dashboard/tests/test_portfolio_inputs.py) `test_project_eac_fallbacks`

### Open questions

- Progress comes from the newest status report. A project without any status report is placed at 0 % progress.

## DASH-05 Project side panel {#dash-05}

A click on a project opens a side drawer with its key facts and the buffer of each role it needs.

As a project manager, I want to open one project from the overview and see its facts and staffing buffer per role, so that I understand why it is late or at risk.

Project manager · Check project health / Check schedule and budget · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** the loaded overview, **when** the user clicks a bubble, a project in the card "Kritischer Ressourcenpfad" or a project in a role or person drawer, **then** `PortfolioState.open_project` stores the project id and opens the drawer. The drawer title is the project code and name.
2. **Given** the open project drawer, **when** the facts are shown, **then** it lists "Status", "Fortschritt" [progress], "Zeit verstrichen" [time passed], "Ende" [end] as dd.mm.yyyy, "Budget" and "EAC". The EAC shows the difference to the budget in percent in brackets, or "Keine Prognose" [no forecast] when the EAC is 0.
3. **Given** a project with required capacity per role, **when** the section "Rollen und Puffer" [roles and buffer] is shown, **then** each role, sorted by name, shows a buffer badge in weeks ("&lt;n&gt; W"), "Rest" [remaining], "geplant" [planned] and "Lücke" [gap] in person-days (PT), the person to look at and the reason. The role name and the person open the role and person drawers on [Portfolio staffing and capacity](./portfolio-capacity.md).
4. **Given** a project without required capacity per role, **when** the drawer is open, **then** it shows "Für dieses Projekt ist kein Bedarf je Rolle erfasst." [no demand per role is recorded for this project].
5. **Given** an open drawer, **when** the user clicks the close button or outside the drawer, **then** `PortfolioState.close_drawer` clears the drawer and it closes.

### Evidence

- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.open_project`, `PortfolioState.close_drawer`, `PortfolioState.selected_project`, `DRAWER_PROJECT`
- [portfolio_drawer.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_drawer.py): `portfolio_drawer`, `_title`, `_project_body`, `_facts`, `_role_line`
- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `_project` (`end_label`, `eac_delta_percent`)
- [resource_path.py](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py): `analyse_projects`
- Tests: [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_drawer_selection_and_computed_vars`; [test_components.py](../../components/alloq-dashboard/tests/test_components.py) `test_portfolio_drawer_shows_project_and_risks`; [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_build_portfolio_for_the_department`, `test_projects_without_required_capacity_have_no_lines`

## DASH-06 Risk grid {#dash-06}

A 5 by 5 grid counts the open risks of the projects in scope by probability and impact.

As a project manager, I want to see all open risks in a probability and impact grid, so that I can see at once how many serious risks the portfolio carries.

Project manager · Check project health / Review open risks · priority 1 · core · v2.0.4

### Acceptance criteria

1. **Given** risks of projects in scope, **when** the card "Offene Risiken" [open risks] is built, **then** only risks with the mitigation status "open" count. Each risk counts in the cell of its probability (rows 5 down to 1) and impact (columns 1 to 5).
2. **Given** a risk with a probability or impact outside 1 to 5, **when** it is read, **then** `risk_to_input` cuts the value to 1 to 5.
3. **Given** a grid cell, **when** its color is chosen, **then** the score, probability times impact, sets one of five bands: up to 4, up to 9, up to 15, up to 19, and above 19.
4. **Given** open risks in scope, **when** the counts beside the grid are shown, **then** "Hoch, Score über 15" [high, score above 15], "Mittel, 5 bis 15" [medium, 5 to 15] and "Niedrig, bis 4" [low, up to 4] count the risks by score. The header shows "&lt;n&gt; offen" [n open].
5. **Given** a cell with no risks, **when** the grid is drawn, **then** the cell shows no number and is disabled, so it cannot be clicked. (no test)
6. **Given** no open risk in scope, **when** the card is drawn, **then** it shows "Keine offenen Risiken." [no open risks]. (no test)

### Evidence

- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `build_portfolio` (open risks, `risk_high`, `risk_medium`, `risk_low`, `risk_open_total`), `risk_matrix`, `risk_band`, `severity`, `MATRIX_SIZE`, `SEVERITY_LOW_MAX`, `SEVERITY_MEDIUM_MAX`, `_BANDS`
- [portfolio_inputs.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py): `risk_to_input`, `clamp`, `load_inputs` (`risk_repo.find_open_by_min_score`, `min_score=0`)
- [portfolio_risks.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_risks.py): `portfolio_risks_card`, `_matrix`, `_cell`, `_severity`, `_band_color`
- Tests: [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_build_portfolio_for_the_department`, `test_risk_bands_and_severity`; [test_portfolio_inputs.py](../../components/alloq-dashboard/tests/test_portfolio_inputs.py) `test_employee_and_risk_mapping`

### Open questions

- Open risks of projects in the state "Abgeschlossen" still count in the grid, because `build_portfolio` filters risks by the projects in scope and not by the project state. Confirm that this is intended.

## DASH-07 Risks in a grid cell {#dash-07}

A click on a cell of the risk grid lists the risks in that cell.

As a project manager, I want to click a cell of the risk grid and see its risks, so that I know which projects carry them.

Project manager · Check project health / Review open risks · priority 2 · comfort · v2.0.4

### Acceptance criteria

1. **Given** a cell with at least one risk, **when** the user clicks it, **then** `PortfolioState.open_risk_cell` stores the cell key "&lt;probability&gt;-&lt;impact&gt;" and opens the drawer with the title "Wahrscheinlichkeit &lt;p&gt;, Auswirkung &lt;i&gt;" [probability, impact].
2. **Given** the open risk drawer, **when** the list is shown, **then** it shows only the risks of that cell. Each risk shows its name, the project code and name, and a badge "Score &lt;n&gt;", red for high, yellow for medium and grey for low.
3. **Given** several open risks, **when** the risk list is built, **then** `risk_items` sorts the risks by score from high to low, then by project code, then by name.
4. **Given** a cell key with no matching risks, **when** the drawer is shown, **then** it shows "Keine Risiken in diesem Feld." [no risks in this cell]. (no test)

### Evidence

- [portfolio_state.py](../../components/alloq-dashboard/src/alloq_dashboard/states/portfolio_state.py): `PortfolioState.open_risk_cell`, `PortfolioState.cell_risks`, `PortfolioState.cell_title`, `DRAWER_RISKS`
- [portfolio_drawer.py](../../components/alloq-dashboard/src/alloq_dashboard/components/portfolio_drawer.py): `_risks_body`, `_risk`
- [portfolio.py](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio.py): `risk_items`
- Tests: [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) `test_drawer_selection_and_computed_vars`; [test_components.py](../../components/alloq-dashboard/tests/test_components.py) `test_portfolio_drawer_shows_project_and_risks`; [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py) `test_build_portfolio_for_the_department`

### Open questions

- The risk drawer does not link to the project or to the risk itself.
