# vitest --changed Flag Verification

> Issue: #342
> Branch: feat/issue-342
> Date: 2026-02-27

## Summary

The `vitest run --changed HEAD~1` flag works correctly in this repository,
but MUST be used with the explicit `--config` flag pointing to the custom
vitest config (`tests/frontend/vitest.config.ts`).

## Verification Results

### Test 1: Without --config (incorrect)

```bash
cd frontend && pnpm exec vitest run --changed HEAD~1
```

**Result:** `No test files found, exiting with code 0`

**Cause:** Without `--config`, vitest uses its default include pattern
(`**/*.{test,spec}.?(c|m)[jt]s?(x)`). Our test files are in
`tests/frontend/unit/` and `tests/frontend/smoke/` — outside the
`frontend/` root. The default pattern doesn't find them.

### Test 2: With --config (correct)

```bash
cd frontend && pnpm exec vitest run --config ../tests/frontend/vitest.config.ts --changed HEAD~1
```

**Result:** Selects only tests affected by `frontend/src/components/Toolbar.tsx`
(most recent commit). Ran 1 test file (responsiveLayout.test.tsx, 9 tests)
instead of the full 22 test files (342 tests). Duration: 1.92s.

**Cause:** The custom config sets `root: frontendDir` and `include` pointing
to the correct test directories. Vitest traverses the module graph from
changed files and selects only tests that transitively import them.

## Conclusion

The `--changed` flag works as expected. For use in `scripts/test-precommit.sh`:

```bash
# Correct invocation (uses custom config):
cd "$REPO_ROOT/frontend" && pnpm exec vitest run \
  --config ../tests/frontend/vitest.config.ts \
  --changed HEAD~1
```

The script MUST include `--config ../tests/frontend/vitest.config.ts`
or the flag will silently find no tests and exit 0 (false negative).

## Edge Cases Discovered

1. **No frontend changes since last commit**: `--changed HEAD~1` outputs
   `No test files found` and exits 0. This is correct behavior —
   if nothing changed, no tests need to run.

2. **First commit on branch**: `HEAD~1` may not exist. Use
   `--changed origin/<base-branch>` instead to compare against the
   branch base. The precommit script should handle this gracefully.

3. **Smoke tests included**: Since `vitest.config.ts` now includes both
   `unit/` and `smoke/`, the `--changed` flag will also detect changes
   to smoke test files themselves and run them.

## Recommendation for scripts/test-precommit.sh

```bash
# Frontend change-scoped tests:
cd "$REPO_ROOT/frontend"
if git rev-parse HEAD~1 >/dev/null 2>&1; then
  pnpm exec vitest run --config ../tests/frontend/vitest.config.ts --changed HEAD~1
else
  # First commit on branch — compare against plan branch base
  pnpm exec vitest run --config ../tests/frontend/vitest.config.ts --changed origin/plan/test-optimization-plan
fi
```
