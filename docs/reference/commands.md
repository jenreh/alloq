---
title: Commands
description: Every Task target in Alloq, grouped by taskfile, with what it runs, the variables it reads and what it changes.
source_paths:
  - Taskfile.dist.yml
  - taskfiles/Taskfile.qa.yml
  - taskfiles/Taskfile.reflex.yml
  - taskfiles/Taskfile.db.yml
  - taskfiles/Taskfile.docker.yml
  - taskfiles/Taskfile.docs.yml
  - taskfiles/Taskfile.release.yml
  - taskfiles/Taskfile.terraform.yaml
  - start.sh
  - docker-compose.yml
  - Dockerfile
  - pyproject.toml
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Commands

Alloq uses [Task](https://taskfile.dev) as its command runner. Do not use `make`.
The entry point is [`Taskfile.dist.yml`](../../Taskfile.dist.yml) in the repository
root. It defines a few project tasks and includes the taskfiles in
[`taskfiles/`](../../taskfiles/).

Each include has a name. By default, the include name becomes a namespace, so the
`upgrade` task in the `db` include is called `task db:upgrade`. An include with
`flatten: true` has no namespace, so its tasks are called by their plain name, e.g.,
`task test`. The `qa` and `reflex` includes are flattened.

Run `task` or `task --list` to see every target with its description. Most tasks
run their tools through `uv run`, so the tools come from the project environment.
Most taskfiles set `silent: true`, so Task does not print each command before it
runs it.

The root taskfile sets one variable. `PROJECT` is read from the `packages` line in
`pyproject.toml`, and its value is `app`. The `qa` include and the `docker` include
use it.

For the first setup, follow [Getting started](../guide/getting-started.md). For the
settings that the app reads when it starts, see
[Configuration](./configuration.md).

## Daily commands

These are the commands a new developer needs most.

| Command | When to use it |
| --- | --- |
| `task init` | Run once after you clone the repository. It installs Python, the packages and the Git hooks, and it migrates the database. |
| `task sync` | Run after you pull changes that touch `pyproject.toml` or `uv.lock`. |
| `task run` | Start the web app on your machine for development. |
| `task test` | Run the test suite with coverage. See [Testing](./testing.md). |
| `task lint` | Check the code with Ruff after every code change. |
| `task format` | Fix the lint findings that Ruff can fix and format the code. |
| `task typecheck` | Check the type annotations in `app/` with ty. |
| `task db:revision -- "message"` | Create a new, empty Alembic migration file to write by hand. |
| `task db:upgrade` | Apply all open migrations to your database. |
| `task docs:dev` | Start the documentation site with live reload while you write docs. |

The project rules in `AGENTS.md` ask you to write migrations by hand, so
`db:revision` does not use `--autogenerate`.

## Project tasks

Source: [`Taskfile.dist.yml`](../../Taskfile.dist.yml). These tasks have no
namespace.

| Target | What it does | Notes |
| --- | --- | --- |
| `default` | Runs `task --list`. | Runs when you call `task` with no target. |
| `init` | Installs and pins the Python version from `requires-python` in `pyproject.toml` with `uv python install` and `uv python pin`. Then it runs `uv sync`, installs the `pre-commit` tool if it is missing, runs `git init -b main` if the folder is not a Git repository, runs `pre-commit install` and runs `alembic upgrade head`. | Touches the database. The database settings must work before you run it, so set up `.env` and the database first. `uv python pin` writes `.python-version`. |
| `sync` | Runs `uv sync`. | Installs the `dev` and `desktop` dependency groups, because `pyproject.toml` sets them as default groups. |
| `clean` | Deletes `__pycache__/`, `.cache/`, `.state/`, `.web/`, `dist/`, `build/`, `coverage.xml` and `.coverage`, then all `__pycache__` folders and `.pyc` files below the root. | Errors are ignored. Deleting `.web/` means the next `reflex run` builds the frontend again. |

## QA tasks (`qa`, flattened)

Source: [`taskfiles/Taskfile.qa.yml`](../../taskfiles/Taskfile.qa.yml). The include
passes `PROJECT` to this taskfile. For the test layout, fixtures and coverage rules,
see [Testing](./testing.md).

| Target | What it does | Notes |
| --- | --- | --- |
| `test` | Runs `uv run pytest --cov`. | Writes coverage data. Pytest options come from `pyproject.toml`. |
| `lint` | Runs `uv run ruff check .`. | Reports findings and changes nothing. |
| `format` | Runs `uv run ruff check --fix .` and then `uv run ruff format .`. | Changes files in place. |
| `typecheck` | Runs `uv run ty check app`. | ty is not in the `dev` dependency group or in `uv.lock`. `uv run` then falls back to a `ty` on your `PATH`, so you must install ty yourself, e.g., with `uv tool install ty`. |

## Reflex and desktop tasks (`reflex`, flattened)

Source: [`taskfiles/Taskfile.reflex.yml`](../../taskfiles/Taskfile.reflex.yml).

### Web app

| Target | What it does | Notes |
| --- | --- | --- |
| `run` | Runs `uv run reflex run`. | Starts the frontend and the backend in development mode with hot reload. |
| `run:debug` | Runs `uv run reflex run --loglevel=debug`. | Same as `run`, with debug logging from Reflex. |
| `run:prod` | Runs `uv run reflex run --env prod --single-port`. | Production mode serves the frontend and the backend on one port. It does not run migrations. The container uses `start.sh` instead, which is described below. |

### Desktop app

The desktop tasks run `scripts/desktop.py` with the `desktop` dependency group
(`reflex-desktop`). They need Rust and the Xcode command line tools. The
`desktop:build` task also needs `cargo-tauri`, and `desktop:doctor` checks for it. Fill in
`configuration/config.desktop.yaml` before you start. The architecture page
[Desktop app](../architecture/desktop.md) explains how the desktop app works.

Most desktop tasks set these environment variables:

- `ALLOQ_DESKTOP=1` turns on the desktop profile and the desktop plugin in
  `rxconfig.py`.
- `CARGO_TARGET_DIR` points to `tauri/src-tauri/target`, so all Rust build output
  goes to one folder.

| Target | What it does | Notes |
| --- | --- | --- |
| `desktop:requirements` | Runs `uv export` to write `requirements.txt` from `uv.lock`, without dev packages, hashes or the project itself. | Generates `requirements.txt`. Task skips it when `uv.lock` and `pyproject.toml` have not changed. The embedded Python runtime installs from this file. |
| `desktop:doctor` | Runs `scripts/desktop.py doctor --bundle`. | Checks the native toolchain, including the tools that the installer build needs. |
| `desktop:dev` | Runs `scripts/desktop.py dev`. | Starts the desktop app with hot reload against your local database. It uses the fake Microsoft sign-in from `app/desktop/fake.py`. Set `ALLOQ_FAKE_ENTRA_EMAIL` to sign in as a different user. The taskfile has a default address for it. |
| `desktop:run` | Runs `desktop:requirements` first, then `scripts/desktop.py run --debug`. | Builds a debug app and opens the native window. |
| `desktop:build` | Runs `desktop:requirements` first, then `scripts/desktop.py build --release --bundle`. | Builds the release app and the macOS installer (`.dmg`). The comment in the taskfile says that the bundle contains Python 3.14 and the YAML profiles, and no secrets. |
| `desktop:clean` | Runs `rm -rf tauri/src-tauri/target`. | Deletes all Tauri build output. The next desktop build compiles everything again. |

## Database tasks (`db`, namespace `db:`)

Source: [`taskfiles/Taskfile.db.yml`](../../taskfiles/Taskfile.db.yml). All tasks run
Alembic through `uv run`. Alembic uses the database that the app configuration
points to. See [Configuration](./configuration.md#app-database).

| Target | What it does | Notes |
| --- | --- | --- |
| `db:default` | Runs `task --list`. | Lists all targets, not only the `db` targets. |
| `db:revision` | Runs `alembic revision -m "<message>"`. | Pass the message after `--`, e.g., `task db:revision -- "add rate column"`. It writes a new file to `alembic/versions/`. The file has empty `upgrade` and `downgrade` functions for you to fill in. |
| `db:current` | Runs `alembic current`. | Shows the revision that the database is on. Reads the database and changes nothing. |
| `db:history` | Runs `alembic history`. | Lists all migrations from the files. |
| `db:upgrade` | Runs `alembic upgrade head`. | Changes the database schema. `task init` and `start.sh` run the same command. |
| `db:downgrade` | Runs `alembic downgrade -1`. | Reverts the last applied migration. This can drop tables or columns and the data in them. |

## Docker tasks (`docker`, namespace `docker:`)

Source: [`taskfiles/Taskfile.docker.yml`](../../taskfiles/Taskfile.docker.yml). The
include sets `IMAGE_NAME` to <code v-pre>{{.PROJECT}}-image</code>, which is `app-image`.

| Target | What it does | Notes |
| --- | --- | --- |
| `docker:default` | Runs `task --list`. | Lists all targets. |
| `docker:build` | Runs `docker build -t app-image:latest .`. | Builds an image from the `Dockerfile`. |
| `docker:test` | Runs `docker compose up --build --watch`. | Builds and starts the services in `docker-compose.yml` and watches the source folders. It does not use the image from `docker:build`, because Compose builds its own image named `alloq`. The command keeps running until you stop it. |

### `docker-compose.yml`

`docker:test` starts two services:

- `alloq-app` runs the app image on port `8080`. It uses the profile `docker_test`
  and the local secret provider. It reads optional overrides from `.env.docker`,
  which must provide `AVUI_DB_ENCRYPTION_KEY`. When you change files in `app/`,
  `components/`, `assets/` or `configuration/`, Compose copies them into the
  container. When you change `pyproject.toml`, `uv.lock`, `Dockerfile` or `start.sh`,
  Compose builds the image again.
- `db` runs Postgres 15 with pgvector. It publishes the database on host port
  `5433` and keeps the data in the volume `alloq-postgres-data`.

You can start only the database with `docker compose up -d db`. Getting started
uses this for local development.

### `start.sh`

The `Dockerfile` runs `start.sh` when the container starts. The script runs
`alembic upgrade head` and then `reflex run --env prod --single-port`. So the
container migrates the database before it accepts requests. `task run:prod` runs
only the second command.

## Docs tasks (`docs`, namespace `docs:`)

Source: [`taskfiles/Taskfile.docs.yml`](../../taskfiles/Taskfile.docs.yml). All tasks
run `npm` inside `docs/`. This taskfile does not set `silent: true`, so Task prints
each command.

| Target | What it does | Notes |
| --- | --- | --- |
| `docs:install` | Runs `npm install`. | Run it once before the other docs tasks. Creates `docs/node_modules/`. |
| `docs:dev` | Runs `npm run docs:dev`. | Starts the VitePress dev server with live reload. |
| `docs:build` | Runs `npm run docs:build`. | Builds the static site into `docs/.vitepress/dist/`. |
| `docs:preview` | Runs `npm run docs:preview`. | Serves the built site locally. Run `docs:build` first. |

All four tasks need `docs/package.json`, which defines the `docs:*` npm scripts.

## Release tasks (`release`, namespace `release:`)

Source: [`taskfiles/Taskfile.release.yml`](../../taskfiles/Taskfile.release.yml).

| Target | What it does | Notes |
| --- | --- | --- |
| `release:default` | Runs `task --list`. | Lists all targets. |
| `release:build` | Bumps the version with `uvx bump-my-version bump`, runs `uv sync`, stages all changes with `git add -A`, commits them as `chore: release v<version>` if anything changed, runs `git push` and creates a GitHub release with `gh release create v<version> --generate-notes`. | Pass `major`, `minor` or `patch` after `--`. The default is `patch`. It commits every change in the working tree, so start from a clean tree. It pushes to the remote and needs a signed-in `gh` CLI. The version lives in `pyproject.toml` under `[tool.bumpversion]`. |

## Terraform tasks (inactive)

Source: [`taskfiles/Taskfile.terraform.yaml`](../../taskfiles/Taskfile.terraform.yaml).
These tasks are not available at `cb9d5b0`. The two includes `dev` and `prod` are
commented out in `Taskfile.dist.yml`, and the repository has no `terraform/` folder.

To turn them on, you would:

1. Add a `terraform/` folder with the Terraform code, a `deploy-azure.sh` script and
   one `<environment>.auto.tfvars` file per environment, e.g.,
   `dev.auto.tfvars`.
2. Remove the comment signs from the `dev` and `prod` blocks in
   `Taskfile.dist.yml`. Each block sets `TF_DIR` to <code v-pre>{{.ROOT_DIR}}/terraform</code> and
   sets `ENVIRONMENT` to `dev` or `prod`.

The taskfile builds `TFVARS` from these two values as
`<TF_DIR>/<ENVIRONMENT>.auto.tfvars`. Every task runs inside `TF_DIR`, and every
task first runs `az login` if the Azure CLI is not signed in. Each target then
exists twice, e.g., `task dev:status` and `task prod:status`.

| Target | What it does | Notes |
| --- | --- | --- |
| `status` | Runs `./deploy-azure.sh status`. | Shows the deployment status. |
| `bootstrap` | Runs `./deploy-azure.sh bootstrap --tfvars <TFVARS>`. | Creates the storage for the Terraform state in Azure. Run it once per environment. Arguments after `--` are passed on. |
| `migrate` | Runs `./deploy-azure.sh migrate --tfvars <TFVARS>`. | Creates or updates the main infrastructure. Arguments after `--` are passed on. |
| `destroy` | Runs `terraform destroy -var-file <TFVARS>`. | Deletes all infrastructure of that environment. Arguments after `--` are passed on. |

## Open questions

- `docker:build` tags the image as `app-image`, but `docker:test` and
  `docker-compose.yml` build and run an image named `alloq`. The description of
  `docker:test` says that it runs the locally built image, which is not what the
  command does.
- `typecheck` depends on a `ty` that is installed outside the project, because ty is
  not a project dependency.
- In `docs:build`, the `generates` path is `docs/.vitepress/dist/index.html`, while
  the task runs in `docs/`. Task reads `generates` relative to the task folder, so the
  path may point to `docs/docs/...`. The task has no `sources`, so this does not stop
  it from running.
- The comment in the terraform taskfile says "Namespace: tf", but the commented
  includes would create the namespaces `dev` and `prod`.
