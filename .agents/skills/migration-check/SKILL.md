---
name: migration-check
description: Validate a hand-written Alembic revision in Alloq (single head, down_revision chain, reversible downgrade, naming) without running it against any database. Use after writing or editing a file in alembic/versions.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep
---

# Migration check

Never run alembic upgrade, downgrade or stamp: the local profile uses a shared Postgres.
Revisions are written by hand, with no autogenerate.

1. List the revision files and read the newest one: `ls alembic/versions | tail -5`.
2. Find the heads: every `down_revision` value is a parent. Exactly one revision may not
   appear as a parent. Check with
   `grep -h "^revision\|^down_revision" alembic/versions/*.py`.
3. Confirm the new file has `revision`, `down_revision` pointing at the previous head,
   a docstring with `Revision ID`, `Revises`, `Create Date`, and a real `downgrade()`
   that undoes `upgrade()` in reverse order.
4. Check naming: foreign keys `fk_<table>_<col>_<reftable>`, indexes `ix_<table>_<col>`,
   unique constraints `uq_...`. Use `op.batch_alter_table` (SQLite tests need it).
5. Check existing rows: a new NOT NULL column needs a `server_default` or a backfill;
   a new FK needs a sensible `ondelete`.
6. Run `uv run pytest tests/test_migrations.py -q` and report the result.

Report problems as a list with file and line. Do not fix them unless asked.
