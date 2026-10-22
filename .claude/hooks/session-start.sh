#!/usr/bin/env bash
# SessionStart: short orientation printed into the session context.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
echo "Branch: $(git branch --show-current)"
echo "Uncommitted files: $(git status --porcelain | wc -l | tr -d ' ')"
echo "Reminder: UV_PROJECT_ENVIRONMENT=.venv.mac (.venv is stale). Never run alembic against the shared DB. Load the alloq-implementation skill before code changes."
exit 0
