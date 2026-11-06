# Implement secure PostgreSQL backup and restore in Alloq

## Task

Add an administration feature that exports the complete configured Alloq
PostgreSQL database into an encrypted ZIP and imports such a ZIP to replace the
current database contents. Access requires **both** admin status and an explicit
new backup permission role. Every export and import requires the acting user's
current local Alloq password again. Treat security requirements below as acceptance
criteria, not follow-up work.

## Confirmed product decisions

- Import replaces the configured database contents after explicit overwrite
  confirmation; it does not merge records or select a different target database.
- Microsoft users must also have and verify a local Alloq password. Block backup
  operations until one is set through the existing password-management flow.
  Microsoft reauthentication does not substitute for the local password.
- ZIPs must be encrypted and require a separate backup passphrase on export and
  import. The account password must never become the archive password.

## Repository context

- Follow `AGENTS.md`; load `alloq-implementation` before implementation and the
  relevant Python, Reflex, appkit, and testing skills. The referenced
  `.entire/agent-guide.md` was absent during prompt preparation; read it if present
  when implementation starts.
- Stack observed: Python 3.14, Reflex 0.10.1, appkit 1.18.0, SQLAlchemy, Alembic,
  PostgreSQL, uv, German UI text, and `appkit_mantine as mn`.
- Application roles live in
  `components/alloq-commons/src/alloq_commons/roles.py`; `app/roles.py` reexports
  shared roles. `DepartmentState.load_user_roles` builds the user-management role
  choices from `ALL_ROLES` and department roles. These application permissions are
  distinct from organizational resource roles and PostgreSQL login roles.
- Authorization helpers live in `alloq_commons/access.py`. Existing offer helpers
  have different AND/OR semantics; do not copy an admin-bypass rule for backups.
- Follow existing page factories and registration in `app/pages/`, `app/app.py`,
  and `app/components/sidebar.py`. Shared code belongs in `alloq-commons`; component
  packages must not import the host app.
- Installed appkit exposes `UserEntity.check_password`, the password hash helper,
  and `user_repo.get_login_status_by_credentials`. Inspect the active installed
  version before reuse. Do not invoke `LoginState.login_with_password` for this:
  it terminates/replaces the current login session.
- Database configuration uses external secrets, including
  `common-db-encryption-key`. The current Docker runtime lacks explicit PostgreSQL
  client installation. Local Compose references PostgreSQL 15; detect actual
  server/tool versions instead of assuming a production version.
- Preserve existing worktree changes, including the modified `pyproject.toml`.

## Requirements

### 1. Access and per-action password verification

1. Add `DATABASE_BACKUP_ROLE` with name `database_backup` and German label
   `Datenbanksicherung`, using an unused role identifier. Offer it in existing user
   management. Do not assign it automatically to administrators.
2. Authorize only an active, validly authenticated user with `is_admin` AND the
   explicit role. Apply this to page content, sidebar visibility, event handlers,
   uploads, job/status routes, and downloads. Direct requests must not bypass it.
3. Re-read the current session and user privileges server-side for every sensitive
   operation; cached UI state and client-supplied user identifiers are insufficient.
4. Require the current account password at the final export/import confirmation.
   Verify it against the authenticated user's current local password hash using
   existing cryptography and account-status checks, off the async event loop.
   Missing passwords, forced-reset accounts, wrong passwords, expired sessions,
   and revoked permissions must prevent execution.
5. Verification authorizes one specific action only. Never use a reusable
   `password_confirmed` boolean or time window covering subsequent actions. Any
   required continuation/download capability must be short-lived, single-use,
   server-issued, and bound to the user, session, operation, and immutable artifact.
   An import authorization cannot be reused for another uploaded archive.
6. Rate-limit password attempts with shared server-side state across workers.
   Reuse a suitable existing throttle or add a narrow equivalent. Return generic
   German errors. Never accept another administrator's credentials.
7. Keep passwords/passphrases out of persistent Reflex state, browser storage,
   URLs, logs, traces, exception bodies, and subprocess arguments. Check event and
   request logging explicitly. Clear form inputs after submission or cancellation.

### 2. Export and archive format

1. Use PostgreSQL-native logical backup tooling, with a consistent custom-format
   dump of the configured database. Include all application schemas, data, schema
   definitions, sequences, large objects, database-stored files, authentication
   tables, and Alembic state. Do not substitute ORM/table-by-table exports.
2. Define a versioned archive containing a database dump, manifest, and authenticated
   signature. Record UTC creation time, app/schema versions, PostgreSQL/tool
   versions, dump length/checksum, and a non-secret encryption-key compatibility
   identifier. Do not include connection credentials or secret keys.
3. Use established authenticated AES-256 ZIP encryption through a reviewed,
   maintained library; reject legacy ZipCrypto and plaintext archives. Offer a
   cryptographically generated passphrase with at least 128 bits of entropy as the
   default, with confirmation and an explicit instruction to store it separately.
   If custom passphrases are supported, enforce a documented strong policy.
4. Authenticate archive origin independently of the user-chosen passphrase using
   a server-held signing/MAC key from the existing external secret provider. Bind
   the canonical manifest and dump digest together. Trust only configured signing
   keys; allow explicit verification-key rotation. Never put signing or database
   encryption keys inside the ZIP. A checksum or encrypted ZIP alone does not
   establish trusted origin for executable database content.
5. Stream downloads through authenticated backend routes with appropriate
   attachment headers and `Cache-Control: no-store`. Never place backups under
   assets/static/public paths or use predictable artifact identifiers.

### 3. Validated, atomic replacement

1. Gate archive staging by the same admin-plus-role authorization. Enforce bounded
   upload and decrypted sizes, entry counts, compression ratios, temporary disk
   usage, process runtime, and concurrent operations. Enforce limits while reading;
   do not load the entire database/ZIP into memory.
2. Reject malformed, unsigned, tampered, plaintext, wrong-passphrase, or unsupported
   archives. Allow only expected entries; reject duplicate names, traversal paths,
   symlinks, nested archives, and unexpected files. Never blindly extract uploads.
   Verify origin and payload integrity before sending any content to PostgreSQL.
3. Preflight actual server/tool compatibility, required extensions and privileges,
   free temporary space, manifest/schema compatibility, and the database encryption
   key. Initially require the same Alembic revision as the running application;
   reject incompatible archives before modifying the target. Do not silently run
   migrations or promise cross-major downgrade support.
4. Show verified backup metadata and identify the destination. Require an explicit
   destructive confirmation, the current account password, and the backup
   passphrase. State that all current data and user accounts will be replaced and
   users will need to sign in again using accounts from the restored backup.
5. Coordinate maintenance across workers/replicas: prevent overlapping backup or
   restore operations, drain active application operations, block new conflicting
   access, and pause background writers. Keep the restore control/status path
   usable. Do not rely solely on disabled buttons or an in-process lock.
6. Restore cleanup and content in one transaction, failing on the first error.
   Failure, timeout, or cancellation must roll back all target changes. Remove
   obsolete application objects absent from the archive as part of replacement;
   `pg_restore --clean` alone does not prove this. Never drop/recreate the database,
   modify protected PostgreSQL roles, or target a database named by the archive.
   Preserve deployment-managed ownership/grants and system objects; establish
   the supported privilege/extension contract before destructive execution.
7. Before committing, validate restored schema/data invariants and invalidate
   restored authentication sessions and transient authentication/reset tokens so
   historical sessions or reset links cannot become valid again. Also invalidate
   live application sessions/caches across workers and reset connection pools as
   needed. Document these intentional security exceptions to exact data recovery.
8. Report success only after commit and required checks. On failure retain a
   recoverable state, release resources, and surface a safe German error. Handle
   worker crashes and stale maintenance state explicitly; never resume access to
   a partially validated restore.

### 4. Runtime, UI, and operations

- Add `/admin/backups` with `Datenbanksicherung`, `Sicherung exportieren`, and
  `Sicherung importieren`, using existing theme and page/form patterns. Include
  password/passphrase fields, overwrite confirmation, progress, and error states.
- Use configured database/TLS settings and safe subprocess argument arrays without
  a shell. Never accept connection strings, target names, paths, or command flags
  from uploaded metadata. Use restricted temporary credentials/files and cleanup
  on success, errors, disconnects, and cancellation.
- Provide compatible `pg_dump`/`pg_restore` in the repository runtime image and
  document local prerequisites. Fail closed with an actionable message if missing
  or unsupported. SQLite is suitable for unit tests only, not backup operations.
- Keep audit records outside data being replaced: actor ID, operation ID, timestamp,
  action, and outcome. Never log credentials, tokens, dump contents, decrypted
  fields, or raw tool errors containing sensitive information.
- Bound temporary artifact lifetime and clean abandoned files. No permanent backup
  history or automatic retention feature is required.
- Document that this backs up one PostgreSQL database, not cluster-global roles,
  tablespaces, external files, Key Vault, or platform configuration. Required external
  encryption/signing keys must be recoverable separately. Verify encrypted-field
  compatibility rather than equating successful SQL restore with a usable app.

## Deliverables and verification

- Deliver focused role/guard, page/state, service, protected transfer routes,
  configuration/runtime changes, tests, and concise operator documentation.
- Write failing tests first. Cover the complete permission matrix, missing/wrong
  passwords, SSO-only accounts, throttling, replay, role revocation, session expiry,
  direct-route access, and password/passphrase exclusion from state/logs.
- Test archive encryption/authenticity and rejection cases, streaming limits,
  cleanup, timeout/cancellation, concurrency/maintenance, rollback, and session
  invalidation. Include the new handlers in the authorization guard audit.
- Run a real disposable PostgreSQL round trip with representative schema/data,
  sequences, binary content, encrypted fields, and extra target-only objects.
  Inject a mid-restore failure and prove the original database remains unchanged.
  Test the supported runtime privilege model, not only a superuser fixture.
- Run `task format`, `task lint`, `task typecheck`, `task test`, handler authorization
  and component boundary checks, and the file-size check. Meet the repository's
  80% coverage requirement. Verify the UI and runtime client tools. Report local,
  container, and production evidence separately; never operate on production to
  prove this feature.
- Keep the diff minimal, functions typed, files at most 1000 lines, UI German,
  and logs parameterized. Add dependencies with `uv add`. Write migrations manually
  only if needed; do not create a PostgreSQL login role for the application role.

## Out of scope

Scheduled backups, cloud backup storage, backup browsing/history, selective data
imports, cluster backups, cross-version migration tooling, deployment, production
restore execution, and unrelated refactors.

## PostgreSQL references

- [pg_dump: consistency, scope, formats, and trust](https://www.postgresql.org/docs/current/app-pgdump.html)
- [pg_restore: cleanup and single-transaction semantics](https://www.postgresql.org/docs/current/app-pgrestore.html)
