---
title: Glossary
description: The domain terms of Alloq with their meaning and code location, and the German UI labels with their English meaning and the page where they appear.
source_paths:
  - components/alloq-commons/src/alloq_commons/entities/
  - components/alloq-commons/src/alloq_commons/services/utilization.py
  - components/alloq-commons/src/alloq_commons/services/daily_rate_pricing.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-commons/src/alloq_commons/roles.py
  - components/alloq-commons/src/alloq_commons/components/
  - components/alloq-project/src/alloq_project/services/
  - components/alloq-project/src/alloq_project/components/
  - components/alloq-project/src/alloq_project/states/
  - components/alloq-team/src/alloq_team/components/
  - components/alloq-team/src/alloq_team/states/team_list_state.py
  - components/alloq-dashboard/src/alloq_dashboard/services/
  - components/alloq-dashboard/src/alloq_dashboard/components/
  - app/components/sidebar.py
  - app/pages/
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Glossary

The Alloq user interface is in German. The code, the comments and these docs are in
English. This page maps the two languages. The first table explains the domain
terms you meet in the code. The tables after it list the German labels that users
see, with their English meaning.

German labels are quoted exactly as they are in the code. Each table is sorted
alphabetically.

## Domain terms

| Term | Meaning | Where in code | Where explained |
| --- | --- | --- | --- |
| Absence | A date range in which an employee is not available. The entity has no type field, so the code does not tell vacation from sickness. | [`absence.py`](../../components/alloq-commons/src/alloq_commons/entities/absence.py) `AbsenceEntity` | [data model](../architecture/data-model.md#absenceentity), [TEAM-12](../features/absences.md#team-12) |
| Access level | The right of a signed-in user. There are three levels: admin, editor and viewer. | [`access.py`](../../components/alloq-commons/src/alloq_commons/access.py) `can_edit`, `can_view` | [security](../architecture/security-and-access.md#access-levels), [AUTH-08](../features/users-and-access.md#auth-08) |
| Actual cost (AC) | The budget times the spent budget percent of a status report. | [`forecast.py`](../../components/alloq-project/src/alloq_project/services/forecast.py) `EVForecastService` | [calculations](../architecture/calculations.md#earned-value-and-forecast) |
| Admin | A user with the appkit admin switch. An admin may do everything, including the administration pages. | [`access.py`](../../components/alloq-commons/src/alloq_commons/access.py) `IS_ADMIN`; `requires_admin` from appkit_user | [security](../architecture/security-and-access.md#guard-decorators) |
| Allocation | The person days of one employee on one project in one role for one week. The planning grid reads and writes allocations. | [`capacity_allocation.py`](../../components/alloq-commons/src/alloq_commons/entities/capacity_allocation.py) `CapacityAllocationEntity` | [data model](../architecture/data-model.md#capacityallocationentity), [PLAN-01](../features/planning-grid.md#plan-01) |
| Available days | The work days of a week minus internal days and absence days, at least 0. | [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) `UtilizationService` | [calculations](../architecture/calculations.md#capacity-of-one-person-in-one-week) |
| Budget (BAC) | The total budget of a project in euros. Earned value and forecasts are based on it. | [`project.py`](../../components/alloq-commons/src/alloq_commons/entities/project.py) `ProjectEntity.budget` | [calculations](../architecture/calculations.md#earned-value-and-forecast) |
| Buffer | The number of weeks between the project end and the cover week of a role. A negative buffer means the role is staffed too late. | [`resource_path.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py) `_role_line`, `buffer_tone` | [calculations](../architecture/calculations.md#buffer-of-one-role-in-one-project), [DASH-09](../features/portfolio-capacity.md#dash-09) |
| Capacity | An assignment of an employee to a project in one role for a date range, with hours per week. It is a different table from the weekly allocation. | [`capacity.py`](../../components/alloq-commons/src/alloq_commons/entities/capacity.py) `CapacityEntity` | [data model](../architecture/data-model.md#capacityentity), [PROJ-18](../features/staffing.md#proj-18) |
| Contribution margin (DB) | The share of the selling price that is left after the production cost. The price is the cost divided by 1 minus the margin, rounded up to 10 euros. | [`daily_rate_pricing.py`](../../components/alloq-commons/src/alloq_commons/services/daily_rate_pricing.py) `price_for_margin`; `DailyRateSettingsEntity.contribution_margin_percent` | [ADM-07](../features/master-data.md#adm-07) |
| Cover week | The week in which the remaining demand of a project role is covered, by planned days or by free role capacity. | [`resource_path.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py) `_planned_cover`, `_consume`, `cover_index` | [calculations](../architecture/calculations.md#buffer-of-one-role-in-one-project) |
| Coverage | On the absence timeline, the smallest number of people present on a work day of a week, compared with the team size. | [`planning_gantt.py`](../../components/alloq-project/src/alloq_project/services/planning_gantt.py) `_coverage`, `_bottleneck` | [PLAN-24](../features/absences.md#plan-24) |
| Daily rate | The production cost and the list price of one role per day. An empty price means it is not set. | [`daily_rate.py`](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py) `DailyRateEntity` | [data model](../architecture/data-model.md#dailyrateentity), [ADM-05](../features/master-data.md#adm-05) |
| Department | An organizational unit of employees. Each department also has a permission role `department_<id>`, which gives no access in the code. | [`department.py`](../../components/alloq-commons/src/alloq_commons/entities/department.py) `DepartmentEntity`; [`roles.py`](../../components/alloq-commons/src/alloq_commons/roles.py) `department_roles` | [data model](../architecture/data-model.md#departmententity), [ADM-08](../features/master-data.md#adm-08) |
| Direct reports | The employees whose `manager_id` points to an employee. | [`employee.py`](../../components/alloq-commons/src/alloq_commons/entities/employee.py) `EmployeeEntity.manager`, `direct_reports` | [TEAM-03](../features/team.md#team-03) |
| EAC | Estimate at completion, the forecast of the total cost. The linear EAC is budget times AC divided by EV. The additive EAC is budget plus AC minus EV. | [`forecast.py`](../../components/alloq-project/src/alloq_project/services/forecast.py) `EVForecastService`; `ProjectEntity.ev_eac_linear`, `ev_eac_additive` | [calculations](../architecture/calculations.md#earned-value-and-forecast), [PROJ-15](../features/project-tracking.md#proj-15) |
| Earned value (EV) | The budget times the progress percent of a status report. | [`forecast.py`](../../components/alloq-project/src/alloq_project/services/forecast.py) `compute_status_ev`; `ProjectEntity.ev_earned_value` | [calculations](../architecture/calculations.md#earned-value-and-forecast) |
| Editor | Admins and users with the role `project_manager`. Editors may read and change dashboard, planning, projects and team. | [`access.py`](../../components/alloq-commons/src/alloq_commons/access.py) `CAN_EDIT`, `requires_editor`, `editor_only` | [security](../architecture/security-and-access.md#guard-decorators), [AUTH-09](../features/users-and-access.md#auth-09) |
| Employee | A team member who can be planned. The same word is also the name of the read only permission role `employee`. | [`employee.py`](../../components/alloq-commons/src/alloq_commons/entities/employee.py) `EmployeeEntity`; [`roles.py`](../../components/alloq-commons/src/alloq_commons/roles.py) `EMPLOYEE_ROLE` | [data model](../architecture/data-model.md#employeeentity) |
| Free capacity per role | The free person days of all people with a role in the coming weeks. The sidebar and the portfolio show it. | [`aggregation.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/aggregation.py) `load_free_capacity`; [`resource_path.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py) `Capacity` | [calculations](../architecture/calculations.md#free-capacity-per-role), [DASH-15](../features/portfolio-capacity.md#dash-15) |
| Free days | Work days minus project days, internal days and absence days in one week. The value is not cut at 0, so a negative value means overbooked. | [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) `compute_employee_gesamt`, `gesamt_bucket` | [calculations](../architecture/calculations.md#free-days-in-the-planning-grid), [PLAN-04](../features/planning-grid.md#plan-04), [DASH-14](../features/planning-grid.md#dash-14) |
| GTK | The unit of the weekly cap in the plan wizard. The cap counts one GTK as 5 person days per week. The code does not spell out the abbreviation. | [`project_plan_state.py`](../../components/alloq-project/src/alloq_project/states/project_plan_state.py) `gtk_count`; [`plan_distribution.py`](../../components/alloq-project/src/alloq_project/services/plan_distribution.py) `default_gtk` | [calculations](../architecture/calculations.md#plan-distribution-in-the-plan-modal), [PLAN-20](../features/staffing.md#plan-20) |
| Horizon | The 13 weeks from the current week that the portfolio looks at. | [`resource_path.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py) `HORIZON_WEEKS` | [calculations](../architecture/calculations.md#other-portfolio-numbers) |
| Internal hours | The hours per week an employee spends on internal work. They are turned into internal days with 8 hours per day. The default is 4. | [`employee.py`](../../components/alloq-commons/src/alloq_commons/entities/employee.py) `internal_hours`; [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) `cap_internal_days` | [calculations](../architecture/calculations.md#capacity-of-one-person-in-one-week) |
| Internal project | A project with `is_internal` set. The project list shows it in its own group. | [`project.py`](../../components/alloq-commons/src/alloq_commons/entities/project.py) `ProjectEntity.is_internal` | [data model](../architecture/data-model.md#projectentity), [PROJ-02](../features/projects.md#proj-02) |
| Key role | The main role of an employee. It is required and is always the first role in the role list. | [`employee.py`](../../components/alloq-commons/src/alloq_commons/entities/employee.py) `key_role_id`; [`team_state.py`](../../components/alloq-team/src/alloq_team/states/team_state.py) `validate_key_role_id` | [data model](../architecture/data-model.md#employeeentity), [TEAM-08](../features/team.md#team-08) |
| List price | The price of a role that customers see. It is calculated with the regular margin unless someone enters a manual list price. | [`daily_rate.py`](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py) `DailyRateEntity.list_price` | [ADM-06](../features/master-data.md#adm-06) |
| Minimum margin (Mindest-DB) | The contribution margin used for the recommended sales price. The default is 30 percent, and it may not be above the regular margin. | [`daily_rate.py`](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py) `min_contribution_margin_percent`, `DEFAULT_MIN_CONTRIBUTION_MARGIN_PERCENT` | [ADM-07](../features/master-data.md#adm-07) |
| Person day (PT) | The unit of all planning numbers, from the German "Personentag". A week has 5 work days and is keyed by its Monday. | [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) `WORK_DAYS_PER_WEEK`, `HOURS_PER_DAY` | [calculations](../architecture/calculations.md) |
| Production cost | The cost of one day of a role. The prices are calculated from it. | [`daily_rate.py`](../../components/alloq-commons/src/alloq_commons/entities/daily_rate.py) `DailyRateEntity.production_cost` | [ADM-05](../features/master-data.md#adm-05) |
| Project manager | The permission role `project_manager`. It gives editor rights without the administration pages. | [`roles.py`](../../components/alloq-commons/src/alloq_commons/roles.py) `PROJECT_MANAGER_ROLE` | [security](../architecture/security-and-access.md#access-levels) |
| Project owner | An employee who is responsible for a project. "Meine" filters and the scope "Direkt unterstellt" use the owners. | [`project.py`](../../components/alloq-commons/src/alloq_commons/entities/project.py) `ProjectEntity.owners`, `project_owners_m2m` | [data model](../architecture/data-model.md#projectentity), [DASH-03](../features/portfolio.md#dash-03) |
| Project state | The state of a project. The values are "Geplant", "Aktiv", "Risiko" and "Abgeschlossen". | [`project.py`](../../components/alloq-commons/src/alloq_commons/entities/project.py) `ProjectStateEnum` | [PROJ-10](../features/project-tracking.md#proj-10) |
| Public holiday | A holiday that lowers the work days of a week. A recurring holiday is stored once and repeated every year. | [`public_holiday.py`](../../components/alloq-commons/src/alloq_commons/entities/public_holiday.py) `PublicHolidayEntity` | [data model](../architecture/data-model.md#publicholidayentity), [ADM-12](../features/master-data.md#adm-12) |
| Ramp-up, ramp-down | The number of weeks at the start and the end of a plan in which the weekly person days rise or fall. On a role, the flags say that the role is needed in full from the start or until the end. | [`plan_distribution.py`](../../components/alloq-project/src/alloq_project/services/plan_distribution.py) `distribute`; [`role.py`](../../components/alloq-commons/src/alloq_commons/entities/role.py) `RoleEntity.ramp_up`, `ramp_down` | [calculations](../architecture/calculations.md#plan-distribution-in-the-plan-modal), [PLAN-20](../features/staffing.md#plan-20) |
| Recommended sales price | The price of a role calculated with the minimum margin. It is always calculated and cannot be entered. | [`daily_rate_pricing.py`](../../components/alloq-commons/src/alloq_commons/services/daily_rate_pricing.py) `price_for_margin` | [ADM-05](../features/master-data.md#adm-05) |
| Required capacity | The total person days of one role that a project needs. | [`required_capacity.py`](../../components/alloq-commons/src/alloq_commons/entities/required_capacity.py) `RequiredCapacityEntity` | [data model](../architecture/data-model.md#requiredcapacityentity), [PROJ-08](../features/projects.md#proj-08) |
| Risk score | Probability times impact, both from 1 to 5. The portfolio calls a score up to 4 low, up to 15 medium and above 15 high. | [`risk.py`](../../components/alloq-commons/src/alloq_commons/entities/risk.py) `RiskEntity`, `HIGH_RISK_SCORE_THRESHOLD` | [calculations](../architecture/calculations.md#other-portfolio-numbers), [PROJ-17](../features/project-tracking.md#proj-17) |
| Risk status | The mitigation state of a risk. The values are `open`, `mitigated` and `resolved`. | [`risk.py`](../../components/alloq-commons/src/alloq_commons/entities/risk.py) `RiskMitigationStatus`, `MITIGATION_STATUS_LABELS` | [PROJ-16](../features/project-tracking.md#proj-16) |
| Role | A job role that people fill and projects need, e.g. a data scientist. It is not a permission role. | [`role.py`](../../components/alloq-commons/src/alloq_commons/entities/role.py) `RoleEntity` | [data model](../architecture/data-model.md#roleentity), [ADM-03](../features/master-data.md#adm-03) |
| Scope | The part of the portfolio that is shown. `department` shows everything, and `team` shows direct reports and owned projects. | [`portfolio_inputs.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/portfolio_inputs.py) `apply_scope`, `SCOPE_DEPARTMENT`, `SCOPE_TEAM` | [calculations](../architecture/calculations.md#portfolio-buffer), [DASH-03](../features/portfolio.md#dash-03) |
| Seniority | The level of an employee. The values are "Advanced", "Senior", "Professional" and "Expert". | [`employee.py`](../../components/alloq-commons/src/alloq_commons/entities/employee.py) `SeniorityLevel` | [data model](../architecture/data-model.md#employeeentity) |
| Status report | A dated entry with the progress and the spent budget of a project, both in percent. | [`status.py`](../../components/alloq-commons/src/alloq_commons/entities/status.py) `ProjectStatusEntity` | [data model](../architecture/data-model.md#projectstatusentity), [PROJ-13](../features/project-tracking.md#proj-13) |
| Utilization | The project days of a person in a week as a percent of the available days. The buckets are `low`, `mid`, `high` and `over`. | [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) `compute_employee_heat`, `heat_bucket` | [calculations](../architecture/calculations.md#percent-per-person-and-week), [TEAM-02](../features/team.md#team-02) |
| Viewer | Editors and users with the role `employee`. Viewers may read the projects page and the resource planning. | [`access.py`](../../components/alloq-commons/src/alloq_commons/access.py) `CAN_VIEW`, `requires_viewer`, `viewer_only` | [security](../architecture/security-and-access.md#guard-decorators), [AUTH-10](../features/users-and-access.md#auth-10) |
| Walking skeleton | The smallest set of stories that gives a working path from sign in to the load of a person. It is a term of the story map and does not appear in the code. | none | [story map](../features/story-map.md#walking-skeleton) |
| Weakest role | The role line of a project with the smallest buffer. The portfolio shows its buffer and its reason. | [`resource_path.py`](../../components/alloq-dashboard/src/alloq_dashboard/services/resource_path.py) `weakest`, `_explain` | [calculations](../architecture/calculations.md#weakest-role-and-reason), [DASH-10](../features/portfolio-capacity.md#dash-10) |
| Work days | The 5 days from Monday to Friday minus public holidays, scaled by the workload. | [`utilization.py`](../../components/alloq-commons/src/alloq_commons/services/utilization.py) `work_days_for_week`, `apply_workload` | [calculations](../architecture/calculations.md#capacity-of-one-person-in-one-week) |
| Workload | The weekly hours of an employee as a percent of 40 hours. | [`models/employee.py`](../../components/alloq-commons/src/alloq_commons/models/employee.py) `Employee.workload_percent`, `STANDARD_WEEKLY_HOURS` | [calculations](../architecture/calculations.md#capacity-of-one-person-in-one-week) |

## UI labels

### Sign in, sidebar and user menu

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "Abmelden" | Sign out | User menu, [AUTH-13](../features/sign-in.md#auth-13) |
| "Abteilungen" | Departments | Sidebar entry and group of department roles on the users page, [ADM-02](../features/users-and-access.md#adm-02) |
| "Administration" | Administration | Sidebar section for admins, [AUTH-11](../features/sign-in.md#auth-11) |
| "Anmelden" | Sign in | Login page, [AUTH-01](../features/sign-in.md#auth-01) |
| "Benutzer" | Users | Sidebar entry and page title, [ADM-01](../features/users-and-access.md#adm-01) |
| "Darstellung" | Appearance, with "Dunkel" [dark], "Hell" [light] and "System" | User menu, [AUTH-13](../features/sign-in.md#auth-13) |
| "Datenbankzugriff geben" / "Datenbankzugriff entziehen" | Grant or revoke database access | Users page in the desktop app, [DESK-07](../features/desktop.md#desk-07) |
| "Feiertage" | Public holidays | Sidebar entry and page title, [ADM-10](../features/master-data.md#adm-10) |
| "Freie Kapazität" | Free capacity per role | Sidebar section, [DASH-15](../features/portfolio-capacity.md#dash-15) |
| "Mit Microsoft anmelden" | Sign in with Microsoft | Login page, [AUTH-02](../features/sign-in.md#auth-02) |
| "Mitarbeiter" | Employee, the read only permission role | Users page, [AUTH-08](../features/users-and-access.md#auth-08) |
| "Passwort vergessen?" | Forgot password? | Login page, [AUTH-03](../features/sign-in.md#auth-03) |
| "Planung" | Planning | Sidebar section, [AUTH-11](../features/sign-in.md#auth-11) |
| "Profil" | Profile | User menu and page title, [AUTH-04](../features/sign-in.md#auth-04) |
| "Projekte" | Projects | Sidebar entry and page title, [PROJ-01](../features/projects.md#proj-01) |
| "Projektmanager" | Project manager, the editor permission role | Users page, [AUTH-08](../features/users-and-access.md#auth-08) |
| "Ressourcenplanung" | Resource planning | Sidebar entry and page title of `/plan`, [PLAN-01](../features/planning-grid.md#plan-01) |
| "Rollen" | Roles | Sidebar entry and page title, [ADM-03](../features/master-data.md#adm-03) |
| "Seitenleiste ausblenden (⌃⌘S)" | Hide the sidebar | Sidebar button, [AUTH-14](../features/sign-in.md#auth-14) |
| "Tagessätze" | Daily rates | Sidebar entry and page title, [ADM-05](../features/master-data.md#adm-05) |
| "Team" | Team | Sidebar entry and page title, [TEAM-01](../features/team.md#team-01) |
| "Übersicht" | Overview, the portfolio | Sidebar entry and page title of `/dashboard`, [DASH-01](../features/portfolio.md#dash-01) |

### Portfolio overview

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "Bedarf erfüllt." | Demand met | Reason of a role line, [DASH-10](../features/portfolio-capacity.md#dash-10) |
| "bis 10 % über" | Up to 10 % over budget | Bubble chart legend, [DASH-04](../features/portfolio.md#dash-04) |
| "Direkt unterstellt" | Direct reports, the scope `team` | Toolbar scope switch, [DASH-03](../features/portfolio.md#dash-03) |
| "Ganze Abteilung" | Whole department, the scope `department` | Toolbar scope switch, [DASH-03](../features/portfolio.md#dash-03) |
| "Gebucht auf" | Booked on | Person side panel, [DASH-13](../features/portfolio-capacity.md#dash-13) |
| "Hoch, Score über 15" | High, score above 15 | Risk card, [DASH-06](../features/portfolio.md#dash-06) |
| "im Budget" | Within budget | Bubble chart legend, [DASH-04](../features/portfolio.md#dash-04) |
| "Kapazität je Rolle" | Capacity per role | Card title, [DASH-11](../features/portfolio-capacity.md#dash-11) |
| "Kritischer Ressourcenpfad" | Critical resource path | Card title of the buffer list, [DASH-08](../features/portfolio-capacity.md#dash-08) |
| "Lücke" | Gap, demand without a plan | Buffer list and role card, [DASH-09](../features/portfolio-capacity.md#dash-09) |
| "Mittel, 5 bis 15" | Medium, 5 to 15 | Risk card, [DASH-06](../features/portfolio.md#dash-06) |
| "Nicht gedeckt in 52 Wochen." | Not covered in 52 weeks | Reason of a role line, [DASH-09](../features/portfolio-capacity.md#dash-09) |
| "niemand eingeplant" | Nobody planned | Reason of a role line, [DASH-10](../features/portfolio-capacity.md#dash-10) |
| "Niedrig, bis 4" | Low, up to 4 | Risk card, [DASH-06](../features/portfolio.md#dash-06) |
| "Offene Risiken" | Open risks | Card title, [DASH-06](../features/portfolio.md#dash-06) |
| "Personen mit der Rolle" | People with the role | Role side panel, [DASH-12](../features/portfolio-capacity.md#dash-12) |
| "Projekte: Zeit und Fortschritt" | Projects by time and progress | Bubble chart title, [DASH-04](../features/portfolio.md#dash-04) |
| "Projekte mit Lücke" | Projects with a gap | Role side panel, [DASH-12](../features/portfolio-capacity.md#dash-12) |
| "Puffer unter 0" | Buffer below 0 | Bubble chart legend, [DASH-04](../features/portfolio.md#dash-04) |
| "über 10 %" | More than 10 % over budget | Bubble chart legend, [DASH-04](../features/portfolio.md#dash-04) |

### Resource planning

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "3 Monate", "6 Monate", "12 Monate" | Planning window of 13, 26 or 52 weeks | Filter bar, [PLAN-07](../features/planning-view.md#plan-07) |
| "Abwesenheit" | Absence | Timeline legend and grid row, [PLAN-23](../features/absences.md#plan-23) |
| "Abwesenheit eintragen" | Record an absence | Toolbar and row menu, [PLAN-26](../features/absences.md#plan-26) |
| "Abwesenheiten" | Absences, the timeline view | View switch, [PLAN-23](../features/absences.md#plan-23) |
| "Alle ausklappen" / "Alle einklappen" | Expand all or collapse all | Toolbar, [PLAN-14](../features/planning-view.md#plan-14) |
| "Änderungen speichern (⌘S)" | Save changes | Toolbar, [PLAN-03](../features/planning-grid.md#plan-03) |
| "Engpass" | Bottleneck, a week with too few people present | Filter bar badge, e.g. "1 Engpass · KW 12", [PLAN-24](../features/absences.md#plan-24) |
| "Feiertag" | Public holiday | Timeline legend, [PLAN-17](../features/planning-view.md#plan-17) |
| "Frei" | Free days | Employee summary in the grid, [PLAN-04](../features/planning-grid.md#plan-04) |
| "Ganzes Team zeigen" | Show the whole team | Filter bar, [PLAN-13](../features/planning-view.md#plan-13) |
| "Geplant" | Planned days | Employee summary in the grid, [PLAN-04](../features/planning-grid.md#plan-04) |
| "Gesamt (allokiert)" | Total allocated | Sum row in the project view, [PLAN-09](../features/planning-grid.md#plan-09) |
| "Gesamt (frei)" | Total free days | Sum row per employee in the team view, [PLAN-04](../features/planning-grid.md#plan-04) |
| "Heute" | Today | Timeline legend, [PLAN-23](../features/absences.md#plan-23) |
| "Interne & Abwesenheit ausblenden" | Hide internal and absence rows | Filter bar, [PLAN-12](../features/planning-view.md#plan-12) |
| "Interne Projekte" | Internal days, shown where they differ from the usual value | Grid row per employee, [PLAN-04](../features/planning-grid.md#plan-04) |
| "KW" | Calendar week | Week headers and tooltips, [PLAN-17](../features/planning-view.md#plan-17) |
| "Neu (ziehen)" | New, drag to create | Timeline legend, [PLAN-26](../features/absences.md#plan-26) |
| "Nur verfügbare" | Only available people | Filter bar, [PLAN-11](../features/planning-view.md#plan-11) |
| "Projekt entfernen" | Remove a project row | Row menu, [PLAN-06](../features/planning-grid.md#plan-06) |
| "Projekt planen" | Plan a project, opens the wizard | Toolbar, [PLAN-19](../features/staffing.md#plan-19) |
| "Projekt zuweisen" | Assign a project | Row menu and dialog, [PLAN-05](../features/planning-grid.md#plan-05) |
| "Projekte" | Projects, the project view | View switch, [PLAN-09](../features/planning-grid.md#plan-09) |
| "Team" | Team, the grid per employee (value `Grid` in code) | View switch, [PLAN-01](../features/planning-grid.md#plan-01) |
| "Überbucht" | Overbooked | Free days cell, [PLAN-04](../features/planning-grid.md#plan-04) |
| "Wochenende" | Weekend | Timeline legend, [PLAN-23](../features/absences.md#plan-23) |

### Plan wizard "Projekt planen"

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "Abbrechen", "Zurück", "Weiter →", "Speichern" | Cancel, back, next, save | Wizard buttons, [PLAN-22](../features/staffing.md#plan-22) |
| "Bedarf gesamt" | Total demand | People step, [PLAN-21](../features/staffing.md#plan-21) |
| "Kapazität / Wo." | Capacity per week, in GTK | Spread step, [PLAN-20](../features/staffing.md#plan-20) |
| "Mitarbeiter" | Employees, the third step | Stepper, [PLAN-21](../features/staffing.md#plan-21) |
| "Plan gesamt" | Total plan | Preview step, [PLAN-22](../features/staffing.md#plan-22) |
| "Planungsdaten" | Planning data, the second step | Stepper, [PLAN-20](../features/staffing.md#plan-20) |
| "Projekt" | Project, the first step | Stepper, [PLAN-19](../features/staffing.md#plan-19) |
| "PT-Bedarf gesamt" | Total required person days | Spread step, [PLAN-20](../features/staffing.md#plan-20) |
| "Ramp-down" | Ramp-down, from "abrupt" to "langsam" [slow] | Spread step slider, [PLAN-20](../features/staffing.md#plan-20) |
| "Ramp-up" | Ramp-up, from "sofort" [at once] to "langsam" [slow] | Spread step slider, [PLAN-20](../features/staffing.md#plan-20) |
| "Verfügbar im Zeitraum" | Available in the period | People step, [PLAN-21](../features/staffing.md#plan-21) |
| "Vorschau" | Preview, the fourth step | Stepper, [PLAN-22](../features/staffing.md#plan-22) |
| "Wochenverteilung (PT)" | Weekly distribution in person days | Spread step chart, [PLAN-20](../features/staffing.md#plan-20) |

### Projects

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "Abgeschlossen" | Completed, a project state and a list group | Filter, form and list, [PROJ-02](../features/projects.md#proj-02) |
| "Aktiv" | Active, a project state | Filter and form, [PROJ-02](../features/projects.md#proj-02) |
| "Alle" / "Meine" | All projects or my projects | Toolbar filter, [PROJ-02](../features/projects.md#proj-02) |
| "Bedarf" | Required person days | Table column and inspector, [PROJ-01](../features/projects.md#proj-01) |
| "Buchungsnummer" | Booking number | Project form and inspector, [PROJ-06](../features/projects.md#proj-06) |
| "Budgetverbrauch (%)" | Spent budget in percent | Status tab, [PROJ-13](../features/project-tracking.md#proj-13) |
| "Earned Value", "Planned Value" | Earned value and planned value | Status tab chart legend, [PROJ-15](../features/project-tracking.md#proj-15) |
| "Fertigstellungswert" | Earned value | Status tab summary, [PROJ-15](../features/project-tracking.md#proj-15) |
| "Fortschritt (%)" | Progress in percent | Status tab, [PROJ-13](../features/project-tracking.md#proj-13) |
| "Geplant" | Planned, a project state and a list group | Filter, form and list, [PROJ-02](../features/projects.md#proj-02) |
| "Impact (1-5)", "Probability (1-5)" | Impact and probability of a risk | Risk tab, [PROJ-16](../features/project-tracking.md#proj-16) |
| "In Bearbeitung" | In progress, the risk status `mitigated` | Risk tab, [PROJ-16](../features/project-tracking.md#proj-16) |
| "Interne Projekte" | Internal projects | List group, [PROJ-02](../features/projects.md#proj-02) |
| "Internes Projekt" | Internal project | Project form switch, [PROJ-06](../features/projects.md#proj-06) |
| "Ist-Kosten" | Actual cost | Status tab summary, [PROJ-15](../features/project-tracking.md#proj-15) |
| "Liste" / "Kacheln" | List or cards | View switch, [PROJ-04](../features/projects.md#proj-04) |
| "Maßnahme" | Mitigation | Risk tab, [PROJ-16](../features/project-tracking.md#proj-16) |
| "Meine Projekte" / "Weitere Projekte" | My projects or other projects | List groups, [PROJ-01](../features/projects.md#proj-01) |
| "Offen", "Geschlossen" | Open and resolved, risk status values | Risk tab, [PROJ-16](../features/project-tracking.md#proj-16) |
| "Personentage" | Person days | Placeholder of the required days per role, [PROJ-08](../features/projects.md#proj-08) |
| "Prognose linear" / "Prognose additiv" | Linear or additive EAC | Status tab summary, [PROJ-15](../features/project-tracking.md#proj-15) |
| "Projekt anlegen" | Create a project | Toolbar, [PROJ-06](../features/projects.md#proj-06) |
| "Projekt-Code" | Project code | Project form, [PROJ-06](../features/projects.md#proj-06) |
| "Projekt-Owner" | Project owners | Project form, [PROJ-06](../features/projects.md#proj-06) |
| "Risiko" | At risk, a project state | Filter and form, [PROJ-02](../features/projects.md#proj-02) |
| "Status", "Ressourcen", "Risiken", "Daten" | Status, resources, risks, data | Tabs of the project drawer, [PROJ-09](../features/project-tracking.md#proj-09) |
| "Tage pro Woche" | Days per week | Resources tab, [PROJ-18](../features/staffing.md#proj-18) |
| "Verbraucht" | Spent budget | Table column, [PROJ-01](../features/projects.md#proj-01) |

### Team

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "Abwesenheit hinzufügen" | Add an absence | Absence dialog, [TEAM-12](../features/absences.md#team-12) |
| "Alle", "Meine", "Überlastet", "Frei" | All, mine, overloaded, free | Toolbar filter, [TEAM-03](../features/team.md#team-03) |
| "Arbeitszeit (h/Woche)" | Working hours per week | Employee form, [TEAM-07](../features/team.md#team-07) |
| "Auslastung 8 W." | Utilization over 8 weeks | Table column, [TEAM-02](../features/team.md#team-02) |
| "Auslastung · nächste 8 Wochen" | Utilization of the next 8 weeks | Inspector, [TEAM-05](../features/team.md#team-05) |
| "Frei 8 W." | Free days over 8 weeks | Table column, [TEAM-02](../features/team.md#team-02) |
| "Interne Projekte (h/Woche)" | Internal hours per week | Employee form, [TEAM-07](../features/team.md#team-07) |
| "Meine Mitarbeiter" / "Weitere Mitarbeiter" | My direct reports or other employees | List groups, [TEAM-03](../features/team.md#team-03) |
| "Mitarbeiter anlegen" | Create an employee | Toolbar, [TEAM-07](../features/team.md#team-07) |
| "Schlüsselrolle" | Key role | Employee form, [TEAM-08](../features/team.md#team-08) |
| "Senioritätslevel" | Seniority | Employee form, [TEAM-07](../features/team.md#team-07) |
| "Vorgesetzter" | Manager | Employee form, [TEAM-07](../features/team.md#team-07) |
| "Weitere Rollen" | Other roles | Employee form, [TEAM-07](../features/team.md#team-07) |

### Administration

| German label | English meaning | Where it appears |
| --- | --- | --- |
| "Abkürzung" | Abbreviation of a role, at most 3 characters | Role form, [ADM-03](../features/master-data.md#adm-03) |
| "DB" | Contribution margin | Daily rates page, next to each price, [ADM-05](../features/master-data.md#adm-05) |
| "DB (Listenpreis)" | Margin of the list price | Daily rates page, [ADM-07](../features/master-data.md#adm-07) |
| "Empf. Verkaufspreis" | Recommended sales price | Daily rates table, [ADM-05](../features/master-data.md#adm-05) |
| "Herstellkosten" | Production cost | Daily rates table, [ADM-05](../features/master-data.md#adm-05) |
| "Jährlich wiederkehrend (fixer Termin)" | Recurring every year on a fixed date | Holiday form, [ADM-10](../features/master-data.md#adm-10) |
| "Kürzel" | Short code of a department, at most 10 characters | Department form, [ADM-08](../features/master-data.md#adm-08) |
| "Listenpreis" | List price | Daily rates table, [ADM-06](../features/master-data.md#adm-06) |
| "manuell" | Manual, the list price was entered by hand | Daily rates table, [ADM-06](../features/master-data.md#adm-06) |
| "Mindest-DB (Empf. VK)" | Minimum margin for the recommended sales price | Daily rates page, [ADM-07](../features/master-data.md#adm-07) |
| "Ramp-Up" / "Ramp-Down" | The role is needed from the start or until the end | Role form and table, [ADM-03](../features/master-data.md#adm-03) |

## Names that differ

These are places where one concept has two names, or one name has two meanings.

- "Interne Projekte" means internal projects (`is_internal`) in the project list. In the employee form and the planning grid it means the internal hours (`internal_hours`). The free days tooltip calls the same hours "Intern".
- "Mitarbeiter" is the label of the permission role `employee`. It is also the general word for a team member on the team page and in the plan wizard.
- The team filter says "Überlastet" [overloaded], and the planning grid says "Überbucht" [overbooked], for a person with more work than days.
- The roles page writes "Ramp-Up" and "Ramp-Down". The plan wizard writes "Ramp-up" and "Ramp-down".
- The status tab shows earned value as "Fertigstellungswert" in the summary and as "Earned Value" in the chart legend. The forecasts are "Prognose linear" in the summary and "Prognose (linear)" in the chart.
- The risk tab uses the English labels "Impact (1-5)" and "Probability (1-5)". The portfolio risk card uses the German "Wahrscheinlichkeit mal Auswirkung".
- The risk status `mitigated` has the label "In Bearbeitung" [in progress], and `resolved` has the label "Geschlossen" [closed].
- The recommended sales price is "Empf. Verkaufspreis" in the table and "Empf. VK" in the margin input.
- The planning view switch shows "Team", but the stored value is `Grid`. The grid itself has the accessible name "Kapazitätsplanung", while the page title is "Ressourcenplanung".
- The code does not explain the unit "GTK".
