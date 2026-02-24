# RC Plane Parametric Generator -- Parameter Specification

> **Author:** Aerospace Engineering Agent
> **Date:** 2026-02-23
> **Version:** 1.1-draft
> **Purpose:** Define every user-configurable and derived parameter for the parametric RC plane generator tool.
> **Fabrication:** Primary output is FDM 3D-printed parts; STL is the primary export format.
> **Backend:** CadQuery (Python) generates all parametric geometry on a local server.
> **Frontend:** Browser-based UI with Three.js viewport, communicating with the Python backend via HTTP/WebSocket.

---

## Table of Contents

1. [Document Conventions](#1-document-conventions)
2. [Global Parameters](#2-global-parameters)
3. [Fuselage](#3-fuselage)
4. [Wings](#4-wings)
5. [Tail / Empennage](#5-tail--empennage)
6. [Control Surfaces](#6-control-surfaces)
7. [Propulsion / Motor Mount](#7-propulsion--motor-mount)
8. [Landing Gear](#8-landing-gear)
9. [3D Printing / Fabrication Parameters](#9-3d-printing--fabrication-parameters)
10. [Derived / Computed Parameters](#10-derived--computed-parameters)
11. [Preset Configurations](#11-preset-configurations)
12. [Validation Rules](#12-validation-rules)
13. [Parameter Dependency Graph](#13-parameter-dependency-graph)

---

## 1. Document Conventions

### Parameter Table Columns

| Column | Meaning |
|--------|---------|
| **Name** | Internal parameter key (camelCase) and display label |
| **Description** | What the parameter controls |
| **Type** | `numeric`, `dropdown`, `toggle`, `slider`, `text`, `array` |
| **Unit** | Measurement unit (mm, deg, %, -- for unitless) |
| **Range** | Typical min/max for RC models |
| **Default** | Sensible default for a ~1m-span sport plane |
| **Scope** | `GLOBAL` or `COMPONENT` |
| **Depends On** | Other parameters this value is constrained by |
| **Phase** | `MVP`, `1.0`, or `Future` |

### Phase Definitions

| Phase | Description |
|-------|-------------|
| **MVP** | Minimum viable shape: basic fuselage + single-panel wing + simple tail. CadQuery generates solid geometry; STL export of each part. Basic print-bed sectioning for wings that exceed bed size. Enough to produce a printable, recognizable RC plane. |
| **1.0** | Full parameter set, presets, control surfaces, multi-panel wings, all tail types, basic validation and warnings. Print-oriented features: joinery (tongue-and-groove, dowel holes), hollowed shells, spar channels, configurable infill guidance, servo pockets. |
| **Future** | Simulation hooks, weight/balance, structural analysis, motor/prop database integration, slicer profile export, multi-material print support. |

### Technology Context

| Aspect | Decision |
|--------|----------|
| **Geometry Engine** | CadQuery (Python), built on OpenCascade BREP kernel. All parametric geometry is authored as CadQuery Workplane operations. |
| **Export Format** | STL (primary), STEP (secondary for CNC/advanced users). CadQuery exports via `cq.exporters.export()`. |
| **Fabrication** | FDM 3D printing is the primary fabrication method. Parameters must account for wall thickness, print orientation, bed size limits, part sectioning, and assembly joints. |
| **Deployment** | Docker containerized. Local: `docker run -p 8000:8000 cheng`. Cloud: Same image on Google Cloud Run. Backend is stateless — aerodynamic parameters are sent per-request from the browser. |
| **Architecture** | FastAPI backend (in Docker) runs CadQuery. Browser UI (Three.js) sends parameter JSON via HTTP, receives tessellated mesh for preview and STL blobs for download. Identical deployment in local and cloud modes. |
| **Data Flow** | `UI param change -> JSON POST to /api/generate -> CadQuery rebuilds geometry -> tessellated mesh returned -> Three.js renders preview`. Final STL export via `/api/export/stl`. Parameters are stateless; browser manages session state. |

---

## 2. Global Parameters

These appear in the **right-side Global Parameters panel** and affect the entire aircraft or multiple components.

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| G01 | `fuselagePreset` / **Fuselage** | Selects the fuselage shape template (Pod, Pod-and-Boom, Conventional, Blended-Wing-Body) | dropdown | -- | see Fuselage section | `Conventional` | GLOBAL | -- | MVP |
| G02 | `engineCount` / **Engines** | Number of engines/motors | numeric (integer) | -- | 0--4 | 1 | GLOBAL | -- | MVP |
| G03 | `wingSpan` / **Span** (wing) | Total wing tip-to-tip span | numeric | mm | 300--3000 | 1000 | GLOBAL | -- | MVP |
| G04 | `tailSpan` / **Span** (tail) | Horizontal stabilizer total span (or V-tail total projected span) | numeric | mm | 100--1200 | 350 | GLOBAL | `tailType` | MVP |
| G05 | `wingChord` / **Chord** | Wing root chord length | numeric | mm | 50--500 | 180 | GLOBAL | -- | MVP |
| G06 | `tailType` / **Tail Type** | Empennage configuration | dropdown | -- | Conventional, T-Tail, V-Tail, Cruciform, Inverted-V, Flying-Wing (none) | `Conventional` | GLOBAL | -- | MVP |
| G07 | `unitSystem` / **Units** | Display unit system | dropdown | -- | Metric (mm), Imperial (in) | `Metric` | GLOBAL | -- | 1.0 |
| G08 | `aircraftPreset` / **Aircraft Preset** | Load a complete preset configuration (Trainer, Sport, Glider, Aerobatic, Scale, Flying-Wing) | dropdown | -- | see Presets section | `Sport` | GLOBAL | -- | 1.0 |
| G09 | `symmetry` / **Symmetric Build** | Enforce left/right symmetry | toggle | -- | on/off | `on` | GLOBAL | -- | 1.0 |
| G10 | `designSpeed` / **Target Cruise Speed** | Estimated cruise speed for Reynolds number calculations | numeric | m/s | 5--50 | 15 | GLOBAL | -- | Future |

### Notes on Global Parameters

- The UI mockups show two "Span" fields in the right panel. Based on context (one for wing, one for tail), they map to `wingSpan` (G03) and `tailSpan` (G04).
- The "Chord" field in the right panel maps to `wingChord` (G05), which is the wing root chord. Tail chord is configured in the tail component panel.
- Changing `tailType` to "Flying-Wing" hides the tail component entirely and enables elevon parameters in the wing's control surface section.

---

## 3. Fuselage

Configurable when the fuselage body is selected in the viewport, or via the Global Parameters `fuselagePreset` dropdown.

### 3.1 Core Shape Parameters

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| F01 | `fuselageLength` / **Length** | Total fuselage length from nose tip to tail end | numeric | mm | 150--2000 | 300 | COMPONENT | -- | MVP |
| F02 | `fuselageWidth` / **Max Width** | Maximum cross-section width | numeric | mm | 20--300 | 50 | COMPONENT | -- | MVP |
| F03 | `fuselageHeight` / **Max Height** | Maximum cross-section height | numeric | mm | 20--300 | 55 | COMPONENT | -- | MVP |
| F04 | `fuselageShape` / **Cross-Section** | Cross-section profile shape | dropdown | -- | Circular, Oval, Rounded-Rectangle, Rectangular, Custom | `Oval` | COMPONENT | -- | 1.0 |
| F05 | `noseShape` / **Nose Shape** | Nose cone/profile type | dropdown | -- | Pointed, Rounded, Flat, Ogive, Elliptical | `Rounded` | COMPONENT | -- | MVP |
| F06 | `noseLength` / **Nose Length** | Length of the nose section (from tip to max cross-section) | numeric | mm | 10--500 | 60 | COMPONENT | `fuselageLength` | MVP |
| F07 | `tailTaper` / **Tail Taper Ratio** | Ratio of tail-end cross-section to max cross-section (0 = pointed, 1 = no taper) | slider | -- | 0.0--1.0 | 0.15 | COMPONENT | -- | MVP |
| F08 | `tailTaperLength` / **Tail Taper Length** | Length of the tapered tail section | numeric | mm | 20--800 | 80 | COMPONENT | `fuselageLength` | 1.0 |

### 3.2 Structural / Layout Parameters

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| F09 | `fuselageType` / **Fuselage Type** | Overall fuselage construction topology | dropdown | -- | Conventional, Pod-and-Boom, Twin-Boom, Nacelle (flying-wing) | `Conventional` | COMPONENT | `fuselagePreset` (G01) | 1.0 |
| F10 | `boomDiameter` / **Boom Diameter** | Tail boom diameter (only for Pod-and-Boom or Twin-Boom) | numeric | mm | 4--30 | 10 | COMPONENT | `fuselageType` = Pod-and-Boom or Twin-Boom | 1.0 |
| F11 | `boomLength` / **Boom Length** | Length of the tail boom from pod to empennage | numeric | mm | 100--1500 | 200 | COMPONENT | `fuselageType` = Pod-and-Boom or Twin-Boom | 1.0 |
| F12 | `wingMountPosition` / **Wing Mount Position** | Longitudinal position of the wing root leading edge along the fuselage, as a percentage of fuselage length measured from the nose | slider | % | 15--60 | 30 | COMPONENT | `fuselageLength` | MVP |
| F13 | `wingMountType` / **Wing Mount Type** | Vertical position of the wing relative to the fuselage | dropdown | -- | High-Wing, Mid-Wing, Low-Wing, Shoulder-Wing | `High-Wing` | COMPONENT | -- | MVP |
| F14 | `wallThickness` / **Wall Thickness** | Shell wall thickness for 3D-printed fuselage. Must be a multiple of nozzle diameter for clean FDM prints (e.g., 0.4mm nozzle -> 0.8, 1.2, 1.6mm walls). | numeric | mm | 0.8--5.0 | 1.6 | COMPONENT | -- | MVP |
| F15 | `hatchPosition` / **Hatch Position** | Location of the access hatch for battery/electronics | dropdown | -- | Top-Forward, Top-Center, Nose-Removable, None | `Top-Forward` | COMPONENT | -- | Future |
| F16 | `hatchLength` / **Hatch Length** | Length of the access hatch opening | numeric | mm | 30--300 | 80 | COMPONENT | `fuselageLength` | Future |
| F17 | `internalBayLength` / **Battery Bay Length** | Length reserved for battery/electronics bay | numeric | mm | 30--400 | 100 | COMPONENT | `fuselageLength` | Future |
| F18 | `internalBayWidth` / **Battery Bay Width** | Width of the internal bay | numeric | mm | 15--200 | 35 | COMPONENT | `fuselageWidth` | Future |

### 3.3 Fuselage Geometry Notes

- The `fuselageLength` default of 300mm matches the dimension annotation visible in the UI mockup.
- `wingMountPosition` at 30% means the wing leading edge sits 90mm back from the nose on a 300mm fuselage. This is a typical trainer/sport arrangement.
- For `Pod-and-Boom` type, the main fuselage pod is defined by F01--F08, and the boom extends rearward from the pod to the tail. The total aircraft length is `noseLength + podLength + boomLength`.
- For `Twin-Boom`, two booms extend aft from the wing, supporting a connecting horizontal stabilizer (like a P-38 layout).

### 3.4 Fuselage 3D Printing Notes

- **CadQuery approach:** The fuselage is modeled as a `cq.Workplane` loft through cross-section profiles at station points along the length, then shelled to `wallThickness`. The shell operation uses `cq.Solid.shell()`.
- **Print orientation:** The fuselage prints on its side (longest axis horizontal) for best surface quality and minimal supports. For fuselages longer than the print bed, CadQuery auto-sections at configurable cut planes (see Section 9).
- **Wall thickness** (F14) is now an MVP parameter since every 3D-printed part needs a defined shell thickness. Default of 1.6mm = 4 perimeters at 0.4mm nozzle width, which provides good strength for PLA/PETG.
- **Wing mount interface:** CadQuery generates matching slots/tabs at the wing mount position for wing-to-fuselage attachment. The joint geometry is parametric based on wing root chord and mount type.

---

## 4. Wings

Configurable when the wing is clicked/selected in the viewport. The UI mockup (screen 2) shows the bottom panel populating with wing-specific parameters when the wing is highlighted yellow.

### 4.1 Planform Parameters

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| W01 | `wingSpan` / **Span** | Total wingspan, tip to tip (mirrors G03) | numeric | mm | 300--3000 | 1000 | GLOBAL | -- | MVP |
| W02 | `wingRootChord` / **Root Chord** | Chord at the wing root (mirrors G05) | numeric | mm | 50--500 | 180 | GLOBAL | -- | MVP |
| W03 | `wingTipChord` / **Tip Chord** | Chord at the wing tip | numeric | mm | 20--500 | 120 | COMPONENT | `wingRootChord` | MVP |
| W04 | `wingTipRootRatio` / **Tip/Root Ratio** | Taper ratio = tipChord / rootChord. Adjusting this auto-calculates tipChord and vice versa. | slider | -- | 0.3--1.0 | 0.67 | COMPONENT | `wingRootChord`, `wingTipChord` | MVP |
| W05 | `wingSweep` / **Sweep** | Leading-edge sweep angle, positive = swept back | numeric | deg | -10--45 | 0 | COMPONENT | -- | MVP |
| W06 | `wingIncidence` / **Incidence** | Wing root incidence angle relative to fuselage datum (positive = leading edge up) | numeric | deg | -3--8 | 2 | COMPONENT | -- | MVP |
| W07 | `wingDihedral` / **Dihedral** | Dihedral angle of the main wing panel | numeric | deg | -10--15 | 3 | COMPONENT | -- | 1.0 |
| W08 | `wingSections` / **Sections** | Number of spanwise panels per half-wing (1 = straight, 2 = one break for polyhedral, 3 = two breaks) | numeric (integer) | -- | 1--4 | 1 | COMPONENT | -- | MVP |

### 4.2 Multi-Panel / Polyhedral Wing Parameters

When `wingSections` > 1, each panel beyond the first needs its own break position and dihedral angle. These are stored as arrays indexed by panel number.

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| W09 | `panelBreakPosition[n]` / **Panel n Break at** | Spanwise position of the break between panel n and panel n+1, as a percentage of the half-span | numeric | % | 20--90 | 60 (for n=1) | COMPONENT | `wingSections` >= n+1 | 1.0 |
| W10 | `panelDihedral[n]` / **Panel n Dihedral** | Dihedral angle for the n-th panel (panel 1 uses W07, panels 2+ defined here) | numeric | deg | -10--45 | 10 (outer panel) | COMPONENT | `wingSections` >= n | 1.0 |
| W11 | `panelSweep[n]` / **Panel n Sweep** | Sweep angle override for panel n (defaults to W05 if not set) | numeric | deg | -10--45 | (inherit W05) | COMPONENT | `wingSections` >= n | 1.0 |

### 4.3 Airfoil Parameters

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| W12 | `wingAirfoil` / **Airfoil** | Root airfoil profile selection | dropdown | -- | Flat-Plate, NACA-0012, NACA-2412, NACA-4412, NACA-6412, Clark-Y, Eppler-193, Eppler-387, Selig-1223, AG-Series, Custom-DAT | `Clark-Y` | COMPONENT | -- | MVP |
| W13 | `wingTipAirfoil` / **Tip Airfoil** | Tip airfoil (if different from root; enables blending) | dropdown | -- | (same list as W12) | (same as W12) | COMPONENT | -- | 1.0 |
| W14 | `wingThicknessScale` / **Thickness Scale** | Scale factor applied to the airfoil thickness distribution (1.0 = use airfoil as-is) | slider | -- | 0.5--2.0 | 1.0 | COMPONENT | `wingAirfoil` | 1.0 |
| W15 | `wingCamberScale` / **Camber Scale** | Scale factor applied to the airfoil camber line (1.0 = use airfoil as-is, 0.0 = symmetric) | slider | -- | 0.0--2.0 | 1.0 | COMPONENT | `wingAirfoil` | Future |

### 4.4 Twist / Washout

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| W16 | `wingWashout` / **Washout (Twist)** | Geometric twist at the tip relative to the root. Positive = tip leading edge rotated down (standard washout for stall safety). | numeric | deg | -3--6 | 2 | COMPONENT | -- | 1.0 |
| W17 | `washoutDistribution` / **Washout Distribution** | How twist is distributed along the span | dropdown | -- | Linear, Elliptical | `Linear` | COMPONENT | `wingWashout` | Future |

### 4.5 Structural / Construction

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| W18 | `sparPosition` / **Main Spar Position** | Chordwise position of the main spar channel as a percentage of chord from the leading edge. CadQuery cuts a circular or rectangular channel through the wing for a carbon/wood spar rod. | slider | % | 20--40 | 30 | COMPONENT | -- | 1.0 |
| W19 | `rearSparPosition` / **Rear Spar Position** | Chordwise position of the rear spar channel (for aileron hinge line and structural support) | slider | % | 55--80 | 70 | COMPONENT | `sparPosition` | 1.0 |
| W20 | `wingSkinThickness` / **Skin Thickness** | Wing shell wall thickness for 3D printing. Must produce printable walls (>= 2 perimeters). | numeric | mm | 0.8--3.0 | 1.2 | COMPONENT | -- | MVP |
| W21 | `sparChannelDiameter` / **Spar Channel Diameter** | Diameter of the spar rod channel cut through the wing (for carbon fiber or wooden dowel spar reinforcement) | numeric | mm | 2--10 | 4 | COMPONENT | `sparPosition` | 1.0 |
| W22 | `ribSpacing` / **Rib Spacing** | Distance between internal ribs (printed as part of the hollow wing structure) | numeric | mm | 15--100 | 40 | COMPONENT | -- | 1.0 |

### 4.6 Wing Geometry Notes

- **Tip/Root Ratio** (W04) and **Tip Chord** (W03) are linked: changing one auto-updates the other. The UI should display both but mark one as "derived." The mockup shows Tip/Root Ratio as the user-facing control.
- **Sweep** in the mockup shows 25 degrees. This maps to `wingSweep` (W05). The default is 0 deg (no sweep) for a typical trainer, but the mockup appears to show a sport/racer configuration.
- The mockup's **Sections** field corresponds to W08. For a basic straight rectangular wing, set to 1. For polyhedral (common in hand-launch gliders), set to 2 or 3.
- Airfoil selection (W12) appears as a dropdown in the mockup bottom panel. The dropdown should show common RC airfoils grouped by category:
  - **Flat/Thin:** Flat-Plate (for small/slow foamies)
  - **Symmetric:** NACA-0009, NACA-0012 (aerobatic)
  - **Light Camber:** NACA-2412, Clark-Y (trainer/sport)
  - **High Camber:** NACA-4412, NACA-6412, Eppler-193 (slow flyers, gliders)
  - **Specialty:** Selig-1223 (high-lift), AG-series (DLG gliders), Eppler-387 (low Re)

### 4.7 Wing 3D Printing Notes

- **CadQuery approach:** Each wing half is generated by lofting between airfoil profile `cq.Wire` objects placed at spanwise stations. The solid is then shelled to `wingSkinThickness`. Internal ribs are boolean-unioned at `ribSpacing` intervals. Spar channels are boolean-subtracted as cylinders at the specified chordwise position.
- **Print orientation:** Wing sections print with the trailing edge down and leading edge up, so the curved upper surface is the "top" face with best finish. This minimizes supports on the aerodynamic surface.
- **Sectioning:** Wings wider than the print bed are automatically sectioned into printable segments (see Section 9, `printBedX`/`printBedY`). Each segment gets matching tongue-and-groove joints at the cut planes. The spar channel passes through all segments for structural continuity.
- **Skin thickness** (W20) is promoted to MVP because every 3D-printed wing needs a defined shell. Default 1.2mm = 3 perimeters at 0.4mm nozzle.
- **Airfoil fidelity:** CadQuery interpolates airfoil .dat coordinates as B-spline wires. For FDM printing, sharp trailing edges are automatically thickened to a minimum of 0.8mm (2 nozzle widths) to be printable, with the trailing edge geometry blunted accordingly.

---

## 5. Tail / Empennage

Configurable when the tail is clicked in the viewport. The UI mockup (screen 3) shows tail-specific parameters in the bottom panel when the tail is highlighted yellow. The mockup shows a V-tail configuration.

### 5.1 Tail Type Selection

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| T01 | `tailType` / **Type** | Empennage configuration type (mirrors G06) | dropdown | -- | Conventional, T-Tail, V-Tail, Cruciform, Inverted-V, Flying-Wing | `Conventional` | GLOBAL | -- | MVP |

### 5.2 Horizontal Stabilizer (Conventional, T-Tail, Cruciform)

These parameters apply when `tailType` is Conventional, T-Tail, or Cruciform.

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| T02 | `hStabSpan` / **H-Stab Span** | Total horizontal stabilizer span | numeric | mm | 100--1200 | 350 | COMPONENT | -- | MVP |
| T03 | `hStabChord` / **H-Stab Chord** | Horizontal stabilizer root chord | numeric | mm | 30--250 | 100 | COMPONENT | -- | MVP |
| T04 | `hStabTipChord` / **H-Stab Tip Chord** | Horizontal stabilizer tip chord | numeric | mm | 20--250 | 80 | COMPONENT | `hStabChord` | 1.0 |
| T05 | `hStabAirfoil` / **H-Stab Airfoil** | Horizontal stabilizer airfoil | dropdown | -- | Flat-Plate, NACA-0009, NACA-0012, (same list as wing, but symmetric defaults) | `NACA-0009` | COMPONENT | -- | 1.0 |
| T06 | `hStabIncidence` / **H-Stab Incidence** | Horizontal stabilizer incidence angle relative to fuselage datum. Typically slightly negative for longitudinal trim. | numeric | deg | -5--5 | -1 | COMPONENT | -- | MVP |
| T07 | `hStabSweep` / **H-Stab Sweep** | Horizontal stabilizer leading-edge sweep | numeric | deg | 0--30 | 0 | COMPONENT | -- | 1.0 |
| T08 | `hStabDihedral` / **H-Stab Dihedral** | Horizontal stabilizer dihedral (0 for flat) | numeric | deg | -10--10 | 0 | COMPONENT | -- | 1.0 |

### 5.3 Vertical Stabilizer / Fin (Conventional, T-Tail, Cruciform)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| T09 | `vStabHeight` / **Fin Height** | Vertical fin height from fuselage top to fin tip | numeric | mm | 30--400 | 100 | COMPONENT | `tailType` != V-Tail, Inverted-V, Flying-Wing | MVP |
| T10 | `vStabRootChord` / **Fin Root Chord** | Vertical fin chord at the root | numeric | mm | 30--300 | 110 | COMPONENT | -- | MVP |
| T11 | `vStabTipChord` / **Fin Tip Chord** | Vertical fin chord at the tip | numeric | mm | 15--250 | 60 | COMPONENT | `vStabRootChord` | 1.0 |
| T12 | `vStabSweep` / **Fin Sweep** | Vertical fin leading-edge sweep angle | numeric | deg | 0--50 | 25 | COMPONENT | -- | 1.0 |
| T13 | `vStabAirfoil` / **Fin Airfoil** | Vertical fin airfoil (almost always symmetric) | dropdown | -- | Flat-Plate, NACA-0006, NACA-0009, NACA-0012 | `NACA-0009` | COMPONENT | -- | 1.0 |

### 5.4 V-Tail Parameters

When `tailType` = V-Tail or Inverted-V. These replace the separate horizontal/vertical stabilizer parameters. The mockup (screen 3) shows exactly this configuration.

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| T14 | `vTailDihedral` / **Dihedral** | V-tail dihedral angle. Standard V-tail ~30--45 deg; Inverted-V is negative. This is the angle of each V-tail surface from horizontal. | numeric | deg | 20--60 (V-Tail), -60-- -20 (Inverted-V) | 35 | COMPONENT | `tailType` = V-Tail or Inverted-V | MVP |
| T15 | `vTailAngle` / **Angle** | Included angle between the two V-tail surfaces (derived: 180 - 2 * dihedral, but can be set directly) | numeric | deg | 60--140 | 110 | COMPONENT | `vTailDihedral` | MVP |
| T16 | `vTailSpan` / **Span** | Total span of the V-tail (projected, tip to tip) | numeric | mm | 80--600 | 280 | COMPONENT | -- | MVP |
| T17 | `vTailChord` / **Chord** | V-tail surface root chord | numeric | mm | 30--200 | 90 | COMPONENT | -- | MVP |
| T18 | `vTailIncidence` / **Incidence** | Incidence angle of the V-tail surfaces | numeric | deg | -3--3 | 0 | COMPONENT | -- | MVP |
| T19 | `vTailAirfoil` / **V-Tail Airfoil** | Airfoil for V-tail surfaces (symmetric) | dropdown | -- | Flat-Plate, NACA-0006, NACA-0009, NACA-0012 | `NACA-0009` | COMPONENT | -- | 1.0 |
| T20 | `vTailSweep` / **V-Tail Sweep** | Leading-edge sweep of V-tail surfaces | numeric | deg | 0--30 | 5 | COMPONENT | -- | 1.0 |
| T21 | `vTailTipChord` / **V-Tail Tip Chord** | Chord at V-tail tip | numeric | mm | 15--150 | 55 | COMPONENT | `vTailChord` | 1.0 |

### 5.5 Tail Arm / Positioning

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| T22 | `tailArm` / **Tail Arm** | Distance from wing aerodynamic center (25% MAC) to the tail aerodynamic center. This is the primary driver of tail effectiveness. | numeric | mm | 80--1500 | 180 | COMPONENT | `fuselageLength`, `wingMountPosition` | MVP |
| T23 | `tailVerticalOffset` / **Vertical Offset** | Height of the tail relative to the fuselage center line. Positive = above (like T-tail), 0 = on the fuselage top. | numeric | mm | -50--150 | 0 | COMPONENT | `tailType` | 1.0 |

### 5.6 Tail Geometry Notes

- The mockup shows exactly six fields for the V-tail: Type, Dihedral, Angle, Span, Chord, Incident -- these map directly to T01, T14, T15, T16, T17, T18.
- **Dihedral** (T14) and **Angle** (T15) are interdependent: `Angle = 180 - 2 * Dihedral`. The UI should allow editing either one and auto-update the other.
- For **Conventional** tail, the bottom panel should show H-Stab and V-Stab parameters grouped separately.
- For **T-Tail**, same as Conventional but the horizontal stabilizer is mounted on top of the vertical fin. `tailVerticalOffset` (T23) auto-sets to the fin height.
- For **Cruciform**, horizontal stab is mounted partway up the vertical fin.
- For **Flying-Wing**, the tail section is entirely hidden and control is via elevons on the wing.
- **Tail arm** (T22) has a major impact on stability. A good rule of thumb for RC planes is `tailArm >= 2.5 * wingRootChord`. The system should warn if this is violated.

### 5.7 Tail 3D Printing Notes

- **CadQuery approach:** Tail surfaces are generated the same way as wings -- airfoil lofts shelled to wall thickness. For V-tail, the two surfaces are generated as mirrored copies rotated by the dihedral angle.
- **Assembly:** Tail surfaces attach to the fuselage (or tail boom) via printed sockets/tabs. CadQuery generates matching mortise-and-tenon joints at the root of each surface. For V-tail, the joint includes the correct dihedral angle.
- **Print considerations:** Tail surfaces are typically small enough to print in one piece. The thin airfoil sections at the tips will use the same trailing-edge thickening as the wing (minimum 0.8mm).

---

## 6. Control Surfaces

Configurable as sub-components when a wing or tail surface is selected. In the MVP, control surfaces are not individually configurable -- they are auto-generated with sensible defaults. In 1.0, they get full parameter sets.

### 6.1 Ailerons (Wing)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| C01 | `aileronEnable` / **Ailerons** | Enable aileron cutouts on the wing | toggle | -- | on/off | `on` | COMPONENT | -- | 1.0 |
| C02 | `aileronSpanStart` / **Aileron Inboard** | Inboard edge of the aileron as % of half-span from root | slider | % | 30--70 | 55 | COMPONENT | `wingSpan`, `aileronEnable` | 1.0 |
| C03 | `aileronSpanEnd` / **Aileron Outboard** | Outboard edge of the aileron as % of half-span from root | slider | % | 70--98 | 95 | COMPONENT | `wingSpan`, `aileronEnable` | 1.0 |
| C04 | `aileronChordPercent` / **Aileron Chord %** | Aileron chord as a percentage of the local wing chord | slider | % | 15--40 | 25 | COMPONENT | -- | 1.0 |
| C05 | `aileronMaxDeflection` / **Aileron Max Deflection** | Maximum deflection angle (for animation/validation only) | numeric | deg | 10--45 | 25 | COMPONENT | -- | Future |

### 6.2 Flaps (Wing)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| C06 | `flapEnable` / **Flaps** | Enable flap cutouts on the wing | toggle | -- | on/off | `off` | COMPONENT | -- | 1.0 |
| C07 | `flapSpanStart` / **Flap Inboard** | Inboard edge of the flap as % of half-span | slider | % | 5--30 | 10 | COMPONENT | `wingSpan`, `flapEnable` | 1.0 |
| C08 | `flapSpanEnd` / **Flap Outboard** | Outboard edge of the flap as % of half-span | slider | % | 30--65 | 50 | COMPONENT | `wingSpan`, `aileronSpanStart`, `flapEnable` | 1.0 |
| C09 | `flapChordPercent` / **Flap Chord %** | Flap chord as a percentage of the local wing chord | slider | % | 15--40 | 25 | COMPONENT | -- | 1.0 |
| C10 | `flapType` / **Flap Type** | Flap hinge mechanism type | dropdown | -- | Plain, Slotted | `Plain` | COMPONENT | -- | Future |

### 6.3 Elevator (Horizontal Stabilizer)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| C11 | `elevatorEnable` / **Elevator** | Enable elevator on the horizontal stabilizer | toggle | -- | on/off | `on` | COMPONENT | `tailType` != Flying-Wing | 1.0 |
| C12 | `elevatorSpanPercent` / **Elevator Span %** | Elevator span as percentage of total H-stab span | slider | % | 50--100 | 100 | COMPONENT | `hStabSpan` | 1.0 |
| C13 | `elevatorChordPercent` / **Elevator Chord %** | Elevator chord as a percentage of the H-stab chord | slider | % | 20--50 | 35 | COMPONENT | `hStabChord` | 1.0 |
| C14 | `allMovingStab` / **All-Moving Stabilizer** | Make the entire horizontal stabilizer a moving surface (stabilator) | toggle | -- | on/off | `off` | COMPONENT | `tailType` = Conventional | Future |

### 6.4 Rudder (Vertical Stabilizer)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| C15 | `rudderEnable` / **Rudder** | Enable rudder on the vertical fin | toggle | -- | on/off | `on` | COMPONENT | `tailType` has vertical fin | 1.0 |
| C16 | `rudderHeightPercent` / **Rudder Height %** | Rudder height as percentage of fin height | slider | % | 50--100 | 90 | COMPONENT | `vStabHeight` | 1.0 |
| C17 | `rudderChordPercent` / **Rudder Chord %** | Rudder chord as a percentage of the fin chord | slider | % | 20--50 | 35 | COMPONENT | `vStabRootChord` | 1.0 |

### 6.5 Ruddervators (V-Tail Control Surfaces)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| C18 | `ruddervatorEnable` / **Ruddervators** | Enable ruddervator cutouts on V-tail surfaces | toggle | -- | on/off | `on` | COMPONENT | `tailType` = V-Tail or Inverted-V | 1.0 |
| C19 | `ruddervatorChordPercent` / **Ruddervator Chord %** | Ruddervator chord as percentage of V-tail chord | slider | % | 20--50 | 35 | COMPONENT | `vTailChord` | 1.0 |
| C20 | `ruddervatorSpanPercent` / **Ruddervator Span %** | Ruddervator span as percentage of total V-tail surface span | slider | % | 60--100 | 90 | COMPONENT | `vTailSpan` | 1.0 |

### 6.6 Elevons (Flying-Wing / Delta)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| C21 | `elevonEnable` / **Elevons** | Enable elevon cutouts (for flying-wing/delta configurations) | toggle | -- | on/off | `on` | COMPONENT | `tailType` = Flying-Wing | 1.0 |
| C22 | `elevonSpanStart` / **Elevon Inboard** | Inboard edge of the elevon as % of half-span | slider | % | 10--40 | 20 | COMPONENT | `wingSpan`, `elevonEnable` | 1.0 |
| C23 | `elevonSpanEnd` / **Elevon Outboard** | Outboard edge of the elevon as % of half-span | slider | % | 60--98 | 90 | COMPONENT | `wingSpan`, `elevonEnable` | 1.0 |
| C24 | `elevonChordPercent` / **Elevon Chord %** | Elevon chord as a percentage of local wing chord | slider | % | 15--35 | 20 | COMPONENT | -- | 1.0 |

### 6.7 Control Surface Notes

- Control surfaces in the MVP are **not individually configurable**. The geometry generator should auto-place them at sensible defaults. Cutouts appear visually but without configurable dimensions.
- In 1.0, the user can click on a control surface in the viewport to expand its parameter sub-panel.
- Flaps and ailerons must not overlap spanwise. The system should enforce `flapSpanEnd <= aileronSpanStart` with a small gap (2% span) for the gap seal.
- For V-tail, ruddervators combine elevator and rudder function. Differential mixing is a radio/transmitter concern, not a geometry concern, but the physical surface dimensions matter.

### 6.8 Control Surface 3D Printing Notes

- **CadQuery approach:** Control surfaces are modeled as separate bodies, boolean-subtracted from the parent wing/tail solid along the hinge line. This produces the parent body with a cutout and a separate control surface body. Both are exported as individual STL files.
- **Hinge gap:** A configurable gap (default 0.5mm per side, 1.0mm total) is added between the control surface and the parent body to allow free rotation after printing and assembly.
- **Hinge provisions:** CadQuery generates small cylindrical holes along the hinge line for hinge pins (piano wire). Pin hole diameter is configurable (default 1.5mm for 1.2mm piano wire + clearance).
- **Servo pockets:** In 1.0, CadQuery can boolean-subtract a rectangular pocket in the wing skin near the control surface for flush-mounting a micro servo. Pocket dimensions are parametric based on common servo sizes (9g micro servo default: 23x12x22mm).

---

## 7. Propulsion / Motor Mount

### 7.1 Configuration

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| P01 | `propulsionType` / **Propulsion Type** | Type of propulsion | dropdown | -- | Electric, Glider (none) | `Electric` | GLOBAL | -- | 1.0 |
| P02 | `motorConfig` / **Motor Configuration** | Tractor (front-pulling) or Pusher (rear-pushing) | dropdown | -- | Tractor, Pusher | `Tractor` | COMPONENT | `propulsionType` = Electric | MVP |
| P03 | `engineCount` / **Engine Count** | Number of motors (mirrors G02) | numeric (integer) | -- | 0--4 | 1 | GLOBAL | -- | MVP |

### 7.2 Motor Mount Geometry

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| P04 | `motorMountDiameter` / **Mount Diameter** | Motor mount boss/ring outer diameter | numeric | mm | 10--60 | 28 | COMPONENT | -- | 1.0 |
| P05 | `motorMountDepth` / **Mount Depth** | Depth of the motor mount into the fuselage/nacelle | numeric | mm | 5--50 | 20 | COMPONENT | -- | 1.0 |
| P06 | `downThrust` / **Down-Thrust Angle** | Motor tilt downward from fuselage datum. Compensates for pitch-up tendency under power. | numeric | deg | 0--8 | 2 | COMPONENT | -- | 1.0 |
| P07 | `rightThrust` / **Right-Thrust Angle** | Motor tilt to the right. Compensates for P-factor and torque roll on single-engine tractor configs. | numeric | deg | 0--5 | 1 | COMPONENT | `motorConfig` = Tractor | 1.0 |

### 7.3 Propeller Clearance

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| P08 | `propDiameter` / **Prop Diameter** | Propeller diameter for clearance checking | numeric | mm | 50--500 | 200 | COMPONENT | -- | 1.0 |
| P09 | `propClearanceMin` / **Min Prop Clearance** | Minimum clearance between prop tip and any surface | numeric | mm | 5--50 | 10 | COMPONENT | `propDiameter` | 1.0 |
| P10 | `spinnerDiameter` / **Spinner Diameter** | Diameter of the prop spinner/nose cone (visual only) | numeric | mm | 10--60 | 30 | COMPONENT | `motorMountDiameter` | 1.0 |
| P11 | `spinnerLength` / **Spinner Length** | Length of the prop spinner | numeric | mm | 10--80 | 25 | COMPONENT | -- | 1.0 |

### 7.4 Multi-Engine Placement

When `engineCount` > 1:

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| P12 | `engineSpanPosition[n]` / **Engine n Span Position** | Spanwise position of engine n as % of half-span | numeric | % | 15--60 | 33 | COMPONENT | `engineCount` > 1 | 1.0 |
| P13 | `engineMountType[n]` / **Engine n Mount** | How the engine is mounted (under-wing pylon, wing-leading-edge, nacelle) | dropdown | -- | Under-Wing, Leading-Edge, Pod-Nacelle | `Under-Wing` | COMPONENT | `engineCount` > 1 | Future |

### 7.5 Motor/Prop Database (Future)

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| P14 | `motorSelection` / **Motor** | Select motor from database (provides weight, kV, max current) | dropdown (database) | -- | (database lookup) | -- | COMPONENT | -- | Future |
| P15 | `propSelection` / **Propeller** | Select propeller from database (provides diameter, pitch, weight) | dropdown (database) | -- | (database lookup) | -- | COMPONENT | -- | Future |
| P16 | `batterySelection` / **Battery** | Battery pack selection (provides weight, voltage, capacity) | dropdown (database) | -- | (database lookup) | -- | COMPONENT | -- | Future |

### 7.6 Propulsion 3D Printing Notes

- **CadQuery approach:** The motor mount is a cylindrical boss or plate generated at the nose (tractor) or tail (pusher) of the fuselage. CadQuery creates bolt-hole patterns for common motor mount patterns (M2/M3 screws in 16mm, 19mm, or 25mm hole spacing).
- **Firewall:** For tractor configurations, CadQuery generates a flat motor-mount plate (firewall) at the nose with configurable thickness (2--4mm, thicker than wall thickness for structural rigidity) and the specified down-thrust and right-thrust angles built into the plate angle.
- **Spinner:** The spinner is a separate body, modeled as a CadQuery `cq.Workplane.revolve()` of a nose-cone profile. Exported as a separate STL.

---

## 8. Landing Gear

### 8.1 Configuration

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| L01 | `landingGearType` / **Gear Type** | Landing gear configuration | dropdown | -- | None (belly-land), Tricycle, Taildragger, Skid | `None` | COMPONENT | -- | 1.0 |
| L02 | `gearRetractable` / **Retractable** | Whether landing gear retracts | toggle | -- | on/off | `off` | COMPONENT | `landingGearType` != None | Future |

### 8.2 Main Gear

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| L03 | `mainGearPosition` / **Main Gear Position** | Longitudinal position of main gear as % of fuselage length from nose. Should be behind CG for tricycle, at/ahead of CG for taildragger. | slider | % | 25--55 | 35 | COMPONENT | `landingGearType` = Tricycle or Taildragger | 1.0 |
| L04 | `mainGearHeight` / **Main Gear Height** | Height of the main gear strut (determines ground clearance) | numeric | mm | 15--150 | 40 | COMPONENT | `landingGearType` != None | 1.0 |
| L05 | `mainGearTrack` / **Main Gear Track** | Lateral distance between left and right main wheels | numeric | mm | 30--400 | 120 | COMPONENT | `landingGearType` != None, != Skid | 1.0 |
| L06 | `mainWheelDiameter` / **Main Wheel Diameter** | Diameter of the main wheels | numeric | mm | 10--80 | 30 | COMPONENT | `landingGearType` != None, != Skid | 1.0 |
| L07 | `gearSweep` / **Gear Sweep** | Forward/aft rake of the main gear struts, viewed from the side. Positive = swept aft. | numeric | deg | -15--30 | 5 | COMPONENT | -- | Future |

### 8.3 Nose / Tail Wheel

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| L08 | `noseGearHeight` / **Nose Gear Height** | Height of the nose gear strut (tricycle only) | numeric | mm | 15--150 | 45 | COMPONENT | `landingGearType` = Tricycle | 1.0 |
| L09 | `noseWheelDiameter` / **Nose Wheel Diameter** | Diameter of the nose wheel | numeric | mm | 8--60 | 20 | COMPONENT | `landingGearType` = Tricycle | 1.0 |
| L10 | `tailWheelDiameter` / **Tail Wheel Diameter** | Diameter of the tail wheel (taildragger only) | numeric | mm | 5--40 | 12 | COMPONENT | `landingGearType` = Taildragger | 1.0 |
| L11 | `tailGearPosition` / **Tail Gear Position** | Longitudinal position of tail wheel as % of fuselage length from nose | slider | % | 85--98 | 92 | COMPONENT | `landingGearType` = Taildragger | 1.0 |

### 8.4 Landing Gear Notes

- Many small RC planes use belly landing with no gear at all -- hence the default of `None`.
- For the MVP, landing gear is not generated. It becomes available in 1.0.
- Main gear position relative to CG is critical for ground handling. For tricycle configuration, the main gear should be 10--20mm behind the CG. For taildragger, the main gear should be at or slightly forward of the CG.
- The system should validate that `propClearanceMin` (P09) is satisfied with the chosen gear height and prop diameter.

### 8.5 Landing Gear 3D Printing Notes

- **CadQuery approach:** Gear struts are modeled as swept profiles (airfoil or rectangular cross-section). Wheel pants are optional revolve bodies. Mounting tabs are boolean-unioned to the fuselage bottom.
- **Material note:** Landing gear struts take impact loads. 3D-printed PLA gear is fragile. The system should note that gear struts may benefit from being printed in PETG/Nylon or replaced with bent music wire (the printed part then becomes a wire-guide bracket). CadQuery generates wire-guide brackets as an alternative to solid printed struts.

---

## 9. 3D Printing / Fabrication Parameters

These parameters control how the aerodynamic geometry is processed for FDM 3D printing. They affect part sectioning, joinery, shell structure, and export.

### 9.1 Print Bed and Sectioning

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| PR01 | `printBedX` / **Print Bed X** | Maximum print bed dimension along X (longest axis) | numeric | mm | 100--500 | 220 | GLOBAL | -- | MVP |
| PR02 | `printBedY` / **Print Bed Y** | Maximum print bed dimension along Y | numeric | mm | 100--500 | 220 | GLOBAL | -- | MVP |
| PR03 | `printBedZ` / **Print Bed Z** | Maximum print height | numeric | mm | 50--500 | 250 | GLOBAL | -- | MVP |
| PR04 | `autoSection` / **Auto-Section Parts** | Automatically split parts that exceed print bed dimensions into printable sections | toggle | -- | on/off | `on` | GLOBAL | `printBedX`, `printBedY`, `printBedZ` | MVP |
| PR05 | `sectionOverlap` / **Joint Overlap** | Length of the tongue-and-groove overlap at each section joint | numeric | mm | 5--30 | 15 | GLOBAL | `autoSection` | MVP |

### 9.2 Shell and Wall Settings

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| PR06 | `nozzleDiameter` / **Nozzle Diameter** | FDM nozzle diameter; wall thickness should be a multiple of this | numeric | mm | 0.2--1.0 | 0.4 | GLOBAL | -- | MVP |
| PR07 | `layerHeight` / **Layer Height** | Print layer height; affects minimum feature resolution | numeric | mm | 0.05--0.4 | 0.2 | GLOBAL | -- | 1.0 |
| PR08 | `minFeatureThickness` / **Min Feature Thickness** | Minimum printable wall/feature thickness (typically 2 * nozzle diameter) | numeric (derived) | mm | -- | 0.8 | GLOBAL | `nozzleDiameter` | MVP |
| PR09 | `trailingEdgeMinThickness` / **TE Min Thickness** | Minimum trailing edge thickness for airfoils; sharp TEs are automatically blunted to this value | numeric | mm | 0.4--2.0 | 0.8 | GLOBAL | `nozzleDiameter` | MVP |

### 9.3 Joinery / Assembly

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| PR10 | `jointType` / **Joint Type** | Type of joint between sectioned parts | dropdown | -- | Tongue-and-Groove, Dowel-Pin, Flat-with-Alignment-Pins | `Tongue-and-Groove` | GLOBAL | -- | MVP |
| PR11 | `jointTolerance` / **Joint Tolerance** | Clearance added to the mating face of joints for press-fit assembly (per side) | numeric | mm | 0.05--0.5 | 0.15 | GLOBAL | -- | MVP |
| PR12 | `dowelDiameter` / **Dowel Pin Diameter** | Diameter of alignment dowel holes (if joint type uses dowels) | numeric | mm | 2--8 | 3 | GLOBAL | `jointType` = Dowel-Pin or Flat-with-Alignment-Pins | 1.0 |
| PR13 | `hingePinDiameter` / **Hinge Pin Hole Diameter** | Diameter of holes for control surface hinge pins (piano wire) | numeric | mm | 0.8--3.0 | 1.5 | GLOBAL | -- | 1.0 |

### 9.4 Internal Structure

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| PR14 | `hollowParts` / **Hollow Parts** | Generate parts as hollow shells with internal ribs (vs solid for very small parts) | toggle | -- | on/off | `on` | GLOBAL | -- | MVP |
| PR15 | `sparChannelEnabled` / **Spar Channels** | Cut channels through wing sections for carbon fiber or wood spar rods | toggle | -- | on/off | `on` | GLOBAL | -- | 1.0 |
| PR16 | `servoPocketEnabled` / **Servo Pockets** | Cut rectangular pockets into wing/fuselage for flush-mounted servos | toggle | -- | on/off | `off` | GLOBAL | -- | 1.0 |
| PR17 | `servoPocketWidth` / **Servo Pocket Width** | Width of the servo pocket cutout | numeric | mm | 8--25 | 12 | COMPONENT | `servoPocketEnabled` | 1.0 |
| PR18 | `servoPocketLength` / **Servo Pocket Length** | Length of the servo pocket cutout | numeric | mm | 15--35 | 23 | COMPONENT | `servoPocketEnabled` | 1.0 |
| PR19 | `servoPocketDepth` / **Servo Pocket Depth** | Depth of the servo pocket cutout | numeric | mm | 8--30 | 22 | COMPONENT | `servoPocketEnabled` | 1.0 |

### 9.5 Export Settings

| # | Name | Description | Type | Unit | Range | Default | Scope | Depends On | Phase |
|---|------|-------------|------|------|-------|---------|-------|------------|-------|
| PR20 | `exportFormat` / **Export Format** | Primary export file format | dropdown | -- | STL, STEP, Both | `STL` | GLOBAL | -- | MVP |
| PR21 | `stlTolerance` / **STL Tolerance** | Angular tolerance for STL tessellation. Lower = smoother surface, larger file. CadQuery `exportStl(tolerance=...)`. | numeric | -- | 0.001--0.1 | 0.01 | GLOBAL | -- | MVP |
| PR22 | `stlAscii` / **STL ASCII Mode** | Export STL in ASCII (human-readable) vs binary (compact) format | toggle | -- | on/off | `off` (binary) | GLOBAL | -- | 1.0 |
| PR23 | `exportPerPart` / **Export Per Part** | Export each component (fuselage, left wing, right wing, tail, etc.) as a separate STL file vs one combined file | toggle | -- | on/off | `on` | GLOBAL | -- | MVP |
| PR24 | `stepExport` / **STEP Export** | Also generate a STEP file for CNC machining or advanced CAD use | toggle | -- | on/off | `off` | GLOBAL | -- | 1.0 |

### 9.6 Export and Deployment Notes

**Export behavior (both modes identical):**
- **STL/STEP streaming:** All exports are streamed as HTTP responses. No temporary files are stored in cloud mode. Local mode may cache files in Docker volume `/data/exports/` temporarily during multi-part zips.
- **Auto-sectioning applies identically:** Print bed sectioning (Section 9.1) works the same in both local and cloud deployments. Multi-part assemblies are automatically detected and exported as separate files in a zip archive.

**3D Printing notes:**
- **Why print bed size matters for MVP:** A 1000mm wingspan cannot fit on a 220mm print bed. The system MUST section wings automatically. For a 1000mm span with 220mm bed, each half-wing (500mm) is cut into 3 sections (~167mm each), each with tongue-and-groove joints and aligned spar channels.
- **CadQuery sectioning approach:** After generating the complete solid for a component (e.g., left wing half), CadQuery performs a series of `cq.Workplane.cut()` operations with planar boxes at the section boundaries. Each resulting fragment gets tongue/groove features added via boolean union/subtract.
- **Joint tolerance** (PR11) is critical for usable prints. 0.15mm per side means a total gap of 0.3mm on a mating surface. This should be tunable since every printer is slightly different. The UI should include a "print test joint" button that exports a small test piece.
- **STL tolerance** (PR21) controls the `tolerance` parameter in `cq.exporters.export(shape, 'output.stl', tolerance=0.01)`. Default of 0.01 gives smooth curves suitable for RC planes without excessively large files.
- **Per-part export** (PR23) is essential for 3D printing -- each part needs to be individually oriented and sliced. The export produces a zip file containing named STLs: `fuselage_section_1.stl`, `wing_left_1.stl`, `wing_left_2.stl`, `tail_vtail_left.stl`, etc.

---

## 10. Derived / Computed Parameters

These are **read-only** parameters calculated from user inputs. They appear in an information panel and are used for validation warnings.

### 10.1 Wing Geometry (Derived)

| # | Name | Formula / Source | Unit | Typical RC Range | Phase |
|---|------|-----------------|------|-----------------|-------|
| D01 | `wingArea` / **Wing Area** | Sum of panel areas (for straight taper: `0.5 * (rootChord + tipChord) * span`) | mm^2 (display as dm^2 or cm^2) | 5--100 dm^2 | MVP |
| D02 | `aspectRatio` / **Aspect Ratio** | `span^2 / wingArea` | -- | 4--20 | MVP |
| D03 | `meanAeroChord` / **MAC** | `(2/3) * rootChord * (1 + taperRatio + taperRatio^2) / (1 + taperRatio)` | mm | 50--400 | MVP |
| D04 | `taperRatio` / **Taper Ratio** | `tipChord / rootChord` (same as W04, just re-derived for clarity) | -- | 0.3--1.0 | MVP |
| D05 | `wingLoading` / **Wing Loading** | `estimatedWeight / wingArea` | g/dm^2 | 10--120 | 1.0 |
| D06 | `reynoldsNumber` / **Reynolds Number** | `(designSpeed * MAC) / kinematicViscosity` (at sea level) | -- | 50,000--500,000 | Future |

### 10.2 Stability (Derived)

| # | Name | Formula / Source | Unit | Typical RC Range | Phase |
|---|------|-----------------|------|-----------------|-------|
| D07 | `horizontalTailVolume` / **H-Tail Volume Coeff** | `(hStabArea * tailArm) / (wingArea * MAC)` | -- | 0.35--0.75 | 1.0 |
| D08 | `verticalTailVolume` / **V-Tail Volume Coeff** | `(vStabArea * tailArm) / (wingArea * span)` | -- | 0.02--0.06 | 1.0 |
| D09 | `cgPosition` / **CG Position** | Estimated CG as % of MAC from the leading edge (target: 25--35% MAC) | % MAC | 20--40 | 1.0 |
| D10 | `staticMargin` / **Static Margin** | `(neutralPoint - cgPosition) / MAC * 100` | % MAC | 5--20 | Future |

### 10.3 Weight Estimation (Derived)

| # | Name | Formula / Source | Unit | Typical RC Range | Phase |
|---|------|-----------------|------|-----------------|-------|
| D11 | `estimatedAirframeWeight` / **Airframe Weight** | Calculated from CadQuery solid volumes, shell thickness, and material density (PLA ~1.24 g/cm^3, PETG ~1.27, LW-PLA ~0.6 with foaming). Backend computes `volume = shape.Volume()` for each part. | g | 20--2000 | Future |
| D12 | `estimatedAllUpWeight` / **All-Up Weight** | Airframe + motor + battery + servos + receiver + estimated wiring | g | 50--5000 | Future |
| D13 | `estimatedStallSpeed` / **Stall Speed** | `sqrt(2 * weight / (airDensity * wingArea * clMax))` | m/s | 2--15 | Future |

### 10.4 Derived Parameter Notes

- In the **MVP**, only wing area (D01), aspect ratio (D02), MAC (D03), and taper ratio (D04) are computed. These are cheap to calculate and provide immediate feedback.
- **Wing loading** (D05) requires at least an estimated total weight. In 1.0, this can be done with a simple user-entered "target weight" field, or auto-estimated from surface areas.
- **Tail volume coefficients** (D07, D08) are the single most important stability sanity checks. The system should flag these with warnings if they fall outside typical ranges.
- For V-tail, the tail volume contribution is split between pitch and yaw. The effective horizontal area is `vTailArea * cos^2(dihedral)` and the effective vertical area is `vTailArea * sin^2(dihedral)`.

---

## 11. Preset Configurations

Presets populate all parameters with values for common RC aircraft types. Users can load a preset and then tweak individual parameters.

### Preset Storage

- **Bundled presets:** All standard presets are bundled in the Docker image (read-only).
- **Local mode (Docker):** Custom user presets are saved to Docker volume `/data/presets/`.
- **Cloud mode (Google Cloud Run):** Custom presets are saved to browser IndexedDB, avoiding cloud storage overhead. Users can export/import presets as JSON files.
- **Parameter values unchanged:** No changes to preset definitions or their parameter values.

### 11.1 MVP Presets (Phase: 1.0)

| Preset | Description | Span | Chord | Airfoil | Sweep | Tail | Typical Use |
|--------|-------------|------|-------|---------|-------|------|-------------|
| **Trainer** | High-wing, flat-bottom airfoil, gentle handling | 1200 | 200 | Clark-Y | 0 | Conventional | Learning to fly |
| **Sport** | Mid-wing, moderate speed, versatile | 1000 | 180 | NACA-2412 | 0--5 | Conventional | General sport flying |
| **Glider** | High AR, polyhedral, high-lift airfoil | 1500 | 150 | Eppler-387 | 0 | Conventional or V-Tail | Thermal soaring |
| **Aerobatic** | Mid-wing, symmetric airfoil, short coupling | 900 | 220 | NACA-0012 | 0 | Conventional | 3D/aerobatics |
| **Delta / Flying Wing** | Swept wing, no tail, elevons | 800 | 300 | NACA-0012 | 30 | Flying-Wing | Speed, FPV |
| **Scale WW2 Fighter** | Low-wing, tapered, retractable gear | 1100 | 200 | NACA-2412 | 5 | Conventional | Scale appearance |
| **Micro Foamie** | Small, lightweight, slow | 400 | 100 | Flat-Plate | 0 | Conventional | Indoor/park flying |

### 11.2 Preset Application Rules

- Loading a preset overwrites all current parameters.
- The UI should show a confirmation dialog before applying a preset.
- After loading, all parameters are editable -- the preset is just a starting point.
- A "Custom" option in the preset dropdown means the user has modified parameters away from any standard preset.

---

## 12. Validation Rules

The system should actively warn (not block) the user when parameters produce aerodynamically questionable or unprintable configurations. All validations are **non-blocking warnings** shown in the UI.

### 12.1 Structural / Geometric Validation (Phase: MVP)

| Rule ID | Condition | Warning Message |
|---------|-----------|-----------------|
| V01 | `wingSpan > 10 * fuselageLength` | "Very high aspect ratio relative to fuselage -- may be structurally fragile" |
| V02 | `taperRatio < 0.3` | "Very aggressive taper ratio -- tip stall risk" |
| V03 | `fuselageLength < wingRootChord` | "Fuselage is shorter than the wing chord -- unusual configuration" |
| V04 | `tailArm < 2 * meanAeroChord` | "Short tail arm -- may have insufficient pitch stability" |
| V05 | `wingTipChord < 30 mm` | "Extremely small tip chord -- may be difficult to build" |

### 12.2 Aerodynamic Validation (Phase: 1.0)

| Rule ID | Condition | Warning Message |
|---------|-----------|-----------------|
| V06 | `horizontalTailVolume < 0.3` | "Low horizontal tail volume -- may be pitch-unstable" |
| V07 | `horizontalTailVolume > 0.8` | "High horizontal tail volume -- may be overly stable / sluggish in pitch" |
| V08 | `verticalTailVolume < 0.02` | "Low vertical tail volume -- may lack directional stability" |
| V09 | `wingLoading > 80 g/dm^2` | "High wing loading -- needs fast landing speed, not beginner-friendly" |
| V10 | `wingLoading < 10 g/dm^2` | "Very low wing loading -- highly wind-sensitive" |
| V11 | `aspectRatio > 15 and wingSweep > 10` | "High AR with significant sweep -- potential flutter risk" |
| V12 | `wingIncidence < 0` | "Negative wing incidence -- the plane will want to fly inverted at cruise" |
| V13 | `wingSweep > 15 and tailType = Flying-Wing and wingWashout < 3` | "Swept flying wing with low washout -- tip stall and tumble risk" |

### 12.3 Propulsion Validation (Phase: 1.0)

| Rule ID | Condition | Warning Message |
|---------|-----------|-----------------|
| V14 | `propDiameter / 2 > mainGearHeight + fuselageHeight / 2` (tractor) | "Prop may strike the ground -- increase gear height or reduce prop diameter" |
| V15 | `motorConfig = Pusher and tailType = Conventional` | "Pusher with conventional tail -- ensure tail structure clears the prop arc" |

### 12.4 3D Printing Validation (Phase: MVP)

| Rule ID | Condition | Warning Message |
|---------|-----------|-----------------|
| V16 | `wallThickness < 2 * nozzleDiameter` | "Wall thickness should be at least 2x nozzle diameter for solid perimeters" |
| V17 | `wallThickness % nozzleDiameter != 0` (approx) | "Wall thickness is not a clean multiple of nozzle diameter -- may produce gaps between perimeters" |
| V18 | `wingSkinThickness < 2 * nozzleDiameter` | "Wing skin too thin for reliable FDM printing" |
| V19 | `wingTipChord * wingAirfoilMaxThickness < minFeatureThickness` | "Wing tip is thinner than minimum printable feature -- consider increasing tip chord or airfoil thickness" |
| V20 | `any part dimension > printBedX or printBedY or printBedZ` (without sectioning) | "Part exceeds print bed -- enable auto-sectioning or reduce dimensions" |
| V21 | `sectionOverlap < 10 and wingSpan > 800` | "Joint overlap may be too short for structural integrity on this span -- increase to 15mm+" |
| V22 | `jointTolerance > 0.3` | "Large joint tolerance -- parts may be loose. Consider 0.10--0.20mm for press-fit" |
| V23 | `jointTolerance < 0.05` | "Very tight joint tolerance -- parts may not fit. Most FDM printers need 0.10mm+ clearance" |

---

## 13. Parameter Dependency Graph

This section documents which parameters affect or constrain other parameters. The UI should reactively update dependent fields and show/hide conditional sections.

### 13.1 Visibility Dependencies

These control which sections/fields are visible in the UI:

```
tailType = "Flying-Wing"
  -> HIDE: entire Tail section (T02-T23)
  -> SHOW: elevon controls (C21-C24)
  -> HIDE: elevator controls (C11-C14)
  -> HIDE: rudder controls (C15-C17)

tailType = "V-Tail" or "Inverted-V"
  -> HIDE: H-Stab parameters (T02-T08)
  -> HIDE: V-Stab parameters (T09-T13)
  -> SHOW: V-Tail parameters (T14-T21)
  -> SHOW: ruddervator controls (C18-C20)
  -> HIDE: separate elevator/rudder controls

tailType = "Conventional" or "Cruciform"
  -> SHOW: H-Stab parameters (T02-T08)
  -> SHOW: V-Stab parameters (T09-T13)
  -> HIDE: V-Tail parameters (T14-T21)

tailType = "T-Tail"
  -> Same as Conventional, but tailVerticalOffset (T23) auto-locks to vStabHeight (T09)

fuselageType = "Pod-and-Boom" or "Twin-Boom"
  -> SHOW: boomDiameter (F10), boomLength (F11)

fuselageType = "Conventional" or "Nacelle"
  -> HIDE: boomDiameter (F10), boomLength (F11)

landingGearType = "None"
  -> HIDE: all gear sub-parameters (L03-L11)

landingGearType = "Tricycle"
  -> SHOW: main gear params (L03-L07) + nose gear params (L08-L09)
  -> HIDE: tail wheel params (L10-L11)

landingGearType = "Taildragger"
  -> SHOW: main gear params (L03-L07) + tail wheel params (L10-L11)
  -> HIDE: nose gear params (L08-L09)

wingSections > 1
  -> SHOW: multi-panel parameters (W09-W11) for each extra panel

engineCount = 0
  -> HIDE: all propulsion mount parameters (P02-P13)

engineCount > 1
  -> SHOW: multi-engine placement (P12-P13)

propulsionType = "Glider"
  -> HIDE: all motor mount and prop parameters (P02-P16)

autoSection = off
  -> HIDE: sectionOverlap (PR05)

jointType = "Tongue-and-Groove"
  -> HIDE: dowelDiameter (PR12)

servoPocketEnabled = off
  -> HIDE: servo pocket dimensions (PR17-PR19)

sparChannelEnabled = off
  -> HIDE: sparChannelDiameter (W21 -- renumbered)
```

### 13.2 Value Dependencies (Auto-Calculation)

```
wingTipChord  <-->  wingTipRootRatio
  tipChord = rootChord * tipRootRatio
  tipRootRatio = tipChord / rootChord
  (bidirectional: editing either recalculates the other)

vTailDihedral  <-->  vTailAngle
  angle = 180 - 2 * dihedral
  dihedral = (180 - angle) / 2
  (bidirectional)

wingArea = f(span, rootChord, tipChord, sections, panelBreaks)
  (auto-recalculated whenever any planform parameter changes)

aspectRatio = span^2 / wingArea
  (auto-recalculated)

MAC = f(rootChord, taperRatio)
  (auto-recalculated)

tailArm = f(fuselageLength, wingMountPosition, tailPosition)
  (auto-recalculated)

minFeatureThickness = 2 * nozzleDiameter
  (auto-recalculated)

trailingEdgeMinThickness >= 2 * nozzleDiameter
  (clamped if user enters less)

numberOfWingSections = ceil(halfSpan / min(printBedX, printBedY))
  (auto-calculated when autoSection = on; informs the user how many pieces per wing half)
```

### 13.3 Constraint Dependencies (Clamping/Warnings)

```
flapSpanEnd <= aileronSpanStart - 2  (% of half-span, 2% gap)
aileronSpanEnd <= 98  (leave wing tip structure)
elevatorSpanPercent + rudderChordPercent  -- no direct conflict but surfaces must fit
mainGearPosition > cgPosition  (for tricycle, main gear must be behind CG)
mainGearPosition <= cgPosition  (for taildragger, main gear at or ahead of CG)
wallThickness >= 2 * nozzleDiameter  (minimum printable wall)
wingSkinThickness >= 2 * nozzleDiameter  (minimum printable shell)
trailingEdgeMinThickness >= 2 * nozzleDiameter  (printable TE)
sectionOverlap >= 10 when wingSpan > 800  (structural joint minimum)
```

---

## Appendix A: Airfoil Database (MVP Subset)

The following airfoils should be available in the MVP dropdown. Coordinate data (.dat files) are bundled in the Docker image at `/app/airfoils/` and are read-only in cloud deployment.

### Airfoil Storage

- **Local mode (Docker):** Airfoil library at `/app/airfoils/` (built into image). Custom airfoil uploads are stored in Docker volume `/data/airfoils/`.
- **Cloud mode (Google Cloud Run):** Airfoil library at `/app/airfoils/` (built into image). Custom airfoil uploads are returned as a file blob to the browser for IndexedDB storage, avoiding cloud storage overhead.
- **Data format unchanged:** No changes to `.dat` file format or airfoil selection logic.

### Bundled Airfoils

| Airfoil | Category | Max Thickness | Max Camber | Best For | Re Range |
|---------|----------|---------------|------------|----------|----------|
| **Flat-Plate** | Flat | ~3% (rounded LE) | 0% | Micro foamies, indoor | < 50k |
| **NACA-0009** | Symmetric | 9% | 0% | Aerobatic, tail surfaces | 100k--500k |
| **NACA-0012** | Symmetric | 12% | 0% | Aerobatic, all-around symmetric | 100k--500k |
| **NACA-2412** | Light camber | 12% | 2% at 40%c | Sport, general purpose | 100k--500k |
| **NACA-4412** | Medium camber | 12% | 4% at 40%c | Trainer, slow-fly | 50k--300k |
| **NACA-6412** | High camber | 12% | 6% at 40%c | Slow flyer, high-lift | 50k--200k |
| **Clark-Y** | Flat-bottom | 11.7% | 3.5% | Classic trainer, easy build | 100k--500k |
| **Eppler-193** | High camber | 12.3% | 5.7% | Glider, slow-fly | 50k--200k |
| **Eppler-387** | Low-drag | 9.1% | 3.8% | Low-Re glider | 50k--300k |
| **Selig-1223** | Ultra-high-lift | 12.1% | 8.7% | Maximum lift, slow flight | 50k--200k |
| **AG-25** | DLG optimized | 7.5% | 2.1% | DLG/F3K glider | 50k--150k |

### Airfoil Data Format

Each airfoil should be stored as a Selig-format `.dat` file:
```
NACA 2412
1.000000  0.001260
0.950000  0.011780
...
0.000000  0.000000
...
0.950000 -0.008780
1.000000 -0.001260
```

The application should also support importing custom airfoil `.dat` files (Phase 1.0).

---

## Appendix B: Parameter Count Summary

| Component | MVP Params | 1.0 Params | Future Params | Total |
|-----------|-----------|------------|---------------|-------|
| Global | 6 | 4 | 1 | 11 |
| Fuselage | 9 | 3 | 4 | 16 |
| Wings | 9 | 11 | 3 | 23 |
| Tail | 9 | 7 | 0 | 16 |
| Control Surfaces | 0 | 20 | 4 | 24 |
| Propulsion | 2 | 9 | 5 | 16 |
| Landing Gear | 0 | 9 | 2 | 11 |
| 3D Printing / Fab | 10 | 10 | 4 | 24 |
| Derived | 4 | 5 | 4 | 13 |
| **TOTAL** | **49** | **78** | **27** | **154** |

MVP delivers 49 user-configurable parameters -- enough to generate a complete, printable RC plane shape with wing, fuselage, and tail, plus essential 3D printing controls (bed size, sectioning, wall thickness, joint tolerance, export format). The full 1.0 release adds 78 more for detailed control over all surfaces, propulsion, landing gear, spar channels, servo pockets, and hinge provisions. Future phases add 27 parameters for simulation, structural analysis, and database integration.

### Parameter changes from v1.0-draft to v1.1-draft

- `wallThickness` (F14) promoted from 1.0 to **MVP** -- essential for 3D printing.
- `wingSkinThickness` (W20) promoted from Future to **MVP** -- essential for 3D printing.
- New `sparChannelDiameter` (W21) added at 1.0 -- replaces old `ribSpacing` numbering.
- `ribSpacing` renumbered to W22 and moved from Future to **1.0** -- internal ribs are printed as part of hollow wing structure.
- **New Section 9** added: 24 3D Printing / Fabrication parameters (PR01--PR24).
- **8 new validation rules** (V16--V23) for 3D printing constraints.
- CadQuery implementation notes added to every component section.

---

## Appendix C: Mapping to UI Mockup Fields

This appendix explicitly maps every field visible in the three UI mockup screenshots to the parameters defined above.

### Screen 1 -- Default State (No component selected)

**Dimension annotations on viewport:**
| Annotation | Parameter | ID |
|------------|-----------|-----|
| 300.00 (top, horizontal) | `fuselageLength` | F01 |
| 190.00 (right, vertical -- appears to be half-span or a projected dimension) | Related to `wingSpan` | W01 |
| SWEEP: 25° | `wingSweep` | W05 |

**Right panel -- GLOBAL PARAMETERS:**
| UI Field | Parameter | ID |
|----------|-----------|-----|
| FUSELAGE: (DROPDOWN) | `fuselagePreset` | G01 |
| ENGINES: [ ] | `engineCount` | G02 |
| SPAN: [ ] (first) | `wingSpan` | G03/W01 |
| SPAN: [ ] (second) | `tailSpan` | G04 |
| CHORD: [ ] | `wingChord` | G05/W02 |
| TAIL TYPE: (DROP DOWN) | `tailType` | G06 |

**Bottom panel:**
- "SELECT A COMPONENT TO CONFIGURE" -- no component-specific params shown.

### Screen 2 -- Wing Selected (yellow highlight)

**Bottom panel -- WING SELECTED:**
| UI Field | Parameter | ID |
|----------|-----------|-----|
| AIRFOIL: (DROP DOWN) | `wingAirfoil` | W12 |
| SECTIONS: [ ] | `wingSections` | W08 |
| SWEEP: [ ] | `wingSweep` | W05 |
| INCIDENT: [ ] | `wingIncidence` | W06 |
| TIP/ROOT RATIO: [ ] | `wingTipRootRatio` | W04 |

### Screen 3 -- Tail Selected (yellow highlight, V-tail shown)

**Bottom panel -- TAIL SELECTED:**
| UI Field | Parameter | ID |
|----------|-----------|-----|
| TYPE: (V-TAIL) | `tailType` | T01 |
| DIHEDRAL: [ ] | `vTailDihedral` | T14 |
| ANGLE: [ ] | `vTailAngle` | T15 |
| SPAN: [ ] | `vTailSpan` | T16 |
| CHORD: [ ] | `vTailChord` | T17 |
| INCIDENT: [ ] | `vTailIncidence` | T18 |

---

## Appendix D: Key Design Decisions and Rationale

### D1: Why Tip/Root Ratio Instead of Separate Taper Ratio?

The mockup shows "TIP/ROOT RATIO" rather than a standard aerospace "taper ratio" field. This is more intuitive for RC builders: "my tip is 2/3 the size of my root" is easier to grasp than "taper ratio lambda = 0.67." Internally they are the same value. The UI label should match the mockup.

### D2: Why Sweep is Both Global and Component?

Sweep appears in the bottom panel when the wing is selected (Screen 2) but also affects the viewport annotations (Screen 1). It is a COMPONENT parameter that gets reflected in the viewport dimension overlay. It does not need to appear in the Global Parameters panel on the right.

### D3: Why Two Span Fields in Global?

The mockup shows two separate "SPAN" fields in the right panel. Based on the context (wing span and tail span are the two most important sizing parameters), these map to `wingSpan` and `tailSpan`. The labels should be disambiguated in implementation: "WING SPAN" and "TAIL SPAN."

### D4: Default Values Chosen for a ~1m Sport Plane

All default values are tuned for a small electric sport plane with approximately:
- 1000mm wingspan
- 300mm fuselage length
- 180mm root chord
- Clark-Y airfoil
- Conventional tail
- Single tractor motor
- ~300g all-up weight

This matches the scale suggested by the mockup dimension annotations and represents the most common entry point for RC builders using a parametric design tool.

### D5: Control Surfaces Deferred to 1.0

The mockup does not show control surface editing UI. Control surfaces are visual/geometric details that add significant complexity. For MVP, the geometry generator should auto-place reasonable control surfaces (25% chord ailerons on the outer 40% of span, full-span elevator at 35% chord, rudder at 35% chord) without user configuration. In 1.0, these become individually adjustable.

### D6: Validation is Warning-Only

The validation system produces warnings, not hard blocks. RC builders often push unconventional designs deliberately, and the tool should not prevent creativity. Red/yellow warning indicators next to affected parameters, plus a summary panel, are sufficient.

### D7: 3D Printing as Primary Fabrication (v1.1 Addition)

FDM 3D printing is the assumed fabrication method. This drives several design decisions:
- **Wall thickness is MVP-critical:** Every part needs a defined shell thickness to be printable. Default values are chosen as clean multiples of a 0.4mm nozzle.
- **Auto-sectioning is MVP-critical:** RC planes with 1m+ wingspans cannot fit on typical print beds (220x220mm). The system must automatically section parts.
- **Trailing edges must be thickened:** Airfoil trailing edges taper to zero thickness, which is unprintable. CadQuery automatically blunts them to `trailingEdgeMinThickness`.
- **Joints are structural:** Wing sections glued together must withstand flight loads. Tongue-and-groove joints with spar continuity provide adequate strength for PLA/PETG at typical RC wing loads.
- **Material density assumptions:** Weight estimation uses PLA density (1.24 g/cm^3) as default. LW-PLA (lightweight foaming PLA, ~0.6 g/cm^3) is a future option for weight-sensitive builds.

### D8: CadQuery as Geometry Engine (v1.1 Addition)

CadQuery was chosen because:
- **Python-native:** Integrates directly with FastAPI for the local server backend.
- **Parametric by design:** CadQuery models are Python functions that take parameters and return solids. This maps perfectly to the parameter system.
- **OpenCascade kernel:** Provides robust BREP operations (loft, shell, boolean cut/union) needed for airfoil-based geometry.
- **STL/STEP export:** Built-in exporters for both formats.
- **No GUI dependency:** Headless operation on the server; Three.js handles all visualization in the browser.

The key CadQuery operations used per component:
- **Fuselage:** `Workplane.loft()` through cross-section wires, then `.shell()`.
- **Wing:** `Workplane.loft()` between airfoil wire profiles at spanwise stations, `.shell()`, boolean subtract spar channels.
- **Tail:** Same as wing, with rotation for dihedral.
- **Joints:** Boolean union tongue features, boolean subtract groove features.
- **Sectioning:** `Workplane.cut()` with plane solids at section boundaries.
- **Export:** `cq.exporters.export(shape, path, type='STL', tolerance=stlTolerance)`.
