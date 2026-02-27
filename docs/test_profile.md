# CHENG Test Layer Profile

> Generated: 2026-02-27
> Branch: plan/test-optimization-plan
> Issue: #338

## Summary

| Layer    | Framework  | Test Count | Estimated Runtime | Notes |
|----------|------------|------------|-------------------|-------|
| Backend  | pytest     | 805        | ~138s (2m18s)     | 1 pre-existing failure in test_cheng_mode |
| Frontend | Vitest     | 342        | ~2.5s             | 3 pre-existing failures in designPortability.test.ts |
| E2E      | Playwright | 28         | ~3-5min (needs live app) | 3 spec files |

---

## Backend Profile (pytest)

**Command:** `python -m pytest tests/backend/ -q --tb=no`
**Total tests:** 805
**Full suite runtime:** ~138 seconds (2 min 18 sec)
**Collected in:** 6.4 seconds

### Test File Breakdown by Estimated Runtime

| File | Tests | Runtime | Notes |
|------|-------|---------|-------|
| test_export.py + test_export_formats.py + test_export_pipeline.py + test_export_preview.py + test_export_security.py | 106 | ~59s | Slow: geometry + file I/O |
| test_geometry.py + test_geometry_generation.py | 84 | ~41s | Slow: CadQuery geometry |
| test_routes.py + test_websocket.py + test_integration.py + test_cloud_run.py | 81 | ~32s | Medium: HTTP + WS handlers |
| test_landing_gear.py + test_tail_airfoil.py + test_tail_clamping.py + test_wing_panel_selection.py + test_smart_splits.py | 119 | ~10s | Medium: some geometry |
| test_multi_section_wings.py | 51 | ~2s | Fast |
| test_cg_calculator.py + test_derived_values.py + test_presets.py + test_weight_estimation.py | 78 | ~0.3s | Very fast: pure math |
| test_models.py + test_cheng_mode.py + test_info_route.py | 57 | ~0.2s | Very fast: model/config |
| test_validation.py + test_validation_v09_v13.py + test_validation_v24_v28.py + test_validation_weight_perf.py | 88 | ~0.07s | Extremely fast: pure logic |
| test_stability.py | 17 | ~0.02s | Extremely fast: pure math |
| test_storage.py + test_memory_storage.py + test_cleanup.py + test_design_portability.py | ~80 | ~0.5s | Very fast: in-memory |

### Slow Test Groups (NOT suitable for smoke)
- **Export tests** (`test_export*.py`): ~59s — trigger full geometry pipeline + disk I/O
- **Geometry generation tests** (`test_geometry*.py`): ~41s — invoke CadQuery directly
- **Route/WebSocket/Integration tests** (`test_routes.py`, `test_websocket.py`, `test_integration.py`): ~32s — run real HTTP/WS handlers with geometry

---

## Frontend Profile (Vitest)

**Command:** `cd frontend && pnpm test -- --run`
**Total tests:** 342 across 22 test files
**Full suite runtime:** ~2.5 seconds (very fast already)
**Config:** `tests/frontend/vitest.config.ts`

### Test File Locations
All frontend tests are in `tests/frontend/unit/`:

| File | Description |
|------|-------------|
| connectionStore.test.ts | WebSocket connection state machine |
| meshParser.test.ts | Binary mesh frame parsing |
| panelsEditing.test.ts | Panel editing logic |
| exportDialog.test.ts | Export dialog interactions |
| hooks.test.ts | Custom React hooks |
| motorToggle.test.ts | Motor config toggle logic |
| panelAirfoils.test.ts | Per-panel airfoil selection |
| validation.test.ts | Frontend validation utilities |
| designStore.test.ts | Main Zustand design store |
| wingPanelSelection.test.ts | Wing panel selection logic |
| coldStart.test.ts | Cold start detection hook |
| indexeddb.test.ts | IndexedDB persistence |
| designPortability.test.ts | Import/export JSON (3 pre-existing failures) |
| printBedPrefs.test.ts | Print bed preferences |
| printBedPrefsIntegration.test.ts | Print bed prefs integration |
| presets.test.ts | Preset configurations |
| controlSurfaceSection.test.tsx | Control surface UI |
| modeBadge.test.tsx | Mode badge component |
| accessibility.test.tsx | ARIA/accessibility |
| responsiveLayout.test.tsx | Responsive layout |
| unitToggle.test.tsx | Unit toggle component |
| StabilityPanel.test.tsx | Stability panel component |

### Pre-existing Failures
- `designPortability.test.ts` — 3 tests fail due to `URL.revokeObjectURL` mock issue in jsdom.
  These are pre-existing and unrelated to the test optimization plan.

---

## E2E Profile (Playwright)

**Command:** `cd frontend && NODE_PATH=./node_modules npx playwright test --list`
**Total tests:** 28 tests in 3 spec files

| Spec File | Tests | Coverage Area |
|-----------|-------|---------------|
| app.spec.ts | 7 | Core app flows (presets, params, export, undo) |
| features.spec.ts | 13 | Extended features (presets, export formats, tail config, panels, WebSocket, camera, design name, history, bidirectional) |
| stability.spec.ts | 8 | Stability overlay, gauges, live region |

**E2E tests require the full app to be running** (backend + frontend). They are excluded from
pre-commit testing entirely and run only at merge time.

---

## Smoke Test Candidates

### Backend Smoke Candidates

Criteria: fast (< 0.5s/test individually), covers critical-path infrastructure, historically stable.

| Test | File | Justification |
|------|------|---------------|
| `TestGetChengMode::test_default_is_local` | test_cheng_mode.py | Config loading |
| `TestGetChengMode::test_local_mode` | test_cheng_mode.py | Config loading |
| `TestGetChengMode::test_cloud_mode` | test_cheng_mode.py | Config loading |
| `TestCreateStorageBackend::test_local_mode_returns_local_storage` | test_cheng_mode.py | Storage init |
| `TestCreateStorageBackend::test_cloud_mode_returns_memory_storage` | test_cheng_mode.py | Storage init |
| `TestInfoEndpoint::test_info_local_mode` | test_cheng_mode.py | API route init |
| `TestInfoEndpoint::test_info_returns_version` | test_cheng_mode.py | API route init |
| `TestHealthEndpoint::test_health_returns_status_ok` | test_cloud_run.py | Health check |
| `TestHealthEndpoint::test_health_returns_mode_field` | test_cloud_run.py | Health check |
| `TestAircraftModel::*` (first 5) | test_models.py | Core Pydantic model |
| `TestValidation::test_no_warnings_for_valid_design` | test_validation.py | Validation entry point |
| `TestStaticStability::test_static_margin_positive_for_stable_config` | test_stability.py | Stability module |
| `TestStaticStability::test_neutral_point_aft_of_cg` | test_stability.py | Stability math |
| `TestDerivedValues::test_derived_computes_aspect_ratio` | test_derived_values.py | Derived values |
| `TestPresets::test_trainer_preset_has_expected_wingspan` (or similar) | test_presets.py | Preset loading |
| `LocalStorageTests` (first 3) | test_storage.py | Storage CRUD |
| `MemoryStorage` (first 3) | test_memory_storage.py | Storage CRUD |

**Target:** 15-20 smoke tests completing in < 5s total.

### Frontend Smoke Candidates

Criteria: fast, no external dependencies, covers core state management and utilities.

| File/Tests | Justification |
|-----------|---------------|
| `connectionStore.test.ts` (all, ~8 tests) | Core WebSocket state machine |
| `validation.test.ts` (first 5 tests) | Frontend warning utilities |
| `meshParser.test.ts` (first 3 tests) | Binary protocol parsing |
| `presets.test.ts` (first 3 tests) | Preset configuration loading |

**Recommended smoke directory:** `tests/frontend/smoke/`
**Target:** 15-20 smoke tests completing in < 5s total.

---

## Slow Test Identification

### Backend — Slowest Groups
1. **Export pipeline** (`test_export*.py`): 59s — triggers full geometry + disk I/O
2. **Geometry generation** (`test_geometry*.py`): 41s — full CadQuery solids
3. **HTTP routes + WebSocket** (`test_routes.py`, `test_websocket.py`): 32s — ASGI app startup

These three groups account for the majority of the ~138s runtime.

### Frontend — Slow Tests
The full frontend suite is already ~2.5s — no significant slow tests identified.
Environment setup (jsdom) accounts for ~20s one-time cost.
The `designPortability.test.ts` has pre-existing mock failures that should be fixed separately.

### E2E — All Slow
All 28 Playwright tests require a live app and are estimated at 3-5 minutes total.
**None should run pre-commit.**

---

## Runtime Targets

| Tier | Target | Backend | Frontend | E2E |
|------|--------|---------|----------|-----|
| Smoke (pre-commit) | < 15s | pytest -m smoke | vitest run tests/frontend/smoke | excluded |
| Change-scoped (pre-commit) | < 45s | pytest --testmon | vitest --changed HEAD~1 | excluded |
| Full suite (pre-merge) | no limit | pytest tests/backend/ | vitest run | playwright test |

---

## Open Questions Answered

1. **Actual breakdown of ~5 min runtime across layers:**
   - pytest: ~138s (2m18s) — dominated by geometry/export/route tests
   - Vitest: ~2.5s (already fast; jsdom setup adds ~20s one-time)
   - Playwright: estimated 3-5min (requires live app, not measured in isolation)
   - **Total pre-commit (current):** ~140s backend + 2.5s frontend = ~2.5 minutes
   - The 5-minute estimate was likely inclusive of startup overhead, app boot, and E2E

2. **Tests that are slow and potentially low-value:**
   - The export tests (59s) are comprehensive but slow. Consider marking as `@pytest.mark.slow` to skip by default.
   - `test_integration.py` covers broad flows — valuable but slow. Keep in full suite only.

3. **pytest-testmon data committed?**
   - **Recommendation: NO.** Add `.testmondata` to `.gitignore`. Each agent regenerates it on first use with a full run.

4. **Shared CI cache for testmon?**
   - Not currently set up. CI will run the full suite anyway (merge gate), so testmon is developer-only.
