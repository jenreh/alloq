#!/usr/bin/env bash
# Stop: run the tests of every component with uncommitted Python changes.
input=$(cat)
[ "$(jq -r '.stop_hook_active // false' <<<"$input")" = "true" ] && exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv.mac}"

targets=$(git status --porcelain -- 'components/*.py' 'app/*.py' 'tests/*.py' \
  | awk '{print $NF}' \
  | sed -E 's#^(components/[^/]+)/.*#\1/tests#; s#^(app|tests)/.*#tests#' \
  | sort -u | while read -r d; do [ -d "$d" ] && echo "$d"; done)
[ -z "$targets" ] && exit 0

# shellcheck disable=SC2086
out=$(timeout 280 uv run --quiet pytest $targets -q -x --no-cov -p no:cacheprovider 2>&1)
if [ $? -ne 0 ]; then
  echo "Tests failed for changed components:" >&2
  tail -n 40 <<<"$out" >&2
  exit 2
fi
exit 0
