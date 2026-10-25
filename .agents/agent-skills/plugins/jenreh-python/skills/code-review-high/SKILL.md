---
name: code-review-high
description: >
  High-effort, recall-oriented code review of the current diff (or a PR, branch or
  path): eight finder angles (line scan, removed behavior, cross-file tracer, reuse,
  simplification, efficiency, altitude, instruction-file conventions) run in parallel
  agents when the tool supports them, dedup only, at most 10 findings. Works in Claude Code, Codex and GitHub Copilot. Use when the
  user asks for a thorough review, "review my changes", or "review before commit".
license: MIT
---

`high effort → 8 angles (parallel agents if available) → dedup (no verify) → ≤10 findings`

You are reviewing for **recall** at high effort: catch every real bug a careful
reviewer would catch in one sitting. At this level, catching real bugs matters
more than avoiding false positives. Err on the side of surfacing.

## Phase 0 — Gather the diff

Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there's no upstream) to get the unified diff under review. If there are
uncommitted changes, or the range diff is empty, also run `git diff HEAD` and
include the working-tree changes in scope — the review often runs before the
commit. If a PR number, branch name, or file path was passed as an argument,
review that target instead. Treat this diff as the review scope.

## Phase 1 — Find candidates (3 correctness + 3 cleanup + 1 altitude + 1 conventions angle, up to 6 candidates each)

Run **8 independent finder angles**. Each surfaces **up to 6 candidate findings**
with `file`, `line`, a one-line `summary`, and a concrete `failure_scenario`.

**Parallel when available.** If the tool can start subagents (Claude Code: the
`Agent` tool; Codex: subagents; Copilot: sub-agents or `/fleet`), start one agent
per angle, all 8 in a single step so they run in parallel. Give each agent: the
diff scope from Phase 0 (or how to get it), its angle's full text from this
file, the cap of 6 candidates, the required fields, and the instruction to
report candidates only and not to edit files. Use a read-only agent type when the
tool has one. Wait for all of them, then pool the results for Phase 2. If an
agent fails or returns nothing, run that angle yourself.

**Inline otherwise.** If the tool has no way to start agents, or the user asked
for no subagents, run the 8 angles in sequence yourself in THIS context.

### Angle A — line-by-line diff scan

Read every hunk in the diff, line by line. Then Read the enclosing function for
each hunk — bugs in unchanged lines of a touched function are in scope (the PR
re-exposes or fails to fix them). For every line ask: what input, state, timing,
or platform makes this line wrong? Look for inverted/wrong conditions,
off-by-one, null/undefined deref, missing `await`, falsy-zero checks,
wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars.

### Angle B — removed-behavior auditor

For every line the diff DELETES or replaces, name the invariant or behavior it
enforced, then search the new code for where that invariant is re-established.
If you can't find it, that's a candidate: a removed guard, a dropped error
path, a narrowed validation, a deleted test that was covering a real case.

### Angle C — cross-file tracer

For each function the diff changes, find its callers (Grep for the symbol) and
check whether the change breaks any call site: a new precondition, a changed
return shape, a new exception, a timing/ordering dependency. Also check callees:
does a parallel change in the same PR make a call unsafe?

### Reuse

The angles above hunt for bugs; this one and the next two hunt for cleanup in
the changed code. Flag new code that re-implements something the codebase
already has — Grep shared/utility modules and files adjacent to the change,
and name the existing helper to call instead.

### Simplification

Flag unnecessary complexity the diff adds: redundant or derivable state,
copy-paste with slight variation, deep nesting, dead code left behind. Name
the simpler form that does the same job.

### Efficiency

Flag wasted work the diff introduces: redundant computation or repeated I/O,
independent operations run sequentially, blocking work added to startup or
hot paths. Also flag long-lived objects built from closures or captured
environments — they keep the entire enclosing scope alive for the object's
lifetime (a memory leak when that scope holds large values); prefer a
class/struct that copies only the fields it needs. Name the cheaper
alternative.

### Altitude

Check that each change fixes the root cause at the right depth rather than
patching a symptom with a fragile bandaid. Special cases layered on shared
infrastructure are a sign the fix isn't deep enough — prefer the simpler, more
general change to the underlying mechanism over adding special cases, and name
that change.

### Conventions (agent instruction files)

Find the agent instruction files that govern the changed code. Per tool:
Claude Code uses ~/.claude/CLAUDE.md, the repo-root CLAUDE.md and any CLAUDE.md or
CLAUDE.local.md; Codex and GitHub Copilot use the repo-root AGENTS.md. Copilot also
reads .github/copilot-instructions.md and .github/instructions/*.instructions.md
(honour their `applyTo` globs). A file in a directory only applies to files at or
below it. Read each one that exists, then check the diff for clear violations of
the rules they state.

Only flag a violation when you can quote the exact rule and the exact line
that breaks it — no style preferences, no vague "spirit of the doc"
inferences. In the finding, name the instruction file path and quote the rule so the
report can cite it. If no instruction file applies, return nothing for this angle.

Cleanup, altitude, and conventions candidates use the same
`file`/`line`/`summary` shape; in `failure_scenario`, state the concrete
cost (what is duplicated, wasted, harder to maintain, or which instruction-file rule
is broken) instead of a crash. Correctness bugs always outrank cleanup,
altitude, and conventions findings when the output cap forces a cut.

Pass every candidate with a nameable failure scenario through — finders that
silently drop half-believed candidates are the dominant cause of misses.

## Phase 2 — Dedup only (no verify)

Pool all candidates. Dedup near-duplicates only (same defect, same location, same reason → keep one). Do NOT run verifiers; do NOT re-judge. Sort by severity.

## Output

Target **at least 5 findings**. If fewer genuine findings exist, emit what you have — do not invent to hit the floor.

Report the results once, with `{level, findings}`, where `level` is `high`.
`findings` is at most 10 entries ranked most-severe first. If more than 10 survive,
keep the 10 most severe. If nothing survives, report an empty list. Each entry has:

- `file`, `line`, `summary`
- `short_summary`: the claim compressed to ≤60 characters, no rationale or consequence clause
- `failure_scenario`
- `category`: a short kebab-case slug for the angle that produced it (`correctness`,
  `simplification`, `efficiency`, `reuse`, `altitude`, `conventions`, or a more
  specific slug like `test-coverage` when one fits better)

How to report depends on the tool you run in:

- **Claude Code:** if a `ReportFindings` tool is available, call it once with the
  fields above. Do not also print the findings as text. Do not create or publish an
  artifact of the review; the tool call is the report.
- **Codex, GitHub Copilot, or any tool without `ReportFindings`:** print the findings
  as a single numbered list in the final message, most severe first, one entry per
  finding in the form
  `N. [category] file:line — short_summary` followed by an indented
  `Summary:` and `Failure scenario:` line. Print nothing else except a one-line
  "No findings." when the list is empty. In Copilot code review, post each finding
  as an inline review comment on `file:line` instead when the host supports it.

## If findings are fixed later

When reported findings get fixed later in the session (the user asks, or later work
fixes them incidentally), report them again with the same findings, each carrying an
`outcome`: `fixed`, `no_change_needed` (the finding was wrong or already handled), or
`skipped` (real but not applied). Do this immediately after the fixes land, before
any prose summary.

- **Claude Code with `ReportFindings`:** call it again; the host UI's per-finding
  status only updates from that call. Do not repeat the findings as text.
- **Other tools:** reprint the numbered list with ` — outcome: <outcome>` appended to
  each entry.
