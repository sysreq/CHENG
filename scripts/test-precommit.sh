#!/usr/bin/env bash
# =============================================================================
# CHENG — Pre-commit test runner
# Smoke tests (always) + change-scoped tests (based on diff)
#
# Usage: bash scripts/test-precommit.sh
#   or:  ./scripts/test-precommit.sh (after chmod +x)
#
# Tiers:
#   Tier 1 — Smoke:         Always run, < 15s total
#   Tier 2 — Change-scoped: Based on git diff, < 45s additional
#   Tier 3 — Full suite:    Pre-merge only (not run here)
#
# Escalation rules:
#   - If infra files changed (*.toml, *.yaml, *.yml, docker*, Makefile, .github/*)
#     → Run full backend + frontend suite instead of change-scoped
#   - If broad changes (≥3 modules): skip this script, run full suite manually
#   - If testmon data is stale/missing: fall back to full pytest
#
# See docs/test_strategy.md for the complete test policy.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root (works from any working directory)
# ---------------------------------------------------------------------------

REPO_ROOT="$(git rev-parse --show-toplevel)"

# ---------------------------------------------------------------------------
# Detect changed files
# ---------------------------------------------------------------------------

# Use HEAD diff — files changed but not yet committed
CHANGED_FILES="$(git diff --name-only HEAD 2>/dev/null || true)"

# Also include staged changes
STAGED_FILES="$(git diff --name-only --cached 2>/dev/null || true)"

# Combine both (unique)
ALL_CHANGED="$(printf '%s\n%s\n' "$CHANGED_FILES" "$STAGED_FILES" | sort -u | grep -v '^$' || true)"

# ---------------------------------------------------------------------------
# Classify changes
# ---------------------------------------------------------------------------

BACKEND_CHANGED=false
FRONTEND_CHANGED=false
INFRA_CHANGED=false

if [ -n "$ALL_CHANGED" ]; then
    while IFS= read -r file; do
        case "$file" in
            backend/*)
                BACKEND_CHANGED=true ;;
            frontend/*)
                FRONTEND_CHANGED=true ;;
            *.toml|*.yaml|*.yml|Dockerfile*|docker-compose*|Makefile|.github/*)
                INFRA_CHANGED=true ;;
            scripts/*)
                # Script changes don't require re-running tests — the script itself changed
                : ;;
        esac
    done <<< "$ALL_CHANGED"
fi

echo "=== CHENG Pre-Commit Tests ==="
echo "Backend changed:  $BACKEND_CHANGED"
echo "Frontend changed: $FRONTEND_CHANGED"
echo "Infra changed:    $INFRA_CHANGED"
echo ""

# ---------------------------------------------------------------------------
# ESCALATION: Infrastructure change → full suite
# ---------------------------------------------------------------------------

if [ "$INFRA_CHANGED" = true ]; then
    echo "[ESCALATE] Infrastructure change detected — running full backend + frontend suite"
    echo ""

    echo "--- Full backend suite ---"
    cd "$REPO_ROOT"
    python -m pytest tests/backend/ -q --tb=short
    BACKEND_EXIT=$?

    echo ""
    echo "--- Full frontend suite ---"
    cd "$REPO_ROOT/frontend"
    pnpm exec vitest run --config ../tests/frontend/vitest.config.ts
    FRONTEND_EXIT=$?

    if [ $BACKEND_EXIT -ne 0 ] || [ $FRONTEND_EXIT -ne 0 ]; then
        echo ""
        echo "[FAIL] Full suite failed. Fix failing tests before committing."
        exit 1
    fi

    echo ""
    echo "[PASS] Full suite passed (escalated due to infra change)"
    exit 0
fi

# ---------------------------------------------------------------------------
# TIER 1: Smoke tests — always run
# ---------------------------------------------------------------------------

echo "--- Tier 1: Smoke tests (always) ---"

# Backend smoke tests
echo "[backend] pytest -m smoke"
cd "$REPO_ROOT"
python -m pytest tests/backend/ -m smoke --tb=short -q
SMOKE_BACKEND_EXIT=$?

# Frontend smoke tests
echo ""
echo "[frontend] vitest run (smoke only)"
cd "$REPO_ROOT/frontend"
pnpm exec vitest run --config ../tests/frontend/vitest.smoke.config.ts
SMOKE_FRONTEND_EXIT=$?

if [ $SMOKE_BACKEND_EXIT -ne 0 ] || [ $SMOKE_FRONTEND_EXIT -ne 0 ]; then
    echo ""
    echo "[FAIL] Smoke tests failed. Fix before committing."
    exit 1
fi

echo ""
echo "[PASS] Smoke tests passed"

# ---------------------------------------------------------------------------
# TIER 2: Change-scoped tests
# ---------------------------------------------------------------------------

if [ "$BACKEND_CHANGED" = false ] && [ "$FRONTEND_CHANGED" = false ]; then
    echo ""
    echo "No backend or frontend source changes detected — skipping Tier 2."
    echo "[PASS] Pre-commit tests complete"
    exit 0
fi

echo ""
echo "--- Tier 2: Change-scoped tests ---"

TIER2_EXIT=0

# Backend change-scoped
if [ "$BACKEND_CHANGED" = true ]; then
    echo "[backend] pytest --testmon (change-scoped)"
    cd "$REPO_ROOT"

    if [ -f ".testmondata" ]; then
        # testmon data exists — run only affected tests
        python -m pytest tests/backend/ --testmon --tb=short -q
        TESTMON_EXIT=$?
    else
        # No testmon data — fall back to full backend suite
        echo "  [WARN] .testmondata not found — running full backend suite"
        echo "  Tip: Run 'python -m pytest tests/backend/ --testmon' once to initialize"
        python -m pytest tests/backend/ -q --tb=short
        TESTMON_EXIT=$?
    fi

    if [ $TESTMON_EXIT -ne 0 ]; then
        TIER2_EXIT=1
    fi
fi

# Frontend change-scoped
if [ "$FRONTEND_CHANGED" = true ]; then
    echo ""
    echo "[frontend] vitest run --changed HEAD~1 (change-scoped)"
    cd "$REPO_ROOT/frontend"

    # Check if HEAD~1 exists (fails on first commit of branch)
    if git rev-parse HEAD~1 >/dev/null 2>&1; then
        pnpm exec vitest run \
            --config ../tests/frontend/vitest.config.ts \
            --changed HEAD~1
        VITEST_CHANGED_EXIT=$?
    else
        # First commit on branch — compare against plan branch base
        echo "  [INFO] HEAD~1 not available — comparing against origin/plan/test-optimization-plan"
        PLAN_BASE="$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || echo 'origin/plan/test-optimization-plan')"
        pnpm exec vitest run \
            --config ../tests/frontend/vitest.config.ts \
            --changed "$PLAN_BASE"
        VITEST_CHANGED_EXIT=$?
    fi

    if [ $VITEST_CHANGED_EXIT -ne 0 ]; then
        TIER2_EXIT=1
    fi
fi

# ---------------------------------------------------------------------------
# Final result
# ---------------------------------------------------------------------------

echo ""
if [ $TIER2_EXIT -ne 0 ]; then
    echo "[FAIL] Change-scoped tests failed. Fix failing tests before committing."
    exit 1
fi

echo "[PASS] Pre-commit tests complete (smoke + change-scoped)"
exit 0
