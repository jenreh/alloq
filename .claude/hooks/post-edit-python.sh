#!/usr/bin/env bash
# PostToolUse(Edit|Write): ruff-fix and format the edited Python file, warn at 1000 lines.
path=$(jq -r '.tool_input.file_path // ""')
case "$path" in *.py) ;; *) exit 0 ;; esac
[ -f "$path" ] || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv.mac}"

out=$(uv run --quiet ruff check --fix --quiet "$path" 2>&1)
status=$?
uv run --quiet ruff format --quiet "$path" >/dev/null 2>&1

lines=$(wc -l <"$path" | tr -d ' ')
if [ "$lines" -gt 1000 ]; then
  echo "Warning: $path has $lines lines (limit 1000). Refactor before finishing." >&2
  status=2
fi
if [ $status -ne 0 ]; then
  [ -n "$out" ] && echo "$out" >&2
  exit 2
fi
exit 0
