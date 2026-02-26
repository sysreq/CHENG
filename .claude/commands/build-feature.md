# /build-feature

Orchestrates the full implementation of a GitHub milestone using parallel
PM and Developer subagents.

**Usage:** `/build-feature <milestone name>`
**Example:** `/build-feature stability plots`

---

## Runtime Setup

Derive the milestone name and branch slug from `$ARGUMENTS`:

```bash
# Raw input, e.g. "stability plots"
RAW_ARGS="$ARGUMENTS"

# Title-case for the GitHub milestone, e.g. "Feature: Stability Plots"
MILESTONE_TITLE="Feature: $(echo "$RAW_ARGS" | sed 's/\b\(.\)/\u\1/g')"

# Slug for branch names, e.g. "Stability-Plots"
MILESTONE_SLUG=$(echo "$RAW_ARGS" | sed 's/\b\(.\)/\u\1/g' | tr ' ' '-')

FRONTEND_BRANCH="Feature-${MILESTONE_SLUG}-FRONTEND"
BACKEND_BRANCH="Feature-${MILESTONE_SLUG}-BACKEND"

REPO_ROOT=$(git rev-parse --show-toplevel)

echo "Milestone : $MILESTONE_TITLE"
echo "FE branch : $FRONTEND_BRANCH"
echo "BE branch : $BACKEND_BRANCH"
echo "Repo root : $REPO_ROOT"
```

---

## Step 1 — Validate the Milestone Exists

```bash
MILESTONE_CHECK=$(gh milestone list --json title | jq -r '.[].title' | grep -F "$MILESTONE_TITLE")

if [ -z "$MILESTONE_CHECK" ]; then
  echo "ERROR: Milestone \"$MILESTONE_TITLE\" not found in this repo."
  echo "Available milestones:"
  gh milestone list --json title | jq -r '.[].title'
  exit 1
fi

echo "✅ Milestone confirmed: $MILESTONE_TITLE"
```

---

## Step 2 — Fetch All Open Issues in the Milestone

```bash
ISSUE_LIST=$(gh issue list \
  --milestone "$MILESTONE_TITLE" \
  --state open \
  --json number,title,body,labels \
  --limit 200)

ISSUE_COUNT=$(echo "$ISSUE_LIST" | jq 'length')
echo "Found $ISSUE_COUNT open issues in milestone."

if [ "$ISSUE_COUNT" -eq 0 ]; then
  echo "ERROR: No open issues found in milestone \"$MILESTONE_TITLE\". Nothing to do."
  exit 1
fi
```

---

## Step 3 — Spawn Both PMs in Parallel

Spawn the Frontend PM and Backend PM simultaneously as subagents.

**Frontend PM inputs:**
- `DOMAIN`: `FRONTEND`
- `DOMAIN_BRANCH`: `{FRONTEND_BRANCH}`
- `ISSUE_LIST`: *(full JSON from Step 2)*
- `REPO_ROOT`: *(from Step 1)*
- `HOLD_ISSUES`: *(any issues with cross-domain deps on the full backend — inspect the DAG after classification)*
- `RELEASE_SIGNAL_SOURCE`: `BACKEND_PM_DONE`

**Backend PM inputs:**
- `DOMAIN`: `BACKEND`
- `DOMAIN_BRANCH`: `{BACKEND_BRANCH}`
- `ISSUE_LIST`: *(full JSON from Step 2)*
- `REPO_ROOT`: *(from Step 1)*
- `HOLD_ISSUES`: *(none)*
- `RELEASE_SIGNAL_SOURCE`: *(none)*

---

## Step 4 — Relay the Backend Completion Signal

As soon as the Backend PM emits its final report:

**If backend status is `DONE` or `DONE (with blocked issues)`:**
> Send to Frontend PM: "ORCHESTRATOR SIGNAL: Backend PM has completed.
> Release HOLD on any issues gated on full backend completion,
> provided their remaining FE dependencies are also satisfied."

**If backend status is `BLOCKED`:**
> Send to Frontend PM: "ORCHESTRATOR SIGNAL: Backend PM is fully blocked.
> Mark all HELD issues as BLOCKED with reason: backend domain did not complete."

---

## Step 5 — Final Report

Once both PMs have returned their reports, output:

```
=== $MILESTONE_TITLE — Build Report ===

Backend PM:  [DONE | DONE (with blocked issues) | BLOCKED: <reason>]
  Merged:  <list>
  Blocked: <list + reasons, if any>

Frontend PM: [DONE | DONE (with blocked issues) | BLOCKED: <reason>]
  Merged:  <list>
  Blocked: <list + reasons, if any>

Overall: [COMPLETE | PARTIAL | BLOCKED]
```

`COMPLETE` = all issues merged.
`PARTIAL`  = at least one issue blocked, rest merged.
`BLOCKED`  = a PM could not start or a full critical path stalled.
