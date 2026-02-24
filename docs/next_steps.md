# Next Steps: Implementation Guide → Task List

This document is a roadmap for the next session(s). Follow it in order.

---

## Step 1: Create `docs/implementation_guide.md`

This is the bridge between the spec (what to build) and the task list (how to build it). It prevents agents from producing incompatible code.

### 1.1 Directory Tree

Define the exact file structure for both backend and frontend. Agents must place files exactly here.

**Derive from:** Section 5.2 (Dockerfile references `backend/`, `frontend/`, `airfoils/`), Section 5.4 (FastAPI app structure), Section 5.7 (frontend stack).

**Must specify:**
```
cheng/
├── CLAUDE.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── airfoils/               # .dat files for airfoil profiles
├── backend/
│   ├── __init__.py
│   ├── main.py             # FastAPI app, lifespan, static mount
│   ├── models.py           # Pydantic: AircraftDesign, ExportRequest, GenerationResult, DesignSummary
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── designs.py      # CRUD endpoints for /api/designs
│   │   ├── generate.py     # POST /api/generate
│   │   ├── export.py       # POST /api/export
│   │   └── websocket.py    # /ws/preview handler
│   ├── geometry/
│   │   ├── __init__.py
│   │   ├── engine.py       # generate_geometry_safe(), _cadquery_limiter
│   │   ├── fuselage.py     # build_fuselage(design) -> cq.Workplane
│   │   ├── wing.py         # build_wing(design) -> cq.Workplane
│   │   ├── tail.py         # build_tail(design) -> cq.Workplane
│   │   ├── airfoil.py      # load_airfoil(name) -> list[tuple[float,float]]
│   │   └── tessellate.py   # tessellate_for_preview(), tessellate_for_export()
│   ├── export/
│   │   ├── __init__.py
│   │   ├── section.py      # auto_section(solid, bed_x, bed_y, bed_z)
│   │   ├── joints.py       # add_tongue_and_groove(left, right, overlap, tolerance)
│   │   └── package.py      # build_zip(sections) -> Path (temp file)
│   ├── storage.py          # StorageBackend Protocol + LocalStorage
│   └── validation.py       # compute_warnings(design) -> list[Warning]
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types/
│       │   └── design.ts       # AircraftDesign interface (mirrors Pydantic model)
│       ├── store/
│       │   ├── designStore.ts   # Zustand store: params, derived, warnings, presets
│       │   └── connectionStore.ts # WebSocket state: connected/reconnecting/disconnected
│       ├── hooks/
│       │   ├── useWebSocket.ts  # WebSocket connection, binary parsing, reconnect logic
│       │   └── useDesignSync.ts # Debounce/throttle → send params → update derived
│       ├── components/
│       │   ├── Toolbar.tsx
│       │   ├── Viewport/
│       │   │   ├── Scene.tsx         # R3F Canvas, lights, camera
│       │   │   ├── AircraftMesh.tsx  # Mesh from binary buffer
│       │   │   ├── Annotations.tsx   # Dimension leaders
│       │   │   └── Controls.tsx      # Orbit/pan/zoom
│       │   ├── panels/
│       │   │   ├── GlobalPanel.tsx
│       │   │   ├── ComponentPanel.tsx # Dispatches to WingPanel/TailPanel
│       │   │   ├── WingPanel.tsx
│       │   │   ├── TailConventionalPanel.tsx
│       │   │   └── TailVTailPanel.tsx
│       │   ├── ExportDialog.tsx
│       │   └── ConnectionStatus.tsx
│       └── lib/
│           ├── presets.ts       # Trainer, Sport, Aerobatic JSON objects
│           ├── validation.ts    # Client-side range clamping + warning display
│           └── meshParser.ts    # Parse binary WebSocket frames into Three.js BufferGeometry
└── tests/
    ├── backend/
    │   ├── test_models.py
    │   ├── test_routes.py
    │   ├── test_geometry.py
    │   └── test_export.py
    └── frontend/
        └── (vitest + playwright specs)
```

### 1.2 Geometry Engine Public API

Define function signatures so the geometry agent and export agent agree on interfaces.

**Must specify these functions with full type signatures:**
- `build_fuselage(design: AircraftDesign) -> cq.Workplane`
- `build_wing(design: AircraftDesign, side: str) -> cq.Workplane`
- `build_tail(design: AircraftDesign) -> cq.Workplane`
- `assemble_aircraft(design: AircraftDesign) -> dict[str, cq.Workplane]` — returns component name → solid
- `tessellate_for_preview(solid: cq.Workplane, tolerance: float = 0.5) -> MeshData`
- `tessellate_for_export(solid: cq.Workplane, tolerance: float = 0.1) -> bytes` (STL binary)
- `MeshData` dataclass: vertices (ndarray), normals (ndarray), faces (ndarray)
- `generate_geometry_safe(design: AircraftDesign) -> GenerationResult` (async, uses limiter)
- `compute_derived_values(design: AircraftDesign) -> dict` (pure math, no CadQuery)

### 1.3 TypeScript AircraftDesign Interface

Write the canonical TypeScript interface that mirrors the Pydantic model. All frontend agents import from `src/types/design.ts`.

**Derive from:** Section 6.3 of mvp_spec.md (Pydantic model). Convert snake_case fields to camelCase for TypeScript.

### 1.4 Zustand Store Shape

Define the store contract so panel agents and viewport agent share state.

**Must specify:**
```typescript
interface DesignStore {
  // Current design params (source of truth)
  design: AircraftDesign;
  setParam: (key: keyof AircraftDesign, value: any) => void;
  loadPreset: (name: 'Trainer' | 'Sport' | 'Aerobatic') => void;
  activePreset: string; // 'Trainer' | 'Sport' | 'Aerobatic' | 'Custom'

  // Derived values (from backend)
  derived: DerivedValues;

  // Validation warnings (from backend)
  warnings: ValidationWarning[];

  // Mesh data (from WebSocket binary)
  meshData: MeshData | null;

  // Selection state
  selectedComponent: string | null; // 'wing' | 'tail' | 'fuselage' | null
  setSelectedComponent: (c: string | null) => void;

  // File operations
  designId: string | null;
  designName: string;
  isDirty: boolean;
}
```

### 1.5 WebSocket Binary Parser

Specify the exact function signature for parsing the binary protocol (Section 6.2) into the store's `meshData` + `derived` + `warnings`.

---

## Step 2: Create the Task List

After `implementation_guide.md` is written, decompose into tasks. Use the Task tools (TaskCreate, TaskUpdate, etc.) with a team.

### Suggested task decomposition:

**Phase 0 — Scaffold (sequential, do first)**
1. Create project directory structure (all empty files with correct paths)
2. Write pyproject.toml with dependencies
3. Write package.json with dependencies
4. Write Dockerfile (copy from spec)
5. Write docker-compose.yml (copy from spec)
6. Write backend/models.py (Pydantic models from spec)
7. Write frontend/src/types/design.ts (TypeScript interface from guide)
8. Write frontend/src/store/designStore.ts (Zustand store from guide)
9. Write frontend/src/lib/presets.ts (3 preset JSON objects from spec Section 4)

**Phase 1 — Parallel tracks (3-4 agents)**

*Track A: Backend API*
- FastAPI app shell (main.py, health, static mount)
- Storage backend (storage.py — nearly copy-paste from spec)
- Design CRUD routes (routes/designs.py)
- Validation logic (validation.py — V01-V06, V16-V23)

*Track B: Geometry Engine*
- Airfoil loader (geometry/airfoil.py — parse .dat files)
- Fuselage generator (geometry/fuselage.py)
- Wing generator (geometry/wing.py)
- Tail generator (geometry/tail.py)
- Assembly + tessellation (geometry/engine.py, tessellate.py)

*Track C: Frontend Core*
- React app shell (App.tsx, routing, layout CSS)
- WebSocket hook + binary parser
- Viewport (R3F scene, camera, selection, annotations)
- Connection status indicator

*Track D: Frontend Panels*
- Global panel (all 8 fields + preset dropdown)
- Wing panel (5 fields + 3 derived readouts)
- Tail panels (conventional + V-tail variants)
- Export dialog (10 fields + estimated parts)

**Phase 2 — Integration (sequential)**
- Wire WebSocket handler (routes/websocket.py → geometry engine → binary response)
- Wire export endpoint (routes/export.py → geometry → sectioning → joints → ZIP)
- Wire generate endpoint (routes/generate.py → geometry → JSON response)
- End-to-end smoke test

**Phase 3 — Polish & Verify**
- Run acceptance criteria from spec Section 10
- Fix any issues found
- Verify Docker build works end-to-end

---

## Context Recovery Notes

If starting a new session:
1. Read `CLAUDE.md` first — it has the full project context
2. Read `docs/mvp_spec.md` sections as needed (it's ~1400 lines, read by section)
3. Read this file (`docs/next_steps.md`) for what to do next
4. Check `docs/implementation_guide.md` — if it exists, skip to Step 2
