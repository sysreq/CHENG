# Product Requirements Document: Parametric RC Plane Generator

**Document version:** 1.2
**Date:** 2026-02-23
**Status:** Draft
**Revision note:** Updated to reflect Docker containerization and dual-deployment model (local Docker for privacy/free use, Google Cloud Run for zero-install access).

---

## 1. Product Vision

The Parametric RC Plane Generator is a purpose-built design tool that lets radio-controlled aircraft hobbyists go from concept to 3D-printable parts in minutes rather than hours or days. By exposing only the parameters that matter for RC plane design --- wingspan, chord, airfoil selection, tail configuration, fuselage type, sweep, and incidence --- the tool eliminates the steep learning curve of general-purpose CAD software while producing geometry that is structurally sound, aerodynamically plausible, and ready for FDM 3D printing. The tool is built as a single Docker image that supports two deployment modes: **local Docker** for privacy-conscious users who want free, offline operation with full performance, and **Google Cloud Run** for zero-install access via a web URL. A Python backend powered by CadQuery (built on the OpenCascade kernel) generates precise parametric geometry, while a browser-based frontend with Three.js provides real-time 3D preview and interaction. This dual-mode architecture means a beginner can start designing by clicking a link, while a power user can run the same tool on their own machine with `docker run`. The tool exists because the gap between "I want to build a custom RC plane" and "I have printable STL files on my desk" is currently filled by either intimidating professional software or tedious manual drafting, and neither path encourages experimentation. This tool makes the design phase fast, visual, and accessible so that more hobbyists spend their time building and flying rather than wrestling with software.

---

## 2. Target Users and Personas

### 2.1 Beginner Builder --- "Alex"

| Attribute | Detail |
|---|---|
| Background | New to RC aircraft, built one or two kits, wants to try a custom design |
| Goals | Start from a proven template, adjust a few dimensions, get plans that will actually fly |
| Frustrations | Existing CAD tools require hours of tutorials; afraid of designing something unflyable; unclear which parameters matter; installing Python or Docker is intimidating |
| Technical comfort | Comfortable with apps and web tools; no CAD experience; basic understanding of lift and drag from YouTube |
| Key needs | Presets, guardrails, clear defaults, visual feedback that the plane "looks right" |
| Deployment preference | **Cloud (primary).** Alex accesses the tool via a URL with zero installation. No Docker, no Python, no command line --- just a browser. This dramatically lowers the barrier to entry. Designs are saved in the browser via IndexedDB. |

### 2.2 Experienced Hobbyist --- "Jordan"

| Attribute | Detail |
|---|---|
| Background | Builds 3--5 planes per year, flies sport and aerobatic, owns a 3D printer and possibly a foam cutter or laser cutter |
| Goals | Rapidly iterate on designs, compare configurations, export plans ready for fabrication |
| Frustrations | Rebuilding designs from scratch in FreeCAD every time; no quick way to see how a parameter change affects the whole plane; manually splitting models for print bed size |
| Technical comfort | Familiar with airfoil databases, basic aerodynamics, comfortable with numeric inputs and Docker |
| Key needs | Full parameter control, multiple export formats, ability to save and revisit designs, local operation for performance and privacy |
| Deployment preference | **Local Docker.** Jordan runs `docker run` on their own machine for faster CadQuery regeneration, no cold starts, and designs stay on local disk. |

### 2.3 Designer/Experimenter --- "Sam"

| Attribute | Detail |
|---|---|
| Background | Aeronautics student or advanced hobbyist, designs unconventional configurations (canards, flying wings, twin booms) |
| Goals | Explore novel geometries, validate with external analysis tools, push design boundaries |
| Frustrations | OpenVSP is overkill for RC-scale; XFLR5 only analyzes, doesn't generate buildable geometry; nothing ties analysis to fabrication |
| Technical comfort | High; understands Reynolds numbers, stability margins, CG calculations; comfortable with Docker and command-line tools |
| Key needs | Full parameter ranges without artificial limits, data export for XFLR5/OpenVSP interop, precise numeric control |
| Deployment preference | **Local Docker.** Sam needs maximum performance for complex geometry regeneration and wants designs stored locally for version control and integration with external analysis tools. |

### 2.4 Club Organizer/Educator --- "Pat"

| Attribute | Detail |
|---|---|
| Background | Runs an RC club or teaches a STEM class, introduces groups to aircraft design |
| Goals | Provide students with a hands-on design experience; share a base design that the whole class customizes; demonstrate how parameter changes affect geometry |
| Frustrations | No tool is simple enough for a classroom setting; can't easily distribute and collect designs; setup time eats into teaching time; installing software on school computers is blocked by IT |
| Technical comfort | Moderate; can teach concepts but does not want to troubleshoot CAD software or Docker installations |
| Key needs | Shareable design links/files, simple starting points, visual cause-and-effect feedback |
| Deployment preference | **Cloud (primary).** Pat shares a single URL with the entire class. Students open it in their browser and start designing immediately --- no installation, no IT approval, no troubleshooting. Each student's designs are saved in their own browser's IndexedDB. |

---

## 3. Competitive Landscape

| Tool | Strengths | Weaknesses | Our differentiation |
|---|---|---|---|
| **OpenVSP (NASA)** | Full parametric aircraft modeler; serious analysis pipeline | Steep learning curve; not RC-focused; UI designed for aerospace engineers | We are purpose-built for RC scale; simpler parameter set; direct-to-fabrication export |
| **XFLR5** | Excellent airfoil and stability analysis | Analysis only; does not generate buildable geometry | We generate geometry first, with analysis as a future integration |
| **RCadvisor / eCalc** | Quick motor/prop/battery sizing calculators | No geometry, no plans, no visual design | We produce the physical design; these tools complement ours |
| **FreeCAD / Fusion 360** | Full 3D CAD; infinite flexibility | Generic; no RC-specific workflows; hours to model a simple wing | We encode RC-specific knowledge so the user skips general CAD entirely |
| **Pencil, paper, and foam** | Zero software overhead; tactile | Error-prone; no parametric iteration; no digital record | We preserve the simplicity while adding precision and iteration speed |

### Unique Value Proposition

**"Idea to printable STL in under five minutes."** No other tool combines RC-specific parametric design, real-time 3D preview, and direct-to-printer STL export in a single, focused workflow. Powered by CadQuery on the backend, the geometry is produced by a real CAD kernel (OpenCascade), ensuring watertight, manifold meshes that slice cleanly in any FDM slicer. With dual deployment --- local Docker or cloud URL --- the tool is accessible to everyone from first-time hobbyists to seasoned builders. We are not a general CAD tool and we are not an analysis tool --- we are the fastest path from design intent to physical printed parts for RC aircraft.

---

## 3.1 Architecture Overview

The tool is a **containerized web application** deployed in two modes from the same Docker image:

```
                    +---------------------------------------------+
                    |           Docker Image                      |
                    |  +---------------------------------------+  |
                    |  | FastAPI + CadQuery + OpenCascade       |  |
                    |  | Static frontend (Three.js)             |  |
                    |  +---------------------------------------+  |
                    +---------------------------------------------+
                           |                          |
              Local Docker mode              Google Cloud Run mode
              +-----------------+            +----------------------+
              | docker run      |            | Cloud Run service    |
              | localhost:8080  |            | https://rc.app.run   |
              | Volume mounts   |            | Scale-to-zero        |
              | Full offline    |            | IndexedDB storage    |
              | No cold start   |            | Zero install         |
              +-----------------+            +----------------------+

Browser (Frontend)                    Python Server (Backend, in container)
+---------------------------+         +-----------------------------+
| Three.js 3D viewport      |  HTTP/  | FastAPI                     |
| Parameter panels (UI)     | <=====> | CadQuery geometry engine    |
| Dark theme, annotations   |  WS     | OpenCascade kernel          |
| Component selection       |         | STL/STEP export             |
| IndexedDB (cloud mode)    |         | Volume storage (local mode) |
+---------------------------+         +-----------------------------+

User adjusts params in UI
  -> params sent as JSON to Python backend
  -> CadQuery regenerates parametric geometry
  -> tessellated mesh sent back to browser
  -> Three.js renders 3D preview
  -> on export: CadQuery produces final STL/STEP files
```

**Why this architecture:**
- **Single Docker image** for both local and cloud deployment. Build once, run anywhere. The same image that a user runs with `docker run -p 8080:8080` is the same image deployed to Cloud Run.
- **CadQuery + OpenCascade** provides a real CAD kernel for precise, watertight geometry --- critical for 3D printing. Browser-only geometry libraries cannot match this fidelity.
- **Local Docker mode** means no cloud dependency, no latency, no hosting costs, and full offline operation. Designs are saved to a Docker volume on the user's machine.
- **Cloud Run mode** means zero installation for beginners and classrooms. Users access the tool via a URL; designs are saved in the browser's IndexedDB. Scale-to-zero keeps hosting costs near zero during idle periods.
- **Browser frontend** means cross-platform UI with no native toolkit dependency. Three.js provides hardware-accelerated 3D rendering.
- **Python ecosystem** gives access to scientific computing libraries (NumPy for airfoil interpolation, SciPy for spline fitting) and Docker packaging eliminates dependency headaches.

---

## 4. User Stories

### 4.1 Starting a New Design

| ID | Story | Priority |
|---|---|---|
| S-01 | As a **Beginner Builder**, I want to start from a preset template (e.g., "Sport Trainer 1200mm") so that I have a known-good starting point. | Must |
| S-02 | As an **Experienced Hobbyist**, I want to start with a blank design and set all parameters myself so that I have full creative control. | Must |
| S-03 | As an **Educator**, I want to load a shared design file from a colleague so that my students all begin from the same baseline. | Should |
| S-04 | As a **Designer/Experimenter**, I want to duplicate an existing design so that I can create a variant without losing the original. | Should |

### 4.2 Accessing the Tool

| ID | Story | Priority |
|---|---|---|
| A-01 | As a **Beginner Builder**, I want to access the tool via a web URL so that I don't need to install Docker or Python. | Should |
| A-02 | As an **Educator**, I want to share a URL with students so they can start designing without any setup. | Should |
| A-03 | As an **Experienced Hobbyist**, I want to run the tool locally via Docker so that my designs stay private and I get better performance. | Must |
| A-04 | As any user, I want my designs saved in my browser so that I can return to them even in cloud mode. | Should |

### 4.3 Configuring Global Parameters

| ID | Story | Priority |
|---|---|---|
| G-01 | As any user, I want to select a fuselage type from a dropdown so that the overall body shape is set without manual modeling. | Must |
| G-02 | As any user, I want to set the number of engines (0--4) so that engine mount geometry is generated automatically. | Must |
| G-03 | As any user, I want to set overall wingspan and chord so that the wing planform scales accordingly. | Must |
| G-04 | As any user, I want to select a tail type (conventional, T-tail, V-tail, cruciform) from a dropdown so that the empennage geometry updates instantly. | Must |
| G-05 | As any user, I want to see dimension annotations on the viewport (span, length, sweep angle) update in real time as I change parameters so that I always know the current measurements. | Must |

### 4.4 Refining Individual Components

#### Wing

| ID | Story | Priority |
|---|---|---|
| W-01 | As any user, I want to click the wing in the viewport to select it and reveal wing-specific parameters so that I can fine-tune the wing independently. | Must |
| W-02 | As an **Experienced Hobbyist**, I want to choose an airfoil from a searchable dropdown (e.g., Clark Y, NACA 2412, MH-60) so that I can match the airfoil to my performance goals. | Must |
| W-03 | As a **Designer/Experimenter**, I want to set the number of wing sections (panels) so that I can create tapered or polyhedral wings. | Should |
| W-04 | As any user, I want to set wing sweep angle so that I can design swept-wing aircraft. | Must |
| W-05 | As an **Experienced Hobbyist**, I want to set wing incidence angle so that I can optimize cruise attitude. | Should |
| W-06 | As any user, I want to set the tip-to-root chord ratio so that I can control wing taper. | Must |

#### Tail / Empennage

| ID | Story | Priority |
|---|---|---|
| T-01 | As any user, I want to click the tail in the viewport to select it and reveal tail-specific parameters so that I can configure the empennage independently. | Must |
| T-02 | As any user, I want to set tail dihedral angle so that I can adjust lateral stability. | Must |
| T-03 | As any user, I want to set tail span and chord independently from the wing so that I can size the tail surfaces correctly. | Must |
| T-04 | As an **Experienced Hobbyist**, I want to set tail incidence angle so that I can trim the aircraft for level flight. | Should |
| T-05 | As a **Designer/Experimenter**, I want to set V-tail dihedral angle precisely so that I can calculate the correct control mixing. | Should |

#### Fuselage

| ID | Story | Priority |
|---|---|---|
| F-01 | As any user, I want the fuselage length and cross-section to adjust automatically when I change wingspan so that proportions remain plausible. | Must |
| F-02 | As an **Experienced Hobbyist**, I want to override fuselage dimensions manually so that I can accommodate specific electronics or battery packs. | Should |

### 4.5 Validating the Design

| ID | Story | Priority |
|---|---|---|
| V-01 | As a **Beginner Builder**, I want to see a warning if my wing loading is outside a recommended range so that I avoid building something that won't fly well. | Should |
| V-02 | As any user, I want the viewport to update in real time as I change any parameter so that I can visually verify the design at every step. | Must |
| V-03 | As a **Designer/Experimenter**, I want to see computed values (wing area, aspect ratio, tail volume coefficient) displayed alongside my inputs so that I can validate the design numerically. | Should |
| V-04 | As a **Beginner Builder**, I want out-of-range parameter values to be flagged with a visual indicator so that I know when I have entered something unusual. | Should |

### 4.6 Exporting and 3D Printing

| ID | Story | Priority |
|---|---|---|
| E-01 | As any user, I want to export the 3D model as an STL file so that I can 3D-print the aircraft components directly. | Must |
| E-02 | As any user, I want the tool to automatically section large components (wings longer than the print bed) into printable segments with alignment features (dowel holes, keyed joints) so that I can print and assemble them without manual splitting. | Must |
| E-03 | As an **Experienced Hobbyist**, I want to configure my print bed dimensions so that the tool sections parts to fit my specific printer. | Should |
| E-04 | As any user, I want the generated geometry to have appropriate wall thicknesses for FDM printing (minimum 1.2mm walls) so that printed parts are structurally sound. | Must |
| E-05 | As an **Experienced Hobbyist**, I want to control infill-friendly internal structures (spar channels, lightening holes) in the generated geometry so that I can balance weight and strength. | Should |
| E-06 | As an **Experienced Hobbyist**, I want to export flat cutting templates as DXF or SVG so that I can use a laser cutter or CNC foam cutter as an alternative fabrication method. | Could |
| E-07 | As a **Designer/Experimenter**, I want to export the geometry in a format compatible with XFLR5 or OpenVSP so that I can run external analysis. | Could |
| E-08 | As any user, I want to export a dimensioned PDF plan sheet so that I can reference overall dimensions during assembly. | Could |
| E-09 | As any user, I want each printable section exported as a separate STL file with a clear naming convention so that I can organize my print queue easily. | Should |
| E-10 | As a **Beginner Builder**, I want the export to include a recommended print orientation for each part so that I get the best strength and surface quality. | Should |

### 4.7 Managing Designs

| ID | Story | Priority |
|---|---|---|
| M-01 | As any user, I want to save my current design to a local file so that I can return to it later. | Must |
| M-02 | As any user, I want to load a previously saved design file so that I can continue working. | Must |
| M-03 | As an **Educator**, I want to share a design as a compact file or link so that students can open it directly. | Could |
| M-04 | As an **Experienced Hobbyist**, I want to keep a history of parameter changes within a session so that I can undo/redo adjustments. | Should |

---

## 5. Feature Phasing

### Phase 1 --- MVP: "First Printable Plane"

**Goal:** A user can generate a basic, plausible RC plane shape from parameters, preview it in 3D, and export print-ready STL files. The tool runs locally via Docker.

**Guiding principle:** What is the smallest thing that provides real value to someone who wants to 3D-print a custom RC plane this weekend?

**Architecture:** Containerized web application. User runs the tool locally with `docker run -p 8080:8080 rcplane-generator`. Browser opens to `localhost:8080`. CadQuery generates geometry on the backend inside the container; Three.js renders the 3D preview in the browser. Designs are saved to a Docker volume.

#### Included

| Feature | Acceptance criteria |
|---|---|
| Docker containerized deployment | User runs `docker run -p 8080:8080 rcplane-generator` and the tool is available at `localhost:8080`; no Python installation required; works on Windows, macOS, and Linux with Docker Desktop |
| 3D viewport with Three.js rendering | User can orbit, pan, and zoom the aircraft model; geometry updates when parameters change; selected components highlighted in yellow |
| CadQuery backend geometry generation | Python/FastAPI server accepts parameter JSON via HTTP, generates geometry with CadQuery, returns mesh data (vertices/faces) for Three.js preview and STL for export |
| Global parameter panel | Fuselage type dropdown with at least 3 options (pod, stick, conventional); engine count (1--2); wingspan input; chord input; tail type dropdown with at least 3 options (conventional, T-tail, V-tail) |
| Wing selection and parameters | Clicking wing highlights it in yellow and reveals: airfoil dropdown (minimum 10 common RC airfoils), sweep angle, tip/root chord ratio |
| Tail selection and parameters | Clicking tail highlights it in yellow and reveals: dihedral, span, chord, incidence |
| Dimension annotations | Span, length, and sweep angle displayed as overlay annotations on the viewport; values update with parameter changes |
| STL export (primary format) | User clicks export button; CadQuery generates watertight STL on the backend; file downloads to the user's machine; file opens correctly in PrusaSlicer and Cura |
| 3D-print-aware geometry | Generated parts have minimum 1.2mm wall thickness; wing sections that exceed a configurable print bed size (default 220x220mm) are automatically sectioned with alignment joints |
| Save/Load design file | User can save current parameters to a JSON file and reload them to restore the exact design state; in local Docker mode, designs are also persisted to the Docker volume |
| 3 built-in presets | "Sport Trainer 1200mm", "Aerobatic 900mm", "Slow Flyer 1500mm" presets load sensible defaults for all parameters |

#### Excluded from MVP

- Cloud Run deployment
- Browser-based IndexedDB storage
- PDF/DXF/SVG export
- Design validation or warnings
- Community features
- Computed aerodynamic values
- Fuselage dimension overrides
- Multi-section wings (multiple dihedral breaks)
- Undo/redo
- Internal structure customization (spar channels, lightening holes)
- Print orientation recommendations

---

### Phase 2 --- 1.0 Release: "Full Design Studio"

**Goal:** A complete, polished tool for designing, validating, and 3D-printing RC planes with confidence. Cloud Run deployment makes the tool accessible to anyone with a browser.

#### Included (in addition to MVP)

| Feature | Acceptance criteria |
|---|---|
| Google Cloud Run deployment | The same Docker image deploys to Cloud Run; tool is accessible via a public URL (e.g., `https://rcplane.example.run`); scales to zero when idle; cold start completes within 15 seconds |
| Browser IndexedDB storage (cloud mode) | In cloud mode, designs are saved to the browser's IndexedDB; user can list, load, and delete saved designs; storage limit clearly communicated to user |
| Shareable design URLs | User can generate a URL that encodes their design parameters; recipient opens the URL and sees the design loaded; works for both cloud and local deployments |
| Multi-section wings | User can define 2--5 wing sections (panels) with independent dihedral, chord, and sweep per section; CadQuery generates each section as a separate printable body with alignment joints |
| Fuselage dimension overrides | User can manually set fuselage length, width, and height independent of auto-scaling |
| Configurable print bed size | User specifies printer bed dimensions (X, Y, Z); sectioning algorithm respects these constraints; default 220x220x250mm |
| Internal structure options | User can toggle spar channels, lightening holes, and servo mount cutouts; CadQuery generates these as boolean operations on the solid geometry |
| Print orientation recommendations | Each exported STL section includes a recommended print orientation note in the filename or companion text file |
| Per-section STL export | Each printable segment exports as a named STL file (e.g., `wing_left_section_1.stl`, `fuselage_front.stl`); all files packaged as a ZIP download |
| STEP export | CadQuery exports native STEP files for users who want to modify geometry in FreeCAD or Fusion 360 |
| DXF/SVG flat-pattern export | Exported flat patterns for alternative fabrication (laser cutting, foam cutting) |
| Design validation warnings | Wing loading, aspect ratio, tail volume coefficient, and CG range are computed; out-of-range values produce yellow warnings; values outside plausible flight envelope produce red warnings |
| Computed aerodynamic readouts | Wing area, wetted area, aspect ratio, tail volume coefficient, and estimated CG range displayed in a collapsible info panel |
| Expanded airfoil library | Minimum 50 airfoils with thumbnail profile previews and basic characteristic tags (flat-bottom, semi-symmetrical, symmetrical, high-lift, low-drag) |
| Expanded fuselage types | At least 6 fuselage options including pod-and-boom, twin-boom, nacelle, flying-wing (no fuselage) |
| Expanded tail types | Conventional, T-tail, V-tail, cruciform, H-tail, flying-wing (elevon, no tail) |
| Undo/redo | Full undo/redo stack for all parameter changes within a session (minimum 50 levels) |
| 10+ presets | Presets covering common RC categories: trainer, sport, aerobatic, glider, flying wing, twin-engine, scale-like |
| Keyboard shortcuts | Common actions (undo, redo, save, export, select next component) have keyboard shortcuts |
| WebSocket live preview | Parameter changes stream to the backend via WebSocket; CadQuery regenerates incrementally; Three.js mesh updates without full page reload; target under 500ms round-trip |

---

### Phase 3 --- Future Release: "Community and Intelligence"

**Goal:** A smart, connected tool that helps users make better design decisions and share knowledge.

| Feature | Description |
|---|---|
| User accounts and authentication | Optional user accounts for cloud mode; designs synced across devices; OAuth login (Google, GitHub) |
| Google Cloud Storage (GCS) persistence | Cloud users can opt into server-side storage via GCS; designs persist beyond browser storage limits and are accessible from any device |
| Published design gallery | Cloud-hosted gallery where users can publish, browse, and fork designs with tags, descriptions, and ratings; local-only operation remains fully functional without it |
| XFLR5/OpenVSP export | Export geometry in formats directly importable by XFLR5 and OpenVSP for stability and performance analysis |
| Performance estimation | Built-in estimation of stall speed, cruise speed, rate of climb, and glide ratio based on weight input and selected motor/prop |
| Motor/prop/servo database | Searchable database of common RC components with weight and thrust data; auto-populate weight budget |
| CG calculator | Interactive CG marker on the viewport; user drags battery/receiver positions; tool shows CG relative to aerodynamic center |
| Shareable design files | Export a self-contained `.rcplane` file (JSON parameters + metadata) that another user can load; optionally a URL scheme for web-hosted galleries |
| Flight envelope visualization | Chart showing speed vs. load factor with structural and aerodynamic limits marked |
| Print material and weight estimator | User selects filament type (PLA, PETG, LW-PLA, ABS) and infill percentage per component; tool estimates total print weight, print time, and filament usage |
| Build/assembly instructions generator | Auto-generated step-by-step guide showing how to assemble printed sections, insert spars, and install electronics |
| Version history | Full design history with named checkpoints and diff visualization between versions |
| Standalone executable packaging | PyInstaller or Electron wrapper that bundles Python + CadQuery + frontend into a single installable application; no Docker installation required by end user |

---

## 6. Feature Priority Matrix (MoSCoW for 1.0 Release)

### Must Have

- Docker containerized deployment (`docker run` for local use)
- CadQuery/Python backend with FastAPI serving geometry generation
- Three.js 3D viewport with orbit/pan/zoom and component selection
- Global parameter panel (fuselage type, engines, wingspan, chord, tail type)
- Wing component selection and parameters (airfoil, sweep, taper ratio)
- Tail component selection and parameters (type, dihedral, span, chord, incidence)
- STL export via CadQuery (watertight, manifold meshes)
- 3D-print-aware geometry (minimum wall thickness, automatic part sectioning for print bed)
- Per-section STL export with clear naming
- Save/Load design files (JSON)
- Built-in presets (minimum 3)
- Real-time visual feedback on parameter changes

### Should Have

- Google Cloud Run deployment (same Docker image, public URL access)
- Browser IndexedDB storage for cloud mode
- Shareable design URLs (parameter encoding)
- Configurable print bed dimensions
- Internal structure options (spar channels, lightening holes, servo cutouts)
- Print orientation recommendations per part
- Multi-section wing panels
- WebSocket live preview (incremental CadQuery regeneration)
- Design validation warnings (wing loading, aspect ratio, tail volume)
- Computed aerodynamic readouts
- Expanded airfoil library (50+)
- Undo/redo
- Wing incidence angle
- Tail incidence angle
- Fuselage dimension overrides
- STEP export for downstream CAD editing
- ZIP packaging of all STL sections

### Could Have

- DXF/SVG flat-pattern export
- XFLR5/OpenVSP interop export
- Keyboard shortcuts
- Expanded fuselage and tail types
- Design duplication
- Airfoil profile thumbnail previews
- PDF dimensioned plan sheet

### Won't Have (in 1.0)

- Built-in aerodynamic simulation or CFD
- Motor/prop/servo database
- User accounts and authentication
- Google Cloud Storage (GCS) persistence
- Community gallery
- Flight envelope visualization
- Material/weight estimation
- Build instructions generator
- Version history with diffs
- Real-time multiplayer editing

---

## 7. Acceptance Criteria for Major Features

### 7.1 Real-Time 3D Viewport

| Criterion | Measurement |
|---|---|
| Three.js renders the CadQuery-generated mesh correctly | Rendered geometry in the browser matches the CadQuery solid to visual inspection; no missing faces, inverted normals, or z-fighting artifacts |
| The aircraft model reflects all current parameters | Changing any single parameter and verifying the visual update matches expected geometry |
| Dimension annotations are accurate | Annotations match parameter values to within 0.1mm |
| Update round-trip is acceptable | Parameter change in browser, HTTP/WebSocket to backend, CadQuery regeneration, mesh transfer back, Three.js render completes within 2 seconds for MVP (target 500ms for Phase 2 with WebSocket) |
| Selected components are visually distinguished | Selected component is highlighted in yellow; non-selected components remain in default color |
| Orbit, pan, zoom work smoothly | Camera controls respond at 60fps on a 2020-era integrated GPU with a typical aircraft model |

### 7.2 Global Parameter Panel

| Criterion | Measurement |
|---|---|
| Fuselage dropdown contains at least 3 options | Count options in dropdown |
| Changing fuselage type updates the silhouette immediately | Visual confirmation within 200ms |
| Engine count accepts integers 0--4 | Input validation rejects non-integer and out-of-range values |
| Wingspan and chord accept numeric input in millimeters | Input fields accept values from 200mm to 5000mm with 1mm resolution |
| Tail type dropdown contains at least 3 options | Count options in dropdown |

### 7.3 Component Selection and Configuration

| Criterion | Measurement |
|---|---|
| Clicking a component in the viewport selects it | Click target area covers the visual footprint of the component; click event triggers selection state |
| Selected component panel appears with correct parameters | Panel contents match the selected component type (wing parameters for wing, tail parameters for tail) |
| Parameter changes in the component panel update the viewport | Each parameter change is reflected visually within 200ms |
| Deselecting a component hides the component panel | Clicking empty viewport space or another component clears the previous selection |

### 7.4 STL Export and 3D Printability

| Criterion | Measurement |
|---|---|
| CadQuery produces watertight STL | File passes STL validation (no degenerate triangles, manifold mesh, correct normals); zero errors when imported into PrusaSlicer, Cura, and Bambu Studio |
| Exported geometry matches viewport | Key dimensions (span, chord, fuselage length) in the STL match parameter values to within 0.5mm |
| Minimum wall thickness is enforced | No wall in the generated geometry is thinner than 1.2mm (2 perimeters at 0.4mm nozzle + tolerance) |
| Large parts are automatically sectioned | Any component exceeding the configured print bed dimensions is split into sections with alignment features (dowel holes or keyed joints); sections fit within bed dimensions with 5mm margin |
| Each section is a separate STL | Export produces one STL per printable section; filenames follow the pattern `{component}_{side}_{section_number}.stl` |
| Alignment features are functional | Keyed joints or dowel holes on mating faces are positioned consistently; a 3mm dowel inserted into opposing holes aligns parts to within 0.3mm |
| Export completes in reasonable time | CadQuery generation + STL tessellation completes within 15 seconds for any valid design |
| File opens in common slicers | Tested in PrusaSlicer, Cura, and Bambu Studio without import errors or non-manifold warnings |

### 7.5 Docker Deployment (Local)

| Criterion | Measurement |
|---|---|
| Single-command launch | `docker run -p 8080:8080 rcplane-generator` starts the application and serves the UI at `localhost:8080` |
| Volume persistence | `docker run -v designs:/data -p 8080:8080 rcplane-generator` persists saved designs across container restarts |
| Cross-platform | Image runs on Docker Desktop for Windows, macOS (Intel + ARM), and Linux without modification |
| Image size | Docker image is under 2GB (CadQuery + OpenCascade + Python + frontend assets) |
| Startup time | Container starts and serves first request within 10 seconds on a modern machine |

### 7.6 Cloud Run Deployment

| Criterion | Measurement |
|---|---|
| Same image deploys to Cloud Run | The locally tested Docker image deploys to Cloud Run without modification via `gcloud run deploy` |
| Cold start is acceptable | First request after scale-to-zero completes within 15 seconds; loading animation is displayed during cold start |
| Concurrent users | Cloud Run instance handles at least 10 concurrent users without degradation (2Gi memory limit) |
| IndexedDB storage works | Designs saved in browser IndexedDB persist across sessions; user can list, load, and delete saved designs |
| HTTPS and custom domain | Cloud Run serves over HTTPS; optional custom domain mapping |

### 7.7 Save/Load

| Criterion | Measurement |
|---|---|
| Save produces a file that fully encodes the design | Loading a saved file restores all parameters to their saved values |
| File format is human-readable JSON | File can be opened in a text editor and parameters are identifiable |
| Loading a file from a different version of the tool produces a clear error or migrates gracefully | Version mismatch is handled without silent data loss |
| IndexedDB storage works in cloud mode | Designs saved in cloud mode persist in the browser's IndexedDB; user can return to the same URL and find their designs |

### 7.8 Design Validation (Phase 2)

| Criterion | Measurement |
|---|---|
| Wing loading is computed and displayed | Displayed value matches manual calculation (wing area x weight) to within 1% |
| Out-of-range wing loading triggers a yellow warning | Warning appears when wing loading exceeds 50 g/dm^2 for a trainer preset |
| Dangerous wing loading triggers a red warning | Red warning appears when wing loading exceeds 100 g/dm^2 |
| Tail volume coefficient is computed | Displayed value matches manual calculation to within 1% |
| Warnings do not block the user | User can still export and save despite active warnings |

---

## 8. Success Metrics

### 8.1 Adoption Metrics

| KPI | Target (6 months post-1.0) |
|---|---|
| Monthly active users (total) | 1,500 |
| Monthly active users (cloud) | 1,000 |
| Monthly active users (local Docker) | 500 |
| Cloud vs. local usage ratio | 60/40 cloud/local (cloud lowers barrier; power users prefer local) |
| Designs created per month | 7,500 |
| Designs exported per month | 3,000 |
| Preset-to-custom ratio | At least 40% of designs are custom (not unmodified presets) |

### 8.2 Engagement Metrics

| KPI | Target |
|---|---|
| Average time from launch to first export | Under 10 minutes |
| Session return rate (users who come back within 7 days) | 30% |
| Average designs saved per user per month | 3 |
| Parameter changes per design session | At least 8 (indicates active exploration) |

### 8.3 Quality Metrics

| KPI | Target |
|---|---|
| Export success rate (export completes without error) | 99.5% |
| STL validation pass rate | 99% |
| User-reported "unflyable design" complaints | Fewer than 5% of forum/support threads |
| Application crash rate | Fewer than 0.1% of sessions |

### 8.4 Cloud-Specific Metrics

| KPI | Target |
|---|---|
| Cold start abandonment rate | Under 10% (users who leave during cold start before the app loads) |
| Cold start p95 latency | Under 15 seconds |
| Cloud Run monthly cost (at target usage) | Under $50/month with scale-to-zero |
| IndexedDB storage utilization | Average user stores fewer than 10MB of designs in browser |
| Cloud-to-local conversion rate | 5% of cloud users eventually install Docker for local use |

### 8.5 Community Metrics (Phase 3)

| KPI | Target |
|---|---|
| Designs shared publicly | 500 per month |
| Shared designs opened by others | 2,000 per month |
| User-contributed presets | 50 within first 3 months of community launch |

---

## 9. Constraints and Assumptions

### 9.1 Technical Constraints

- **Docker containerization.** The tool is packaged as a single Docker image containing the Python backend (FastAPI + CadQuery + OpenCascade), static frontend assets (Three.js), and all dependencies. This eliminates "works on my machine" installation issues and enables deployment to both local Docker and Cloud Run from the same artifact.
- **Dual deployment model.** The same Docker image runs locally (`docker run -p 8080:8080`) or on Google Cloud Run. The application detects its environment and adjusts storage strategy accordingly (Docker volume for local, IndexedDB hints for cloud).
- **CadQuery as the geometry engine.** All parametric modeling, boolean operations, filleting, and STL/STEP export are performed by CadQuery. The frontend never generates geometry --- it only renders meshes received from the backend. This ensures export fidelity (the STL you download is exactly what CadQuery computed, not a re-tessellation of the preview mesh).
- **Cloud Run constraints.** Cloud Run instances are limited to 2Gi memory and have a cold start latency of 5--15 seconds after scale-to-zero. WebSocket connections on Cloud Run have a maximum timeout of 3600 seconds (1 hour). These constraints are acceptable for the use case but must be considered in architecture decisions.
- **3D printing (FDM) as primary fabrication target.** Generated geometry must be printable on consumer FDM printers. This means: watertight manifold solids, minimum 1.2mm wall thickness, automatic sectioning for print bed size, and alignment features at section joints. Other fabrication methods (laser cutting, foam cutting) are supported as secondary export formats.
- **Parametric, not freeform.** The tool generates geometry from parameters. Users cannot drag vertices or sculpt surfaces. This is a deliberate constraint that keeps the tool fast and foolproof.
- **RC scale only.** The tool is designed for aircraft with wingspans between 200mm and 5000mm. Parameters, defaults, and validation ranges assume RC-scale Reynolds numbers and structural loads. It is not intended for full-scale aircraft design.
- **No built-in physics simulation.** The tool does not perform CFD, FEA, or flight dynamics simulation. Validation is limited to rule-of-thumb checks (wing loading, aspect ratio, tail volume). Users who need simulation export to external tools.

### 9.2 Scope Boundaries --- What This Tool Is NOT

- **Not a CAD tool.** Users cannot draw arbitrary shapes, create assemblies, or define mechanical constraints. CadQuery is used internally but users never interact with it directly.
- **Not a slicer.** The tool produces STL files, not G-code. Users import the STL into their preferred slicer (PrusaSlicer, Cura, Bambu Studio, etc.) to configure print settings, supports, and infill.
- **Not a flight simulator.** The tool does not simulate flight dynamics or control response.
- **Not an electronics configurator.** Motor, ESC, servo, and battery selection is out of scope for MVP and 1.0. It enters scope in Phase 3 as a database lookup, not as a design feature.
- **Not a build guide.** The tool produces printable parts, not step-by-step assembly instructions (until Phase 3).
- **Not a materials database.** Material selection and weight estimation are Phase 3 features.

### 9.3 Assumptions

- Users understand basic RC aircraft concepts (wing, fuselage, tail, wingspan, chord) even if they cannot define them precisely.
- Users have access to an FDM 3D printer and basic slicer software (PrusaSlicer, Cura, or equivalent). The tool produces STL files, not G-code --- the user handles slicing and printing.
- **Local users** have Docker Desktop installed (Windows, macOS) or Docker Engine (Linux). Docker is the only prerequisite for local use --- no Python installation is required.
- **Cloud users** need only a modern web browser. No Docker, no Python, no installation of any kind. The cloud deployment is fully functional for design and export; designs are persisted in the browser's IndexedDB.
- Cloud mode is **optional**. The tool is fully functional when run locally via Docker. Cloud Run deployment is a convenience for users who cannot or prefer not to install Docker.
- Users have a modern web browser (Chrome, Firefox, Edge, Safari) on a desktop OS (Windows 10+, macOS 11+, Ubuntu 20.04+). The tool does not target mobile devices in Phase 1 or 2.
- CadQuery and its OpenCascade bindings are installed inside the Docker image and do not need to be installed by the user.
- Airfoil coordinate data (Selig format .dat files) is freely available and can be bundled or fetched from public databases (UIUC Airfoil Database).
- Users are comfortable with millimeter units. Imperial unit support is a Phase 2 "Could Have."
- Typical print bed size is 220x220x250mm (Prusa MK3/MK4 class). The default sectioning parameters assume this size but are configurable.
- Browser IndexedDB storage is available and sufficient (typically ~50MB per origin) for storing design JSON files in cloud mode. Power users who exceed this limit are directed to local Docker mode.

---

## 10. Risks and Mitigations

### 10.1 Users Design Unflyable Aircraft

| Risk level | High |
|---|---|
| Description | The parametric freedom allows users to create geometries that are aerodynamically unsound, structurally weak, or impossible to build. If users build and crash these designs, they will blame the tool. |
| Mitigation | Phase 1: Include sensible parameter ranges with soft limits. Phase 2: Add validation warnings based on established RC design rules of thumb. Clearly communicate that the tool is a geometry generator, not an engineering certification. Include a disclaimer on export. |

### 10.2 Geometry Generation Produces Invalid Meshes

| Risk level | Medium |
|---|---|
| Description | Certain parameter combinations (extreme taper, high sweep with short chord, zero-length sections) may produce self-intersecting or degenerate geometry that fails in slicers or cutters. |
| Mitigation | Implement mesh validation before export. Constrain parameter combinations that are known to produce degenerate geometry. Test export with automated fuzzing across the parameter space. |

### 10.3 Scope Creep Toward General CAD

| Risk level | Medium |
|---|---|
| Description | User feedback will inevitably request freeform editing, custom cross-sections, mechanical assemblies, and other features that push the tool toward becoming a general CAD application. |
| Mitigation | Maintain a strict product boundary: parametric RC planes only. Direct users to FreeCAD/Fusion 360 for needs outside this scope. Every feature request must pass the test: "Does this help someone go from idea to buildable RC plane plans faster?" |

### 10.4 Airfoil Data Licensing or Accuracy

| Risk level | Low |
|---|---|
| Description | Airfoil coordinate data sourced from public databases may have accuracy issues or unclear licensing for redistribution. |
| Mitigation | Use the UIUC Airfoil Database (public domain). Validate coordinates against known references. Include provenance metadata for each airfoil. Allow users to import custom airfoil .dat files as an escape hatch. |

### 10.5 CadQuery Regeneration Latency

| Risk level | High |
|---|---|
| Description | CadQuery geometry generation involves the full OpenCascade kernel. Complex models with boolean operations (spar channels, lightening holes, sectioning cuts) may take several seconds to regenerate, breaking the real-time feedback loop. |
| Mitigation | MVP: Accept up to 2-second round-trip; show a loading indicator during regeneration. Phase 2: Implement incremental regeneration (only recompute the changed component). Use a lightweight preview mesh for interactive feedback while the full CadQuery solid builds in the background. Cache unchanged components. Profile CadQuery operations to identify bottlenecks. Consider pre-generating meshes for common parameter ranges. |

### 10.6 Cloud Run Cold Start Latency

| Risk level | High |
|---|---|
| Description | Cloud Run instances scale to zero when idle. The first request after an idle period triggers a cold start that takes 5--15 seconds as the container image is loaded and CadQuery/OpenCascade are initialized. This delay may frustrate first-time users who expect instant page load, causing them to abandon the tool before it finishes loading. |
| Mitigation | Configure `min-instances=1` in production to keep one instance warm (adds ~$10--20/month cost). For cost-sensitive deployments, implement a loading animation with a progress indicator and explanatory text ("Initializing design engine...") so users know the tool is loading, not broken. Optimize Docker image layers so CadQuery initialization is as fast as possible. Monitor cold start abandonment rate as a key metric. |

### 10.7 Cloud Run Costs Scale with Usage

| Risk level | Medium |
|---|---|
| Description | CadQuery geometry generation is CPU-intensive. If the cloud deployment becomes popular, Cloud Run costs could grow significantly with the number of concurrent users and regeneration requests. |
| Mitigation | Configure scale-to-zero to avoid costs during idle periods. Set a maximum instance count to cap costs. Implement request throttling and debouncing on the frontend (wait until user stops adjusting a slider before sending a regeneration request). Provide self-hosting instructions so organizations with heavy usage can run their own instance. Monitor per-user cost and set usage alerts. |

### 10.8 Browser Storage Limits in Cloud Mode

| Risk level | Low |
|---|---|
| Description | Browser IndexedDB storage is typically limited to ~50MB per origin. Power users who create many complex designs in cloud mode may hit this limit, resulting in failed saves or lost work. |
| Mitigation | Display storage usage in the UI. Warn users when approaching the limit. Provide a one-click export of all designs as a JSON file for backup. Encourage power users to switch to local Docker mode for unlimited storage. Phase 3: Offer server-side GCS storage for authenticated cloud users. |

### 10.9 CadQuery Installation and Platform Compatibility (Docker Eliminates)

| Risk level | Low (reduced from Medium) |
|---|---|
| Description | CadQuery depends on the OpenCascade kernel via cadquery-ocp wheels. Previously, these binary wheels could fail to install on certain Python versions or platforms. |
| Mitigation | Docker containerization eliminates this risk entirely for end users. CadQuery and all its dependencies are pre-installed in the Docker image and tested in CI. The user never runs `pip install`. The only prerequisite for local use is Docker Desktop (Windows, macOS) or Docker Engine (Linux). |

### 10.10 3D-Printed Parts Are Structurally Inadequate

| Risk level | Medium |
|---|---|
| Description | FDM-printed parts have anisotropic strength (weak in the Z-axis layer direction). Wings and tail surfaces experience bending and torsion loads that may exceed FDM part strength, leading to in-flight failures. |
| Mitigation | Generate geometry with appropriate wall thickness (minimum 1.2mm). Include spar channels in the design so users can insert carbon fiber or wooden spars for primary load paths. Provide print orientation recommendations that place load-bearing layers in the strongest direction. Include a disclaimer that the tool generates geometry, not structural certification. Phase 2: Add estimated weight readout so users can sanity-check against typical RC aircraft weights. |

### 10.11 Performance Degradation in Three.js Viewport

| Risk level | Low |
|---|---|
| Description | High-polygon meshes from CadQuery (especially filleted or curved surfaces) may cause Three.js rendering to drop below 60fps on lower-end hardware. |
| Mitigation | Send a simplified preview mesh to Three.js (reduced polygon count) while keeping the full-fidelity mesh for STL export. Use Three.js LOD (level of detail) for distant views. Set a polygon budget for the preview mesh. |

### 10.12 Low Adoption Due to Niche Audience

| Risk level | Low (reduced from Medium) |
|---|---|
| Description | The RC plane hobby community is relatively small. The tool may struggle to reach critical mass for community features in Phase 3. |
| Mitigation | Cloud Run deployment significantly reduces this risk by eliminating the installation barrier. A user can try the tool in seconds via a URL, compared to the previous requirement of installing Python or Docker. Focus Phases 1 and 2 on standalone value that does not depend on network effects. Partner with RC clubs and forums (RCGroups, FliteTest) for early distribution. Educators can share the URL with entire classrooms, creating organic growth. Ensure the tool is valuable even to a single user with no community. |

### 10.13 Export Format Compatibility

| Risk level | Low |
|---|---|
| Description | STL, DXF, and SVG implementations may have subtle compatibility issues with specific slicer or cutter software. |
| Mitigation | Test exports against the 5 most popular tools in each category (slicers: PrusaSlicer, Cura, Bambu Studio; cutters: LightBurn, LaserGRBL; CAD: FreeCAD, Fusion 360). Maintain a compatibility matrix in documentation. |

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **Airfoil** | The cross-sectional shape of a wing or tail surface, defining its aerodynamic characteristics |
| **Aspect ratio** | Wingspan squared divided by wing area; higher values indicate longer, narrower wings |
| **Chord** | The distance from the leading edge to the trailing edge of a wing or tail surface |
| **CG (Center of Gravity)** | The balance point of the aircraft; must fall within a specific range for stable flight |
| **Cloud Run** | Google Cloud's serverless container platform; automatically scales containers based on incoming traffic, including scaling to zero when idle |
| **Cold start** | The delay when a Cloud Run instance starts from zero; includes container image loading and application initialization |
| **Dihedral** | The upward angle of the wing or tail from the horizontal; contributes to roll stability |
| **Docker** | A platform for packaging applications and their dependencies into standardized containers that run consistently across environments |
| **Empennage** | The tail assembly of an aircraft, including horizontal and vertical stabilizers |
| **Incidence angle** | The angle between a wing or tail surface and the fuselage reference line |
| **IndexedDB** | A browser-based database API for storing structured data client-side; used in cloud mode for design persistence |
| **Scale-to-zero** | Cloud Run's ability to reduce running instances to zero when no requests are being processed, eliminating costs during idle periods |
| **Sweep** | The angle at which the wing leading edge is angled backward (or forward) from perpendicular to the fuselage |
| **Tail volume coefficient** | A dimensionless ratio relating tail area and moment arm to wing area and chord; used to assess tail sizing adequacy |
| **Taper ratio** | The ratio of tip chord to root chord; a value of 1.0 is rectangular, less than 1.0 is tapered |
| **V-tail** | A tail configuration using two angled surfaces instead of separate horizontal and vertical stabilizers |
| **Wing loading** | The aircraft weight divided by wing area; a key indicator of flight characteristics and landing speed |

---

## Appendix B: UI Reference

The following screens from the design mockups define the reference UI layout:

- **Screen 1 (Default state):** Top-down aircraft view in central viewport with dimension annotations. Right panel shows Global Parameters (fuselage dropdown, engines, span, chord, tail type). Bottom-left panel shows "SELECT A COMPONENT TO CONFIGURE" prompt. Bottom-right shows an action button.
- **Screen 2 (Wing selected):** Wings highlighted in yellow. Bottom-left panel shows wing parameters: Airfoil dropdown, Sections, Sweep, Incident, Tip/Root Ratio.
- **Screen 3 (Tail selected):** Tail highlighted in yellow (V-tail configuration). Bottom-left panel shows tail parameters: Type (V-Tail), Dihedral, Angle, Span, Chord, Incident.

These mockups establish the interaction pattern: click a component to select it, see its parameters in the detail panel, adjust parameters, and observe real-time viewport updates.
