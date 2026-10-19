---
title: Testing
description: How to run the Alloq tests, where each test lives, what the shared fixtures give you, what the guard tests enforce, and short recipes for state, service and component tests.
source_paths:
  - pyproject.toml
  - taskfiles/Taskfile.qa.yml
  - .github/workflows/ci.yml
  - tests/conftest.py
  - components/alloq-commons/tests/conftest.py
  - components/alloq-dashboard/tests/conftest.py
  - components/alloq-project/tests/conftest.py
  - tests/test_component_boundaries.py
  - tests/test_handler_authorization.py
  - tests/test_migrations.py
  - tests/test_configuration_profiles.py
  - tests/test_desktop_login.py
  - app/desktop/schema.py
  - components/alloq-commons/tests/js/grid_logic.test.mjs
  - components/alloq-commons/tests/test_departments.py
  - components/alloq-commons/tests/test_roles.py
  - components/alloq-dashboard/tests/test_portfolio.py
  - components/alloq-dashboard/tests/test_aggregation.py
  - tests/test_sidebar.py
  - .claude/skills/alloq-implementation/references/testing.md
  - .claude/skills/alloq-implementation/references/pitfalls.md
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Testing

Alloq uses pytest for the Python code and the Node.js test runner for one
JavaScript module. This page says how to run the tests, where a new test goes, and
what the guard tests check. For the order of work (test first, then code, then the
gates), read [Contributing](../guide/contributing.md). For every task target, read
[Commands](./commands.md).

The feature pages under [`../features/`](../features/story-map.md) list the tests for each
story. This page does not repeat that mapping.

## How to run the tests

| What | Command |
| --- | --- |
| Whole suite with coverage | `task test` |
| Whole suite without coverage, as CI runs it | `uv run pytest -q` |
| One file | `uv run pytest components/alloq-commons/tests/test_departments.py -q` |
| One package | `uv run pytest components/alloq-project/tests -q` |
| One test | `uv run pytest tests/test_migrations.py::test_revision_chain -q` |
| The JavaScript test | `node --test "components/*/tests/js/*.test.mjs"` |

`task test` runs `uv run pytest --cov`. The settings come from
[`pyproject.toml`](../../pyproject.toml):

- `testpaths` lists `tests` and the `tests` folder of each of the four component
  packages, so a plain `pytest` collects all of them.
- `asyncio_mode = "auto"` lets you write `async def test_...` without a marker.
- `import_mode = "importlib"` lets two packages have test files with the same name.
- Coverage measures branches in `app` and in the `src` folder of each component
  package. `fail_under = 80` makes `task test` fail when the total coverage is
  below 80 %. The report lists the missing lines and skips fully covered files.

The JavaScript test [`grid_logic.test.mjs`](../../components/alloq-commons/tests/js/grid_logic.test.mjs)
tests the pure functions of the ExcelGrid in
[`grid_logic.js`](../../components/alloq-commons/src/alloq_commons/components/excel_grid/grid_logic.js),
e.g. `parseTSV` and `planPaste`. It needs Node.js 22 and no packages. No task target
runs it, so run the `node --test` command above when you change `grid_logic.js`.

CI runs both suites in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
on every push to `main` and on every pull request:

- The Python job runs `ruff check`, `ruff format --check` and `uv run pytest -q`.
  It sets `PROFILES=local`, dummy database and OAuth secrets, and a throwaway
  encryption key, because importing `app` loads the YAML configuration.
- The JavaScript job runs `node --test "components/*/tests/js/*.test.mjs"`.

CI does not pass `--cov`, so it does not check the 80 % coverage gate, and it does
not run `task typecheck`. Run `task test` and `task typecheck` yourself before you
open a pull request.

## Test layout

| Code in | Test in |
| --- | --- |
| `components/alloq-commons/src/...` | `components/alloq-commons/tests/test_<feature>.py` |
| `components/alloq-<pkg>/src/...` | `components/alloq-<pkg>/tests/test_<feature>.py` |
| `app/...`, migrations and checks across packages | `tests/test_<topic>.py` |

Add a test to the existing file for the feature before you create a new file, e.g.
department tests go into `test_departments.py`. Group tests in `class TestX:` the
way the neighbouring tests do.

### Root `tests/`

| Area | Files |
| --- | --- |
| Guard tests | [test_handler_authorization.py](../../tests/test_handler_authorization.py), [test_component_boundaries.py](../../tests/test_component_boundaries.py), [test_configuration_profiles.py](../../tests/test_configuration_profiles.py), [test_migrations.py](../../tests/test_migrations.py) |
| App, pages and sidebar | [test_app.py](../../tests/test_app.py), [test_sidebar.py](../../tests/test_sidebar.py), [test_login_page.py](../../tests/test_login_page.py), [test_users_page.py](../../tests/test_users_page.py) |
| Configuration and URLs | [test_configuration.py](../../tests/test_configuration.py), [test_rxconfig.py](../../tests/test_rxconfig.py), [test_public_url.py](../../tests/test_public_url.py) |
| Desktop app | [test_desktop_login.py](../../tests/test_desktop_login.py), [test_desktop_entra.py](../../tests/test_desktop_entra.py), [test_desktop_fake.py](../../tests/test_desktop_fake.py), [test_desktop_db_access.py](../../tests/test_desktop_db_access.py) |

### `components/alloq-commons/tests/`

| Area | Files |
| --- | --- |
| Access levels | [test_access.py](../../components/alloq-commons/tests/test_access.py) |
| Roles, rates, departments, holidays | [test_roles.py](../../components/alloq-commons/tests/test_roles.py), [test_role_colors.py](../../components/alloq-commons/tests/test_role_colors.py), [test_departments.py](../../components/alloq-commons/tests/test_departments.py), [test_daily_rates.py](../../components/alloq-commons/tests/test_daily_rates.py), [test_daily_rate_pricing.py](../../components/alloq-commons/tests/test_daily_rate_pricing.py), [test_public_holidays.py](../../components/alloq-commons/tests/test_public_holidays.py), [test_holiday_state.py](../../components/alloq-commons/tests/test_holiday_state.py) |
| Employees and projects | [test_employees.py](../../components/alloq-commons/tests/test_employees.py), [test_projects.py](../../components/alloq-commons/tests/test_projects.py), [test_quick_project.py](../../components/alloq-commons/tests/test_quick_project.py) |
| Calculations | [test_utilization.py](../../components/alloq-commons/tests/test_utilization.py) |
| Shared UI | [test_shell.py](../../components/alloq-commons/tests/test_shell.py), [test_list_view.py](../../components/alloq-commons/tests/test_list_view.py), [test_theme.py](../../components/alloq-commons/tests/test_theme.py), [test_excel_grid.py](../../components/alloq-commons/tests/test_excel_grid.py), [js/grid_logic.test.mjs](../../components/alloq-commons/tests/js/grid_logic.test.mjs) |
| Regression tests from code reviews | [test_review_fixes_commons.py](../../components/alloq-commons/tests/test_review_fixes_commons.py) |

### `components/alloq-dashboard/tests/`

| Area | Files |
| --- | --- |
| KPI aggregation | [test_aggregation.py](../../components/alloq-dashboard/tests/test_aggregation.py), [test_aggregation_utilization.py](../../components/alloq-dashboard/tests/test_aggregation_utilization.py) |
| Dashboard card states | [test_dashboard_states.py](../../components/alloq-dashboard/tests/test_dashboard_states.py) |
| Portfolio | [test_portfolio.py](../../components/alloq-dashboard/tests/test_portfolio.py), [test_portfolio_inputs.py](../../components/alloq-dashboard/tests/test_portfolio_inputs.py), [test_portfolio_state.py](../../components/alloq-dashboard/tests/test_portfolio_state.py) |
| Rendering | [test_components.py](../../components/alloq-dashboard/tests/test_components.py) |

### `components/alloq-project/tests/`

| Area | Files |
| --- | --- |
| Project list and drawer | [test_project_list.py](../../components/alloq-project/tests/test_project_list.py), [test_project_sorting.py](../../components/alloq-project/tests/test_project_sorting.py), [test_project_state.py](../../components/alloq-project/tests/test_project_state.py), [test_project_state_handlers.py](../../components/alloq-project/tests/test_project_state_handlers.py), [test_project_components.py](../../components/alloq-project/tests/test_project_components.py), [test_project_resource_state.py](../../components/alloq-project/tests/test_project_resource_state.py), [test_employee_read_only.py](../../components/alloq-project/tests/test_employee_read_only.py) |
| Plan a project and forecasts | [test_project_plan_state.py](../../components/alloq-project/tests/test_project_plan_state.py), [test_resource_planning.py](../../components/alloq-project/tests/test_resource_planning.py), [test_forecast.py](../../components/alloq-project/tests/test_forecast.py) |
| Planning grid, editing and saving | [test_planning_grid_editing.py](../../components/alloq-project/tests/test_planning_grid_editing.py), [test_planning_save_grid.py](../../components/alloq-project/tests/test_planning_save_grid.py), [test_planning_store_fixes.py](../../components/alloq-project/tests/test_planning_store_fixes.py), [test_planning_time_range_edits.py](../../components/alloq-project/tests/test_planning_time_range_edits.py), [test_planning_quick_create.py](../../components/alloq-project/tests/test_planning_quick_create.py), [test_planning_absence.py](../../components/alloq-project/tests/test_planning_absence.py) |
| Planning filters and view | [test_planning_availability_filter.py](../../components/alloq-project/tests/test_planning_availability_filter.py), [test_planning_hide_internal.py](../../components/alloq-project/tests/test_planning_hide_internal.py), [test_planning_view_settings.py](../../components/alloq-project/tests/test_planning_view_settings.py), [test_planning_project_view_state.py](../../components/alloq-project/tests/test_planning_project_view_state.py), [test_planning_builders_idle.py](../../components/alloq-project/tests/test_planning_builders_idle.py) |
| Planning rendering | [test_planning_grid_rendering.py](../../components/alloq-project/tests/test_planning_grid_rendering.py), [test_planning_readability.py](../../components/alloq-project/tests/test_planning_readability.py), [test_planning_block_summary.py](../../components/alloq-project/tests/test_planning_block_summary.py), [test_planning_toolbar.py](../../components/alloq-project/tests/test_planning_toolbar.py), [test_planning_legend.py](../../components/alloq-project/tests/test_planning_legend.py), [test_planning_gantt.py](../../components/alloq-project/tests/test_planning_gantt.py) |

### `components/alloq-team/tests/`

| Area | Files |
| --- | --- |
| Team list and state | [test_team_list.py](../../components/alloq-team/tests/test_team_list.py), [test_team_sorting.py](../../components/alloq-team/tests/test_team_sorting.py), [test_team_state.py](../../components/alloq-team/tests/test_team_state.py) |
| Employee components | [test_employee.py](../../components/alloq-team/tests/test_employee.py) |

## Fixtures and database setup

Production runs on PostgreSQL. The tests never need a running database. They use
SQLite in memory, or they replace the repository and the session with mocks.

[`tests/conftest.py`](../../tests/conftest.py) and the `conftest.py` files of
`alloq-commons`, `alloq-dashboard` and `alloq-project` contain only
`pytest_plugins = ["appkit_commons.testing"]`. `alloq-team/tests` has no `conftest.py`. Its tests do not use the shared
fixtures, and they pass when you run that folder alone. If you add a test there that
needs a shared fixture, add the same `conftest.py` first.

The plugin `appkit_commons.testing` comes from the `appkit-commons` dependency. When
pytest loads it, it registers a `DatabaseConfig` for SQLite in memory, a
`ReflexConfig` and an `AuthenticationConfiguration` in the service registry. It
does this before the test modules are imported, because some modules read the
registry at import time. It also provides these fixtures:

| Fixture | What it gives you |
| --- | --- |
| `async_engine` | An async SQLite engine in memory (`aiosqlite`, one shared connection). It creates every table of `appkit_commons.database.entities.Base.metadata`. The Alloq entities use this `Base`, so their tables exist too. |
| `async_session_factory` | An `async_sessionmaker` bound to that engine. |
| `async_session` | One `AsyncSession` inside a transaction that is rolled back after the test. |
| `clean_service_registry` | An empty service registry for one test. The old registry comes back afterwards. |
| `mock_secret_provider`, `mock_secrets` | Secrets for tests without a real secret store. |
| `captured_logs` | `caplog` with log propagation turned on. |
| `faker_instance`, `temp_dir` | A `Faker` object and a temporary folder. |

Use `async_session` when you test a repository against real SQL. Use mocks for the
repository and the session when you test a state handler (see the recipes below).
SQLite does not behave like PostgreSQL in every case, e.g. for `ARRAY` columns,
which the `ArrayType` column type stores as JSON on SQLite. Keep the queries plain
enough to run on both.

From [`test_roles.py`](../../components/alloq-commons/tests/test_roles.py):

```python
async def test_find_all_paginated(self, async_session: AsyncSession) -> None:
    repo = RoleRepository()
    async_session.add(RoleEntity(name="Alpha", description="First"))
    async_session.add(RoleEntity(name="Beta", description="Second"))
    await async_session.flush()

    results = await repo.find_all_paginated(async_session, limit=10, offset=0)
    assert [r.name for r in results] == ["Alpha", "Beta"]
```

Ruff relaxes some rules for `test_*.py` files in `pyproject.toml`, e.g. `assert`
(`S101`), magic numbers (`PLR2004`), private names (`SLF001`) and missing argument
types (`ANN001`). The house rule still asks for type hints, so add them as the
neighbouring tests do.

## Guard tests

The guard tests check rules for the whole code base. They are fast, so run them
every time you add a handler, an import or a migration.

### Handler authorization

[`tests/test_handler_authorization.py`](../../tests/test_handler_authorization.py)
imports every module of the four component packages and three `app` modules, and
finds every Reflex state. Mixins are skipped and checked through the states that
use them. The rule is that every event handler that can reach the database checks
the user's rights on the server.

Each handler must be in exactly one of these groups:

- It has `@requires_editor`. This is the normal guard in `alloq_dashboard`,
  `alloq_project`, `alloq_team` and for `SidebarState`.
- It has `@requires_admin`. This is only for the administration states in
  `ADMIN_STATES`, e.g. `RoleState` and `DepartmentState`.
- It has `@requires_viewer` and is listed in `VIEWER_HANDLERS`. The employee role
  may run these loads, and their source must not contain a write call such as
  `.commit(` or `.add(`.
- It is a background handler listed in `INLINE_ADMIN_CHECK`. It calls
  `self._run_card_load(...)`, which checks the rights inside `async with self:`.
- It is listed in `UI_ONLY_HANDLERS`. It must not reach the database, directly or
  through a `self.` helper. The test looks for markers such as
  `get_asyncdb_session`, `_repo.` and `aggregation.`.
- It is listed in `PRE_AUTH_HANDLERS`. These are the desktop sign-in and sign-out.

Other tests in the file check that:

- No handler in the planning packages uses `@requires_admin`.
- No handler in an administration state uses `@requires_editor` or
  `@requires_viewer`.
- No background handler uses a guard decorator, because the decorators call
  `get_state` without the state lock.
- No allowlist entry names a handler that no longer exists or that now has a guard.

When it fails:

- The message of `test_every_handler_is_admin_guarded_or_ui_only` lists the
  unguarded handlers as `State.handler`. If the handler loads or saves data, add
  `@requires_editor`, or `@requires_admin` in the administration. If it only changes
  UI state, add it to `UI_ONLY_HANDLERS` under the concrete state.
- If `test_ui_only_handler_does_not_reach_database` fails, the handler is not UI
  only. Split it into a guarded loader and a UI toggle, or guard it and remove it
  from the allowlist.
- If `test_allowlists_have_no_stale_entries` fails, you renamed, removed or guarded
  a handler. Remove its entry from the allowlist.
- If a background handler fails, remove the decorator and use `_run_card_load`.

[Security and access](../architecture/security-and-access.md) explains the levels.

### Component boundaries

[`tests/test_component_boundaries.py`](../../tests/test_component_boundaries.py)
parses every Python file under `components/*/src` and fails if one of them imports
`app` or a module below `app`. The component packages must work without the host
app. It also checks that `app.roles.ALL_ROLES` is the same object as
`alloq_commons.roles.ALL_ROLES`.

When it fails, move the code you need from `app` into a component package, usually
`alloq_commons`, and import it from there in both places. The failure lists the
offending files.

### Configuration profiles

[`tests/test_configuration_profiles.py`](../../tests/test_configuration_profiles.py)
reads every `configuration/config*.yaml` file. It checks that:

- `app.environment`, where set, is a value of the `Environment` enum.
- The logging file named in `app.logging` exists.
- `logging.prod.yaml` uses no colour formatter.
- The `local` and `docker_test` profiles load through the real settings code with
  stub secrets, and their `authentication.server_url` has no port.
- The default profile fails without `PUBLIC_BASE_URL`, and it derives the server
  URL and the OAuth redirect URLs from `PUBLIC_BASE_URL` and `PUBLIC_PATH_PREFIX`.

When it fails, fix the YAML value the message names. A new profile file gets the
first two checks automatically.
[Configuration](./configuration.md) describes the profiles.

### Migrations

[`tests/test_migrations.py`](../../tests/test_migrations.py) tests the Alembic
migrations that move or fix data. It loads a migration file with `importlib`, builds
only the tables that the migration touches with `sa.Table(...)` on SQLite, patches
the module's `op`, and runs `upgrade` and `downgrade`:

```python
def _run(module: ModuleType, step: str, conn: Connection) -> None:
    operations = Operations(MigrationContext.configure(conn))
    with patch.object(module, "op", operations):
        getattr(module, step)()
```

A migration that only changes the schema needs no own test. A migration that moves
or fixes data gets a test that checks the rows after `upgrade` and again after
`downgrade`. Column changes on existing tables go through `op.batch_alter_table`, so
they run on SQLite.

Every migration also changes the Alembic history.
`TestSchema.test_known_revisions_are_the_alembic_history` in
[`tests/test_desktop_login.py`](../../tests/test_desktop_login.py) compares that
history with `KNOWN_REVISIONS` in [`app/desktop/schema.py`](../../app/desktop/schema.py).
The newest revision comes first. When you add a migration, put its revision at the
start of `KNOWN_REVISIONS`.

## Recipes

### A state handler test

Patch the repository and the session in the module of the state, not in the module
where the repository is defined. Then fake a signed-in admin, so the guard lets the
call through. From
[`test_departments.py`](../../components/alloq-commons/tests/test_departments.py):

```python
MODULE = "alloq_commons.state.department_states"


@pytest.fixture
def repo() -> Iterator[AsyncMock]:
    session = AsyncMock()

    @asynccontextmanager
    async def _ctx() -> AsyncIterator[Any]:
        yield session

    mock = AsyncMock()
    mock.find_all_paginated = AsyncMock(return_value=[_entity()])
    with (
        patch(f"{MODULE}.department_repo", mock),
        patch(f"{MODULE}.get_asyncdb_session", _ctx),
    ):
        yield mock
```

The same file defines `_as_admin(state, **others)`. It replaces `state.get_state` so
that it returns a fake `LoginState` with an admin user, or one of the states in
`others`. `_run(handler, *args)` runs the handler and joins its toasts into one
string:

```python
async def test_create_duplicate_shows_message(self, repo: AsyncMock) -> None:
    repo.create = AsyncMock(side_effect=IntegrityError("x", {}, Exception()))
    state = DepartmentState()
    with _as_admin(state):
        text = await _run(
            state.create_department, {"name": "IT", "abbreviation": "IT"}
        )
    assert "bereits vergeben" in text
```

Other files have their own versions of these helpers, e.g. `_admin_login` or
`as_admin`. Use the one that is already in the file you extend. A UI-only handler or
a computed var needs neither the fixture nor `_as_admin`. Create the state, set its
vars, call the handler and read the result.

For each handler, cover the normal case, the `ValidationError` case, the
`IntegrityError` case where it applies, the "not found" case, and the change of the
modal or flag.

### A service test

A pure service needs no mocks. Build the input, call the function, and check the
result. From [`test_portfolio.py`](../../components/alloq-dashboard/tests/test_portfolio.py):

```python
def test_team_scope_keeps_direct_reports_and_owned_projects() -> None:
    boss, report, other = emp(1, "Chefin"), emp(2, "A", manager_id=1), emp(3, "B")
    owned = project(10, "P10", end=friday(4), owners=(1,))
    foreign = project(11, "P11", end=friday(4), owners=(3,))
    data = inputs((owned, foreign), (boss, report, other), current=1)

    scoped = apply_scope(data, SCOPE_TEAM)

    assert [e.id for e in scoped.employees] == [2]
    assert [p.id for p in scoped.projects] == [10]
```

A loader that opens a session is tested by patching the session and the row
loaders in the service module, e.g. `aggregation.get_asyncdb_session`,
`aggregation._load_project_rows` and `aggregation._today` in
[`test_aggregation.py`](../../components/alloq-dashboard/tests/test_aggregation.py).

### A component render test

Render the component with `str(...)` and check that the output contains a var name,
a handler name or a module constant. From
[`test_departments.py`](../../components/alloq-commons/tests/test_departments.py):

```python
def test_table_renders(self) -> None:
    rendered = str(departments_table())
    assert "filtered_departments" in rendered


def test_toolbar_has_search_and_add(self) -> None:
    assert len(departments_toolbar()) == 2
```

## Pitfalls in tests

- **Assert on constants for text with umlauts.** `str(component)` escapes non-ASCII
  characters, so "nächste" appears as `n\u00e4chste` and a plain `in` check fails.
  Put the label into a module constant and assert on the constant, e.g. `COLUMNS` in
  [`test_team_list.py`](../../components/alloq-team/tests/test_team_list.py). Or
  escape the label the same way, as
  [`test_sidebar.py`](../../tests/test_sidebar.py) does with
  `json.dumps(label)[1:-1]`.
- **Use a mixin, not a substate, for extra state logic.** If a substate has computed
  vars that read parent vars, a test that creates the parent state alone fails with
  `ValueError: Invalid path [... project_list_state]`. The error only shows when the
  substate module is imported in the same test run. Write
  `class X(rx.State, mixin=True)` instead, e.g. `ProjectListState` in `ProjectState`.
  List the UI-only handlers of a mixin under the concrete state in
  `UI_ONLY_HANDLERS`, because the guard test skips mixins.
- **Give fake users a `roles` list.** `can_edit` and `can_view` read `user.roles`, so
  a fake such as `SimpleNamespace(user_id=1, is_admin=True)` crashes them. Write
  `SimpleNamespace(user_id=1, is_admin=True, roles=[])`, as
  [`test_project_plan_state.py`](../../components/alloq-project/tests/test_project_plan_state.py)
  does.
- **Keep database code in the module the tests patch.** Tests patch names such as
  `f"{MODULE}.department_repo"` and `f"{MODULE}.get_asyncdb_session"`. `patch()`
  replaces the name in the module where the code looks it up. If you move a handler
  or loader that uses the database into another module, the patch no longer
  applies, and the test reaches the real code. When you split a large file, move only
  UI-only handlers and pure functions, and keep the callers of the repository and the
  session where they are.
