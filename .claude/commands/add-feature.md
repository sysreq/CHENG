# /add-feature — Multi-Agent Feature Design Command

You are executing a slash command in the current Claude Code session. You will create a GitHub Project linked to the current repository, prepare shared context, then sequentially spawn independent agents for each design step. **This command blocks the current session until all agents complete or a blocker is hit.**

**Feature Idea:** $ARGUMENTS

---

## Your Responsibilities (Command — Current Session)

You own the **project lifecycle**, not the design work. You:

1. Create a GitHub Project under `@me` and link it to the current repo
2. Add a "Plans" status option to the built-in Status field
3. Write a shared context file for sub-agents
4. Spawn Step 1 agent → block until done → verify output
5. Spawn Step 2 agent → block until done → verify output
6. Commit all artifacts and report final status

You do NOT write drafts, critiques, brainstorms, or syntheses. That work belongs to the spawned agents operating in their own context windows.

---

## Phase 0: Setup — Create the GitHub Project

### 0A. Ensure Auth Scope

```bash
gh auth status

# If 'project' scope is missing:
gh auth refresh -s project
```

### 0B. Derive Feature Summary

Generate a concise summary (≤10 words) of the feature idea. Store it as `FEATURE_SUMMARY`.

### 0C. Detect Repository Info

```bash
GH_REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner')
GH_USER=$(gh api user -q '.login')
REPO_NUMBER=$(gh repo view --json id -q '.id')

echo "Repository: ${GH_REPO}"
echo "User: ${GH_USER}"
```

### 0D. Check for Existing Project (Idempotency)

Before creating a new project, check if one with the same title already exists:

```bash
EXISTING_PROJECT=$(gh project list --owner "@me" --format json | jq -r \
  --arg title "Feature: ${FEATURE_SUMMARY}" \
  '.projects[] | select(.title == $title) | .number')

if [ -n "$EXISTING_PROJECT" ] && [ "$EXISTING_PROJECT" != "null" ]; then
  PROJECT_NUMBER=$EXISTING_PROJECT
  echo "Found existing project #${PROJECT_NUMBER} — resuming."
else
  # Create the project (see 0E)
  echo "No existing project found — creating new one."
fi
```

### 0E. Create the Project & Link to Repo

```bash
# Create the project under the authenticated user
PROJECT_URL=$(gh project create \
  --owner "@me" \
  --title "Feature: ${FEATURE_SUMMARY}" \
  --format json | jq -r '.url')

PROJECT_NUMBER=$(echo "$PROJECT_URL" | grep -oP '\d+$')

# Get the project node ID
PROJECT_JSON=$(gh project view ${PROJECT_NUMBER} \
  --owner "@me" \
  --format json)

PROJECT_ID=$(echo "$PROJECT_JSON" | jq -r '.id')

echo "Project #${PROJECT_NUMBER} created: ${PROJECT_URL}"

# Link the project to the current repository so it appears on the repo's Projects tab
gh project link ${PROJECT_NUMBER} --owner "@me" --repo "${GH_REPO}"

echo "Project linked to ${GH_REPO}"
```

### 0F. Add "Plans" Status Option

The built-in Status field has Todo, In Progress, and Done. Add a fourth: **Plans**.

```bash
FIELDS_JSON=$(gh project field-list ${PROJECT_NUMBER} \
  --owner "@me" \
  --format json)

STATUS_FIELD_ID=$(echo "$FIELDS_JSON" | jq -r \
  '.fields[] | select(.name == "Status") | .id')

# Check if "Plans" already exists
HAS_PLANS=$(echo "$FIELDS_JSON" | jq -r \
  '.fields[] | select(.name == "Status") | .options[] | select(.name == "Plans") | .id')

if [ -z "$HAS_PLANS" ] || [ "$HAS_PLANS" = "null" ]; then
  # Build updated options array: existing + Plans
  EXISTING_OPTIONS=$(echo "$FIELDS_JSON" | jq -c \
    '[.fields[] | select(.name == "Status") | .options[] | {name: .name, color: .color, description: .description}]')

  UPDATED_OPTIONS=$(echo "$EXISTING_OPTIONS" | jq -c \
    '. + [{"name": "Plans", "color": "PURPLE", "description": "Design planning complete"}]')

  gh api graphql -f query='
    mutation($projectId: ID!, $fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
      updateProjectV2Field(input: {
        projectId: $projectId
        fieldId: $fieldId
        singleSelectOptions: $options
      }) {
        projectV2Field {
          ... on ProjectV2SingleSelectField {
            options { id name }
          }
        }
      }
    }' \
    -f projectId="${PROJECT_ID}" \
    -f fieldId="${STATUS_FIELD_ID}" \
    --argjson options "${UPDATED_OPTIONS}"

  echo "Added 'Plans' status option."
else
  echo "'Plans' status already exists."
fi
```

### 0G. Capture All Status Option IDs

Re-fetch after the mutation to get the Plans option ID:

```bash
FIELDS_JSON=$(gh project field-list ${PROJECT_NUMBER} \
  --owner "@me" \
  --format json)

PLANS_OPTION_ID=$(echo "$FIELDS_JSON" | jq -r \
  '.fields[] | select(.name == "Status") | .options[] | select(.name == "Plans") | .id')

TODO_OPTION_ID=$(echo "$FIELDS_JSON" | jq -r \
  '.fields[] | select(.name == "Status") | .options[] | select(.name == "Todo") | .id')

IN_PROGRESS_OPTION_ID=$(echo "$FIELDS_JSON" | jq -r \
  '.fields[] | select(.name == "Status") | .options[] | select(.name == "In Progress") | .id')

DONE_OPTION_ID=$(echo "$FIELDS_JSON" | jq -r \
  '.fields[] | select(.name == "Status") | .options[] | select(.name == "Done") | .id')

echo "Status IDs captured: Plans=${PLANS_OPTION_ID}"
```

### 0H. Write Shared Context File

This is the data handoff mechanism. Agents read this file instead of re-querying GitHub.

```bash
mkdir -p .projects/${PROJECT_NUMBER}

cat > .projects/${PROJECT_NUMBER}/context.json << CONTEXT_EOF
{
  "project_number": ${PROJECT_NUMBER},
  "project_id": "${PROJECT_ID}",
  "project_url": "${PROJECT_URL}",
  "feature_summary": "${FEATURE_SUMMARY}",
  "feature_description": $(echo "$ARGUMENTS" | jq -Rs .),
  "gh_repo": "${GH_REPO}",
  "gh_user": "${GH_USER}",
  "status_field_id": "${STATUS_FIELD_ID}",
  "plans_option_id": "${PLANS_OPTION_ID}",
  "todo_option_id": "${TODO_OPTION_ID}",
  "in_progress_option_id": "${IN_PROGRESS_OPTION_ID}",
  "done_option_id": "${DONE_OPTION_ID}",
  "steps_completed": [],
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
CONTEXT_EOF

echo "Context written to .projects/${PROJECT_NUMBER}/context.json"
```

---

## Phase 1: Spawn Step 1 Agent — Define the Problem

Launch the Step 1 agent as an **independent subprocess with its own context window**. Pass the project number — the agent reads everything else from context.json. This command blocks until the agent exits.

```bash
echo ""
echo "🚀 Spawning Step 1 agent: Define the Problem..."
echo "   Agent has its own context. This session will block until it completes."
echo ""

claude -p "You are executing Step 1 of a feature design workflow.

PROJECT_NUMBER=${PROJECT_NUMBER}

Read the agent instructions from .claude/agents/feature/step-1-define.md and execute them fully.
Read the project context from .projects/${PROJECT_NUMBER}/context.json.

The feature idea is:
${ARGUMENTS}

Execute all phases of Step 1. When complete, write your final approved problem definition to .projects/${PROJECT_NUMBER}/1/final.md and update .projects/${PROJECT_NUMBER}/context.json steps_completed array to include 'step-1'." \
  --allowedTools "Bash,Read,Write,Edit" \
  --print \
  > .projects/${PROJECT_NUMBER}/step-1-output.log 2>&1

STEP1_EXIT=$?
echo "Step 1 agent exited with code: ${STEP1_EXIT}"
```

### 1A. Verify Step 1 Completion

```bash
if [ ! -f ".projects/${PROJECT_NUMBER}/1/final.md" ]; then
  echo "❌ ERROR: Step 1 did not produce .projects/${PROJECT_NUMBER}/1/final.md"
  echo ""
  echo "Agent output (last 50 lines):"
  tail -50 .projects/${PROJECT_NUMBER}/step-1-output.log
  echo ""
  echo "Check the full log: .projects/${PROJECT_NUMBER}/step-1-output.log"
  # Do NOT proceed to Step 2
  exit 1
fi

# Verify the context was updated
STEP1_DONE=$(jq -r '.steps_completed | index("step-1")' .projects/${PROJECT_NUMBER}/context.json)
if [ "$STEP1_DONE" = "null" ]; then
  echo "⚠️ Warning: Step 1 produced final.md but did not update context.json"
  echo "   Updating context.json manually..."
  jq '.steps_completed += ["step-1"]' .projects/${PROJECT_NUMBER}/context.json \
    > .projects/${PROJECT_NUMBER}/context.json.tmp \
    && mv .projects/${PROJECT_NUMBER}/context.json.tmp .projects/${PROJECT_NUMBER}/context.json
fi

echo "✅ Step 1 complete. Problem definition: $(wc -w < .projects/${PROJECT_NUMBER}/1/final.md) words"
```

---

## Phase 2: Spawn Step 2 Agent — Explore the Solution Space

```bash
echo ""
echo "🚀 Spawning Step 2 agent: Explore the Solution Space..."
echo "   Agent has its own context. This session will block until it completes."
echo ""

claude -p "You are executing Step 2 of a feature design workflow.

PROJECT_NUMBER=${PROJECT_NUMBER}

Read the agent instructions from .claude/agents/feature/step-2-explore.md and execute them fully.
Read the project context from .projects/${PROJECT_NUMBER}/context.json.
Read the approved problem definition from .projects/${PROJECT_NUMBER}/1/final.md.

Execute all phases of Step 2. When complete, write your final approved synthesis to .projects/${PROJECT_NUMBER}/2/final.md and update .projects/${PROJECT_NUMBER}/context.json steps_completed array to include 'step-2'." \
  --allowedTools "Bash,Read,Write,Edit" \
  --print \
  > .projects/${PROJECT_NUMBER}/step-2-output.log 2>&1

STEP2_EXIT=$?
echo "Step 2 agent exited with code: ${STEP2_EXIT}"
```

### 2A. Verify Step 2 Completion

```bash
if [ ! -f ".projects/${PROJECT_NUMBER}/2/final.md" ]; then
  echo "❌ ERROR: Step 2 did not produce .projects/${PROJECT_NUMBER}/2/final.md"
  echo ""
  echo "Agent output (last 50 lines):"
  tail -50 .projects/${PROJECT_NUMBER}/step-2-output.log
  echo ""
  echo "Check the full log: .projects/${PROJECT_NUMBER}/step-2-output.log"
  exit 1
fi

STEP2_DONE=$(jq -r '.steps_completed | index("step-2")' .projects/${PROJECT_NUMBER}/context.json)
if [ "$STEP2_DONE" = "null" ]; then
  echo "⚠️ Warning: Step 2 produced final.md but did not update context.json"
  jq '.steps_completed += ["step-2"]' .projects/${PROJECT_NUMBER}/context.json \
    > .projects/${PROJECT_NUMBER}/context.json.tmp \
    && mv .projects/${PROJECT_NUMBER}/context.json.tmp .projects/${PROJECT_NUMBER}/context.json
fi

echo "✅ Step 2 complete. Solution synthesis: $(wc -w < .projects/${PROJECT_NUMBER}/2/final.md) words"
```

---

## Phase 3: Finalize — Commit & Report

### 3A. Commit All Design Artifacts

```bash
git add .projects/${PROJECT_NUMBER}/
git commit -m "docs: Feature design — ${FEATURE_SUMMARY}

Project: #${PROJECT_NUMBER}
Steps completed: Define Problem, Explore Solutions
Artifacts: .projects/${PROJECT_NUMBER}/"
```

### 3B. Print Summary

```bash
echo ""
echo "════════════════════════════════════════════════════"
echo "✅ /add-feature Complete (Steps 1–2)"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Project Board: ${PROJECT_URL}"
echo "Linked Repo:   ${GH_REPO}"
echo "Feature:       ${FEATURE_SUMMARY}"
echo ""

STEP1_SCORE=$(jq -r '.step1_score // "N/A"' .projects/${PROJECT_NUMBER}/context.json)
STEP1_ITERS=$(jq -r '.step1_iterations // "N/A"' .projects/${PROJECT_NUMBER}/context.json)
STEP2_ROUNDS=$(jq -r '.step2_rounds // "N/A"' .projects/${PROJECT_NUMBER}/context.json)

echo "Step 1 — Define the Problem:"
echo "  Score: ${STEP1_SCORE}/10 in ${STEP1_ITERS} iteration(s)"
echo "  Output: .projects/${PROJECT_NUMBER}/1/final.md"
echo ""
echo "Step 2 — Explore Solution Space:"
echo "  Consensus in ${STEP2_ROUNDS} round(s)"
echo "  Output: .projects/${PROJECT_NUMBER}/2/final.md"
echo ""
echo "Step 3 — Design the Interface:    ⏳ Not yet implemented"
echo "Step 4 — Technical Design:        ⏳ Not yet implemented"
echo "Step 5 — Implementation Plan:     ⏳ Not yet implemented"
echo ""
echo "Artifacts: .projects/${PROJECT_NUMBER}/"
echo "Logs:      .projects/${PROJECT_NUMBER}/step-{1,2}-output.log"
echo "════════════════════════════════════════════════════════"
```

---

## Idempotency / Resume

If rerun with the same feature summary:

1. Phase 0D detects the existing project and skips creation/linking
2. Each agent checks for existing issues and artifacts before creating new ones
3. Context.json `steps_completed` array tells the command which steps to skip

```bash
# If resuming, check what's already done
COMPLETED=$(jq -r '.steps_completed[]' .projects/${PROJECT_NUMBER}/context.json 2>/dev/null)

if echo "$COMPLETED" | grep -q "step-1"; then
  echo "Step 1 already complete — skipping."
  # Skip Phase 1, proceed to Phase 2
fi

if echo "$COMPLETED" | grep -q "step-2"; then
  echo "Step 2 already complete — skipping."
  # Skip Phase 2, proceed to Phase 3
fi
```

---

## Extensibility

To add Steps 3–5 later:

1. Create `.claude/agents/feature/step-3-interface.md` (and so on)
2. Add a new Phase block in this command after Phase 2, following the same pattern:
   - Spawn agent with `claude -p` passing the project number
   - Block until agent exits
   - Verify `final.md` output exists
3. Each agent reads `context.json` + prior steps' `final.md` files
4. Each agent creates its own issue, manages its own lifecycle, writes to Plans on completion
