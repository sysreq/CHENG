# Feature Requirements: Mass Properties Override & Dynamic Stability (DATCOM)

> **Document status:** Draft v1.0 — 2026-02-26
> **Author:** Research synthesis from codebase review + USAF DATCOM literature
> **Scope:** Two new features for CHENG parametric RC plane generator
> **Dependencies:** `backend/stability.py`, `backend/models.py`, `backend/validation.py`, `frontend/src/components/panels/StabilityPanel.tsx`

---

## 1. Executive Summary

This document specifies two interrelated features that extend CHENG's existing static stability analysis into the domain of dynamic stability:

**Feature A — Mass Properties Override:** Allows users to input measured or manufacturer-specified mass properties (total mass, CG location, moments of inertia) rather than relying solely on CHENG's geometric estimates. This is essential for real-world RC aircraft where the installed electronics (battery, motor, ESC, servos, receiver) dominate the weight distribution and are not captured by airframe geometry alone.

**Feature B — DATCOM Dynamic Stability Analysis:** Uses the United States Air Force Stability and Control Data Compendium (USAF DATCOM) empirical semi-analytical methods to estimate aerodynamic stability derivatives, then computes the classical dynamic stability modes: short-period, phugoid (longitudinal) and Dutch roll, roll, spiral (lateral/directional). Results tell the designer not just *whether* the aircraft is stable, but *how* it responds after a disturbance — oscillation period, damping character, and whether the motion converges or diverges.

Together these features transform CHENG from a geometry-and-static-stability tool into a preliminary flight dynamics design aid, appropriate for early-stage RC aircraft development.

---

## 2. Background & Motivation

### 2.1 What Static Stability Already Provides

CHENG v1.0 computes seven static stability metrics via `backend/stability.py`, driven by the existing `compute_static_stability()` function:

| Metric | Symbol | Existing field |
|--------|--------|----------------|
| Neutral point position | NP | `neutral_point_mm`, `neutral_point_pct_mac` |
| CG position as % MAC | CG%MAC | `cg_pct_mac` |
| Static margin | SM | `static_margin_pct` |
| Horizontal tail volume coefficient | V_h | `tail_volume_h` |
| Vertical tail volume coefficient | V_v | `tail_volume_v` |
| Wing loading | W/S | `wing_loading_g_dm2` |

Two validation warnings exist: V34 (marginal static margin 0–2% MAC) and V35 (negative static margin — pitch-unstable). The `StabilityPanel.tsx` displays these via three gauge components: `CgVsNpGauge`, `StaticMarginGauge`, and `PitchStabilityIndicator`.

Static stability answers: "If I disturb this aircraft from trimmed flight, does the restoring moment push it back?" A positive static margin means yes — but it says nothing about *how quickly* it returns, whether it oscillates, or whether those oscillations decay or grow.

### 2.2 Why Dynamic Stability Matters

Dynamic stability governs the *transient response* to disturbances. An aircraft with good static stability may still have:

- **Short-period oscillations** that are too rapid and lightly damped, making pitch control feel "twitchy" and prone to pilot-induced oscillation (PIO).
- **Phugoid oscillations** (pitch-speed-altitude exchange) that take 20–60 seconds per cycle and require constant pilot correction on long flights.
- **Dutch roll** — a coupled yaw-roll oscillation that is uncomfortable at best, uncontrollable at worst. Common in swept-wing designs.
- **Spiral divergence** — a slow, insidious mode where a banked turn tightens without pilot input. The most common cause of RC "death spiral" accidents.
- **Sluggish roll response** (large roll mode time constant) — the aircraft feels unresponsive to aileron input.

For RC aircraft designers, understanding these modes before the first flight — even with engineering-level accuracy rather than CFD-level precision — can prevent crashes, wasted prints, and dangerous situations.

### 2.3 What USAF DATCOM Is

The **USAF Stability and Control Data Compendium** (DATCOM) is a handbook of empirical and semi-analytical methods for estimating aerodynamic stability and control derivatives of fixed-wing aircraft. It was compiled between 1960 and 1978 by the McDonnell Douglas Corporation in collaboration with the Flight Dynamics Laboratory at Wright-Patterson Air Force Base, with the final digital implementation (Digital DATCOM) completed in 1979 (AFFDL-TR-79-3032).

DATCOM organizes its methods by aircraft component and parameter type across roughly 3,100 pages. The digital implementation (a FORTRAN program) accepts a geometric description of an aircraft and flight conditions, and outputs dimensionless stability and control derivatives. DATCOM is the canonical starting point for preliminary aerodynamic design in the absence of wind tunnel or flight test data.

Its key advantage for CHENG is that **all inputs required by the relevant DATCOM sections are already captured in `AircraftDesign`** — wing geometry, tail geometry, fuselage dimensions, airfoil selection. No additional geometric information is needed beyond what CHENG already tracks.

### 2.4 Limitations and Appropriate Expectations for RC-Scale Aircraft

DATCOM was validated primarily against military aircraft data from the 1950s–1970s — typically chord Reynolds numbers of 1,000,000 and above. RC aircraft typically operate at:

- **Re = 100,000–500,000** at the wing (trainer: ~300,000, small sport: ~150,000)
- Low Mach numbers (M < 0.05 in most cases, certainly M < 0.15 even for fast models)
- Relatively thick airfoils (8–12% t/c) that behave similarly to DATCOM's validated database
- Low aspect ratios in some configurations (flying wings, delta-like planforms)

Known limitations at RC scale:

1. **Turbulent skin friction assumption:** Digital DATCOM assumes fully turbulent boundary layers. At Re < 500,000, significant laminar runs exist, reducing skin friction drag (this affects CDα but not derivative estimates severely).
2. **Lift curve slope accuracy:** DATCOM uses lifting-line theory corrections (DATCOM Section 4.1.3.2) which lose accuracy below AR~4 and at low Re where laminar separation can reduce effective lift slope.
3. **No propeller slipstream effects:** DATCOM does not model propwash over the tail, which significantly affects Cmq and CLq for tractor-configuration RC aircraft.
4. **No ground effect.**
5. **No flexible structures:** Relevant for foam/thin-film aircraft but CHENG targets rigid 3D-printed structures.
6. **Flying wing / BWB:** DATCOM's handling of blended-wing-body configurations is limited. Results for CHENG's `fuselage_preset = "Blended-Wing-Body"` should be flagged with lower confidence.

**Expected accuracy:** Derivative estimates within ±20–30% of flight-test values for conventional configurations (Trainer, Sport, Aerobatic) at the Reynolds number range typical for those wing spans. This is sufficient for design guidance and go/no-go screening, but not for autopilot control law design.

The UI must communicate clearly that all dynamic stability values are **engineering estimates** and should be validated against flight testing.

---

## 3. Feature A: Mass Properties Override

### 3.1 Problem Statement

CHENG currently estimates total weight from geometry and `material_density`, supplemented by `motor_weight_g` and `battery_weight_g` point masses. The CG estimate places the motor at the nose and the battery at `battery_position_frac` along the fuselage. This model is:

- Adequate for preliminary airframe sizing (V34/V35 static margin warnings)
- Inadequate for accurate dynamic stability analysis, because Ixx, Iyy, Izz cannot be reliably estimated from the rough geometric model

Real builders weigh each component before assembly and can measure the installed CG with a simple balance point test. They also have manufacturer-specified motor, battery, and electronics weights. These measured values are far more accurate than CHENG's estimates and must be allowed to override the estimates.

### 3.2 Scope

The following inputs are in scope for Feature A:

#### 3.2.1 Total Mass Override

| Field ID | Name | Unit | Range | Notes |
|----------|------|------|-------|-------|
| MP01 | `mass_total_override_g` | grams | 50–10,000 | Override for total all-up weight. Replaces `weight_total_g` in dynamic analysis only. |

When MP01 is set, it feeds into `wing_loading_g_dm2` recalculation and replaces the geometry-estimated weight in all DATCOM derivative computations.

#### 3.2.2 CG Position Override

| Field ID | Name | Unit | Range | Notes |
|----------|------|------|-------|-------|
| MP02 | `cg_override_x_mm` | mm from nose | 0–fuselage_length | Override longitudinal CG. Replaces `estimated_cg_mm` from engine. |
| MP03 | `cg_override_z_mm` | mm above keel | -50–+100 | Vertical CG offset from aircraft keel/datum line. Default 0. |
| MP04 | `cg_override_y_mm` | mm from centerline | -100–+100 | Lateral CG for asymmetric loading checks. Normally 0. |

MP02 is the most commonly needed override. MP03 and MP04 are advanced inputs that affect lateral/directional dynamic modes.

#### 3.2.3 Moments of Inertia

| Field ID | Name | Unit | Range | Notes |
|----------|------|------|-------|-------|
| MP05 | `ixx_override_kg_m2` | kg·m² | 0.001–10.0 | Roll inertia (about longitudinal axis). Most sensitive to wing mass distribution. |
| MP06 | `iyy_override_kg_m2` | kg·m² | 0.001–10.0 | Pitch inertia (about lateral axis). Governs short-period and phugoid. |
| MP07 | `izz_override_kg_m2` | kg·m² | 0.001–10.0 | Yaw inertia (about vertical axis). Governs Dutch roll, spiral. |

Products of inertia (Ixy, Ixz, Iyz) are out of scope for this feature (see Section 6). For conventional symmetric aircraft the off-diagonal terms are small and their omission introduces less than 5% error in mode frequencies.

Each of MP05–MP07 has an independent override toggle. When not overridden, CHENG falls back to its geometric estimation formulas (Section 3.4.2).

### 3.3 User Interface Requirements

#### 3.3.1 Panel Placement

A new **"Mass Properties"** collapsible section should be added to the **existing Fuselage/Propulsion panel** (or as a dedicated sub-tab in a redesigned physics panel), positioned after the existing motor/battery weight inputs. It should not be a top-level tab — it is an advanced option, not a primary workflow step.

#### 3.3.2 Override Mode Toggle

Each overrideable property group has a two-state toggle:

```
[ Estimated ]  [ Override ]
```

When "Estimated" is active (default), the estimated value is shown as a read-only derived field in muted text. When "Override" is active, an input field appears for the user to type or use a slider to set the value. The estimated value remains visible below the input as a reference.

#### 3.3.3 Display Format

- **Total mass:** show both estimated and override in grams and ounces
- **CG position:** show in mm from nose (primary) with computed MAC% alongside
- **Moments of inertia:** show in kg·m² (primary) with g·cm² as secondary (RC-scale friendly). Provide a "?" tooltip explaining what the value governs physically.

#### 3.3.4 Unit Handling

The unit toggle system (`unitStore.ts`, `units.ts`) should be extended for mass properties:

- Mass: grams / ounces (not kg, as RC components are specified in grams)
- Length offsets: mm / inches (existing unit toggle applies)
- Inertia: kg·m² primary / g·cm² secondary display. The factor is 1 kg·m² = 10,000 g·cm² (for reference: a typical 1000mm-span trainer has Iyy ≈ 0.008 kg·m²).

#### 3.3.5 Visual Indicators

- An orange "Overridden" badge on any group where the user has provided override values
- A "Reset to Estimated" link that clears the override for that group
- When mass override differs from geometric estimate by more than 30%, show a yellow info note (not a blocking warning)

### 3.4 Backend Requirements

#### 3.4.1 Pydantic Model Changes

New fields are added to `AircraftDesign` in `backend/models.py`:

```python
# ── Mass Properties Override (MP01-MP07) ─────────────────────────────────
# All fields Optional — None means "use geometric estimate"
mass_total_override_g: Optional[float] = Field(default=None, ge=50.0, le=10000.0)
cg_override_x_mm:      Optional[float] = Field(default=None, ge=0.0,  le=2000.0)
cg_override_z_mm:      Optional[float] = Field(default=None, ge=-50.0, le=100.0)
cg_override_y_mm:      Optional[float] = Field(default=None, ge=-100.0, le=100.0)
ixx_override_kg_m2:    Optional[float] = Field(default=None, ge=0.0001, le=10.0)
iyy_override_kg_m2:    Optional[float] = Field(default=None, ge=0.0001, le=10.0)
izz_override_kg_m2:    Optional[float] = Field(default=None, ge=0.0001, le=10.0)
```

All fields default to `None` for backward compatibility with existing designs. When `None`, the backend uses geometric estimates.

#### 3.4.2 Moment of Inertia Estimation (Fallback)

When inertia overrides are absent, CHENG must estimate Ixx, Iyy, Izz from geometry. The recommended approach is the **component build-up method**:

**Wing (each half):**
```
I_wing_roll  = (m_wing / 12) * (span/2)^2        [dominant term: mass at tip]
I_wing_pitch = (m_wing / 12) * (chord)^2
I_wing_yaw   = I_wing_roll + I_wing_pitch         [parallel axis theorem contribution]
```

**Fuselage (approximated as solid cylinder along X-axis):**
```
I_fus_pitch = (m_fus / 12) * (length^2 + 3*radius^2)
I_fus_roll  = (m_fus / 2)  * radius^2
I_fus_yaw   = I_fus_pitch
```

**Tail surfaces (treated as thin plates at distance l_t from CG):**
```
I_tail_pitch_contribution = m_tail * l_t^2        [parallel axis]
```

**Total (summed + parallel axis):**
```
Ixx = I_wing_roll + I_fus_roll
Iyy = I_wing_pitch + I_fus_pitch + m_tail * l_t^2 + m_motor * x_motor^2
Izz = I_wing_yaw  + I_fus_yaw   + m_tail * l_t^2
```

These estimates are rough (±30–50%) but sufficient to produce qualitatively correct dynamic mode predictions. They should be clearly labeled "Estimated" in the UI and never presented as accurate.

A new function `estimate_inertia(design, derived)` should be added to `backend/stability.py` (or a new `backend/mass_properties.py` module).

#### 3.4.3 Effective Values Resolution

A helper function `resolve_mass_properties(design, derived)` returns a `MassProperties` dataclass with the effective values after applying overrides:

```python
@dataclass
class MassProperties:
    mass_g: float           # MP01 or weight_total_g
    cg_x_mm: float          # MP02 or estimated_cg_mm (absolute from nose)
    cg_z_mm: float          # MP03 or 0.0
    cg_y_mm: float          # MP04 or 0.0
    ixx_kg_m2: float        # MP05 or estimated
    iyy_kg_m2: float        # MP06 or estimated
    izz_kg_m2: float        # MP07 or estimated
    ixx_estimated: bool     # True if fallback was used
    iyy_estimated: bool
    izz_estimated: bool
```

This object is the interface between Feature A and Feature B.

### 3.5 Validation Requirements

| Warning ID | Trigger | Message | Fields |
|-----------|---------|---------|--------|
| V41 | `mass_total_override_g` differs from `weight_total_g` by more than 40% | "Mass override ({value}g) is {pct}% different from geometry estimate ({estimate}g). Verify component weights." | `mass_total_override_g` |
| V42 | `cg_override_x_mm` differs from `estimated_cg_mm` by more than 15% of fuselage_length | "CG override position is far from geometry estimate. Confirm balance point measurement." | `cg_override_x_mm` |
| V43 | Any inertia override is physically implausible (e.g., Iyy < Ixx for a conventional layout) | "Pitch inertia (Iyy) should be larger than roll inertia (Ixx) for conventional aircraft. Check inertia values." | `iyy_override_kg_m2`, `ixx_override_kg_m2` |

---

## 4. Feature B: DATCOM Dynamic Stability Analysis

### 4.1 Problem Statement

Static stability (V34/V35, the CG vs NP gauge) tells the designer whether the aircraft will return to trim after a perturbation. It does not tell them:

- How many oscillations before the motion damps out
- Whether a 20-second phugoid will make the aircraft difficult to fly
- Whether the Dutch roll will be noticeable or violent
- Whether a spiral mode will tighten slowly (recoverable) or rapidly (dangerous)
- Whether the roll response feels crisp or sluggish

These questions require dynamic stability analysis: assembling the linearized equations of motion about a trim condition, computing eigenvalues, and interpreting the resulting modes. DATCOM provides the aerodynamic stability derivatives needed to populate those equations from geometry alone — no wind tunnel required.

### 4.2 DATCOM Overview for This Application

The full USAF DATCOM spans five physical volumes. The sections applicable to CHENG are:

| Volume | Section | Title | Relevance |
|--------|---------|-------|-----------|
| 2 | 4.1 | Wings at Angle of Attack | Wing lift curve slope CLα_w |
| 2 | 4.1.3.2 | Subsonic Wing CLα — Finite Span Correction | Primary CLα formula |
| 2 | 4.2 | Body Aerodynamics | Fuselage CNα contribution |
| 2 | 4.3 | Wing-Body Combinations | Interference factor KWB |
| 2 | 4.5 | Wing-Body-Tail Combinations | Total CLα, Cmα of complete aircraft |
| 3 | 5.1 | Downwash and Dynamic Pressure Ratio | Tail downwash dε/dα |
| 3 | 5.2 | Tail Aerodynamics | Horizontal tail CLα_t, Cmα_t |
| 3 | 5.3 | Tail-Body Combinations | Tail contribution with interference |
| 3 | 6.1 | Lateral-Directional Static Derivatives | CYβ, Clβ, Cnβ |
| 3 | 6.1.4 | Vertical Tail CYβ, Cnβ | Fin directional stability |
| 3 | 6.1.5 | Wing Clβ — Dihedral Effect | Geometric + sweep contributions |
| 4 | 7.1 | Pitch Damping: CLq, Cmq | Pitch damping from tail |
| 4 | 7.1.2 | CLq_dot, Cmq_dot (α-dot terms) | Apparent mass corrections |
| 4 | 7.3 | Roll Damping: Clp | Wing and tail roll damping |
| 4 | 7.4 | Yaw Rate Derivatives: Cnr, Clr, CYr | Fin and wing yaw damping |
| 4 | 7.5 | Cross Derivatives: Cnp, Clp, CYp | Lateral coupling |

Note: Digital DATCOM (AFFDL-TR-79-3032) is a FORTRAN implementation of these sections. CHENG will implement equivalent formulas in pure Python — not a subprocess call to the FORTRAN binary.

**Flight condition inputs required:**

| Input | Symbol | Unit | Where it comes from |
|-------|--------|------|---------------------|
| True airspeed | V | m/s | User input (new: `flight_speed_ms`) |
| Altitude | h | m | User input (new: `flight_altitude_m`) |
| Trim angle of attack | α₀ | deg | Computed from CLtrim = W/(½ρV²S) |
| Air density | ρ | kg/m³ | Computed from h via ISA model |

### 4.3 Stability Derivatives to Estimate

This section documents each derivative: symbol, physical meaning, DATCOM section, and formula approach.

---

#### 4.3.1 Longitudinal Derivatives

**CLα — Lift Curve Slope (total aircraft)**

- Symbol: `CL_alpha`
- Physical meaning: Rate of change of lift coefficient with angle of attack (1/rad). The primary stiffness parameter for longitudinal static stability. Typically 4–6 /rad for RC-scale aircraft.
- DATCOM section: 4.1.3.2 (wing), 4.5 (complete aircraft)
- Formula approach:

```
Wing lift curve slope (Polhamus/DATCOM semi-empirical):
  a_w = (2π AR) / (2 + sqrt(4 + AR²(1 + tan²Λ_c/2 / β²)))

  where:
    AR    = wing aspect ratio
    Λ_c/2 = half-chord sweep angle (rad)
    β     = sqrt(1 - M²), compressibility correction (≈1 at RC speeds)

Complete aircraft:
  CL_alpha = a_w * (1 + dε/dα) * η_t * (S_t/S_w)
  (simplified; full DATCOM 4.5 adds fuselage body factor KWB ≈ 1.05–1.10)

  where:
    dε/dα = downwash gradient at horizontal tail (DATCOM Section 5.1)
           ≈ 2 * a_w / (π * AR)  (approximate for unswept wings)
    η_t   = tail dynamic pressure ratio (typically 0.85–0.95)
    S_t   = horizontal tail area
    S_w   = wing reference area
```

**CDα — Drag Curve with AoA**

- Symbol: `CD_alpha`
- Physical meaning: Induced drag slope, relevant mainly for phugoid period accuracy. CDα ≈ 2 * CLtrim / (π * AR * e) where e is Oswald efficiency.
- DATCOM section: 4.1.5 (drag build-up)
- Formula: Use simple induced drag: CDα = 2*CL0/(π*AR*e), where e≈0.75–0.85 for RC aircraft.

**Cmα — Pitching Moment Slope**

- Symbol: `Cm_alpha`
- Physical meaning: Rate of change of pitching moment with AoA. Must be negative for pitch stability. Directly related to static margin: Cmα = -CL_alpha * (SM_fraction_MAC).
- DATCOM section: 4.5 (Wing-body-tail pitching moment)
- Formula:

```
Cm_alpha = CL_alpha_w * (x_cg - x_ac_w)/c_bar
         - CL_alpha_t * η_t * (S_t/S_w) * (l_t/c_bar) * (1 - dε/dα)

  where:
    x_cg       = CG position (fraction MAC)
    x_ac_w     = wing aerodynamic center (0.25 for all RC airfoils in CHENG)
    c_bar      = MAC
    CL_alpha_t = tail section lift slope ≈ 0.9 * a_w (DATCOM 5.2, aspect-ratio correction)
    l_t        = effective tail arm
```

Note: This is algebraically equivalent to `Cmα = -CL_alpha * SM_frac` at the trim condition, confirming consistency with the existing static stability computation.

**CLq — Lift Due to Pitch Rate**

- Symbol: `CL_q`
- Physical meaning: Incremental lift produced when the aircraft pitches. The tail traces an arc, changing its local angle of attack. Positive for aft-tail configurations.
- DATCOM section: 7.1
- Formula:

```
CL_q = 2 * CL_alpha_t * η_t * (S_t/S_w) * (l_t / c_bar)

     ≈ 2 * V_h * CL_alpha_t / CL_alpha_w
```

**Cmq — Pitch Damping Derivative** *(most important dynamic derivative)*

- Symbol: `Cm_q`
- Physical meaning: Rate of change of pitching moment with pitch rate. Always negative (stabilizing). Primary damping term for both short-period and phugoid modes. A tail makes the dominant contribution.
- DATCOM section: 7.1
- Formula:

```
Cm_q = -2 * CL_alpha_t * η_t * (S_t/S_w) * (l_t/c_bar)²

     = -2 * V_h * (l_t/c_bar) * CL_alpha_t

  Typical RC values: -5 to -20 (per radian of pitch rate, non-dimensional)
  Units: 1/rad (when using c_bar/(2V) as reference)
```

**CLα̇, Cmα̇ — Angle-of-Attack Rate Derivatives (apparent mass terms)**

- Symbol: `CL_alphadot`, `Cm_alphadot`
- Physical meaning: Apparent mass effect from the changing downwash lag at the tail. Cmα̇ is negative (adds to pitch damping). These terms are secondary in importance for slow RC aircraft.
- DATCOM section: 7.1.2
- Formula:

```
CL_alphadot = 2 * CL_alpha_t * η_t * (S_t/S_w) * (l_t/c_bar) * (dε/dα)
Cm_alphadot = -CL_alphadot * (l_t/c_bar)

  Typical RC values: CL_alphadot ≈ 1–4, Cm_alphadot ≈ -3 to -12
```

---

#### 4.3.2 Lateral/Directional Derivatives

**CYβ — Side Force Due to Sideslip**

- Symbol: `CY_beta`
- Physical meaning: Change in side force with sideslip angle. Primarily from the vertical fin. Negative (fin pushes back toward zero sideslip).
- DATCOM section: 6.1.4
- Formula:

```
CY_beta = -CL_alpha_v * η_v * (S_v/S_w) * (1 + dσ/dβ)

  where:
    CL_alpha_v = vertical fin lift slope (DATCOM 4.1.3.2, treating fin as a low-AR wing)
    η_v        = fin dynamic pressure ratio ≈ 0.9
    S_v        = vertical fin area
    dσ/dβ      = sidewash gradient (≈ 0.1–0.3 for conventional fuselages)
```

**Clβ — Dihedral Effect (roll due to sideslip)**

- Symbol: `Cl_beta`
- Physical meaning: Roll moment produced by sideslip. Negative = laterally stable (sideslip to right → roll left, leveling the bank). Composed of geometric dihedral, sweep, and fin contributions.
- DATCOM section: 6.1.5
- Formula:

```
Cl_beta_dihedral = -(CL_alpha_w / 2π) * Γ_eff * (π/180)
  [Γ_eff = geometric dihedral angle, deg → rad factor]

Cl_beta_sweep = -CL * tan(Λ_c/4) / (4 * AR)
  [CL = trim lift coefficient; stronger at low speed, swept wings]

Cl_beta_fin = -CL_alpha_v * η_v * (S_v/S_w) * (z_v/b)
  [z_v = vertical distance of fin AC above CG; b = wing span]

Cl_beta_total = Cl_beta_dihedral + Cl_beta_sweep + Cl_beta_fin
  Typical RC values: -0.05 to -0.25 /rad
```

**Cnβ — Directional Stability (yaw due to sideslip, "weathercock stability")**

- Symbol: `Cn_beta`
- Physical meaning: Yawing moment produced by sideslip. Must be positive for directional stability (sideslip right → yaw right, weathercocking back). The vertical fin is the dominant contributor.
- DATCOM section: 6.1.4
- Formula:

```
Cn_beta_fin = CL_alpha_v * η_v * (S_v/S_w) * (l_v/b)
  [l_v = moment arm from CG to fin AC; b = wing span]

Cn_beta_wing = -CL * (1 - 3*λ)/(6*(1+λ)) * tan(Λ_c/4)
  [λ = taper ratio; swept wings contribute negative Cnβ]

Cn_beta_fuselage = (small, negative contribution for conventional fuselages)
  ≈ -k_n * k_rl * (S_B_side * l_fus) / (S_w * b)

Cn_beta_total = Cn_beta_fin + Cn_beta_wing + Cn_beta_fuselage
  Must be positive. Typical RC values: 0.03 to 0.15 /rad
```

**Clp — Roll Damping**

- Symbol: `Cl_p`
- Physical meaning: Roll moment produced by roll rate. Always negative (damping). Governs the roll mode time constant. Wing is the dominant contributor.
- DATCOM section: 7.3
- Formula:

```
Cl_p_wing = -(CL_alpha_w / 8) * (1 + 3λ) / (1 + λ)  [rectangular: -a_w/8]
Cl_p_tail = -CL_alpha_t * η_t * (S_t/S_w) * (l_t/b)²  [small contribution]

Cl_p_total ≈ Cl_p_wing
  Typical RC values: -0.3 to -0.7 /rad
```

**Cnr — Yaw Damping**

- Symbol: `Cn_r`
- Physical meaning: Yawing moment due to yaw rate. Always negative. Fin and wing drag are contributors.
- DATCOM section: 7.4
- Formula:

```
Cn_r_fin = -CL_alpha_v * η_v * (S_v/S_w) * (l_v/b)²
Cn_r_wing = -(CL² / (π*AR) + CD0/8) [approximate]

Cn_r_total ≈ Cn_r_fin + Cn_r_wing
  Typical RC values: -0.05 to -0.25 /rad
```

**Clr — Roll Due to Yaw Rate**

- Symbol: `Cl_r`
- Physical meaning: Rolling moment produced by yaw rate. Positive for most configurations (coupling term in Dutch roll).
- DATCOM section: 7.4 (coupling)
- Formula:

```
Cl_r ≈ CL / 4  [wing contribution, approximate]
Cl_r_fin = CL_alpha_v * η_v * (S_v/S_w) * (z_v/b) * (l_v/b)

Cl_r_total = Cl_r_wing + Cl_r_fin
  Typical RC values: 0.05 to 0.30 /rad
```

**Cnp — Yaw Due to Roll Rate**

- Symbol: `Cn_p`
- Physical meaning: Yawing moment from roll rate (adverse yaw from differential wing lift/drag). Important for Dutch roll coupling.
- DATCOM section: 7.5
- Formula:

```
Cn_p ≈ -CL/8 * (1 - 3λ)/(1+λ)  [wing, simplified]
  Sign and magnitude depend heavily on lift coefficient (trim condition).
  Typical RC values: -0.05 to +0.10 /rad
```

**CYp, CYr — Side Force Rate Derivatives**

- Physical meaning: Fin side force due to roll rate and yaw rate respectively. Secondary terms used for completeness in the equations of motion.
- DATCOM sections: 7.5, 7.4
- Formulas are fin contributions only, analogous to Cl_r and Cn_r formulas above.

---

### 4.4 Dynamic Stability Modes

Given the above derivatives, plus mass properties (Ixx, Iyy, Izz, mass, CG) and flight condition (V, ρ, α_trim), CHENG assembles the linearized equations of motion and computes eigenvalues. This section specifies the modes, their interpretation, and the applicable handling quality thresholds.

#### 4.4.1 Longitudinal Modes

The longitudinal motion is described by the 4×4 state matrix A_long in the state vector [u, w, q, θ] (or equivalently [ΔV, Δα, Δq, Δθ]). The eigenvalues of A_long yield two complex pairs corresponding to the short-period and phugoid modes.

**Short-Period Mode:**

- Physical description: Rapid pitch oscillation at nearly constant airspeed. The aircraft nose bobs up and down. AoA changes quickly while speed remains almost constant.
- Typical frequency: ωn = 2–15 rad/s (period 0.4–3 seconds) for RC aircraft
- Typical damping: ζ = 0.5–0.9 (well damped)
- Governing derivatives: Cmα (stiffness), Cmq + Cmα̇ (damping), Iyy (inertia)

Approximate formulas (short-period approximation, from MIT OCW 16.333):
```
ωn_sp² = (q_bar * S_w * c_bar / (Iyy)) * (-Cm_alpha / (c_bar/(2V)))
        = (-Cm_alpha * q_bar * S_w * c_bar) / Iyy * (2V/c_bar)

  Simplified: ωn_sp ≈ sqrt(q_bar * S_w * c_bar * (-Cmα) / Iyy)

2*ζ_sp*ωn_sp = (q_bar * S_w * c_bar / (2*V*Iyy)) * (-(Cm_q + Cm_alphadot) * c_bar / (2V))
               + (q_bar * S_w / m) * (-CL_alpha / (2V))

  where q_bar = ½ρV²
```

**Phugoid Mode:**

- Physical description: Slow pitch-speed-altitude exchange. The aircraft climbs, slows, descends, accelerates, repeating. Altitude varies significantly; AoA barely changes.
- Typical frequency: ωn = 0.05–0.5 rad/s (period 10–120 seconds)
- Typical damping: ζ = 0.01–0.1 (lightly damped — most RC pilots constantly correct for this)
- Governing derivatives: CD0 (damping), CL0/V (frequency), mass

Lanchester's approximation (classical):
```
ωn_phugoid ≈ g*sqrt(2) / V_trim

ζ_phugoid ≈ CD0 / (CL_trim * sqrt(2))
           = 1 / (L/D * sqrt(2))

Period_phugoid = 2π / ωn_phugoid ≈ π*V_trim*sqrt(2) / g  [seconds]
```

Note: Lanchester's formula is independent of DATCOM derivatives but is the standard textbook approximation. For improved accuracy, the full 4×4 eigenvalue solution should be used.

#### 4.4.2 Lateral/Directional Modes

The lateral motion is described by the 4×4 state matrix A_lat in [β, p, r, φ] (sideslip, roll rate, yaw rate, bank angle). The eigenvalues yield one complex pair (Dutch roll) and two real roots (roll mode, spiral mode).

**Dutch Roll Mode:**

- Physical description: Coupled yaw-roll oscillation. The aircraft yaws right while rolling left, then yaws left while rolling right. Annoying on RC aircraft; dangerous if divergent.
- Typical frequency: ωn = 1–5 rad/s (period 1–6 seconds)
- Typical damping: ζ = 0.05–0.3 (lightly damped; ζ < 0 = divergent Dutch roll)
- Governing derivatives: Cnβ (frequency/stiffness), Cnr (yaw damping), Clβ, Clr (coupling)

Approximate formula:
```
ωn_dr² ≈ (q_bar * S_w * b / Izz) * Cn_beta

ζ_dr ≈ -(Cn_r * q_bar * S_w * b²) / (2 * V * Izz * ωn_dr)
       - (Cl_beta * Cl_r / Cl_p) * correction_term

  [Simplified — full solution requires 4×4 eigenvalue of A_lat]
```

For implementation, the full eigenvalue solution of A_lat is recommended over approximations for Dutch roll, as the approximations are less reliable when Clβ/Cnβ ratio is large (common in high-dihedral RC designs).

**Roll Mode:**

- Physical description: First-order decay of roll rate when aileron is neutralized. Not an oscillation — just a time constant τ_roll.
- Typical time constant: τ_roll = 0.1–0.5 s (shorter = more responsive)
- Governing derivative: Clp (roll damping), Ixx (roll inertia)

Formula:
```
τ_roll = -Ixx / (q_bar * S_w * b² * Cl_p / (2V))
       = -2*V*Ixx / (q_bar * S_w * b² * Cl_p)

  [Cl_p is negative, so τ_roll is positive]
```

**Spiral Mode:**

- Physical description: Very slow divergence or convergence from a banked turn. If unstable, the bank angle slowly increases without pilot input — "death spiral." Most light aircraft have mildly unstable spiral modes (time to double > 20 s) which pilots easily control.
- Typical time to double/halve: 20 s – ∞ (stable or very slowly unstable)
- Governing: Balance of Clβ (rolls into bank) vs Cnβ*Clr - Clβ*Cnr

Approximate stability criterion (Routh criterion applied to lateral quartic):
```
Spiral stable if:  Cl_beta * Cn_r > Cn_beta * Cl_r

Spiral time constant: τ_spiral = -2*V*Izz / (q_bar * S_w * b * (Cl_beta*Cn_r - Cn_beta*Cl_r) / Cl_p)
  [Positive τ = stable; negative τ = divergent; display as "time to double" if divergent]
```

#### 4.4.3 Handling Quality Criteria

Full MIL-SPEC criteria (MIL-F-8785C / MIL-HDBK-1797) apply to manned aircraft and are not directly applicable to RC aircraft. However, the boundary values are still useful as design guidance. CHENG should display these as informational thresholds, not pass/fail grades.

| Mode | Parameter | RC Guideline (Level 1 analogue) | Basis |
|------|-----------|--------------------------------|-------|
| Short-period | ζ | 0.35 – 1.30 | MIL-F-8785C Category B |
| Short-period | ωn (rad/s) | 1.0 – 10.0 | Engineering judgment for RC |
| Phugoid | ζ | > 0.04 (just positive) | MIL-F-8785C Level 3 minimum |
| Dutch roll | ζ | > 0.08 | MIL-F-8785C 3.3.1.1 |
| Dutch roll | ζ*ωn | > 0.15 rad/s | MIL-F-8785C 3.3.1.1 |
| Dutch roll | ωn | > 0.4 rad/s | MIL-F-8785C 3.3.1.1 |
| Roll mode | τ (s) | < 1.0 | MIL-F-8785C 3.3.1.4 |
| Spiral mode | t₂ (s) | > 12 (mild divergence OK) | MIL-F-8785C 3.3.1.3 |

---

### 4.5 Flight Condition Inputs

Two new user inputs are needed for dynamic stability analysis:

| Field ID | Name | Param name | Unit | Default | Range |
|----------|------|-----------|------|---------|-------|
| FC01 | Cruise Airspeed | `flight_speed_ms` | m/s | 15.0 | 5–80 |
| FC02 | Flight Altitude | `flight_altitude_m` | m | 0 (sea level) | 0–3000 |

These should be added to `AircraftDesign` as optional fields with defaults. The UI should show airspeed in both m/s and km/h (or mph with the unit toggle), as RC pilots typically think in km/h or mph.

**Derived flight condition quantities** (computed in `datcom.py`, not user-editable):

```python
# ISA atmosphere model (simplified, valid to 11,000m)
T = 288.15 - 0.0065 * altitude_m      # Temperature (K)
rho = 1.225 * (T / 288.15)**4.256     # Air density (kg/m³)
q_bar = 0.5 * rho * V**2              # Dynamic pressure (Pa)

# Trim condition
CL_trim = mass_kg * g / (q_bar * S_w_m2)
alpha_trim_rad = CL_trim / CL_alpha   # Small angle assumption
```

Where V = `flight_speed_ms`, S_w_m2 is the wing area in m² (convert from mm²), and g = 9.81 m/s².

**Stall check:** If CL_trim > CL_max (approximate CL_max ≈ 1.2 for NACA-4-series, 1.0 for flat plate), the flight condition is below stall speed and derivatives are meaningless. Emit a warning.

---

### 4.6 Backend Requirements

#### 4.6.1 New Module: `backend/datcom.py`

New pure-math module with the following public API:

```python
from backend.models import AircraftDesign
from backend.mass_properties import MassProperties  # Feature A

@dataclass
class FlightCondition:
    speed_ms: float        # True airspeed
    altitude_m: float      # Altitude for ISA density
    rho: float             # Computed air density (kg/m³)
    q_bar: float           # Dynamic pressure (Pa)
    CL_trim: float         # Trim lift coefficient
    alpha_trim_rad: float  # Trim AoA (rad)

@dataclass
class StabilityDerivatives:
    # Longitudinal
    CL_alpha: float        # /rad
    CD_alpha: float        # /rad
    Cm_alpha: float        # /rad (negative = stable)
    CL_q: float            # /rad
    Cm_q: float            # /rad (negative = damping)
    CL_alphadot: float     # /rad
    Cm_alphadot: float     # /rad
    # Lateral/Directional
    CY_beta: float         # /rad
    Cl_beta: float         # /rad (negative = stable)
    Cn_beta: float         # /rad (positive = stable)
    CY_p: float            # /rad
    Cl_p: float            # /rad (negative = damping)
    Cn_p: float            # /rad
    CY_r: float            # /rad
    Cl_r: float            # /rad
    Cn_r: float            # /rad (negative = damping)

@dataclass
class DynamicModes:
    # Longitudinal
    sp_omega_n: float      # Short-period natural frequency (rad/s)
    sp_zeta: float         # Short-period damping ratio
    sp_period_s: float     # Short-period period (s)
    phugoid_omega_n: float # Phugoid natural frequency (rad/s)
    phugoid_zeta: float    # Phugoid damping ratio
    phugoid_period_s: float# Phugoid period (s)
    # Lateral/Directional
    dr_omega_n: float      # Dutch roll natural frequency (rad/s)
    dr_zeta: float         # Dutch roll damping ratio
    dr_period_s: float     # Dutch roll period (s)
    roll_tau_s: float      # Roll mode time constant (s)
    spiral_tau_s: float    # Spiral time constant (s, positive=stable, negative=divergent)
    spiral_t2_s: float     # Time to double amplitude if divergent (s), inf if stable
    # Metadata
    derivatives_estimated: bool = True  # Always True — DATCOM is empirical

def compute_stability_derivatives(
    design: AircraftDesign,
    mass_props: MassProperties,
    flight_cond: FlightCondition,
) -> StabilityDerivatives: ...

def compute_dynamic_modes(
    design: AircraftDesign,
    mass_props: MassProperties,
    flight_cond: FlightCondition,
    derivs: StabilityDerivatives,
) -> DynamicModes: ...

def compute_flight_condition(design: AircraftDesign, mass_props: MassProperties) -> FlightCondition: ...
```

#### 4.6.2 Implementation Notes

- All units in SI internally (kg, m, rad, s, Pa). Convert from `AircraftDesign` mm to m at function entry.
- Wing area in m²: `S_w = design.wing_area_mm2 * 1e-6`  (from `DerivedValues.wing_area_cm2 * 1e-4`)
- Tail areas: `S_h = h_stab_span * h_stab_chord * 1e-6`, `S_v = 0.8 * v_stab_root_chord * v_stab_height * 1e-6`
- MAC in m: `c_bar = mean_aero_chord_mm * 1e-3`
- Span in m: `b = wing_span * 1e-3`
- The eigenvalue computation for `DynamicModes` requires assembling the 4×4 A_long and A_lat matrices. Use `numpy.linalg.eig()`. This is the only numpy dependency needed.
- All DATCOM formulas must have a citation comment pointing to the specific section number, e.g.:

```python
# DATCOM Section 4.1.3.2 — Subsonic wing lift curve slope (Polhamus formula)
a_w = (2 * math.pi * AR) / (2 + math.sqrt(4 + AR**2 * (1 + (math.tan(sweep_half_chord_rad))**2 / beta**2)))
```

- V-tail handling: Use the existing `_tail_volume_h` and `_tail_volume_v` projections already in `stability.py` as the effective S_h and S_v for the derivative formulas.
- Flying wing: Omit tail contributions. Elevon control derivatives replace elevator — this is a more complex case. For BWB preset, emit a "V44: Flying wing dynamic analysis is approximate" warning.

#### 4.6.3 Integration with Engine

`compute_derived_values()` in `backend/geometry/engine.py` should call the datcom module as a final step after existing static stability computation:

```python
# After compute_static_stability():
if design.flight_speed_ms is not None:
    mass_props = resolve_mass_properties(design, derived)
    fc = compute_flight_condition(design, mass_props)
    derivs = compute_stability_derivatives(design, mass_props, fc)
    modes = compute_dynamic_modes(design, mass_props, fc, derivs)
    # Add to DerivedValues or a new DynamicStabilityResult model
```

Dynamic stability results should be added to either `DerivedValues` (if few fields) or a new `DynamicStabilityResult` sub-model nested in the WebSocket JSON trailer.

#### 4.6.4 Accuracy Notes

Each computed derivative should have an internally tracked uncertainty flag. The public-facing model includes:

```python
derivatives_estimated: bool = True  # Always True — DATCOM is semi-empirical
```

The frontend must display an "Estimated" badge on all derivative and mode values.

---

### 4.7 Frontend Requirements

#### 4.7.1 Panel Structure

Extend the existing `StabilityPanel.tsx` with a new **"Dynamic Stability"** section below the existing static stability gauges. The section should be collapsible (use `<details>` consistent with the existing "Raw Values" section).

Alternatively, if the panel becomes too crowded, a separate **"Dynamic"** sub-tab alongside the existing static stability content is acceptable. This is a product design decision for the UI team.

#### 4.7.2 Flight Condition Input Fields

Two small input fields at the top of the dynamic section:

```
Airspeed: [_____] m/s  (≈ [converted] km/h)
Altitude: [_____] m    (≈ [converted] ft)
```

These should use standard ParamSlider components if sliders are desired, or compact number inputs. Changes trigger WebSocket re-send (same as any design param change — no special handling needed since they'll be in `AircraftDesign`).

#### 4.7.3 Mode Display Cards

Each dynamic mode should be displayed as a compact card:

```
┌─ Short-Period ─────────────────────────────────────┐
│  ωn: 3.4 rad/s    ζ: 0.72    Period: 1.8 s        │
│  [●●●● Good] — Well damped oscillation             │
└─────────────────────────────────────────────────────┘

┌─ Phugoid ──────────────────────────────────────────┐
│  ωn: 0.14 rad/s   ζ: 0.06    Period: 44 s         │
│  [●○○○ Lightly damped] — Manageable with autopilot │
└─────────────────────────────────────────────────────┘

┌─ Dutch Roll ───────────────────────────────────────┐
│  ωn: 2.1 rad/s    ζ: 0.18    Period: 3.0 s        │
│  [●●○○ Marginal] — Meets minimum stability         │
└─────────────────────────────────────────────────────┘

┌─ Roll Mode ────────────────────────────────────────┐
│  τ: 0.24 s                                         │
│  [●●●● Good] — Responsive roll                     │
└─────────────────────────────────────────────────────┘

┌─ Spiral Mode ──────────────────────────────────────┐
│  t₂: 34 s (mildly divergent)                       │
│  [●●●○ Acceptable] — Recoverable with pilot input  │
└─────────────────────────────────────────────────────┘
```

Quality indicator colors:
- Green (●●●●): Meets Level 1 handling quality criteria
- Yellow (●●○○): Meets Level 2 (mildly degraded, flyable)
- Orange (●○○○): Level 3 (controllable but poor)
- Red (○○○○): Outside Level 3 (potentially dangerous)

#### 4.7.4 Estimated Badge

A persistent `ESTIMATED` badge (amber, small) must appear on all dynamic stability values. A tooltip on the badge explains:

> "Dynamic stability values are engineering estimates based on USAF DATCOM empirical methods. They are accurate to ±20–30% for conventional configurations at typical RC speeds. Validate with flight testing before relying on these values for safety-critical decisions."

#### 4.7.5 Stability Derivatives Expandable Section

Below the mode cards, an expandable "Stability Derivatives" section shows the raw derivative values in a table for advanced users who want to verify the computation or export for simulation:

| Derivative | Value | Units |
|-----------|-------|-------|
| CLα | 4.82 | /rad |
| Cmα | -1.23 | /rad |
| Cmq | -12.4 | /rad |
| Cnβ | 0.087 | /rad |
| Clβ | -0.095 | /rad |
| Clp | -0.42 | /rad |
| ... | ... | ... |

#### 4.7.6 New TypeScript Types

Extend `frontend/src/types/design.ts`:

```typescript
export interface DynamicStabilityResult {
  // Modes
  spOmegaN: number;        // rad/s
  spZeta: number;
  spPeriodS: number;       // s
  phugoidOmegaN: number;   // rad/s
  phugoidZeta: number;
  phugoidPeriodS: number;  // s
  drOmegaN: number;        // rad/s
  drZeta: number;
  drPeriodS: number;       // s
  rollTauS: number;        // s
  spiralTauS: number;      // s (positive=stable)
  spiralT2S: number;       // s (time to double; Infinity if stable)
  // Derivatives (for advanced display)
  clAlpha: number;
  cmAlpha: number;
  cmQ: number;
  cyBeta: number;
  clBeta: number;
  cnBeta: number;
  clP: number;
  cnR: number;
  // Metadata
  derivativesEstimated: true;
}
```

`DerivedValues` interface should gain an optional `dynamicStability?: DynamicStabilityResult` field. It is `undefined` when `flight_speed_ms` is not set.

---

### 4.8 Validation Requirements

All new warnings follow the existing non-blocking `ValidationWarning` pattern (level="warn").

| Warning ID | Trigger Condition | Message | Fields |
|-----------|------------------|---------|--------|
| V36 | Short-period ζ < 0.35 | "Short-period mode is lightly damped (ζ={val:.2f}). Aircraft may feel twitchy in pitch. Consider increasing horizontal tail area or arm." | `h_stab_span`, `tail_arm` |
| V37 | Short-period ζ > 1.5 | "Short-period mode is overdamped (ζ={val:.2f}). Pitch response may feel sluggish. Consider decreasing tail area." | `h_stab_span` |
| V38 | Phugoid ζ < 0 | "Phugoid mode is divergent (ζ={val:.2f}). Aircraft will slowly diverge in pitch over cycles of 20–60 seconds." | `wing_incidence`, `battery_position_frac` |
| V39 | Dutch roll ζ < 0 | "Dutch roll mode is divergent. Aircraft will develop increasing yaw-roll oscillations. Increase vertical fin area." | `v_stab_height`, `v_stab_root_chord` |
| V40 | Dutch roll ζ < 0.08 | "Dutch roll is lightly damped (ζ={val:.2f}). May be uncomfortable. Consider increasing vertical fin area." | `v_stab_height` |
| V41 | Spiral t₂ < 8 s | "Spiral mode diverges rapidly (doubles in {t2:.1f}s). Aircraft will tighten into a bank without pilot input." | `wing_dihedral`, `v_stab_height` |
| V42 | Roll τ > 1.0 s | "Roll mode time constant is large ({tau:.2f}s). Roll response will feel sluggish." | `aileron_span_start`, `aileron_chord_percent` |
| V43 | CL_trim > CL_max | "Flight speed {speed:.0f} m/s is below the estimated stall speed. Dynamic analysis invalid at this condition." | `flight_speed_ms` |
| V44 | Flying wing preset | "Dynamic stability analysis for flying-wing configurations is approximate. DATCOM methods assume a conventional aft tail." | `fuselage_preset` |
| V45 | CL_trim < 0.1 | "Aircraft is flying faster than necessary (very low CL_trim). Check cruise speed input." | `flight_speed_ms` |

Note: V41–V43 (mass properties validation) from Section 3.5 use the same ID space — the actual assignment of V41, V42, V43 between Features A and B should be resolved during implementation to avoid conflicts. The numbers above in Section 4.8 assume Feature A uses a separate ID range; coordinate with the validation module maintainer.

---

## 5. Implementation Approach

### 5.1 Phasing Recommendation

The features have a hard dependency: accurate dynamic analysis requires accurate mass properties. The recommended development sequence is:

**Phase 1 — Mass Properties Override (2–3 sprints)**
- Backend: New Pydantic fields (MP01–MP07) in `AircraftDesign`
- Backend: `backend/mass_properties.py` with `estimate_inertia()` and `resolve_mass_properties()`
- Backend: Validation warnings (mass property range checks)
- Frontend: Mass Properties section in Fuselage/Propulsion panel
- Frontend: Override toggle pattern (Estimated / Override)
- Tests: Unit tests for inertia estimation formulas

**Phase 2 — DATCOM Derivatives (2–3 sprints)**
- Backend: `backend/datcom.py` — `StabilityDerivatives`, `FlightCondition`, `compute_stability_derivatives()`
- Backend: Flight condition fields (FC01, FC02) in `AircraftDesign`
- Backend: `compute_flight_condition()` with ISA atmosphere model
- Backend: Integration into `engine.compute_derived_values()`
- Tests: Unit tests comparing derivatives against known reference aircraft (e.g., Cessna 172 published values)

**Phase 3 — Dynamic Modes + Display (2–3 sprints)**
- Backend: `compute_dynamic_modes()` using numpy eigenvalue analysis
- Backend: New `DynamicStabilityResult` model + WebSocket trailer integration
- Backend: Validation warnings V36–V45
- Frontend: Mode display cards in `StabilityPanel.tsx`
- Frontend: TypeScript types, ESTIMATED badge
- Frontend: Derivatives expandable table
- E2E: Playwright tests verifying mode cards appear when flight speed is set

### 5.2 Open Source References

| Project | Language | Description | Relevance |
|---------|----------|-------------|-----------|
| [PyDatcom](https://github.com/arktools/pydatcom) | Python | Interface/parser for Digital DATCOM binary output | Useful for formula cross-reference; not a pure-Python implementation |
| [Digital DATCOM (PDAS)](https://www.pdas.com/datcom.html) | Fortran | Official FORTRAN implementation. PDAS distributes freely. | Reference implementation; not suitable for subprocess use in CHENG |
| [OpenVSP / VSPAERO](https://openvsp.org/) | C++/Python API | Vortex-lattice aerodynamics tool from NASA; Python bindings available | Higher fidelity alternative for derivative computation; substantial integration effort |
| [JSBSim](https://jsbsim.sourceforge.net/) | C++/Python | Full 6-DOF flight dynamics simulator; requires DATCOM-format aerodynamic tables | Overkill for derivative estimation; useful for validation |
| [AeroPython](https://github.com/barbagroup/AeroPython) | Python | Panel method aerodynamics; educational | Cross-check CLα estimates |
| [NACA TN 1428 / ESDU 70011] | — | Lift-curve slope of finite wings at low speed | Basis for subsonic wing CLα formula used in DATCOM 4.1.3.2 |

**Recommendation:** Implement the derivative formulas from scratch in `backend/datcom.py` citing the DATCOM section numbers. Use PyDatcom only as a parser if validation against the FORTRAN output is desired during testing. The pure-Python approach has no external binary dependency and is testable with standard pytest.

### 5.3 DATCOM Publication References

**Primary Reference:**

> Finck, R.D. et al. *USAF Stability and Control DATCOM*. McDonnell Douglas Corporation for the USAF Flight Dynamics Laboratory. AFFDL-TR-79-3032 (Volume I, User's Manual), 1979. Available from DTIC at https://apps.dtic.mil/sti/citations/ADB072483 and from Internet Archive at https://archive.org/details/DTIC_ADB072483.

The document is 3,134 pages (113 MB PDF) comprising five volumes. The 1978 revision is the most complete version.

**Key volumes for this feature:**
- Volume 2 (Section 4): Component aerodynamics — wings, bodies, wing-body combinations
- Volume 3 (Sections 5, 6): Downwash, tail aerodynamics, lateral-directional derivatives
- Volume 4 (Section 7): Dynamic derivatives (pitch damping, roll damping, yaw damping)

**Digital DATCOM User's Manual:**
> Williams, J.E. and Vukelich, S.R. *The USAF Stability and Control Digital DATCOM. Volume I, Users Manual*. McDonnell Douglas Corporation. AFFDL-TR-79-3032, 1979. Available via NTIS at https://ntrl.ntis.gov/NTRL/dashboard/searchResults/titleDetail/ADA086557.xhtml.

**Supporting references:**

> Caughey, D.A. *Introduction to Aircraft Stability and Control*, Cornell MAE 5070 course notes, 2011. (Excellent treatment of short-period/phugoid derivations.) Available at https://courses.cit.cornell.edu/mae5070/Caughey_2011_04.pdf

> MIT OpenCourseWare 16.333. *Approximate Longitudinal Dynamics Models.* Available at https://ocw.mit.edu/courses/16-333-aircraft-stability-and-control-fall-2004/

> Roskam, J. *Airplane Flight Dynamics and Automatic Flight Controls*. DARcorporation, 1979/1995. (Standard reference for lateral-directional approximations.)

> Nelson, R.C. *Flight Stability and Automatic Control*, 2nd ed. McGraw-Hill, 1998. (Standard undergraduate text; all mode formulas derivable from here.)

### 5.4 Technical Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DATCOM lift slope inaccurate at Re < 200,000 | High | Medium | Display ESTIMATED badge on all values; add UI note for sub-200g aircraft |
| Propwash over tail not modeled (tractor configs) | High | Medium | Add design note warning for tractor motors: "Propwash increases Cmq and CLq by an estimated 20–40%. Dynamic values may be optimistic." |
| Inertia estimation error > 50% | Medium | High | Phase 1 (mass override) before Phase 2/3; encourage users to use swingweight testing. Document estimation method clearly. |
| numpy eigenvalue solver instability for degenerate configs | Low | Medium | Wrap eig() in try/except; return NaN modes with "Analysis failed" UI state |
| Flying wing derivative estimation unreliable | High | Low | V44 warning; clearly label BWB results as "low confidence" |
| User confusion between static and dynamic stability | Medium | Medium | Keep static stability gauges visually prominent; make dynamic section clearly secondary; add tooltip explaining the difference |
| Stall condition at low speed | Medium | Medium | V43 warning; gray out mode cards and show "Increase airspeed above stall speed" |
| Short-period formula fails for very low Cmα (near-neutral) | Low | Low | Guard: if |Cmα| < 0.01, display "Near-neutral — short period analysis unreliable" |

---

## 6. Out of Scope

The following items are explicitly out of scope for this feature and should not be included in the implementation:

- **CFD or panel-method aerodynamics** — VSPAERO, OpenFOAM, or any numerical flow solver. DATCOM empirical methods only.
- **Aeroelastic effects** — wing bending, torsional divergence, flutter. 3D-printed structures are assumed rigid.
- **Propulsion coupling** — thrust vectoring, gyroscopic effects of spinning props, propwash beyond the design note in Section 5.4.
- **Nonlinear simulation / ODE integration** — time-domain flight simulation (JSBSim territory).
- **Products of inertia** — Ixy, Ixz, Iyz. Assumed zero (symmetric aircraft).
- **Control surface effectiveness derivatives** — CLδe, Cmδe, Clδa, Cnδr. These require additional control power analysis that is a separate feature.
- **Multi-engine configurations** — the current `engine_count` field already has `le=1`. Out of scope.
- **Transonic and supersonic flight** — DATCOM has methods for M > 0.8 but RC aircraft never reach these speeds.
- **Fuel state changes** — RC aircraft have fixed battery weight; CG shift during flight is negligible.

---

## 7. Acceptance Criteria

### Feature A — Mass Properties Override

- [ ] `AircraftDesign` accepts all MP01–MP07 fields as Optional[float] with None defaults
- [ ] Existing designs without these fields load without error (backward compatibility)
- [ ] When override fields are None, `resolve_mass_properties()` returns the geometric estimate
- [ ] When override fields are set, `resolve_mass_properties()` returns the override values
- [ ] `estimate_inertia()` returns physically plausible values for all 6 built-in presets (Ixx < Iyy for all conventional configs; Iyy < Izz for all conventional configs)
- [ ] UI shows "Estimated" and "Override" toggle for mass, CG position, and each inertia axis
- [ ] Override values are persisted in design JSON and round-trip correctly through save/load
- [ ] V41 (mass discrepancy > 40%) fires when override differs substantially from estimate
- [ ] V42 (CG discrepancy) fires when override CG is far from geometric estimate
- [ ] Unit display shows grams and ounces for mass; mm and inches for CG offsets; kg·m² and g·cm² for inertia

### Feature B — DATCOM Dynamic Stability

- [ ] `backend/datcom.py` exists and exports `compute_stability_derivatives()`, `compute_dynamic_modes()`, `compute_flight_condition()`
- [ ] All formulas have DATCOM section citation comments
- [ ] `compute_stability_derivatives()` returns all 16 derivatives for a conventional design
- [ ] CLα for a rectangular AR=6 unswept wing is within 5% of 2πAR/(2+AR) at M=0 (Prandtl-Glauert limit)
- [ ] Cmq is negative for all CHENG presets (damping, not destabilizing)
- [ ] Cnβ is positive for all CHENG presets with a vertical tail (directionally stable)
- [ ] `compute_dynamic_modes()` returns valid (non-NaN) modes for all 6 built-in presets at their design cruise speed
- [ ] Short-period ωn and ζ are positive and finite for all stable configurations
- [ ] Phugoid period is within 20% of Lanchester's formula `2π*V/(g*sqrt(2))` for a clean configuration
- [ ] `DynamicStabilityResult` appears in the WebSocket JSON trailer when `flight_speed_ms` is non-null
- [ ] Frontend renders mode cards for all 5 modes
- [ ] ESTIMATED badge is visible on all dynamic values
- [ ] Validation warnings V36–V45 fire at the correct threshold conditions
- [ ] V43 fires when trim CL exceeds 1.3 (below stall speed)
- [ ] All new backend tests pass: `python -m pytest tests/backend/ -v` (>800 tests total)
- [ ] No regression in existing 782 backend tests
- [ ] Playwright E2E: With Trainer preset and `flight_speed_ms=12`, the Dynamic Stability section appears with 5 mode cards
- [ ] The "Analysis requires airspeed" placeholder is shown when `flight_speed_ms` is null

---

## 8. Glossary

| Term | Definition |
|------|-----------|
| **Static Margin** | Distance from CG to Neutral Point, expressed as percentage of MAC. Positive = pitch-stable. Existing CHENG metric. |
| **Neutral Point (NP)** | Longitudinal position along the aircraft where an angle-of-attack change produces no change in pitching moment. CG must be forward of NP for static stability. |
| **Center of Gravity (CG)** | The point through which the total weight of the aircraft acts. A key variable in both static and dynamic stability. |
| **Ixx** | Moment of inertia about the longitudinal (roll) axis. Governs roll mode time constant and Dutch roll. Units: kg·m². For a 1000mm RC trainer, typically 0.003–0.015 kg·m². |
| **Iyy** | Moment of inertia about the lateral (pitch) axis. Governs short-period and phugoid frequencies. Typically 0.006–0.030 kg·m² for the same trainer. |
| **Izz** | Moment of inertia about the vertical (yaw) axis. Governs Dutch roll and spiral modes. Typically Izz ≈ Ixx + Iyy for conventional aircraft (Huygens-Steiner). |
| **CLα** | Lift curve slope — rate of change of total aircraft lift coefficient with angle of attack (1/rad). Typically 4–6 /rad for RC-scale aircraft. |
| **Cmα** | Pitching moment slope — rate of change of pitching moment coefficient with AoA. Must be negative for pitch stability. Directly proportional to negative static margin. |
| **Short-Period Mode** | Rapid (0.5–3 second period), well-damped longitudinal oscillation in pitch angle and angle of attack at nearly constant airspeed. Governs "feel" of pitch response. |
| **Phugoid Mode** | Slow (10–120 second period), lightly-damped longitudinal oscillation exchanging kinetic and potential energy. Pilot corrects for this continuously without usually noticing. |
| **Dutch Roll Mode** | Coupled yaw-roll oscillation (1–6 second period). Named for the motion resembling a Dutch speed skater. Can be uncomfortable or dangerous if underdamped. |
| **Roll Mode** | First-order (non-oscillatory) convergence of roll rate when controls are neutralized. Characterized by time constant τ (seconds). Shorter τ = more responsive roll. |
| **Spiral Mode** | Very slow (20s–∞) first-order convergence or divergence of bank angle. If divergent (unstable spiral), the aircraft slowly tightens a turn without pilot input. |
| **Damping Ratio (ζ)** | Ratio describing how quickly an oscillation decays. ζ=0: undamped (sustained oscillation); ζ=1: critically damped (fastest non-oscillatory return); ζ>1: overdamped; ζ<0: divergent. |
| **Natural Frequency (ωn)** | Frequency of oscillation in rad/s in the undamped case. Related to period by T = 2π/ωd where ωd = ωn√(1-ζ²). |
| **DATCOM** | USAF Stability and Control Data Compendium. A handbook of empirical and semi-analytical methods for estimating aerodynamic stability derivatives from aircraft geometry alone, without wind tunnel testing. |
| **Stability Derivative** | A partial derivative describing how a force or moment coefficient changes with a particular motion variable (e.g., Cmq = ∂Cm/∂(qc̄/2V)). These populate the equations of motion. |
| **Trim Condition** | The steady flight state about which linearization occurs. Defined by airspeed, altitude, and the angle of attack required to maintain level flight (CL = W/qS). |
| **Dynamic Pressure (q̄)** | ½ρV². The pressure available for generating aerodynamic forces. All force/moment coefficients are normalized by q̄ × reference area (or area × length). |

---

*Document ends.*

*References for further reading:*
- *USAF DATCOM on DTIC:* https://apps.dtic.mil/sti/citations/ADB072483
- *Digital DATCOM description:* https://www.pdas.com/datcomDescription.html
- *Wikipedia DATCOM overview:* https://en.wikipedia.org/wiki/USAF_Stability_and_Control_DATCOM
- *Aircraft dynamic modes:* https://en.wikipedia.org/wiki/Aircraft_dynamic_modes
- *MIL-F-8785C handling qualities (DTIC):* https://apps.dtic.mil/sti/tr/pdf/ADA319979.pdf
- *Cornell MAE 5070 Dynamic Stability notes:* https://courses.cit.cornell.edu/mae5070/DynamicStability.pdf
- *MIT 16.333 Longitudinal Approximations:* https://ocw.mit.edu/courses/16-333-aircraft-stability-and-control-fall-2004/
