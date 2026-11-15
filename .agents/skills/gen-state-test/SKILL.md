---
name: gen-state-test
description: Scaffold pytest tests for an Alloq Reflex state, with the repo's patching and rendering conventions. Use when the user asks for tests of a state, handler or mixin in an Alloq package.
disable-model-invocation: true
---

# Generate a state test

Load `reflex-testing-state` and `alloq-implementation`, then follow these Alloq rules:

- Put the test in the package's own `tests/` folder, named `test_<module>.py`.
- Patch the repository where it is used: `patch("<module under test>.<x>_repo")`, not where it is defined.
- List logic for big states lives in mixins (`mixin=True`); test the concrete state, never a substate.
- Tests run on SQLite; mock repositories instead of a database unless it is a repository test.
- Assert on module constants for German UI text. `str(component)` escapes umlauts
  and `rx.icon` renders as `LucideName`, so assert on those forms.
- Handlers with guards: see `tests/test_handler_authorization.py`; new handlers must be
  registered there when UI-only, viewer or background.
- Cover: success path, empty input, error from the repository, and authorization where relevant.

Write the failing test first and run it with `uv run pytest <file> -q --no-cov`.
