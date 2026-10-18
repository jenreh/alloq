# Known pitfalls

Each entry says what goes wrong, why, and what to do. Most come from earlier
sessions; search memory for more detail.

## State design

- **Substate instead of mixin.** A substate whose computed vars read parent vars
  breaks tests that create the parent state alone
  (`ValueError: Invalid path [... project_list_state]`). Use
  `class X(rx.State, mixin=True)` and list its UI-only handlers under the concrete
  state in `UI_ONLY_HANDLERS`.
- **Parent vars in a mixin.** Declare them only under `if TYPE_CHECKING:`; a plain
  annotation creates a second state var with the same name.
- **A guard decorator on a background handler.** `@requires_admin`,
  `@requires_editor` and `@requires_viewer` call `get_state` without the state lock
  and fail at runtime; the guard test rejects them. Use `_run_card_load`.
- **Fake users without `roles`.** `can_edit`/`can_view` read `user.roles`; a
  `SimpleNamespace(user_id, is_admin)` fake crashes them. Add `roles=[]`.
- **UI-only handler that calls a loader.** If an "open dialog" handler also loads data,
  it is no longer UI-only. Split it: guarded loader handler plus UI-only toggle, or
  guard the whole handler and keep it out of the allowlist.
- **"reading 'length'" crash in the running dev app** after adding state classes.
  The browser holds the old state shape. Reload the page and sign in again; it is
  not a code bug.

## UI

- **`de_number` ignores `fz`, `c`, `fw`.** It renders a bare text node. Wrap it:
  `mn.text(de_number(v, suffix=" PT"), fz=..., c=..., span=True)`, or use `number()`
  in `alloq_dashboard/components/portfolio_shared.py`.
- **Colors outside the theme.** Use `alloq_commons.theme` tokens and scales. The
  Alloq design-system artifact with teal colors is outdated; the app is macOS blue.
- **Sticky headers in the planning grids** need `width` equal to the table width
  (`PlanningStore.table_width`, gantt `_total_width()`), or their background stops
  at the viewport edge when scrolling right.
- **`max_length=` on `mn.text_input` does nothing.** appkit_mantine renders unknown
  snake_case props as CSS (`css:{["maxLength"]: 20}`), so the browser never limits
  typing. Use `custom_attrs={"maxLength": N}`; `alloq_commons/components/forms.py`
  uses `maxlength=` which also reaches the DOM. About 14 older inputs still pass
  `max_length=`; fix them only when asked, and rely on the `XCreate` limits server-side.
- **English UI text slipped in.** Labels, placeholders, toasts, empty states and
  confirmations are German. Log messages stay English.

## Tests

- **Umlauts in render tests.** `str(component)` escapes `ä` as `\u00e4`. Assert on
  the module constant, or use `json.dumps(label)[1:-1]` like `tests/test_sidebar.py`.
- **Stale allowlist entry.** Renaming or guarding a handler without updating
  `UI_ONLY_HANDLERS` fails `test_allowlists_have_no_stale_entries`.
- **New migration without `KNOWN_REVISIONS`.** `tests/test_desktop_login.py`
  compares `app/desktop/schema.py` with the Alembic history; prepend the new revision.

## Migrations

- Written by hand; never `alembic revision --autogenerate`.
- File name `YYYY_MM_DD_<topic>.py`; `down_revision` is the current head (check the
  newest files in `alembic/versions/`, several can share one date).
- Column changes on existing tables go through `op.batch_alter_table` so they run on
  SQLite in tests.
- `downgrade()` really reverses the upgrade, including moved data.

## Files over the 1000-line limit

These were already too long when this skill was written:

| File | Lines (2026-10-18) |
| --- | --- |
| `alloq_project/states/project_state.py` | ~1460 |
| `alloq_project/states/project_plan_state.py` | ~1250 |
| `alloq_dashboard/services/aggregation.py` | ~1190 |
| `alloq_team/states/team_state.py` | ~990 (at the limit) |

When a task touches one of them:

- Bug fixes: keep the change local and small; do not refactor unasked.
- New features: put new code into a new module (a mixin for states, a new service
  module for aggregation logic) and import it, so the file does not grow.
- Mention the file size in the summary so the user can plan a split.

Run `python .claude/skills/alloq-implementation/scripts/check_file_sizes.py` for the
current list.

## Folders

- `alloq_commons/state/` and `alloq_commons/states/` both exist. Follow the folder of
  the closest neighbour; do not move files.
- `alloq-team/tests/` has no `conftest.py`; do not assume fixtures from
  `appkit_commons.testing` there without adding one deliberately.
