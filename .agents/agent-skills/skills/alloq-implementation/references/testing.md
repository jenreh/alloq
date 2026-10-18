# Alloq testing

## Contents

1. Setup and commands
2. Where tests go
3. State tests: repo patch, `_as_admin`, `_run`
4. Service and loader tests
5. Component tests
6. Migration tests
7. The guard tests

## 1. Setup and commands

- `pyproject.toml`: `asyncio_mode = "auto"` (async tests need no marker),
  `import_mode = "importlib"`, branch coverage with `fail_under = 80`.
- Package conftests (`alloq-commons`, `alloq-project`, `alloq-dashboard`) contain only
  `pytest_plugins = ["appkit_commons.testing"]`. `alloq-team/tests` has none.
- Ruff relaxes `S101`, `PLR2004`, `SLF001` in tests, so `assert`, magic numbers and
  `aggregation._RiskRow(...)` are fine there. Type hints are still expected.
- Fast loop: `uv run pytest components/alloq-commons/tests/test_departments.py -q`.
  Full gate: `task test` (`pytest --cov`).

## 2. Where tests go

| Code in | Test in |
| --- | --- |
| `components/alloq-commons/src/...` | `components/alloq-commons/tests/test_<feature>.py` |
| `components/alloq-<pkg>/src/...` | `components/alloq-<pkg>/tests/test_<feature>.py` |
| `app/...`, migrations, cross-package guards | `tests/test_<topic>.py` |

Extend the existing test file of the feature (for departments:
`test_departments.py`, for dashboard KPIs: `test_aggregation.py`, for the project
state: `test_project_state.py` / `test_project_state_handlers.py`) before creating a
new one. Group with `class TestX:` like the neighbours do.

## 3. State tests

Canonical helpers: `components/alloq-commons/tests/test_departments.py`. Other files
have their own variants (`_admin_login`, `as_admin`, `_login_as_admin`); use the one
already in the file you extend. Only extract a shared helper when you touch those
files anyway.

Patch the repository and the session in the state module:

```python
MODULE = "alloq_commons.state.department_states"


@pytest.fixture
def repo() -> Iterator[AsyncMock]:
    """Patch the department repository and the DB session."""
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

Fake an admin so `@requires_admin` lets the call through. `others` supplies states
that the handler fetches with `get_state`:

```python
@contextmanager
def _as_admin(state: DepartmentState, **others: Any) -> Iterator[None]:
    user = MagicMock(is_admin=True, user_id=1)

    async def _user() -> MagicMock:
        return user

    login = MagicMock()
    type(login).authenticated_user = property(lambda _self: _user())
    login.redir = AsyncMock(return_value=None)

    async def _get_state(cls: type) -> Any:
        return login if cls is LoginState else others[cls.__name__]

    object.__setattr__(state, "get_state", _get_state)
    try:
        yield
    finally:
        object.__delattr__(state, "get_state")
```

Drive a handler and collect its toasts as text:

```python
async def _run(handler: Any, *args: Any) -> str:
    """Drive a handler and return its toasts as text."""
    result = handler(*args)
    if hasattr(result, "__aiter__"):
        return " ".join([str(i) async for i in result if i is not None])
    await result
    return ""
```

Typical tests:

```python
async def test_create_duplicate_shows_message(self, repo: AsyncMock) -> None:
    repo.create = AsyncMock(side_effect=IntegrityError("x", {}, Exception()))
    state = DepartmentState()
    with _as_admin(state):
        text = await _run(
            state.create_department, {"name": "IT", "abbreviation": "IT"}
        )
    assert "bereits vergeben" in text


def test_filter_matches_name_or_abbreviation(self) -> None:
    state = DepartmentState()
    state.departments = [
        Department(id=1, name="Informationstechnik", abbreviation="IT"),
        Department(id=2, name="Personal", abbreviation="HR"),
    ]
    state.search_filter = "hr"
    assert [d.id for d in state.filtered_departments] == [2]
```

UI-only handlers and computed vars need neither the repo fixture nor `_as_admin`:
create the state, set vars, call the handler, read the computed var.

Per state test cover: happy path, `ValidationError` path, `IntegrityError` path where
it applies, "not found" path, and that the modal or flag changes as expected.

## 4. Service and loader tests

Pure services need no mocks. From `components/alloq-dashboard/tests/test_portfolio.py`:

```python
def test_team_scope_keeps_direct_reports_and_owned_projects() -> None:
    ...
    assert [e.id for e in scoped.employees] == [2]
    assert [p.id for p in scoped.projects] == [10]
```

Loaders that open a session are tested by patching the session and the row loaders
in the service module. From `test_aggregation.py`:

```python
with (
    patch("alloq_dashboard.services.aggregation.get_asyncdb_session", fake_session),
    patch(
        "alloq_dashboard.services.aggregation._load_project_rows",
        return_value=projects,
    ),
    patch(
        "alloq_dashboard.services.aggregation._load_risk_rows",
        return_value=risks[:1],
    ),
    patch(
        "alloq_dashboard.services.aggregation._today",
        return_value=date(2026, 5, 8),
    ),
):
    payload = await aggregation.load_project_health()
```

Mapping functions such as `_risk_to_row(entity)` can be tested directly with an
entity built in the test (`RiskEntity(...)` with `id` set by hand).

## 5. Component tests

Render with `str(...)` and assert on var names, handler names or module constants:

```python
def test_table_renders(self) -> None:
    rendered = str(departments_table())
    assert "filtered_departments" in rendered


def test_toolbar_has_search_and_add(self) -> None:
    assert len(departments_toolbar()) == 2
```

`str(component)` JSON-escapes non-ASCII text, so `"nächste"` shows as
`"n\u00e4chste"`. Put labels with umlauts into a module constant (for example
`COLUMNS` in `alloq_team/components/employee_table.py`) and assert on the constant.

## 6. Migration tests

Schema-only migrations need no own test. Migrations that move or fix data get a test
in `tests/test_migrations.py`, run offline on SQLite with the module's `op` patched:

```python
def _load(filename: str) -> ModuleType:
    path = VERSIONS / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    ...


def _run(module: ModuleType, step: str, conn: Connection) -> None:
    operations = Operations(MigrationContext.configure(conn))
    with patch.object(module, "op", operations):
        getattr(module, step)()
```

Build only the tables the migration touches with `sa.Table(...)` in a fixture, run
`upgrade`, assert rows, run `downgrade`, assert again.

Every migration changes the Alembic history, so also prepend the revision to
`KNOWN_REVISIONS` in `app/desktop/schema.py`;
`tests/test_desktop_login.py::TestSchema::test_known_revisions_are_the_alembic_history`
fails otherwise.

## 7. The guard tests

- `tests/test_handler_authorization.py`: every handler is guarded or allowlisted (see
  SKILL.md). Its failure message lists the offending `State.handler` names.
- `tests/test_component_boundaries.py`: no file under `components/*/src` imports `app`.

Run both after adding handlers or imports; they are fast.
