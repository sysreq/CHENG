# CHENG Implementation Guide

> **Bridge Document — v0.1.0**
>
> This document translates the [MVP Specification](mvp_spec.md) into concrete implementation contracts: directory layout, API signatures, TypeScript interfaces, store shape, and module boundaries. Implementation agents should treat this document as their primary reference alongside the spec.
>
> **Precedence:** If this guide conflicts with `mvp_spec.md`, the spec wins. If this guide is silent on a topic, check the spec.

---

## 1. Directory Tree

All files must be placed exactly at these paths. No additional top-level directories without spec team approval.

```
cheng/
├── CLAUDE.md                          # Project conventions for AI agents
├── Dockerfile                         # Multi-stage build (spec §5.2)
├── docker-compose.yml                 # Dev environment (spec §5.3)
├── pyproject.toml                     # Python deps: fastapi, cadquery, uvicorn, anyio, pydantic
├── uv.lock                            # Locked Python dependencies
├── airfoils/                          # .dat files for airfoil coordinate profiles
│   ├── flat_plate.dat
│   ├── naca0012.dat
│   ├── naca2412.dat
│   ├── naca4412.dat
│   ├── naca6412.dat
│   ├── clark_y.dat
│   ├── eppler193.dat
│   ├── eppler387.dat
│   ├── selig1223.dat
│   └── ag25.dat
├── backend/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app, lifespan, static mount, route registration
│   ├── models.py                      # Pydantic: AircraftDesign, ExportRequest, GenerationResult, DesignSummary
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── designs.py                 # CRUD: GET/POST/DELETE /api/designs
│   │   ├── generate.py                # POST /api/generate (REST fallback)
│   │   ├── export.py                  # POST /api/export → StreamingResponse ZIP
│   │   └── websocket.py               # /ws/preview handler: last-write-wins, binary response
│   ├── geometry/
│   │   ├── __init__.py                # Re-exports: assemble_aircraft, generate_geometry_safe
│   │   ├── engine.py                  # assemble_aircraft(), generate_geometry_safe(), _cadquery_limiter
│   │   ├── fuselage.py                # build_fuselage(design) → cq.Workplane
│   │   ├── wing.py                    # build_wing(design, side) → cq.Workplane
│   │   ├── tail.py                    # build_tail(design) → dict[str, cq.Workplane]
│   │   ├── airfoil.py                 # load_airfoil(name) → list[tuple[float, float]]
│   │   └── tessellate.py              # tessellate_for_preview(), tessellate_for_export(), MeshData
│   ├── export/
│   │   ├── __init__.py
│   │   ├── section.py                 # auto_section(), SectionPart dataclass
│   │   ├── joints.py                  # add_tongue_and_groove()
│   │   └── package.py                 # build_zip(sections, design) → Path (temp file on /data/tmp)
│   ├── storage.py                     # StorageBackend Protocol + LocalStorage class
│   └── validation.py                  # compute_warnings(design) → list[ValidationWarning]
├── frontend/
│   ├── package.json                   # React 19, Three.js/R3F, Zustand, Radix, Tailwind 4
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts                 # Dev proxy: /api/* and /ws/* → localhost:8000
│   ├── tsconfig.json                  # strict: true, paths: { "@/*": ["./src/*"] }
│   ├── tsconfig.node.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx                   # React root, StrictMode
│       ├── App.tsx                    # Layout shell: Toolbar + Viewport + Panels + ExportDialog
│       ├── types/
│       │   └── design.ts             # AircraftDesign, DerivedValues, MeshData, ValidationWarning, etc.
│       ├── store/
│       │   ├── designStore.ts         # Zustand + Zundo + Immer: design params, derived, warnings, mesh
│       │   └── connectionStore.ts     # WebSocket connection state machine
│       ├── hooks/
│       │   ├── useWebSocket.ts        # WS connection, binary parsing, reconnect logic
│       │   └── useDesignSync.ts       # Debounce/throttle → send params → update derived
│       ├── components/
│       │   ├── Toolbar.tsx            # File ops, view controls, undo/redo, connection status
│       │   ├── Viewport/
│       │   │   ├── Scene.tsx          # R3F Canvas, lights, camera, dark background (#2A2A2E)
│       │   │   ├── AircraftMesh.tsx   # BufferGeometry from binary data, component highlighting
│       │   │   ├── Annotations.tsx    # Dimension leaders: length, wingspan, sweep angle
│       │   │   └── Controls.tsx       # Orbit (right-click), Pan (middle-click), Zoom (scroll)
│       │   ├── panels/
│       │   │   ├── GlobalPanel.tsx    # 8 fields + preset dropdown
│       │   │   ├── ComponentPanel.tsx # Router: dispatches to Wing/Tail panels based on selection
│       │   │   ├── WingPanel.tsx      # 5 editable + 6 derived read-only
│       │   │   ├── TailConventionalPanel.tsx  # 6 fields (conventional/T-tail/cruciform)
│       │   │   └── TailVTailPanel.tsx # 5 fields (V-tail variant)
│       │   ├── ExportDialog.tsx       # Modal: 10 print params + estimated parts + Export ZIP button
│       │   └── ConnectionStatus.tsx   # Green/Yellow/Red dot + banner
│       └── lib/
│           ├── presets.ts             # Trainer, Sport, Aerobatic preset objects + factory
│           ├── validation.ts          # Client-side range clamping + warning display helpers
│           ├── meshParser.ts          # Parse binary WebSocket frames → typed MeshFrame/ErrorFrame
│           └── config.ts              # getApiUrl(), getWebSocketUrl() helpers
└── tests/
    ├── backend/
    │   ├── conftest.py                # Shared fixtures: test_design, mock_storage
    │   ├── test_models.py             # Pydantic model validation, serialization
    │   ├── test_routes.py             # FastAPI TestClient: all REST endpoints
    │   ├── test_geometry.py           # Geometry generation: watertight, dimensions match
    │   ├── test_export.py             # Sectioning, joints, ZIP packaging
    │   └── test_validation.py         # All V01-V06, V16-V23 warning rules
    └── frontend/
        ├── vitest.config.ts
        ├── unit/                      # Vitest: store, parser, presets, validation
        └── e2e/                       # Playwright: viewport interaction, export flow
```

### File count summary

| Directory | Files | Purpose |
|-----------|-------|---------|
| Root | 5 | Config: CLAUDE.md, Dockerfile, docker-compose.yml, pyproject.toml, uv.lock |
| airfoils/ | 10 | Coordinate data for 10 airfoil profiles |
| backend/ | 16 | Python: FastAPI app, geometry engine, export pipeline, storage, validation |
| frontend/src/ | 21 | TypeScript: React app, store, hooks, components, utilities |
| tests/ | 8+ | Backend pytest + frontend vitest/playwright |
| **Total** | **~60** | |

### Module ownership (for parallel agent assignment)

| Track | Modules | Dependencies |
|-------|---------|-------------|
| **A: Backend API** | main.py, routes/\*, storage.py, validation.py, models.py | models.py must exist first |
| **B: Geometry Engine** | geometry/\*, export/\* | models.py, airfoils/ |
| **C: Frontend Core** | App.tsx, store/\*, hooks/\*, Viewport/\*, ConnectionStatus, lib/meshParser, lib/config | types/design.ts must exist first |
| **D: Frontend Panels** | panels/\*, ExportDialog, Toolbar, lib/presets, lib/validation | types/design.ts, store/ must exist first |

---

## 2. Geometry Engine Public API

> **Module:** `backend/geometry/`
>
> All functions use CadQuery's `cq.Workplane` as the primary solid representation. CadQuery operations are CPU-bound; all public async functions use the shared `_cadquery_limiter` (CapacityLimiter(4)) to prevent OOM.

### 2.1 Data Classes

#### MeshData

**Module:** `backend/geometry/tessellate.py`

```python
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class MeshData:
    """Tessellated mesh data for WebSocket binary transport.

    Contains the raw vertex, normal, and face data that gets packed into the
    binary WebSocket frame (message type 0x01) per spec Section 6.2.

    Layout in the binary frame:
      - vertices: N x 3 float32 array of (x, y, z) positions
      - normals:  N x 3 float32 array of (nx, ny, nz) per-vertex normals
      - faces:    M x 3 uint32 array of triangle vertex indices

    Attributes:
        vertices: Shape (N, 3), dtype float32. Vertex positions in mm.
        normals:  Shape (N, 3), dtype float32. Unit-length per-vertex normals.
        faces:    Shape (M, 3), dtype uint32. Triangle indices into vertices/normals.
    """

    vertices: NDArray[np.float32]   # shape (N, 3)
    normals: NDArray[np.float32]    # shape (N, 3)
    faces: NDArray[np.uint32]       # shape (M, 3)

    @property
    def vertex_count(self) -> int:
        """Number of vertices."""
        return self.vertices.shape[0]

    @property
    def face_count(self) -> int:
        """Number of triangular faces."""
        return self.faces.shape[0]

    def to_binary_frame(self) -> bytes:
        """Pack into the WebSocket binary frame format (spec Section 6.2).

        Returns a bytes object with layout:
          [msg_type: uint32][vertex_count: uint32][face_count: uint32]
          [vertices: N*12 bytes][normals: N*12 bytes][faces: M*12 bytes]

        The JSON trailer (derived values + validation) is NOT included here;
        the WebSocket handler appends it separately.
        """
        ...
```

#### SectionPart

**Module:** `backend/export/section.py`

```python
from __future__ import annotations

from dataclasses import dataclass
import cadquery as cq


@dataclass
class SectionPart:
    """A single printable section of a component, ready for STL export.

    Created by the auto-sectioning algorithm after splitting oversized
    components to fit the user's print bed. Each SectionPart carries both
    the CadQuery solid (for tessellation) and metadata (for the manifest).

    The filename follows the convention: {component}_{side}_{section_num}of{total_sections}.stl
    Examples: "wing_left_1of3.stl", "fuselage_center_1of2.stl", "v_stab_center_1of1.stl"
    """

    solid: cq.Workplane
    filename: str
    component: str            # "wing", "fuselage", "h_stab", "v_stab", "v_tail"
    side: str                 # "left", "right", "center"
    section_num: int          # 1-based section number along the split axis
    total_sections: int
    dimensions_mm: tuple[float, float, float]  # bounding box (x, y, z) after sectioning
    print_orientation: str    # "trailing-edge down", "flat", "leading-edge down"
    assembly_order: int       # 1-based global assembly order hint
```

### 2.2 Component Builders

#### build_fuselage

**Module:** `backend/geometry/fuselage.py`

```python
from __future__ import annotations

import cadquery as cq
from backend.models import AircraftDesign


def build_fuselage(design: AircraftDesign) -> cq.Workplane:
    """Build the fuselage solid based on the selected fuselage preset.

    Generates a closed, watertight fuselage solid positioned at the origin
    with the nose pointing in the +X direction. The fuselage length runs
    along the X axis, width along Y, and height along Z.

    The geometry varies by fuselage_preset (G01):

    - **"Conventional"**: Tubular fuselage built by lofting circular/oval
      cross-sections along X. Three zones:
        - Nose (25% of fuselage_length): tapers from small nose radius to max cross-section.
        - Cabin (50%): constant cross-section with wing saddle cutout.
        - Tail cone (25%): tapers down to small tail radius.
      Wall thickness is 1.6 mm (F14, preset-controlled in MVP).

    - **"Pod"**: Shorter, wider fuselage for pusher configurations. Blunter nose
      (15%), wider cabin (60%), shorter tail cone (25%). Oval cross-sections.

    - **"BWB" (Blended-Wing-Body)**: Blends smoothly into the wing root.
      Lofts from rounded-rectangle nose to airfoil-shaped wing junction.

    All presets include:
    - Wing saddle cutout positioned per wing_mount_type (High/Mid/Low/Shoulder)
    - Motor mount boss at nose (Tractor) or tail (Pusher) per motor_config
    - Hollow interior when hollow_parts is True

    Args:
        design: Complete aircraft design parameters.

    Returns:
        cq.Workplane with fuselage solid. Origin at nose, +X toward tail, +Z up.

    Raises:
        ValueError: If fuselage_preset is not one of "Conventional", "Pod", "BWB".
    """
    ...
```

#### build_wing

**Module:** `backend/geometry/wing.py`

```python
from __future__ import annotations

from typing import Literal
import cadquery as cq
from backend.models import AircraftDesign


def build_wing(design: AircraftDesign, side: Literal["left", "right"]) -> cq.Workplane:
    """Build one wing half (left or right) as a solid.

    Generates a single wing panel from root to tip. The two halves are built
    separately so they can be independently sectioned for printing.

    **Geometry construction process:**

    1. **Airfoil loading**: Load profile from .dat file corresponding to
       design.wing_airfoil (e.g., "Clark-Y" -> "clark_y.dat"). Normalized to chord=1.0.

    2. **Root section**: Scale airfoil to design.wing_chord (G05). Position at Y=0.
       Apply wing incidence (W08, fixed at 2 deg in MVP).

    3. **Tip section**: Scale airfoil to tip_chord = wing_chord * wing_tip_root_ratio.
       Position at Y = ±wing_span/2. Apply wing twist (W06, fixed at 0 deg in MVP).

    4. **Sweep**: Offset tip X by (wing_span/2) * tan(wing_sweep * pi/180).

    5. **Dihedral**: Offset tip Z by (wing_span/2) * tan(wing_dihedral * pi/180).
       Value is per-panel, not total included angle.

    6. **Loft**: Create solid via cq loft() with ruled=False (smooth surface).

    7. **Trailing edge enforcement**: Enforce min thickness of te_min_thickness (PR09).

    8. **Skin shell**: If hollow_parts is True, shell to wing_skin_thickness (W20),
       leaving root face open for spar insertion and fuselage mating.

    9. **Mirror**: "left" extends in -Y, "right" extends in +Y.

    Args:
        design: Complete aircraft design parameters.
        side:   Which wing half. "left" extends in -Y, "right" in +Y.

    Returns:
        cq.Workplane with wing half solid. Root at Y=0, tip at Y=±span/2.

    Raises:
        FileNotFoundError: If airfoil .dat file not found.
        ValueError: If airfoil profile has fewer than 10 points.
    """
    ...
```

#### build_tail

**Module:** `backend/geometry/tail.py`

```python
from __future__ import annotations

import cadquery as cq
from backend.models import AircraftDesign


def build_tail(design: AircraftDesign) -> dict[str, cq.Workplane]:
    """Build all tail surfaces based on the selected tail type.

    Returns a dictionary of named tail components. Keys are used as component
    identifiers throughout the export pipeline (filenames, manifest, assembly order).

    **Tail types and returned components:**

    - **"Conventional"**: {"h_stab_left", "h_stab_right", "v_stab"}
    - **"T-Tail"**: Same keys as Conventional; h_stab mounted atop v_stab.
    - **"V-Tail"**: {"v_tail_left", "v_tail_right"} — rotated by v_tail_dihedral.
    - **"Cruciform"**: Same keys as Conventional; h_stab at v_stab midpoint.

    All tail surfaces:
    - Positioned at X = tail_arm aft of wing aerodynamic center
    - Use flat-plate or symmetric airfoil profiles
    - Shelled to wing_skin_thickness if hollow_parts is True
    - Trailing edge min thickness enforced per te_min_thickness

    Args:
        design: Complete aircraft design parameters.

    Returns:
        Dict mapping component name → positioned CadQuery solid.

    Raises:
        ValueError: If tail_type is not one of the four supported types.
    """
    ...
```

#### assemble_aircraft

**Module:** `backend/geometry/engine.py`

```python
from __future__ import annotations

import cadquery as cq
from backend.models import AircraftDesign


def assemble_aircraft(design: AircraftDesign) -> dict[str, cq.Workplane]:
    """Assemble all aircraft components into their final positions.

    Calls each component builder, then translates/rotates into the aircraft
    coordinate system: Origin at nose, +X aft, +Y starboard, +Z up.

    **Assembly steps:**
    1. Build fuselage (already at origin).
    2. Build wing halves, translate to wing mount position:
       - X: 25-35% of fuselage_length (varies by fuselage_preset)
       - Z: per wing_mount_type (High/Mid/Low/Shoulder)
    3. Build tail surfaces, translate to X = wing_position_x + tail_arm.
    4. Combine into a single dictionary.

    Returns:
        Dict with keys: "fuselage", "wing_left", "wing_right", plus tail keys
        (varies by tail_type — see build_tail). Total: 5 or 4 entries.

    Raises:
        ValueError: If any component builder raises.
        RuntimeError: If CadQuery boolean operations fail.
    """
    ...
```

### 2.3 Tessellation

#### tessellate_for_preview

**Module:** `backend/geometry/tessellate.py`

```python
def tessellate_for_preview(solid: cq.Workplane, tolerance: float = 0.5) -> MeshData:
    """Tessellate a CadQuery solid into triangle mesh for WebSocket preview.

    Uses coarser tolerance than export for fast transfer. Default 0.5mm produces
    ~20k-50k triangles (~1-3 MB binary) for a 1000mm aircraft.

    Args:
        solid:     CadQuery Workplane containing one or more solids.
        tolerance: Max chordal deviation in mm. Default 0.5mm for preview.

    Returns:
        MeshData with float32 vertices/normals and uint32 face indices.
    """
    ...
```

#### tessellate_for_export

**Module:** `backend/geometry/tessellate.py`

```python
def tessellate_for_export(solid: cq.Workplane, tolerance: float = 0.1) -> bytes:
    """Tessellate a CadQuery solid into binary STL for file export.

    Uses finer tolerance for dimensional accuracy. Output must be watertight
    (acceptance criterion D1: zero errors in PrusaSlicer/Cura/Bambu Studio).

    Binary STL: 80-byte header + 4-byte count + 50 bytes/triangle.

    Args:
        solid:     CadQuery Workplane containing a single solid.
        tolerance: Max chordal deviation in mm. Default 0.1mm for export quality.

    Returns:
        Binary STL file content as bytes.
    """
    ...
```

### 2.4 Async Generation Entry Point

**Module:** `backend/geometry/engine.py`

```python
from __future__ import annotations

import anyio
from backend.models import AircraftDesign, GenerationResult

# Module-level singleton — shared across REST, WebSocket, and export handlers.
# Limits concurrent CadQuery operations to 4 to keep peak memory under ~2 GB.
_cadquery_limiter = anyio.CapacityLimiter(4)


async def generate_geometry_safe(design: AircraftDesign) -> GenerationResult:
    """Generate aircraft geometry with concurrency control.

    Primary entry point for all geometry generation. Wraps blocking CadQuery
    operations in a thread with CapacityLimiter.

    Pipeline: validate → assemble_aircraft → tessellate → compute_derived → compute_warnings → pack result.

    Args:
        design: Validated AircraftDesign parameters.

    Returns:
        GenerationResult with vertices, normals, faces, derived values, and warnings.
    """
    result = await anyio.to_thread.run_sync(
        lambda: _generate_geometry_blocking(design),
        limiter=_cadquery_limiter,
        cancellable=True,
    )
    return result


def _generate_geometry_blocking(design: AircraftDesign) -> GenerationResult:
    """Synchronous geometry generation — runs inside a worker thread.

    NOT public API. Called only by generate_geometry_safe().
    """
    ...
```

### 2.5 Derived Values Computation

**Module:** `backend/geometry/engine.py`

```python
from __future__ import annotations

from backend.models import AircraftDesign


def compute_derived_values(design: AircraftDesign) -> dict:
    """Compute all 8 derived/read-only values from design parameters.

    Pure math — no CadQuery, no geometry. Safe to call frequently.

    **Formulas:**
    1. wing_tip_chord_mm     = wing_chord × wing_tip_root_ratio
    2. wing_area_cm2         = 0.5 × (wing_chord + tip_chord) × wing_span / 100
    3. aspect_ratio          = wing_span² / wing_area_mm²
    4. mean_aero_chord_mm    = (2/3) × wing_chord × (1 + λ + λ²) / (1 + λ)  where λ = wing_tip_root_ratio
    5. taper_ratio           = tip_chord / wing_chord  (= wing_tip_root_ratio in MVP)
    6. estimated_cg_mm       = 0.25 × mean_aero_chord_mm
    7. min_feature_thickness_mm = 2 × nozzle_diameter
    8. wall_thickness_mm     = 1.6 (Conventional/Pod) or wing_skin_thickness (BWB)

    Returns:
        Dict with keys matching the WebSocket JSON trailer "derived" object.
    """
    lambda_ = design.wing_tip_root_ratio

    wing_tip_chord_mm = design.wing_chord * lambda_
    wing_area_mm2 = 0.5 * (design.wing_chord + wing_tip_chord_mm) * design.wing_span
    wing_area_cm2 = wing_area_mm2 / 100.0
    aspect_ratio = (design.wing_span ** 2) / wing_area_mm2
    mean_aero_chord_mm = (
        (2.0 / 3.0) * design.wing_chord
        * (1 + lambda_ + lambda_ ** 2) / (1 + lambda_)
    )
    taper_ratio = wing_tip_chord_mm / design.wing_chord
    estimated_cg_mm = 0.25 * mean_aero_chord_mm
    min_feature_thickness_mm = 2.0 * design.nozzle_diameter

    wall_thickness_map = {
        "Conventional": 1.6,
        "Pod": 1.6,
        "BWB": design.wing_skin_thickness,
    }
    wall_thickness_mm = wall_thickness_map.get(design.fuselage_preset, 1.6)

    return {
        "wing_tip_chord_mm": wing_tip_chord_mm,
        "wing_area_cm2": wing_area_cm2,
        "aspect_ratio": aspect_ratio,
        "mean_aero_chord_mm": mean_aero_chord_mm,
        "taper_ratio": taper_ratio,
        "estimated_cg_mm": estimated_cg_mm,
        "min_feature_thickness_mm": min_feature_thickness_mm,
        "wall_thickness_mm": wall_thickness_mm,
    }
```

### 2.6 Export Pipeline

#### auto_section

**Module:** `backend/export/section.py`

```python
from __future__ import annotations

import cadquery as cq

_JOINT_MARGIN_MM: float = 20.0   # Margin per axis for joint features
_SPLIT_OFFSET_MM: float = 10.0   # Offset when midpoint hits internal features


def auto_section(
    solid: cq.Workplane,
    bed_x: float,
    bed_y: float,
    bed_z: float,
) -> list[cq.Workplane]:
    """Recursively split a solid into sections that fit on the print bed.

    Algorithm (spec §8.2):
    1. Usable volume = (bed - 20mm margin) per axis.
    2. If solid fits, return [solid].
    3. Find axis with largest overshoot.
    4. Bisect at midpoint of that axis.
    5. If bisection produces degenerate geometry, offset by ±10mm and retry.
    6. Recurse on each half.

    Args:
        solid:  CadQuery Workplane to section.
        bed_x/y/z: Print bed dimensions in mm (PR01/02/03).

    Returns:
        List of solids, each fitting within usable bed volume.

    Raises:
        ValueError: If bed dimensions minus margin ≤ 0.
        RuntimeError: If splitting fails after 20 recursion levels.
    """
    ...
```

#### add_tongue_and_groove

**Module:** `backend/export/joints.py`

```python
from __future__ import annotations

import cadquery as cq

_TONGUE_AREA_FRACTION: float = 0.60   # Tongue = 60% of cross-sectional area
_TONGUE_FILLET_RADIUS_MM: float = 1.0  # Fillet on tongue corners


def add_tongue_and_groove(
    left: cq.Workplane,
    right: cq.Workplane,
    overlap: float,
    tolerance: float,
    nozzle_diameter: float,
) -> tuple[cq.Workplane, cq.Workplane]:
    """Add tongue-and-groove joint features to two adjacent sections.

    Per spec §8.3:
    - Tongue protrudes from +axis face of left by `overlap` mm.
    - Groove cut into -axis face of right to depth of `overlap` mm.
    - Groove width = tongue width + 2 × tolerance.
    - Tongue cross-section = 60% of cut-plane area.
    - Tongue corners filleted at 1mm radius.
    - Min tongue width = 3 × nozzle_diameter.

    Args:
        left:            Lower-numbered section. Tongue added to +axis face.
        right:           Higher-numbered section. Groove cut into -axis face.
        overlap:         Tongue/groove length in mm (PR05, default 15).
        tolerance:       Clearance per side in mm (PR11, default 0.15).
        nozzle_diameter: FDM nozzle in mm (PR06). Min tongue = 3× this.

    Returns:
        (modified_left, modified_right) with joint features applied.
    """
    ...
```

#### build_zip

**Module:** `backend/export/package.py`

```python
from __future__ import annotations

from pathlib import Path
from backend.models import AircraftDesign
from backend.export.section import SectionPart

EXPORT_TMP_DIR: Path = Path("/data/tmp")


def build_zip(sections: list[SectionPart], design: AircraftDesign) -> Path:
    """Create ZIP archive with STL files and manifest.

    Tessellates each section (tolerance=0.1), writes STLs + manifest.json
    to a temp ZIP on /data/tmp. Caller must delete after streaming (spec §8.5).

    manifest.json structure: see spec §8.4 (design_name, design_id, version,
    total_parts, parts[], assembly_notes[]).

    Returns:
        Path to temp ZIP file, closed and ready for streaming.
    """
    ...
```

### 2.7 Airfoil Loader

**Module:** `backend/geometry/airfoil.py`

```python
from __future__ import annotations

AIRFOIL_DIR: str = "/app/airfoils"

SUPPORTED_AIRFOILS: list[str] = [
    "Flat-Plate", "NACA-0012", "NACA-2412", "NACA-4412", "NACA-6412",
    "Clark-Y", "Eppler-193", "Eppler-387", "Selig-1223", "AG-25",
]


def load_airfoil(name: str) -> list[tuple[float, float]]:
    """Load an airfoil profile from a .dat file.

    File lookup: lowercase, replace hyphens with underscores, append ".dat".
    Examples: "Clark-Y" -> "clark_y.dat", "NACA-2412" -> "naca_2412.dat"

    Parses both Selig and Lednicer formats. Special case "Flat-Plate" returns
    a programmatic diamond profile (3% chord thickness).

    Returns coordinates in Selig order: TE upper → LE → TE lower.
    Normalized to unit chord (x ∈ [0, 1]). Minimum 10 points.

    Raises:
        FileNotFoundError: If .dat file not found.
        ValueError: If fewer than 10 valid coordinate pairs, or name unsupported.
    """
    ...
```

### 2.8 Module Map Summary

| Function / Class | Module Path | Called By |
|---|---|---|
| `MeshData` | `backend/geometry/tessellate.py` | `tessellate_for_preview`, WebSocket handler |
| `SectionPart` | `backend/export/section.py` | `auto_section`, `build_zip`, export route |
| `build_fuselage()` | `backend/geometry/fuselage.py` | `assemble_aircraft` |
| `build_wing()` | `backend/geometry/wing.py` | `assemble_aircraft` |
| `build_tail()` | `backend/geometry/tail.py` | `assemble_aircraft` |
| `assemble_aircraft()` | `backend/geometry/engine.py` | `_generate_geometry_blocking`, export pipeline |
| `tessellate_for_preview()` | `backend/geometry/tessellate.py` | `_generate_geometry_blocking` |
| `tessellate_for_export()` | `backend/geometry/tessellate.py` | `build_zip` |
| `generate_geometry_safe()` | `backend/geometry/engine.py` | REST, WebSocket, export handlers |
| `compute_derived_values()` | `backend/geometry/engine.py` | `_generate_geometry_blocking`, validation |
| `auto_section()` | `backend/export/section.py` | export pipeline |
| `add_tongue_and_groove()` | `backend/export/joints.py` | export pipeline |
| `build_zip()` | `backend/export/package.py` | export route handler |
| `load_airfoil()` | `backend/geometry/airfoil.py` | `build_wing`, `build_tail` |

### 2.9 Constants Reference

| Constant | Value | Defined In | Purpose |
|---|---|---|---|
| `_cadquery_limiter` | `CapacityLimiter(4)` | `engine.py` | Max concurrent CadQuery ops |
| `_JOINT_MARGIN_MM` | `20.0` | `section.py` | Margin per axis for joints |
| `_SPLIT_OFFSET_MM` | `10.0` | `section.py` | Offset for degenerate splits |
| `_TONGUE_AREA_FRACTION` | `0.60` | `joints.py` | Tongue = 60% cross-section |
| `_TONGUE_FILLET_RADIUS_MM` | `1.0` | `joints.py` | Fillet on tongue corners |
| `EXPORT_TMP_DIR` | `Path("/data/tmp")` | `package.py` | Temp dir for ZIP files |
| `AIRFOIL_DIR` | `"/app/airfoils"` | `airfoil.py` | Airfoil .dat file directory |
| Preview tolerance | `0.5` mm | `tessellate_for_preview` | Chordal deflection for WS |
| Export tolerance | `0.1` mm | `tessellate_for_export` | Chordal deflection for STL |
| Wing incidence (MVP fixed) | `2` deg | `build_wing` | W08, safe default |
| Wing twist (MVP fixed) | `0` deg | `build_wing` | W06, safe default |
| V-tail sweep (MVP fixed) | `0` deg | `build_tail` | T15, safe default |

---

## 3. TypeScript Interfaces

> **Module:** `frontend/src/types/design.ts`
>
> Single source of truth for all frontend types. Every frontend module imports from here.

```typescript
// ============================================================================
// CHENG — Canonical Frontend Type Definitions
// Mirrors backend/models.py Pydantic models (snake_case -> camelCase)
// ============================================================================

// ---------------------------------------------------------------------------
// Enum / Literal Types
// ---------------------------------------------------------------------------

/** Aircraft preset names. 'Custom' auto-selected when any param is manually edited. */
export type PresetName = 'Trainer' | 'Sport' | 'Aerobatic' | 'Custom';

/** Fuselage body style. Controls cross-section shape and wallThickness. */
export type FuselagePreset = 'Pod' | 'Conventional' | 'Blended-Wing-Body';

/** Motor mounting position relative to the fuselage. */
export type MotorConfig = 'Tractor' | 'Pusher';

/** Vertical placement of the wing on the fuselage. */
export type WingMountType = 'High-Wing' | 'Mid-Wing' | 'Low-Wing' | 'Shoulder-Wing';

/** Tail configuration. Determines which tail params are visible in the UI. */
export type TailType = 'Conventional' | 'T-Tail' | 'V-Tail' | 'Cruciform';

/** Available airfoil profiles. Corresponding .dat files in airfoils/ directory. */
export type WingAirfoil =
  | 'Flat-Plate' | 'NACA-0012' | 'NACA-2412' | 'NACA-4412' | 'NACA-6412'
  | 'Clark-Y' | 'Eppler-193' | 'Eppler-387' | 'Selig-1223' | 'AG-25';

/** Joint mechanism for sectioned parts. */
export type JointType = 'Tongue-and-Groove' | 'Dowel-Pin' | 'Flat-with-Alignment-Pins';

/** Selectable component in the 3D viewport. */
export type ComponentSelection = 'wing' | 'tail' | 'fuselage' | null;

/** Source of a parameter change — controls debounce/throttle timing. */
export type ChangeSource = 'slider' | 'text' | 'immediate';

// ---------------------------------------------------------------------------
// AircraftDesign — mirrors backend Pydantic model
// ---------------------------------------------------------------------------

/**
 * Complete aircraft design parameters. Sent to backend on every change via
 * WebSocket (/ws/preview) or REST (POST /api/generate).
 */
export interface AircraftDesign {
  // ── Meta ──────────────────────────────────────────────────────────
  /** Protocol version. Always "0.1.0" for MVP. */
  version: string;
  /** UUID v4 identifier. Generated client-side on new designs. */
  id: string;
  /** User-assigned design name. Default: "Untitled Aircraft". */
  name: string;

  // ── Global / Fuselage ─────────────────────────────────────────────
  /** Fuselage body style. @see FuselagePreset */
  fuselagePreset: FuselagePreset;
  /** Number of engines. @min 0 @max 4 @default 1 */
  engineCount: number;
  /** Motor position. "Tractor" = nose, "Pusher" = rear. @default "Tractor" */
  motorConfig: MotorConfig;
  /** Total wingspan tip-to-tip. @unit mm @min 300 @max 3000 @default 1000 */
  wingSpan: number;
  /** Wing root chord. Tip = wingChord × wingTipRootRatio. @unit mm @min 50 @max 500 @default 180 */
  wingChord: number;
  /** Wing vertical placement on fuselage. @default "High-Wing" */
  wingMountType: WingMountType;
  /** Fuselage length nose to tail. @unit mm @min 150 @max 2000 @default 300 */
  fuselageLength: number;
  /** Tail configuration type. @default "Conventional" */
  tailType: TailType;

  // ── Wing ──────────────────────────────────────────────────────────
  /** Airfoil profile name. Must match a .dat file. @default "Clark-Y" */
  wingAirfoil: WingAirfoil;
  /** Sweep angle. Positive = swept back. @unit deg @min -10 @max 45 @default 0 */
  wingSweep: number;
  /** Tip/root chord ratio. 1.0 = rectangular. @min 0.3 @max 1.0 @default 1.0 */
  wingTipRootRatio: number;
  /** Dihedral per panel. Positive = tips up. @unit deg @min -10 @max 15 @default 3 */
  wingDihedral: number;
  /** Wing skin wall thickness. @unit mm @min 0.8 @max 3.0 @default 1.2 */
  wingSkinThickness: number;

  // ── Tail (Conventional / T-Tail / Cruciform) ──────────────────────
  /** H-stab span. @unit mm @min 100 @max 1200 @default 350 */
  hStabSpan: number;
  /** H-stab chord. @unit mm @min 30 @max 250 @default 100 */
  hStabChord: number;
  /** H-stab incidence. Negative = LE down. @unit deg @min -5 @max 5 @default -1 */
  hStabIncidence: number;
  /** Vertical fin height. @unit mm @min 30 @max 400 @default 100 */
  vStabHeight: number;
  /** Vertical fin root chord. @unit mm @min 30 @max 300 @default 110 */
  vStabRootChord: number;

  // ── Tail (V-Tail) ────────────────────────────────────────────────
  /** V-tail dihedral from horizontal. @unit deg @min 20 @max 60 @default 35 */
  vTailDihedral: number;
  /** V-tail span. @unit mm @min 80 @max 600 @default 280 */
  vTailSpan: number;
  /** V-tail chord. @unit mm @min 30 @max 200 @default 90 */
  vTailChord: number;
  /** V-tail incidence. @unit deg @min -3 @max 3 @default 0 */
  vTailIncidence: number;

  // ── Shared Tail ───────────────────────────────────────────────────
  /** Wing AC to tail AC distance. @unit mm @min 80 @max 1500 @default 180 */
  tailArm: number;

  // ── Export / Print ────────────────────────────────────────────────
  /** Printer bed X. @unit mm @min 100 @max 500 @default 220 */
  printBedX: number;
  /** Printer bed Y. @unit mm @min 100 @max 500 @default 220 */
  printBedY: number;
  /** Printer bed Z. @unit mm @min 50 @max 500 @default 250 */
  printBedZ: number;
  /** Auto-section parts exceeding bed. @default true */
  autoSection: boolean;
  /** Joint overlap length. @unit mm @min 5 @max 30 @default 15 */
  sectionOverlap: number;
  /** Joint mechanism. @default "Tongue-and-Groove" */
  jointType: JointType;
  /** Joint clearance per side. @unit mm @min 0.05 @max 0.5 @default 0.15 */
  jointTolerance: number;
  /** FDM nozzle diameter. @unit mm @min 0.2 @max 1.0 @default 0.4 */
  nozzleDiameter: number;
  /** Hollow out solid parts. @default true */
  hollowParts: boolean;
  /** Trailing edge min thickness. @unit mm @min 0.4 @max 2.0 @default 0.8 */
  teMinThickness: number;
}

// ---------------------------------------------------------------------------
// DerivedValues — computed by backend, read-only on frontend
// ---------------------------------------------------------------------------

/** Backend-computed values from WebSocket JSON trailer. */
export interface DerivedValues {
  /** Tip chord = wingChord × wingTipRootRatio. @unit mm */
  tipChordMm: number;
  /** Wing area (both panels). @unit cm² */
  wingAreaCm2: number;
  /** Aspect ratio = span² / area. */
  aspectRatio: number;
  /** Mean Aerodynamic Chord. @unit mm */
  meanAeroChordMm: number;
  /** Taper ratio = tipChord / rootChord. */
  taperRatio: number;
  /** Balance point = 25% MAC from wing LE. @unit mm */
  estimatedCgMm: number;
  /** Min feature thickness = 2 × nozzle. @unit mm */
  minFeatureThicknessMm: number;
  /** Fuselage wall thickness (preset-controlled). @unit mm */
  wallThicknessMm: number;
}

// ---------------------------------------------------------------------------
// ValidationWarning
// ---------------------------------------------------------------------------

/** Structural warning IDs (V01-V06). */
export type StructuralWarningId = 'V01' | 'V02' | 'V03' | 'V04' | 'V05' | 'V06';
/** Print warning IDs (V16-V23). */
export type PrintWarningId = 'V16' | 'V17' | 'V18' | 'V20' | 'V21' | 'V22' | 'V23';
/** All warning IDs. */
export type WarningId = StructuralWarningId | PrintWarningId;

/** Non-blocking validation warning from the backend. */
export interface ValidationWarning {
  id: WarningId;
  level: 'warn';
  message: string;
  /** camelCase field names affected — for displaying warning icons. */
  fields: string[];
}

// ---------------------------------------------------------------------------
// MeshData — parsed from WebSocket binary frame
// ---------------------------------------------------------------------------

/** Parsed mesh from WebSocket binary protocol (spec §6.2). */
export interface MeshData {
  /** Flat vertex positions [x0,y0,z0, x1,y1,z1, ...]. */
  vertices: Float32Array;
  /** Flat vertex normals [nx0,ny0,nz0, ...]. */
  normals: Float32Array;
  /** Flat face indices [i0,i1,i2, ...] (3 per triangle). */
  faces: Uint32Array;
  vertexCount: number;
  faceCount: number;
}

// ---------------------------------------------------------------------------
// REST Response Types
// ---------------------------------------------------------------------------

/** REST fallback response from POST /api/generate. */
export interface GenerationResult {
  vertices: number[][];
  normals: number[][];
  faces: number[][];
  derived: Record<string, number>;
  validation: Array<{ id: string; level: string; message: string; fields?: string[] }>;
}

/** Summary for design listing (GET /api/designs). */
export interface DesignSummary {
  id: string;
  name: string;
  createdAt: string;
  modifiedAt: string;
}

/** Request body for POST /api/export. */
export interface ExportRequest {
  design: AircraftDesign;
  format: 'stl';
}
```

---

## 4. Zustand Store Shape

### 4.1 Design Store

> **Module:** `frontend/src/store/designStore.ts`

```typescript
import type {
  AircraftDesign, DerivedValues, ValidationWarning, MeshData,
  PresetName, ComponentSelection, ChangeSource,
} from '../types/design';

/**
 * Main application store. Zundo tracks only `design` + `activePreset` for undo/redo.
 * Derived values, mesh data, and UI state are excluded from history.
 */
export interface DesignStore {
  // ── Design Parameters (undo/redo tracked) ───────────────────────
  design: AircraftDesign;
  setParam: <K extends keyof AircraftDesign>(key: K, value: AircraftDesign[K], source?: ChangeSource) => void;
  loadPreset: (name: Exclude<PresetName, 'Custom'>) => void;
  activePreset: PresetName;
  lastChangeSource: ChangeSource;

  // ── Derived Values (from backend, read-only) ────────────────────
  derived: DerivedValues | null;
  setDerived: (derived: DerivedValues) => void;

  // ── Validation Warnings (from backend) ──────────────────────────
  warnings: ValidationWarning[];
  setWarnings: (warnings: ValidationWarning[]) => void;

  // ── Mesh Data (from WebSocket binary) ───────────────────────────
  meshData: MeshData | null;
  setMeshData: (mesh: MeshData) => void;

  // ── Viewport Selection ──────────────────────────────────────────
  selectedComponent: ComponentSelection;
  setSelectedComponent: (component: ComponentSelection) => void;

  // ── File Operations ─────────────────────────────────────────────
  designId: string | null;
  designName: string;
  isDirty: boolean;
  setDesignName: (name: string) => void;
  newDesign: () => void;
  loadDesign: (id: string) => Promise<void>;
  saveDesign: () => Promise<string>;

  // ── Undo/Redo via Zundo temporal middleware ─────────────────────
  // Access via: useDesignStore.temporal.getState().undo() / .redo()
  // Only `design` and `activePreset` are tracked.
}

/** Subset of state tracked by Zundo for undo/redo. */
export type UndoableState = Pick<DesignStore, 'design' | 'activePreset'>;
```

### 4.2 Connection Store

> **Module:** `frontend/src/store/connectionStore.ts`

```typescript
/**
 * WebSocket connection state machine.
 * - 'connected': Green dot. Full functionality.
 * - 'reconnecting': Yellow pulsing dot. Retry every 3s, max 5 attempts.
 * - 'disconnected': Red dot + banner. Inputs disabled. Auto-retry every 30s.
 */
export type ConnectionState = 'connected' | 'reconnecting' | 'disconnected';

export interface ConnectionStore {
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;  // 5
  setState: (state: ConnectionState) => void;
  incrementAttempt: () => void;
  resetAttempts: () => void;
}
```

### 4.3 Preset Definitions

> **Module:** `frontend/src/lib/presets.ts`

Preset factory functions create fresh objects with new UUIDs on each call. See spec §4 for exact values.

| Preset | Wingspan | Chord | Airfoil | Mount | Dihedral | Taper |
|--------|----------|-------|---------|-------|----------|-------|
| Trainer | 1200mm | 200mm | Clark-Y | High-Wing | 3° | 1.0 |
| Sport | 1000mm | 180mm | NACA-2412 | Mid-Wing | 3° | 0.67 |
| Aerobatic | 900mm | 220mm | NACA-0012 | Mid-Wing | 0° | 1.0 |

```typescript
export const PRESET_DESCRIPTIONS: Record<Exclude<PresetName, 'Custom'>, string>;
export const PRESET_FACTORIES: Record<Exclude<PresetName, 'Custom'>, () => AircraftDesign>;
export function createDesignFromPreset(name: Exclude<PresetName, 'Custom'>): AircraftDesign;
export const DEFAULT_PRESET: Exclude<PresetName, 'Custom'> = 'Trainer';
```

---

## 5. WebSocket Binary Parser

> **Module:** `frontend/src/lib/meshParser.ts`

### 5.1 Frame Types

```typescript
const MSG_TYPE_MESH  = 0x00000001;
const MSG_TYPE_ERROR = 0x00000002;

/** Parsed mesh update frame. */
export interface MeshFrame {
  type: 0x01;
  vertexCount: number;
  faceCount: number;
  vertices: Float32Array;
  normals: Float32Array;
  faces: Uint32Array;
  derived: DerivedValues;
  validation: ValidationWarning[];
}

/** Parsed error frame. */
export interface ErrorFrame {
  type: 0x02;
  error: string;
  detail: string;
  field: string | null;
}

export type ParsedFrame = MeshFrame | ErrorFrame;
```

### 5.2 Parser Implementation

```typescript
/**
 * Parse a binary WebSocket frame from the CHENG backend.
 *
 * Mesh update (0x01) layout — all little-endian:
 *   [0..4]   uint32 message type
 *   [4..8]   uint32 vertex count (N)
 *   [8..12]  uint32 face count (M)
 *   [12..]   float32[N×3] vertex positions
 *   [..]     float32[N×3] vertex normals
 *   [..]     uint32[M×3]  face indices
 *   [..]     UTF-8 JSON   trailer {derived, validation}
 *
 * Error (0x02) layout:
 *   [0..4]   uint32 message type
 *   [4..]    UTF-8 JSON   {error, detail, field}
 *
 * @throws Error if buffer too small or unknown message type.
 */
export function parseMeshFrame(data: ArrayBuffer): ParsedFrame;
```

### 5.3 Three.js BufferGeometry Converter

```typescript
import * as THREE from 'three';

/**
 * Create Three.js BufferGeometry from a parsed MeshFrame.
 * Uses Float32Arrays directly as buffer attributes (zero-copy).
 * Computes bounding box and sphere for frustum culling.
 * Caller is responsible for disposal when geometry is replaced.
 */
export function createBufferGeometry(frame: MeshFrame): THREE.BufferGeometry;
```

---

## 6. WebSocket & Design Sync Hooks

### 6.1 useWebSocket

> **Module:** `frontend/src/hooks/useWebSocket.ts`

```typescript
/**
 * Manages the WebSocket connection to /ws/preview.
 * Opens on mount, closes on unmount. Call exactly once at App level.
 *
 * - Parses binary frames via parseMeshFrame()
 * - Updates designStore (meshData, derived, warnings) on MeshFrame
 * - Updates connectionStore on open/close/error
 * - Implements reconnection: 3s interval, max 5 attempts → disconnected
 */
export function useWebSocket(): {
  send: (design: AircraftDesign) => void;
  disconnect: () => void;
};
```

**Connection lifecycle:**

```
Mount → connect() → ws = new WebSocket(url)
  ├── onopen    → connectionStore.setState('connected'), resetAttempts()
  ├── onmessage → parseMeshFrame(data) → update designStore
  ├── onerror   → console.error (close follows)
  ├── onclose   → if !intentional → startReconnect()
  └── Unmount   → intentional=true, ws.close()
```

**Reconnection (spec §7.6):**

| From | To | Trigger |
|------|----|---------|
| Connected | Reconnecting | WS close/error |
| Reconnecting | Connected | Successful WS open |
| Reconnecting | Disconnected | 5 failed attempts (15s) |
| Disconnected | Reconnecting | User "Retry" click OR auto every 30s |

**Critical:** Set `ws.binaryType = 'arraybuffer'` — parseMeshFrame expects ArrayBuffer, not Blob.

### 6.2 useDesignSync

> **Module:** `frontend/src/hooks/useDesignSync.ts`

```typescript
/**
 * Watches designStore for parameter changes and sends updates via WebSocket.
 * Applies debounce/throttle per spec §7.7:
 *   - Sliders: throttled at 100ms
 *   - Text inputs: debounced at 300ms
 *   - Dropdowns/toggles: immediate
 * Call exactly once at App level.
 */
export function useDesignSync(send: (design: AircraftDesign) => void): void;
```

**Change source tracking:** Components pass `source` when calling `setParam`:
- Slider components: `setParam('wingSweep', 15, 'slider')`
- Text inputs: `setParam('wingSpan', 1200, 'text')`
- Dropdowns/toggles/presets: `setParam('tailType', 'V-Tail', 'immediate')`

**Reconnection resend:** When connection transitions reconnecting → connected, immediately send current design state.

### 6.3 Serialization (camelCase → snake_case)

```typescript
/**
 * Convert camelCase AircraftDesign to snake_case for backend.
 * Mapping is explicit (not algorithmic) to catch mismatches at compile time.
 */
export function serializeDesign(design: AircraftDesign): Record<string, unknown>;
```

Full field mapping in Appendix A.

---

## 7. Module Boundary Rules

### 7.1 Dependency Diagram

```
              ALLOWED IMPORT DIRECTIONS
              ========================

types/  ←──  store/  ←──  hooks/  ←──  components/
               ^               ^
               │               │
              lib/  ───────────┘
```

### 7.2 Rules

| # | Rule | Rationale |
|---|------|-----------|
| 1 | `types/` has **zero** project imports | Leaf module; interfaces and type aliases only |
| 2 | `store/` imports only from `types/` | State shape and actions use types only |
| 3 | `lib/` imports only from `types/` | Testable in isolation; no side effects |
| 4 | `hooks/` imports from `store/`, `lib/`, `types/` | Composes stores + lib into behaviors |
| 5 | `components/` imports from all layers | Only layer that may depend on everything |
| 6 | **No circular dependencies** | Extract shared parts to `types/` or `lib/` |
| 7 | Components **never** import other component directories | Communicate via store only |
| 8 | `store/` never imports `hooks/` or `components/` | Data down, events up |

### 7.3 Full Module Inventory

| Module | Files | Imports From |
|--------|-------|-------------|
| `types/` | `design.ts` | (none) |
| `store/` | `designStore.ts`, `connectionStore.ts` | `types/` |
| `lib/` | `meshParser.ts`, `presets.ts`, `validation.ts`, `config.ts` | `types/` |
| `hooks/` | `useWebSocket.ts`, `useDesignSync.ts` | `types/`, `store/`, `lib/` |
| `components/` | Toolbar, Viewport/\*, panels/\*, ExportDialog, ConnectionStatus | all layers |

---

## 8. Build Configuration

### 8.1 vite.config.ts

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000', ws: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    target: 'es2020',
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three', '@react-three/fiber', '@react-three/drei'],
        },
      },
    },
  },
});
```

### 8.2 tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "jsx": "react-jsx",
    "noEmit": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

### 8.3 Environment Variables

| Variable | Default | Usage |
|----------|---------|-------|
| `VITE_API_URL` | `''` | REST base URL. Empty = same-origin. |
| `VITE_WS_URL` | `''` | WebSocket URL. Empty = computed from `window.location`. |

Empty defaults work in both dev (Vite proxy to :8000) and production (FastAPI serves static at :8000).

### 8.4 Frontend Dependencies

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "three": "^0.170.0",
    "@react-three/fiber": "^9.0.0",
    "@react-three/drei": "^10.0.0",
    "zustand": "^5.0.0",
    "zundo": "^3.0.0",
    "immer": "^10.0.0",
    "@radix-ui/react-dropdown-menu": "^2.0.0",
    "@radix-ui/react-dialog": "^1.0.0",
    "@radix-ui/react-slider": "^1.0.0",
    "@radix-ui/react-tooltip": "^1.0.0",
    "@radix-ui/react-toggle": "^1.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^6.0.0",
    "typescript": "^5.7.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@types/three": "^0.170.0",
    "tailwindcss": "^4.0.0",
    "vitest": "^3.0.0",
    "@testing-library/react": "^16.0.0",
    "playwright": "^1.49.0"
  }
}
```

---

## Appendix A: Field Name Mapping (Python ↔ TypeScript)

| Python (snake_case) | TypeScript (camelCase) |
|---|---|
| `fuselage_preset` | `fuselagePreset` |
| `engine_count` | `engineCount` |
| `motor_config` | `motorConfig` |
| `wing_span` | `wingSpan` |
| `wing_chord` | `wingChord` |
| `wing_mount_type` | `wingMountType` |
| `fuselage_length` | `fuselageLength` |
| `tail_type` | `tailType` |
| `wing_airfoil` | `wingAirfoil` |
| `wing_sweep` | `wingSweep` |
| `wing_tip_root_ratio` | `wingTipRootRatio` |
| `wing_dihedral` | `wingDihedral` |
| `wing_skin_thickness` | `wingSkinThickness` |
| `h_stab_span` | `hStabSpan` |
| `h_stab_chord` | `hStabChord` |
| `h_stab_incidence` | `hStabIncidence` |
| `v_stab_height` | `vStabHeight` |
| `v_stab_root_chord` | `vStabRootChord` |
| `v_tail_dihedral` | `vTailDihedral` |
| `v_tail_span` | `vTailSpan` |
| `v_tail_chord` | `vTailChord` |
| `v_tail_incidence` | `vTailIncidence` |
| `tail_arm` | `tailArm` |
| `print_bed_x` | `printBedX` |
| `print_bed_y` | `printBedY` |
| `print_bed_z` | `printBedZ` |
| `auto_section` | `autoSection` |
| `section_overlap` | `sectionOverlap` |
| `joint_type` | `jointType` |
| `joint_tolerance` | `jointTolerance` |
| `nozzle_diameter` | `nozzleDiameter` |
| `hollow_parts` | `hollowParts` |
| `te_min_thickness` | `teMinThickness` |
| **Derived (JSON trailer)** | |
| `wing_tip_chord_mm` | `tipChordMm` |
| `wing_area_cm2` | `wingAreaCm2` |
| `aspect_ratio` | `aspectRatio` |
| `mean_aero_chord_mm` | `meanAeroChordMm` |
| `taper_ratio` | `taperRatio` |
| `estimated_cg_mm` | `estimatedCgMm` |
| `min_feature_thickness_mm` | `minFeatureThicknessMm` |
| `wall_thickness_mm` | `wallThicknessMm` |

---

*End of Implementation Guide. This document, together with [mvp_spec.md](mvp_spec.md), provides everything needed to implement the MVP. When in doubt, the spec wins.*
