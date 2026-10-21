#!/usr/bin/env bash
# Print Markdown release notes from the conventional commits between two refs.
# Usage: scripts/release_notes.sh [since-tag] [until-ref]
#   since-tag defaults to the latest tag, until-ref to HEAD
set -euo pipefail

since="${1:-$(git describe --tags --abbrev=0 2>/dev/null || true)}"
until="${2:-HEAD}"
range="${since:+$since..}$until"

git log --no-merges --format='%h%x09%s' "$range" | awk -F'\t' '
  BEGIN {
    n = split("feat fix perf refactor other", order, " ")
    titles["feat"] = "Features"
    titles["fix"] = "Bug fixes"
    titles["perf"] = "Performance"
    titles["refactor"] = "Refactoring"
    titles["other"] = "Other changes"
  }
  $2 ~ /^chore(\([^)]*\))?: release / { next }
  {
    sha = $1; text = $2; type = "other"; scope = ""
    if (match(text, /^[a-z]+(\([^)]*\))?!?: /)) {
      head = substr(text, 1, RLENGTH - 2)
      text = substr(text, RLENGTH + 1)
      sub(/!$/, "", head)
      type = head
      if ((p = index(head, "(")) > 0) {
        type = substr(head, 1, p - 1)
        scope = substr(head, p + 1, length(head) - p - 1)
      }
    }
    if (type == "feature") type = "feat"
    if (!(type in titles)) type = "other"
    prefix = (scope != "") ? "**" scope ":** " : ""
    items[type] = items[type] "- " prefix text " (" sha ")\n"
  }
  END {
    for (i = 1; i <= n; i++) {
      t = order[i]
      if (items[t] != "") printf "## %s\n\n%s\n", titles[t], items[t]
    }
  }'
