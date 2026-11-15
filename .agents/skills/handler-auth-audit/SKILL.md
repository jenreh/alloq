---
name: handler-auth-audit
description: Audit Reflex event handlers in an Alloq package against the handler authorization contract (requires_editor, requires_viewer, requires_admin, UI-only, background). Use after adding or changing a state handler, or before merging a feature that touches states.
allowed-tools: Bash, Read, Grep
---

# Handler authorization audit

The contract lives in `alloq-implementation` ("Security: the handler authorization
contract") and is enforced by `tests/test_handler_authorization.py`.

1. List the handlers in scope: `grep -n "@rx.event" -A3 components/<pkg>/src/<module>/states/*.py`
   (or the state files the user names).
2. For each handler decide the single correct case:
   - touches DB in a planning package -> `@requires_editor`
   - administration state -> `@requires_admin`
   - read-only load for the employee role -> `@requires_viewer` and listed in `VIEWER_HANDLERS`
   - offers/price list read by every signed-in user -> listed in `SIGNED_IN_HANDLERS`
   - UI state only -> no decorator, listed in `UI_ONLY_HANDLERS["<State>"]`, no repo or session use
   - background -> no decorator, inline `_can_edit` check, listed in `INLINE_ADMIN_CHECK`
3. Decorator order: `@rx.event` first, the guard directly below it.
4. Run `uv run pytest tests/test_handler_authorization.py -q`.

Output a table: handler, expected case, actual, verdict. Flag missing guards first.
