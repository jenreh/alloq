---
title: Sign in and find your way
description: How people sign in to Alloq, reset a password, move between pages with the sidebar and manage their own account.
story_ids: [AUTH-01, AUTH-02, AUTH-03, AUTH-11, AUTH-12, AUTH-14, AUTH-04, AUTH-13]
source_paths:
  - app/app.py
  - app/pages/login.py
  - app/pages/profile.py
  - app/public_url.py
  - app/components/sidebar.py
  - app/components/sidebar_state.py
  - components/alloq-commons/src/alloq_commons/access.py
  - components/alloq-commons/src/alloq_commons/components/shell.py
  - components/alloq-commons/src/alloq_commons/components/toolbar.py
  - configuration/config.yaml
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Sign in and find your way

This page covers the first steps of every person who uses Alloq. A person signs in, finds the pages they may open, and looks after their own account. The stories belong to the activity "Sign in" on the [story map](./story-map.md).

The activity has these user tasks and sub-tasks:

- **Sign in.** Sign in with email and password, sign in with Microsoft in the browser, and reset a forgotten password.
- **Find my way in the app.** Navigate by access level, and arrange the window.
- **Manage my account.** Change profile and password, and use the user menu.

Several rules come from the installed package `appkit_user`, not from the repository. The evidence names the module and the symbol for these rules but does not link them. The desktop app signs in differently. Its stories are on the [desktop page](./desktop.md).

## AUTH-01 Sign in with email and password {#auth-01}

People sign in to the web app with their email address and password.

As an employee, I want to sign in with my email address and password, so that I can open the planning pages I am allowed to see.

Employee · Sign in / Sign in with email and password · priority 1 · core · v0.2.0 · skeleton

### Acceptance criteria

1. **Given** the web app (not the desktop build) shows the login page at `/login`, **when** the page renders, **then** the card shows the field "E-Mail" with the placeholder "name@firma.de", the field "Passwort" [password], the button "Anmelden" [sign in] and the link "Passwort vergessen?" [forgot password?]. Both fields are required, and the email field has the type email.
2. **Given** a person fills in the form, **when** they press "Anmelden", **then** the form calls `LoginState.login_with_password` from `appkit_user`, and the button shows a loading state while `LoginState.is_loading` is true.
3. **Given** the email address or the password is wrong, **when** the person submits the form, **then** the card shows `LoginState.error_message` in a red alert, and a toast shows the same text. The message is "Ungültiger Benutzername oder Passwort." [invalid user name or password]. A deactivated account gets "Ihr Konto wurde deaktiviert. Bitte wenden Sie sich an einen Administrator." and an account that is not verified gets a similar message. (no test)
4. **Given** the login page loads, **when** its load handlers run, **then** `LoginState.clear_session_storage_token` runs. The desktop build also adds a handler that hides the splash screen.
5. **Given** the sign-in succeeds, **when** `appkit_user` redirects, **then** the person goes to the page they asked for before sign-in. Without such a page, the person goes to the homepage "/", which is the planning page.

### Evidence

- [app/pages/login.py](../../app/pages/login.py): `create_login_page`, `login_view`, `_card_content`, `_password_form`
- [app/app.py](../../app/app.py): `create_login_page()`, `create_planning_page(sidebar(), route="/")`
- `appkit_user.authentication.states`: `LoginState.login_with_password`, `LoginState._LOGIN_ERROR_MESSAGES`, `LoginState.redir`
- Tests: [tests/test_login_page.py](../../tests/test_login_page.py) `TestLoginView.test_password_form_submits_to_login_state`, `test_registers_route_and_clears_token_on_load`; [tests/test_app.py](../../tests/test_app.py) `TestAppWiring.test_planning_page_is_the_homepage`

### Open questions

- The password sign-in exists since v0.2.0 on the login page of `appkit_user`. The login page in Alloq's own style in `app/pages/login.py` came in v2.0.0. The map shows v0.2.0.

## AUTH-02 Sign in with Microsoft {#auth-02}

People sign in to the web app with their Microsoft account.

As an employee, I want to sign in with my Microsoft account, so that I do not need a separate Alloq password.

Employee · Sign in / Sign in with Microsoft in the browser · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** Azure or GitHub sign-in is turned on in the configuration, **when** the web login page renders, **then** a divider "oder" [or] and the single sign-on buttons appear. "Mit Microsoft anmelden" [sign in with Microsoft] shows when `LoginState.enable_azure_oauth` is true. "Mit GitHub anmelden" [sign in with GitHub] shows when `LoginState.enable_github_oauth` is true.
2. **Given** the default configuration, **when** the app loads its sign-in providers, **then** only the provider "azure" is set up, and the GitHub provider is commented out. (no test)
3. **Given** the app starts, **when** `app/app.py` imports the callback pages of `appkit_user`, **then** the routes `/oauth/azure/callback` and `/oauth/github/callback` exist, so the provider can send the person back to finish the sign-in. (no test)
4. **Given** `PUBLIC_BASE_URL` and `PUBLIC_PATH_PREFIX` are set, **when** the configuration loads, **then** the redirect URL of each provider is `<base><prefix>/oauth/<provider>/callback`.

### Evidence

- [app/pages/login.py](../../app/pages/login.py): `_single_sign_on`, `SSO_BUTTON`
- [app/app.py](../../app/app.py): imports of `azure_oauth_callback_page`, `github_oauth_callback_page`
- [app/public_url.py](../../app/public_url.py): `apply_public_url`, `OAUTH_CALLBACK_PATH`
- [configuration/config.yaml](../../configuration/config.yaml): `app.authentication.oauth_providers`
- Tests: [tests/test_login_page.py](../../tests/test_login_page.py) `TestLoginView.test_single_sign_on_buttons`; [tests/test_public_url.py](../../tests/test_public_url.py) `TestApplyPublicUrl.test_derives_authentication_urls`

### Open questions

- `appkit_user` also registers `/oauth/google/callback` and `/oauth/apple/callback` when it is imported. Alloq sets up no Google or Apple provider, and the login page has no button for them. Should the docs mention these routes?

## AUTH-03 Reset a forgotten password {#auth-03}

People who forgot their password can set a new one with a link they get by email.

As an employee, I want to reset a forgotten password by email, so that I can sign in again without help from an administrator.

Employee · Sign in / Reset a forgotten password · priority 1 · core · v0.2.0

### Acceptance criteria

1. **Given** a person is on the web login page, **when** they click "Passwort vergessen?", **then** the app opens `/password-reset`.
2. **Given** a person asks for a reset for any email address, **when** they submit the request, **then** the page always shows "Wenn diese E-Mail-Adresse registriert ist, erhalten Sie eine Bestätigungsmail." [if this address is registered, you will get a confirmation email]. So the page never shows whether the address exists. An invalid address shows "Bitte geben Sie eine gültige E-Mail-Adresse ein." [please enter a valid email address]. (no test)
3. **Given** the confirm page `/password-reset/confirm` opens, **when** the token in the URL is missing, unknown, used or expired, **then** the page sets a token error and redirects to `/password-reset`. The errors are "Kein gültiger Token gefunden.", "Ungültiger oder abgelaufener Token.", "Dieser Token wurde bereits verwendet." and "Dieser Token ist abgelaufen." (no test)
4. **Given** a valid token, **when** the person enters a new password, **then** the password needs at least 12 characters with an upper-case letter, a lower-case letter, a digit and a special character. Both entries must match, or the page shows "Passwörter stimmen nicht überein." [passwords do not match]. A password the person used before is refused. (no test)
5. **Given** the new password is accepted, **when** the reset completes, **then** a toast says "Passwort erfolgreich zurückgesetzt. Bitte melden Sie sich an." [password reset, please sign in] and the app redirects to `/login`. (no test)
6. **Given** the app runs below a path prefix, **when** the reset pages render their logo, **then** the logo paths include the prefix, because `app/app.py` builds them with `rx.asset`.

### Evidence

- [app/app.py](../../app/app.py): `auth_page_logos`, `create_password_reset_request_page`, `create_password_reset_confirm_page`
- [app/pages/login.py](../../app/pages/login.py): `_password_form`
- `appkit_user.authentication.password_reset_states`: `PasswordResetRequestState.request_password_reset`, `PasswordResetConfirmState.validate_token`, `PasswordResetConfirmState.confirm_password_reset`
- `appkit_user.authentication.password_policy`: `MIN_PASSWORD_LENGTH`, `PASSWORD_REGEX`, `PASSWORD_MISMATCH_MESSAGE`
- Tests: [tests/test_login_page.py](../../tests/test_login_page.py) `TestLoginView.test_password_form_submits_to_login_state`; [tests/test_app.py](../../tests/test_app.py) `TestAuthPageLogos.test_logos_carry_frontend_path`

### Open questions

- The reset rules live in `appkit_user`, and Alloq has no test of its own for them. `configuration/config.yaml` has no mail server settings. Does the reset email work in production?
- The desktop login has no password form and no reset link. Can a person reach the reset page in the desktop app?

## AUTH-11 Sidebar shows allowed pages {#auth-11}

The sidebar lists only the pages that the signed-in person may open.

As an employee, I want the sidebar to show only the pages I can use, so that I do not open pages that refuse me.

Employee · Find my way in the app / Navigate by access level · priority 1 · core · v2.0.0

### Acceptance criteria

1. **Given** a signed-in admin or project manager, **when** the sidebar renders, **then** the section "Planung" [planning] lists "Übersicht" [overview] (`/dashboard`), "Ressourcenplanung" [resource planning] (`/plan`), "Projekte" [projects] (`/projects`) and "Team" (`/team`).
2. **Given** a person with only the employee role, **when** the sidebar renders, **then** only "Ressourcenplanung" and "Projekte" show. These are the routes in `VIEWER_ROUTES`. "Übersicht" and "Team" need edit rights.
3. **Given** a project manager, **when** the sidebar renders, **then** all four planning pages and the section "Freie Kapazität" [free capacity] show, but the section "Administration" does not. [DASH-15](./portfolio-capacity.md#dash-15) describes the free capacity section.
4. **Given** an admin, **when** the sidebar renders, **then** the section "Administration" shows "Benutzer" [users], "Rollen" [roles], "Tagessätze" [daily rates], "Abteilungen" [departments] and "Feiertage" [public holidays]. The `requires_admin` component of `appkit_user` guards this section.
5. **Given** the person is on the homepage "/" or "/index", **when** the sidebar marks the active item, **then** "Ressourcenplanung" gets `aria-current="page"`. On every other route, an item is marked only when the route matches exactly.
6. **Given** the person clicks a navigation item, **when** the app follows the link, **then** the loading bar at the top of the window starts, because the item calls `LoadingState.set_is_loading(True)`. (no test)

### Evidence

- [app/components/sidebar.py](../../app/components/sidebar.py): `sidebar`, `PLANNING_ITEMS`, `ADMIN_ITEMS`, `VIEWER_ROUTES`, `_guarded_nav_item`, `_nav_item`, `_capacity_section`, `_admin_section`, `is_route_active`
- [components/alloq-commons/src/alloq_commons/access.py](../../components/alloq-commons/src/alloq_commons/access.py): `viewer_only`, `editor_only`
- [components/alloq-commons/src/alloq_commons/components/shell.py](../../components/alloq-commons/src/alloq_commons/components/shell.py): `_loading_bar`
- Tests: [tests/test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarComponent.test_renders_navigation_entries`, `test_employees_see_only_planning_and_projects`, `test_project_managers_see_every_planning_page`, `test_administration_stays_admin_only`, `test_homepage_highlights_planning_navigation`

### Open questions

- `/team` and `/dashboard` need edit rights, so an employee does not see them. Is this the intended experience for employees?
- The sidebar came with the macOS style window in v2.0.0. The filter for employees came in v2.0.4.

## AUTH-12 Sidebar counters {#auth-12}

The sidebar shows how many projects are open and how many employees exist.

As a project manager, I want counters next to "Projekte" and "Team" in the sidebar, so that I see the size of the portfolio and the team at a glance.

Project manager · Find my way in the app / Navigate by access level · priority 2 · comfort · v2.0.0

### Acceptance criteria

1. **Given** an admin or a project manager, **when** the sidebar mounts, **then** `SidebarState.load` counts the projects whose state is not completed and all employees. "Projekte" shows the first number and "Team" the second.
2. **Given** a person without edit rights, **when** `SidebarState.load` is called, **then** the `@requires_editor` guard refuses it and no database query runs.
3. **Given** the counts were loaded less than 30 seconds ago, **when** the sidebar mounts again after a page change, **then** the counts are not loaded again (`REFRESH_SECONDS = 30.0`).
4. **Given** `SidebarState.invalidate` ran, **when** the sidebar mounts next, **then** the counts are loaded again.
5. **Given** a counter is 0, **when** the navigation item renders, **then** no number shows. (no test)

### Evidence

- [app/components/sidebar_state.py](../../app/components/sidebar_state.py): `SidebarState`, `SidebarState.load`, `SidebarState.invalidate`, `count_open_projects`, `count_employees`, `REFRESH_SECONDS`
- [app/components/sidebar.py](../../app/components/sidebar.py): `_COUNTS`, `_nav_item`, `sidebar`
- Tests: [tests/test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarStateLoad.test_load_counts_open_projects_and_employees`, `test_non_admin_is_refused`, `test_recent_data_is_not_reloaded`, `test_invalidate_forces_reload`

### Open questions

- No code in the repository calls `SidebarState.invalidate`, only the tests do. So after a person creates a project or an employee, the counters can be up to 30 seconds old. Should the project and team handlers call it?

## AUTH-14 Hide the sidebar {#auth-14}

People can hide the sidebar with a button or a keyboard shortcut.

As an employee, I want to hide the sidebar, so that the planning grid gets more room.

Employee · Find my way in the app / Arrange the window · priority 1 · comfort · v2.0.0

### Acceptance criteria

1. **Given** a window at least 768 px wide, **when** the person presses ⌃⌘S, ⌘\\ or Ctrl+\\, or clicks the button "Seitenleiste ausblenden (⌃⌘S)" [hide sidebar], **then** the sidebar hides or shows again. The app stores the choice in `sessionStorage` under the key "alloq.sidebar.collapsed".
2. **Given** the sidebar is hidden, **when** the person clicks the button "Seitenleiste einblenden (⌃⌘S)" [show sidebar] in the page toolbar, **then** the sidebar shows again.
3. **Given** the page loads again in the same browser tab, **when** the head script runs, **then** the hidden state comes back before the page first paints.
4. **Given** a window narrower than 768 px, **when** the person toggles the sidebar, **then** the sidebar opens as a drawer over the page, and a click on the backdrop closes it.

### Evidence

- [components/alloq-commons/src/alloq_commons/components/shell.py](../../components/alloq-commons/src/alloq_commons/components/shell.py): `SIDEBAR_SCRIPT`, `STORAGE_KEY`, `NARROW_PX`, `app_layout`
- [components/alloq-commons/src/alloq_commons/components/toolbar.py](../../components/alloq-commons/src/alloq_commons/components/toolbar.py): `sidebar_reveal_button`
- [app/components/sidebar.py](../../app/components/sidebar.py): `_window_row`
- [app/app.py](../../app/app.py): `SIDEBAR_SCRIPT` in the head scripts
- Tests: [components/alloq-commons/tests/test_shell.py](../../components/alloq-commons/tests/test_shell.py) `TestSidebarScript.test_binds_control_command_s_and_command_backslash`, `test_restores_and_persists_collapsed_state`, `test_narrow_window_uses_drawer`, `TestWindowToolbar.test_reveal_button_toggles_sidebar`

## AUTH-04 Change profile and password {#auth-04}

Every signed-in person can see their account details and change their password.

As an employee, I want a profile page with my account details and a form to change my password, so that I can keep my account up to date.

Employee · Manage my account / Change profile and password · priority 1 · comfort · v0.2.0

### Acceptance criteria

1. **Given** any signed-in person, **when** they open `/profile`, **then** the page opens in the app window with the toolbar title "Profil" [profile] and the subtitle "Kontoeinstellungen und Passwort" [account settings and password]. The page checks only the session and no role. (no test)
2. **Given** the profile page, **when** it renders, **then** it shows "Name" and "E-Mail / Benutzername" [email or user name] as read-only fields, and the status rows "Administrator", "Aktiv" [active] and "Verifiziert" [verified]. (no test)
3. **Given** the person changes their password, **when** the new password breaks the policy (12 characters with upper case, lower case, digit and special character) or the two entries differ, **then** an error toast appears and nothing is saved. On success, the app clears the fields and an info toast asks the person to sign in again. (no test)
4. **Given** a signed-in person opens the user menu in the sidebar, **when** they click "Profil", **then** the app opens `/profile`.

### Evidence

- [app/pages/profile.py](../../app/pages/profile.py): `create_profile_page`, `_profile_page`
- [app/app.py](../../app/app.py): `create_profile_page(sidebar())`
- [app/components/sidebar.py](../../app/components/sidebar.py): `_user_menu`
- `appkit_user.user_management.components.user_profile`: `user_profile_view`
- `appkit_user.user_management.states.profile_states`: `ProfileState.handle_password_update`
- Tests: [tests/test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarComponent.test_user_menu_exposes_color_mode_options`

### Open questions

- The toasts for a password change come from `appkit_user` in English, e.g. "Password updated successfully. Please sign in again." The rest of the app is German. Is this intended?
- No Alloq test covers `/profile`. The sidebar test checks only the menu labels.

## AUTH-13 User menu {#auth-13}

The user menu at the bottom of the sidebar opens the profile, sets the appearance and signs the person out.

As an employee, I want a user menu with my name, the appearance setting and sign-out, so that I can manage my session from any page.

Employee · Manage my account / Use the user menu · priority 1 · comfort · v2.0.0

### Acceptance criteria

1. **Given** a signed-in person, **when** the sidebar renders, **then** the bottom shows "Version &lt;n&gt;" with the version from the app configuration. Below it is a button with the avatar, name and email of the person, with the label "Benutzermenü" [user menu].
2. **Given** the person opens the menu, **when** it shows, **then** it offers "Profil", the group "Darstellung" [appearance] with "Dunkel" [dark], "Hell" [light] and "System", and "Abmelden" [sign out]. The active appearance has a check mark.
3. **Given** the web app, **when** the person clicks "Abmelden", **then** `LoginState.logout` ends the session. (no test)
4. **Given** the desktop app, **when** the person clicks "Abmelden", **then** `DesktopLoginState.sign_out` runs instead. It also forgets the Microsoft account and its database connections, see [DESK-06](./desktop.md#desk-06). (no test)

### Evidence

- [app/components/sidebar.py](../../app/components/sidebar.py): `_user_menu`, `_user_button`, `_color_mode_item`, `_version`, `SIGN_OUT`
- Tests: [tests/test_sidebar.py](../../tests/test_sidebar.py) `TestSidebarComponent.test_sidebar_shows_version_above_user_menu`, `test_user_menu_exposes_color_mode_options`

### Open questions

- The version line came in v2.0.4 (commit 8635267). The rest of the menu came in v2.0.0.
