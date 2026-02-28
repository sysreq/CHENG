# Step 1: Define the Problem — Independent Agent

You are an independent agent executing Step 1 of a feature design workflow. You operate in your own context. All project metadata comes from the shared context file. When you finish, you write your outputs and exit — the orchestrator handles what happens next.

---

## Phase 0: Load Context

### 0A. Read Shared Context

```bash
PROJECT_NUMBER=<injected by orchestrator>

CONTEXT=$(cat .projects/${PROJECT_NUMBER}/context.json)

PROJECT_ID=$(echo "$CONTEXT" | jq -r '.project_id')
PROJECT_URL=$(echo "$CONTEXT" | jq -r '.project_url')
FEATURE_SUMMARY=$(echo "$CONTEXT" | jq -r '.feature_summary')
FEATURE_DESCRIPTION=$(echo "$CONTEXT" | jq -r '.feature_description')
STATUS_FIELD_ID=$(echo "$CONTEXT" | jq -r '.status_field_id')
PLANS_OPTION_ID=$(echo "$CONTEXT" | jq -r '.plans_option_id')
IN_PROGRESS_OPTION_ID=$(echo "$CONTEXT" | jq -r '.in_progress_option_id')
GH_USER=$(echo "$CONTEXT" | jq -r '.gh_user')
GH_REPO=$(echo "$CONTEXT" | jq -r '.gh_repo')

echo "Step 1 agent loaded context for project #${PROJECT_NUMBER}: ${FEATURE_SUMMARY}"
```

### 0B. Ensure Auth Scope

```bash
gh auth status
# If 'project' scope is missing:
# gh auth refresh -s project
```

### 0C. Create Working Directory

```bash
mkdir -p .projects/${PROJECT_NUMBER}/1
```

### 0D. Create the Step 1 Issue

Create this step's issue and add it to the project board. Check for an existing issue first (idempotency).

```bash
# Check if Step 1 issue already exists in the project
PROJECT_ITEMS=$(gh project item-list ${PROJECT_NUMBER} \
  --owner "@me" \
  --format json)

EXISTING_STEP1=$(echo "$PROJECT_ITEMS" | jq -r \
  '.items[] | select(.content.title | test("Step 1")) | .content.number')

if [ -n "$EXISTING_STEP1" ] && [ "$EXISTING_STEP1" != "null" ]; then
  STEP1_ISSUE_NUM=$EXISTING_STEP1
  echo "Step 1 issue already exists: #${STEP1_ISSUE_NUM}"
else
  # Create the issue
  STEP1_ISSUE_URL=$(gh issue create \
    --title "Step 1: Define the Problem — ${FEATURE_SUMMARY}" \
    --body "## Objective
Clearly define the problem before exploring solutions.

## Feature Idea
${FEATURE_DESCRIPTION}

## Deliverables
- Problem statement (pain, persona, frequency)
- Symptom vs. root cause analysis
- Measurable success criteria
- Scope boundaries

## Process
Iterative draft→critique→score loop (max 5 iterations, target ≥9/10).

## Status
- [ ] Draft v1
- [ ] Critique v1
- [ ] Score v1
- [ ] Approved (≥9/10)

---
_Project: ${PROJECT_URL}_" \
    --label "feature,design" \
    --json url -q '.url' 2>/dev/null || \
    gh issue create \
    --title "Step 1: Define the Problem — ${FEATURE_SUMMARY}" \
    --body "Step 1 of feature design for: ${FEATURE_DESCRIPTION}" \
    --label "feature,design" | grep -oP 'https://\S+')

  STEP1_ISSUE_NUM=$(echo "$STEP1_ISSUE_URL" | grep -oP '\d+$')

  # Add to project and set status to "In Progress"
  ITEM_ID=$(gh project item-add ${PROJECT_NUMBER} \
    --owner "@me" \
    --url "${STEP1_ISSUE_URL}" \
    --format json | jq -r '.id')

  gh project item-edit \
    --id "${ITEM_ID}" \
    --project-id "${PROJECT_ID}" \
    --field-id "${STATUS_FIELD_ID}" \
    --single-select-option-id "${IN_PROGRESS_OPTION_ID}"

  echo "Created Step 1 issue: #${STEP1_ISSUE_NUM}, added to project, status: In Progress"
fi
```

### 0E. Save Step 1 Issue Number to Context

```bash
# Update context.json with step 1 issue number
CONTEXT=$(cat .projects/${PROJECT_NUMBER}/context.json)
echo "$CONTEXT" | jq --argjson num "${STEP1_ISSUE_NUM}" '.step1_issue_number = $num' \
  > .projects/${PROJECT_NUMBER}/context.json
```

---

## Phase 1: Iterative Problem Definition Loop

Execute the following loop. **Maximum 5 iterations.** Exit early if independent score ≥ 9/10.

Set `ITERATION=1`.

---

### Step 1A — DRAFT (Generative Persona)

**Adopt a creative, empathetic, user-focused lens.** Write the problem definition to `.projects/${PROJECT_NUMBER}/1/draft-v${ITERATION}.md`.

The draft MUST contain these sections:

```markdown
# Problem Definition v${ITERATION}

## Problem Statement
<!-- One clear paragraph: what pain exists, for whom, how often. Be specific. -->

## Symptom vs. Root Cause
| Symptom (what users see/complain about) | Root Cause (underlying issue) |
|----------------------------------------|-------------------------------|
| ...                                    | ...                           |

## User Impact
- **Who is affected:** (persona, segment, frequency of encounter)
- **Current workaround:** (what they do today without this feature)
- **Cost of inaction:** (what happens if we never build this)

## Success Criteria
<!-- Each criterion must be testable — a number, a binary yes/no, or a measurable threshold. -->
1. ...
2. ...
3. ...

## Scope Boundaries
- **In scope:** ...
- **Out of scope:** ...
- **Assumptions:** ...
```

If `ITERATION > 1`: incorporate ALL feedback from the previous critique and address EVERY gap identified in the score feedback.

---

### Step 1B — CRITIQUE (Adversarial Persona)

**Switch to rigorous, adversarial review mode.** You are now a skeptical reviewer whose job is to find flaws. Write to `.projects/${PROJECT_NUMBER}/1/critique-v${ITERATION}.md`.

```markdown
# Critique of Problem Definition v${ITERATION}

## Scores
- **Clarity:** _/10 — Could two different engineers read this and build the same thing?
- **Completeness:** _/10 — Edge cases considered? Success criteria truly measurable?
- **Accuracy:** _/10 — Does the symptom/root-cause analysis hold up under scrutiny?
- **Actionability:** _/10 — Could a team start sprint planning from this document?

## Issues Found
1. [MUST FIX] ...
2. [MUST FIX] ...
3. [SHOULD IMPROVE] ...
4. [NICE TO HAVE] ...

## Suggested Rewrites
<!-- Concrete alternative text for every MUST FIX item -->
```

---

### Step 1C — SCORE (Independent Review)

Shell out to Gemini for an independent, unbiased score. The purpose is to avoid self-reinforcing bias — an external model evaluates the work.

```bash
DRAFT=$(cat .projects/${PROJECT_NUMBER}/1/draft-v${ITERATION}.md)
CRITIQUE=$(cat .projects/${PROJECT_NUMBER}/1/critique-v${ITERATION}.md)

gemini -p "You are an independent reviewer scoring a problem definition for a software feature.

ORIGINAL FEATURE IDEA:
${FEATURE_DESCRIPTION}

DRAFT (v${ITERATION}):
${DRAFT}

INTERNAL CRITIQUE:
${CRITIQUE}

Score this problem definition on a scale of 1-10 where:
- 1-3: Fundamentally unclear or missing key elements
- 4-6: Right structure but significant gaps remain
- 7-8: Solid but needs refinement in specific areas
- 9-10: Ready for solution design — clear, measurable, actionable

Respond in EXACTLY this format (no other text):
SCORE: <number>
REASONING: <2-3 sentences explaining the score>
GAPS: <comma-separated list of remaining issues, or NONE>" \
  > .projects/${PROJECT_NUMBER}/1/score-v${ITERATION}.txt 2>&1
```

**Gemini fallback:** If `gemini` is not available or errors out, self-score using the adversarial persona but mark the record:

```bash
if [ $? -ne 0 ] || [ ! -s ".projects/${PROJECT_NUMBER}/1/score-v${ITERATION}.txt" ]; then
  echo "⚠️ Gemini unavailable — falling back to self-score."
  # Self-score: be STRICT. Adopt the adversarial persona's perspective.
  # Write the score file in the same SCORE/REASONING/GAPS format.
  # Prepend: "⚠️ Independent review unavailable — self-scored"
fi
```

Parse the score:

```bash
SCORE=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/1/score-v${ITERATION}.txt | head -1)
REASONING=$(grep -oP 'REASONING: \K.*' .projects/${PROJECT_NUMBER}/1/score-v${ITERATION}.txt)
GAPS=$(grep -oP 'GAPS: \K.*' .projects/${PROJECT_NUMBER}/1/score-v${ITERATION}.txt)

echo "Iteration ${ITERATION}: Score ${SCORE}/10"
```

---

### Step 1D — Post Iteration Results to Issue

```bash
gh issue comment ${STEP1_ISSUE_NUM} --body "## Iteration ${ITERATION} Results

**Score:** ${SCORE}/10
**Reasoning:** ${REASONING}
**Gaps:** ${GAPS}

<details>
<summary>Draft v${ITERATION}</summary>

$(cat .projects/${PROJECT_NUMBER}/1/draft-v${ITERATION}.md)
</details>

<details>
<summary>Critique v${ITERATION}</summary>

$(cat .projects/${PROJECT_NUMBER}/1/critique-v${ITERATION}.md)
</details>"
```

---

### Step 1E — Decision Gate

- **If score ≥ 9:** Proceed to Phase 2 (Finalize). Set `FINAL_SCORE=${SCORE}`.
- **If score < 9 AND iteration < 5:** Increment `ITERATION`, return to Step 1A with all feedback incorporated.
- **If score < 9 AND iteration = 5:** **STOP.** Post a blocker comment:

```bash
gh issue comment ${STEP1_ISSUE_NUM} --body "## ⚠️ BLOCKED

Problem definition did not reach quality threshold (≥9/10) after **5 iterations**.

| Version | Score | Key Gaps |
|---------|-------|----------|
$(for i in $(seq 1 5); do
  S=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/1/score-v${i}.txt 2>/dev/null || echo "N/A")
  G=$(grep -oP 'GAPS: \K.*' .projects/${PROJECT_NUMBER}/1/score-v${i}.txt 2>/dev/null || echo "N/A")
  echo "| v${i} | ${S}/10 | ${G} |"
done)

**Awaiting human review before proceeding.**
@${GH_USER} — please review and provide direction."
```

If blocked, still write the best draft as `final.md` so the orchestrator can detect output exists but note the blocker in context.json.

---

## Phase 2: Finalize

Once score ≥ 9:

### 2A. Write Final Problem Definition

```bash
cp .projects/${PROJECT_NUMBER}/1/draft-v${ITERATION}.md \
   .projects/${PROJECT_NUMBER}/1/final.md

echo "Final problem definition written to .projects/${PROJECT_NUMBER}/1/final.md"
```

### 2B. Post Completion to Issue

```bash
gh issue comment ${STEP1_ISSUE_NUM} --body "## ✅ Step 1 Complete — Problem Definition Approved

### Iteration History
| Version | Score | Key Changes |
|---------|-------|-------------|
$(for i in $(seq 1 ${ITERATION}); do
  S=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/1/score-v${i}.txt 2>/dev/null || echo "N/A")
  if [ "$i" -eq 1 ]; then
    echo "| v${i} | ${S}/10 | Initial draft |"
  else
    echo "| v${i} | ${S}/10 | Addressed feedback from v$((i-1)) |"
  fi
done)

### Final Problem Definition

$(cat .projects/${PROJECT_NUMBER}/1/final.md)

---
**Score:** ${FINAL_SCORE}/10
**Iterations:** ${ITERATION}
**Status:** Approved — ready for Step 2: Explore the Solution Space"
```

### 2C. Close Issue & Move to Plans

```bash
# Close the issue
gh issue close ${STEP1_ISSUE_NUM} --reason completed \
  --comment "Problem definition approved with score ${FINAL_SCORE}/10 after ${ITERATION} iteration(s)."

# Move to "Plans" on the project board
PROJECT_ITEMS=$(gh project item-list ${PROJECT_NUMBER} \
  --owner "@me" \
  --format json)

STEP1_ITEM_ID=$(echo "$PROJECT_ITEMS" | jq -r \
  '.items[] | select(.content.title | test("Step 1")) | .id')

gh project item-edit \
  --id "${STEP1_ITEM_ID}" \
  --project-id "${PROJECT_ID}" \
  --field-id "${STATUS_FIELD_ID}" \
  --single-select-option-id "${PLANS_OPTION_ID}"

echo "Step 1 issue #${STEP1_ISSUE_NUM} closed and moved to Plans."
```

### 2D. Update Shared Context

```bash
CONTEXT=$(cat .projects/${PROJECT_NUMBER}/context.json)
echo "$CONTEXT" | jq \
  --argjson score ${FINAL_SCORE} \
  --argjson iters ${ITERATION} \
  '.steps_completed += ["step-1"] | .step1_score = $score | .step1_iterations = $iters' \
  > .projects/${PROJECT_NUMBER}/context.json
```

### 2E. Commit Artifacts

```bash
git add .projects/${PROJECT_NUMBER}/1/
git commit -m "docs: Step 1 problem definition for ${FEATURE_SUMMARY}

Project: #${PROJECT_NUMBER}
Issue: #${STEP1_ISSUE_NUM}
Score: ${FINAL_SCORE}/10
Iterations: ${ITERATION}"
```

### 2F. Signal Completion

```bash
echo ""
echo "════════════════════════════════════════════════"
echo "✅ Step 1: Define the Problem — COMPLETE"
echo "════════════════════════════════════════════════"
echo ""
echo "Project Board: ${PROJECT_URL}"
echo "Issue: #${STEP1_ISSUE_NUM} (closed → Plans)"
echo "Score: ${FINAL_SCORE}/10"
echo "Iterations: ${ITERATION}"
echo "Output: .projects/${PROJECT_NUMBER}/1/final.md"
echo ""
echo "Handing back to orchestrator."
echo "════════════════════════════════════════════════"
```

---

## Execution Notes

- **Draft vs. Critique are distinct personas.** Draft = generative, empathetic, user-focused. Critique = adversarial, precise, demanding. Both are you, but with fundamentally different orientations. Never blend them.
- **Gemini is the independent tie-breaker.** The whole point of an external score is to avoid self-reinforcing bias. If Gemini is unavailable and you self-score, be STRICT — err toward lower scores.
- **Never skip the critique.** Even if the draft feels perfect, the adversarial pass catches blind spots.
- **The issue is the audit trail.** Every iteration posts to the issue so there's a complete history on GitHub.
- **Idempotency:** If rerun, check for existing draft/critique/score files in `.projects/${PROJECT_NUMBER}/1/` and resume from the last incomplete iteration. Check the last `score-v*.txt` file to determine where you left off.
- **Your output contract:** The orchestrator expects `.projects/${PROJECT_NUMBER}/1/final.md` to exist when you exit. If blocked after 5 iterations, still write the best version as final.md.
