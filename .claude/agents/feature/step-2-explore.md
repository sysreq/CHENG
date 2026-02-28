# Step 2: Explore the Solution Space — Independent Agent

You are an independent agent executing Step 2 of a feature design workflow. You operate in your own context. All project metadata comes from the shared context file. The approved problem definition comes from Step 1's output. When you finish, you write your outputs and exit.

---

## Phase 0: Load Context

### 0A. Read Shared Context & Problem Definition

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

echo "Step 2 agent loaded context for project #${PROJECT_NUMBER}: ${FEATURE_SUMMARY}"

# Load the approved problem definition from Step 1
PROBLEM_DEFINITION=$(cat .projects/${PROJECT_NUMBER}/1/final.md)
echo "Problem definition loaded ($(echo "$PROBLEM_DEFINITION" | wc -w) words)."
```

### 0B. Ensure Auth Scope

```bash
gh auth status
# If 'project' scope is missing:
# gh auth refresh -s project
```

### 0C. Create Working Directory

```bash
mkdir -p .projects/${PROJECT_NUMBER}/2/brainstorm
```

### 0D. Save Problem Definition Locally

```bash
cp .projects/${PROJECT_NUMBER}/1/final.md \
   .projects/${PROJECT_NUMBER}/2/problem-definition.md
```

### 0E. Create the Step 2 Issue

```bash
PROJECT_ITEMS=$(gh project item-list ${PROJECT_NUMBER} \
  --owner "@me" \
  --format json)

EXISTING_STEP2=$(echo "$PROJECT_ITEMS" | jq -r \
  '.items[] | select(.content.title | test("Step 2")) | .content.number')

if [ -n "$EXISTING_STEP2" ] && [ "$EXISTING_STEP2" != "null" ]; then
  STEP2_ISSUE_NUM=$EXISTING_STEP2
  echo "Step 2 issue already exists: #${STEP2_ISSUE_NUM}"
else
  STEP2_ISSUE_URL=$(gh issue create \
    --title "Step 2: Explore the Solution Space — ${FEATURE_SUMMARY}" \
    --body "## Objective
Brainstorm and evaluate multiple solution approaches through multi-agent exploration.

## Process
1. Parallel brainstorm: 4 expert agents explore independently
2. Synthesis: Lead architect cherry-picks and unifies best ideas
3. Consensus loop: All 4 agents review and score (target: all ≥9/10, max 5 rounds)

## Expert Agents
- 🏗️ **Domain Expert** — deep knowledge of the problem space
- 👤 **End User Advocate** — practical user perspective
- 🎨 **UX Designer** — interaction design and information architecture
- 🔮 **Outside Consultant** — first-principles, cross-domain thinking

## Inputs
- Problem definition from Step 1 (Issue #$(echo "$CONTEXT" | jq -r '.step1_issue_number'))

## Status
- [ ] Brainstorm (4 agents)
- [ ] Synthesis v1
- [ ] Consensus round 1
- [ ] Approved (all ≥9/10)

---
_Project: ${PROJECT_URL}_" \
    --label "feature,design" \
    --json url -q '.url' 2>/dev/null || \
    gh issue create \
    --title "Step 2: Explore the Solution Space — ${FEATURE_SUMMARY}" \
    --body "Step 2 of feature design for: ${FEATURE_DESCRIPTION}" \
    --label "feature,design" | grep -oP 'https://\S+')

  STEP2_ISSUE_NUM=$(echo "$STEP2_ISSUE_URL" | grep -oP '\d+$')

  ITEM_ID=$(gh project item-add ${PROJECT_NUMBER} \
    --owner "@me" \
    --url "${STEP2_ISSUE_URL}" \
    --format json | jq -r '.id')

  gh project item-edit \
    --id "${ITEM_ID}" \
    --project-id "${PROJECT_ID}" \
    --field-id "${STATUS_FIELD_ID}" \
    --single-select-option-id "${IN_PROGRESS_OPTION_ID}"

  echo "Created Step 2 issue: #${STEP2_ISSUE_NUM}, added to project, status: In Progress"
fi
```

### 0F. Save Step 2 Issue Number to Context

```bash
CONTEXT=$(cat .projects/${PROJECT_NUMBER}/context.json)
echo "$CONTEXT" | jq --argjson num "${STEP2_ISSUE_NUM}" '.step2_issue_number = $num' \
  > .projects/${PROJECT_NUMBER}/context.json
```

### 0G. Helper Functions

```bash
# Resolve a project item ID by title keyword
get_item_id() {
  local KEYWORD="$1"
  gh project item-list ${PROJECT_NUMBER} \
    --owner "@me" \
    --format json | jq -r \
    --arg kw "$KEYWORD" \
    '.items[] | select(.content.title | test($kw)) | .id'
}
```

---

## Phase 1: Parallel Brainstorm — 4 Expert Agents

Launch 4 agents **simultaneously** using backgrounded subprocesses. Each agent gets a distinct generalized expert persona and writes its analysis independently. They are NOT designing a solution — they are thinking through how someone in their domain would **approach** the problem.

**Critical: All 4 must run in parallel using `&` and `wait`.**

```bash
PROBLEM_FILE=".projects/${PROJECT_NUMBER}/2/problem-definition.md"

# ──────────────────────────────────────────────
# AGENT 1: Domain Expert
# ──────────────────────────────────────────────
claude --print -p "You are a Senior Domain Expert with deep technical knowledge in the problem space described below. You think in terms of system architecture, reliability patterns, state management, and technical constraints.

Read this problem definition and brainstorm your approach to solving it. Focus on:
- Technical architecture patterns relevant to this problem (redundancy, state management, data flow)
- Domain-specific constraints and requirements that must be respected
- Lessons from similar systems in this domain or adjacent domains
- Safety, reliability, and performance implications
- Configuration and customization patterns that work well in this space

Do NOT design a UI or write requirements. Think through the PRINCIPLES and PATTERNS that should guide the solution. Write 500-800 words.

PROBLEM DEFINITION:
$(cat ${PROBLEM_FILE})
" > .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert.md 2>&1 &
PID_DOMAIN=$!

# ──────────────────────────────────────────────
# AGENT 2: End User Advocate
# ──────────────────────────────────────────────
claude --print -p "You are an End User Advocate — a passionate, hands-on practitioner who uses tools like this every day. You know exactly what frustrates users and what delights them. You have practical experience with existing solutions and strong opinions about what works and what doesn't.

Read this problem definition and brainstorm your approach to solving it. Focus on:
- Real-world usage scenarios (under time pressure, in suboptimal conditions, with distractions)
- What configuration options actually matter vs. what's noise
- Common mistakes users make and how to prevent them
- Lessons from existing tools that solve similar or adjacent problems
- The 'just let me do my thing' problem — minimal config vs. power users
- Physical and environmental context that affects usage

Do NOT design a UI or write requirements. Think through what a REAL USER needs and what existing tools get right and wrong. Write 500-800 words.

PROBLEM DEFINITION:
$(cat ${PROBLEM_FILE})
" > .projects/${PROJECT_NUMBER}/2/brainstorm/end-user.md 2>&1 &
PID_USER=$!

# ──────────────────────────────────────────────
# AGENT 3: Outside Consultant
# ──────────────────────────────────────────────
# Prefer Gemini for independence; fall back to Claude if unavailable.
CONSULTANT_PROMPT="You are a senior technology consultant brought in from outside the team. You have no domain bias — you approach this purely from first principles of software product design and information architecture.

Read this problem definition and brainstorm your approach to solving it. Focus on:
- Information architecture: what's the minimum viable configuration surface?
- Progressive disclosure: what should users see first vs. on demand?
- Analogous problems in other domains and what we can learn from them
- Data model implications: how should entities, presets, and settings relate?
- Onboarding patterns: first-time vs. returning user flows
- Risks and tradeoffs the team might be blind to from being too close to the domain

Do NOT design a UI or write requirements. Think through the STRATEGIC APPROACH to this problem. Write 500-800 words.

PROBLEM DEFINITION:
$(cat ${PROBLEM_FILE})"

# Try Gemini first for true independence
if command -v gemini &> /dev/null; then
  gemini -p "${CONSULTANT_PROMPT}" \
    > .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant.md 2>&1 &
  PID_CONSULTANT=$!
else
  echo "⚠️ Gemini unavailable — Outside Consultant role filled by Claude (reduced independence)" \
    > .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant.md
  claude --print -p "${CONSULTANT_PROMPT}" \
    >> .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant.md 2>&1 &
  PID_CONSULTANT=$!
fi

# ──────────────────────────────────────────────
# AGENT 4: UX Designer
# ──────────────────────────────────────────────
claude --print -p "You are a Senior UX Designer who has shipped configuration-heavy products at scale (think Figma, Notion, VS Code). You think in terms of user mental models, interaction cost, and the balance between flexibility and simplicity.

Read this problem definition and brainstorm your approach to solving it. Focus on:
- User mental models: how do users think about the entities and concepts in this problem?
- Interaction cost analysis: how many decisions before the user reaches their goal?
- The naming/labeling problem: when and why do users name things, and what creates friction?
- Progressive disclosure: how to surface the right options without overwhelming
- Error states and recovery: what if they make a wrong choice? How do they undo/redo?
- Accessibility and learnability: can a new user succeed without documentation?

Do NOT produce wireframes or mockups. Think through the INTERACTION DESIGN PRINCIPLES that should guide the solution. Write 500-800 words.

PROBLEM DEFINITION:
$(cat ${PROBLEM_FILE})
" > .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer.md 2>&1 &
PID_UX=$!

# ──────────────────────────────────────────────
# WAIT FOR ALL AGENTS
# ──────────────────────────────────────────────
echo "⏳ All 4 brainstorm agents launched. Waiting for completion..."
wait $PID_DOMAIN $PID_USER $PID_CONSULTANT $PID_UX
echo "✅ All agents complete."
```

### 1B. Post Brainstorm Results to Issue

```bash
gh issue comment ${STEP2_ISSUE_NUM} --body "## 🧠 Brainstorm Round — All 4 Agents Complete

<details>
<summary>🏗️ Domain Expert</summary>

$(cat .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert.md)
</details>

<details>
<summary>👤 End User Advocate</summary>

$(cat .projects/${PROJECT_NUMBER}/2/brainstorm/end-user.md)
</details>

<details>
<summary>🔮 Outside Consultant</summary>

$(cat .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant.md)
</details>

<details>
<summary>🎨 UX Designer</summary>

$(cat .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer.md)
</details>"
```

---

## Phase 2: Synthesis — Cherry-Pick the Best Ideas

Now YOU (the Step 2 agent, as lead architect) read all 4 brainstorm outputs and synthesize a unified solution approach. This is your core value-add — pattern matching across domains.

Read all four brainstorm files, then write the synthesis to `.projects/${PROJECT_NUMBER}/2/synthesis-v1.md`:

```markdown
# Solution Synthesis v${ROUND}

## Source Attribution
For each element below, note which agent(s) contributed the core idea.

## Core Approach
<!-- 2-3 paragraphs: the unified solution philosophy -->

## Key Principles (cherry-picked from agents)
| # | Principle | Source Agent(s) | Why It Won |
|---|-----------|----------------|------------|
| 1 | ...       | ...            | ...        |
| 2 | ...       | ...            | ...        |

## Solution Architecture
<!-- How the pieces fit together. Not a UI spec — a conceptual model. -->

## User Flow (Conceptual)
<!-- The sequence of decisions/actions, not screens. -->
1. User opens app → ...
2. ...

## Open Questions Resolved
<!-- Ideas from agents that conflicted and how you resolved them -->

## Deliberately Excluded
<!-- Good ideas from agents that you chose NOT to include, and why -->
```

---

## Phase 3: Consensus Loop — Agent Review & Scoring

Feed the synthesis back to all 4 original agents for review. Each agent scores from their domain perspective. **Agents receive their full history** (original brainstorm + all prior syntheses and reviews) so they have accumulated context.

**Maximum 5 rounds.** Exit when all 4 agents score ≥ 9/10.

Set `ROUND=1`.

### 3A. Build Agent History & Launch Parallel Reviews

```bash
SYNTHESIS=$(cat .projects/${PROJECT_NUMBER}/2/synthesis-v${ROUND}.md)

# ── Build per-agent history (brainstorm + all prior syntheses + reviews) ──
build_agent_history() {
  local AGENT_NAME="$1"
  local BRAINSTORM=$(cat .projects/${PROJECT_NUMBER}/2/brainstorm/${AGENT_NAME}.md)
  local HISTORY="YOUR ORIGINAL BRAINSTORM:
${BRAINSTORM}"

  for prev in $(seq 1 $((ROUND - 1))); do
    local SYNTH_FILE=".projects/${PROJECT_NUMBER}/2/synthesis-v${prev}.md"
    if [ -f "${SYNTH_FILE}" ]; then
      HISTORY="${HISTORY}

--- SYNTHESIS YOU REVIEWED IN ROUND ${prev} ---
$(cat ${SYNTH_FILE})"
    fi

    local REVIEW_FILE=".projects/${PROJECT_NUMBER}/2/brainstorm/${AGENT_NAME}-review-v${prev}.md"
    if [ -f "${REVIEW_FILE}" ]; then
      HISTORY="${HISTORY}

--- YOUR REVIEW FROM ROUND ${prev} ---
$(cat ${REVIEW_FILE})"
    fi
  done

  echo "$HISTORY"
}

REVIEW_INSTRUCTIONS="Review this synthesis from your domain perspective. Score it 1-10.

Respond in EXACTLY this format:
SCORE: <number>
ASSESSMENT: <2-3 sentences on what works well from your domain>
CONCERNS: <specific issues that must be addressed, or NONE>
SUGGESTIONS: <concrete improvements, or NONE>"

# Launch all 4 reviews in parallel
DOMAIN_HISTORY=$(build_agent_history "domain-expert")
USER_HISTORY=$(build_agent_history "end-user")
CONSULTANT_HISTORY=$(build_agent_history "outside-consultant")
UX_HISTORY=$(build_agent_history "ux-designer")

claude --print -p "You are the same Domain Expert from the brainstorm phase. Here is your full context:

${DOMAIN_HISTORY}

THE LEAD ARCHITECT HAS SYNTHESIZED ALL 4 AGENTS' IDEAS INTO THIS SOLUTION (v${ROUND}):
${SYNTHESIS}

${REVIEW_INSTRUCTIONS}
" > .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert-review-v${ROUND}.md 2>&1 &
PID_DOMAIN_R=$!

claude --print -p "You are the same End User Advocate from the brainstorm phase. Here is your full context:

${USER_HISTORY}

THE LEAD ARCHITECT HAS SYNTHESIZED ALL 4 AGENTS' IDEAS INTO THIS SOLUTION (v${ROUND}):
${SYNTHESIS}

${REVIEW_INSTRUCTIONS}
" > .projects/${PROJECT_NUMBER}/2/brainstorm/end-user-review-v${ROUND}.md 2>&1 &
PID_USER_R=$!

# Outside Consultant: prefer Gemini
CONSULTANT_REVIEW_PROMPT="You are the same outside technology consultant from the brainstorm phase. Here is your full context:

${CONSULTANT_HISTORY}

THE LEAD ARCHITECT HAS SYNTHESIZED ALL 4 AGENTS' IDEAS INTO THIS SOLUTION (v${ROUND}):
${SYNTHESIS}

${REVIEW_INSTRUCTIONS}"

if command -v gemini &> /dev/null; then
  gemini -p "${CONSULTANT_REVIEW_PROMPT}" \
    > .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant-review-v${ROUND}.md 2>&1 &
  PID_CONSULTANT_R=$!
else
  claude --print -p "${CONSULTANT_REVIEW_PROMPT}" \
    > .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant-review-v${ROUND}.md 2>&1 &
  PID_CONSULTANT_R=$!
fi

claude --print -p "You are the same Senior UX Designer from the brainstorm phase. Here is your full context:

${UX_HISTORY}

THE LEAD ARCHITECT HAS SYNTHESIZED ALL 4 AGENTS' IDEAS INTO THIS SOLUTION (v${ROUND}):
${SYNTHESIS}

${REVIEW_INSTRUCTIONS}
" > .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer-review-v${ROUND}.md 2>&1 &
PID_UX_R=$!

echo "⏳ All 4 review agents launched (Round ${ROUND}). Waiting..."
wait $PID_DOMAIN_R $PID_USER_R $PID_CONSULTANT_R $PID_UX_R
echo "✅ All reviews complete for round ${ROUND}."
```

### 3B. Parse Scores

```bash
SCORE_DOMAIN=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert-review-v${ROUND}.md | head -1)
SCORE_USER=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/end-user-review-v${ROUND}.md | head -1)
SCORE_CONSULTANT=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant-review-v${ROUND}.md | head -1)
SCORE_UX=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer-review-v${ROUND}.md | head -1)

echo "Round ${ROUND} Scores: Domain=${SCORE_DOMAIN} User=${SCORE_USER} Consultant=${SCORE_CONSULTANT} UX=${SCORE_UX}"
```

### 3C. Post Review Round to Issue

```bash
gh issue comment ${STEP2_ISSUE_NUM} --body "## 📊 Consensus Round ${ROUND}

| Agent | Score | Key Concern |
|-------|-------|-------------|
| 🏗️ Domain Expert | ${SCORE_DOMAIN}/10 | $(grep -oP 'CONCERNS: \K.*' .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert-review-v${ROUND}.md) |
| 👤 End User | ${SCORE_USER}/10 | $(grep -oP 'CONCERNS: \K.*' .projects/${PROJECT_NUMBER}/2/brainstorm/end-user-review-v${ROUND}.md) |
| 🔮 Consultant | ${SCORE_CONSULTANT}/10 | $(grep -oP 'CONCERNS: \K.*' .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant-review-v${ROUND}.md) |
| 🎨 UX Designer | ${SCORE_UX}/10 | $(grep -oP 'CONCERNS: \K.*' .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer-review-v${ROUND}.md) |

**Consensus: $([ $SCORE_DOMAIN -ge 9 ] && [ $SCORE_USER -ge 9 ] && [ $SCORE_CONSULTANT -ge 9 ] && [ $SCORE_UX -ge 9 ] && echo '✅ REACHED' || echo '❌ NOT YET')**"
```

### 3D. Decision Gate

```bash
if [ "$SCORE_DOMAIN" -ge 9 ] && [ "$SCORE_USER" -ge 9 ] && \
   [ "$SCORE_CONSULTANT" -ge 9 ] && [ "$SCORE_UX" -ge 9 ]; then
  echo "✅ CONSENSUS REACHED in round ${ROUND}!"
  # → Proceed to Phase 4 (Finalize)
elif [ "$ROUND" -ge 5 ]; then
  echo "⚠️ BLOCKED: No consensus after 5 rounds."
  # → Post blocker and continue to finalize with best version
else
  echo "Revising synthesis based on feedback..."
  # → Revise and loop back to 3A
fi
```

### 3E. Revision (If No Consensus)

If consensus is not reached, YOU (the lead architect) revise the synthesis. Read ALL agent feedback from this round and produce an updated synthesis.

**Critical: Address every CONCERN and evaluate every SUGGESTION from agents who scored < 9.**

Write `.projects/${PROJECT_NUMBER}/2/synthesis-v$((ROUND + 1)).md` with the same structure as the original, plus:

```markdown
## Changes in v${NEXT_ROUND} (responding to Round ${ROUND} feedback)

| Agent | Their Concern | How Addressed |
|-------|--------------|---------------|
| ...   | ...          | ...           |
```

Then increment `ROUND` and loop back to Step 3A.

### 3F. Blocked State (Round 5, No Consensus)

```bash
gh issue comment ${STEP2_ISSUE_NUM} --body "## ⚠️ BLOCKED — No Consensus After 5 Rounds

| Round | Domain | User | Consultant | UX |
|-------|--------|------|------------|-----|
$(for r in $(seq 1 5); do
  SD=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  SU=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/end-user-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  SC=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  SX=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  echo "| ${r} | ${SD}/10 | ${SU}/10 | ${SC}/10 | ${SX}/10 |"
done)

**Persistent dissent from:** $([ ${SCORE_DOMAIN:-0} -lt 9 ] && echo '🏗️ Domain') $([ ${SCORE_USER:-0} -lt 9 ] && echo '👤 User') $([ ${SCORE_CONSULTANT:-0} -lt 9 ] && echo '🔮 Consultant') $([ ${SCORE_UX:-0} -lt 9 ] && echo '🎨 UX')

**Awaiting human input to break the deadlock.**
@${GH_USER}"
```

---

## Phase 4: Finalize

Once all 4 agents score ≥ 9/10 (or after blocker with best available version):

### 4A. Write Final Synthesis

```bash
cp .projects/${PROJECT_NUMBER}/2/synthesis-v${ROUND}.md \
   .projects/${PROJECT_NUMBER}/2/final.md

echo "Final synthesis written to .projects/${PROJECT_NUMBER}/2/final.md"
```

### 4B. Post Completion to Issue

```bash
gh issue comment ${STEP2_ISSUE_NUM} --body "## ✅ Step 2 Complete — Solution Consensus Reached

### Consensus History
| Round | Domain | User | Consultant | UX |
|-------|--------|------|------------|-----|
$(for r in $(seq 1 ${ROUND}); do
  SD=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/domain-expert-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  SU=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/end-user-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  SC=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/outside-consultant-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  SX=$(grep -oP 'SCORE: \K\d+' .projects/${PROJECT_NUMBER}/2/brainstorm/ux-designer-review-v${r}.md 2>/dev/null | head -1 || echo "N/A")
  echo "| ${r} | ${SD}/10 | ${SU}/10 | ${SC}/10 | ${SX}/10 |"
done)

### Final Solution Approach

$(cat .projects/${PROJECT_NUMBER}/2/final.md)

---
**All 4 agents approved (≥9/10)**
**Rounds to consensus:** ${ROUND}
**Ready for Step 3: Design the Interface**"
```

### 4C. Close Issue & Move to Plans

```bash
gh issue close ${STEP2_ISSUE_NUM} --reason completed \
  --comment "Solution exploration complete. All 4 domain experts reached consensus after ${ROUND} round(s)."

STEP2_ITEM_ID=$(get_item_id "Step 2")

gh project item-edit \
  --id "${STEP2_ITEM_ID}" \
  --project-id "${PROJECT_ID}" \
  --field-id "${STATUS_FIELD_ID}" \
  --single-select-option-id "${PLANS_OPTION_ID}"

echo "Step 2 issue #${STEP2_ISSUE_NUM} closed and moved to Plans."
```

### 4D. Update Shared Context

```bash
CONTEXT=$(cat .projects/${PROJECT_NUMBER}/context.json)
echo "$CONTEXT" | jq \
  --argjson round ${ROUND} \
  --argjson sd ${SCORE_DOMAIN} \
  --argjson su ${SCORE_USER} \
  --argjson sc ${SCORE_CONSULTANT} \
  --argjson sx ${SCORE_UX} \
  '.steps_completed += ["step-2"] | .step2_rounds = $round | .step2_scores = {"domain": $sd, "user": $su, "consultant": $sc, "ux": $sx}' \
  > .projects/${PROJECT_NUMBER}/context.json
```

### 4E. Commit Artifacts

```bash
git add .projects/${PROJECT_NUMBER}/2/
git commit -m "docs: Step 2 solution exploration for ${FEATURE_SUMMARY}

Project: #${PROJECT_NUMBER}
Issue: #${STEP2_ISSUE_NUM}
Agents: Domain Expert, End User, Outside Consultant, UX Designer
Consensus rounds: ${ROUND}
All agents scored ≥ 9/10"
```

### 4F. Signal Completion

```bash
echo ""
echo "════════════════════════════════════════════════"
echo "✅ Step 2: Explore the Solution Space — COMPLETE"
echo "════════════════════════════════════════════════"
echo ""
echo "Project Board: ${PROJECT_URL}"
echo "Issue: #${STEP2_ISSUE_NUM} (closed → Plans)"
echo "Consensus: All 4 agents ≥ 9/10 after ${ROUND} round(s)"
echo ""
echo "Agent Scores (Final Round):"
echo "  🏗️ Domain Expert:      ${SCORE_DOMAIN}/10"
echo "  👤 End User Advocate:   ${SCORE_USER}/10"
echo "  🔮 Outside Consultant:  ${SCORE_CONSULTANT}/10"
echo "  🎨 UX Designer:         ${SCORE_UX}/10"
echo ""
echo "Output: .projects/${PROJECT_NUMBER}/2/final.md"
echo ""
echo "Handing back to orchestrator."
echo "════════════════════════════════════════════════"
```

---

## Execution Notes

### Agent Persistence via Context Accumulation
Each brainstorm agent is a stateless subprocess. To simulate persistence across consensus rounds, every review invocation feeds the agent:
1. Their **original brainstorm** (foundational thinking)
2. Each **prior synthesis they reviewed** (what they were responding to)
3. Each **prior review they wrote** (their evolving feedback)
4. The **current synthesis** being reviewed

This is built by the `build_agent_history` function. By Round 3, an agent sees their full decision trail, which is functionally equivalent to a persistent session with memory.

### Parallelism
All 4 agents (3x `claude --print` + 1x `gemini`/`claude`) run as backgrounded subprocesses. The `wait` command blocks until all complete.

### Score Parsing Safety
The `head -1` in score parsing handles cases where an agent's output might contain "SCORE" in reasoning text. Only the first match is used.

### Gemini Fallback
If `gemini` CLI is unavailable, the Outside Consultant role is filled by a `claude --print` invocation, with a warning flag: `⚠️ Gemini unavailable — Outside Consultant role filled by Claude (reduced independence)`.

### Idempotency
If rerun, detect existing brainstorm/synthesis files and resume from the appropriate round. Check the last `synthesis-v*.md` and `*-review-v*.md` files to determine the current round.

### Your Output Contract
The orchestrator expects `.projects/${PROJECT_NUMBER}/2/final.md` to exist when you exit. If blocked after 5 rounds, still write the best version as final.md.

### All Issue Lookups Are Project-Scoped
Never use `gh issue list` to find issues. Use `gh project item-list` or the `get_item_id` helper to resolve items within this project only.
