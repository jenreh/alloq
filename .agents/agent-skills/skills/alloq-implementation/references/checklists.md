# Checklists per change type

Use the list that matches the task. Each step names the file to touch, so you can
see quickly what a complete change looks like.

## New field on an existing entity

1. Entity `commons/entities/<x>.py`: `Mapped[...] = mapped_column(...)`; optional
   fields are `Mapped[str | None]` with `nullable=True`.
2. `to_dict()` in the same entity: add the key. Read models are built from it, so a
   missing key silently drops the value.
3. Read model `commons/models/<x>.py`: field with a default (`""`, `0`, `None`).
4. Write model `XCreate`: field with `Field(...)` limits that match the column.
5. Form parsing in the state (`_x_from_form`) and the create/update handlers: set
   the new attribute on the entity.
6. Component: form field (`mn.text_input(name=..., label="<German>", ...)` with
   `default_value` for edit mode and `custom_attrs={"maxLength": N}` for a length
   limit), table column and header if it should show. Keep the label in a module
   constant so tests can assert on it.
7. Migration `alembic/versions/YYYY_MM_DD_<topic>.py`: hand-written,
   `with op.batch_alter_table("<table>") as batch_op: batch_op.add_column(...)`,
   `downgrade()` drops it. `down_revision` is the current head; prepend the new
   revision to `KNOWN_REVISIONS` in `app/desktop/schema.py`.
8. Desktop app reads with the same entities, so no extra desktop code is needed
   unless `app/desktop/` code lists columns explicitly (grep for the table name).
9. Tests: `to_dict` key, write model limits, handler stores the value, component
   renders the field.

## New entity

Everything above, plus: repository with singleton, exports in `entities/__init__.py`,
`models/__init__.py`, `repositories/__init__.py`, `op.create_table` with
`created`/`updated` columns like `2026_10_18_departments.py`, and a test file.

## New state handler

1. Decide the guard (SKILL.md, security section). Default is `@rx.event` +
   `@requires_editor`; administration states use `@requires_admin`.
2. UI-only: add the name to `UI_ONLY_HANDLERS["<ConcreteState>"]` in
   `tests/test_handler_authorization.py`, sorted like its neighbours. In a mixin,
   use the concrete state's name.
3. Keep data access in a repository or loader; the handler calls it inside
   `async with get_asyncdb_session() as session:`.
4. German toast texts; `logger.exception` in the last `except`.
5. Tests: one per path (success, validation, not found, error).
6. Run `uv run pytest tests/test_handler_authorization.py -q`.

## New computed var or filter

1. `@rx.var` method on the state or mixin, returning a typed value.
2. If it needs a new UI-only setter, follow "New state handler".
3. Test by setting vars on a bare state and reading the var.

## New page

1. Components in the feature package (`<pkg>/components/<x>.py`).
2. Page factory: admin page in `app/pages/<x>.py`, feature page in `<pkg>/pages.py`;
   `app_page(route=..., title="<German>", sidebar=sidebar, toolbar=window_toolbar(...),
   admin_only=True, on_load=[XState.load_x])`.
3. Register in `app/app.py` (`create_x_page(sidebar())`) and add
   `("/route", "<German label>", "<lucide icon>")` to `PLANNING_ITEMS` or
   `ADMIN_ITEMS` in `app/components/sidebar.py`.
4. Tests: render tests for the new components in the feature package;
   `tests/test_sidebar.py::...::test_renders_navigation_entries` already loops over
   all sidebar items, so a new entry is covered once it renders.

## New service

1. Pure function or frozen dataclass in `<pkg>/services/<topic>.py`; input is rows or
   models, output is a model or dataclass. No session inside the pure part.
2. Loader in a separate function or `*_inputs.py` module if it reads the DB.
3. A DB-reaching function name that a UI-only handler might call must not be added
   to a UI-only handler; the guard test checks `aggregation.` and similar markers.
4. Tests: plain unit tests for the pure part; patched session for the loader.

## Bug fix

1. Reproduce with a failing test in the test file of the code that is wrong. Name it
   after the expected behaviour (`test_drill_down_score_clamps_impact`).
2. Fix at the source of the wrong value, not where it shows. If two places compute
   the same thing, make one call the other instead of copying the formula.
3. Keep the diff small, even in files over 1000 lines; note the file size in your
   summary instead of refactoring unasked.
4. Run the touched test file, then the full gates.
