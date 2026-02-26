# XFoil Integration Feasibility — Aerospace Expert Findings

> **Author:** Aerospace / CFD Expert (Senior Computational Fluid Dynamics Engineer)
> **Date:** 2026-02-26
> **Collaboration Partner:** Linux/DevOps Expert (see open questions in Section 11)
> **Scope:** Feasibility assessment of airfoil polar analysis integration into CHENG v1.0+

---

## 1. Verdict Summary

XFoil is the correct aerodynamic tool for CHENG and is well-matched to RC aircraft Reynolds numbers (Re ≈ 50,000–500,000). It is the industry standard for low-speed, low-Reynolds-number airfoil analysis, has a 35-year validation record against wind tunnel data for exactly the airfoil families CHENG supports (NACA 4-series, Clark-Y, Eppler, Selig), and produces the full polar suite (Cl, Cd, Cm vs. α) that RC designers need. The primary integration challenge is not aerodynamic correctness but operational: XFoil is a Fortran 77 binary with an interactive terminal interface, making subprocess automation non-trivial in a containerized FastAPI environment. A compelling alternative exists — **neuralfoil** — a pure-Python ML surrogate of XFoil that is ~1000x faster, Docker-friendly, requires zero binary management, and achieves accuracy within 2–5% of XFoil for the Re range relevant to CHENG. The recommended implementation strategy is neuralfoil for the initial integration (fast, container-safe, no subprocess complexity) with XFoil available as an optional high-fidelity backend via a pluggable interface. Both tools produce aerodynamically valid and useful results for the CHENG user base.

---

## 2. XFoil Technical Overview

### What XFoil Computes

XFoil (Mark Drela, MIT, 1986–2013) is a coupled panel method / integral boundary layer solver for 2D airfoil analysis at subsonic speeds. Its formulation:

**Inviscid (outer) flow:**
- Linear-strength vortex panel method on the airfoil surface
- Karman-Tsien compressibility correction (negligible at RC Mach numbers < 0.1)
- Solves for surface velocity distribution Ue(s) = V∞(1 + vortex influence)
- Exact at panel resolution; error scales as O(1/N²) where N = panel count

**Viscous (inner) boundary layer — the key capability:**
- Two-equation lag-entrainment integral BL formulation (Green 1977 + Swafford)
- Separate treatment of laminar and turbulent BL regimes
- Transition prediction via the e^N (e-to-the-N) amplification factor method (Van Ingen / Smith-Gamberoni)
- Laminar separation bubble modeling: XFoil detects bubbles and applies a displacement thickness correction
- Strong viscous-inviscid interaction (fully coupled, not weakly coupled) — critical at low Re where boundary layers are thick relative to chord

**Primary outputs per angle of attack:**
- Cl — section lift coefficient
- Cd — section drag coefficient (viscous + pressure drag integrated from wake)
- Cm — section pitching moment coefficient about quarter-chord
- Cdp — pressure drag component
- Transition location (top surface): xtr_top as fraction of chord
- Transition location (bottom surface): xtr_bot as fraction of chord
- Cp distribution — surface pressure coefficient vs. chord
- Trailing edge angle and separation flag

**Polar mode (batch):** XFoil's OPER/ASEQ command sweeps α from α_min to α_max in steps, writing a polar file. This is the primary mode for CHENG integration.

### Governing Physics Summary

The viscous-inviscid coupling is why XFoil succeeds where pure panel methods fail at RC Reynolds numbers. At Re < 500,000, boundary layers are thick, laminar, and prone to separation. The displacement thickness effect of the BL modifies the effective inviscid body shape — XFoil iterates between the inviscid solution and BL solution until convergence. This iteration occasionally fails near stall (massively separated flow) — a known and manageable limitation.

### Validation Status

XFoil has been validated extensively against wind tunnel data for NACA 4-series and low-Re airfoils:
- NACA 4412 at Re=160,000–500,000: Cd error typically ±5–15% in attached flow (Abbott & Von Doenhoff + Drela papers)
- Eppler 387 at Re=100,000–300,000: XFoil matches UIUC wind tunnel data within 10–20% on Cd, <5% on Cl in linear range
- Clark-Y: Well-characterized, XFoil matches historic NACA wind tunnel data within engineering accuracy
- Selig-1223, AG-25: Designed using XFoil; wind tunnel correlation is excellent in their design Re range

Known systematic errors:
- Cd is **underpredicted** at very low Re (< 80,000) where XFoil's BL model struggles with extensive laminar regions and large separation bubbles
- Cl_max is **overpredicted** near stall (XFoil's post-stall behavior is not reliable)
- Post-stall (α > α_stall): unreliable — XFoil diverges or gives non-physical results

---

## 3. RC Reynolds Number Considerations

### Reynolds Number Calculation

For CHENG aircraft, Reynolds number at the mean aerodynamic chord:

```
Re = (V∞ × c) / ν
```

Where:
- V∞ = cruise airspeed [m/s]
- c = chord length [m] (use MAC for representative analysis)
- ν = kinematic viscosity of air ≈ 1.5 × 10⁻⁵ m²/s at sea level, 20°C

**Typical CHENG aircraft Re ranges:**

| Aircraft / Surface       | Chord (mm) | Speed (m/s) | Re (approx.)    |
|--------------------------|------------|-------------|-----------------|
| Trainer wing (root)      | 200        | 12          | 160,000         |
| Trainer wing (tip)       | 200        | 12          | 160,000         |
| Sport wing (root)        | 180        | 15          | 180,000         |
| Sport wing (tip)         | 120        | 15          | 120,000         |
| Aerobatic wing (root)    | 220        | 20          | 293,000         |
| Glider wing              | 150        | 8           | 80,000          |
| Trainer h-stab           | 100        | 12          | 80,000          |
| Glider h-stab            | 80         | 8           | 42,000          |
| Sport h-stab             | 100        | 15          | 100,000         |

### Laminar Separation Bubbles — The Critical RC Phenomenon

At Re < 500,000, airfoil boundary layers remain laminar well past the minimum pressure point. If the adverse pressure gradient is steep enough, the laminar BL separates, forms a free shear layer, transitions to turbulent, and reattaches — creating a **laminar separation bubble (LSB)**. This bubble:

1. Increases effective airfoil camber/thickness (displacement effect)
2. Adds drag beyond what attached-flow models predict
3. Can "burst" (fail to reattach) at high α → abrupt stall
4. Is highly sensitive to freestream turbulence level (Ncrit)

XFoil explicitly models LSBs via its displacement thickness correction and is one of very few tools that does this correctly in 2D. This is precisely why it remains the standard for RC airfoil design.

**Critical Re thresholds for XFoil reliability:**

| Re Range         | XFoil Behavior                                           | Recommendation                          |
|------------------|----------------------------------------------------------|------------------------------------------|
| Re > 300,000     | Reliable; Cd within 5–10%; Cl/Cd within 5%              | Use directly, high confidence            |
| 100,000–300,000  | Good; LSBs present but XFoil handles them               | Use; Ncrit tuning recommended            |
| 50,000–100,000   | Adequate; larger LSBs, XFoil may under-predict drag 15–20% | Use with caution; add uncertainty band |
| Re < 50,000      | Unreliable; massive separation, XFoil often fails to converge | Flag to user; avoid or use thin airfoils |

For CHENG: tail surfaces of gliders (Re ≈ 40,000–60,000) are in the marginal zone. Wing surfaces are generally above Re = 80,000 for any sensible design.

### Ncrit — Turbulence Amplification Factor

Ncrit is the logarithm of the critical amplification ratio of the most amplified Tollmien-Schlichting wave at transition. It controls when XFoil declares boundary layer transition.

**Physical meaning:** Higher Ncrit → lower freestream turbulence → later natural transition → longer laminar run → lower drag (in attached flow) → more abrupt stall.

**Recommended values for CHENG:**

| Environment                          | Ncrit | Notes                                  |
|--------------------------------------|-------|----------------------------------------|
| Low-turbulence wind tunnel           | 12–14 | For validation/comparison purposes     |
| Average wind tunnel                  | 9     | **XFoil's default**                    |
| Open air RC flying (calm day)        | 9–11  | Clean, low-turbulence outdoor air      |
| Open air RC flying (gusty/thermal)   | 7–9   | Elevated atmospheric turbulence        |
| RC prop wash on wing (tractor)       | 5–7   | Significant turbulence from propeller  |

**Recommendation for CHENG:** Default Ncrit = 9 (XFoil default). Expose as an advanced user parameter with tooltip explanation. For tractor-motor designs, suggest Ncrit = 7 in the UI. Do not present this as a beginner parameter.

### Transition Fixing

For thick airfoils (t/c > 12%) and high-α analysis, "free transition" (XFoil default) can over-predict performance. For most CHENG airfoils in normal flight, free transition is correct. Fixed transition (forced at a specified chordwise location) is useful for research comparison only — not needed for CHENG.

---

## 4. Recommended Outputs for RC Designers

Listed in priority order from most to least critical for a typical CHENG user:

### Priority 1: Essential (Minimum Viable Feature)

**Cl vs. α (lift curve)**
- Shows linear range, stall angle, and Cl_max
- RC designer needs: Where is stall? What's the maximum lift I can generate?
- Display: line chart, α on x-axis (−5° to +20°), Cl on y-axis

**Cl/Cd vs. α (efficiency curve)**
- The single most useful chart for RC efficiency — tells you where L/D is maximized
- RC designer needs: What angle gives best glide? Where should I cruise?
- Display: line chart with clear maximum marker

**Key scalar callouts (derived from polar):**
- Cl_max and α_stall (stall angle of attack)
- (Cl/Cd)_max and corresponding α
- Cl at zero incidence (quantifies camber contribution)
- Cd_min (minimum profile drag)

**Operating point marker:**
- Mark cruise condition on all charts (computed from cruise speed + weight + wing area)
- Shows stall margin (Cl_max − Cl_cruise) visually
- This is the most direct feedback for "is my design efficient at cruise?"

### Priority 2: Important (Full Feature)

**Cd vs. Cl (drag polar / "bucket")**
- Classic aerodynamicist's view — shows the low-drag "laminar bucket" for some RC airfoils (Eppler-387, AG-25)
- Less intuitive for non-experts but very useful for efficiency comparison

**Cm vs. α (pitching moment curve)**
- Shows Cmα slope — negative slope = airfoil stable (nose-down pitch with increasing α)
- Positive-cambered airfoils (NACA 4412, Clark-Y) have negative Cm0 (nose-down pitching moment at zero lift) — this must be trimmed by horizontal tail incidence
- Direct input for stability refinement

**Transition location vs. α**
- Shows where laminar-to-turbulent transition occurs on top and bottom surfaces
- Useful for understanding drag sources; advanced feature

### Priority 3: Advanced / Optional

**Wing airfoil vs. tail airfoil comparison overlay**
- Overlays polars for the wing airfoil and tail airfoil on the same chart
- Useful for checking that the tail is generating lift at the correct Cl
- Requires running XFoil/neuralfoil for both surfaces

**Per-section polars for multi-section wings**
- Separately analyze each panel's airfoil at its local Re (different chord, same speed)
- Panel 1 (inboard): higher Re, different airfoil
- Panels 2–4: lower Re (smaller chord if tapered), different airfoil if W12 override used
- Full feature scope only

**Cp distribution (pressure coefficient vs. chord)**
- Expert feature — shows suction peak, adverse gradient, bubble location
- Useful for diagnosing stall type and optimizing airfoil selection
- Low priority for CHENG's target user

### Derived Scalar Outputs for Non-Expert RC Designers

These translate polar data into actionable design feedback:

| Output                      | Formula                                         | Display                          |
|-----------------------------|-------------------------------------------------|----------------------------------|
| Stall speed estimate        | V_stall = sqrt(2W / (ρ × S × Cl_max))          | "Stalls at ≈ N m/s"              |
| Cruise L/D                  | Cl_cruise / Cd_cruise at operating point        | "Cruise efficiency: N:1"         |
| Stall margin (Cl units)     | Cl_max − Cl_cruise                              | "Stall margin: ΔCl = 0.xx"       |
| Stall margin (speed margin) | 1 − (V_cruise / V_stall) → expressed as %      | "N% above stall speed"           |
| Airfoil pitch stability     | Sign of Cmα                                     | "Stable" / "Unstable" indicator  |

---

## 5. Required Inputs

### 5.1 Gap Analysis Against Existing CHENG Parameters

| Input Required              | Status in CHENG                               | Action Needed                                    |
|-----------------------------|-----------------------------------------------|--------------------------------------------------|
| Airfoil geometry            | Available — `.dat` files in `/airfoils/`      | None — `backend/geometry/airfoil.py` loads these |
| Wing chord (root)           | `wing_chord` (G05, field in AircraftDesign)   | None — already available                         |
| Wing chord (tip)            | Derived: `wing_chord × wing_tip_root_ratio`   | None — compute from existing fields              |
| Wing MAC                    | `mean_aero_chord_mm` in DerivedValues         | None — already computed by engine                |
| H-stab chord                | `h_stab_chord` in AircraftDesign             | None — already available                         |
| **Cruise airspeed**         | **MISSING** — not a parameter in CHENG        | **Must add** — new param or derive from wing loading |
| Air density / altitude      | **MISSING** — no altitude parameter           | **Estimate** sea level (1.225 kg/m³); altitude optional |
| Wing incidence angle        | `wing_incidence` in AircraftDesign           | None — sets operating Cl reference point         |
| Tail airfoil type           | `tail_airfoil` (T23) in AircraftDesign       | None — already available                         |
| Aircraft total weight       | `weight_total_g` in DerivedValues            | None — already computed                          |
| Wing area                   | `wing_area_cm2` in DerivedValues             | None — already computed                          |
| Per-panel airfoils          | `panel_airfoils` (W12) in AircraftDesign     | None — already available                         |

### 5.2 Cruise Airspeed — The Critical Gap

CHENG has no cruise speed parameter. This is the most important missing input for airfoil polar analysis, because without it:
- Reynolds number cannot be computed precisely
- Operating Cl cannot be computed (need W and V to get Cl_op = 2W / (ρV²S))
- Cruise point cannot be marked on polar charts

**Options for filling this gap:**

**Option A (Recommended): Add cruise speed as a user parameter**
- New parameter: `cruise_speed_ms` (float, range 5–40 m/s, default 12 m/s)
- Place in Global panel or Propulsion section
- Display label: "Cruise Speed (m/s)" with optional m/s ↔ km/h conversion
- ID: G09 or P03 (following existing conventions)

**Option B: Estimate from wing loading**
- V_cruise ≈ sqrt(2 × WL_kg_m2 / (ρ × Cl_cruise_assumed))
- Assumes Cl_cruise ≈ 0.5 (reasonable for most RC aircraft)
- WL in kg/m² = wing_loading_g_dm2 / 100
- Less accurate but requires no new parameter
- Appropriate for an "estimated operating point" display

**Option C: Use fixed Re values per aircraft type**
- Trainer: Re = 150,000 (conservative)
- Sport: Re = 200,000
- Aerobatic: Re = 250,000
- Glider: Re = 80,000
- Least accurate but simplest to implement; no user input needed

**Recommendation:** Option A for any serious polar analysis. Option B as a fallback label shown when no cruise speed is entered. Option C only if speed is never added as a parameter.

### 5.3 Angle of Attack Range

Recommended sweep: α = −5° to +20°, step = 0.5°

Rationale:
- −5° captures negative-lift conditions (aerobatics, inverted, dive entry)
- +20° exceeds stall for all CHENG airfoils (stall typically at +12° to +17° at these Re)
- 0.5° steps = 50 evaluation points = reasonable resolution, fast with neuralfoil, ~2–5 seconds with XFoil subprocess

For XFoil, reduce to 1° steps (25 points) if subprocess latency is a concern.

### 5.4 Complete Input Specification

```python
class AirfoilAnalysisRequest:
    airfoil_name: str        # e.g., "Clark-Y", "NACA-4412"
    chord_mm: float          # actual chord in mm (NOT normalized)
    airspeed_ms: float       # freestream velocity in m/s
    altitude_m: float = 0.0  # altitude for air density (default sea level)
    alpha_min: float = -5.0  # degrees
    alpha_max: float = 20.0  # degrees
    alpha_step: float = 0.5  # degrees
    ncrit: float = 9.0       # transition amplification factor
    mach: float = 0.0        # computed internally from airspeed; expose for override
```

**Reynolds number computation:**

```python
import math

def compute_reynolds(chord_m: float, airspeed_ms: float, altitude_m: float = 0.0) -> float:
    """ISA atmosphere, sea level to 3000m."""
    T = 288.15 - 0.0065 * altitude_m     # Temperature [K]
    rho = 1.225 * (T / 288.15) ** 4.256  # Density [kg/m³], ISA approximation
    mu = 1.716e-5 * (T / 273.15) ** 1.5 * (383.55 / (T + 110.4))  # Sutherland
    nu = mu / rho                         # Kinematic viscosity [m²/s]
    return (airspeed_ms * chord_m) / nu

def compute_mach(airspeed_ms: float, altitude_m: float = 0.0) -> float:
    T = 288.15 - 0.0065 * altitude_m
    a = math.sqrt(1.4 * 287.058 * T)    # Speed of sound [m/s]
    return airspeed_ms / a
```

Mach number relevance: At V = 40 m/s (very fast for RC), Mach ≈ 0.12. Compressibility corrections negligible below Mach 0.3. XFoil's Karman-Tsien correction handles this automatically; neuralfoil accepts Mach as an input. For CHENG, Mach < 0.15 always — compressibility is irrelevant but should be passed correctly.

---

## 6. Airfoil Coordinate Generation

CHENG already has `.dat` files for all supported airfoils in `/airfoils/`. The `backend/geometry/airfoil.py` module loads them via `load_airfoil(name)` in Selig format. This is the correct approach and requires no changes for XFoil/neuralfoil integration.

### Coordinate Requirements by Airfoil Type

**NACA 4-digit (NACA-2412, NACA-4412, NACA-6412, NACA-0006, NACA-0009, NACA-0012):**
- Can be generated analytically from the 4-digit formula — no `.dat` file needed
- CHENG currently uses `.dat` files (correct approach for CadQuery geometry)
- For polar analysis, the existing `.dat` files are directly usable
- Alternative: use the `naca` Python library (`pip install naca`) or compute from formula
- NACA 4-digit formula is closed-form — thickness distribution + camber line analytically defined

**NACA 5-digit (not currently in CHENG):**
- More complex camber line; closed-form but piecewise
- Not needed for current airfoil set

**Clark-Y:**
- Tabulated only — no closed-form equation
- CHENG has `clark_y.dat` — canonical NACA TN-1233 data (47 coordinate pairs)
- Widely used; well-validated; the `.dat` file is the correct source

**Eppler-193, Eppler-387:**
- Designed using Eppler's inverse design code; tabulated
- CHENG has `.dat` files for both — use directly
- Eppler-387 is available in UIUC database (56 points, clean data)

**Selig-1223:**
- Designed by Michael Selig (UIUC); coordinates from UIUC database
- CHENG has `selig1223.dat` — authoritative source

**AG-25 (Airplane Girl 25):**
- Designed by Mark Drela for DLG (discus launch glider)
- Coordinates from UIUC database or aerodynamics.danboger.com
- CHENG has `ag25.dat` — use directly

**Flat-Plate:**
- CHENG generates this programmatically (6% diamond profile in `generate_flat_plate()`)
- For aerodynamic analysis, a flat plate at t/c = 0–3% at low Re behaves very differently from a diamond — XFoil/neuralfoil results are less physically meaningful
- Recommend flagging flat-plate analyses as approximate; real flat plates have XFoil convergence issues

**Symmetric (NACA-0006, NACA-0009, NACA-0012):**
- Computed from NACA 4-digit formula with zero camber
- CHENG `.dat` files are correct and usable

### Python Libraries for Coordinate Generation

If `.dat` files are ever insufficient or if on-the-fly generation is needed:

- `naca` (PyPI): `pip install naca` — generates NACA 4/5-digit coordinates analytically; 100 points default; returns numpy array
- `aeropy` (PyPI): broader airfoil geometry tools; heavier dependency
- UIUC Airfoil Database API: `http://m-selig.ae.illinois.edu/ads/coord_database.html` — authoritative source for all non-NACA profiles; not an API but downloadable

**Conclusion:** CHENG's existing `.dat` files are the correct source. No additional coordinate generation library is needed. The `load_airfoil()` function already handles all supported types.

---

## 7. Accuracy vs. Alternatives Table

| Tool | Method | Accuracy at RC Re (50k–500k) | Speed | Docker Complexity | CHENG Suitability | Notes |
|------|--------|------------------------------|-------|---------------------|-------------------|-------|
| **XFoil** | Panel + viscous BL (e^N) | High (Cl ±3%, Cd ±10–20%) | Medium (1–5s per polar via subprocess) | High (Fortran binary, non-interactive subprocess management) | Good | Industry standard; convergence issues near stall; subprocess automation is the main challenge |
| **neuralfoil** | ML surrogate of XFoil | High (within 2–5% of XFoil; validated against 50k+ XFoil polars) | Very High (< 50ms per polar, pure Python) | None (pip install, pure Python + numpy) | Excellent | Recommended for initial integration; Peter Sharpe (MIT); handles Re 1k–100M; accuracy degrades slightly vs XFoil below Re 50k |
| **MSES** | Multiblock ISES (successor) | Very High (better than XFoil for multi-element, transonic) | Slow (minutes) | Very High (academic license, Fortran) | Poor | Overkill for RC; not open source |
| **OpenFOAM RANS** | 3D/2D RANS CFD | Very High (reference accuracy) | Very Slow (hours per case) | Extreme (separate container, mesh generation, solver) | Poor | Vastly over-engineered for this application; Docker image > 2GB |
| **Thin airfoil theory** | Analytical (inviscid) | Low (Cl only, ±10%; no Cd, no stall) | Instantaneous | None | Partial | Gives Cl_α = 2π/rad, Cl at zero incidence = 2π × camber; useful as fallback; no viscous effects |
| **Panel method (inviscid)** | Vortex panel only | Low–Medium (Cl good ±5%, no Cd, no stall) | Very High (< 1ms) | None (Python implementations exist: pyaero, pyvlm) | Partial | Better than thin airfoil; still no viscosity; Cd=0 for attached flow |
| **XFLR5** | XFoil + VLM + LLT | High (XFoil base + 3D corrections) | Medium | High (Qt GUI binary, no CLI) | Poor for automated use | Excellent for manual design; not automatable in web app context |

### Detailed Assessment: neuralfoil vs XFoil

**neuralfoil** (github.com/peterdsharpe/NeuralFoil, PyPI: `neuralfoil`) deserves detailed treatment as the recommended path:

- **What it is:** A neural network trained on 50,000+ XFoil polars, covering Re = 1,000–100,000,000, α = −25° to +25°, Mach 0–0.9, Ncrit 0–24, ~1,500 airfoil geometries
- **Inputs:** Airfoil coordinates (CST parameterization internally, any .dat externally), Re, α, Mach, Ncrit
- **Outputs:** Cl, Cd, Cm, Cdp, Cp distribution, transition locations — same as XFoil
- **Accuracy validation:** Published RMS errors vs. XFoil: ΔCl ≈ 0.006, ΔCd ≈ 0.00022, ΔCm ≈ 0.003 (excellent)
- **Limitations:** Cannot exceed XFoil's physical accuracy (it learned from XFoil); post-stall behavior inherits XFoil's unreliability; very thin airfoils (t/c < 2%) may be less accurate
- **Speed:** Full polar (−5° to +20°, 51 α points) in < 50ms — suitable for real-time or near-real-time updates
- **Installation:** `pip install neuralfoil` — pure Python, NumPy/SciPy dependency only

**The key difference:** neuralfoil has no convergence issues. XFoil can fail to converge near stall (especially below Re 100k) and requires careful subprocess handling. neuralfoil always returns a result (potentially less accurate near stall, but never crashes).

---

## 8. Integration with Existing CHENG Stability Analysis

### 8.1 Aerodynamic Center vs. 25% Chord Assumption

CHENG's `backend/stability.py` currently uses the fixed assumption:

```
Wing AC at 25% MAC for all RC airfoils
```

This is the thin-airfoil theory result and is a good approximation for NACA 4-series and similar airfoils. XFoil/neuralfoil provide the actual aerodynamic center location (where Cm is nearly constant with α), which is typically 24–27% chord for most RC airfoils — close enough that the fixed 25% assumption rarely introduces significant error in static margin prediction (< 1–2% MAC).

**However**, for certain airfoils at low Re, the AC can shift:
- Selig-1223 (ultra-high camber): AC may be at 22–24% chord at low Re
- Eppler-387 (low-drag design): AC is well-placed at ~25–26%
- NACA symmetric (0012): AC is very close to 25% at all Re

**Recommendation:** Replace the fixed 25% with the actual Cmα-derived AC from the polar. This improves NP accuracy by 0–3% MAC. The change to `stability.py` is:

```python
# Current (approximate):
# NP_frac_MAC = 0.25 + 0.88 * V_h

# Improved (with polar data):
# ac_frac = -Cm_slope / Cl_slope  (from linear fit of polar in attached-flow range)
# NP_frac_MAC = ac_frac + 0.88 * V_h
```

### 8.2 Stall Speed Estimation — New Derived Value

With Cl_max from the polar, CHENG can compute stall speed:

```python
# New derived value: stall_speed_ms
# V_stall = sqrt(2 * W / (rho * S * Cl_max))
# W = weight_total_g / 1000 * 9.81  [N]
# S = wing_area_cm2 / 10000         [m²]
# rho = 1.225 kg/m³ (sea level)
# Cl_max from wing airfoil polar at operating Re
```

This is a high-value addition — directly tells RC builders the minimum safe flying speed.

### 8.3 Operating Cl at Cruise — Design Feedback

With cruise speed (new parameter) and aircraft weight/wing area (existing derived values):

```python
# Operating lift coefficient at cruise
Cl_op = (2 * W) / (rho * V_cruise**2 * S)
```

This tells the user whether they are flying in the efficient part of the polar (near Cl/Cd_max) or in an off-design condition. A "cruise efficiency rating" (Cl_op / (Cl/Cd)_max) gives beginner-friendly feedback.

### 8.4 Tail Airfoil Cm Impact on Trim

The horizontal tail airfoil's Cm0 (pitching moment at zero incidence) affects pitch trim. For CHENG's symmetric tail airfoils (NACA-0006, NACA-0009, NACA-0012), Cm0 = 0 by symmetry — this is correct and requires no special handling. If asymmetric tail airfoils were ever added, the tail Cm would need to enter the pitch trim equation.

For the current CHENG tail airfoil set (symmetric profiles only), tail polar analysis primarily provides:
- Tail surface Cl efficiency vs. Re (smaller tail chord → lower Re → potentially in the marginal Re zone for thin symmetric profiles)
- Validation that the tail is operating in its linear Cl range at cruise

### 8.5 Cache Strategy

Polar results must be cached. The cache key is:

```python
cache_key = (airfoil_name, round(Re, -3), ncrit)
# Round Re to nearest 1000 to avoid excessive cache misses
# Ignore Mach (negligible variation at RC speeds)
```

Cache entries are design-independent — the same airfoil at the same Re and Ncrit produces the same polar regardless of which aircraft it is attached to. A simple in-memory dictionary (LRU cache) with 50–100 entries is sufficient. Polars are small (< 5 KB per entry).

Estimated cache coverage: with 12 airfoils × 5 Re values (50k, 100k, 150k, 200k, 300k) = 60 unique polars. With neuralfoil's 50ms evaluation time, even cache misses are fast enough to be non-blocking in the WebSocket update loop.

---

## 9. Minimum Viable vs. Full Feature Scope

### Minimum Viable (MVP Airfoil Analysis Feature)

The smallest version that provides real value to an RC designer:

1. **Backend:** neuralfoil integration as a pure-Python module in `backend/airfoil_analysis.py`
   - Input: airfoil name, Re (computed from existing chord + new cruise_speed param), Ncrit=9 fixed
   - Output: Cl_max, α_stall, (Cl/Cd)_max, Cd_min, operating Cl at cruise, stall speed estimate
   - Cache: simple `functools.lru_cache` on the polar computation function

2. **New parameter:** `cruise_speed_ms` (G09) — added to `AircraftDesign` model and Global panel

3. **New derived values:** `cl_max`, `alpha_stall_deg`, `cl_cd_max`, `stall_speed_ms` — added to `DerivedValues`

4. **Frontend:** Display new derived values in the Stability Panel as scalar readouts (no new charts)
   - Stall speed: "Estimated stall speed: N m/s"
   - Cruise efficiency: "Cruise L/D: N:1"
   - Stall margin: "Stall margin: Δα = N° (ΔCl = N)"

**Total development scope (MVP):** Backend ~150 LoC + Frontend ~80 LoC. Low complexity.

### Full Feature Scope

Complete airfoil polar analysis integration:

1. **Interactive polar charts** — Cl vs. α, Cl/Cd vs. α, Cd vs. Cl (drag polar) — rendered in the Stability Panel or a dedicated "Aerodynamics" tab
2. **Operating point marker** — highlights cruise condition on all charts
3. **Wing vs. tail comparison overlay** — two airfoils on same chart
4. **Per-panel analysis** for multi-section wings (up to 4 panels with W12 airfoil overrides)
5. **Ncrit user control** — advanced parameter with RC-appropriate defaults and tooltip
6. **Cm data integrated into stability calculation** — actual AC replaces fixed 25% assumption
7. **Pressure Cp chart** — expert feature, optional
8. **Altitude parameter** — affects Re and stall speed calculation
9. **XFoil subprocess backend** — optional high-fidelity mode via pluggable interface

**Total development scope (full):** Backend ~400 LoC + Frontend ~500 LoC (new chart components). Medium–High complexity.

---

## 10. Implementation Complexity Estimate

### Component Breakdown

| Component | Complexity | Estimated LOC | Notes |
|-----------|------------|---------------|-------|
| neuralfoil integration + Re computation | Low | ~100 | `pip install neuralfoil`; wraps polar evaluation; pure Python |
| `AirfoilAnalysisResult` Pydantic model | Low | ~40 | Polar data + scalar outputs; follows existing CamelModel pattern |
| Cruise speed parameter (G09) | Low | ~20 | Add field to `AircraftDesign`, add to Global panel UI |
| Polar caching (LRU) | Low | ~20 | `@functools.lru_cache` or explicit dict in `backend/airfoil_analysis.py` |
| New `/api/airfoil/polar` REST endpoint | Low | ~50 | OR integrate into WebSocket trailer; REST is simpler for charts |
| Stall speed + operating Cl derived values | Low | ~30 | Added to `compute_derived_values()` in `engine.py` |
| New scalar readouts in Stability Panel | Low | ~80 | Frontend — follow existing DerivedField pattern |
| Interactive polar charts (React + Recharts/Victory) | Medium | ~300 | New chart components; requires chart library selection |
| Operating point marker on charts | Low | ~50 | Once charts exist |
| Wing vs. tail comparison overlay | Medium | ~100 | Additional airfoil_analysis call + chart overlay layer |
| Per-panel analysis (multi-section) | Medium | ~150 | Loop over panels; aggregate/display results |
| XFoil subprocess backend | High | ~300 | Async subprocess management; stdin/stdout protocol; convergence handling; platform-specific binary |
| Ncrit user control | Low | ~30 | Parameter + tooltip |
| Cm → actual AC in stability.py | Low | ~30 | One-line change + test update |
| Altitude parameter | Low | ~25 | Optional; ISA model already written above |

### Overall Complexity Rating

| Phase | Scope | Complexity | Justification |
|-------|-------|------------|---------------|
| Phase 1: Scalar outputs only | neuralfoil + new derived values + cruise speed param | **Low** | Pure Python; follows existing patterns exactly; no new UI components needed |
| Phase 2: Polar charts | Full interactive charts in Stability Panel | **Medium** | New chart library; new API endpoint or extended WebSocket; chart component design |
| Phase 3: XFoil subprocess | Optional high-fidelity backend | **High** | Binary management; async subprocess; convergence fallback logic; platform portability in Docker |

**Recommendation:** Execute Phase 1 and Phase 2 in sequence. Skip Phase 3 unless users specifically request higher accuracy than neuralfoil provides (unlikely for the CHENG user base).

---

## 11. Open Questions for Linux/DevOps Expert

The following questions are outside aerodynamic scope and require input from the infrastructure/DevOps expert:

### Q1: neuralfoil Package Size and Docker Impact
`neuralfoil` depends on NumPy and potentially TensorFlow or JAX for the neural network inference. What is the installed size of `neuralfoil` + dependencies? How does this impact the Docker image size budget? (Current image presumably already has NumPy via scipy/cadquery.)

### Q2: XFoil Binary in Docker
If XFoil subprocess is implemented (Phase 3): What is the cleanest way to include the XFoil binary in the Docker image? Options:
- Build from source in Dockerfile (Fortran compiler required)
- Copy pre-built binary (x86_64 Linux; arm64 if Cloud Run is multi-arch)
- Use `xfoil` package from apt/conda-forge

Does the current base image have `gfortran` available? What is the image architecture (amd64 / arm64)?

### Q3: Subprocess Security in Cloud Mode
If XFoil runs as a subprocess in `CHENG_MODE=cloud`, a user could potentially trigger unbounded computation. What is the existing timeout/resource limit strategy? Can the `CapacityLimiter(4)` pattern from CadQuery be reused for XFoil subprocesses?

### Q4: Concurrent Polar Requests
Multiple WebSocket clients could simultaneously request polar analysis (one per connected browser tab). neuralfoil is pure Python and GIL-bound but very fast (< 50ms). Is this a concern for Cloud Run concurrency? Does the existing thread pool pattern (`anyio.to_thread.run_sync`) handle this correctly?

### Q5: Polar API: WebSocket vs. REST
Should polar data be returned in the existing WebSocket JSON trailer (alongside `derived` and `warnings`) or via a new REST endpoint (`GET /api/airfoil/polar?airfoil=Clark-Y&re=160000`)? WebSocket has the advantage of automatic re-delivery when design parameters change. REST is simpler for chart-specific requests that aren't tied to geometry regeneration. What is the latency profile of each approach given the existing WebSocket binary frame size?

### Q6: neuralfoil Accuracy at Very Low Re
The CHENG glider preset produces tail surface Re ≈ 40,000–60,000. Has neuralfoil been validated at Re < 50,000? If accuracy degrades significantly in this range, should CHENG flag a "Low Reynolds number — polar accuracy limited" warning to users? What Re threshold should trigger this warning?

### Q7: Chart Library Selection
What chart libraries are currently used or available in the CHENG frontend (React 19, Vite 6, pnpm)? Recharts (MIT, small, React-native) and Victory (MIT, larger) are common choices. D3 directly is also possible via R3F. Is there a preference or constraint (bundle size, license)?

### Q8: Persistent Polar Cache
The LRU in-memory cache is wiped on server restart. For `CHENG_MODE=local`, should polars be cached to disk (`/data/polars/` alongside designs)? This would make subsequent polar requests instant after the first computation. Does the existing `LocalStorage` / `MemoryStorage` pattern extend naturally to this use case?

---

*End of aerospace expert findings. Awaiting Linux/DevOps expert findings at `reqs/devops/xfoil-devops-expert-findings.md` for cross-synthesis.*
