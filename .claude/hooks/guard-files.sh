#!/usr/bin/env bash
# PreToolUse(Edit|Write|NotebookEdit): block generated, secret and data files.
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // ""')
[ -z "$path" ] && exit 0
name=$(basename "$path")

case "$name" in
  uv.lock|reflex.lock|coverage.xml|.env|.env.*|*.db|*.db-shm|*.db-wal|*.sqlite3|*.sqlite3-shm|*.sqlite3-wal)
    case "$name" in .env.example|.env.sample) exit 0 ;; esac
    echo "Blocked: $name is generated, a secret or a local database. Use uv add / the task runner, or edit it yourself." >&2
    exit 2 ;;
esac
case "$path" in
  */uploaded_files/*)
    echo "Blocked: uploaded_files/ holds user data." >&2
    exit 2 ;;
esac
exit 0
