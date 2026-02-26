# Feature Requirements: Airfoil Polar Analysis (Cl, Cd, Cl/Cd)

> **Author:** Technical Architect (synthesis of CFD Expert + Linux/DevOps independent research)
> **Date:** 2026-02-26
> **Input Documents:**
> - `reqs/aerospace/xfoil-cfd-expert-findings.md` — Aerospace/CFD expert findings (Mark Drela-era XFoil validation, neuralfoil accuracy profile, CHENG gap analysis)
> - Linux/DevOps independent research (web search, Dockerfile analysis, Cloud Run docs)
> **Status:** Final — ready for implementation planning

---

## 1. Executive Summary

Airfoil polar analysis — computing the Cl vs. α (lift curve), Cl/Cd vs. α (efficiency curve), and derived scalars such as Cl_max, stall speed, and cruise lift-to-drag ratio — is a high-value addition to CHENG that directly answers the RC designer's most practical questions: "Where does my wing stall?", "How efficient is my airfoil at cruise?", and "What is my speed margin above stall?" The feature is well-matched to CHENG's existing architecture: airfoil .dat files already exist, wing geometry and weight are already computed, and the backend is already Python-based. The only missing input is cruise airspeed, which requires adding one new user parameter (G09).

The recommended implementation approach is **neuralfoil** (Peter Sharpe, MIT), a pure-Python/NumPy machine-learning surrogate of XFoil that requires no external binaries, compiles zero Fortran, introduces no X11 or display dependencies, and delivers full polar computation in under 50ms. Its single non-trivial dependency is `aerosandbox` (which already depends on NumPy, already present in the CHENG image). neuralfoil has been peer-reviewed and published (arxiv 2503.16323), achieving mean drag error of 0.37% on standard cases and 2.0% on challenging post-stall and transitional cases relative to XFoil — fully adequate for CHENG's RC audience. XFoil subprocess integration is documented as a Phase 5 optional upgrade path with significant additional complexity; it is explicitly not recommended for the initial feature.

The feasibility verdict is **FEASIBLE WITHOUT CONDITIONS** for the neuralfoil path. A full MVP (scalar outputs: Cl_max, stall speed, cruise L/D, stall margin) can be delivered as a backend-only change in approximately 2–3 days. The complete feature including interactive polar charts requires an additional 4–6 days of frontend work and a chart library addition (recharts recommended). Total implementation effort across both phases is estimated at **7–10 developer-days (M complexity)**.

The overall complexity rating is **Medium** — no novel infrastructure is needed, all integration points follow established CHENG patterns (new DerivedValues fields, new route, new panel section), and neuralfoil's pure-Python nature means the Dockerfile requires only a single `pip install` line addition. The primary risk is aerosandbox transitive dependency size (~25–40 MB installed, dominated by SciPy), which is manageable. XFoil subprocess fallback, if ever pursued, is rated **High** complexity and is explicitly out of scope for this feature.

---

## 2. Feasibility Assessment

### 2.1 Approach Options

| Approach | Feasibility on Cloud Run | Accuracy | Speed | Docker Size Impact | Complexity | Recommended? |
|---|---|---|---|---|---|---|
| **neuralfoil** (pure Python ML surrogate) | Full — zero binary, zero display deps | High — ΔCl 0.006, ΔCd 0.00022 RMS vs. XFoil; ~2% on hard cases | Excellent — <50ms per full polar (51 α points) | Low — ~30–45 MB (aerosandbox + SciPy; NumPy already present) | Low | **YES** |
| XFoil binary via `apt-get install xfoil` | Partial — binary execution allowed; X11/PGPLOT deps require Xvfb or build-time PGPLOT strip | High — industry standard; Cd ±10–20%, Cl ±3–5% | Medium — 2–5s per polar via subprocess | Medium — xfoil binary ~2 MB; PGPLOT + Xvfb adds 20–50 MB; gfortran runtime ~5 MB | High | No — initial |
| XFoil compiled from source in Dockerfile | Partial — compilation adds gfortran (~80 MB build dep, squashed); binary ~2 MB at runtime | Same as above | Same as above | Medium — multi-stage build avoids gfortran in final image; binary only is ~2 MB | Very High | No |
| xfoil-python / xfoil PyPI wrapper | Partial — requires compiled Fortran extension (`.so`); platform-specific | Same as XFoil | Same as XFoil (wraps Fortran lib) | Medium — ships pre-built wheels for amd64; arm64 Cloud Run may require source build | High | No |
| pyxfoil (subprocess wrapper) | Same as XFoil binary | Same as XFoil | Same as XFoil | Same as XFoil binary | High | No |
| Inviscid panel method (pure Python) | Full | Low — no viscosity, no stall, Cd ≈ 0 | Excellent — <1ms | None | Low | No — Cd=0 is misleading |
| Thin airfoil theory (analytical) | Full | Very Low — Cl_α = 2π only; no Cd, no stall | Instantaneous | None | Trivial | No — informational only |
| OpenFOAM RANS | Not practical — >2 GB image, separate mesh container | Very High (reference) | Very Slow — hours per case | Extreme — separate container | Extreme | No |
| Client-side WASM XFoil | Not viable — no confirmed stable WASM port exists as of 2026-02 | Same as XFoil if it existed | Unknown | None (client-side) | Extreme | No |

**Note on xfoil-python (PyPI):** The `xfoil` package (v1.1.1, daniel-de-vries) presents XFoil as a compiled Python extension module (Fortran compiled to a `.so`). It ships pre-built wheels for Linux x86_64, making it installable without a Fortran compiler. However: (a) it is not actively maintained, (b) it strips XFoil's PGPLOT graphics layer, which actually helps for headless use, but (c) its API is minimal and it has no arm64 wheels (Cloud Run defaults to amd64 but this is worth noting). It is a viable but inferior alternative to neuralfoil — slower and less maintained. Not recommended.

### 2.2 Cloud Run Architecture Compatibility

**Subprocess execution:** Cloud Run allows subprocess execution of compiled binaries. The container runtime contract requires only that binaries be compiled for 64-bit Linux. A GitHub project (`fortran-cloudrun`) demonstrates Fortran 90 running on Cloud Run. XFoil subprocess is therefore not blocked by Cloud Run's execution model. However, subprocess automation of XFoil via stdin/stdout is non-trivial (see below).

**Display requirements — the critical XFoil constraint:** XFoil's interactive interface and its PGPLOT graphics library require X11 when plotting is enabled. The `apt-get install xfoil` package on Ubuntu/Debian includes PGPLOT with X11 linkage. In headless batch operation (no `PLOP` commands, redirected output), XFoil can run without a connected X11 display **if the binary is built without PGPLOT or if PGPLOT is compiled with a null driver**. The Ubuntu/Debian prebuilt `xfoil` package links PGPLOT with X11, meaning `DISPLAY` must be set. The workaround is either: (a) compile XFoil from source with PGPLOT disabled, or (b) install `Xvfb` (X Virtual Framebuffer) and set `DISPLAY=:99`. Both add Docker complexity. This is the main practical reason to avoid XFoil subprocess for this feature.

**Ephemeral filesystem:** Cloud Run containers have a writable ephemeral filesystem (tmpfs) at `/tmp`. XFoil writes polar output files (e.g., `polar.txt`) to disk. Writing to `/tmp` works in Cloud Run — the existing CHENG export pattern already uses `/data/tmp/` with similar semantics. No constraint here for XFoil subprocess if it were pursued.

**Docker image size — current baseline:** CHENG uses `python:3.11-slim` + CadQuery/OCP + FastAPI. CadQuery/OCP is the dominant dependency; the runtime image is estimated at 800 MB–1.2 GB (OCP wheels are approximately 600–800 MB). Adding `neuralfoil` + `aerosandbox` (without full optional deps) adds approximately 30–45 MB — a marginal increase. For reference: `numpy` is already present (required by CadQuery); `scipy` (required by aerosandbox) is approximately 30 MB installed; the neuralfoil package itself and aerosandbox core are approximately 15 MB combined. XFoil binary plus PGPLOT/Xvfb would add another 30–60 MB on top, a comparable but less clean addition.

**Cold start penalty:** Cloud Run cold starts are already managed by CHENG's `useColdStart` hook. neuralfoil's model weights are loaded on first import (a ~100–200ms one-time cost per container instance). This occurs during server startup, not on the first user request — negligible cold start impact if `import neuralfoil` is placed at module level in `backend/airfoil_analysis.py`. XFoil subprocess would require no import overhead but adds per-request process spawn latency (~200–500ms for process startup even before computation).

**Concurrency model:** Multiple simultaneous polar requests are a realistic scenario (one per connected browser tab). neuralfoil is pure Python and therefore GIL-bound. However, at <50ms per polar, even 10 simultaneous requests complete in under 500ms total on a single thread. For higher concurrency, polars can be run via `anyio.to_thread.run_sync()` following the exact same pattern used for CadQuery in `backend/routes/websocket.py`. The existing `CapacityLimiter(4)` for CadQuery applies to the thread pool; polar analysis is fast enough that a separate limiter is not required — it can share the pool or run unthrottled on the async event loop given its speed.

**CHENG_MODE compatibility:** neuralfoil is fully compatible with both `local` and `cloud` modes. There are no file system write operations in the polar computation path (only in-memory arrays). The caching strategy (LRU dict) works identically in both modes.

### 2.3 Feasibility Verdict

**FEASIBLE — neuralfoil path has no blocking constraints.**

Using neuralfoil: all Cloud Run constraints are met, no X11 dependency, no subprocess complexity, compatible with both `local` and `cloud` CHENG modes. Implementation follows existing CHENG patterns directly.

Using XFoil subprocess: feasible in principle (Cloud Run allows binary execution, /tmp is writable), but requires resolving the X11/PGPLOT display dependency, adds subprocess automation complexity (PTY or pexpect required, not plain stdin/stdout for some XFoil builds), and introduces convergence failure handling. This path is **conditionally feasible** and explicitly deferred to Phase 5.

---

## 3. Recommended Approach: neuralfoil

### 3.1 What Is neuralfoil

neuralfoil (github.com/peterdsharpe/NeuralFoil, PyPI: `neuralfoil`) is a neural-network-based surrogate of XFoil, created by Peter Sharpe at MIT. It was trained on over 50,000 XFoil polars spanning Reynolds numbers from 10,000 to 100,000,000, angles of attack from −25° to +25°, Mach numbers from 0 to 0.9, Ncrit values from 0 to 24, and approximately 1,500 airfoil geometries including NACA 4-series, Eppler, Selig, and arbitrary user-defined profiles. The neural network is trained in PyTorch but executed at runtime in pure NumPy, making it a zero-binary, zero-PyTorch deployment. Inputs are airfoil coordinates (in Selig .dat format — directly compatible with CHENG's existing `load_airfoil()` output), plus Re, α, Mach, Ncrit. Outputs match XFoil's outputs: Cl, Cd, Cm, Cdp, transition locations (xtr_top, xtr_bot), and an `analysis_confidence` scalar that flags low-confidence predictions (useful for very low Re or extreme AoA). A peer-reviewed paper was published in 2025 (arxiv 2503.16323, "NeuralFoil: An Airfoil Aerodynamics Analysis Tool Using Physics-Informed Machine Learning").

### 3.2 Why neuralfoil Over XFoil Subprocess

- **No binary management:** `pip install neuralfoil` is the complete installation. No Fortran compiler, no apt package, no architecture-specific binary. Works identically on amd64 and arm64.
- **No display dependency:** XFoil's PGPLOT layer requires X11 or Xvfb in the Debian package. neuralfoil has no display dependency whatsoever.
- **No subprocess complexity:** XFoil batch automation requires either pexpect (PTY-based) or careful stdin/stdout management with per-prompt timing. The CHENG Dockerfile uses `python:3.11-slim` with no PTY tooling installed. neuralfoil is a direct Python function call.
- **No convergence failures:** XFoil fails to converge near stall (particularly below Re = 100,000) and returns no result for those α points. neuralfoil always returns a value and uses `analysis_confidence` to signal uncertainty instead of crashing.
- **Speed compatible with WebSocket update loop:** At <50ms per polar, neuralfoil can run synchronously or in a thread alongside the existing CadQuery geometry generation without blocking the event loop.
- **Cache-friendly:** neuralfoil is a pure function. Caching by (airfoil_name, Re_rounded, Ncrit) gives 100% hit rate for the same design with unchanged airfoil/speed. `functools.lru_cache` applies trivially.
- **Pure-Python GIL compatibility:** No foreign threads, no subprocess management, no signal handling required. Fully compatible with anyio's task group model.
- **License:** neuralfoil is MIT licensed. XFoil is GPL licensed — including it in a Docker image that is redistributed requires the entire image to be GPL-compatible, which is a legal consideration for any future commercial deployment. This is not a current CHENG constraint but is worth noting.
- **Actively maintained:** Latest release in 2025; AeroSandbox 4.x integration adds NeuralFoil 0.3.0 with caching of neural network parameters for additional speed.

### 3.3 Known Limitations of neuralfoil vs. XFoil

- **Accuracy ceiling is XFoil's accuracy:** neuralfoil learned from XFoil — it cannot be more accurate than XFoil. XFoil itself underpredicts Cd at Re < 80,000 and overpredicts Cl_max near stall. These XFoil biases propagate into neuralfoil.
- **Post-stall behavior:** Both XFoil and neuralfoil produce unreliable results above the stall angle. neuralfoil reports `analysis_confidence` < 0.5 in this regime, which CHENG should use to clip display to the attached-flow range (α ≤ α_stall).
- **Very thin airfoils:** Flat-plate profiles (t/c < 3%) and very thin symmetric profiles at extreme α may have reduced accuracy. CHENG's flat-plate is analytically generated at 3% — flag these analyses as approximate.
- **No Cp distribution in standalone mode:** The PyPI `neuralfoil` package does not expose surface Cp distributions in its core API (it does within AeroSandbox). Cp charts (a Priority 3 feature per the CFD expert) would require importing via AeroSandbox rather than standalone neuralfoil. This is acceptable — Cp charts are optional.
- **No boundary layer trip forcing:** XFoil allows forcing transition at a specified chordwise location (`VPAR XT`). neuralfoil uses only Ncrit for transition control. For CHENG's use case (free transition, outdoor flight), this is not a limitation.
- **Training data extrapolation:** Very unusual airfoil geometries not well-represented in the 1,500-airfoil training set may have degraded accuracy. All CHENG airfoils (NACA 4-series, Clark-Y, Eppler, Selig, AG-25) are canonical and well within the training distribution.

### 3.4 Fallback Strategy

If neuralfoil proves insufficient (e.g., a future user base requests higher accuracy or Cp distributions for specific airfoil design workflows), the upgrade path is:

1. **Phase 5 — XFoil subprocess:** Build XFoil from source in a multi-stage Dockerfile, stripping PGPLOT (compile with `PGPLOT_DIR` undefined or use the PGPLOT null device). Run via `anyio.to_thread.run_sync()` with a `asyncio.timeout()` guard (10s max). Use `subprocess.Popen(stdin=PIPE, stdout=PIPE, stderr=PIPE)` — XFoil reads commands from stdin without requiring a PTY if PGPLOT is disabled. Implement a pluggable backend interface in `backend/airfoil_analysis.py` (a `PolarBackend` Protocol with `compute_polar()` method) so neuralfoil and XFoil are swappable at configuration time.
2. **aerosandbox.Airfoil.get_aero_from_xfoil():** AeroSandbox (already a dependency via neuralfoil) wraps XFoil subprocess with proper fallback handling. If XFoil is installed in the image, this provides a higher-level integration than raw subprocess.

The pluggable backend interface should be designed into Phase 1 even if only neuralfoil is implemented, so Phase 5 is a drop-in addition rather than a refactor.

---

## 4. Technical Complexity & Cost Estimate

### 4.1 Implementation Phases

| Phase | Description | Effort | Dependencies |
|---|---|---|---|
| Phase 1 | Backend: neuralfoil integration, ISA atmosphere model, polar caching, new `cruise_speed_ms` parameter (G09), scalar DerivedValues fields (cl_max, alpha_stall_deg, cl_cd_max, stall_speed_ms, cruise_cl, cruise_re, stall_margin_pct) | S — 2 days | None — neuralfoil pip install |
| Phase 2 | Backend: full polar endpoint `POST /api/analysis/polar` returning arrays (alpha, cl, cd, cm, cl_cd), tail airfoil analysis, AC-corrected stability integration | M — 3 days | Phase 1 |
| Phase 3 | Frontend: scalar metric display in StabilityPanel.tsx (Cl_max, stall speed, cruise L/D, stall margin callouts, "via neuralfoil" attribution) | S — 1 day | Phase 1 |
| Phase 4 | Frontend: interactive polar charts (Cl vs. α, Cl/Cd vs. α, Cd vs. Cl), operating point marker, stall marker, wing vs. tail overlay, recharts integration | M — 4–5 days | Phase 2, Phase 3 |
| Phase 5 | XFoil subprocess backend (optional): multi-stage Dockerfile, PolarBackend Protocol, subprocess management, convergence handling, PGPLOT-disabled build | L — 6–8 days | Phase 1 (pluggable interface) |

**Recommended execution order:** Phase 1 → Phase 3 → Phase 2 → Phase 4. This delivers scalar outputs to users quickly (3 days) before building the more complex chart infrastructure.

### 4.2 New Dependencies

| Package | Purpose | Installed Size | Docker Change | Notes |
|---|---|---|---|---|
| `neuralfoil` | ML polar surrogate | ~5–10 MB | `pip install neuralfoil` in pyproject.toml | Requires aerosandbox |
| `aerosandbox` | neuralfoil dependency; ISA atmosphere utilities also available | ~20–35 MB | Transitive via neuralfoil | NumPy already present; SciPy is the large new dep (~30 MB) |
| `recharts` (frontend) | Polar charts | ~180 KB gzipped | `pnpm add recharts` | MIT license; React-native; no D3 peer dep required |

**Total new Docker image impact:** approximately 30–45 MB for the neuralfoil path. Negligible relative to the ~800 MB+ OCP/CadQuery baseline.

**SciPy note:** aerosandbox depends on SciPy for optimization and interpolation. If SciPy is already present in the venv (check `uv lock`), the additional size is zero. If not, it adds ~30 MB — still acceptable.

### 4.3 Backend File Changes

| File | Change Type | Description |
|---|---|---|
| `backend/airfoil_analysis.py` | **New** | Core polar module. `AirfoilAnalysisRequest` model, `AirfoilPolar` result model, `compute_airfoil_polar()` function (neuralfoil backend), `compute_reynolds()` and `compute_mach()` ISA utilities, `_get_airfoil_coords()` adapter for CHENG's `load_airfoil()`, LRU polar cache keyed by (airfoil_name, Re_rounded_1k, ncrit). Defines `PolarBackend` Protocol for Phase 5 extensibility. |
| `backend/models.py` | **Modified** | Add `cruise_speed_ms: float = Field(default=12.0, ge=5.0, le=40.0)` to `AircraftDesign`. Add 7 new fields to `DerivedValues` (see Section 5.3). |
| `backend/geometry/engine.py` | **Modified** | Call `compute_airfoil_polar()` from `compute_derived_values()` when `cruise_speed_ms` > 0. Populate new DerivedValues scalar fields from polar result. Add ISA-level Re display string. |
| `backend/stability.py` | **Modified** (Phase 2 only) | Accept optional `wing_ac_frac` parameter from polar. Replace hardcoded `0.25` with actual aerodynamic center when polar data is available (`ac_frac = -Cm_slope / Cl_slope` from linear fit). Falls back to 0.25 if no polar data. |
| `backend/validation.py` | **Modified** | Add V36 (cruise Cl too high), V37 (stall speed too high), V38 (poor L/D at cruise), V39 (low-Re accuracy warning for tail at Re < 50,000). |
| `backend/routes/analysis.py` | **New** | `POST /api/analysis/polar` REST endpoint. Accepts `AirfoilAnalysisRequest`, returns `AirfoilPolar` with full arrays. Called on demand by the frontend chart component (not embedded in every WebSocket frame). |
| `backend/main.py` | **Modified** | Register new `analysis` router: `app.include_router(analysis.router)`. |
| `pyproject.toml` | **Modified** | Add `neuralfoil>=0.1.3` and `aerosandbox>=4.2.4,<4.3.0` (pinned minor version per neuralfoil's own setup.py constraint) to `[project.dependencies]`. |
| `uv.lock` | **Regenerated** | Run `uv lock` after pyproject.toml change. |

### 4.4 Frontend File Changes

| File | Change Type | Description |
|---|---|---|
| `frontend/src/components/panels/StabilityPanel.tsx` | **Modified** | Add new "Airfoil Performance" section below the existing stability gauges. Display Cl_max, stall speed, cruise L/D, stall margin as `DerivedField` components. Add "Toggle Polar Charts" button (triggers `StabilityOverlay` or inline chart section). Add "Computed via neuralfoil" attribution link in a `<p className="text-xs text-zinc-500">` footer. |
| `frontend/src/components/stability/AirfoilScalars.tsx` | **New** | Compact callout grid for the 4 key scalar outputs: Cl_max, Stall Speed, Cruise L/D, Stall Margin %. Follows `DerivedField` component pattern. |
| `frontend/src/components/stability/PolarChart.tsx` | **New** (Phase 4) | recharts `ComposedChart` with two line series (Cl vs. α and Cl/Cd vs. α on a secondary Y axis) plus a `ReferenceLine` at cruise α (operating point) and a `ReferenceDot` at α_stall. Responsive via `ResponsiveContainer`. |
| `frontend/src/components/stability/DragPolarChart.tsx` | **New** (Phase 4, optional) | recharts `LineChart` for the Cd vs. Cl (drag polar / "bucket") view. |
| `frontend/src/hooks/useAirfoilPolar.ts` | **New** (Phase 4) | Custom hook. On user request (button click), fetches `POST /api/analysis/polar` with current design parameters. Returns `{polar, loading, error}`. Caches response by (airfoil, Re, Ncrit) in React state. Does not fetch automatically on every design change — only on explicit user request. |
| `frontend/src/store/designStore.ts` | **Modified** | Add new camelCase derived fields to the `DerivedValues` TypeScript type: `clMax`, `alphaStallDeg`, `clCdMax`, `stallSpeedMs`, `cruiseCl`, `cruiseRe`, `stallMarginPct`. |
| `frontend/src/components/panels/GlobalPanel.tsx` | **Modified** | Add `cruise_speed_ms` (G09) slider. Range 5–40 m/s, default 12, step 0.5. Display computed Re next to slider as a `DerivedField` or inline annotation: `Re ≈ {cruiseRe.toLocaleString()}`. |

### 4.5 Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| aerosandbox/SciPy adds >50 MB to Docker image, triggering Cloud Run cold start regression | Low | Medium | Measure image size delta before and after; if SciPy is already present in the venv (likely via cadquery transitive deps), impact is zero. Use `pip show scipy` in the build to verify. |
| neuralfoil accuracy at Re < 50,000 (glider tail) is insufficient for user trust | Medium | Low | neuralfoil reports `analysis_confidence` per α point; use this to show uncertainty bands or suppress the polar for very-low-Re surfaces. Add V39 warning. |
| aerosandbox version pinning conflict with future cadquery updates | Low | Medium | Pin `aerosandbox>=4.2.4,<5.0` in pyproject.toml and audit on each cadquery version bump. |
| recharts bundle size impacts frontend load time | Low | Low | recharts is ~450 KB minified, ~180 KB gzipped. CHENG already ships Three.js (~600 KB gzipped). Impact is acceptable. Use dynamic import (`React.lazy`) for the chart component so it only loads when the user opens the polar view. |
| XFoil Phase 5 PGPLOT display issue blocks subprocess in Cloud Run | High (if attempted) | Medium | Mitigated by: (a) building XFoil without PGPLOT in Dockerfile; (b) using `DISPLAY=` environment variable (empty, not unset) to prevent PGPLOT from attempting to open a display; (c) using Xvfb as last resort. This risk does not affect Phase 1–4. |
| Operating point computation incorrect for multi-section wings (different chords per panel) | Medium | Low | Use MAC (mean aerodynamic chord) for operating Cl computation, which is already computed by engine.py. Document that the operating point is a whole-wing average. Per-panel analysis is Phase 4/optional. |
| neuralfoil import time adds cold start latency | Low | Low | Import at module level in `backend/airfoil_analysis.py` so it loads once at startup, not per-request. Estimate: 100–300ms one-time import (model weights). |

---

## 5. Requirements

### 5.1 New Aircraft Parameter: Cruise Speed

**Parameter ID:** G09
**Name:** `cruise_speed_ms`
**Description:** Estimated cruise airspeed used to compute Reynolds number, operating lift coefficient, stall margin, and cruise efficiency. Does not affect geometry or weight. Used exclusively for aerodynamic performance calculations.
**Type:** `float`, range 5–40 m/s, default 12.0 m/s
**UI:** Global panel, new slider labeled "Cruise Speed". Display in both m/s and km/h (km/h = m/s × 3.6). Use existing `UnitToggle` store if applicable, or show both units inline: "12.0 m/s (43.2 km/h)".
**Validation:** No hard constraints. Add soft warning (V37) if computed stall speed exceeds cruise speed (impossible flight condition).
**Display:** Show computed Reynolds number next to slider as an annotation: `Re = {cruiseRe.toLocaleString()} (MAC, sea level)`. This makes the abstract parameter concrete for users who know what Re means and harmless for those who don't.
**Persistence:** Stored in `AircraftDesign` JSON alongside all other parameters. Included in preset definitions for all 6 built-in presets (Trainer: 12 m/s, Sport: 15 m/s, Aerobatic: 22 m/s, Glider: 8 m/s, FlyingWing: 14 m/s, Scale: 15 m/s).
**Derivation fallback:** If `cruise_speed_ms` == 0 or is absent (backward compat), estimate from wing loading: `V_est = sqrt(2 × WL_kg_m2 / (1.225 × 0.5))` (assuming Cl_cruise = 0.5). Use this estimate internally but flag derived aerodynamic values as "estimated" in the UI.

### 5.2 New Polar Analysis Module: `backend/airfoil_analysis.py`

#### Input Model

```python
class AirfoilAnalysisRequest(CamelModel):
    airfoil_name: str           # e.g., "Clark-Y", "NACA-4412"
    chord_mm: float             # actual chord in mm (converted to m internally)
    airspeed_ms: float          # freestream velocity [m/s]
    altitude_m: float = 0.0    # ISA altitude [m], default sea level
    alpha_min: float = -5.0    # degrees, sweep start
    alpha_max: float = 20.0    # degrees, sweep end
    alpha_step: float = 0.5    # degrees, sweep step
    ncrit: float = 9.0          # transition amplification factor
```

#### Output Model

```python
class AirfoilPolar(CamelModel):
    # Per-alpha arrays (length = (alpha_max - alpha_min) / alpha_step + 1)
    alpha: list[float]          # angle of attack [deg]
    cl: list[float]             # section lift coefficient
    cd: list[float]             # section drag coefficient (viscous + pressure)
    cm: list[float]             # section pitching moment about quarter-chord
    cl_cd: list[float]          # L/D ratio (computed from cl/cd, masked where cd=0)
    confidence: list[float]     # neuralfoil analysis_confidence per alpha [0–1]

    # Scalar summaries (derived from arrays)
    cl_max: float               # peak Cl in the sweep
    alpha_stall_deg: float      # alpha at Cl_max
    cl_cd_max: float            # peak Cl/Cd in the sweep
    alpha_best_glide_deg: float # alpha at (Cl/Cd)_max
    cd_min: float               # minimum Cd in the sweep
    cl_at_zero_alpha: float     # Cl at alpha=0 (camber contribution)

    # Operating point (at cruise condition)
    cruise_cl: float            # Cl at cruise speed and aircraft weight
    cruise_cd: float            # Cd at cruise Cl (interpolated from polar)
    cruise_l_d: float           # L/D at cruise
    cruise_re: float            # Reynolds number at cruise (informational)
    cruise_alpha_deg: float     # angle of attack at cruise Cl (interpolated)

    # Flight performance derived values
    stall_speed_ms: float       # V_stall = sqrt(2W / (rho * S * Cl_max))
    stall_margin_pct: float     # (Cl_max - cruise_cl) / Cl_max * 100
    stall_margin_delta_cl: float # Cl_max - cruise_cl (absolute)

    # Coordinate system (for AC correction to stability.py)
    aerodynamic_center_frac: float  # AC as fraction of chord (from Cm slope fit)

    # Metadata
    airfoil_name: str
    reynolds_number: float
    mach_number: float
    ncrit: float
    backend: str = "neuralfoil"  # "neuralfoil" | "xfoil" (Phase 5)
```

#### Core Function Signature

```python
def compute_airfoil_polar(
    design: AircraftDesign,
    chord_mm: float,            # which chord to use (root, tip, MAC, h_stab)
    surface: str = "wing",      # "wing" | "tail" (for logging/caching key)
) -> AirfoilPolar:
    """Compute airfoil polar for one surface of the aircraft.

    Reads airfoil name from design.wing_airfoil (or design.tail_airfoil for tail).
    Uses design.cruise_speed_ms for Re computation.
    Uses existing CHENG .dat files via load_airfoil().
    Caches by (airfoil_name, Re_rounded_1000, ncrit).
    """
```

#### ISA Atmosphere Helper

```python
def compute_reynolds(chord_m: float, airspeed_ms: float, altitude_m: float = 0.0) -> float:
    """International Standard Atmosphere, valid 0–11,000 m (troposphere)."""
    T = 288.15 - 0.0065 * altitude_m          # Temperature [K]
    rho = 1.225 * (T / 288.15) ** 4.256       # Density [kg/m³]
    mu = 1.716e-5 * (T / 273.15) ** 1.5 * (383.55 / (T + 110.4))  # Sutherland
    nu = mu / rho                              # Kinematic viscosity [m²/s]
    return (airspeed_ms * chord_m) / nu

def compute_mach(airspeed_ms: float, altitude_m: float = 0.0) -> float:
    """Speed of sound via ISA temperature profile."""
    T = 288.15 - 0.0065 * altitude_m
    return airspeed_ms / (1.4 * 287.058 * T) ** 0.5
```

#### Caching Strategy

```python
import functools

@functools.lru_cache(maxsize=128)
def _cached_polar(
    airfoil_name: str,
    re_rounded: int,         # Re rounded to nearest 1000 for cache efficiency
    ncrit: float,
    alpha_min: float,
    alpha_max: float,
    alpha_step: float,
    mach: float,
) -> tuple:
    """Inner cached function returning raw neuralfoil arrays."""
    ...
```

Cache key rationale: `re_rounded = round(re, -3)` (to nearest 1000) avoids excessive cache misses when chord varies by a millimeter. Mach is included but is nearly constant for RC (<0.12 at 40 m/s). Expected cache size: 12 airfoils × 5 common Re values × 1 Ncrit = 60 entries — well within `maxsize=128`.

### 5.3 New Derived Values Fields

The following fields are added to `DerivedValues` in `backend/models.py`. All follow the existing snake_case convention (serialized as camelCase to the frontend via `alias_generator=to_camel`).

```python
# ── Airfoil Polar Derived Values (Phase 1+) ───────────────────────────────────
# Computed by backend/airfoil_analysis.py, populated in engine.compute_derived_values().
# All default to 0.0 for backward compatibility with designs that predate G09.

# Wing airfoil polar scalars (at cruise Re, wing MAC chord)
cl_max: float = 0.0             # Maximum lift coefficient (wing airfoil at cruise Re)
alpha_stall_deg: float = 0.0    # Stall angle of attack [degrees]
cl_cd_max: float = 0.0          # Peak lift-to-drag ratio
alpha_best_glide_deg: float = 0.0  # Angle of attack at (Cl/Cd)_max
cd_min: float = 0.0             # Minimum profile drag coefficient
cruise_cl: float = 0.0          # Operating Cl at cruise speed + current weight + wing area
cruise_cd: float = 0.0          # Cd at cruise condition (interpolated from polar)
cruise_l_d: float = 0.0         # L/D ratio at cruise operating point
cruise_re: float = 0.0          # Reynolds number at MAC chord, cruise speed, sea level
cruise_alpha_deg: float = 0.0   # Angle of attack at cruise condition

# Flight performance
stall_speed_ms: float = 0.0     # V_stall = sqrt(2W / (rho * S * Cl_max)) [m/s]
stall_margin_pct: float = 0.0   # (Cl_max - cruise_cl) / Cl_max * 100 [%]
stall_margin_delta_cl: float = 0.0  # Cl_max - cruise_cl [dimensionless]

# Tail airfoil (Phase 2+)
tail_cl_max: float = 0.0        # Tail airfoil Cl_max at h-stab chord Re
tail_cruise_re: float = 0.0     # Reynolds number at h_stab_chord, cruise speed
```

**Design note on `tail_cl_max`:** CHENG's current tail airfoils are all symmetric (NACA-0006, -0009, -0012, Flat-Plate). Symmetric airfoils at zero incidence have Cl = 0 by definition. `tail_cl_max` is the maximum Cl magnitude the tail can generate, which informs whether the tail has sufficient authority at the operating Re. For glider tails at Re ≈ 40,000, thin symmetric profiles (NACA-0006) can have reduced Cl_max — useful information for the user.

### 5.4 On-Demand Polar Endpoint

**Recommendation: Option (b) — separate REST endpoint `POST /api/analysis/polar`, called on demand.**

Rationale:

- **Data size:** A full polar (51 α points × 6 arrays) serialized to JSON is approximately 4–6 KB. Embedding this in every WebSocket binary frame would add 4–8 KB per update, on top of the existing mesh binary. The WebSocket frame is already potentially large (mesh vertices + normals + faces). For a design with many geometry changes per second (slider drag), this adds measurable overhead even if the polar data has not changed.
- **Computation cost:** neuralfoil at 50ms is fast but not negligible when the user is rapidly sliding wing_chord or wing_span. The operating-point scalar values (cruise_cl, stall_speed_ms, stall_margin_pct) can be embedded in the WebSocket trailer as derived values — these are cheap to compute from a cached polar. The full polar arrays (for charts) are only needed when the user explicitly opens the polar chart view.
- **UX:** The polar chart is an on-demand "deep dive" tool, not a continuously updating display. A "Run Polar Analysis" button is the correct UX pattern — it makes the computation cost explicit and does not surprise users with latency during normal parameter exploration.
- **Caching:** The REST endpoint response can include `Cache-Control: no-store` (polars are deterministic, but design parameters change frequently; server-side LRU cache is sufficient). The frontend hook `useAirfoilPolar.ts` caches the last result by (airfoil, Re, Ncrit) in React state and re-fetches only when those values change.

**Scalar derived values (cl_max, stall_speed_ms, etc.) remain in the WebSocket trailer** — they are computed from the cached polar result at negligible cost and provide immediate feedback as the user adjusts cruise speed or wing area. Only the full alpha/cl/cd arrays are gated behind the REST endpoint.

**Endpoint spec:**

```
POST /api/analysis/polar
Content-Type: application/json
Body: AirfoilAnalysisRequest (JSON)

Response 200: AirfoilPolar (JSON)
Response 422: Validation error (invalid airfoil name, out-of-range Re)
Response 500: Computation error (neuralfoil failure — should not occur in normal operation)
```

### 5.5 Validation Rules

Continuing from V35 (the last existing validation code defined in `backend/validation.py`):

**V36 — Cruise Cl too high (stall margin insufficient)**
- Condition: `cruise_cl > 0.85 * cl_max` (less than 15% stall margin)
- Level: `warn`
- Message: "Low stall margin: aircraft is operating at {cruise_cl:.2f} Cl (Cl_max = {cl_max:.2f}), leaving only {stall_margin_pct:.0f}% margin above stall. Increase cruise speed, reduce weight, or increase wing area."
- Fields: `["cruise_speed_ms", "wing_span", "wing_chord"]`
- Only triggers when `cl_max > 0` and `cruise_cl > 0` (polar has been computed)

**V37 — Stall speed too high for configuration**
- Condition: `stall_speed_ms > 15` and `fuselage_preset == "Conventional"` and estimated wing loading suggests a trainer/sport class design
- Level: `warn`
- Message: "Estimated stall speed of {stall_speed_ms:.1f} m/s is high for this configuration. Consider reducing wing loading or increasing Cl_max by selecting a higher-camber airfoil."
- Fields: `["wing_span", "wing_chord", "wing_airfoil"]`
- Only triggers when `stall_speed_ms > 0`

**V38 — Poor cruise efficiency**
- Condition: `cruise_l_d < 5.0` (highly draggy configuration at cruise)
- Level: `warn`
- Message: "Cruise L/D of {cruise_l_d:.1f}:1 is low. This aircraft will have short flight endurance. Consider increasing aspect ratio, reducing fuselage drag (use Conventional preset), or selecting a lower-drag airfoil (Eppler-387, Selig-1223)."
- Fields: `["wing_span", "wing_chord", "wing_airfoil", "cruise_speed_ms"]`
- Only triggers when `cruise_l_d > 0`

**V39 — Low Reynolds number polar accuracy warning**
- Condition: `tail_cruise_re < 50000` (tail surface in marginal XFoil accuracy zone)
- Level: `warn`
- Message: "Tail surface Reynolds number of {tail_cruise_re:.0f} is below 50,000. Airfoil polar accuracy is reduced at this Re — treat tail aerodynamic values as approximate."
- Fields: `["h_stab_chord", "cruise_speed_ms"]`
- Only triggers when `tail_cruise_re > 0`

**Implementation note:** All four new codes must be added to `backend/validation.py` following the existing pattern (one function per code, called from `compute_warnings()`). Never add validation logic to `engine.py` — the CLAUDE.md convention is explicit on this.

### 5.6 UI Requirements

#### Stability Panel Changes (StabilityPanel.tsx)

Add a new "Airfoil Performance" section between the existing stability gauges and the "Raw Values" `<details>` element.

**Structure:**

```tsx
{/* New section: Airfoil Performance scalars */}
{derived.clMax > 0 && (
  <section aria-label="Airfoil Performance">
    <h4 className="text-xs font-medium text-zinc-300 mb-2">Airfoil Performance</h4>
    <AirfoilScalars derived={derived} />
    {/* Attribution footer */}
    <p className="text-xs text-zinc-600 mt-1">
      Computed via <span className="text-zinc-500">neuralfoil</span>
      {' '}(2D section, sea level, Ncrit = 9)
    </p>
    {/* Polar chart trigger */}
    <button
      className="mt-2 text-xs text-blue-400 hover:text-blue-300 underline"
      onClick={() => setShowPolarChart(true)}
    >
      View polar charts →
    </button>
  </section>
)}
```

The `derived.clMax > 0` guard ensures the section is hidden until `cruise_speed_ms` is set and polar computation has run.

**AirfoilScalars layout:** 2×2 grid of callout cards:

| Card | Value | Unit | Color coding |
|---|---|---|---|
| Cl_max | `derived.clMax.toFixed(2)` | — | Neutral (zinc-300) |
| Stall Speed | `derived.stallSpeedMs.toFixed(1)` | m/s | Green if <12, yellow if 12–18, red if >18 |
| Cruise L/D | `derived.cruiseLd.toFixed(1)` | :1 | Green if >10, yellow if 5–10, red if <5 |
| Stall Margin | `derived.stallMarginPct.toFixed(0)` | % | Green if >20%, yellow if 10–20%, red if <10% |

#### Polar Chart Component (PolarChart.tsx)

**Chart type:** `recharts` `ComposedChart` with:
- Primary Y axis: Cl (left)
- Secondary Y axis: Cl/Cd (right)
- X axis: α in degrees
- Line 1: Cl vs. α (blue, `dataKey="cl"`, `yAxisId="left"`)
- Line 2: Cl/Cd vs. α (orange, `dataKey="clCd"`, `yAxisId="right"`)
- `ReferenceLine` at `cruise_alpha_deg` (vertical dashed line, labeled "Cruise")
- `ReferenceDot` at (alpha_stall_deg, cl_max) labeled "Stall"
- Optional: `ReferenceLine` at y=0 on left axis

**Second chart:** `LineChart` for Cd vs. Cl (drag polar):
- X axis: Cl
- Y axis: Cd
- `ReferenceDot` at (cruise_cl, cruise_cd) labeled "Cruise"
- `ReferenceDot` at (cl_max, Cd_at_stall) labeled "Stall"

**Wing vs. tail overlay (Phase 4):** Add a second `Line` in each chart using tail polar data (fetched via a second `useAirfoilPolar` call for the tail airfoil + h_stab_chord). Use a distinct color (green) and dashed stroke for the tail.

**Axis ranges:**
- α: −5° to +22° (fixed, clipped to sweep range)
- Cl: auto-scaled ±10% from data range, minimum range 0–1.5
- Cl/Cd: auto-scaled, minimum range 0–20
- Cd: auto-scaled from data, minimum range 0–0.05

**Responsive sizing:** Wrap in `<ResponsiveContainer width="100%" height={260}>`. The polar chart panel floats in a `<div>` below the scalar section — it does not need a modal/overlay (the existing `StabilityOverlay` is for the full stability panel; polar charts are inline).

**Chart placement:** Inline within StabilityPanel, below `AirfoilScalars`, collapsed by default (hidden until user clicks "View polar charts"). Use a simple `useState` toggle rather than a modal. This avoids focus management complexity and keeps context visible.

#### Flight Condition Inputs

These are **not exposed as sliders** in the main flow. The polar is computed at:
- Altitude: sea level (0 m) — fixed, not user-configurable in Phase 1–4
- Ncrit: 9.0 — fixed default, not user-configurable in Phase 1–4

**Phase 4 advanced controls** (hidden by default, accessible via a "⚙ Advanced" disclosure toggle within the polar chart section):
- Altitude: `<input type="range" min="0" max="3000" step="100" />` labeled "Altitude (m) — affects air density and Re". Show computed Re next to input.
- Ncrit: `<input type="range" min="3" max="14" step="1" />` labeled "Turbulence factor (Ncrit)". Tooltip explaining: "Higher = cleaner air. RC outdoor flying: 9–11. Prop wash: 5–7."

These advanced inputs only affect the polar REST endpoint call, not the WebSocket-embedded scalar values (which always use altitude=0, Ncrit=9 for consistency and performance).

### 5.7 Airfoil Coordinate Sources

For each CHENG airfoil type, coordinates are obtained as follows:

| Airfoil | Source | Notes |
|---|---|---|
| NACA-0006, NACA-0009, NACA-0012, NACA-2412, NACA-4412, NACA-6412 | Existing `.dat` files loaded by `load_airfoil()` | CHENG files are in Selig format; neuralfoil accepts these directly via its `Airfoil(coordinates=pts)` constructor. |
| Clark-Y | `clark_y.dat` (NACA TN-1233 tabulation, 47 coordinate pairs) | Well-validated; use directly. |
| Eppler-193, Eppler-387 | `eppler193.dat`, `eppler387.dat` (UIUC database) | Eppler-387 at 56 points is the UIUC canonical file; use directly. |
| Selig-1223 | `selig1223.dat` (UIUC database, Michael Selig) | Authoritative source; use directly. |
| AG-25 | `ag25.dat` (UIUC database, Mark Drela DLG design) | Use directly. |
| Flat-Plate | `generate_flat_plate()` — programmatic 3% diamond | neuralfoil/XFoil analysis of a flat plate is physically meaningful only in limited cases. Flag all Flat-Plate polar results with a disclaimer: "Flat plate analysis is approximate; results are not valid near stall." Show `confidence=0` for the entire polar. |

**Implementation:** `backend/airfoil_analysis.py` imports `load_airfoil` from `backend.geometry.airfoil` and calls it to get `list[tuple[float,float]]`. This list is converted to a `numpy.ndarray` of shape `(N, 2)` and passed to `neuralfoil.get_aero_from_airfoil_coordinates(coordinates=coords_array, ...)`. No additional coordinate generation library is needed.

### 5.8 Performance Requirements

| Metric | Requirement | Expected (neuralfoil) |
|---|---|---|
| Single polar computation (51 α points) | < 200ms first call; < 5ms cached | ~30–50ms first call; <1ms cached |
| Full polar for both wing + tail surfaces | < 400ms first call | ~60–100ms (two uncached polars) |
| Concurrent polars (5 simultaneous users) | < 2s each | ~50ms each; effectively non-blocking |
| Scalar derived values (embedded in WebSocket trailer) | < 50ms additional latency | <5ms (uses cached polar; only ISA + Cl formula evaluation) |
| Cold start import overhead | < 500ms | ~100–300ms (neuralfoil model weight loading) |
| REST endpoint response time `POST /api/analysis/polar` | < 500ms | ~50ms uncached, <5ms cached |

---

## 6. Out of Scope (Explicitly Excluded)

The following are explicitly **not** included in this feature:

- **3D lifting-line or vortex-lattice analysis** (whole-aircraft polars, spanwise lift distribution, induced drag) — would require a separate solver (OpenVSP, AVL, or custom VLM). This is a separate future feature.
- **OpenFOAM or RANS CFD** — vastly over-engineered for CHENG's user base; Docker image impact alone (>2 GB) makes it infeasible.
- **Aeroelastic effects** — wing bending/torsion coupling with aerodynamic loads. RC aircraft structures are stiff relative to aerodynamic loads at these speeds; aeroelasticity is not relevant.
- **Propeller-airfoil interaction** — modeling the turbulent prop wash effect on the wing boundary layer would require coupling the propulsion model with the aerodynamics. Not in scope.
- **High-speed or transonic effects** — all CHENG aircraft fly at Mach < 0.15. neuralfoil handles this correctly (Mach is an input), but transonic modeling specifically (Mach > 0.3) is not a CHENG use case.
- **Boundary layer transition trip forcing** — forcing transition at a specific chordwise location (`VPAR XT` in XFoil terminology). Free transition (Ncrit-based) is correct for outdoor RC flight. Trip forcing is a wind tunnel calibration tool only.
- **Multi-element airfoils (flaps/slots)** — CHENG's control surfaces are hinge-cut trailing edge flaps without aerodynamic gap modeling. Multi-element polar analysis would require a separate panel method.
- **Airfoil inverse design** — designing an airfoil to meet a target polar. This is a separate design workflow.
- **3D wing polar corrections** — span efficiency, induced drag correction (CDi = CL²/(π × AR × e)), Oswald factor. These can be computed analytically from existing derived values without a new module. Considered for Phase 4 "Quick Stats" display if desired.
- **Per-section polar analysis for multi-section wings** — analyzing each of up to 4 wing panels at its local Re independently. This is a natural Phase 4 extension but adds complexity (up to 4 neuralfoil calls + 4 chart overlays). Deferred to a follow-on issue.

---

## 7. Acceptance Criteria

The following criteria must be met for the feature to be considered complete. Each is independently testable.

**Phase 1 — Backend scalar outputs:**

- [ ] `pip install neuralfoil` (or `uv add neuralfoil`) succeeds in a fresh `python:3.11-slim` Docker environment without errors.
- [ ] `backend/airfoil_analysis.py` exists and `compute_airfoil_polar(design, chord_mm=200)` returns an `AirfoilPolar` object with no exceptions for all 12 CHENG airfoils.
- [ ] For a Trainer design at default parameters (Clark-Y, chord=200mm, cruise_speed=12 m/s): `cl_max` is in range [1.0, 2.0], `alpha_stall_deg` is in range [10°, 20°], `stall_speed_ms` is in range [5, 15] m/s.
- [ ] `AircraftDesign` model accepts `cruise_speed_ms` field. Designs without this field (saved before this feature) deserialize correctly with default value 12.0 m/s (backward compatibility).
- [ ] `DerivedValues` includes all 14 new fields. WebSocket JSON trailer includes all new fields in camelCase format.
- [ ] All 12 new fields default to 0.0 when `cruise_speed_ms == 0` or polar computation has not run.
- [ ] The scalar polar computation (embedded in WebSocket path) adds < 50ms to the existing generate-and-send latency on a cache hit; < 200ms on a cache miss.
- [ ] V36, V37, V38, V39 are present in `backend/validation.py`, tested in `tests/backend/test_validation.py`, and trigger under their specified conditions.
- [ ] V36 triggers when `cruise_cl > 0.85 * cl_max`. V37 triggers when `stall_speed_ms > 15`. V38 triggers when `cruise_l_d < 5`. V39 triggers when `tail_cruise_re < 50000`.

**Phase 2 — Polar REST endpoint:**

- [ ] `POST /api/analysis/polar` returns HTTP 200 with a valid `AirfoilPolar` JSON body for a valid `AirfoilAnalysisRequest`.
- [ ] `POST /api/analysis/polar` returns HTTP 422 for an invalid airfoil name (not in SUPPORTED_AIRFOILS).
- [ ] Full polar arrays (alpha, cl, cd, cm, cl_cd, confidence) have equal length equal to `(alpha_max - alpha_min) / alpha_step + 1`.
- [ ] Tail airfoil polar is computed separately and `tail_cl_max` / `tail_cruise_re` fields are non-zero when `h_stab_span > 0`.
- [ ] `aerodynamic_center_frac` is within [0.20, 0.35] for all standard CHENG airfoils at Re > 50,000 (validate against thin airfoil theory 25% expectation).
- [ ] When `aerodynamic_center_frac` is provided to `stability.py`, the NP calculation uses it instead of the hardcoded 0.25. The change is < 3% MAC for all CHENG presets (verify numerically).

**Phase 3 — Frontend scalar display:**

- [ ] StabilityPanel shows "Airfoil Performance" section when `derived.clMax > 0`.
- [ ] StabilityPanel hides "Airfoil Performance" section when `derived.clMax === 0` (no cruise speed set or polar not yet computed).
- [ ] Cl_max, stall speed, cruise L/D, stall margin callout cards are visible with correct values matching backend derived values.
- [ ] Stall margin card shows green/yellow/red coloring based on thresholds (>20% green, 10–20% yellow, <10% red).
- [ ] "Computed via neuralfoil" attribution is visible in the panel.
- [ ] GlobalPanel shows cruise_speed_ms slider (range 5–40 m/s, step 0.5, default 12.0).
- [ ] GlobalPanel shows Re annotation next to the slider, updating live as the slider changes.
- [ ] All new derived field names follow camelCase convention in TypeScript (`clMax`, not `cl_max`).

**Phase 4 — Polar charts:**

- [ ] Clicking "View polar charts →" renders Cl vs. α and Cl/Cd vs. α charts inline in the StabilityPanel.
- [ ] Charts show a loading state while `POST /api/analysis/polar` is in flight.
- [ ] Charts show cruise operating point marker (vertical reference line at cruise α).
- [ ] Charts show stall marker (reference dot at α_stall, Cl_max).
- [ ] Chart data is cached in React state and does not re-fetch if airfoil + Re + Ncrit have not changed.
- [ ] Charts are responsive (fill panel width at any panel size).
- [ ] Alpha points with `confidence < 0.5` are rendered with reduced opacity or a dashed line.
- [ ] If wing and tail airfoil are different, charts overlay both polars with distinct colors and a legend.

**General:**

- [ ] Backend test suite (`python -m pytest tests/backend/ -v`) passes with all new tests included. Test count increases from 782 by at least 20 new tests (polar computation, ISA formulas, V36–V39 validation, polar endpoint).
- [ ] Frontend Vitest suite (`cd frontend && pnpm test`) passes.
- [ ] Docker image builds successfully with `neuralfoil` added to `pyproject.toml`.
- [ ] The 27 existing Playwright E2E tests continue to pass.
- [ ] No regression in WebSocket frame size or latency for designs with `cruise_speed_ms == 0` (polar disabled path).

---

## 8. Appendix: Airfoil Analysis Background

### What Cl, Cd, and Cm Mean for RC Aircraft Designers

**Cl — Lift Coefficient**
The lift coefficient is a dimensionless measure of an airfoil's lift generation: `L = q × S × Cl`, where `q = ½ρV²` is dynamic pressure and `S` is wing area. For a given aircraft weight and wing area, the required Cl at cruise is fixed by `Cl_cruise = 2W / (ρV²S)`. The designer's freedom is in choosing an airfoil whose polar puts cruise in the most efficient region (near Cl/Cd_max). The lift curve Cl vs. α is linear up to stall; the slope is approximately 2π/radian (thin airfoil theory) for most RC airfoils — XFoil/neuralfoil compute the actual slope.

**Cd — Drag Coefficient**
Cd is the sum of profile drag (friction + pressure drag from the boundary layer) and, for a complete wing, induced drag (CDi = CL²/(π × AR × e)). XFoil/neuralfoil compute the **section** (2D) Cd — profile drag only. Total aircraft drag requires adding induced drag analytically: `CD_total = Cd_profile + CL²/(π × AR × e)` where AR is aspect ratio and e is Oswald efficiency (≈ 0.7–0.85 for typical RC wings). For CHENG's display, the 2D section Cd from neuralfoil is the correct input; users should understand it represents profile drag only.

**Cm — Pitching Moment Coefficient**
Cm is measured about the quarter-chord point. A negative Cm0 (at zero lift) means the airfoil has a nose-down pitching moment at zero angle of attack — typical for positive-camber airfoils (Clark-Y, NACA-4412). This must be trimmed by the horizontal tail at cruise incidence. The Cmα slope (dCm/dα) determines the aerodynamic center location: `AC_frac = 0.25 - Cmα / Clα`. For most subsonic RC airfoils, AC is close to 25% chord — the fixed assumption currently used in CHENG's `stability.py`.

### Why Reynolds Number Matters at RC Scale

Reynolds number (Re = V × c / ν) governs whether the boundary layer on an airfoil is laminar or turbulent. At RC scale (Re = 40,000–500,000), the boundary layer is predominantly laminar, making the flow highly sensitive to airfoil geometry and operating conditions. Key phenomena:

- **Laminar separation bubbles (LSBs):** At low Re, the laminar boundary layer often separates at the minimum-pressure point, transitions to turbulent in the separated shear layer, and reattaches — forming a bubble. This bubble increases effective drag and can burst (fail to reattach) at high α, causing abrupt stall. XFoil and neuralfoil explicitly model LSBs. Pure panel methods (Cd = 0 in inviscid flow) miss this entirely.
- **Laminar bucket:** Some airfoils (Eppler-387, AG-25) have a range of Cl values where the boundary layer stays laminar on both surfaces, producing a characteristic "dip" in the drag polar — low Cd in the "bucket." This is highly desirable for glider applications and appears clearly in polar charts.
- **Re sensitivity:** Cd can increase by 2–3× when Re drops from 200,000 to 60,000 (a glider at low speed). This is why glider tail surfaces (Re ≈ 40,000) need special attention — the tail may have significantly higher profile drag than the wing.

### What neuralfoil Is and Why It's Chosen

neuralfoil is a neural network trained on XFoil polars, implementing physics-informed constraints (Cl → 0 at zero camber + zero α; Cd > 0 always; Cm is Mach-dependent via Prandtl-Glauert). The neural network takes as input a Kulfan (CST) parameterization of the airfoil shape plus Re, α, Mach, and Ncrit; the CST parameters are computed internally from the input .dat coordinates. Outputs are Cl, Cd, Cm, and confidence. The key properties that make it suitable for CHENG:

1. **No binary dependencies** — pure NumPy inference, trained weights stored as package data.
2. **Smooth predictions** — neuralfoil smooths XFoil's occasionally jagged convergence behavior near transition. At Re ≈ 80,000, XFoil sometimes shows abrupt jumps in Cd as Ncrit crosses the transition threshold; neuralfoil interpolates through these smoothly.
3. **Always returns a result** — XFoil can fail to converge and return nothing near stall. neuralfoil always returns a prediction, flagging low confidence via the `analysis_confidence` output.
4. **Published accuracy** — peer-reviewed paper (arxiv 2503.16323) with reproducible validation against a held-out test set. Mean Cl error 0.006, mean Cd error 0.00022 vs. XFoil.

### How CHENG's Coordinate System Maps to XFoil Conventions

CHENG's airfoil .dat files are in **Selig format**: coordinates start at the trailing edge upper surface, trace around the upper surface to the leading edge, then along the lower surface back to the trailing edge. `x` runs from 0 (LE) to 1 (TE), `y` is the surface offset (positive = upper surface).

XFoil and neuralfoil both expect Selig format. CHENG's `load_airfoil()` returns coordinates in Selig order, already normalized to unit chord. The integration is direct: `neuralfoil.get_aero_from_airfoil_coordinates(coordinates=np.array(load_airfoil(name)), ...)`.

CHENG's CadQuery geometry uses a different convention (local XZ workplane, Y = global Z). The airfoil .dat coordinates are used **only** for aerodynamic analysis — they are not the CadQuery workplane coordinates. The two uses are independent, and no coordinate transformation is needed between them for the polar analysis path.

---

*End of feasibility study and requirements document. Intermediate findings file preserved at `reqs/aerospace/xfoil-cfd-expert-findings.md`.*

*This document is the authoritative requirements specification for the airfoil polar analysis feature. Implementation should begin with Phase 1 (backend scalar outputs) as a standalone PR, followed by Phase 3 (frontend scalars), then Phase 2 (polar endpoint), then Phase 4 (charts).*
