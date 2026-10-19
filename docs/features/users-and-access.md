---
title: Users and access
description: How admins manage user accounts and give access levels, and how Alloq protects sessions, checks rights on the server and runs behind a reverse proxy.
story_ids: [ADM-01, ADM-02, AUTH-05, AUTH-08, AUTH-09, AUTH-10, AUTH-06, AUTH-07]
source_paths:
  - app/app.py
  - app/configuration.py
  - app/public_url.py
  - app/pages/users.py
  - app/components/db_access_button.py
  - app/components/sidebar.py
  - app/desktop/db_access_state.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-commons/src/alloq_commons/roles.py
  - components/alloq-commons/src/alloq_commons/models/department.py
  - components/alloq-commons/src/alloq_commons/state/department_states.py
  - components/alloq-commons/src/alloq_commons/components/shell.py
  - configuration/config.yaml
  - tests/test_handler_authorization.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Users and access

This page covers how an admin decides who may use Alloq and what each person may do. It also covers the rules that protect the data on the server, and the settings for running Alloq behind a reverse proxy. The stories belong to the activity "Set up the organisation" on the [story map](./story-map.md). The other half of that activity, the master data, is on the page [Roles, rates, departments and holidays](./master-data.md).

The activity has these user tasks and sub-tasks on this page:

- **Manage users.** Manage the user accounts and give each user an access level and departments.
- **Control access.** Protect sessions, assign access levels by role, guard actions on the server, and run behind a reverse proxy.

The mechanism behind sessions, access levels and guards is described on the architecture page [Security and access](../architecture/security-and-access.md). The stories below link to it and do not explain the mechanism again. Several rules come from the installed package `appkit_user`, not from the repository. The evidence names the module and the symbol for these rules but does not link them.

## ADM-01 Manage users {#adm-01}

Admins list, add, edit and delete the users who can sign in.

As an administrator, I want to manage the user accounts, so that only the right people can sign in to Alloq.

Administrator · Manage users / Manage users · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** a signed-in admin, **when** the admin opens `/admin/users` with the title "Benutzer" [users], **then** the page loads the role choices (`DepartmentState.load_user_roles`), the users (`UserState.load_users`) and the database access list for the desktop app (`DatabaseAccessState.load`).
2. **Given** the users page, **when** it renders, **then** the toolbar shows the title "Benutzer", the subtitle "Administration · Benutzer anlegen, bearbeiten und löschen" [administration, create, edit and delete users], the user search and the add button. The page mounts the add and edit dialogs itself, because it builds its own table view. (no test)
3. **Given** the app runs as the desktop app, **when** the user table renders, **then** each row has a button "Datenbankzugriff" [database access]. In the web app the button is missing. The rules of this button are in the story [DESK-07](./desktop.md#desk-07).
4. **Given** a user who is not an admin, **when** the user opens the users page, **then** the page shows the no-permission content of `appkit_user` instead of the table. See [AUTH-08](#auth-08).

### Evidence

- [app/pages/users.py](../../app/pages/users.py): `create_users_page`, `user_toolbar`, `row_actions`
- [app/components/db_access_button.py](../../app/components/db_access_button.py): `database_access_button`
- `appkit_user.user_management.components.user`: `user_table_view`, `add_user_modal`, `edit_user_modal`, `search_user_input`, `add_user_button`
- `appkit_user.user_management.states.user_states`: `UserState`
- Tests: [tests/test_users_page.py](../../tests/test_users_page.py) `TestUsersPage.test_on_load_loads_users`, `test_on_load_loads_database_access`, `test_database_access_button_only_in_the_desktop_app`

### Open questions

- Creating, editing and deleting a user happens in `UserState` and `user_table_view` of the installed package `appkit_user`. The rules of these actions, e.g. which fields are required, are not in this repository, so this page does not list them.

## ADM-02 Give users access level and departments {#adm-02}

Admins give each user an access role and, if they want, one or more department roles.

As an administrator, I want to give each user an access role, so that project managers can edit planning and employees can only read it.

Administrator · Manage users / Manage users · priority 2 · core · v2.0.4

### Acceptance criteria

1. **Given** the users page loads, **when** `DepartmentState.load_user_roles` runs, **then** the user dialog offers the roles "Projektmanager" [project manager] and "Mitarbeiter" [employee], followed by one role per department in the group "Abteilungen" [departments]. The handler is guarded with `@requires_admin`.
2. **Given** a department, **when** its role is built, **then** the role name is `department_<id>`, so the role stays the same when someone renames the department. The label is "&lt;name&gt; (&lt;abbreviation&gt;)", e.g. "Informationstechnik (IT)", and the description is "Mitglied der Abteilung &lt;name&gt;" [member of the department].
3. **Given** a user with a role, **when** the user works in Alloq, **then** the role decides the access level. The rules for each level are in [AUTH-08](#auth-08).

### Evidence

- [components/alloq-commons/src/alloq_commons/state/department_states.py](../../components/alloq-commons/src/alloq_commons/state/department_states.py): `DepartmentState.load_user_roles`
- [components/alloq-commons/src/alloq_commons/roles.py](../../components/alloq-commons/src/alloq_commons/roles.py): `PROJECT_MANAGER_ROLE`, `EMPLOYEE_ROLE`, `ALL_ROLES`, `DEPARTMENT_ROLE_GROUP`, `department_role_name`, `department_roles`
- [components/alloq-commons/src/alloq_commons/models/department.py](../../components/alloq-commons/src/alloq_commons/models/department.py): `Department.label`
- Tests: [components/alloq-commons/tests/test_departments.py](../../components/alloq-commons/tests/test_departments.py) `TestDepartmentRoles.test_user_management_offers_app_and_department_roles`, `test_role_name_uses_id`

### Open questions

- No code outside `roles.py` and `DepartmentState.load_user_roles` reads the `department_<id>` roles. It is not clear whether the department role is only a label for now, or whether a filter is planned.

## AUTH-05 Require a valid session {#auth-05}

Pages and events only work with a valid session. Everyone else goes to the login page.

As an administrator, I want every page and every event to require a valid session, so that nobody reads planning data without signing in.

Administrator · Control access / Protect sessions · priority 1 · core · v0.3.0

### Acceptance criteria

1. **Given** the app is built, **when** `app/app.py` creates `rx.App`, **then** `add_session_guard` is in `api_transformer`. In the production setup with a single port, a page load without a session is redirected to the login route before the app shell is sent.
2. **Given** a client sends a WebSocket event, **when** its session is missing or expired, **then** the session filter from `install_session_filter(app)` rejects the event before any handler or `on_load` handler runs, so no page data is sent.
3. **Given** a page built with `app_page`, **when** it is registered, **then** it goes through `authenticated_page` of `appkit_user`. This adds the session monitor, and with `admin_only=True` it shows the no-permission content to users who are not admins.
4. **Given** the default configuration, **when** a session is idle, **then** it ends after `session_timeout: 25` minutes, and the token is refreshed with `auth_token_refresh_delta: 10` minutes. (no test)

The session filter checks the route that the client reports, so it stops a browser without a session but not a client that sends crafted socket messages. The guards on each handler in [AUTH-09](#auth-09) are the layer that enforces rights. The details are in [Sessions](../architecture/security-and-access.md#sessions).

### Evidence

- [app/app.py](../../app/app.py): `app`, `add_session_guard`, `install_session_filter`
- [components/alloq-commons/src/alloq_commons/components/shell.py](../../components/alloq-commons/src/alloq_commons/components/shell.py): `app_page`
- [configuration/config.yaml](../../configuration/config.yaml): `app.authentication.session_timeout`, `app.authentication.auth_token_refresh_delta`
- `appkit_user.authentication.http_guard`: `add_session_guard`, `SessionGuardMiddleware`
- `appkit_user.authentication.session_filter`: `install_session_filter`, `SessionFilter`
- `appkit_user.authentication.templates`: `authenticated_page`
- Tests: [tests/test_app.py](../../tests/test_app.py) `TestAppWiring.test_session_guard_installed`, `test_session_filter_installed`; [components/alloq-commons/tests/test_shell.py](../../components/alloq-commons/tests/test_shell.py) `TestAppPage.test_registers_route_with_template`

## AUTH-08 Three access levels by role {#auth-08}

Three access levels decide what a user may read and change: admin, project manager and employee.

As an administrator, I want to give each user an access level through roles, so that project managers can plan, employees can only read and only admins can change the administration.

Administrator · Control access / Assign access levels by role · priority 1 · core · v2.0.4 (approximate)

This story also covers the draft ADM-13, which keeps the administration pages closed to everyone except admins. The table of which page needs which level is in [Which page needs which level](../architecture/security-and-access.md#which-page-needs-which-level).

### Acceptance criteria

1. **Given** the Alloq roles, **when** user management offers them, **then** there are two app roles, `project_manager` with the label "Projektmanager" and `employee` with the label "Mitarbeiter". Admin rights come from the `is_admin` flag of `appkit_user`, not from a role.
2. **Given** a signed-in user, **when** the app checks edit rights, **then** `can_edit` is true for admins and for users with the role `project_manager`.
3. **Given** a signed-in user, **when** the app checks read rights, **then** `can_view` is true for admins, for project managers and for users with the role `employee`.
4. **Given** a user with a department role only, **when** the app checks rights, **then** the user has no access level, because `can_edit` and `can_view` check only the two app roles and the admin flag.
5. **Given** a signed-in user without read rights, **when** the user opens a page part wrapped in `viewer_only` or `editor_only` with the fallback `no_access()`, **then** the page shows "Sie haben nicht die notwendigen Berechtigungen, um auf diese Seite zuzugreifen." [you do not have the rights to open this page].
6. **Given** a page part wrapped in `admin_only`, **when** a user who is not an admin views it, **then** the part is not rendered, because `admin_only` checks only the `is_admin` flag.
7. **Given** a user who is not an admin, **when** the user opens one of the pages "Benutzer", "Rollen" [roles], "Tagessätze" [daily rates], "Abteilungen" or "Feiertage" [public holidays] under `/admin`, **then** `app_page(admin_only=True)` shows the fallback of `appkit_user` with the title "Du hast nicht die notwendigen Rechte, um diese Inhalte zu sehen!" [you do not have the rights to see this content] instead of the page. (no test)
8. **Given** a user who is not an admin, **when** a data handler of an administration state runs, e.g. `HolidayState.load_holidays`, **then** `@requires_admin` stops it with the toast "Sie haben keine Berechtigung für diese Aktion." [you are not allowed to do this], and the handler reads and writes nothing.
9. **Given** the sidebar, **when** a project manager or an employee is signed in, **then** the section "Administration" is hidden. It shows only for admins.

### Evidence

- [components/alloq-commons/src/alloq_commons/roles.py](../../components/alloq-commons/src/alloq_commons/roles.py): `PROJECT_MANAGER_ROLE`, `EMPLOYEE_ROLE`, `ALL_ROLES`
- [components/alloq-commons/src/alloq_commons/access.py](../../components/alloq-commons/src/alloq_commons/access.py): `can_edit`, `can_view`, `CAN_EDIT`, `CAN_VIEW`, `IS_ADMIN`, `viewer_only`, `editor_only`, `admin_only`, `no_access`, `NO_ACCESS_MSG`
- [components/alloq-commons/src/alloq_commons/components/shell.py](../../components/alloq-commons/src/alloq_commons/components/shell.py): `app_page`
- [app/components/sidebar.py](../../app/components/sidebar.py): `ADMIN_ITEMS`, `_admin_section`
- `appkit_user.authentication.components.components`: `default_fallback`, `requires_admin`
- `appkit_user.authentication.decorators`: `requires_admin`
- Tests: [components/alloq-commons/tests/test_access.py](../../components/alloq-commons/tests/test_access.py) `TestEmployeeRole.test_employee_role_is_offered_in_user_management`, `TestCanEdit.test_admins_and_project_managers_may_edit`, `TestCanView.test_admins_managers_and_employees_may_read`, `TestRenderGuards.test_no_access_explains_the_missing_rights`, `TestRenderGuards.test_admin_only_checks_admin_flag`; [components/alloq-commons/tests/test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) `TestHolidayStateRequiresAdmin.test_non_admin_is_rejected`; [tests/test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarComponent.test_administration_stays_admin_only`

### Open questions

- `PROJECT_MANAGER_ROLE` exists since v0.2.0. The employee role, `can_view`, `can_edit` and the three access levels came in v2.0.4. `@requires_admin` on the administration states came in v0.3.0. The map shows v2.0.4 as an approximate release.
- Criterion 4 follows from the code of `can_edit` and `can_view`, but no test checks a user who has only a department role.

## AUTH-09 Check rights on the server {#auth-09}

Every action checks the rights of the caller on the server, so a hidden button is never the only protection.

As an administrator, I want each event handler to check the rights of the caller on the server, so that a user cannot run an action that the UI hides from them.

Administrator · Control access / Guard actions on the server · priority 1 · core · v2.0.4

The decorators and how they work are described in [Guard decorators](../architecture/security-and-access.md#guard-decorators).

### Acceptance criteria

1. **Given** a handler with `@requires_editor`, **when** an admin or a project manager calls it, **then** the handler runs.
2. **Given** a handler with `@requires_viewer`, **when** an admin, a project manager or an employee calls it, **then** the handler runs.
3. **Given** a handler with `@requires_editor` or `@requires_viewer`, **when** a signed-in user without the right calls it, **then** the handler does not run. A toast "Sie haben keine Berechtigung für diese Aktion." appears at the top right, and a warning with the user id is logged.
4. **Given** a guarded handler, **when** a caller without a session calls it, **then** the caller is redirected to the login page.
5. **Given** a guarded handler, **when** it is wrapped, **then** the wrapper keeps the name of the handler and stores its level, `viewer` or `editor`, in the attribute `alloq_access_level`.
6. **Given** an administration handler, e.g. `DatabaseAccessState.load`, **when** it is decorated, **then** it uses `@requires_admin` of `appkit_user`, which lets only users with the `is_admin` flag run it.

### Evidence

- [components/alloq-commons/src/alloq_commons/access.py](../../components/alloq-commons/src/alloq_commons/access.py): `requires_editor`, `requires_viewer`, `_guard`, `_NOT_AUTHORIZED_MSG`, `ACCESS_LEVEL_ATTR`
- [app/desktop/db_access_state.py](../../app/desktop/db_access_state.py): `DatabaseAccessState.load`
- `appkit_user.authentication.decorators`: `requires_admin`
- Tests: [components/alloq-commons/tests/test_access.py](../../components/alloq-commons/tests/test_access.py) `TestRequiresEditor.test_admins_and_project_managers_run_the_handler`, `TestRequiresEditor.test_readers_and_others_are_denied`, `TestRequiresEditor.test_anonymous_users_are_redirected`, `TestRequiresEditor.test_keeps_the_handler_name`, `TestRequiresViewer.test_allowed_users_run_the_handler`; [tests/test_desktop_db_access.py](../../tests/test_desktop_db_access.py) `TestDatabaseAccessState.test_load_needs_an_alloq_admin`

## AUTH-10 Test that every handler is guarded {#auth-10}

A test fails when someone adds an event handler without the right guard.

As an administrator, I want the test suite to check the guard of every event handler, so that no new handler opens data to the wrong users.

Administrator · Control access / Guard actions on the server · priority 2 · core · v0.3.0

The test and its lists are described in [The handler authorization test](../architecture/security-and-access.md#the-handler-authorization-test).

### Acceptance criteria

1. **Given** all states in the packages `alloq_commons`, `alloq_dashboard`, `alloq_project` and `alloq_team`, plus the sidebar, database access and desktop login states, **when** the test collects their handlers, **then** each handler must have a guard, be a listed viewer handler, check rights inside the handler, be a UI handler or be a listed handler that runs before sign-in. Any other handler fails the test.
2. **Given** the administration states `DailyRateState`, `DepartmentState`, `RoleState`, `HolidayState` and `DatabaseAccessState`, **when** the test checks them, **then** none of their handlers may use `@requires_editor` or `@requires_viewer`.
3. **Given** the states in `alloq_dashboard`, `alloq_project` and `alloq_team` and the `SidebarState`, **when** the test checks them, **then** none of their handlers may use `@requires_admin`, so project managers can run them.
4. **Given** the list `VIEWER_HANDLERS` with the loads of `ProjectState`, `ProjectResourceState` and `PlanningStore`, **when** the test checks it, **then** the handlers with `@requires_viewer` are exactly the handlers in the list.
5. **Given** a handler in `VIEWER_HANDLERS`, **when** the test reads its code, **then** the code contains no write call such as `.commit(` or `.add(`.
6. **Given** a handler in `UI_ONLY_HANDLERS`, e.g. `SplashState.finish` or `SidebarState.invalidate`, **when** the test reads its code and the helpers it calls, **then** the code must not reach the database.
7. **Given** a background handler, **when** the test checks it, **then** it must not have a guard decorator.
8. **Given** a card load in `INLINE_ADMIN_CHECK`, **when** the test reads `_run_card_load`, **then** the code takes `async with self:`, then calls `await _can_edit(self`, and only then calls `await loader()`.
9. **Given** an entry in `UI_ONLY_HANDLERS`, `INLINE_ADMIN_CHECK` or `PRE_AUTH_HANDLERS` whose handler was removed or now has a guard, **when** the test runs, **then** it fails because the entry is stale.

### Evidence

- [tests/test_handler_authorization.py](../../tests/test_handler_authorization.py): `PACKAGES`, `EXTRA_MODULES`, `ADMIN_STATES`, `EDITOR_PACKAGES`, `EDITOR_STATES`, `INLINE_ADMIN_CHECK`, `PRE_AUTH_HANDLERS`, `VIEWER_HANDLERS`, `UI_ONLY_HANDLERS`, `WRITE_MARKERS`
- Tests: [tests/test_handler_authorization.py](../../tests/test_handler_authorization.py) `test_every_handler_is_admin_guarded_or_ui_only`, `test_administration_handlers_stay_admin_only`, `test_planning_handlers_are_open_to_project_managers`, `test_viewer_handlers_are_exactly_the_allowlist`, `test_viewer_handler_does_not_write`, `test_ui_only_handler_does_not_reach_database`, `test_guards_are_not_used_on_background_handlers`, `test_background_handlers_check_edit_rights_inside_state_lock`, `test_allowlists_have_no_stale_entries`

### Open questions

- The test exists since v0.3.0. The rules for editors, viewers and handlers that run before sign-in came in v2.0.4.

## AUTH-06 Trust HTTPS only from known proxies {#auth-06}

Behind a reverse proxy, the app trusts the HTTPS header only from known proxies.

As an administrator, I want the app to accept `X-Forwarded-Proto` only from trusted proxies, so that links and cookies use HTTPS and no client can fake the scheme.

Administrator · Control access / Run behind a reverse proxy · priority 1 · core · v0.2.0

The setting is also described in [Proxy headers](../architecture/security-and-access.md#proxy-headers).

### Acceptance criteria

1. **Given** the app is built, **when** `app/app.py` adds its API transformers, **then** `add_https_middleware` wraps the app in `ForceHTTPSMiddleware`. The middleware sets the scheme from `X-Forwarded-Proto` and does not redirect.
2. **Given** `app.trusted_proxies` is set, **when** the middleware is built, **then** it receives exactly these peer addresses as `trusted_hosts`.
3. **Given** a request from a peer that is not in `trusted_proxies`, **when** it sends `X-Forwarded-Proto: https`, **then** the scheme stays `http`.
4. **Given** `trusted_proxies` is not set, **when** the configuration loads, **then** the value is `None`, which trusts every peer. The comment in `configuration/config.yaml` says to set it wherever the backend port can be reached without the proxy.

### Evidence

- [app/app.py](../../app/app.py): `add_https_middleware`
- [app/configuration.py](../../app/configuration.py): `AppConfig.trusted_proxies`
- [configuration/config.yaml](../../configuration/config.yaml): `app.trusted_proxies`
- `appkit_commons.middleware`: `ForceHTTPSMiddleware`
- Tests: [tests/test_app.py](../../tests/test_app.py) `TestAddHttpsMiddleware.test_wraps_with_force_https_middleware`, `test_passes_configured_trusted_proxies`, `test_ignores_forwarded_proto_from_untrusted_peer`; `TestAppConfigTrustedProxies.test_defaults_to_none`

### Open questions

- `add_https_middleware` exists since v0.2.0. The setting `trusted_proxies` came in v0.3.0.

## AUTH-07 Build public links from the base URL {#auth-07}

In production, the app builds all its public links from `PUBLIC_BASE_URL` and an optional path prefix.

As an administrator, I want to set the public address of the app in two environment variables, so that OAuth callbacks, reset links and API links work behind a proxy without URLs written into the configuration.

Administrator · Control access / Run behind a reverse proxy · priority 2 · core · v0.4.2

The variables are listed in the [configuration reference](../reference/configuration.md).

### Acceptance criteria

1. **Given** the environment is `production`, as in the default `configuration/config.yaml`, **when** `PUBLIC_BASE_URL` is missing, **then** `configure()` raises `RuntimeError` with "PUBLIC_BASE_URL must be set in production".
2. **Given** `PUBLIC_BASE_URL` is set, **when** it is not an http or https origin, or it contains a path, a query or a fragment, **then** `PublicUrl.create` raises `PublicUrlError`.
3. **Given** `PUBLIC_PATH_PREFIX` is set, **when** it contains "//", "?", "#", a backslash or a space, **then** `PublicUrlError` is raised. A valid prefix gets one leading slash and no trailing slash.
4. **Given** only `PUBLIC_PATH_PREFIX` is set, **when** the app reads the environment, **then** the prefix is ignored and a warning is logged.
5. **Given** a valid public URL, **when** `apply_public_url` runs, **then** `server_url` becomes the base URL plus the prefix and `server_port` becomes 0. The Reflex `deploy_url` and `api_url` include the prefix. `frontend_port` is 443 for https and 80 for http. Each OAuth redirect URL becomes the app URL plus `/oauth/<provider>/callback`.
6. **Given** a public URL, **when** `reflex_server_urls` is called, **then** it returns the bare origin for both URLs, because Reflex adds the paths itself. Without a public URL it returns the configured values or the local defaults.

### Evidence

- [app/public_url.py](../../app/public_url.py): `PublicUrl`, `PublicUrlError`, `_normalize_base_url`, `_normalize_path_prefix`, `apply_public_url`, `reflex_server_urls`, `PUBLIC_BASE_URL_ENV`, `PUBLIC_PATH_PREFIX_ENV`, `OAUTH_CALLBACK_PATH`
- [app/configuration.py](../../app/configuration.py): `configure`
- Tests: [tests/test_configuration_profiles.py](../../tests/test_configuration_profiles.py) `test_default_profile_requires_public_base_url`; [tests/test_public_url.py](../../tests/test_public_url.py) `TestPublicUrlCreate.test_rejects_invalid_base_url`, `TestPublicUrlCreate.test_rejects_invalid_prefix`, `TestPublicUrlFromEnv.test_prefix_without_base_url_is_ignored`, `TestApplyPublicUrl.test_frontend_port_is_scheme_default`, `TestReflexServerUrls.test_public_url_gives_bare_origin`

### Open questions

- `reflex_server_urls` is defined and tested, but `rxconfig.py` does not call it at `cb9d5b0`. It is not clear where it is meant to be used.
