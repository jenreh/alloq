# Database backup and restore

The **Administration → Datenbanksicherung** page exports and replaces the complete
configured Alloq PostgreSQL database. A user needs the administrator switch **and**
the explicit **Datenbanksicherung** permission. Administrators receive no automatic
backup permission. A current local Alloq password is required for every action,
including when signed in through Microsoft. Use the existing password-reset flow
to set a local password when necessary.

## Enable

Set `app.database_backup.enabled: true` and configure
`app.database_backup.signing_key` through the existing secret provider, for example
`secret:alloq-backup-signing-key`. Alternatively use
`APP__DATABASE_BACKUP__ENABLED` and `APP__DATABASE_BACKUP__SIGNING_KEY`. Use a unique,
cryptographically random key of at least 32 bytes, separate from the database
encryption key. Missing trust configuration fails closed. Keep old signing keys in
`verification_keys` while older archives must remain importable. Preserve these
keys independently of database backups. Trusting another installation's signing
key explicitly authorizes its database dumps to execute SQL here.

Install matching-major `pg_dump`, `pg_restore` and `psql`. The Docker runtime uses
the signed PostgreSQL APT repository and defaults to `POSTGRES_MAJOR=16`; the local
Compose build sets 15 to match its existing PostgreSQL 15 service. Set the build
argument to the actual server major. Connection and TLS settings come from the
configured database; libpq certificate environment settings are honored. Unsupported
URL options fail closed rather than silently using a different connection.

The configured database account must own, or have ownership-role membership for,
all application schemas and objects, read all data, manage its large objects, and
be permitted to recreate the installed extensions. It does not need superuser,
cluster role creation, or database creation. Restore does not modify PostgreSQL
login roles or recreate the database. Roll out this version to **all** app workers
and workshop workers before enabling restores: old binaries do not participate in
the operation locks. Direct database clients and external writers must be stopped
separately before restore.

## Use

For export, enter the account password and a separate backup passphrase twice.
Prefer the built-in generator, which uses 192 random bits. Custom phrases need
24–256 characters and at least eight different characters. Store the passphrase
separately before submitting; the application clears the fields and cannot recover
the passphrase. Archives use AES-256 ZIP (AE-2) and HMAC-SHA256 origin verification.
Compatible browsers stream directly to the chosen file; other browsers use their
download mechanism with memory bounded by the configured archive limit.

For import, upload the ZIP, enter the account password and backup passphrase, and
select **Sicherung prüfen**. Review its verified timestamp, version and destination.
Then re-enter both secrets and type **DATENBANK ERSETZEN** before selecting
**Datenbank ersetzen**. Changing the file requires another inspection; the server
checks its digest again. The initial version accepts only matching PostgreSQL
majors, installed extension versions, Alembic heads, and external database
encryption-key fingerprints. It does not upgrade or downgrade schema versions.

Import removes target-only application objects as well as replacing archived
objects. Cleanup, restore, row-count/schema checks, grant preservation and session
invalidation execute in one transaction. Failure or cancellation kills the native
client and rolls back that transaction. A worker crash cannot release maintenance
while the restore transaction is still running, because that transaction holds its
own lock. Until it ends, other app work is rejected. Whole websocket events and
workshop jobs hold shared leases, so existing work drains before replacement.

All current and restored sessions, OAuth handshake states and password-reset
tokens/requests are removed before commit. Live websocket authentication caches
are invalidated on every event. Reauthenticate using an account from the restored
database; the account and role assignments may differ from the replaced database.
These token removals and preservation of target deployment grants are intentional
exceptions to exact historical recovery.

## Limits and scope

Defaults are 512 MiB per encrypted ZIP, 1 GiB per dump/rendered SQL, a 300-second
operation deadline, and five password attempts per account in a durable 15-minute
window. Archive entries, fields, compression ratios, temporary space and concurrent
operations are bounded. Secrets travel only in HTTP bodies; they never enter
Reflex events/state, URLs or application audit logs. Audit records contain actor
ID, operation ID, action and outcome and go to the application's external logs.

Temporary files live under a private owner-only directory in the OS temporary
directory and are removed on completion/error/disconnect. A lifespan sweeper
removes abandoned workspaces after twice the operation deadline plus 60 seconds,
checking file locks to avoid active operations. With no running app process,
cleanup occurs after the next start; use ephemeral/encrypted runtime storage.

This is a logical backup of one database, including database-stored binary data,
large objects and authentication data. It does not include cluster-global roles,
tablespaces, external files, Key Vault or deployment settings. Retain external
database encryption and backup signing keys separately. ZIP encryption protects
the dump; it does not replace access controls on the downloaded file.

Verification: `task format`, `task lint`, `task typecheck`, `task test`. The tests
create a private Unix-socket PostgreSQL cluster when `initdb` and `pg_ctl` are
installed; they never connect to the configured application database. Container
build and deployed restore checks are separate from these local results.
