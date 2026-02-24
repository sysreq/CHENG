# CHENG MVP Specification

> **Canonical Reference Document — v0.1.0**
>
> This document is the single source of truth for MVP implementation of CHENG (Parametric RC Plane Generator). It resolves all discrepancies found across the 5 primary design documents and 3 cross-review documents. During development, if any other document conflicts with this spec, **this spec wins**.

---

## 1. MVP Overview

**Product Vision:** CHENG is a containerized web application that enables hobbyists to design fully parametric, 3D-printable RC aircraft. Users adjust high-level parameters (wingspan, airfoil, tail configuration) and the system generates a complete, printable airframe as sectioned STL files ready for home FDM printers.

**Target Users:**

- **Primary — Beginner Builder (Alex persona):** First-time RC builder with basic 3D printing experience. Needs guided workflow, sensible defaults, and clear visual feedback. Should not need to understand aerodynamic theory to produce a flyable plane.
- **Secondary — Experienced Hobbyist (Jordan persona):** Has built kits before and wants fine-grained control. Uses CHENG to rapidly prototype custom designs before committing to a build.

**Success Criteria:** A first-time user can go from idea to printable STL in **under 10 minutes**.

**Deployment:** Local Docker container only. Launch with:

```bash
docker run -p 8000:8000 -v ~/.cheng:/data cheng
```

Cloud Run deployment is deferred to 1.0.

---

## 2. Resolved Decisions

This section documents every discrepancy found across the 8 source documents, with the canonical resolution and rationale. These decisions are final for MVP and should not be re-litigated without new evidence.

| # | Issue | Resolution | Rationale |
|---|-------|-----------|-----------|
| 1 | Parameter count (49 vs 43) | **43 user-configurable** | Accept PM's 7 cuts (W08, W06, T15, F05, F06, F07, PR21) — all have safe defaults that work for all 3 presets |
| 2 | W07 wingDihedral phasing | **Promote to MVP** | 2 reviewers agree; high visual impact on model, simple single-value input, critical for trainer stability |
| 3 | G08 aircraftPreset | **MVP with 3 presets** (Trainer, Sport, Aerobatic) | PRD requires it; essential for beginner onboarding — eliminates blank-canvas paralysis |
| 4 | W04 wingTipRootRatio default | **Change to 1.0** | Rectangular wing is beginner-friendly; presets can override (Sport uses 0.67) |
| 5 | D01–D04 derived values | **Display in MVP** (read-only) | Trivial to compute, high educational value, requested by both aero and UX reviewers |
| 6 | P02 motorConfig location | **Add to Global panel** | "Nose (Tractor) / Rear (Pusher)" dropdown next to engine count — affects fuselage geometry |
| 7 | F01 fuselageLength location | **Add to Global panel** | Most critical fuselage parameter for MVP; cross-review flagged it as missing from Global |
| 8 | Tail span in Global panel | **Remove from Global** | Keep only in Tail component panel — reduces Global panel clutter |
| 9 | Chord fields in Global panel | **Single root chord** | Tip chord derived via Tip/Root Ratio in wing panel; avoids confusing beginners with two chord inputs |
| 10 | Node base image (node:22-slim vs node:22-alpine) | **node:22-alpine** | Smaller image, sufficient for build stage, faster CI |
| 11 | Storage class names (ABC vs Protocol) | **Protocol + LocalStorage** | `Protocol` is more Pythonic than ABC for structural subtyping |
| 12 | docker-compose frontend (separate Dockerfile vs inline) | **Inline node:22-alpine** | Simpler; no extra Dockerfile needed for dev frontend |
| 13 | Cloud Run concurrency (4 vs 10) | **4** | Conservative for CadQuery memory usage (~200–500 MB per operation). Deferred to 1.0 |
| 14 | Cloud Run timeout (300s vs 3600s) | **3600s** | WebSocket connections need long-lived support. Deferred to 1.0 |
| 15 | CadQuery concurrency control | **Explicit CapacityLimiter(4)** | Prevents OOM on memory-constrained systems; shared across REST, WebSocket, and export paths |
| 16 | Port number | **8000** | Both docs already agree; single port serves everything |
| 17 | Parameter naming (technical vs beginner-friendly) | **Defer renaming to 1.0** | MVP ships with standard aero terms + tooltips; full rename requires UX testing |
| 18 | Print params location (panels vs export dialog) | **Export dialog, not component panels** | Exception: wall thickness stays as read-only info in fuselage panel |
| 19 | Test joint feature | **Defer to 1.0** | Good idea but not blocking for MVP launch |
| 20 | Bidirectional param UI pattern | **Defer to 1.0** | MVP shows both fields, simple recalc, no toggle — full bidirectional editing adds complexity |
| 21 | CG (center of gravity) calculator | **Add simplified D05 to MVP** | Full CG calculator deferred to 1.0, but a simple 25% MAC balance-point estimate is trivial to compute and essential — without it, beginners cannot balance a flyable plane |

---

## 3. Canonical MVP Parameter List

This section defines every parameter the MVP exposes. Parameters are organized by the UI panel in which they appear. The table is the single source of truth; all other documents, code, and tests must agree with it.

**Conventions**

- **ID** uses the prefix of its subsystem (`G` = Global, `W` = Wing, `T` = Tail, `F` = Fuselage, `P` = Propulsion, `PR` = Print/Export, `D` = Derived).
- **Type** is one of: `dropdown`, `numeric`, `numeric(int)`, `slider`, `toggle`, `computed`.
- **Range** for dropdowns lists the legal enum values; for numerics it is `[min, max]`.
- **Panel Location** is where the parameter is displayed and edited in the UI.
- **Derived / read-only** rows are shaded with a `(read-only)` suffix and cannot be edited by the user.

---

### 3.1 Global Panel

These parameters establish the overall aircraft configuration. Changing a Global parameter may trigger recomputation of derived values in component panels.

| # | ID | Name | Display Label | Type | Default | Range / Options | Unit | Panel |
|---|-----|------|---------------|------|---------|-----------------|------|-------|
| 1 | G01 | fuselagePreset | Fuselage | dropdown | Conventional | Pod, Conventional, Blended-Wing-Body | — | Global |
| 2 | G02 | engineCount | Engines | numeric(int) | 1 | 0–4 | — | Global |
| 3 | P02 | motorConfig | Motor Position | dropdown | Tractor | Nose (Tractor), Rear (Pusher) | — | Global |
| 4 | G03 | wingSpan | Wingspan | numeric | 1000 | 300–3000 | mm | Global |
| 5 | G05 | wingChord | Wing Root Chord | numeric | 180 | 50–500 | mm | Global |
| 6 | F13 | wingMountType | Wing Position | dropdown | High-Wing | High-Wing, Mid-Wing, Low-Wing, Shoulder-Wing | — | Global |
| 7 | F01 | fuselageLength | Fuselage Length | numeric | 300 | 150–2000 | mm | Global |
| 8 | G06 | tailType | Tail Type | dropdown | Conventional | Conventional, T-Tail, V-Tail, Cruciform | — | Global |

> **Note on G05 wingChord:** This is the *root* chord. The tip chord is derived as `G05 × W04` and displayed read-only in the Wing panel (see W03 below). There is no separate tip chord input in the Global panel.

---

### 3.2 Wing Component Panel

The Wing panel contains 5 user-editable parameters plus 4 read-only derived values. The derived values update in real time as the user adjusts wing geometry.

| # | ID | Name | Display Label | Type | Default | Range / Options | Unit | Panel |
|---|-----|------|---------------|------|---------|-----------------|------|-------|
| 9 | W12 | wingAirfoil | Airfoil | dropdown | Clark-Y | Flat-Plate, NACA-0012, NACA-2412, NACA-4412, NACA-6412, Clark-Y, Eppler-193, Eppler-387, Selig-1223, AG-25 | — | Wing |
| 10 | W05 | wingSweep | Sweep | numeric | 0 | −10–45 | deg | Wing |
| 11 | W04 | wingTipRootRatio | Tip/Root Ratio | slider | 1.0 | 0.3–1.0 | — | Wing |
| 12 | W07 | wingDihedral | Dihedral | numeric | 3 | −10–15 | deg (per panel) | Wing |
| 13 | W20 | wingSkinThickness | Skin Thickness | numeric | 1.2 | 0.8–3.0 | mm | Wing |
| — | W03 | wingTipChord | Tip Chord *(read-only)* | computed | — | — | mm | Wing |
| — | D01 | wingArea | Wing Area *(read-only)* | computed | — | — | cm² | Wing |
| — | D02 | aspectRatio | Aspect Ratio *(read-only)* | computed | — | — | — | Wing |
| — | D03 | meanAeroChord | Mean Aero Chord *(read-only)* | computed | — | — | mm | Wing |
| — | D04 | taperRatio | Taper Ratio *(read-only)* | computed | — | — | — | Wing |
| — | D05 | estimatedCG | Balance Point *(read-only)* | computed | — | — | mm from wing LE | Wing |

**Derived value formulas:**

```
W03  wingTipChord    = G05 × W04
D01  wingArea        = 0.5 × (G05 + W03) × G03          [result in mm², display as cm²]
D02  aspectRatio     = G03² / D01_mm²
D03  meanAeroChord   = (2/3) × G05 × (1 + λ + λ²) / (1 + λ)    where λ = W04
D04  taperRatio      = W03 / G05                                  (equivalent to W04)
D05  estimatedCG     = 0.25 × D03                                 [distance aft of wing LE at root, mm]
```

> **Note on W07 wingDihedral:** The value is the angle *per panel* (per side), not the total included angle. A value of 3 means each wing panel is tilted 3 degrees upward from horizontal.

> **Note on D04:** In the MVP, `taperRatio` is numerically identical to `wingTipRootRatio` (W04). It is displayed separately to match standard aerodynamic notation. If independent tip chord editing is added in 1.0 (bidirectional param pattern), D04 and W04 may diverge.

> **Note on D05 estimatedCG:** This is the recommended balance point using the standard 25% MAC rule of thumb. The display text should read e.g. "Balance at 50 mm from wing leading edge." This gives beginners the critical information needed to balance the assembled model for flight, without requiring them to understand CG theory. A full CG calculator (accounting for component weights, battery placement, etc.) is deferred to 1.0.

---

### 3.3 Tail Component Panel — Conventional / T-Tail / Cruciform

When `G06 tailType` is set to Conventional, T-Tail, or Cruciform, the Tail panel shows these 6 user-editable parameters:

| # | ID | Name | Display Label | Type | Default | Range / Options | Unit | Panel |
|---|-----|------|---------------|------|---------|-----------------|------|-------|
| 14 | T02 | hStabSpan | H-Stab Span | numeric | 350 | 100–1200 | mm | Tail |
| 15 | T03 | hStabChord | H-Stab Chord | numeric | 100 | 30–250 | mm | Tail |
| 16 | T06 | hStabIncidence | H-Stab Incidence | numeric | −1 | −5–5 | deg | Tail |
| 17 | T09 | vStabHeight | Fin Height | numeric | 100 | 30–400 | mm | Tail |
| 18 | T10 | vStabRootChord | Fin Root Chord | numeric | 110 | 30–300 | mm | Tail |
| 19 | T22 | tailArm | Tail Arm | numeric | 180 | 80–1500 | mm | Tail |

> **Note on T22 tailArm vs. F01 fuselageLength:** Tail arm is the distance from the wing's aerodynamic center to the tail's aerodynamic center — it is independent of fuselage length. If `tailArm > fuselageLength`, the tail extends beyond the fuselage (physically unrealistic). A validation warning (V06) fires in this case. In the MVP, these parameters are not auto-linked; presets provide sensible pairings, and the warning catches user errors.

---

### 3.4 Tail Component Panel — V-Tail

When `G06 tailType` is set to V-Tail, the Tail panel swaps to show these 5 user-editable parameters (the conventional H-stab and V-stab fields are hidden):

| # | ID | Name | Display Label | Type | Default | Range / Options | Unit | Panel |
|---|-----|------|---------------|------|---------|-----------------|------|-------|
| 20 | T14 | vTailDihedral | V-Tail Dihedral | numeric | 35 | 20–60 | deg | Tail |
| 21 | T16 | vTailSpan | V-Tail Span | numeric | 280 | 80–600 | mm | Tail |
| 22 | T17 | vTailChord | V-Tail Chord | numeric | 90 | 30–200 | mm | Tail |
| 23 | T18 | vTailIncidence | V-Tail Incidence | numeric | 0 | −3–3 | deg | Tail |
| 19 | T22 | tailArm | Tail Arm | numeric | 180 | 80–1500 | mm | Tail |

> **Conditional visibility:** At any given time, the user sees either params 14–19 (conventional/T-tail/cruciform) **or** params 19–23 (V-tail), never both. T22 `tailArm` appears in both layouts.

---

### 3.5 Export Dialog

These parameters appear in the Export/Print dialog, not in the component panels. They control how the 3D model is sectioned and prepared for 3D printing.

| # | ID | Name | Display Label | Type | Default | Range / Options | Unit | Panel |
|---|-----|------|---------------|------|---------|-----------------|------|-------|
| 24 | PR01 | printBedX | Print Bed X | numeric | 220 | 100–500 | mm | Export |
| 25 | PR02 | printBedY | Print Bed Y | numeric | 220 | 100–500 | mm | Export |
| 26 | PR03 | printBedZ | Print Bed Z | numeric | 250 | 50–500 | mm | Export |
| 27 | PR04 | autoSection | Auto-Section | toggle | on | on / off | — | Export |
| 28 | PR05 | sectionOverlap | Joint Overlap | numeric | 15 | 5–30 | mm | Export |
| 29 | PR10 | jointType | Joint Type | dropdown | Tongue-and-Groove | Tongue-and-Groove, Dowel-Pin, Flat-with-Alignment-Pins | — | Export |
| 30 | PR11 | jointTolerance | Joint Tolerance | numeric | 0.15 | 0.05–0.5 | mm | Export |
| 31 | PR06 | nozzleDiameter | Nozzle Diameter | numeric | 0.4 | 0.2–1.0 | mm | Export |
| 32 | PR14 | hollowParts | Hollow Parts | toggle | on | on / off | — | Export |
| 33 | PR09 | trailingEdgeMinThickness | TE Min Thickness | numeric | 0.8 | 0.4–2.0 | mm | Export |
| — | PR08 | minFeatureThickness | Min Feature Thickness *(read-only)* | computed | — | — | mm | Export |

**Derived value formula:**

```
PR08 minFeatureThickness = 2 × PR06
```

---

### 3.6 Implicit / Preset-Controlled Parameters

These parameters exist in the data model but are not directly editable in the MVP. They are controlled by preset selection or have safe defaults.

| ID | Name | Controlled By | MVP Value |
|----|------|---------------|-----------|
| F14 | wallThickness | G01 fuselagePreset | 1.6 mm (Conventional), varies by preset |
| W08 | wingIncidence | Safe default | 2 deg |
| W06 | wingTwist | Safe default | 0 deg |
| T15 | vTailSweep | Safe default | 0 deg |
| F05 | noseLength | Derived from fuselageLength | proportional |
| F06 | cabinLength | Derived from fuselageLength | proportional |
| F07 | tailConeLength | Derived from fuselageLength | proportional |
| PR21 | supportStrategy | Safe default | Normal |

> **Note on F14 wallThickness:** In the MVP it is controlled by the fuselage preset (G01) and displayed as a read-only informational value in the Fuselage component panel. Direct editing of wall thickness is deferred to 1.0.

---

### 3.7 Parameter Count Summary

| Category | Count | Notes |
|----------|-------|-------|
| Global panel — editable | 8 | Always visible |
| Wing panel — editable | 5 | Always visible |
| Tail panel — editable (conventional/T-tail/cruciform) | 6 | Shown when tailType ≠ V-Tail |
| Tail panel — editable (V-tail) | 5 | Shown when tailType = V-Tail |
| Export dialog — editable | 10 | Shown in export flow |
| **Total user-configurable (max visible at once)** | **29** | 8 + 5 + 6 + 10 (conventional) or 8 + 5 + 5 + 10 (V-tail) |
| **Total user-configurable (unique params)** | **33** | Counting both tail layouts; T22 shared |
| Derived / read-only displayed | 8 | W03, D01–D05, PR08, F14 |
| Implicit / hidden safe defaults | 8 | W08, W06, T15, F05–F07, PR21, plus F14 display |
| **Total displayed values** | **~41** | Editable + derived |

---

## 4. Presets

The MVP ships with three aircraft presets accessible via `G08 aircraftPreset` in the Global panel. Selecting a preset populates **all** user-configurable parameters with the values defined below. After loading a preset, the user may freely modify any parameter; the preset serves only as a starting point.

### 4.1 Trainer

**Design intent:** A forgiving, stable platform for first-time RC pilots and beginners learning basic flight maneuvers. The high-wing configuration with generous dihedral provides strong self-correcting roll stability. The rectangular planform (tip/root ratio = 1.0) maximizes lift at low speeds and resists tip stalls. The Clark-Y airfoil provides a good lift-to-drag ratio at low Reynolds numbers typical of this size. The longer fuselage and large tail surfaces increase pitch and yaw damping for docile handling.

**Typical use case:** First build, flight training, slow-speed park flying, teaching aerodynamics fundamentals.

```json
{
  "presetName": "Trainer",
  "presetDescription": "Stable, forgiving high-wing trainer for beginners",

  "G01_fuselagePreset": "Conventional",
  "G02_engineCount": 1,
  "P02_motorConfig": "Tractor",
  "G03_wingSpan": 1200,
  "G05_wingChord": 200,
  "F13_wingMountType": "High-Wing",
  "F01_fuselageLength": 400,
  "G06_tailType": "Conventional",

  "W12_wingAirfoil": "Clark-Y",
  "W05_wingSweep": 0,
  "W04_wingTipRootRatio": 1.0,
  "W07_wingDihedral": 3,
  "W20_wingSkinThickness": 1.2,

  "T02_hStabSpan": 400,
  "T03_hStabChord": 120,
  "T06_hStabIncidence": -1,
  "T09_vStabHeight": 120,
  "T10_vStabRootChord": 130,
  "T22_tailArm": 220,

  "T14_vTailDihedral": 35,
  "T16_vTailSpan": 280,
  "T17_vTailChord": 90,
  "T18_vTailIncidence": 0,

  "PR01_printBedX": 220,
  "PR02_printBedY": 220,
  "PR03_printBedZ": 250,
  "PR04_autoSection": true,
  "PR05_sectionOverlap": 15,
  "PR10_jointType": "Tongue-and-Groove",
  "PR11_jointTolerance": 0.15,
  "PR06_nozzleDiameter": 0.4,
  "PR14_hollowParts": true,
  "PR09_trailingEdgeMinThickness": 0.8
}
```

**Key derived values (computed on load):**

| Derived Param | Value |
|---------------|-------|
| W03 wingTipChord | 200 mm (200 × 1.0) |
| D01 wingArea | 2400 cm² (0.5 × (200 + 200) × 1200 = 240000 mm²) |
| D02 aspectRatio | 6.0 (1200² / 240000) |
| D03 meanAeroChord | 200 mm |
| D04 taperRatio | 1.0 |
| D05 estimatedCG | 50 mm from wing LE (0.25 × 200) |
| PR08 minFeatureThickness | 0.8 mm (2 × 0.4) |

---

### 4.2 Sport

**Design intent:** A versatile mid-wing aircraft suitable for intermediate pilots who want a balance of stability and aerobatic capability. The moderate taper (tip/root ratio = 0.67) improves roll rate and reduces induced drag compared to a rectangular wing, while the 5-degree sweep adds visual appeal and improves directional stability at higher speeds. The NACA-2412 airfoil provides a good compromise between lift generation and inverted flight capability. The mid-wing position allows both upright and inverted maneuvers with similar handling.

**Typical use case:** Intermediate sport flying, basic aerobatics (loops, rolls, split-S), moderate-speed flight, transitioning from trainer to more agile aircraft.

```json
{
  "presetName": "Sport",
  "presetDescription": "Versatile mid-wing sport plane for intermediate pilots",

  "G01_fuselagePreset": "Conventional",
  "G02_engineCount": 1,
  "P02_motorConfig": "Tractor",
  "G03_wingSpan": 1000,
  "G05_wingChord": 180,
  "F13_wingMountType": "Mid-Wing",
  "F01_fuselageLength": 300,
  "G06_tailType": "Conventional",

  "W12_wingAirfoil": "NACA-2412",
  "W05_wingSweep": 5,
  "W04_wingTipRootRatio": 0.67,
  "W07_wingDihedral": 3,
  "W20_wingSkinThickness": 1.2,

  "T02_hStabSpan": 350,
  "T03_hStabChord": 100,
  "T06_hStabIncidence": -1,
  "T09_vStabHeight": 100,
  "T10_vStabRootChord": 110,
  "T22_tailArm": 180,

  "T14_vTailDihedral": 35,
  "T16_vTailSpan": 280,
  "T17_vTailChord": 90,
  "T18_vTailIncidence": 0,

  "PR01_printBedX": 220,
  "PR02_printBedY": 220,
  "PR03_printBedZ": 250,
  "PR04_autoSection": true,
  "PR05_sectionOverlap": 15,
  "PR10_jointType": "Tongue-and-Groove",
  "PR11_jointTolerance": 0.15,
  "PR06_nozzleDiameter": 0.4,
  "PR14_hollowParts": true,
  "PR09_trailingEdgeMinThickness": 0.8
}
```

**Key derived values (computed on load):**

| Derived Param | Value |
|---------------|-------|
| W03 wingTipChord | 120.6 mm (180 × 0.67) |
| D01 wingArea | 1503 cm² (0.5 × (180 + 120.6) × 1000 = 150300 mm²) |
| D02 aspectRatio | 6.65 (1000² / 150300) |
| D03 meanAeroChord | 153.2 mm |
| D04 taperRatio | 0.67 |
| D05 estimatedCG | 38.3 mm from wing LE (0.25 × 153.2) |
| PR08 minFeatureThickness | 0.8 mm (2 × 0.4) |

---

### 4.3 Aerobatic

**Design intent:** A purpose-built aerobatic platform for experienced pilots seeking precision maneuvers and unlimited-style aerobatics. The symmetric NACA-0012 airfoil generates zero lift at zero angle of attack, making inverted and knife-edge flight as predictable as upright flight. The rectangular planform (tip/root ratio = 1.0) with zero dihedral eliminates any inherent roll tendency, giving the pilot full authority. The wider chord relative to span yields a lower aspect ratio for faster roll rates and snappier response. The slightly shorter fuselage and tail arm trade pitch damping for quicker pitch response.

**Typical use case:** Precision aerobatics, 3D flying, pattern competition practice, advanced maneuvers (snap rolls, lomcevaks, harrier), experienced pilots.

```json
{
  "presetName": "Aerobatic",
  "presetDescription": "Symmetrical-airfoil aerobatic plane for advanced pilots",

  "G01_fuselagePreset": "Conventional",
  "G02_engineCount": 1,
  "P02_motorConfig": "Tractor",
  "G03_wingSpan": 900,
  "G05_wingChord": 220,
  "F13_wingMountType": "Mid-Wing",
  "F01_fuselageLength": 280,
  "G06_tailType": "Conventional",

  "W12_wingAirfoil": "NACA-0012",
  "W05_wingSweep": 0,
  "W04_wingTipRootRatio": 1.0,
  "W07_wingDihedral": 0,
  "W20_wingSkinThickness": 1.2,

  "T02_hStabSpan": 350,
  "T03_hStabChord": 110,
  "T06_hStabIncidence": 0,
  "T09_vStabHeight": 120,
  "T10_vStabRootChord": 120,
  "T22_tailArm": 170,

  "T14_vTailDihedral": 35,
  "T16_vTailSpan": 280,
  "T17_vTailChord": 90,
  "T18_vTailIncidence": 0,

  "PR01_printBedX": 220,
  "PR02_printBedY": 220,
  "PR03_printBedZ": 250,
  "PR04_autoSection": true,
  "PR05_sectionOverlap": 15,
  "PR10_jointType": "Tongue-and-Groove",
  "PR11_jointTolerance": 0.15,
  "PR06_nozzleDiameter": 0.4,
  "PR14_hollowParts": true,
  "PR09_trailingEdgeMinThickness": 0.8
}
```

**Key derived values (computed on load):**

| Derived Param | Value |
|---------------|-------|
| W03 wingTipChord | 220 mm (220 × 1.0) |
| D01 wingArea | 1980 cm² (0.5 × (220 + 220) × 900 = 198000 mm²) |
| D02 aspectRatio | 4.09 (900² / 198000) |
| D03 meanAeroChord | 220 mm |
| D04 taperRatio | 1.0 |
| D05 estimatedCG | 55 mm from wing LE (0.25 × 220) |
| PR08 minFeatureThickness | 0.8 mm (2 × 0.4) |

---

### 4.4 Preset Comparison Matrix

For quick reference, the following table highlights the key differentiating parameters across presets:

| Parameter | Trainer | Sport | Aerobatic |
|-----------|---------|-------|-----------|
| Wingspan | 1200 mm | 1000 mm | 900 mm |
| Wing Root Chord | 200 mm | 180 mm | 220 mm |
| Wing Area | 2400 cm² | 1503 cm² | 1980 cm² |
| Aspect Ratio | 6.0 | 6.65 | 4.09 |
| Airfoil | Clark-Y | NACA-2412 | NACA-0012 |
| Tip/Root Ratio | 1.0 | 0.67 | 1.0 |
| Sweep | 0 deg | 5 deg | 0 deg |
| Dihedral | 3 deg | 3 deg | 0 deg |
| Wing Position | High-Wing | Mid-Wing | Mid-Wing |
| Fuselage Length | 400 mm | 300 mm | 280 mm |
| Tail Arm | 220 mm | 180 mm | 170 mm |
| H-Stab Incidence | −1 deg | −1 deg | 0 deg |

### 4.5 Preset Behavior Rules

1. **Loading a preset replaces all parameters.** When the user selects a preset from the `G08 aircraftPreset` dropdown, every user-configurable parameter is overwritten with the preset values defined above. There is no partial merge.

2. **V-tail parameters are always populated.** Even though the three MVP presets all default to `Conventional` tail type, the V-tail parameters (T14, T16, T17, T18) are stored with sensible defaults so that if the user switches `G06 tailType` to V-Tail after loading a preset, the V-tail geometry is immediately valid.

3. **Editing any parameter after loading clears the preset indicator (one-way).** The UI should display the active preset name (e.g., "Trainer") but as soon as any parameter is modified, the indicator should change to "Custom." This is a one-way transition in the MVP — even if the user manually restores the exact preset values, the indicator stays on "Custom." Reverting to a named preset requires re-selecting it from the dropdown (which overwrites all parameters). Automatic preset detection by deep-comparing all parameters is deferred to 1.0.

4. **Presets do not override print/export settings by default.** Although the preset JSON includes print parameters for completeness (and for first-time users), a future preference may allow users to "lock" their print settings so that loading a preset only affects aircraft geometry. In the MVP, presets always overwrite all parameters including print settings.

5. **Preset extensibility.** The preset system is designed to accept additional presets in future releases (e.g., Glider, Flying Wing, Scale Warbird). Each preset must specify values for all user-configurable parameters defined in Section 3. Community-contributed presets may be supported in a post-1.0 release via a preset import/export mechanism.

---

## 5. Tech Stack (Canonical)

### 5.1 Overview

The MVP runs as a single Docker container serving both the Python backend and the pre-built React frontend as static files. There is no cloud deployment, no multi-container orchestration, and no browser-only storage mode.

| Concern | MVP Solution |
|---------|-------------|
| Deployment | `docker run -p 8000:8000 -v ~/.cheng:/data cheng` |
| Backend | Python 3.11 + FastAPI + CadQuery/OpenCascade |
| Frontend | React 19 + TypeScript, built by Vite, served as static files by FastAPI |
| 3D Rendering | Three.js via React Three Fiber (R3F) |
| State Management | Zustand + Zundo (undo/redo) + Immer (immutable updates) |
| Communication | HTTP REST + WebSocket (`/ws/preview`) |
| Persistence | JSON files on a Docker volume (`/data/designs/`) |
| Port | **8000** (single port for everything) |

> **Security note:** The Docker command binds to `0.0.0.0:8000`, which exposes the application to all interfaces including the local network. There is no authentication in the MVP. This is standard for local development tools but users should be aware that anyone on the same LAN can access the UI and trigger CadQuery operations. For users on shared or public networks, binding to localhost only (`docker run -p 127.0.0.1:8000:8000 ...`) is recommended.

### 5.2 Canonical Dockerfile

Multi-stage build: Node builds the frontend, Python serves everything.

```dockerfile
# ── Stage 1: Frontend Build ──────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ── Stage 2: Python Runtime ──────────────────────────────────────────
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./static/
COPY airfoils/ ./airfoils/
RUN mkdir -p /data/designs
ENV PORT=8000
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key decisions baked into this Dockerfile:**

- `node:22-alpine` for the frontend build stage (small image, fast CI).
- `python:3.11-slim` for runtime (CadQuery requires CPython; slim keeps image size reasonable).
- `uv` for Python dependency resolution (faster than pip, lockfile support).
- Frontend assets land in `/static/` and are served by FastAPI's `StaticFiles` mount.
- `/data/designs/` is the persistence directory, expected to be a Docker volume.

### 5.3 Canonical docker-compose.yml (Local Development)

During development, the backend and frontend run as separate services with hot-reload. The frontend dev server proxies API calls to the backend.

```yaml
services:
  backend:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./backend:/app/backend
      - cheng-data:/data
    command: >
      uvicorn backend.main:app
      --host 0.0.0.0 --port 8000
      --reload --reload-dir /app/backend

  frontend:
    image: node:22-alpine
    working_dir: /app
    volumes:
      - ./frontend:/app
    ports: ["5173:5173"]
    command: sh -c "corepack enable && pnpm dev --host"

volumes:
  cheng-data:
```

**Notes:**

- The `frontend` service uses an inline `node:22-alpine` image directly — no separate Dockerfile needed for development.
- Backend hot-reloads on Python file changes via `--reload-dir`.
- Frontend hot-reloads via Vite's built-in HMR.
- The `cheng-data` named volume persists designs across container restarts.
- In production (single-container mode), only the Dockerfile from Section 5.2 is used.

### 5.4 FastAPI App Structure

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload CadQuery on startup -- first import takes ~2-4s
    import cadquery as cq
    cq.Workplane("XY").box(1, 1, 1)  # warm up OpenCascade kernel
    yield

app = FastAPI(title="CHENG", version="0.1.0", lifespan=lifespan)

# --- API routes registered here (see Section 6) ---

# Health check (before static mount so it is not shadowed)
@app.get("/health")
async def health():
    return {"status": "ok"}

# Static files mount MUST be last -- it catches all unmatched routes
# and serves index.html for SPA client-side routing
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

**Startup behavior:** The lifespan event imports CadQuery and runs a trivial box operation. This forces OpenCascade to load its shared libraries and JIT-compile internal stubs, so the first real `/api/generate` request does not pay the cold-start penalty.

### 5.5 Storage Backend

```python
import json
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    """Protocol defining the storage interface. MVP implements LocalStorage only."""

    def save_design(self, design_id: str, data: dict) -> None: ...
    def load_design(self, design_id: str) -> dict: ...
    def list_designs(self) -> list[dict]: ...
    def delete_design(self, design_id: str) -> None: ...


class LocalStorage:
    """Reads/writes .cheng JSON files to a directory on the Docker volume."""

    def __init__(self, base_path: str = "/data/designs"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _path(self, design_id: str) -> Path:
        # Sanitize to prevent path traversal
        safe_id = Path(design_id).name
        return self.base_path / f"{safe_id}.cheng"

    def save_design(self, design_id: str, data: dict) -> None:
        self._path(design_id).write_text(json.dumps(data, indent=2))

    def load_design(self, design_id: str) -> dict:
        return json.loads(self._path(design_id).read_text())

    def list_designs(self) -> list[dict]:
        designs = []
        for p in sorted(self.base_path.glob("*.cheng"), key=lambda f: f.stat().st_mtime, reverse=True):
            data = json.loads(p.read_text())
            designs.append({
                "id": data.get("id", p.stem),
                "name": data.get("name", "Untitled"),
                "modified_at": p.stat().st_mtime,
            })
        return designs

    def delete_design(self, design_id: str) -> None:
        path = self._path(design_id)
        if path.exists():
            path.unlink()
```

**MVP scope:** `LocalStorage` is the only implementation. There is no `MemoryStorage`, no `IndexedDB` backend, and no storage abstraction factory. The `Protocol` class exists so that a `CloudStorage` implementation can be added in 1.0 without modifying calling code.

### 5.6 CadQuery Thread Runner

CadQuery and OpenCascade are CPU-bound and not async-aware. All geometry operations run in a thread pool, gated by an explicit capacity limiter to prevent OOM on memory-constrained systems.

```python
import anyio

_cadquery_limiter = anyio.CapacityLimiter(4)


async def generate_geometry_safe(design: AircraftDesign) -> GenerationResult:
    """Run CadQuery geometry generation in a thread with concurrency control."""
    result = await anyio.to_thread.run_sync(
        lambda: _generate_geometry_blocking(design),
        limiter=_cadquery_limiter,
        cancellable=True,
    )
    return result
```

**Why `CapacityLimiter(4)`:** Each CadQuery operation can consume 200–500 MB of RAM during BREP evaluation. Limiting concurrency to 4 keeps peak memory under ~2 GB, which is safe for typical developer machines and the default Docker memory limit. The limiter is set at module level (singleton) so all entry points — REST, WebSocket, and export — share the same pool.

**Why `cancellable=True`:** If a WebSocket client disconnects mid-generation, the task can be cancelled rather than completing uselessly. CadQuery itself is not cancellable, but the enclosing coroutine will raise `Cancelled` at the next await point.

**WebSocket last-write-wins and export priority:** The WebSocket handler must cancel any in-flight generation for its connection before submitting a new one (see Section 6.2, step 4). However, because CadQuery operations are not interruptible once started, a cancelled task still occupies a limiter slot until it completes. In the worst case, a rapid sequence of parameter changes could temporarily fill all 4 slots with stale preview generations, causing an export request to queue behind them. For the MVP (single-user, local Docker), this is acceptable — the stale operations complete within seconds and the export proceeds. If this becomes a bottleneck, a dedicated export limiter slot or a priority queue can be added in 1.0.

### 5.7 Frontend Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| UI Framework | React | 19 | Component model, concurrent rendering |
| Language | TypeScript (strict) | 5.x | Type safety across the entire frontend |
| Bundler | Vite | 6.x | Fast HMR in dev, optimized production builds |
| 3D Rendering | Three.js via R3F | latest | WebGL rendering of mesh previews |
| State | Zustand + Zundo + Immer | latest | Global store with undo/redo and immutable updates |
| UI Primitives | Radix Primitives | latest | Accessible, unstyled base components |
| Styling | Tailwind CSS | 4.x | Utility-first CSS, no runtime cost |
| Package Manager | pnpm | latest | Fast, disk-efficient dependency management |
| Testing | Vitest + Playwright | latest | Unit/integration tests + E2E browser tests |

---

## 6. API Contract

### 6.1 REST Endpoints

All REST endpoints are prefixed with `/api/` except `/health`. Request and response bodies are JSON unless otherwise noted.

| Method | Path | Request Body | Response Body | Status Codes | Description |
|--------|------|-------------|---------------|-------------|-------------|
| `GET` | `/health` | — | `{"status": "ok"}` | 200 | Health check |
| `POST` | `/api/generate` | `AircraftDesign` | `GenerationResult` | 200, 422 | Generate geometry (REST fallback) |
| `POST` | `/api/export` | `ExportRequest` | ZIP binary (StreamingResponse) | 200, 422 | Export STL files as ZIP |
| `GET` | `/api/designs` | — | `DesignSummary[]` | 200 | List all saved designs |
| `GET` | `/api/designs/{id}` | — | `AircraftDesign` | 200, 404 | Load a saved design |
| `POST` | `/api/designs` | `AircraftDesign` | `{"id": "..."}` | 201, 422 | Save a new design |
| `DELETE` | `/api/designs/{id}` | — | `{"ok": true}` | 200, 404 | Delete a saved design |

**Error responses** follow a consistent shape:

```json
{
  "detail": "Human-readable error message",
  "errors": [
    {"field": "wing_span", "message": "Value must be between 300 and 3000"}
  ]
}
```

**Notes:**

- `POST /api/generate` is the REST fallback for clients that cannot use WebSocket. For interactive preview, the WebSocket protocol (Section 6.2) is strongly preferred.
- `POST /api/export` returns a `StreamingResponse` with `Content-Type: application/zip` and a `Content-Disposition` header for the filename. No temporary files are created on disk (see Section 8.5).
- `POST /api/designs` assigns an ID server-side if the `id` field is missing or empty. If an `id` is provided and already exists, the design is overwritten (upsert semantics).

### 6.2 WebSocket Protocol

**Path:** `/ws/preview`

The WebSocket connection is the primary communication channel for interactive 3D preview. The client sends the full `AircraftDesign` JSON on every parameter change; the server responds with a binary mesh update or an error.

#### Client -> Server (Text Frame)

The client sends a JSON text frame containing the complete `AircraftDesign` object. Sending frequency is controlled client-side:

- **Sliders:** throttled at 100ms (send at most every 100ms while dragging)
- **Text inputs:** debounced at 300ms (send 300ms after the user stops typing)
- **Dropdowns/toggles:** sent immediately on change

```json
{
  "version": "0.1.0",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Plane",
  "wing_span": 1200,
  "wing_chord": 180
}
```

#### Server -> Client (Binary Frame): Mesh Update

Message type `0x01`. Binary layout (little-endian):

| Offset | Size | Type | Description |
|--------|------|------|-------------|
| 0 | 4 | uint32 | Message type (`0x00000001` = mesh update) |
| 4 | 4 | uint32 | Vertex count (N) |
| 8 | 4 | uint32 | Face count (M) |
| 12 | N * 12 | float32[3] | Vertex positions (x, y, z per vertex) |
| 12 + N*12 | N * 12 | float32[3] | Vertex normals (nx, ny, nz per vertex) |
| 12 + N*24 | M * 12 | uint32[3] | Face indices (3 vertex indices per triangle) |
| 12 + N*24 + M*12 | variable | UTF-8 JSON | Trailer: derived values + validation messages |

**JSON trailer structure:**

```json
{
  "derived": {
    "wing_area_cm2": 2400,
    "aspect_ratio": 6.0,
    "mean_aero_chord_mm": 200,
    "taper_ratio": 1.0,
    "tip_chord_mm": 200,
    "estimated_cg_mm": 50,
    "min_feature_thickness_mm": 0.8
  },
  "validation": [
    {"id": "V01", "level": "warn", "message": "Very high aspect ratio relative to fuselage", "fields": ["wing_span", "fuselage_length"]}
  ]
}
```

#### Server -> Client (Binary Frame): Error

Message type `0x02`. Binary layout:

| Offset | Size | Type | Description |
|--------|------|------|-------------|
| 0 | 4 | uint32 | Message type (`0x00000002` = error) |
| 4 | variable | UTF-8 JSON | Error detail object |

```json
{
  "error": "Geometry generation failed",
  "detail": "Wing chord (500mm) exceeds 40% of wing span (1000mm); this produces degenerate geometry",
  "field": "wing_chord"
}
```

#### Connection Lifecycle

1. Client opens `ws://localhost:8000/ws/preview`.
2. Server accepts; no authentication required in MVP.
3. Client sends `AircraftDesign` JSON on each parameter change.
4. Server cancels any in-flight generation for this connection before starting a new one (last-write-wins).
5. Server sends binary mesh update or error.
6. On disconnect, server cancels any pending generation and cleans up.

### 6.3 Pydantic Models

#### AircraftDesign

The canonical parameter model. Flat structure with validation constraints matching the parameter table.

```python
from pydantic import BaseModel, Field
from uuid import uuid4


class AircraftDesign(BaseModel):
    # ── Meta ─────────────────────────────────────────────────────────
    version: str = "0.1.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Untitled Aircraft"

    # ── Global / Fuselage ────────────────────────────────────────────
    fuselage_preset: str = "Conventional"
    engine_count: int = Field(ge=0, le=4, default=1)
    motor_config: str = "Tractor"
    wing_span: float = Field(ge=300, le=3000, default=1000)        # mm
    wing_chord: float = Field(ge=50, le=500, default=180)          # mm
    wing_mount_type: str = "High-Wing"
    fuselage_length: float = Field(ge=150, le=2000, default=300)   # mm
    tail_type: str = "Conventional"

    # ── Wing ─────────────────────────────────────────────────────────
    wing_airfoil: str = "Clark-Y"
    wing_sweep: float = Field(ge=-10, le=45, default=0)            # degrees
    wing_tip_root_ratio: float = Field(ge=0.3, le=1.0, default=1.0)
    wing_dihedral: float = Field(ge=-10, le=15, default=3)         # degrees
    wing_skin_thickness: float = Field(ge=0.8, le=3.0, default=1.2)  # mm

    # ── Tail (Conventional) ──────────────────────────────────────────
    h_stab_span: float = Field(ge=100, le=1200, default=350)      # mm
    h_stab_chord: float = Field(ge=30, le=250, default=100)       # mm
    h_stab_incidence: float = Field(ge=-5, le=5, default=-1)      # degrees
    v_stab_height: float = Field(ge=30, le=400, default=100)      # mm
    v_stab_root_chord: float = Field(ge=30, le=300, default=110)  # mm

    # ── Tail (V-Tail) ───────────────────────────────────────────────
    v_tail_dihedral: float = Field(ge=20, le=60, default=35)      # degrees
    v_tail_span: float = Field(ge=80, le=600, default=280)        # mm
    v_tail_chord: float = Field(ge=30, le=200, default=90)        # mm
    v_tail_incidence: float = Field(ge=-3, le=3, default=0)       # degrees

    # ── Shared Tail ──────────────────────────────────────────────────
    tail_arm: float = Field(ge=80, le=1500, default=180)          # mm

    # ── Export / Print ───────────────────────────────────────────────
    print_bed_x: float = Field(ge=100, le=500, default=220)       # mm
    print_bed_y: float = Field(ge=100, le=500, default=220)       # mm
    print_bed_z: float = Field(ge=50, le=500, default=250)        # mm
    auto_section: bool = True
    section_overlap: float = Field(ge=5, le=30, default=15)       # mm
    joint_type: str = "Tongue-and-Groove"
    joint_tolerance: float = Field(ge=0.05, le=0.5, default=0.15) # mm per side
    nozzle_diameter: float = Field(ge=0.2, le=1.0, default=0.4)   # mm
    hollow_parts: bool = True
    te_min_thickness: float = Field(ge=0.4, le=2.0, default=0.8)  # mm
```

#### ExportRequest

```python
class ExportRequest(BaseModel):
    design: AircraftDesign
    format: str = "stl"  # MVP: "stl" only; "step" and "dxf" deferred to 1.0
```

#### GenerationResult

```python
class GenerationResult(BaseModel):
    vertices: list[list[float]]     # [[x, y, z], ...] -- for REST fallback
    normals: list[list[float]]      # [[nx, ny, nz], ...]
    faces: list[list[int]]          # [[i0, i1, i2], ...]
    derived: dict                   # wing_area_cm2, aspect_ratio, etc.
    validation: list[dict]          # [{"id": "V01", "level": "warn", "message": "..."}]
```

#### DesignSummary

```python
from datetime import datetime

class DesignSummary(BaseModel):
    id: str
    name: str
    created_at: datetime
    modified_at: datetime
```

---

## 7. UI Layout Spec

### 7.1 Screen Layout

```
+---------------------------------------------------------------+
|  [New] [Open] [Save]     [Top] [Fit]     [Undo] [Redo]  [*]  |
+-------------------------------------------+-------------------+
|                                           |                   |
|                                           |  GLOBAL           |
|                                           |  PARAMETERS       |
|             VIEWPORT                      |  PANEL            |
|          (Three.js canvas,                |  (right,          |
|           fills remaining                 |   fixed width     |
|           space)                          |   ~280px)         |
|                                           |                   |
+---------------------------+---------------+-------------------+
|  COMPONENT DETAIL PANEL   |          [EXPORT STL]             |
|  (bottom-left, ~60% w)    |          (bottom-right)           |
+---------------------------+-----------------------------------+
```

`[*]` = connection status dot (green = connected, yellow = reconnecting, red = disconnected).

**Toolbar** (top bar, left-to-right):

| Group | Controls | Notes |
|-------|----------|-------|
| File | New, Open, Save | Standard file operations |
| View | Top, Fit | Top resets to top-down orthographic; Fit auto-frames the model |
| Edit | Undo, Redo | Full undo/redo stack for all parameter changes |
| Status | Connection dot | Far right; see Section 7.6 |

### 7.2 Global Parameters Panel

Fixed-width right panel (~280 px). Fields listed top to bottom:

| # | Field | Control | Constraints |
|---|-------|---------|-------------|
| 1 | Aircraft Preset | Dropdown: Trainer, Sport, Aerobatic, Custom | Loading a preset populates all parameters; editing any param switches preset to Custom |
| 2 | Fuselage | Dropdown: Pod, Conventional, Blended-Wing-Body | Changes fuselage silhouette |
| 3 | Engines | Numeric stepper (0–4) + Motor Position dropdown (Nose / Rear), side by side | Stepper clamps to 0–4 |
| 4 | Wingspan | Text input with unit label "mm" | Range 300–3000, integer |
| 5 | Wing Chord | Text input with unit label "mm" | Range 50–500, integer |
| 6 | Wing Position | Dropdown: High, Mid, Low, Shoulder | Vertical placement of wing on fuselage |
| 7 | Fuselage Length | Text input with unit label "mm" | Range 150–2000, integer |
| 8 | Tail Type | Dropdown: Conventional, T-Tail, V-Tail, Cruciform | Determines which tail fields appear in Component Detail Panel |

### 7.3 Component Detail Panel

Occupies the bottom-left region (~60% of window width). Content is context-sensitive based on viewport selection.

**Default state (nothing selected):**
Panel displays `SELECT A COMPONENT TO CONFIGURE` in subdued (#888) text, centered.

**Wing selected:**

| Field | Control | Constraints |
|-------|---------|-------------|
| Airfoil | Searchable dropdown (10+ airfoils grouped by category) | Categories: Flat-bottom, Semi-symmetric, Symmetric, etc. |
| Sweep | Text input + slider (deg) | −10–45 deg |
| Tip / Root Ratio | Slider + text input | 0.3–1.0 |
| Dihedral | Text input + slider (deg) | −10–15 deg |
| Skin Thickness | Text input (mm) | 0.8–3.0 mm |
| --- | --- | --- |
| Wing Area | Read-only computed (cm²) | Derived from span, root chord, taper |
| Aspect Ratio | Read-only computed | span² / area |
| Balance Point | Read-only computed (mm from wing LE) | 25% of MAC — where to balance for flight |

Separator line divides editable fields from derived (read-only) values.

**Tail selected — Conventional / T-Tail / Cruciform:**

| Field | Control | Constraints |
|-------|---------|-------------|
| H-Stab Span | Text input (mm) | 100–1200 |
| H-Stab Chord | Text input (mm) | 30–250 |
| H-Stab Incidence | Text input (deg) | −5–5 |
| Fin Height | Text input (mm) | 30–400 |
| Fin Root Chord | Text input (mm) | 30–300 |
| Tail Arm | Text input (mm) | 80–1500 |

**Tail selected — V-Tail:**

| Field | Control | Constraints |
|-------|---------|-------------|
| Dihedral | Text input (deg) | 20–60 |
| Span | Text input (mm) | 80–600 |
| Chord | Text input (mm) | 30–200 |
| Incidence | Text input (deg) | −3–3 |
| Tail Arm | Text input (mm) | 80–1500 |

### 7.4 Export Dialog

Modal dialog triggered by the `EXPORT STL` button.

```
+-----------------------------------------------+
|  EXPORT FOR 3D PRINTING                       |
|                                               |
|  Printer Bed Size:                            |
|   X: [220] mm  Y: [220] mm  Z: [250] mm     |
|                                               |
|  Sectioning:                                  |
|   [x] Auto-section parts for bed size        |
|   Joint Type: [Tongue-and-Groove v]           |
|   Joint Overlap: [15] mm                     |
|   Joint Tolerance: [0.15] mm                 |
|                                               |
|  Print Settings:                              |
|   Nozzle Diameter: [0.4] mm                  |
|   [x] Hollow parts                           |
|   TE Min Thickness: [0.8] mm                 |
|                                               |
|  Estimated Parts: 9 pieces                   |
|                                               |
|                     [Export ZIP]  [Cancel]     |
+-----------------------------------------------+
```

| Field | Default | Notes |
|-------|---------|-------|
| Bed X / Y / Z | 220 / 220 / 250 mm | Common Ender-3 / Prusa MK3 bed size |
| Auto-section | Enabled | Splits parts that exceed bed dimensions |
| Joint Type | Tongue-and-Groove | Dropdown for future joint types |
| Joint Overlap | 15 mm | Range 5–30 mm |
| Joint Tolerance | 0.15 mm | Range 0.05–0.5 mm |
| Nozzle Diameter | 0.4 mm | Range 0.2–1.0 mm |
| Hollow parts | Enabled | Generates hollow structures with internal ribs |
| TE Min Thickness | 0.8 mm | Trailing-edge minimum; range 0.4–2.0 mm |
| Estimated Parts | Computed | Updates live as settings change |

`Export ZIP` triggers backend generation and downloads a ZIP containing one named STL per section. `Cancel` dismisses the dialog.

### 7.5 Dimension Annotations

Three annotations are always visible on the viewport:

| Annotation | Placement | Format |
|------------|-----------|--------|
| Overall Length | Horizontal leader line, nose to tail, offset below fuselage | `1045 mm` |
| Wingspan | Horizontal leader line, tip to tip, offset above wings | `1200 mm` |
| Sweep Angle | Arc indicator near wing leading edge | `15.0°` |

**Style:** thin white lines (1 px, `#CCCCCC`), monospace font (10 px), minimal visual weight. Leader lines use short perpendicular tick marks at endpoints. Annotations reposition automatically with camera angle to remain legible.

### 7.6 Connection Status Indicator

Located at the far right of the toolbar.

| State | Indicator | UI Behavior |
|-------|-----------|-------------|
| Connected | Green dot (`#34C759`) | Normal operation; all controls enabled |
| Reconnecting | Yellow pulsing dot (`#FFD60A`) | Toast notification: "Reconnecting to backend..." Auto-retry via WebSocket every 3 seconds. Controls remain enabled but parameter changes are queued |
| Disconnected | Red dot (`#FF3B30`) | Persistent banner below toolbar: "Backend unavailable. Is Docker running?" All edit controls become read-only; Export button disabled |

Transition rules:
- Connected to Reconnecting: triggered by WebSocket `close` or `error` event.
- Reconnecting to Connected: triggered by successful WebSocket `open` event.
- Reconnecting to Disconnected: triggered after 5 consecutive failed reconnect attempts (15 seconds total).
- Disconnected to Reconnecting: user clicks "Retry" in the banner, or automatic retry every 30 seconds.

### 7.7 Viewport Behavior

| Property | Specification |
|----------|---------------|
| Default view | Top-down orthographic |
| Zoom | Scroll wheel; smooth interpolation |
| Pan | Middle-click drag |
| Orbit | Right-click drag |
| Select component | Left-click on mesh; selected component highlighted in yellow (`#FFD60A`); others remain medium gray (`#6B6B70`) |
| Deselect | Left-click on empty space; component panel returns to default |
| Debounce (text inputs) | 300 ms after last keystroke before sending parameter update |
| Throttle (sliders) | 100 ms minimum interval between updates |
| Loading overlay | Semi-transparent spinner appears if CadQuery regeneration takes > 300 ms |
| Background color | Dark charcoal (`#2A2A2E`) |
| Aircraft base color | Medium gray (`#6B6B70`) |
| Selection highlight | Yellow (`#FFD60A`) |
| Target frame rate | 60 fps on 2020-era integrated GPU (Intel UHD 630 or equivalent) |

---

## 8. Export Pipeline

### 8.1 MVP Export Format

The MVP exports **STL only**. STEP (for CNC/laser workflows) and DXF (for flat panel layouts) are deferred to 1.0. STL is sufficient for the primary use case: 3D printing RC plane parts at home.

### 8.2 Auto-Sectioning Algorithm

The auto-sectioning system splits components that exceed the user's print bed dimensions into pieces that each fit on the bed.

**Inputs:**

- Complete BREP solid for each component (wing half, fuselage, tail surface, etc.)
- Print bed dimensions from the design parameters: `print_bed_x`, `print_bed_y`, `print_bed_z` (parameters PR01, PR02, PR03)

**Algorithm:**

```
function auto_section(solid, bed_x, bed_y, bed_z):
    # Leave 20mm margin on each axis for joint features
    max_x = bed_x - 20
    max_y = bed_y - 20
    max_z = bed_z - 20

    bbox = bounding_box(solid)

    if bbox.x <= max_x and bbox.y <= max_y and bbox.z <= max_z:
        return [solid]  # fits on bed, no splitting needed

    # Find the axis that exceeds the bed by the most
    overshoot = {
        'x': bbox.x - max_x,
        'y': bbox.y - max_y,
        'z': bbox.z - max_z,
    }
    split_axis = max(overshoot, key=overshoot.get)

    # Split at the midpoint of the longest-exceeding axis
    midpoint = bbox.center[split_axis]
    left, right = bisect_solid(solid, axis=split_axis, position=midpoint)

    # Recurse on each half
    return auto_section(left, bed_x, bed_y, bed_z) +
           auto_section(right, bed_x, bed_y, bed_z)
```

**Key behaviors:**

- Recursion continues until every piece fits within the usable bed volume (bed dimensions minus 20mm margin).
- The 20mm margin reserves space for joint features (tongue/groove protrusions).
- Splitting is always along the longest-exceeding axis to minimize the total number of sections.
- For a 1000mm wingspan plane on a 220x220mm bed, each wing half (500mm) typically splits into 3 sections.
- **Known limitation (MVP):** The midpoint split may intersect internal features (spar channels, wing-fuselage junction). If the cut plane produces unprintable geometry, the implementation should offset the split point by ±10mm to avoid the feature. A more sophisticated split-point optimizer is deferred to 1.0.

### 8.3 Joint Generation

Joints are automatically added at every section boundary to enable accurate reassembly.

**Default joint type: Tongue-and-Groove** (parameter PR10)

```
Section N (left)          Section N+1 (right)
┌──────────────┐          ┌──────────────┐
│              ├──┐  ┌────┤              │
│              │  ├──┤    │              │
│              ├──┘  └────┤              │
└──────────────┘          └──────────────┘
     tongue ──►     ◄── groove
```

**Joint geometry details:**

- **Tongue** protrudes from the +axis face of section N.
- **Groove** is cut into the -axis face of section N+1.
- **Overlap length:** controlled by `section_overlap` (PR05, default 15mm). This is how far the tongue extends into the groove.
- **Clearance per side:** controlled by `joint_tolerance` (PR11, default 0.15mm). The groove is wider than the tongue by 2 x tolerance (total gap = 0.3mm), providing a snug but assemblable fit with standard FDM tolerances.
- **Spar channel alignment:** for wing sections, spar channels (if present) are maintained co-axial across the joint boundary to within 0.2mm. This ensures that a carbon spar can pass through multiple sections without binding.

**Joint sizing heuristic:**

- Tongue cross-section is 60% of the section's cross-sectional area at the cut plane.
- Tongue corners are filleted at 1mm radius to reduce stress concentration and improve printability.
- Minimum tongue width is 3 x `nozzle_diameter` (PR06) to ensure the feature is printable.

### 8.4 ZIP Packaging

The export endpoint produces a single ZIP file containing all parts and a machine-readable manifest.

**File naming convention:** `{component}_{side}_{section}.stl`

Examples for a 1000mm conventional plane:

```
wing_left_1of3.stl
wing_left_2of3.stl
wing_left_3of3.stl
wing_right_1of3.stl
wing_right_2of3.stl
wing_right_3of3.stl
fuselage_center_1of2.stl
fuselage_center_2of2.stl
h_stab_left_1of1.stl
h_stab_right_1of1.stl
v_stab_center_1of1.stl
manifest.json
```

**manifest.json structure:**

```json
{
  "design_name": "My Plane",
  "design_id": "550e8400-e29b-41d4-a716-446655440000",
  "version": "0.1.0",
  "total_parts": 11,
  "parts": [
    {
      "filename": "wing_left_1of3.stl",
      "component": "wing",
      "side": "left",
      "section": 1,
      "total_sections": 3,
      "dimensions_mm": [205, 180, 28],
      "print_orientation": "trailing-edge down",
      "assembly_order": 1
    }
  ],
  "assembly_notes": [
    "Join wing sections with cyanoacrylate or epoxy",
    "Insert carbon spar through aligned spar channels before final glue-up",
    "Attach wing halves to fuselage at the wing saddle"
  ]
}
```

**Typical part counts:** 5–15 parts for a 1000mm wingspan plane on a 220x220mm bed.

### 8.5 Streaming Export via Temp File

The export endpoint writes the ZIP archive to a temporary file on the `/data` volume, then streams it back to the client. Using a temp file instead of `io.BytesIO` avoids OOM risk — high-resolution STLs of curved aircraft surfaces can total 50–100 MB uncompressed across 5–15 parts, and combined with CadQuery's 200–500 MB per-operation overhead, an in-memory approach could exceed Docker's default 2 GB memory limit.

```python
import json
import tempfile
import zipfile
from pathlib import Path
from fastapi.responses import FileResponse


EXPORT_TMP_DIR = Path("/data/tmp")
EXPORT_TMP_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/api/export")
async def export_stl(request: ExportRequest):
    design = request.design

    # Generate geometry and split into printable sections
    # (runs through the CadQuery limiter -- see Section 5.6)
    sections = await generate_and_section(design)

    # Build ZIP on disk (temp file on /data volume)
    tmp = tempfile.NamedTemporaryFile(
        dir=EXPORT_TMP_DIR, suffix=".zip", delete=False
    )
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for part in sections:
                stl_bytes = tessellate_for_export(part.solid)
                zf.writestr(part.filename, stl_bytes)
            zf.writestr("manifest.json", json.dumps(build_manifest(sections), indent=2))
        tmp.close()

        filename = f"{design.name.replace(' ', '_')}_export.zip"
        return FileResponse(
            tmp.name,
            media_type="application/zip",
            filename=filename,
            background=BackgroundTask(lambda: Path(tmp.name).unlink(missing_ok=True)),
        )
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise
```

**Why temp file on `/data`:** The `/data` directory is already a Docker volume mount, so temp files use the host filesystem rather than the container's writable layer. A `BackgroundTask` deletes the temp file after the response is fully sent. This approach keeps peak memory usage to CadQuery's working set only, with no large ZIP buffers in RAM. The `_cadquery_limiter` (Section 5.6) ensures that at most 4 export operations run concurrently.

---

## 9. Validation Rules (MVP Subset)

### 9.1 Range Validation

Every numeric input is validated against its declared min/max range on each keystroke (debounced). Behavior:

1. **Visual feedback:** Out-of-range values cause the input field border to turn red (`#FF3B30`) immediately on input.
2. **Clamping before send:** When the debounce timer fires (300 ms), the value is clamped to the valid range *before* being sent to the backend. The backend never receives an out-of-range value.
3. **Visual replacement:** The clamped value replaces the user's typed text after a 1-second idle timeout (separate from the 300 ms debounce). This delay lets the user finish typing multi-digit numbers without the input snapping mid-keystroke (e.g., typing "1500" should not clamp at "1" or "15").
4. **Type enforcement:** Non-numeric characters are rejected at the input level (no letters, no special characters except decimal point where applicable).

### 9.2 Structural / Geometric Warnings

Non-blocking warnings computed on every parameter change. These alert the user to potentially problematic designs but do not prevent export.

| ID | Condition | Warning Text | Affected Field(s) |
|----|-----------|--------------|-------------------|
| V01 | `wingspan > 10 * fuselageLength` | "Very high aspect ratio relative to fuselage" | Wingspan, Fuselage Length |
| V02 | `tipRootRatio < 0.3` | "Aggressive taper — tip stall risk" | Tip/Root Ratio |
| V03 | `fuselageLength < wingChord` | "Fuselage shorter than wing chord" | Fuselage Length, Wing Chord |
| V04 | `tailArm < 2 * MAC` | "Short tail arm — may lack pitch stability" | Tail Arm |
| V05 | `wingChord * tipRootRatio < 30` | "Extremely small tip chord" | Wing Chord, Tip/Root Ratio |
| V06 | `tailArm > fuselageLength` | "Tail arm exceeds fuselage — tail extends past the body" | Tail Arm, Fuselage Length |

MAC (Mean Aerodynamic Chord) is computed as:
```
MAC = (2/3) * rootChord * (1 + taper + taper²) / (1 + taper)
```
where `taper` = `tipRootRatio` and `rootChord` = `wingChord`.

### 9.3 3D Printing Warnings

Non-blocking warnings specific to FDM printability, evaluated against the export dialog settings.

| ID | Condition | Warning Text | Affected Field(s) |
|----|-----------|--------------|-------------------|
| V16 | `skinThickness < 2 * nozzleDiameter` | "Wall too thin for solid perimeters" | Skin Thickness, Nozzle Diameter |
| V17 | `skinThickness % nozzleDiameter > 0.01` | "Wall not clean multiple of nozzle diameter" | Skin Thickness, Nozzle Diameter |
| V18 | `skinThickness < 2 * nozzleDiameter` | "Wing skin too thin for reliable FDM" | Skin Thickness |
| V20 | Any part dimension exceeds bed size AND auto-section disabled | "Enable auto-sectioning or reduce dimensions" | Bed Size, Wingspan/Fuselage Length |
| V21 | `jointOverlap < 10 AND wingspan > 800` | "Joint overlap too short for this span" | Joint Overlap, Wingspan |
| V22 | `jointTolerance > 0.3` | "Parts may be loose" | Joint Tolerance |
| V23 | `jointTolerance < 0.05` | "Parts may not fit" | Joint Tolerance |

### 9.4 Validation Behavior

- **Timing:** Warnings are recomputed on every parameter change, debounced together with geometry regeneration (300 ms for text inputs, 100 ms for sliders).
- **Transport:** The backend returns warnings alongside mesh data in the WebSocket JSON trailer (see Section 6.2).
- **Non-blocking:** Warnings never block export. The user can export STL files with active warnings.
- **Visual treatment:** A small warning triangle icon (`#FFD60A`) appears inline next to each affected parameter field. The Export dialog also summarizes active warnings at the bottom if any exist.
- **Interaction:** Clicking a warning triangle shows a tooltip containing the warning message. No additional action is required from the user.

---

## 10. Acceptance Criteria

All criteria must pass before the MVP is considered shippable. Organized by feature area.

### 10.1 3D Viewport

| # | Criterion | Measurement |
|---|-----------|-------------|
| A1 | Mesh renders correctly | No missing faces, inverted normals, or z-fighting visible at any zoom level |
| A2 | Parameters reflect in viewport | Changing any global or component parameter visually updates the model within the round-trip time budget |
| A3 | Dimension annotations accurate | Displayed values match parameter values to within 0.1 mm |
| A4 | Update round-trip < 2 seconds | Time from parameter change to completed viewport update is under 2 s (measured on reference hardware: 4-core CPU, 16 GB RAM, integrated GPU) |
| A5 | Component highlight works | Selected component turns yellow (`#FFD60A`); all other components remain gray (`#6B6B70`) |
| A6 | Camera controls smooth | Orbit, pan, and zoom maintain 60 fps on a 2020-era integrated GPU (Intel UHD 630 or equivalent) |

### 10.2 Global Parameters

| # | Criterion | Measurement |
|---|-----------|-------------|
| B1 | Fuselage dropdown has 3 options | Pod, Conventional, Blended-Wing-Body all present and selectable |
| B2 | Changing fuselage updates silhouette | Visual update of fuselage shape completes within 2 s |
| B3 | Engine count accepts 0–4 | Stepper clamps to range; values outside 0–4 are rejected |
| B4 | Motor position toggles | Nose/Rear dropdown changes motor mount position visually |
| B5 | Wingspan accepts 300–3000 mm | Values within range accepted with 1 mm resolution; out-of-range values flagged and clamped |
| B6 | Wing chord accepts 50–500 mm | Values within range accepted with 1 mm resolution; out-of-range values flagged and clamped |
| B7 | Tail type dropdown has 4 options | Conventional, T-Tail, V-Tail, Cruciform all present; selecting each changes tail geometry |
| B8 | Aircraft presets load correctly | Trainer, Sport, and Aerobatic each populate all global and component parameters with preset values |
| B9 | Custom preset auto-selected | Manually editing any parameter switches the preset dropdown to "Custom" |

### 10.3 Component Selection

| # | Criterion | Measurement |
|---|-----------|-------------|
| C1 | Click wing selects it | Wing mesh highlights yellow; Component Detail Panel populates with wing-specific fields |
| C2 | Click tail selects it | Tail mesh highlights yellow; Component Detail Panel populates with correct field set for the active tail type |
| C3 | Click empty space deselects | Highlight removed from all components; Component Detail Panel returns to default "SELECT A COMPONENT" state |
| C4 | Component params update viewport | Each component parameter change (airfoil, sweep, dihedral, etc.) is reflected visually in the viewport |

### 10.4 STL Export

| # | Criterion | Measurement |
|---|-----------|-------------|
| D1 | Watertight STL | Zero errors reported on import in PrusaSlicer 2.7+, Cura 5.x, and Bambu Studio 1.x |
| D2 | Dimensions match parameters | Key dimensions (wingspan, fuselage length, chord) in the exported STL match parameter values to within 0.5 mm |
| D3 | Min wall 1.2 mm enforced | No wall in generated geometry is thinner than 1.2 mm (verified via slicer cross-section inspection) |
| D4 | Auto-sectioning works | Parts exceeding printer bed dimensions are automatically split into sections with mating joint features |
| D5 | Per-section STL files | Export produces a ZIP archive containing one descriptively named STL file per section |
| D6 | Joint alignment | Mating features on adjacent sections align to within 0.3 mm when virtually assembled |
| D7 | Export completes < 15 s | Full aircraft export (including sectioning) completes within 15 seconds on reference hardware |
| D8 | Slicer compatible | Exported STL files open without errors or warnings in PrusaSlicer 2.7+, Cura 5.x, and Bambu Studio 1.x |

### 10.5 Docker Deployment

| # | Criterion | Measurement |
|---|-----------|-------------|
| E1 | Single command launch | `docker run -p 8000:8000 cheng` starts the container and serves the UI at `http://localhost:8000` |
| E2 | Volume persistence | `docker run -p 8000:8000 -v ~/.cheng:/data cheng` persists saved designs across container restarts |
| E3 | Cross-platform | Container runs successfully on Docker Desktop for Windows, macOS (Intel and Apple Silicon), and Linux |
| E4 | Image size < 2 GB | Total image size including CadQuery, OpenCascade, Python runtime, and frontend assets is under 2 GB |
| E5 | Startup < 10 seconds | Container starts and serves its first HTTP request within 10 seconds of `docker run` |

### 10.6 Save / Load

| # | Criterion | Measurement |
|---|-----------|-------------|
| F1 | Save encodes full design | Loading a saved design restores every global parameter, component parameter, and export setting to their exact saved values |
| F2 | JSON is human-readable | Saved file is valid JSON with descriptive key names; parameters are identifiable when opened in a text editor |
| F3 | File listing works | `GET /api/designs` returns a JSON array of all saved design names and timestamps |
| F4 | Save/load round-trip | Save a design, restart the container (with volume mount), load the design — all values match |

### 10.7 Derived Values

| # | Criterion | Measurement |
|---|-----------|-------------|
| G1 | Wing area displayed | Wing area (cm²) is shown in the Component Detail Panel and updates when span, chord, or taper ratio changes |
| G2 | Aspect ratio accurate | Displayed aspect ratio matches `span² / area` to within 1% |
| G3 | MAC computed correctly | Mean Aerodynamic Chord uses the standard formula: `(2/3) * rootChord * (1 + t + t²) / (1 + t)` where `t = tipRootRatio` |
| G4 | Values are read-only | Derived value fields cannot be edited by the user (input is disabled; no cursor on click) |
| G5 | Balance point displayed | Estimated CG (25% MAC) shown in wing panel; updates when chord or taper ratio changes |

### 10.8 Validation

| # | Criterion | Measurement |
|---|-----------|-------------|
| H1 | Range validation visual | Out-of-range values produce a red border on the affected input field within 300 ms |
| H2 | Values are clamped | Backend never receives a parameter value outside its declared min/max range |
| H3 | Structural warnings display | All V01–V06 warnings trigger correctly and display a warning triangle next to affected fields |
| H4 | Print warnings display | All V16–V23 warnings trigger correctly when export dialog settings meet their conditions |
| H5 | Warnings are non-blocking | Export proceeds successfully even with active warnings |
| H6 | Warning tooltips work | Clicking a warning icon shows a tooltip with the full warning message |

### 10.9 Connection Status

| # | Criterion | Measurement |
|---|-----------|-------------|
| I1 | Green dot when connected | Status indicator is green during normal WebSocket operation |
| I2 | Yellow dot on reconnect | Stopping and restarting the backend triggers yellow pulsing dot and "Reconnecting..." toast |
| I3 | Red dot after failure | After 5 failed reconnect attempts (15 s), indicator turns red and banner appears |
| I4 | Recovery works | Restarting the backend while in disconnected state causes automatic recovery to green |
| I5 | Read-only in disconnected | All parameter inputs and the Export button are disabled when status is red |

### 10.10 End-to-End Scenario

| # | Criterion | Measurement |
|---|-----------|-------------|
| J1 | Idea to printable STL < 10 min | A first-time user (matching the Alex persona) can launch Docker, select a preset, adjust 3–5 parameters, and export a valid STL ZIP in under 10 minutes |
| J2 | Preset to export < 3 min | Selecting a preset and exporting immediately (no customization) completes in under 3 minutes including export time |

---

## 11. Out of Scope (Explicitly Deferred)

The following features are **not** in the MVP. Each item lists the document that owns its 1.0 specification.

| Feature | Deferred To | Owning Document |
|---------|-------------|-----------------|
| Cloud Run deployment | 1.0 | architecture.md |
| CHENG_MODE toggle (local/cloud) | 1.0 | architecture.md |
| MemoryStorage / IndexedDB backend | 1.0 | architecture.md |
| Cold start UX (skeleton loader, progress bar) | 1.0 | ux_design.md |
| Mode badge (Local/Cloud indicator) | 1.0 | ux_design.md |
| STEP export format | 1.0 | product_requirements.md |
| DXF export format | 1.0 | product_requirements.md |
| SVG export format | Future | product_requirements.md |
| Multi-section wings (distinct inner/outer panels) | 1.0 | aero_parameters.md |
| Control surfaces (ailerons, elevator, rudder) | 1.0 | aero_parameters.md |
| Landing gear parameters | 1.0 | aero_parameters.md |
| Bidirectional parameter editing (toggle direction) | 1.0 | cross_review_ux.md |
| Parameter renaming for beginners | 1.0 | cross_review_ux.md |
| Test joint feature (print-before-commit) | 1.0 | cross_review_aero.md |
| Community preset import/export | Future | product_requirements.md |
| Collaboration / sharing | Future | product_requirements.md |
| AI-assisted design suggestions | Future | product_requirements.md |
| Direct motor/ESC/servo database | Future | aero_parameters.md |
| Structural FEA analysis | Future | product_requirements.md |
| CG (center of gravity) full calculator | 1.0 | aero_parameters.md (Note: simplified 25% MAC balance point is in MVP as D05) |
| W08 wingIncidence (direct editing) | 1.0 | aero_parameters.md |
| W06 wingTwist (direct editing) | 1.0 | aero_parameters.md |
| T15 vTailSweep (direct editing) | 1.0 | aero_parameters.md |
| F05/F06/F07 fuselage section lengths (direct editing) | 1.0 | aero_parameters.md |
| PR21 supportStrategy (direct editing) | 1.0 | aero_parameters.md |
| F14 wallThickness (direct editing) | 1.0 | aero_parameters.md |

---

*End of MVP Specification. This document supersedes all prior design documents for MVP scope decisions. For 1.0 and Future feature specifications, refer to the owning documents listed in Section 11.*
