---
title: Getting started
description: Set up a local Alloq development environment, run the web app, sign in and run the quality gates.
source_paths:
  - Taskfile.dist.yml
  - taskfiles/Taskfile.qa.yml
  - taskfiles/Taskfile.reflex.yml
  - taskfiles/Taskfile.db.yml
  - pyproject.toml
  - .env.example
  - configuration/config.yaml
  - configuration/config.local.yaml
  - docker-compose.yml
  - rxconfig.py
  - app/configuration.py
  - alembic/env.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Getting started

This page takes you from a fresh clone to a running Alloq web app on your machine.
At the end you can sign in, change code and run the same checks as the CI.

## What you need

- **Python 3.14.** You do not have to install it yourself. `task init` reads
  `requires-python = ">=3.14"` from [pyproject.toml](../../pyproject.toml) and
  installs that version with uv.
- **uv**, the package manager. The repo is a uv workspace with the host app and
  four packages under `components/`.
- **Task**, the task runner. Every command on this page is a `task` target. See
  [Commands](../reference/commands.md) for the full list.
- **PostgreSQL 15 or newer.** You can use your own server or the `db` service in
  [docker-compose.yml](../../docker-compose.yml).
- **ty**, the type checker, for `task typecheck`. It is not a dependency in
  `pyproject.toml`, so install it yourself and make sure it is on your `PATH`.
- **Node.js**, only if you build these docs or run the JavaScript tests.
- **Rust and the Xcode command line tools**, only if you work on the desktop app.
  The comments in [taskfiles/Taskfile.reflex.yml](../../taskfiles/Taskfile.reflex.yml)
  list them.

## 1. Create the `.env` file

The app reads its settings from YAML files in `configuration/` and from
environment variables. A `.env` file in the repo root is loaded on start, so put
your local values there. Start from [.env.example](../../.env.example) and copy it
to `.env`. Git ignores `.env`.

Set these three lines first:

```bash
PROFILES=local
SECRET_PROVIDER=local
UV_PROJECT_ENVIRONMENT=.venv.mac
```

- `PROFILES=local` loads `configuration/config.local.yaml` on top of
  `configuration/config.yaml`.
- `SECRET_PROVIDER=local` makes the app read secrets from environment variables
  instead of Azure Key Vault.
- `UV_PROJECT_ENVIRONMENT=.venv.mac` is the virtual environment the team uses on
  macOS. Any other folder name works too.

### Secrets

[configuration/config.yaml](../../configuration/config.yaml) refers to secrets with
values such as `secret:alloq-db-user`. With the local provider, the app looks for
an environment variable with that name. It tries the name as written, in upper
case, and with dashes turned into underscores (`ALLOQ_DB_USER`). The lookup is
`_get_secret_from_env` in appkit_commons.

The `local` profile needs these secrets:

| Secret in `config.yaml` | Environment variable | What it is |
| --- | --- | --- |
| `alloq-db-user` | `ALLOQ_DB_USER` | Postgres user |
| `alloq-db-password` | `ALLOQ_DB_PASSWORD` | Postgres password |
| `alloq-db-host` | `ALLOQ_DB_HOST` | Postgres host |
| `alloq-db-name` | `ALLOQ_DB_NAME` | Postgres database name |
| `common-db-encryption-key` | `COMMON_DB_ENCRYPTION_KEY` | Fernet key that appkit uses to encrypt stored OAuth tokens |
| `common-oauth-azure-client-id` | `COMMON_OAUTH_AZURE_CLIENT_ID` | Client id of the Microsoft sign-in |
| `common-oauth-azure-client-secret` | `COMMON_OAUTH_AZURE_CLIENT_SECRET` | Client secret of the Microsoft sign-in |
| `common-oauth-azure-tenant-id` | `COMMON_OAUTH_AZURE_TENANT_ID` | Entra tenant id |

The Azure values are needed because `config.local.yaml` keeps the Azure provider
from `config.yaml`. If you do not use Microsoft sign-in locally, any text works,
and the CI workflow in [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
sets them to `ci`. You can create a Fernet key with the same command the CI uses:

```bash
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

::: warning Names in .env.example
`.env.example` still uses older secret names (`mn-db-user`, `avui-db-encryption-key`).
They do not match the `secret:` references in `config.yaml`. Use the names in the
table above.
:::

Never commit real credentials. Production reads the same names from Azure Key
Vault. See [Configuration](../reference/configuration.md) for how profiles, secrets
and environment overrides work together.

## 2. Start a database

If you use the Compose database, start only the `db` service:

```bash
docker compose up -d db
```

It creates the database `alloq-db` with user and password `postgres` and publishes
it on host port `5433`. `config.yaml` uses port `5432`, so override the port in
`.env`:

```bash
ALLOQ_DB_HOST=localhost
ALLOQ_DB_NAME=alloq-db
ALLOQ_DB_USER=postgres
ALLOQ_DB_PASSWORD=postgres
APP__DATABASE__PORT=5433
```

`APP__DATABASE__PORT` uses the double underscore override that
[Configuration](../reference/configuration.md#environment-overrides) explains.

## 3. Initialize the project

```bash
task init
```

`task init` runs these steps from [Taskfile.dist.yml](../../Taskfile.dist.yml):

1. It installs and pins the Python version from `pyproject.toml`.
2. It runs `uv sync`. This installs the dev and desktop dependency groups, because
   `pyproject.toml` sets them as default groups.
3. It installs pre-commit if it is missing and runs `pre-commit install`.
4. It runs `alembic upgrade head`, so the database must be reachable at this point.

Later, when dependencies change, `task sync` is enough. To apply new migrations, run
`task db:upgrade`.

## 4. Run the app

```bash
task run
```

`task run` calls `reflex run`. With the `local` profile, the app is served at
`http://localhost:8080/alloq`. The port and the `/alloq` path prefix come from
`frontend_port` and `frontend_path` in
[configuration/config.local.yaml](../../configuration/config.local.yaml). The
backend listens on port `3030` from `config.yaml`.

- `task run:debug` starts the same app with debug logging.
- `task run:prod` starts it in Reflex production mode on one port.

When `app.environment` is `production`, the app refuses to start without the
`PUBLIC_BASE_URL` environment variable (`configure()` in
[app/configuration.py](../../app/configuration.py)). The base profile and the `prod`
profile set `production`. The `local` profile sets `local`, so you do not need the
variable on your machine.

The planning page ("Ressourcenplanung" [resource planning]) opens at `/` and at
`/plan`. All other pages are in the sidebar.

## 5. Sign in

The login page ("Anmelden" [sign in]) has an email and password form and a
"Mit Microsoft anmelden" [sign in with Microsoft] button.

The baseline migration seeds one administrator account with the email `admin`.
A later migration sets `needs_password_reset` on it while its password is still the
committed default. The login page does not read this flag, so change the password
yourself. Ask a team member for the local test login. Use it only against your
local database, and never commit it or write it into a file in the repo.

What a signed-in user can see and do depends on the role. Administrators can do
everything. Project managers edit planning. Employees only read. See
[Security and access](../architecture/security-and-access.md).

::: tip "reading 'length'" after a code change
If the browser shows this error after you added a state class, reload the page and
sign in again. The browser still holds the old state shape. It is not a bug in
your code.
:::

## 6. Run the quality gates

Run these before you push. On every pull request and every push to `main`, the CI
runs `ruff check`, `ruff format --check`, `pytest` and the JavaScript tests. It
does not run the type check or the coverage limit, so run those yourself.

```bash
task format     # ruff check --fix, then ruff format
task lint       # ruff check .
task typecheck  # ty check app
task test       # pytest --cov, fails below 80 % coverage
```

For a quick loop, run one test file:

```bash
uv run pytest components/alloq-commons/tests/test_departments.py -q
```

[Testing](../reference/testing.md) explains the test layout, the guard tests and how
to write a state test.

## Optional: desktop app and docs

- `task desktop:dev` starts the desktop app with hot reload and a faked Microsoft
  sign-in against your local database. See [Desktop app](../architecture/desktop.md).
- `task docs:install` and then `task docs:dev` start this documentation site with
  live reload.

## Next steps

- Read [Contributing](./contributing.md) before you change code.
- Read the [Architecture overview](../architecture/overview.md) to see how the
  packages fit together.
- Open the [Story map](../features/story-map.md) to see what Alloq does for each
  user.
