#!/usr/bin/env bash
# PreToolUse(Bash): block Alembic commands that touch a database or autogenerate.
# The local profile points at a shared Postgres, and migrations are hand-written.
cmd=$(jq -r '.tool_input.command // ""')
# alembic must be invoked as a command, not merely mentioned in text
start='(^|[;&|(]|uv run|uvx|python3? -m)[[:space:]]*alembic'

if grep -Eq "${start}[^|;&]*--autogenerate" <<<"$cmd"; then
  echo "Blocked: write Alembic revisions by hand (no --autogenerate)." >&2
  exit 2
fi
if grep -Eq "${start}[[:space:]]+(-[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]+)*(upgrade|downgrade|stamp)\b" <<<"$cmd"; then
  echo "Blocked: never run alembic upgrade/downgrade/stamp from here; the local profile uses a shared database. Ask the user to run it." >&2
  exit 2
fi
exit 0
