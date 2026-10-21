---
title: Contributing
description: How to change Alloq code - where each layer lives, tests first, the handler guard rules, the quality gates, hand-written migrations, and how to keep the story map current.
source_paths:
  - .claude/skills/alloq-implementation/SKILL.md
  - .claude/skills/alloq-implementation/references/architecture.md
  - .claude/skills/alloq-implementation/references/checklists.md
  - .claude/skills/alloq-implementation/references/pitfalls.md
  - .claude/skills/alloq-implementation/references/testing.md
  - .claude/skills/alloq-implementation/scripts/check_file_sizes.py
  - AGENTS.md
  - tests/test_handler_authorization.py
  - tests/test_component_boundaries.py
  - app/desktop/schema.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Contributing

This page explains how the team changes Alloq code. It follows the house rules in
[.claude/skills/alloq-implementation/SKILL.md](../../.claude/skills/alloq-implementation/SKILL.md),
which AI agents load before every code change. The rules are the same for people.

Read [Getting started](./getting-started.md) first, so the app and the tests run on
your machine.

## The workflow for every change

1. **Look for earlier decisions.** Search the team memory for the feature words
   and for any error text you see. Earlier sessions stored known traps there.
2. **Read the code of the layer you touch.** The departments slice is the
   reference for every layer. Copy its shape. The
   [Layers](../architecture/layers.md) page walks through it.
3. **Plan the smallest change.** Touch only the layers the task needs. Do not move
   files, rename folders or refactor neighbouring code unless the task asks for it.
4. **Write or adjust the test first.** For a bug, first write a test that fails
   because of the bug. Run the touched test files once before you change code, so
   you know which failures were there before you started.
5. **Implement the change.**
6. **Run the gates.** `task format && task lint && task typecheck && task test`.
   For a quick loop, run only the touched test file with `uv run pytest <file> -q`.
   Run `tests/test_handler_authorization.py` every time you add or change an event
   handler.
7. **Check file sizes.** Run
   `python .claude/skills/alloq-implementation/scripts/check_file_sizes.py`.
8. **Update the story map** if the change adds or changes behaviour that a user can
   see. See [Keep the story map alive](#keep-the-story-map-alive).

## Where code goes

Alloq has a host app in `app/` and four uv workspace packages in `components/`.

| Package | What it holds |
| --- | --- |
| `alloq-commons` | Entities, models, repositories, shared services, shared UI parts, `theme.py`, `roles.py`, `access.py`, and the administration states |
| `alloq-project` | Projects and capacity planning, in `components/`, `services/`, `states/` and `pages.py` |
| `alloq-dashboard` | Dashboard and portfolio, with the same layout plus `models.py` for card data |
| `alloq-team` | Team overview and employees, with the same layout |

Data flows through these layers. The paths are for departments, under
`components/alloq-commons/src/alloq_commons/`.

| Layer | Example file | Rule |
| --- | --- | --- |
| Entity | `entities/department.py` | `class DepartmentEntity(Entity, Base)` with a `to_dict()` that returns every field |
| Model | `models/department.py` | A Pydantic read model, plus a `DepartmentCreate` write model with `Field` limits |
| Repository | `repositories/department_repository.py` | A `BaseRepository` subclass and a module singleton `department_repo` |
| Service | `<package>/services/*.py` | Pure functions and dataclasses. Database loading stays in loader functions or `*_inputs.py` modules |
| State | `state/department_states.py` | An `rx.State` with `rx.Field` vars and `@rx.event` handlers |
| Component | `components/department.py` | Plain functions that return `rx.Component`, built from `mn.*` and shared parts |
| Page | [app/pages/departments.py](../../app/pages/departments.py) | A page factory such as `create_departments_page(sidebar, route, title)` that uses `app_page` |
| Registration | [app/app.py](../../app/app.py) | Call the factory with `sidebar()`, and add a sidebar entry in `app/components/sidebar.py` if needed |
| Migration | [alembic/versions/2026_10_18_departments.py](../../alembic/versions/2026_10_18_departments.py) | Hand-written, with a real `downgrade()` |

The import direction is fixed. Feature packages import `alloq_commons` and appkit,
and never `app`. [tests/test_component_boundaries.py](../../tests/test_component_boundaries.py)
(`test_components_do_not_import_host_app`) fails otherwise. Feature packages do not
import each other unless that import already exists. The host app may import
everything.

`alloq_commons` has a `state/` folder (departments, roles, daily rates) and a
`states/` folder (holidays). Put new code next to its closest neighbour and do not
merge the two folders.

### Which layer for which kind of code

- **A calculation**, e.g. a score, a sum or a sort order, goes into a service
  function or a small dataclass that you can test without a database.
  `alloq_project/services/project_sorting.py` is one example.
- **Database reads and writes** go through a repository method or a loader
  function. States do not build SQL.
- **UI state**, e.g. an open dialog or a filter, lives in the state. When a state
  file is large, put new vars and handlers into a mixin
  (`class X(rx.State, mixin=True)`). Do not use a substate, because substates break
  the tests that create the state on its own.
- **Rendering** goes into function components that read state vars. Keep logic in
  them to `rx.cond`, `rx.foreach` and formatting.
- **A value that both the UI and a test need**, e.g. a label or a column list,
  becomes a module constant, so the test can assert on it.

[Architecture overview](../architecture/overview.md) and
[Layers](../architecture/layers.md) describe the structure in more detail.

## Guard every event handler

Reflex runs event handlers over a websocket for anyone with a session. A page guard
only hides the page, so every handler must check the rights itself. The access
levels are in `alloq_commons.access`:

- Administrators may do everything.
- The project manager role ("Projektmanager") may read and edit every planning
  page, but not the administration.
- The employee role ("Mitarbeiter") may only read the planning and projects pages.

For each new or changed handler, pick exactly one of these cases:

1. **The handler reads or writes data in a planning package** (`alloq_dashboard`,
   `alloq_project`, `alloq_team`, or `SidebarState`). Put `@rx.event` and then
   `@requires_editor` from `alloq_commons.access` on it. This is the default.
2. **The handler is in an administration state.** These are `DailyRateState`,
   `DepartmentState`, `RoleState`, `HolidayState` and `DatabaseAccessState`, listed
   in `ADMIN_STATES`. Use `@requires_admin` from
   `appkit_user.authentication.decorators`.
3. **The handler only reads, and employees may run it.** Use `@requires_viewer` and
   add the name to `VIEWER_HANDLERS`. The handler must not write.
4. **The handler only changes UI state**, e.g. it opens a dialog or sets a filter.
   Use no guard and add the name to `UI_ONLY_HANDLERS["<ConcreteState>"]`. The test
   scans the handler and the `self.` helpers it calls for database markers such as
   `get_asyncdb_session` and `_repo.`, so the handler must not touch a repository
   or a session.
5. **The handler is a background handler** (`@rx.event(background=True)`). Guard
   decorators do not work there, because they need the state lock. Check the rights
   inside `async with self` through `_CardLoadMixin._run_card_load`, and list the
   handler in `INLINE_ADMIN_CHECK`.

All lists are in [tests/test_handler_authorization.py](../../tests/test_handler_authorization.py).
Handlers from a mixin are listed under the concrete state that uses the mixin,
e.g. `TeamState`, `ProjectState` or `PlanningStore`. Remove a list entry when you
delete or guard the handler, because stale entries fail the test too.

Edit controls in the planning UI go inside `editor_only(...)` or use
`disabled=~CAN_EDIT`. Use `admin_only(...)` only in the administration.
[Security and access](../architecture/security-and-access.md) explains the whole
access model.

## Style rules that ruff does not check

- UI text is German, including toasts, placeholders, empty states and
  confirmations. Code, comments, docstrings and log messages are English.
- Every module has `logger = logging.getLogger(__name__)`. Log calls use `%s`
  arguments and never f-strings. Use `logger.debug` by default, `logger.info` for
  important events, and `logger.warning` or `logger.error` only for problems. Do not
  use `print`.
- A handler handles errors in this order: a `ValidationError` shows a German hint,
  an `IntegrityError` shows a duplicate message, and any other `Exception` calls
  `logger.exception` and shows a generic German error toast.
- Colors, radii and shadows come only from `alloq_commons.theme`. The theme is
  macOS blue.
- Use `mn.*` components from appkit_mantine and the shared parts, e.g.
  `modal_form_layout`, `delete_dialog`, `toolbar_search`, `app_page` and
  `window_toolbar`.
- `max_length=20` on an `mn` input becomes CSS and limits nothing. Use
  `custom_attrs={"maxLength": 20}` for the browser limit, and keep the real check in
  the write model with `Field(max_length=20)`.
- Every function has type hints, also in tests. Lines are at most 88 characters.

## Keep files under 1000 lines

No Python file should grow past 1000 lines.
`.claude/skills/alloq-implementation/scripts/check_file_sizes.py` lists every file
in `app/` and `components/*/src` that is over the limit and exits with code 1 if it
finds one. At `cb9d5b0` it finds none. These files are close to the limit:

| File | Lines at `cb9d5b0` |
| --- | --- |
| `alloq_project/states/project_plan_state.py` | 995 |
| `alloq_project/states/project_state.py` | 983 |
| `alloq_team/states/team_state.py` | 982 |
| `alloq_dashboard/services/aggregation.py` | 965 |

When you add a feature to one of them, put the new code into a new module, e.g. a
mixin for a state or a new service module, and import it. For a bug fix, keep the
change small and local, and do not refactor the file unless someone asks for it.

## Write migrations by hand

Never run `alembic revision --autogenerate`. `task db:revision -- "message"` creates
a new file without steps, and you write the steps yourself. The `file_template` in
[alembic.ini](../../alembic.ini) names the file `YYYY_MM_DD_<slug>.py`.

- Check that `down_revision` is the current head. Several files can share one
  date, so look at the newest files in `alembic/versions/`.
- Change columns of existing tables with `op.batch_alter_table`, so the migration
  also runs on SQLite in the tests.
- Write a `downgrade()` that undoes the upgrade, including any data it moved.
- Add the new revision at the front of `KNOWN_REVISIONS` in
  [app/desktop/schema.py](../../app/desktop/schema.py). The desktop app compares
  the database with this list, and
  `tests/test_desktop_login.py::TestSchema::test_known_revisions_are_the_alembic_history`
  fails if you forget it.
- If the migration changes data, add a test to `tests/test_migrations.py`.

## Checklists per change type

[references/checklists.md](../../.claude/skills/alloq-implementation/references/checklists.md)
lists every file to touch for these changes:

- a new field on an existing entity
- a new entity
- a new state handler
- a new computed var or filter
- a new page
- a new service
- a bug fix

[references/pitfalls.md](../../.claude/skills/alloq-implementation/references/pitfalls.md)
lists known traps, e.g. a fake user without `roles` that crashes `can_edit`, or
umlauts that `str(component)` escapes in render tests.

## Definition of done

- [ ] The test was written first, and it covers the new behaviour or the bug.
- [ ] `task format && task lint && task typecheck && task test` all pass.
- [ ] `tests/test_handler_authorization.py` and `tests/test_component_boundaries.py`
      pass.
- [ ] Every new handler has its guard or its list entry.
- [ ] A new migration is hand-written, uses `op.batch_alter_table` for column
      changes, has a real `downgrade()`, and its revision is in `KNOWN_REVISIONS`.
- [ ] No touched file grew past 1000 lines.
- [ ] UI text is German, colors come from the theme, there is no `print`, and log
      calls use no f-strings.
- [ ] The story map and its feature page describe the change.

## Keep the story map alive

The [story map](../features/story-map.md) describes everything Alloq does, as user
stories that come from the code. It belongs to the whole team, not to one person.
When the code changes and the map does not, the map is wrong, and the next reader
trusts a wrong page. So every change that a user can notice also updates the map,
in the same pull request.

For every feature change, do these steps:

1. **Find the story.** Search the feature pages for the state, handler or service
   you changed. Each story lists them in its Evidence block.
2. **Add or update the story.** A new behaviour gets a new story. A changed
   behaviour updates the story that already describes it. A removed behaviour
   removes its story, and the map entry with it.
3. **Write it in the agreed shape.**
   - The heading has a stable ID and an anchor, e.g.
     `## PLAN-03 Short title {#plan-03}`. The ID is `<AREA>-<NN>`. Never reuse or
     renumber an ID, because other pages link to it.
   - Start with one plain sentence that says what the story is about.
   - Then write `As a <persona>, I want <goal>, so that <benefit>`, with one persona:
     Administrator, Project manager, Employee, Offer editor or Desktop user.
   - Write each acceptance criterion as Given, When, Then. Each one must match a
     concrete rule in the code, e.g. a `Field(max_length=...)` limit, a guard, a
     filter, a calculation or an error message.
   - Add an Evidence block with relative links to the source files and tests, and
     name the symbol next to each link.
   - Mark a criterion that no test covers with `(no test)`.
   - If you are not sure how the code behaves, write the question under "Open
     questions". Do not guess.
4. **Place it on the map.** Put the story under the user task and sub-task it
   belongs to, ordered by how much the task needs it. Core behaviour goes above
   comfort features such as filters or saved view settings. Put it in the release
   slice that introduces it. Until the next release tag exists, that slice is
   "unreleased".
5. **Update `last_verified_commit`** in the frontmatter of every page you checked
   against the code.

In the review, check the story against the code. Every path and symbol in the
Evidence block must exist, and a search with `rg` for each of them confirms it.
