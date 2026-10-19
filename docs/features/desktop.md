---
title: Desktop app
description: How people start the alloq desktop app on a Mac, sign in with Microsoft, work with the central database under their own identity, and how admins and developers set up, build and test the app.
story_ids: [DESK-09, DESK-10, DESK-08, DESK-01, DESK-02, DESK-03, DESK-05, DESK-06, DESK-04, DESK-07, DESK-11, DESK-12]
source_paths:
  - app/__init__.py
  - app/app.py
  - app/desktop/config.py
  - app/desktop/entra.py
  - app/desktop/login_state.py
  - app/desktop/schema.py
  - app/desktop/profile.py
  - app/desktop/fake.py
  - app/desktop/db_access.py
  - app/desktop/db_access_state.py
  - app/components/db_access_button.py
  - app/components/sidebar.py
  - app/pages/login.py
  - app/pages/users.py
  - components/alloq-commons/src/alloq_commons/desktop.py
  - components/alloq-commons/src/alloq_commons/components/splash.py
  - components/alloq-commons/src/alloq_commons/components/shell.py
  - assets/css/aq-splash.css
  - configuration/config.desktop.yaml
  - configuration/config.desktop_fake.yaml
  - alembic/versions/2026_10_15_desktop_database_role.py
  - rxconfig.py
  - scripts/desktop.py
  - taskfiles/Taskfile.reflex.yml
  - tauri/src-tauri/tauri.conf.json
  - tauri/src-tauri/src/main.rs
  - tauri/src-tauri/src/app_menu.rs
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Desktop app

This page covers the alloq desktop app for macOS. The app is a native window with its own embedded backend. People sign in with their Microsoft account, and every database connection uses their own Microsoft Entra ID token. The stories belong to the activity "Use the desktop app" on the [story map](./story-map.md).

The activity has these user tasks and sub-tasks:

- **Start the desktop app.** Open the native window, use the desktop settings without any setup, and see a splash screen while the backend starts.
- **Sign in on the desktop.** Sign in with Microsoft, get a clear message when the account or the database does not fit, keep the account after a restart, and sign out.
- **Work with the central database.** Connect to Postgres with your own token, which the app renews in the background.
- **Set up desktop access.** Grant database access to users, build the app without secrets, and test the app locally with a faked sign-in.

After the sign-in, desktop users see the same pages as in the browser. The mechanism behind this page is in [Desktop app architecture](../architecture/desktop.md): how the app runs, the sign-in flow, the token renewal, the schema check, the database role and the build. This page does not repeat it. The web sign-in is on [Sign in and find your way](./sign-in.md).

## DESK-09 Native window with embedded backend {#desk-09}

The desktop app is a native macOS window that starts its own backend.

As a desktop user, I want alloq as a native app window, so that I can start it like any other Mac app.

Desktop user · Start the desktop app / Start the desktop app · priority 1 · core · v2.0.0

### Acceptance criteria

1. **Given** the app starts, **when** the window opens, **then** the window is titled "alloq", is 1440 x 900 pixels, is at least 1100 x 700 pixels, is centered, and has an overlay title bar with the window buttons at x 16, y 26. (no test)
2. **Given** the app is already running, **when** the user starts it again, **then** the running window gets the focus, because the shell uses the single instance plugin. (no test)
3. **Given** another program uses the port 127.0.0.1:18442, **when** the app starts, **then** a native error dialog says that the app could not start because the port is in use, and the app exits. (no test)
4. **Given** a bundled app, **when** it starts, **then** it copies the app payload to a writable folder of the user. It copies the payload again when the payload stamp differs, and it keeps the runtime state of the backend. (no test)
5. **Given** macOS, **when** the user chooses "Über alloq" [about alloq] in the app menu, **then** a native About panel shows the version, the copyright, the text "Ressourcenplanung für Softwareteams" [resource planning for software teams] and a link to the repository. (no test)
6. **Given** the bundled backend, **when** a client opens the event socket, **then** CORS allows only `tauri://localhost`, `http://tauri.localhost` and `http://127.0.0.1:18442`. Outside the bundle the Reflex default applies.

### Evidence

- [tauri.conf.json](../../tauri/src-tauri/tauri.conf.json): `productName`, `app.windows` (label `main`)
- [main.rs](../../tauri/src-tauri/src/main.rs): `main` (`tauri_plugin_single_instance`, port check and error dialog), `BACKEND_PORT`, `port_available`, `ensure_writable_app_root`, `PAYLOAD_STAMP`, `spawn_backend`
- [app_menu.rs](../../tauri/src-tauri/src/app_menu.rs): `build_menu`, `about::show`
- [rxconfig.py](../../rxconfig.py): `desktop_plugins`, `cors_origins`, `TAURI_ORIGINS`, `DESKTOP_PORT`
- Tests: [test_desktop_login.py](../../tests/test_desktop_login.py) `TestProfile.test_bundle_allows_only_the_webview`

### Open questions

- `tauri.conf.json` and `Cargo.toml` carry the version 0.4.4, while the app is at v2.0.4. Which version does the About panel show in a release build?
- The Rust shell has no automated tests.

## DESK-10 Desktop configuration profile {#desk-10}

The desktop app switches on its own configuration profile before the app loads.

As a desktop user, I want the app to use the desktop settings automatically, so that it connects to the central database without any setup on my Mac.

Desktop user · Start the desktop app / Start the desktop app · priority 2 · core · v2.0.0

### Acceptance criteria

1. **Given** `ALLOQ_DESKTOP=1` is set or `REFLEX_DESKTOP_APP_ROOT` exists (the Tauri host sets it), **when** the app checks whether it is the desktop app, **then** `is_desktop()` is true.
2. **Given** the desktop app, **when** `app/__init__.py` runs before `configure()`, **then** `activate_desktop_profile` adds "desktop" as the last entry of `PROFILES`, so it overrides every server value. A second call adds nothing.
3. **Given** the app runs inside the bundle, **when** it prepares the backend, **then** `REFLEX_BACKEND_ONLY` defaults to true, because the bundle serves a frontend that was built before.
4. **Given** the web build, **when** `rxconfig.py` builds the Reflex config, **then** it adds no desktop plugin.
5. **Given** the desktop profile, **when** it is loaded, **then** it sets the backend port 18442, no OAuth providers and an empty encryption key.

### Evidence

- [desktop.py](../../components/alloq-commons/src/alloq_commons/desktop.py): `is_desktop`, `DESKTOP_ENV`, `DESKTOP_ROOT_ENV`
- [profile.py](../../app/desktop/profile.py): `is_desktop`, `in_bundle`, `activate_desktop_profile`, `prepare_embedded_backend`
- [app/\_\_init\_\_.py](../../app/__init__.py): calls `activate_desktop_profile` and `prepare_embedded_backend`
- [rxconfig.py](../../rxconfig.py): `desktop_plugins`
- [config.desktop.yaml](../../configuration/config.desktop.yaml): `reflex.backend_port`, `app.authentication.oauth_providers`, `app.database.encryption_key`
- Tests: [test_desktop_login.py](../../tests/test_desktop_login.py) `TestProfile.test_embedded_runtime_counts_as_desktop`, `TestProfile.test_desktop_profile_is_added_last`, `TestProfile.test_embedded_backend_runs_backend_only`, `TestProfile.test_web_build_has_no_desktop_plugin`, `TestProfile.test_desktop_profile_ships_no_secrets`

## DESK-08 Splash screen {#desk-08}

While the embedded backend starts, the desktop app shows a splash screen.

As a desktop user, I want a splash screen while the app starts, so that I do not see connection warnings or an empty window.

Desktop user · Start the desktop app / Start the desktop app · priority 3 · comfort · v2.0.0

### Acceptance criteria

1. **Given** the desktop build, **when** a page registered with `app_page` or the login page loads, **then** `SplashState.finish` is the last `on_load` handler. The web build keeps its handlers.
2. **Given** `SplashState.finish` ran once, **when** the user changes pages, **then** `ready` stays true for the whole session, so the splash does not show again.
3. **Given** the splash is visible, **when** Reflex shows connection warnings, **then** `aq-splash.css` hides the toasts and the "Connection Error" element. The splash shows the app icon, the name "alloq" and a progress bar with the label "Wird geladen" [loading].
4. **Given** `ready` becomes true, **when** the splash hides, **then** it fades out over 450 ms (`FADE_MS`) and then takes no more clicks. (no test)

### Evidence

- [splash.py](../../components/alloq-commons/src/alloq_commons/components/splash.py): `SplashState`, `SplashState.finish`, `splash`, `_progress_bar`, `FADE_MS`
- [shell.py](../../components/alloq-commons/src/alloq_commons/components/shell.py): `desktop_handlers`, `app_page`
- [aq-splash.css](../../assets/css/aq-splash.css)
- [login.py](../../app/pages/login.py): `create_login_page`, `login_view`
- Tests: [test_shell.py](../../components/alloq-commons/tests/test_shell.py) `TestDesktop.test_desktop_pages_end_by_hiding_the_splash`, `TestDesktop.test_web_pages_keep_their_handlers`, `TestDesktop.test_splash_state`, `TestDesktop.test_splash_hides_connection_warnings`

## DESK-01 Microsoft sign-in only {#desk-01}

In the desktop app people sign in with their Microsoft account only.

As a desktop user, I want to sign in with my Microsoft account, so that the app can open the central database with my own identity.

Desktop user · Sign in on the desktop / Sign in on the desktop · priority 1 · core · v2.0.0

### Acceptance criteria

1. **Given** the desktop build, **when** the login page renders, **then** it shows the splash, the text "Melde dich mit deinem Microsoft-Konto an. Die Anmeldung öffnet sich im Browser." [sign in with your Microsoft account, the sign-in opens in the browser] and the button "Mit Microsoft anmelden" [sign in with Microsoft]. It shows no password form.
2. **Given** a Microsoft account is in the token cache, **when** the user clicks "Mit Microsoft anmelden", **then** the app signs in silently without a browser. Only without a cached account does it open the system browser.
3. **Given** the browser sign-in, **when** it runs, **then** MSAL uses the public client with PKCE, the prompt "select_account" and a timeout of 300 seconds (`sign_in_timeout`). No client secret is sent.
4. **Given** a sign-in is already running (`is_loading` is true), **when** the user clicks the button again, **then** the second click does nothing. (no test)
5. **Given** the Microsoft sign-in succeeds, **when** the alloq session is created, **then** the app closes the old pooled connections, creates the appkit session and redirects to the requested page, or else to the homepage.
6. **Given** `tenant_id` or `client_id` is empty or still a placeholder that starts with "&lt;", **when** the user signs in, **then** the app shows "Die Desktop-App ist nicht eingerichtet: Mandant und Client-ID fehlen in configuration/config.desktop.yaml." [the desktop app is not set up, tenant and client ID are missing].

### Evidence

- [login.py](../../app/pages/login.py): `_desktop_sign_in`, `_card_content`, `login_view`
- [login_state.py](../../app/desktop/login_state.py): `DesktopLoginState.sign_in_with_microsoft`, `microsoft_account`, `get_sign_in`, `reset_connections`
- [entra.py](../../app/desktop/entra.py): `EntraSignIn._app`, `EntraSignIn.sign_in_silently`, `EntraSignIn.sign_in_interactively`
- [config.py](../../app/desktop/config.py): `DesktopConfig`, `DesktopConfig.configured`, `POSTGRES_SCOPE`
- [config.desktop.yaml](../../configuration/config.desktop.yaml): `app.desktop`
- Tests: [test_login_page.py](../../tests/test_login_page.py) `test_desktop_variant_signs_in_with_microsoft_only`; [test_desktop_login.py](../../tests/test_desktop_login.py) `TestMicrosoftAccount.test_cached_account_skips_the_browser`, `TestMicrosoftAccount.test_browser_when_nothing_is_cached`, `TestSignInFlow.test_opens_the_alloq_session`; [test_desktop_entra.py](../../tests/test_desktop_entra.py) `TestSignIn.test_public_client_without_secret`, `TestConfig.test_placeholders_are_not_configured`, `TestConfig.test_unconfigured_app_refuses_sign_in`

### Open questions

- The tag v2.0.0 was created on 2026-10-15, before v0.4.5 and v1.0.0 (2026-10-16), and all three tags contain the desktop commit `e7b3977`. Is v2.0.0 the right slice for the desktop stories?

## DESK-02 Only known, active users {#desk-02}

The desktop sign-in opens a session only for a known, active alloq user.

As a desktop user, I want a clear message when my Microsoft account has no usable alloq account, so that I know whom to ask.

Desktop user · Sign in on the desktop / Sign in on the desktop · priority 2 · core · v2.0.0

### Acceptance criteria

1. **Given** a Microsoft account, **when** the app looks up the alloq user, **then** it compares the email address without regard to case.
2. **Given** no alloq user has that email, **when** the sign-in continues, **then** it stops with "Für &lt;email&gt; gibt es kein alloq-Konto. Bitte wende dich an eine Administratorin oder einen Administrator." [there is no alloq account for this email, please ask an admin]. The desktop app does not create users.
3. **Given** the alloq user is inactive or not verified, **when** the sign-in continues, **then** it stops with "Dein alloq-Konto ist deaktiviert." [your alloq account is deactivated] or "Dein alloq-Konto ist noch nicht freigeschaltet." [your alloq account is not yet approved].
4. **Given** Microsoft returns no access token, **when** the app reads the result, **then** it shows "Die Anmeldung bei Microsoft ist fehlgeschlagen." [the Microsoft sign-in failed] followed by the error description.
5. **Given** the Microsoft account has no `preferred_username` and no `email` claim, **when** the app reads the result, **then** it shows "Das Microsoft-Konto liefert keine E-Mail-Adresse." [the Microsoft account gives no email address].
6. **Given** any other error, **when** the sign-in fails, **then** it shows "Anmeldung fehlgeschlagen. Bitte versuche es erneut." [sign-in failed, please try again] and logs the exception.

### Evidence

- [login_state.py](../../app/desktop/login_state.py): `find_user`, `allowed_user`, `NO_ACCOUNT`, `STATUS_MESSAGES`, `FAILED`, `DesktopLoginState.sign_in_with_microsoft`
- [entra.py](../../app/desktop/entra.py): `_account`, `SignInError`
- Tests: [test_desktop_login.py](../../tests/test_desktop_login.py) `test_find_user_ignores_case`, `TestSignInFlow.test_unknown_user`, `TestSignInFlow.test_inactive_user`, `TestSignInFlow.test_microsoft_error_is_shown`, `TestSignInFlow.test_unexpected_error`; [test_desktop_entra.py](../../tests/test_desktop_entra.py) `TestSignIn.test_failed_sign_in_shows_the_reason`, `TestSignIn.test_account_without_email`

## DESK-03 Refuse a wrong schema version {#desk-03}

The desktop app refuses the sign-in when the database schema does not match its version.

As a desktop user, I want the app to stop at sign-in when it does not fit the database schema, so that an old app never writes to a newer database.

Desktop user · Sign in on the desktop / Sign in on the desktop · priority 3 · core · v2.0.0

### Acceptance criteria

1. **Given** the `alembic_version` of the database equals the newest known revision, **when** the sign-in checks the schema, **then** the check passes.
2. **Given** the database has an older known revision, **when** the sign-in checks the schema, **then** it stops with "Die Datenbank hat den älteren Stand &lt;rev&gt;, diese App braucht &lt;rev&gt;. Die Migration auf dem Server steht noch aus." [the database has the older revision, this app needs the newer one, the migration on the server is still pending].
3. **Given** the database has an unknown revision or none, **when** the sign-in checks the schema, **then** it stops with "Die Datenbank hat den Stand &lt;rev&gt;, den diese App nicht kennt. Bitte die App aktualisieren." [the database has a revision this app does not know, please update the app]. Without a revision the text says "unbekannt" [unknown].
4. **Given** the schema does not match, **when** the sign-in ends, **then** the app creates no session and shows the message on the login card.
5. **Given** a developer adds a migration, **when** the tests run, **then** `KNOWN_REVISIONS` must equal the Alembic history, newest first.

### Evidence

- [schema.py](../../app/desktop/schema.py): `schema_problem`, `KNOWN_REVISIONS`, `EXPECTED_REVISION`
- [login_state.py](../../app/desktop/login_state.py): `allowed_user`
- Tests: [test_desktop_login.py](../../tests/test_desktop_login.py) `TestSchema.test_matching_schema`, `TestSchema.test_mismatch_says_which_side_is_behind`, `TestSignInFlow.test_schema_mismatch_stops_sign_in`, `TestSchema.test_known_revisions_are_the_alembic_history`

## DESK-05 Restore the account from the Keychain {#desk-05}

After a restart the desktop app restores the Microsoft account from the macOS Keychain.

As a desktop user, I want the app to remember my Microsoft account, so that I do not sign in again after every start.

Desktop user · Sign in on the desktop / Sign in on the desktop · priority 4 · comfort · v2.0.0

### Acceptance criteria

1. **Given** macOS, **when** the app builds its token cache, **then** the cache is encrypted in the Keychain under the service "alloq" and the account "entra-token-cache". Other systems use the encrypted store of the operating system.
2. **Given** no account is signed in in this process, **when** a database connection is needed, **then** `restore()` tries the cached account silently and never opens a browser.
3. **Given** a restore attempt ran, **when** another connection is needed within 30 seconds (`RESTORE_INTERVAL`), **then** the app makes no new attempt.
4. **Given** the app is not set up, **when** `restore()` runs, **then** it returns no account instead of raising an error.

### Evidence

- [entra.py](../../app/desktop/entra.py): `token_cache`, `KEYCHAIN_SERVICE`, `KEYCHAIN_ACCOUNT`, `EntraSignIn.restore`, `RESTORE_INTERVAL`, `connect_params`
- Mechanism: [Token renewal and restart](../architecture/desktop.md#token-renewal-and-restart)
- Tests: [test_desktop_entra.py](../../tests/test_desktop_entra.py) `test_token_cache_uses_keychain_on_macos`, `TestConnectParams.test_cached_account_is_restored_for_a_connection`, `TestConnectParams.test_restore_is_throttled`, `TestConnectParams.test_restore_without_configuration`

### Open questions

- `doc/desktop.md` says that the user continues without the sign-in page while the alloq session is still valid. That depends on the session timeout of appkit, and no alloq test checks it.

## DESK-06 Sign out on the desktop {#desk-06}

Signing out of the desktop app also forgets the Microsoft account and closes the database connections.

As a desktop user, I want sign-out to remove my Microsoft account from this Mac, so that the next person cannot use my database access.

Desktop user · Sign in on the desktop / Sign out on the desktop · priority 1 · core · v2.0.0

### Acceptance criteria

1. **Given** the desktop app, **when** the user clicks "Abmelden" [sign out] in the [user menu](./sign-in.md#auth-13), **then** `DesktopLoginState.sign_out` runs instead of `LoginState.logout`. It ends the appkit session and returns the redirect of the appkit logout.
2. **Given** the sign-out, **when** it runs, **then** the app removes the Microsoft account from the token cache, drops the token and stops the refresh timer.
3. **Given** the sign-out, **when** it runs, **then** the app closes all pooled database connections, because they carry the identity of the previous user.
4. **Given** the account was signed out, **when** the refresh timer would fire, **then** no refresh runs.

### Evidence

- [login_state.py](../../app/desktop/login_state.py): `DesktopLoginState.sign_out`, `reset_connections`
- [entra.py](../../app/desktop/entra.py): `EntraSignIn.sign_out`, `EntraSignIn._refresh_in_background`
- [sidebar.py](../../app/components/sidebar.py): `SIGN_OUT`
- Tests: [test_desktop_login.py](../../tests/test_desktop_login.py) `TestSignOut.test_forgets_account_and_connections`, `TestResetConnections.test_closes_pools`; [test_desktop_entra.py](../../tests/test_desktop_entra.py) `TestSignIn.test_sign_out_forgets_cached_accounts`, `TestBackgroundRefresh.test_no_refresh_after_sign_out`

## DESK-04 Own Entra token per connection {#desk-04}

Every database connection of the desktop app uses the Entra token of the person who signed in.

As a desktop user, I want the app to connect to Postgres with my own token, so that no shared database password ships with the app.

Desktop user · Work with the central database / Work with the central database · priority 1 · core · v2.0.0

### Acceptance criteria

1. **Given** the desktop build with the real Microsoft sign-in (not the fake one), **when** `app/app.py` loads, **then** `install_db_auth` registers a `do_connect` listener once. A later call only swaps the sign-in object.
2. **Given** a signed-in account, **when** a new database connection opens, **then** the user name is `db_role`, or the email when `db_role` is empty, and the password is the access token.
3. **Given** nobody is signed in and no account can be restored, **when** a connection is attempted, **then** it fails with `NotSignedInError`.
4. **Given** a cached token, **when** it expires in more than 60 seconds (`EXPIRY_SLACK`), **then** the app reuses it. Otherwise a silent refresh runs.
5. **Given** a token was issued, **when** the app keeps it, **then** a background thread renews it 300 seconds before it expires (`REFRESH_MARGIN`), but not earlier than after 60 seconds. When the renewal fails, it tries again after 60 seconds (`RETRY_SECONDS`). When Entra gives no lifetime, the app assumes 3600 seconds.
6. **Given** a refresh fails, **when** `access_token` is called, **then** it raises `NotSignedInError` but keeps the account, so the next connection tries again.
7. **Given** the desktop profile, **when** the database settings load, **then** user name and password are empty, `ssl_mode` is `require`, `pool_size` is 2 and `max_overflow` is 3. (no test)

### Evidence

- [entra.py](../../app/desktop/entra.py): `install_db_auth`, `connect_params`, `_account` (`db_user`), `EntraSignIn.access_token`, `EntraSignIn._remember`, `EntraSignIn._refresh_in_background`, `NotSignedInError`, `EXPIRY_SLACK`, `REFRESH_MARGIN`, `RETRY_SECONDS`, `TOKEN_LIFETIME_FALLBACK`
- [app.py](../../app/app.py): `install_db_auth(sign_in)` when `get_sign_in()` is an `EntraSignIn`
- [config.py](../../app/desktop/config.py): `DesktopConfig.db_role`, `POSTGRES_SCOPE`
- [config.desktop.yaml](../../configuration/config.desktop.yaml): `app.database`
- Mechanism: [Sign-in flow](../architecture/desktop.md#sign-in-flow)
- Tests: [test_desktop_entra.py](../../tests/test_desktop_entra.py) `TestConnectParams.test_install_registers_once_and_swaps_provider`, `TestConnectParams.test_user_and_token_as_password`, `TestSignIn.test_group_role_is_the_database_user`, `TestConnectParams.test_no_connection_before_sign_in`, `TestAccessToken.test_cached_token_until_shortly_before_expiry`, `TestBackgroundRefresh.test_renewal_is_scheduled_before_expiry`, `TestBackgroundRefresh.test_failed_refresh_retries_soon`, `TestAccessToken.test_failed_refresh_keeps_the_account`

## DESK-07 Grant database access {#desk-07}

In the desktop app a database admin gives or takes away the database access of a user on the users page.

As an administrator, I want to grant and revoke the database access of a user from the users page of the desktop app, so that new colleagues can use the desktop app without database commands.

Administrator · Set up desktop access / Grant database access · priority 1 · core · v2.0.0 (approximate)

The users page itself is in [ADM-01 Manage users](./users-and-access.md#adm-01). The database role and the setup in Azure are in [Database access for desktop users](../architecture/desktop.md#database-access-for-desktop-users).

### Acceptance criteria

1. **Given** the users page `/admin/users`, **when** it renders in the desktop app, **then** each row gets the button "Datenbankzugriff" [database access]. The web app shows no such button.
2. **Given** an alloq admin opens the users page, **when** `DatabaseAccessState.load` (`@requires_admin`) runs, **then** in the desktop app it reads whether the signed-in login may manage the role `<database>_app` and which logins hold the role. On the server it does nothing. On an error the switch is locked and the list is empty.
3. **Given** the signed-in login holds the role with ADMIN OPTION, **when** the admin clicks the button of a user without access, **then** the app finds the login of the user (an exact name wins over a match that ignores case). If the login is missing, it creates the Entra principal in the database "postgres". Then it grants the role and shows "Datenbankzugriff für &lt;email&gt; vergeben." [database access granted].
4. **Given** the user already has access, **when** the admin clicks the button, **then** the app revokes the role and shows "Datenbankzugriff für &lt;email&gt; entzogen." [database access revoked]. A user without a login stays unchanged.
5. **Given** the signed-in login lacks ADMIN OPTION, **when** the button renders, **then** it is disabled and its tooltip says "Hat Datenbankzugriff (ändern nur mit Admin-Rechten in der Datenbank)" [has access, change only with admin rights in the database] or "Kein Datenbankzugriff (geben nur mit Admin-Rechten in der Datenbank)" [no access, grant only with admin rights in the database]. A direct call of `toggle` is ignored. With ADMIN OPTION the tooltip says "Datenbankzugriff geben" [grant database access] or "Datenbankzugriff entziehen" [revoke database access].
6. **Given** the grant or revoke fails, **when** the toggle ends, **then** a known error shows its own message, e.g. "Dir fehlen die Admin-Rechte in der Datenbank. ..." [you lack admin rights in the database] or "Für &lt;email&gt; ließ sich kein Datenbank-Benutzer anlegen. ..." [no database user could be created for this email]. Any other error shows "Der Datenbankzugriff ließ sich nicht ändern. Bitte versuche es erneut." [the database access could not be changed, please try again].
7. **Given** a toggle is running or the email is empty, **when** another toggle arrives, **then** it is ignored. The running row shows a loading spinner, and a green icon means that the user has access.
8. **Given** the server runs the migration `ee66ff77aa88` on PostgreSQL, **when** it upgrades, **then** it creates the NOLOGIN role `<database>_app` with read and write rights on all tables and sequences, also for later tables, and does not touch `azure_pg_admin`. On other databases it does nothing.

### Evidence

- [users.py](../../app/pages/users.py): `row_actions`, `create_users_page`
- [db_access_button.py](../../app/components/db_access_button.py): `database_access_button`
- [db_access_state.py](../../app/desktop/db_access_state.py): `DatabaseAccessState.load`, `DatabaseAccessState.toggle`, `DatabaseAccessState.locked`, `get_access`, `FAILED`
- [db_access.py](../../app/desktop/db_access.py): `DatabaseAccess.overview`, `DatabaseAccess.grant`, `DatabaseAccess.revoke`, `DatabaseAccess._create_principal`, `MAINTENANCE_DATABASE`, `NOT_ADMIN`, `NO_PRINCIPAL`, `quote_identifier`, `maintenance_connection`
- [2026_10_15_desktop_database_role.py](../../alembic/versions/2026_10_15_desktop_database_role.py): `_CREATE_ROLE`, `_DROP_ROLE`, `upgrade`
- Tests: [test_users_page.py](../../tests/test_users_page.py) `TestUsersPage.test_database_access_button_only_in_the_desktop_app`; [test_desktop_db_access.py](../../tests/test_desktop_db_access.py) `TestDatabaseAccessState.test_load_in_the_desktop_app`, `TestDatabaseAccessState.test_load_on_the_server_does_nothing`, `TestDatabaseAccessState.test_load_failure_locks_the_switch`, `TestDatabaseAccessState.test_load_needs_an_alloq_admin`, `TestDatabaseAccess.test_grant_uses_the_existing_principal`, `TestDatabaseAccess.test_grant_creates_a_missing_principal`, `TestDatabaseAccessState.test_toggle_grants`, `TestDatabaseAccessState.test_toggle_revokes_a_member`, `TestDatabaseAccess.test_revoke_without_principal_does_nothing`, `TestDatabaseAccessState.test_toggle_without_db_admin_rights`, `TestDatabaseAccessState.test_toggle_shows_the_access_error`, `TestDatabaseAccessState.test_toggle_hides_unexpected_errors`, `TestDatabaseAccessState.test_toggle_ignores_users_without_email`, `TestRoleMigration.test_only_postgresql_has_roles`, `TestRoleMigration.test_leaves_azure_system_role_unchanged`

### Open questions

- `db_access.py` came with commit `5a4b495` (first tag v2.0.0), but the role migration came with `f0e0bce` (first tag v0.4.5). Which slice is right?

## DESK-11 Ship no secrets {#desk-11}

The desktop build ships only public identifiers and never a secret.

As an administrator, I want the desktop build to stop when a secret would ship with the app, so that no password or key leaves the build machine.

Administrator · Set up desktop access / Build and ship the desktop app · priority 1 · core · v2.0.0

The manual setup in Azure and Postgres is described in [Setup in Azure, done once](../architecture/desktop.md#setup-in-azure-done-once). No code checks it.

### Acceptance criteria

1. **Given** `config.desktop.yaml` has a line `key: secret:name`, **when** the build copies the configuration, **then** it resolves the value on the build machine only for `tenant_id`, `client_id`, `host` and `name`, and writes it as a plain value.
2. **Given** any other key uses `secret:`, or `secret:` appears inside a value, **when** the build runs, **then** it stops with `BuildError`.
3. **Given** the build assembles the payload, **when** it copies the configuration, **then** only `config.yaml`, `config.desktop.yaml` and `logging.yaml` go in. The server profiles and `.env` stay out.
4. **Given** a bundled interpreter for another Python version, **when** the build runs, **then** it removes the old runtime and its site-packages.
5. **Given** a developer, **when** they run the desktop tasks, **then** `task desktop:doctor` checks the toolchain, `task desktop:run` builds a debug app and opens it, and `task desktop:build` builds the release app and the macOS installer (.dmg). (no test)

### Evidence

- [desktop.py](../../scripts/desktop.py): `resolve_build_time_values`, `SECRET_LINE`, `BUILD_TIME_KEYS`, `BuildError`, `copy_configuration`, `CONFIG_FILES`, `drop_stale_runtime`
- [Taskfile.reflex.yml](../../taskfiles/Taskfile.reflex.yml): `desktop:doctor`, `desktop:run`, `desktop:build`
- [config.desktop.yaml](../../configuration/config.desktop.yaml): `app.desktop`, `app.database`
- Mechanism: [Build and run](../architecture/desktop.md#build-and-run)
- Tests: [test_desktop_login.py](../../tests/test_desktop_login.py) `TestBuildScript.test_public_ids_are_resolved_at_build_time`, `TestBuildScript.test_other_secrets_stop_the_build`, `TestBuildScript.test_payload_gets_yaml_profiles_only`, `TestBuildScript.test_stale_runtime_is_dropped`

## DESK-12 Run locally with a faked sign-in {#desk-12}

Developers can run the desktop app against the local database with a faked Microsoft sign-in.

As a desktop user who develops alloq, I want to fake the Microsoft sign-in, so that I can test the desktop app against my local database.

Desktop user · Set up desktop access / Test the desktop app locally · priority 1 · comfort · v2.0.0

### Acceptance criteria

1. **Given** `ALLOQ_FAKE_ENTRA_EMAIL=<email>` is set outside the app bundle, **when** the app picks its sign-in, **then** it uses `FakeEntraSignIn`. The fake signs in as that email without a browser and logs a warning. The app then uses the local database credentials of the profile `desktop_fake` and installs no token listener.
2. **Given** the app runs inside the bundle, **when** `ALLOQ_FAKE_ENTRA_EMAIL` is set, **then** the app ignores the variable and does not add the profile `desktop_fake`.
3. **Given** the fake sign-in, **when** the database schema does not match, **then** the app only logs the mismatch as a warning and the sign-in continues.
4. **Given** the desktop build, **when** the payload is assembled, **then** the profile `desktop_fake` is never bundled.
5. **Given** a developer, **when** they run `task desktop:dev`, **then** the app starts with hot reload and the fake sign-in against the local database. (no test)

### Evidence

- [fake.py](../../app/desktop/fake.py): `fake_email`, `FakeEntraSignIn`
- [login_state.py](../../app/desktop/login_state.py): `get_sign_in`, `allowed_user`
- [profile.py](../../app/desktop/profile.py): `FAKE_ENV`, `FAKE_PROFILE`, `activate_desktop_profile`
- [app.py](../../app/app.py): `install_db_auth` only for an `EntraSignIn`
- [config.desktop_fake.yaml](../../configuration/config.desktop_fake.yaml)
- [desktop.py](../../scripts/desktop.py): `CONFIG_FILES`
- [Taskfile.reflex.yml](../../taskfiles/Taskfile.reflex.yml): `desktop:dev`
- Mechanism: [Testing without Microsoft sign-in](../architecture/desktop.md#testing-without-microsoft-sign-in)
- Tests: [test_desktop_fake.py](../../tests/test_desktop_fake.py) `test_get_sign_in_uses_the_fake`, `test_fake_sign_in_returns_the_configured_account`, `test_fake_email_only_outside_the_bundle`, `test_fake_profile_is_never_bundled`; [test_desktop_login.py](../../tests/test_desktop_login.py) `TestProfile.test_fake_profile_only_outside_the_bundle`, `TestSignInFlow.test_fake_sign_in_tolerates_older_schema`

### Open questions

- The real persona of this story is a developer, who is not one of the four personas. Should the story move to the guide pages?
