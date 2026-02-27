# CHENG Test Strategy

## Overview

### The Problem

Running the full test suite before every commit is too slow. The CHENG test
suite currently has ~800 backend tests (~138s), ~340 frontend Vitest tests
(~2.5s), and 28 Playwright E2E tests. Running everything pre-commit adds
2-3 minutes of latency to every commit, slowing down development.

### The Solution: Tiered Testing

CHENG uses a three-tier test architecture that balances speed with coverage:

| Tier | Name | When | Time Budget | Mechanism |
|------|------|------|-------------|-----------|
| 1 | Smoke | Always, pre-commit | < 15s total | `@pytest.mark.smoke` + smoke vitest config |
| 2 | Change-scoped | Pre-commit, when source changed | < 45s additional | `pytest --testmon` + `vitest --changed` |
| 3 | Full suite | Pre-merge (CI enforced) | < 10 min | Full `pytest` + full `vitest run` |

The pre-commit script (`scripts/test-precommit.sh`) runs Tier 1 and Tier 2
automatically. Tier 3 is enforced by the CI workflow on every pull request.

---

## Tier 1: Smoke Tests

Smoke tests are a small, carefully selected subset of tests that validate the
most critical paths. They always run, regardless of what changed.

**Target:** < 15 seconds total (backend + frontend combined).

**Backend smoke tests** are tagged with `@pytest.mark.smoke`:

```python
@pytest.mark.smoke
def test_default_has_few_warnings():
    ...
```

The `smoke` marker is registered in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "smoke: fast, critical-path tests that always run pre-commit (< 15s total)",
]
```

To run backend smoke tests manually:

```bash
python -m pytest tests/backend/ -m smoke --tb=short -q
```

**Frontend smoke tests** live in `tests/frontend/smoke/` and use the
`.smoke.test.ts` suffix. They are loaded by `tests/frontend/vitest.smoke.config.ts`.

To run frontend smoke tests manually:

```bash
cd frontend
pnpm exec vitest run --config ../tests/frontend/vitest.smoke.config.ts
```

### What makes a good smoke test?

A smoke test should:
- Run in under 1 second
- Cover a critical integration point (model validation, storage round-trip,
  WebSocket message parsing, unit conversion)
- Detect regressions in core data structures or contracts
- Never depend on external services or the live app

A smoke test should NOT:
- Run geometry computation (too slow)
- Require a running server
- Test edge cases or error paths in detail (leave that to integration tests)

### Adding a new backend smoke test

1. Write a fast unit test (no CadQuery, no HTTP client, no async where avoidable).
2. Add `@pytest.mark.smoke` decorator.
3. Verify it runs in the smoke suite: `python -m pytest tests/backend/ -m smoke -v`

### Adding a new frontend smoke test

1. Create a file in `tests/frontend/smoke/` with the suffix `.smoke.test.ts`.
2. Import only from `frontend/src/` (no React component rendering needed for
   pure utility smoke tests).
3. Verify it appears in the smoke run:
   ```bash
   cd frontend
   pnpm exec vitest run --config ../tests/frontend/vitest.smoke.config.ts
   ```

---

## Tier 2: Change-Scoped Tests

Change-scoped tests run only the tests affected by your current changes.
This gives near-full coverage without paying for the full suite time.

**Target:** < 45 seconds additional (on top of Tier 1 smoke tests).

### Backend: pytest-testmon

`pytest-testmon` tracks which source files each test covers using Python
coverage. On subsequent runs it only runs tests whose covered source has changed.

To initialize testmon data (run once after setup, or after large refactors):

```bash
python -m pytest tests/backend/ --testmon
```

This creates `.testmondata` in the repo root (gitignored). Subsequent runs
with `--testmon` only execute affected tests.

To run manually:

```bash
python -m pytest tests/backend/ --testmon --tb=short -q
```

**Fallback:** If `.testmondata` is missing (first run on a new machine, after
a full clean, or if the pre-commit script detects it is absent), the script
falls back to running the full backend suite with a warning:

```
[WARN] .testmondata not found — running full backend suite
Tip: Run 'python -m pytest tests/backend/ --testmon' once to initialize
```

### Frontend: vitest --changed

Vitest's `--changed` flag runs only test files that import modules changed
since a given commit reference.

```bash
cd frontend
pnpm exec vitest run --config ../tests/frontend/vitest.config.ts --changed HEAD~1
```

**Important:** The `--config` flag is required. Without it, vitest silently
finds 0 tests and exits with code 0, giving a false pass. Always include
`--config ../tests/frontend/vitest.config.ts` when running `vitest --changed`.

**Fallback:** If `HEAD~1` does not exist (first commit on a new branch), the
pre-commit script falls back to comparing against the upstream branch:

```bash
pnpm exec vitest run \
    --config ../tests/frontend/vitest.config.ts \
    --changed origin/plan/test-optimization-plan
```

---

## Tier 3: Full Suite

The full test suite is the merge gate. It runs automatically on every pull
request via GitHub Actions (`.github/workflows/ci.yml`).

**Backend (from repo root):**

```bash
python -m pytest tests/backend/ -v
```

**Frontend (from repo root):**

```bash
cd frontend
pnpm exec vitest run --config ../tests/frontend/vitest.config.ts
```

**Playwright E2E** (manual only — requires the live app):

```bash
cd frontend
NODE_PATH=./node_modules npx playwright test
```

E2E tests are excluded from CI because they require a running backend and
frontend. Run them manually before merging significant UI changes.

---

## Pre-Commit Script

`scripts/test-precommit.sh` is the single entry point for pre-commit testing.
Run it from the repo root:

```bash
bash scripts/test-precommit.sh
```

The script:

1. Detects which files changed (staged + unstaged against HEAD).
2. Classifies changes as backend, frontend, or infra.
3. Applies escalation rules (see below).
4. Runs Tier 1 smoke tests (always).
5. Runs Tier 2 change-scoped tests (if backend or frontend files changed).
6. Exits 0 on pass, 1 on failure with a clear `[FAIL]` message.

The `fail()` helper function is used throughout instead of `set -e`, so the
script can report exactly which test tier failed before exiting.

---

## Escalation Rules

The pre-commit script escalates automatically when infrastructure files change.
You can also escalate manually when making broad changes.

### Automatic escalation: infrastructure change

If any of the following file types changed:

- `*.toml` (pyproject.toml, etc.)
- `*.yaml` / `*.yml` (CI configs, Docker Compose)
- `Dockerfile*`, `docker-compose*`
- `Makefile`
- `.github/*`

The script runs the **full backend + frontend suite** instead of the tiered
approach:

```
[ESCALATE] Infrastructure change detected — running full backend + frontend suite
```

### Manual escalation: broad changes

If you are making changes that touch 3 or more modules, shared utilities,
or core config files, skip the pre-commit script and run the full suite
directly:

```bash
python -m pytest tests/backend/ -v
cd frontend && pnpm exec vitest run --config ../tests/frontend/vitest.config.ts
```

This is documented in `.claude/agents/developer_agent.md` as an explicit rule.

---

## Edge Cases

### testmon data is stale or missing

**Symptom:** `.testmondata` does not exist, or testmon reports all tests as
needing to run even for tiny changes.

**Cause:** `.testmondata` is gitignored and not committed. It must be
regenerated on each developer machine.

**Resolution:** Run the full backend suite once with testmon to rebuild:

```bash
python -m pytest tests/backend/ --testmon
```

After this, subsequent `--testmon` runs will be incremental.

**Pre-commit script behavior:** Falls back to full backend suite with a warning.
This is safe — you get correct results, just slower than testmon would provide.

### Smoke tests fail

**Cause:** A core integration point has regressed (model validation, storage
protocol, WebSocket message format, unit conversion).

**Resolution:** Fix the regression before committing. Smoke test failures
indicate a problem that would affect all users immediately.

The pre-commit script exits with `[FAIL]` and a descriptive message:

```
[FAIL] Backend smoke tests failed. Fix before committing.
```

### HEAD~1 not available (first commit on new branch)

**Cause:** The branch has only one commit, so `HEAD~1` does not exist.

**Resolution:** The pre-commit script detects this and falls back to comparing
against the upstream branch automatically. No manual intervention needed.

### Broad change but not classified as infra

**Cause:** You are refactoring multiple modules but the changed files are not
in the infra escalation list.

**Resolution:** Run the full suite manually before committing:

```bash
python -m pytest tests/backend/ -v
cd frontend && pnpm exec vitest run --config ../tests/frontend/vitest.config.ts
```

---

## Adding New Tests

Use this guide to decide which tier a new test belongs in.

| Question | If Yes | If No |
|----------|--------|-------|
| Does it test a critical contract that all users depend on? | Consider Tier 1 (smoke) | Consider Tier 2 or 3 |
| Does it run in under 1 second with no external dependencies? | Eligible for Tier 1 | Must be Tier 2 or 3 |
| Does it require CadQuery, HTTP client, or async engine? | Tier 2 or 3 | Can be Tier 1 if fast |
| Does it require the live app or a running server? | Tier 3 (Playwright E2E) | Tier 1 or 2 |

**Rule of thumb:**
- Tier 1 (smoke): model validation, data structures, storage protocol, unit
  conversion, WebSocket message parsing — things that break everything if wrong.
- Tier 2 (change-scoped): feature-specific logic, route handlers, geometry
  helpers — things that matter for specific modules.
- Tier 3 (full suite + E2E): end-to-end flows, export pipelines, UI interactions
  — things that require the full stack.

---

## Success Metrics

| Metric | Target | Current Baseline |
|--------|--------|-----------------|
| Pre-commit wall time (Tier 1 + 2) | < 60s | ~15-30s typical |
| Smoke test suite time | < 15s | ~1s backend + ~0.8s frontend |
| Full backend suite time | < 5 min | ~138s |
| Full frontend Vitest time | < 60s | ~2.5s |
| Pre-merge regressions slipping through | 0 | — |

The pre-commit script should never block developers with false positives.
If a test is too slow or flaky for Tier 1, move it to Tier 2. If it requires
the full stack, move it to Tier 3 (CI).

---

## Related Files

| File | Purpose |
|------|---------|
| `scripts/test-precommit.sh` | Pre-commit test runner (Tier 1 + 2) |
| `tests/frontend/vitest.smoke.config.ts` | Vitest config for smoke tests only |
| `tests/frontend/vitest.config.ts` | Vitest config for full frontend suite |
| `tests/frontend/smoke/` | Frontend smoke test directory |
| `.github/workflows/ci.yml` | CI workflow (Tier 3, enforced on PRs) |
| `.claude/agents/developer_agent.md` | Developer agent with test policy |
| `pyproject.toml` | `[tool.pytest.ini_options]` with marker definitions |
| `.gitignore` | `.testmondata` is gitignored (regenerated per machine) |
