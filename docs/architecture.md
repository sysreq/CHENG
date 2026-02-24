# CHENG - Software Architecture Document

> **Parametric RC Plane Generator - Complete System Design**
>
> Version: 0.3 (Revised - Docker Deployment + Cloud Run Support)
> Last Updated: 2026-02-23

---

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [Deployment Architecture](#2-deployment-architecture)
3. [Data Model / Schema](#3-data-model--schema)
4. [Parameter Dependency Graph](#4-parameter-dependency-graph)
5. [Geometry Generation Pipeline](#5-geometry-generation-pipeline)
6. [State Management Architecture](#6-state-management-architecture)
7. [File Format & Storage](#7-file-format--storage)
8. [Export Pipeline](#8-export-pipeline)
9. [Validation Engine](#9-validation-engine)
10. [Plugin / Extension Architecture](#10-plugin--extension-architecture)
11. [Phase Breakdown](#11-phase-breakdown)

---

## 1. Technology Stack

### 1.0 Architecture Overview

CHENG is a **containerized client-server application** that runs identically in local Docker and Google Cloud Run environments:

```
┌─────────────────────────────────────────────────────────────────┐
│                     DOCKER CONTAINER                             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Python Backend (FastAPI + CadQuery + OpenCascade)       │    │
│  │  Serves built frontend static files                      │    │
│  │  Geometry generation, STL/STEP export, Validation        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                        ▲                                         │
│                   Port 8000                                      │
└────────────────────────┼────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            │    Browser (UI)         │
            │    React + Three.js     │
            │    Parameter UI         │
            │    3D Preview           │
            └─────────────────────────┘

LOCAL MODE:   docker run -p 8000:8000 -v ~/.cheng:/data cheng
CLOUD MODE:   Same image deployed to Google Cloud Run
```

**Deployment modes:**
- **Local mode** (`CHENG_MODE=local`): User runs a Docker container on their machine. Designs persist to a mounted volume (`/data/designs/`). No cloud dependency.
- **Cloud mode** (`CHENG_MODE=cloud`): Same image deployed to Cloud Run. Backend is stateless. All design state lives in the browser (Zustand store + IndexedDB). Backend is a pure function: parameters in, mesh/STL out.

The environment variable `CHENG_MODE` (default: `local`) toggles storage behavior. The geometry engine, API, and frontend are identical in both modes.

### 1.1 Backend: **Python 3.11+ / FastAPI / CadQuery**

**CadQuery** is the parametric geometry engine. It is a Python library built on the OpenCascade (OCCT) kernel, giving us professional-grade B-rep solid modeling:

**Why CadQuery:**
- **B-rep kernel (OpenCascade)**: True solid geometry, not just meshes. Lofts produce smooth NURBS surfaces, not faceted approximations. This is critical for aerodynamic shapes.
- **Native STEP export**: STEP output is a first-class citizen -- no WASM hacks or conversion layers needed.
- **Native STL export**: Tessellation of B-rep solids to triangle meshes with configurable tolerance (angular deflection, linear deflection). Produces watertight meshes ideal for 3D printing.
- **Lofting**: `Workplane.loft()` creates smooth solids between multiple cross-section profiles -- exactly what we need for wings (airfoil sections at different span stations) and fuselages (cross-sections along the longitudinal axis).
- **Splines**: `Workplane.spline()` creates smooth curves through point sets -- perfect for airfoil profiles.
- **Shell**: `Workplane.shell()` hollows out solids with a specified wall thickness -- useful for lightweight fuselage sections.
- **Boolean operations**: `cut()`, `union()`, `intersect()` for control surface cutouts, motor mount holes, assembly joint features.
- **Mature ecosystem**: Well-documented, active community, used in production CAD workflows.

**Why FastAPI:**
- Async support allows serving WebSocket connections for real-time preview updates alongside REST endpoints for export operations
- Automatic OpenAPI documentation for the API
- Pydantic model validation maps directly to our parameter constraint system
- Lightweight; starts in < 1 second locally
- **Stateless request model**: The backend holds NO design state between requests. ALL design state lives in the frontend Zustand store. Each backend request is a pure function (parameters in, mesh/STL out). This enables horizontal scaling on Cloud Run where multiple users may hit the same container.

```python
# Example: CadQuery wing section loft
import cadquery as cq

def generate_wing(params: WingParams) -> cq.Workplane:
    """Loft between airfoil sections to create a wing solid."""
    half_span = params.span / 2
    sections = []

    for section in params.sections:
        # Get airfoil coordinates (normalized 0-1)
        coords = get_airfoil_coords(section.airfoil)

        # Scale by chord, apply twist
        scaled = scale_and_twist(coords, section.chord, section.twist)

        # Create spline wire on workplane at spanwise position
        offset = section.span_position * half_span
        wp = (
            cq.Workplane("XZ")
            .transformed(offset=(0, offset, 0))
            .spline(scaled, close=True)
        )
        sections.append(wp)

    # Loft between all sections
    wing_half = cq.Workplane("XY").add(sections).loft()

    # Mirror for full wing
    wing = wing_half.mirror("XZ")

    return wing
```

**Rejected alternatives for geometry engine:**
- **OpenCascade.js (WASM in browser)**: 15MB WASM bundle, cold-start latency, complex C++ API exposed through JS bindings. CadQuery wraps OCCT with a far more productive Python API.
- **Custom TypeScript geometry engine**: Produces faceted meshes, not B-rep solids. Cannot export proper STEP files. Would need to rewrite all the lofting/spline/boolean logic that CadQuery already provides.
- **JSCAD**: CSG-focused, no B-rep, no STEP, poor fit for smooth aerodynamic surfaces.
- **Build123d**: Viable CadQuery alternative with a more modern API. Could be substituted later with minimal architecture changes since it also uses OCCT. CadQuery chosen for its larger community and more documentation.

### 1.2 Frontend: **React 19 + TypeScript + Vite**

**Justification:**
- Largest ecosystem for 3D web applications (React Three Fiber, drei, etc.)
- TypeScript is essential for a parametric tool with hundreds of typed parameters, constraints, and interfaces
- Component model maps naturally to the panel-based UI (Global Parameters panel, Component Parameters panel, Viewport, Toolbar)
- Zustand (our state manager) is built by the React Three Fiber team (pmndrs) and integrates seamlessly
- Vite provides fast HMR during development

**Rejected alternatives:**
- **Svelte**: Smaller ecosystem for 3D; fewer CAD-oriented libraries
- **Vue**: Viable, but React Three Fiber gives us a significant head start for the 3D viewport

### 1.3 3D Viewport Rendering: **Three.js via React Three Fiber (R3F)**

The browser does **not** generate geometry. It only **renders** meshes received from the Python backend.

**Justification:**
- Three.js is the industry standard for web 3D rendering
- React Three Fiber provides declarative scene management integrated with React
- Built-in support for: raycasting (component selection/highlighting), loading external meshes (STL/glTF from backend), orbit/pan/zoom controls
- `@react-three/drei` provides ready-made helpers: `Html` overlays for dimension annotations, `Line` for construction lines, `OrbitControls`, `GizmoHelper`
- We load meshes from the backend as `BufferGeometry` (via glTF binary or raw vertex buffers over WebSocket)

**Data flow:**
```
Browser (param change) ──WebSocket──→ Python Backend
                                          │
                                    CadQuery generates
                                    B-rep solid
                                          │
                                    Tessellate to mesh
                                    (vertices + faces)
                                          │
Python Backend ──WebSocket──→ Browser receives mesh
                                          │
                                    Three.js renders
                                    BufferGeometry
```

### 1.4 State Management: **Zustand + Zundo (undo/redo) + Immer**

**Justification:**
- Zustand is minimal, fast, and TypeScript-first
- `subscribeWithSelector` middleware enables granular subscriptions: the viewport only re-renders when mesh data changes, not when UI state changes
- **Zundo** middleware provides time-travel undo/redo with minimal code
- **Immer** middleware enables immutable state updates with mutable syntax (critical for deeply nested aircraft parameter trees)
- Works outside React components (important for WebSocket message handlers)

```typescript
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { temporal } from 'zundo';
import { subscribeWithSelector } from 'zustand/middleware';

const useDesignStore = create<DesignState>()(
  subscribeWithSelector(
    temporal(
      immer((set) => ({
        aircraft: defaultAircraft,
        setWingSpan: (span: number) =>
          set((state) => { state.aircraft.wing.span = span; }),
      })),
      { limit: 100 }
    )
  )
);
```

### 1.5 UI Components: **Radix Primitives + Tailwind CSS + Custom Panels**

**Justification:**
- **Radix Primitives**: Unstyled, accessible primitives for dropdowns, sliders, tooltips, popovers. We need heavy customization for the dark CAD theme shown in mockups.
- **Tailwind CSS**: Utility-first CSS that enables rapid iteration on the dark theme.
- **Custom panel system**: The layout (viewport + right panel + bottom-left panel) is specific enough that we build it ourselves using CSS Grid.
- Numeric input fields with drag-to-adjust (like Blender/Figma) are custom components built on top of Radix's primitives.

### 1.6 Communication Layer: **HTTP REST + WebSocket**

| Channel | Protocol | Use |
|---------|----------|-----|
| Parameter updates | WebSocket | Real-time bidirectional: params out, mesh data back |
| Preview mesh | WebSocket | Binary mesh data (vertices/faces) for Three.js |
| Export (STL/STEP) | HTTP POST | Trigger export, return file download |
| Design save/load | HTTP POST/GET | JSON design file to/from local filesystem |
| Validation results | WebSocket | Pushed alongside mesh updates |
| Airfoil database | HTTP GET | Query/search airfoil profiles |

### 1.7 Build & Development Tooling

**Frontend:**

| Tool | Purpose |
|------|---------|
| **Vite** | Dev server + bundler (fast HMR, native ESM) |
| **Vitest** | Unit testing (Vite-native, fast) |
| **Biome** | Linting + formatting (faster than ESLint + Prettier) |
| **pnpm** | Package manager (fast, disk-efficient) |

**Backend:**

| Tool | Purpose |
|------|---------|
| **uv** | Python package manager (fast Rust-based pip replacement) |
| **pytest** | Unit testing for geometry generation |
| **Ruff** | Python linting + formatting |
| **mypy** | Type checking for Python |

**Packaging & Deployment:**

| Tool | Purpose |
|------|---------|
| **Docker** | Primary distribution: multi-stage Dockerfile (frontend build + Python runtime) |
| **docker-compose** | Local development: backend + frontend hot reload with volume mounts |
| **Google Cloud Run** | Cloud deployment target: `gcloud run deploy` or Cloud Build |
| **Artifact Registry** | Container image hosting for Cloud Run deployments |
| **PyInstaller** or **Nuitka** | Future: standalone executable for users without Docker |

### 1.8 Launch Workflow

```bash
# ── Development (docker-compose) ──────────────────────────
cd cheng/
docker compose up            # Backend (FastAPI + CadQuery) + Frontend (Vite dev server)
                             # Frontend hot-reloads, backend auto-restarts on code changes
                             # Opens at http://localhost:5173 (Vite proxy → backend:8000)

# ── Development (without Docker) ──────────────────────────
cd cheng/
uv run cheng serve --dev     # Starts FastAPI backend + opens Vite dev server proxy

# ── Production: Local Docker ──────────────────────────────
docker run -p 8000:8000 \
  -v ~/.cheng:/data \
  -e CHENG_MODE=local \
  cheng                      # Opens at http://localhost:8000
                             # Designs saved to ~/.cheng/designs/ on host

# ── Production: Cloud Run ─────────────────────────────────
gcloud run deploy cheng \
  --image gcr.io/PROJECT/cheng:latest \
  --memory 2Gi \
  --set-env-vars CHENG_MODE=cloud \
  --min-instances 0 \
  --max-instances 10         # Scale-to-zero, stateless, browser stores designs

# ── Production (pip install, no Docker) ───────────────────
pip install cheng
cheng serve                  # Starts bundled backend, serves built frontend
                             # Opens browser to http://localhost:8000
```

The FastAPI server serves both the API and the built frontend static files from a single process. The Docker image is the canonical distribution method.

---

## 2. Deployment Architecture

### 2.1 Dockerfile Design

The Docker image uses a **multi-stage build** to keep the final image small while supporting the full CadQuery + OpenCascade toolchain:

```dockerfile
# ── Stage 1: Frontend Build ──────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build
# Output: /app/frontend/dist/

# ── Stage 2: Python Runtime ──────────────────────────────
FROM python:3.11-slim AS runtime

# Install system dependencies for OpenCascade
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglu1-mesa libx11-6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (CadQuery + OpenCascade)
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from Stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist/

# Copy bundled data (airfoil database, templates)
COPY backend/data/ ./backend/data/

# Create data directory for local mode
RUN mkdir -p /data/designs

# Environment
ENV CHENG_MODE=local
ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "cheng.backend", "--host", "0.0.0.0", "--port", "8000"]
```

**Image details:**
- Base: `python:3.11-slim` (~150MB) -- chosen for CadQuery compatibility
- CadQuery + OpenCascade add ~400MB to the image
- Built frontend assets are ~2MB
- Airfoil database (bundled .dat files) adds ~1MB
- **Total image size: ~600MB**

### 2.2 Local Mode (`CHENG_MODE=local`)

```
┌─────────────────────────────────────────────────────────────────┐
│  HOST MACHINE                                                    │
│                                                                  │
│  ~/.cheng/                    Docker Container                   │
│  ├── designs/        ◄────── /data/designs/  (volume mount)     │
│  │   ├── trainer.cheng       Designs saved to local filesystem   │
│  │   └── glider.cheng                                           │
│  └── custom_airfoils/ ◄──── /data/custom_airfoils/              │
│                                                                  │
│  docker run -p 8000:8000 -v ~/.cheng:/data cheng                │
└─────────────────────────────────────────────────────────────────┘
```

- Volume mount: `-v ~/.cheng:/data` maps host directory to container `/data/`
- Designs are saved as `.cheng` JSON files to `/data/designs/`
- Custom airfoils stored in `/data/custom_airfoils/`
- Bundled airfoil database is read-only inside the image at `/app/backend/data/airfoils/`
- Full save/load/list API works against the mounted volume

### 2.3 Cloud Mode (`CHENG_MODE=cloud`)

```
┌───────────────────────┐          ┌────────────────────────────────┐
│  User's Browser       │          │  Google Cloud Run               │
│                       │  HTTPS   │                                 │
│  React + Three.js     │◄────────►│  FastAPI + CadQuery             │
│  Zustand Store        │          │  Stateless (no /data volume)    │
│  IndexedDB (designs)  │          │  CHENG_MODE=cloud               │
│                       │          │  Memory: 2Gi                    │
│  All design state     │          │  Scale: 0-10 instances          │
│  persisted locally    │          │                                 │
│  in browser storage   │          │  Same Docker image as local     │
└───────────────────────┘          └────────────────────────────────┘
```

**Key differences from local mode:**
- **No persistent storage on the server.** Cloud Run containers are ephemeral.
- **All design state lives in the browser**: Zustand store holds the working state; IndexedDB provides persistence across page reloads.
- Backend is a **pure function**: receives `AircraftDesign` JSON, returns mesh/STL/validation. No server-side sessions, no filesystem writes.
- **Save/load flow**: Frontend serializes design JSON directly to/from IndexedDB. The backend save/load endpoints are disabled in cloud mode; the frontend handles persistence entirely.
- **Export flow**: Backend generates STL/STEP/ZIP in memory and streams it as an HTTP response. No temp files on disk.

**Cloud Run configuration:**

| Setting | Value | Rationale |
|---------|-------|-----------|
| Memory | 2Gi | CadQuery + OpenCascade require ~800MB baseline; geometry generation uses additional memory per request |
| CPU | 2 | CadQuery operations are CPU-bound |
| Max instances | 10 | Cost control; each instance can handle concurrent requests |
| Min instances | 0 (default) or 1 | 0 = scale-to-zero (free when idle); 1 = warm container (~$15/month) |
| Concurrency | 4 | Multiple users per container; CadQuery operations are isolated per thread |
| Request timeout | 300s | Large exports (fine STL) can take time |

### 2.4 Environment Variable Configuration

| Variable | Default | Values | Description |
|----------|---------|--------|-------------|
| `CHENG_MODE` | `local` | `local`, `cloud` | Toggles storage backend and API behavior |
| `PORT` | `8000` | any | HTTP port (Cloud Run sets this automatically) |
| `CHENG_DATA_DIR` | `/data` | path | Data directory root for local mode |
| `CHENG_LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error` | Logging verbosity |
| `CHENG_WORKERS` | `1` | 1-4 | Uvicorn worker count (Cloud Run: 1; local: 1-2) |
| `CHENG_CORS_ORIGINS` | `*` | URL list | Allowed CORS origins (restrict in cloud) |

### 2.5 Cold Start Considerations

The OpenCascade kernel has a significant initialization cost:

| Phase | Time | Trigger |
|-------|------|---------|
| Container start | 1-2s | Docker/Cloud Run boots the container |
| Python + FastAPI init | 0.5-1s | Module imports, route registration |
| OpenCascade kernel load | 3-8s | First CadQuery operation loads the OCCT shared libraries |
| **Total cold start** | **5-11s** | First request after scale-from-zero |

**Mitigation strategies:**

1. **Warm container (`min-instances=1`)**: Keeps one Cloud Run instance always running. Eliminates cold starts at a cost of ~$15/month. Recommended for production.

2. **Lazy-load OpenCascade on first request**: The server starts accepting HTTP connections immediately. The first CadQuery operation triggers the OCCT load. The frontend shows a "Geometry engine loading..." indicator during this time.

3. **Eager preload at startup**: Import CadQuery and run a trivial operation during server startup (`lifespan` event). This moves the cold start cost to container boot time rather than first-request time, which is better for Cloud Run health checks.

```python
# backend/server.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload OpenCascade kernel during startup
    import cadquery as cq
    _ = cq.Workplane("XY").box(1, 1, 1)  # Forces OCCT initialization
    logger.info("OpenCascade kernel preloaded")
    yield

app = FastAPI(lifespan=lifespan)
```

4. **Frontend cold-start handling**: The frontend must handle a "backend not ready" state gracefully:

```typescript
// frontend/src/api/connection.ts

class BackendConnection {
  private retryCount = 0;
  private maxRetries = 10;

  async connectWithRetry(url: string) {
    while (this.retryCount < this.maxRetries) {
      try {
        await this.connect(url);
        this.retryCount = 0;
        return;
      } catch (e) {
        this.retryCount++;
        const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000);
        useDesignStore.getState().setBackendStatus('connecting');
        await sleep(delay);
      }
    }
    useDesignStore.getState().setBackendStatus('error');
  }
}
```

### 2.6 Thread-Safe CadQuery Operations

CadQuery/OpenCascade is **not thread-safe** at the global level. Each request must use an isolated OpenCascade context:

```python
# backend/geometry/runner.py
import anyio

async def generate_geometry_safe(design: AircraftDesign) -> GenerationResult:
    """Run CadQuery geometry generation in an isolated thread."""
    # anyio.to_thread.run_sync() runs the blocking function in a
    # separate thread from the anyio worker thread pool.
    # Each thread gets its own OpenCascade context.
    result = await anyio.to_thread.run_sync(
        lambda: _generate_geometry_blocking(design),
        cancellable=True,
    )
    return result

def _generate_geometry_blocking(design: AircraftDesign) -> GenerationResult:
    """Blocking CadQuery operations -- runs in a worker thread."""
    # All CadQuery objects created here are local to this thread.
    # No shared mutable state with other requests.
    import cadquery as cq

    wing_solid = generate_wing_solid(design.wing)
    fuselage_solid = generate_fuselage_solid(design.fuselage)
    tail_solid = generate_tail_solid(design.tail)
    # ... tessellate, validate, etc.
    return GenerationResult(...)
```

**Concurrency model:**
- Cloud Run may route multiple concurrent requests to one container (concurrency=4).
- Each CadQuery operation runs in its own thread via `anyio.to_thread.run_sync()`.
- No shared mutable state between requests. Each request creates fresh CadQuery `Workplane` objects.
- Thread pool size is bounded by the `CHENG_WORKERS` setting and anyio's default thread pool.

### 2.7 Docker Compose for Local Development

```yaml
# docker-compose.yml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app/backend          # Hot reload backend code
      - cheng-data:/data                # Persistent design storage
    environment:
      - CHENG_MODE=local
      - CHENG_LOG_LEVEL=debug
    command: >
      uvicorn cheng.backend.server:app
      --host 0.0.0.0 --port 8000 --reload
      --reload-dir /app/backend

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src         # Hot reload frontend code
    environment:
      - VITE_BACKEND_URL=http://backend:8000

volumes:
  cheng-data:
```

### 2.8 Cloud Run Deployment

```bash
# Build and push image to Artifact Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/cheng:latest .

# Deploy to Cloud Run
gcloud run deploy cheng \
  --image gcr.io/PROJECT_ID/cheng:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 4 \
  --timeout 300 \
  --set-env-vars "CHENG_MODE=cloud,CHENG_LOG_LEVEL=info" \
  --min-instances 0 \
  --max-instances 10 \
  --allow-unauthenticated
```

---

## 3. Data Model / Schema

### 3.1 Design Philosophy

The data model is **shared between frontend and backend** as a single source of truth:
1. **TypeScript interfaces** define the shapes for the frontend (UI, state management)
2. **Pydantic models** define the same shapes for the backend (validation, CadQuery input)
3. The JSON wire format is identical -- both sides serialize/deserialize the same schema
4. **Serializable**: Every piece of design state can be serialized to JSON
5. **Defaulted**: Every parameter has a sensible default; a new design is immediately valid
6. **Constrained**: Every numeric parameter has min/max bounds and a unit
7. **Hierarchical**: Aircraft > Components > Sub-components > Parameters
8. **ID-addressed**: Every component has a unique ID for selection, referencing, and undo/redo

### 3.2 Pydantic Models (Python - Backend, Source of Truth)

The Python Pydantic models are the **canonical schema**. TypeScript interfaces are generated from them (or manually kept in sync during MVP).

```python
# ============================================================
# backend/models/aircraft.py
# ============================================================
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

# ── Units ──────────────────────────────────────────────────
# All dimensions stored in millimeters internally.
# Display can be converted to mm, cm, in.

# ── Airfoil ────────────────────────────────────────────────

class AirfoilSource(str, Enum):
    NACA4 = "naca4"
    NACA5 = "naca5"
    DAT_FILE = "dat-file"
    CUSTOM = "custom"

class AirfoilProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                           # e.g., "NACA 2412", "Clark Y"
    source: AirfoilSource

    naca_digits: Optional[str] = None   # e.g., "2412"
    coordinates: Optional[list[tuple[float, float]]] = None  # (x, y) pairs

    max_thickness_percent: Optional[float] = None
    max_camber_percent: Optional[float] = None
    max_camber_position: Optional[float] = None

# ── Fuselage ───────────────────────────────────────────────

class FuselageType(str, Enum):
    POD = "pod"
    CONVENTIONAL = "conventional"
    FLYING_WING = "flying-wing"
    BLENDED_WING = "blended-wing"

class NoseShape(str, Enum):
    OGIVE = "ogive"
    ROUNDED = "rounded"
    FLAT = "flat"
    POINTED = "pointed"

class TailShape(str, Enum):
    TAPERED = "tapered"
    BLUNT = "blunt"
    UPSWEPT = "upswept"

class WingMounting(str, Enum):
    HIGH = "high"
    MID = "mid"
    LOW = "low"
    SHOULDER = "shoulder"

class FuselageCrossSection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    station_position: float = Field(ge=0.0, le=1.0)  # 0=nose, 1=tail
    width: float = Field(ge=20, le=500)               # mm
    height: float = Field(ge=20, le=500)               # mm
    corner_radius: float = Field(ge=0, le=250)         # mm
    rotation: float = Field(ge=-180, le=180, default=0) # degrees

class Fuselage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: FuselageType = FuselageType.CONVENTIONAL
    length: float = Field(ge=200, le=5000, default=800)             # mm
    cross_sections: list[FuselageCrossSection] = Field(default_factory=list)

    nose_length: float = Field(ge=10, le=2000, default=100)         # mm
    nose_shape: NoseShape = NoseShape.OGIVE
    tail_length: float = Field(ge=10, le=2000, default=150)         # mm
    tail_shape: TailShape = TailShape.TAPERED

    wing_position: float = Field(ge=0.15, le=0.50, default=0.25)   # ratio
    wing_mounting: WingMounting = WingMounting.HIGH

    wall_thickness: float = Field(ge=0.8, le=10, default=1.6)      # mm (FDM: >= 2 perimeters)

# ── Wing ───────────────────────────────────────────────────

class WingSection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    span_position: float = Field(ge=0.0, le=1.0)       # 0=root, 1=tip
    chord: float = Field(ge=30, le=2000, default=200)   # mm
    airfoil: str = "naca-2412"                           # airfoil ID
    twist: float = Field(ge=-10, le=10, default=0)      # degrees
    sweep_angle: float = Field(ge=-45, le=60, default=0) # degrees
    dihedral_angle: float = Field(ge=-15, le=45, default=3) # degrees

class ControlSurfaceType(str, Enum):
    AILERON = "aileron"
    FLAP = "flap"
    FLAPERON = "flaperon"
    SPOILER = "spoiler"
    ELEVON = "elevon"

class HingeLineType(str, Enum):
    STRAIGHT = "straight"
    TAPERED = "tapered"

class ControlSurface(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: ControlSurfaceType
    parent_id: str

    span_start: float = Field(ge=0.0, le=1.0)
    span_end: float = Field(ge=0.0, le=1.0)
    chord_ratio: float = Field(ge=0.15, le=0.45, default=0.25)

    max_deflection_up: float = Field(ge=0, le=45, default=25)      # degrees
    max_deflection_down: float = Field(ge=0, le=45, default=20)    # degrees
    hinge_line: HingeLineType = HingeLineType.STRAIGHT

class Wing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    span: float = Field(ge=300, le=10000, default=1500)             # mm
    sections: list[WingSection] = Field(default_factory=list)       # min 2
    control_surfaces: list[ControlSurface] = Field(default_factory=list)
    incidence: float = Field(ge=-5, le=10, default=2)               # degrees
    symmetric: bool = True

# ── Tail ───────────────────────────────────────────────────

class TailType(str, Enum):
    CONVENTIONAL = "conventional"
    T_TAIL = "T-tail"
    V_TAIL = "V-tail"
    CRUCIFORM = "cruciform"
    H_TAIL = "H-tail"
    INVERTED_V = "inverted-V"
    NONE = "flying-wing-none"

class HorizontalStabilizer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    span: float = Field(ge=100, le=5000, default=400)
    root_chord: float = Field(ge=30, le=1000, default=130)
    tip_chord: float = Field(ge=20, le=1000, default=90)
    airfoil: str = "naca-0009"
    sweep_angle: float = Field(ge=-15, le=45, default=5)
    dihedral_angle: float = Field(ge=-10, le=10, default=0)
    incidence: float = Field(ge=-10, le=5, default=-1)
    elevator: Optional[ControlSurface] = None

class VerticalStabilizer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    height: float = Field(ge=50, le=3000, default=150)
    root_chord: float = Field(ge=30, le=1000, default=140)
    tip_chord: float = Field(ge=20, le=1000, default=80)
    airfoil: str = "naca-0009"
    sweep_angle: float = Field(ge=-10, le=60, default=25)
    cant_angle: float = Field(ge=0, le=60, default=0)
    rudder: Optional[ControlSurface] = None

class VTailSurfaces(BaseModel):
    left: VerticalStabilizer
    right: VerticalStabilizer

class TailGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: TailType = TailType.CONVENTIONAL
    moment_arm: float = Field(ge=200, le=5000, default=550)         # mm

    horizontal_stabilizer: Optional[HorizontalStabilizer] = None
    vertical_stabilizer: Optional[VerticalStabilizer] = None
    v_tail_surfaces: Optional[VTailSurfaces] = None
    v_tail_dihedral: Optional[float] = Field(ge=20, le=60, default=35)

# ── Propulsion ─────────────────────────────────────────────

class EngineType(str, Enum):
    ELECTRIC_PUSHER = "electric-pusher"
    ELECTRIC_TRACTOR = "electric-tractor"
    ELECTRIC_TWIN = "electric-twin"
    NONE = "none"

class Motor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "2212 1400KV"
    kv: float = Field(ge=100, le=5000, default=1400)
    weight: float = Field(ge=5, le=2000, default=52)           # grams
    max_watts: float = Field(ge=10, le=10000, default=250)
    shaft_diameter: float = Field(ge=1, le=10, default=3.17)   # mm

class Propeller(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    diameter: float = Field(ge=50, le=1000, default=229)       # mm
    pitch: float = Field(ge=30, le=500, default=114)           # mm
    blades: int = Field(ge=2, le=4, default=2)

class EngineMount(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    position_x: float = 0    # mm (longitudinal)
    position_y: float = 0    # mm (vertical)
    position_z: float = 0    # mm (lateral)
    thrust_angle: float = Field(ge=0, le=10, default=2)       # downthrust degrees
    side_angle: float = Field(ge=-5, le=5, default=0)         # sidethrust degrees

class Propulsion(BaseModel):
    type: EngineType = EngineType.ELECTRIC_TRACTOR
    count: int = Field(ge=0, le=4, default=1)
    motors: list[Motor] = Field(default_factory=list)
    propellers: list[Propeller] = Field(default_factory=list)
    mounts: list[EngineMount] = Field(default_factory=list)

# ── Landing Gear ───────────────────────────────────────────

class LandingGearType(str, Enum):
    TRICYCLE = "tricycle"
    TAILDRAGGER = "taildragger"
    BELLY = "belly"
    NONE = "none"

class StrutType(str, Enum):
    WIRE = "wire"
    LEAF_SPRING = "leaf-spring"
    OLEO = "oleo"
    FIXED = "fixed"

class LandingGear(BaseModel):
    type: LandingGearType = LandingGearType.BELLY
    main_wheel_diameter: float = Field(ge=10, le=200, default=55)
    main_wheel_width: float = Field(ge=5, le=60, default=18)
    main_gear_span: float = Field(ge=50, le=8000, default=180)
    aux_wheel_diameter: Optional[float] = Field(ge=5, le=100, default=30)
    strut_height: float = Field(ge=20, le=300, default=80)
    strut_type: StrutType = StrutType.WIRE

# ── 3D Printing Parameters ────────────────────────────────

class PrintSettings(BaseModel):
    """Parameters specific to FDM 3D printing."""
    nozzle_diameter: float = Field(ge=0.2, le=1.0, default=0.4)    # mm
    layer_height: float = Field(ge=0.1, le=0.6, default=0.2)       # mm
    min_wall_thickness: float = Field(ge=0.4, le=5.0, default=1.2) # mm (3 perimeters @ 0.4)
    infill_percent: float = Field(ge=0, le=100, default=10)         # %

    # Print bed constraints for part sectioning
    bed_size_x: float = Field(ge=100, le=1000, default=220)        # mm (e.g., Ender 3)
    bed_size_y: float = Field(ge=100, le=1000, default=220)        # mm
    bed_size_z: float = Field(ge=50, le=500, default=250)          # mm

    # Assembly features
    joint_type: str = Field(default="tab-slot")                     # tab-slot, dowel, tongue-groove
    joint_clearance: float = Field(ge=0.05, le=1.0, default=0.2)   # mm (printer tolerance)
    spar_channel_diameter: float = Field(ge=0, le=20, default=6)   # mm (for carbon rod spar)

# ── Aircraft Design (Root) ─────────────────────────────────

class AircraftDesign(BaseModel):
    """Root model for a complete aircraft design."""
    version: str = "1.0.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Untitled Aircraft"
    created_at: str = ""
    modified_at: str = ""
    description: str = ""
    display_units: str = Field(default="mm", pattern="^(mm|cm|in)$")

    fuselage: Fuselage = Field(default_factory=Fuselage)
    wing: Wing = Field(default_factory=Wing)
    tail: TailGroup = Field(default_factory=TailGroup)
    propulsion: Propulsion = Field(default_factory=Propulsion)
    landing_gear: LandingGear = Field(default_factory=LandingGear)
    print_settings: PrintSettings = Field(default_factory=PrintSettings)
```

### 3.3 TypeScript Interfaces (Frontend - Mirror of Pydantic)

```typescript
// ============================================================
// frontend/src/models/aircraft.ts
// ============================================================

// These interfaces mirror the Python Pydantic models exactly.
// Field names use camelCase (JS convention); the API layer
// converts to/from snake_case automatically.

type Millimeters = number;
type Degrees = number;
type Ratio = number;

type ComponentId = string;
type AirfoilId = string;

type ComponentType =
  | 'fuselage' | 'wing' | 'wing-section'
  | 'horizontal-stabilizer' | 'vertical-stabilizer'
  | 'control-surface' | 'engine-mount' | 'landing-gear';

// Airfoil
interface AirfoilProfile {
  id: AirfoilId;
  name: string;
  source: 'naca4' | 'naca5' | 'dat-file' | 'custom';
  nacaDigits?: string;
  coordinates?: [number, number][];
  maxThicknessPercent?: number;
  maxCamberPercent?: number;
  maxCamberPosition?: number;
}

// Fuselage
type FuselageType = 'pod' | 'conventional' | 'flying-wing' | 'blended-wing';

interface FuselageCrossSection {
  id: ComponentId;
  stationPosition: Ratio;
  width: Millimeters;
  height: Millimeters;
  cornerRadius: Millimeters;
  rotation: Degrees;
}

interface Fuselage {
  id: ComponentId;
  type: FuselageType;
  length: Millimeters;
  crossSections: FuselageCrossSection[];
  noseLength: Millimeters;
  noseShape: 'ogive' | 'rounded' | 'flat' | 'pointed';
  tailLength: Millimeters;
  tailShape: 'tapered' | 'blunt' | 'upswept';
  wingPosition: Ratio;
  wingMounting: 'high' | 'mid' | 'low' | 'shoulder';
  wallThickness: Millimeters;
}

// Wing
interface WingSection {
  id: ComponentId;
  spanPosition: Ratio;
  chord: Millimeters;
  airfoil: AirfoilId;
  twist: Degrees;
  sweepAngle: Degrees;
  dihedralAngle: Degrees;
}

interface ControlSurface {
  id: ComponentId;
  type: 'aileron' | 'flap' | 'flaperon' | 'spoiler' | 'elevon';
  parentId: ComponentId;
  spanStart: Ratio;
  spanEnd: Ratio;
  chordRatio: Ratio;
  maxDeflectionUp: Degrees;
  maxDeflectionDown: Degrees;
  hingeLine: 'straight' | 'tapered';
}

interface Wing {
  id: ComponentId;
  span: Millimeters;
  sections: WingSection[];
  controlSurfaces: ControlSurface[];
  incidence: Degrees;
  symmetric: boolean;
}

// Tail
type TailType = 'conventional' | 'T-tail' | 'V-tail' | 'cruciform'
  | 'H-tail' | 'inverted-V' | 'flying-wing-none';

interface HorizontalStabilizer {
  id: ComponentId;
  span: Millimeters;
  rootChord: Millimeters;
  tipChord: Millimeters;
  airfoil: AirfoilId;
  sweepAngle: Degrees;
  dihedralAngle: Degrees;
  incidence: Degrees;
  elevator?: ControlSurface;
}

interface VerticalStabilizer {
  id: ComponentId;
  height: Millimeters;
  rootChord: Millimeters;
  tipChord: Millimeters;
  airfoil: AirfoilId;
  sweepAngle: Degrees;
  cantAngle: Degrees;
  rudder?: ControlSurface;
}

interface TailGroup {
  id: ComponentId;
  type: TailType;
  momentArm: Millimeters;
  horizontalStabilizer?: HorizontalStabilizer;
  verticalStabilizer?: VerticalStabilizer;
  vTailSurfaces?: { left: VerticalStabilizer; right: VerticalStabilizer };
  vTailDihedral?: Degrees;
}

// Propulsion
type EngineType = 'electric-pusher' | 'electric-tractor' | 'electric-twin' | 'none';

interface Motor {
  id: ComponentId;
  name: string;
  kv: number;
  weight: number;
  maxWatts: number;
  shaftDiameter: Millimeters;
}

interface Propeller {
  id: ComponentId;
  diameter: Millimeters;
  pitch: Millimeters;
  blades: number;
}

interface EngineMount {
  id: ComponentId;
  positionX: Millimeters;
  positionY: Millimeters;
  positionZ: Millimeters;
  thrustAngle: Degrees;
  sideAngle: Degrees;
}

interface Propulsion {
  type: EngineType;
  count: number;
  motors: Motor[];
  propellers: Propeller[];
  mounts: EngineMount[];
}

// Landing Gear
type LandingGearType = 'tricycle' | 'taildragger' | 'belly' | 'none';

interface LandingGear {
  type: LandingGearType;
  mainWheelDiameter: Millimeters;
  mainWheelWidth: Millimeters;
  mainGearSpan: Millimeters;
  auxWheelDiameter?: Millimeters;
  strutHeight: Millimeters;
  strutType: 'wire' | 'leaf-spring' | 'oleo' | 'fixed';
}

// 3D Print Settings
interface PrintSettings {
  nozzleDiameter: Millimeters;
  layerHeight: Millimeters;
  minWallThickness: Millimeters;
  infillPercent: number;
  bedSizeX: Millimeters;
  bedSizeY: Millimeters;
  bedSizeZ: Millimeters;
  jointType: 'tab-slot' | 'dowel' | 'tongue-groove';
  jointClearance: Millimeters;
  sparChannelDiameter: Millimeters;
}

// Aircraft Design (Root)
interface AircraftDesign {
  version: string;
  id: string;
  name: string;
  createdAt: string;
  modifiedAt: string;
  description: string;
  displayUnits: 'mm' | 'cm' | 'in';
  fuselage: Fuselage;
  wing: Wing;
  tail: TailGroup;
  propulsion: Propulsion;
  landingGear: LandingGear;
  printSettings: PrintSettings;
}

// Computed / Derived Values (calculated by backend, sent to frontend)
interface DerivedValues {
  wingArea: number;                   // mm^2
  wingAspectRatio: number;
  wingMeanAerodynamicChord: number;   // mm
  wingTaperRatio: number;
  tailArea: number;                   // mm^2
  horizontalTailVolumeCoefficient: number;
  verticalTailVolumeCoefficient: number;
  estimatedEmptyWeight: number;       // grams
  estimatedCGPosition: { x: number; y: number; z: number };
  cgRangeForward: number;
  cgRangeAft: number;
  wingLoading: number;                // g/dm^2
  reynoldsNumber: number;
  stallSpeed: number;                 // m/s
  // 3D print specific
  estimatedFilamentWeight: number;    // grams
  estimatedPrintTime: number;         // hours
  partCount: number;                  // number of sections needed
  longestPart: number;                // mm (must fit in print bed)
}

interface ValidationMessage {
  severity: 'error' | 'warning' | 'info';
  component: ComponentId;
  parameter: string;
  message: string;
  suggestion?: string;
}
```

### 3.4 Parameter Constraints Table (Key Parameters)

| Component | Parameter | Min | Max | Default | Unit | Step |
|-----------|-----------|-----|-----|---------|------|------|
| Wing | span | 300 | 10000 | 1500 | mm | 10 |
| Wing | incidence | -5 | 10 | 2 | deg | 0.5 |
| WingSection | chord | 30 | 2000 | 200 | mm | 5 |
| WingSection | twist | -10 | 10 | 0 | deg | 0.5 |
| WingSection | sweepAngle | -45 | 60 | 0 | deg | 1 |
| WingSection | dihedralAngle | -15 | 45 | 3 | deg | 1 |
| Fuselage | length | 200 | 5000 | 800 | mm | 10 |
| Fuselage | wallThickness | 0.8 | 10 | 1.6 | mm | 0.1 |
| Fuselage | wingPosition | 0.15 | 0.50 | 0.25 | ratio | 0.01 |
| HStab | span | 100 | 5000 | 400 | mm | 10 |
| HStab | incidence | -10 | 5 | -1 | deg | 0.5 |
| VStab | height | 50 | 3000 | 150 | mm | 5 |
| TailGroup | vTailDihedral | 20 | 60 | 35 | deg | 1 |
| ControlSurface | chordRatio | 0.15 | 0.45 | 0.25 | ratio | 0.01 |
| Propeller | diameter | 50 | 1000 | 250 | mm | 10 |
| PrintSettings | bedSizeX | 100 | 1000 | 220 | mm | 10 |
| PrintSettings | bedSizeY | 100 | 1000 | 220 | mm | 10 |
| PrintSettings | bedSizeZ | 50 | 500 | 250 | mm | 10 |
| PrintSettings | wallThickness | 0.4 | 5.0 | 1.2 | mm | 0.1 |
| PrintSettings | jointClearance | 0.05 | 1.0 | 0.2 | mm | 0.05 |
| PrintSettings | sparChannelDiameter | 0 | 20 | 6 | mm | 0.5 |

---

## 4. Parameter Dependency Graph

### 4.1 Dependency Map

Parameters are not independent. Changing one parameter can invalidate or require recalculation of others.

```
Wingspan change
  ├─→ Wing area (recalculate)
  ├─→ Aspect ratio (recalculate)
  ├─→ Wing loading (recalculate)
  ├─→ Aileron span limits (re-clamp)
  ├─→ Landing gear span limits (re-clamp)
  ├─→ MAC position (recalculate)
  ├─→ CG estimate (recalculate)
  ├─→ Stall speed estimate (recalculate)
  ├─→ Wing section count for printing (recalculate)
  └─→ Part sectioning planes (recalculate)

Wing chord change (root or tip)
  ├─→ Taper ratio (recalculate)
  ├─→ Wing area (recalculate)
  ├─→ MAC (recalculate)
  ├─→ Reynolds number estimate (recalculate)
  ├─→ Control surface absolute size (recalculate)
  └─→ CG estimate (recalculate)

Fuselage length change
  ├─→ Tail moment arm limits (re-clamp)
  ├─→ CG range (recalculate)
  ├─→ Nose/tail fairing length limits (re-clamp)
  ├─→ Estimated weight (recalculate)
  └─→ Fuselage section count for printing (recalculate)

Tail type change (e.g., conventional → V-tail)
  ├─→ Completely swap TailGroup sub-structure
  ├─→ Remove horizontal + vertical stabilizers
  ├─→ Create V-tail surfaces with defaults
  ├─→ Recalculate tail volume coefficients
  └─→ Recalculate CG estimate

Fuselage type change
  ├─→ Reset cross-section array to type defaults
  ├─→ Recalculate fuselage volume/weight
  └─→ May invalidate wing mounting options

Engine count change
  ├─→ Add/remove motor + mount entries
  ├─→ Recalculate weight estimate
  └─→ Recalculate CG estimate

Print bed size change
  ├─→ Recalculate part sectioning for wing
  ├─→ Recalculate part sectioning for fuselage
  ├─→ Recalculate joint/connector placements
  └─→ Update part count and longest part estimates

Wall thickness change
  ├─→ Recalculate estimated print weight
  ├─→ Recalculate structural validation
  └─→ Re-shell all hollow components
```

### 4.2 Change Propagation Strategy: **Backend-Computed Derived State**

Unlike a browser-only app, our derived values are computed **on the backend** as part of geometry regeneration. The flow is:

```
Frontend: User changes parameter
    │
    ▼
Frontend: Update Zustand store immediately (optimistic UI)
    │
    ▼
Frontend: Send updated AircraftDesign JSON via WebSocket
    │
    ▼
Backend: Validate + clamp parameters (Pydantic)
    │
    ▼
Backend: Compute derived values (wing area, CG, etc.)
    │
    ▼
Backend: Generate geometry via CadQuery
    │
    ▼
Backend: Tessellate to preview mesh
    │
    ▼
Backend: Send response via WebSocket:
         { mesh: <binary>, derived: {...}, validation: [...] }
    │
    ▼
Frontend: Update Three.js viewport with new mesh
Frontend: Update derived values display
Frontend: Update validation messages
```

**Why compute on backend?**
- CadQuery needs the full parameter set to generate geometry anyway
- Derived values like CG position, wing area, part count depend on the actual B-rep geometry (surface area, volume, sectioning)
- Single source of truth: derived values and geometry are always consistent
- Avoids duplicating math between Python and TypeScript

### 4.3 Constraint Clamping

When a parent parameter changes, dependent parameter limits may shrink and current values may become out-of-range. This is handled on the backend via Pydantic validators:

```python
from pydantic import model_validator

class AircraftDesign(BaseModel):
    # ... fields ...

    @model_validator(mode='after')
    def clamp_dependent_params(self) -> 'AircraftDesign':
        """Post-validation: clamp parameters whose limits depend on other params."""
        # Nose/tail length can't exceed 40% of fuselage
        max_nose = self.fuselage.length * 0.4
        self.fuselage.nose_length = min(self.fuselage.nose_length, max_nose)

        max_tail = self.fuselage.length * 0.4
        self.fuselage.tail_length = min(self.fuselage.tail_length, max_tail)

        # Landing gear span can't exceed 80% of wing span
        max_gear = self.wing.span * 0.8
        self.landing_gear.main_gear_span = min(
            self.landing_gear.main_gear_span, max_gear
        )

        # Wall thickness must be >= printer's min wall thickness
        min_wall = self.print_settings.min_wall_thickness
        self.fuselage.wall_thickness = max(self.fuselage.wall_thickness, min_wall)

        # Control surface spanEnd > spanStart
        for cs in self.wing.control_surfaces:
            cs.span_end = max(cs.span_end, cs.span_start + 0.05)

        return self
```

---

## 5. Geometry Generation Pipeline

### 5.1 Pipeline Overview

```
AircraftDesign (JSON)
    │
    ▼
Python Backend (FastAPI)
    │
    ├─→ Airfoil Profile Generation (NACA formula / DAT file lookup)
    │       produces: list of (x,y) coordinate tuples
    │
    ├─→ Wing Generation (CadQuery loft between spline sections)
    │       produces: cq.Workplane solid
    │
    ├─→ Fuselage Generation (CadQuery loft between cross-sections)
    │       produces: cq.Workplane solid
    │
    ├─→ Tail Generation (reuses wing pipeline with config switch)
    │       produces: cq.Workplane solid
    │
    ├─→ Part Sectioning (split solids at print-bed boundaries)
    │       produces: list of cq.Workplane solids with joints
    │
    ├─→ Assembly Composition (position all components)
    │       produces: cq.Assembly
    │
    ├─→ Tessellation for Preview (low tolerance → triangle mesh)
    │       produces: vertices + faces arrays
    │
    └─→ Tessellation for Export (high tolerance → STL file)
            produces: binary STL bytes
```

### 5.2 Airfoil Profile Generation

Airfoil profiles are the foundation of all lifting surfaces. Generated in Python and used as CadQuery spline inputs.

```python
import math
from typing import list

def generate_naca4(digits: str, num_points: int = 80) -> list[tuple[float, float]]:
    """Generate NACA 4-digit airfoil coordinates (Selig format)."""
    m = int(digits[0]) / 100     # max camber
    p = int(digits[1]) / 10      # max camber position
    t = int(digits[2:]) / 100    # thickness

    upper = []
    lower = []

    for i in range(num_points + 1):
        beta = i / num_points * math.pi
        x = (1 - math.cos(beta)) / 2  # cosine spacing

        # Thickness distribution
        yt = 5 * t * (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )

        # Camber line
        if p == 0:
            yc = 0.0
            dyc = 0.0
        elif x < p:
            yc = (m / p**2) * (2 * p * x - x**2)
            dyc = (2 * m / p**2) * (p - x)
        else:
            yc = (m / (1 - p)**2) * ((1 - 2*p) + 2*p*x - x**2)
            dyc = (2 * m / (1 - p)**2) * (p - x)

        theta = math.atan2(dyc, 1)
        upper.append((x - yt * math.sin(theta), yc + yt * math.cos(theta)))
        lower.append((x + yt * math.sin(theta), yc - yt * math.cos(theta)))

    # Selig format: upper TE→LE, then lower LE→TE
    coords = list(reversed(upper)) + lower[1:]  # avoid duplicate LE point
    return coords


def scale_airfoil(
    coords: list[tuple[float, float]],
    chord: float,
    twist_deg: float = 0,
) -> list[tuple[float, float]]:
    """Scale normalized coords by chord and apply twist around quarter-chord."""
    twist_rad = math.radians(twist_deg)
    qc = chord * 0.25
    result = []
    for x, y in coords:
        # Scale
        sx = x * chord
        sy = y * chord
        # Twist around quarter-chord
        dx = sx - qc
        rx = dx * math.cos(twist_rad) - sy * math.sin(twist_rad) + qc
        ry = dx * math.sin(twist_rad) + sy * math.cos(twist_rad)
        result.append((rx, ry))
    return result
```

### 5.3 Wing Geometry Generation (CadQuery)

```python
import cadquery as cq
from models.aircraft import Wing, WingSection

def generate_wing_solid(wing: Wing) -> cq.Workplane:
    """Generate a wing solid by lofting between airfoil spline sections."""
    half_span = wing.span / 2
    wires = []

    for section in wing.sections:
        # Get airfoil coordinates and scale
        coords = get_airfoil_coords(section.airfoil)
        scaled = scale_airfoil(coords, section.chord, section.twist)

        # Calculate spanwise position with sweep and dihedral
        y_offset = section.span_position * half_span
        sweep_offset = y_offset * math.tan(math.radians(section.sweep_angle))
        dihedral_z = y_offset * math.sin(math.radians(section.dihedral_angle))
        span_y = y_offset * math.cos(math.radians(section.dihedral_angle))

        # Create a workplane at the section's spanwise position
        # XZ plane = airfoil profile plane, Y = spanwise axis
        wp = cq.Workplane("XZ").transformed(
            offset=cq.Vector(sweep_offset, span_y, dihedral_z)
        )

        # Create spline wire from airfoil coordinates
        wire = wp.spline(scaled, close=True)
        wires.append(wire.val())

    # Loft between all section wires
    wing_half = cq.Workplane("XY").add(wires).loft()

    # Shell to make hollow (for weight savings in 3D printing)
    # Only if wall thickness > 0
    if wing.parent_design.print_settings.min_wall_thickness > 0:
        wing_half = wing_half.shell(-wing.parent_design.fuselage.wall_thickness)

    # Mirror for the other half (if symmetric)
    if wing.symmetric:
        mirrored = wing_half.mirror("XZ")
        wing_full = wing_half.union(mirrored)
        return wing_full

    return wing_half


def section_wing_for_printing(
    wing_solid: cq.Workplane,
    wing: Wing,
    bed_size_y: float,
) -> list[cq.Workplane]:
    """Split wing into sections that fit the print bed."""
    half_span = wing.span / 2
    section_length = bed_size_y - 20  # leave margin for joints
    num_sections = math.ceil(half_span / section_length)

    sections = []
    for i in range(num_sections):
        y_start = i * section_length
        y_end = min((i + 1) * section_length, half_span)

        # Cut section using two planes
        section = (
            wing_solid
            .cut(cq.Workplane("XZ").transformed(offset=(0, 0, 0))
                 .box(10000, 10000, y_start * 2, centered=(True, True, False))
                 .translate((0, -5000, -y_start)))
        )
        # ... additional cutting logic for clean sections

        # Add joint features (tab-slot or dowel holes)
        section = add_joint_features(section, wing, i, num_sections)
        sections.append(section)

    return sections
```

### 5.4 Fuselage Geometry Generation (CadQuery)

```python
def generate_fuselage_solid(fuselage: Fuselage) -> cq.Workplane:
    """Generate fuselage by lofting between cross-section profiles."""
    wires = []

    for cs in fuselage.cross_sections:
        x_pos = cs.station_position * fuselage.length

        # Create cross-section as a rounded rectangle (superellipse)
        wp = cq.Workplane("YZ").transformed(offset=cq.Vector(x_pos, 0, 0))

        if cs.corner_radius > 0:
            wire = (
                wp
                .rect(cs.width, cs.height)
                .val()
            )
            # Apply fillet to corners
            wire = wp.rect(cs.width, cs.height).vertices().fillet(cs.corner_radius)
        else:
            wire = wp.ellipse(cs.width / 2, cs.height / 2)

        wires.append(wire.val())

    # Loft between all cross-sections
    fuselage_solid = cq.Workplane("XY").add(wires).loft()

    # Shell to make hollow (wall_thickness)
    fuselage_solid = fuselage_solid.shell(-fuselage.wall_thickness)

    return fuselage_solid
```

### 5.5 Tail Geometry Generation

Tail surfaces reuse the wing generation pipeline with different parameters:
- **Conventional**: One horizontal stabilizer (lofted like a small wing) + one vertical stabilizer (wing on the YZ plane instead of XZ)
- **T-tail**: Vertical stabilizer solid; horizontal stabilizer positioned at its top
- **V-tail**: Two wing-like surfaces canted outward at `vTailDihedral` angle
- **H-tail**: Horizontal stabilizer with two vertical surfaces at its tips

### 5.6 Control Surface Cutouts (CadQuery Boolean Operations)

```python
def cut_control_surface(
    wing_solid: cq.Workplane,
    cs: ControlSurface,
    wing: Wing,
) -> tuple[cq.Workplane, cq.Workplane]:
    """Cut a control surface out of the wing and return both pieces."""
    half_span = wing.span / 2

    # Define the cut region
    y_start = cs.span_start * half_span
    y_end = cs.span_end * half_span

    # The cut is at chord_ratio from trailing edge
    # Create a cutting box from the hinge line to the trailing edge
    # This is a simplified approach; the actual implementation would
    # follow the chord distribution along the span

    cut_tool = create_cs_cut_tool(wing, cs)
    fixed_wing = wing_solid.cut(cut_tool)
    control_surface = wing_solid.intersect(cut_tool)

    # Add hinge gap (small offset between surfaces)
    control_surface = control_surface.translate((0.5, 0, 0))  # 0.5mm gap

    return fixed_wing, control_surface
```

### 5.7 3D Print Assembly Features (CadQuery)

This is a critical differentiator for the 3D-print-focused architecture.

```python
def add_tab_slot_joint(
    part_a: cq.Workplane,
    part_b: cq.Workplane,
    joint_plane_y: float,
    clearance: float = 0.2,
    tab_width: float = 10,
    tab_depth: float = 5,
) -> tuple[cq.Workplane, cq.Workplane]:
    """Add interlocking tab-slot features at the joint plane."""
    # Tab on part_a
    tab = (
        cq.Workplane("XZ")
        .transformed(offset=(0, joint_plane_y, 0))
        .rect(tab_width, tab_depth)
        .extrude(tab_depth)
    )
    part_a = part_a.union(tab)

    # Matching slot on part_b (with clearance)
    slot = (
        cq.Workplane("XZ")
        .transformed(offset=(0, joint_plane_y, 0))
        .rect(tab_width + clearance, tab_depth + clearance)
        .extrude(tab_depth + clearance)
    )
    part_b = part_b.cut(slot)

    return part_a, part_b


def add_spar_channel(
    wing_section: cq.Workplane,
    spar_diameter: float,
    spar_position_chord_ratio: float = 0.25,
) -> cq.Workplane:
    """Cut a channel through the wing section for a carbon fiber spar."""
    if spar_diameter <= 0:
        return wing_section

    # Cut a cylindrical channel along the span at the spar position
    channel = (
        cq.Workplane("XZ")
        .circle(spar_diameter / 2)
        .extrude(10000)  # through entire span
    )
    return wing_section.cut(channel)
```

### 5.8 Mesh Tessellation for Preview

CadQuery uses OpenCascade's tessellation engine. We send the resulting triangle mesh to the browser:

```python
from OCP.StlAPI import StlAPI_Writer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
import numpy as np

def tessellate_for_preview(
    solid: cq.Workplane,
    angular_tolerance: float = 0.5,   # radians - lower = smoother
    linear_tolerance: float = 1.0,     # mm - lower = smoother
) -> dict:
    """Tessellate a CadQuery solid to vertices + faces for Three.js."""
    shape = solid.val().wrapped

    # Mesh the shape
    BRepMesh_IncrementalMesh(shape, linear_tolerance, False, angular_tolerance)

    # Extract vertices and faces from all triangulations
    vertices = []
    faces = []
    vertex_offset = 0

    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = explorer.Current()
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, loc)

        if triangulation is not None:
            # Extract nodes
            for i in range(1, triangulation.NbNodes() + 1):
                pt = triangulation.Node(i)
                vertices.extend([pt.X(), pt.Y(), pt.Z()])

            # Extract triangles
            for i in range(1, triangulation.NbTriangles() + 1):
                tri = triangulation.Triangle(i)
                i1, i2, i3 = tri.Get()
                faces.extend([
                    i1 - 1 + vertex_offset,
                    i2 - 1 + vertex_offset,
                    i3 - 1 + vertex_offset,
                ])

            vertex_offset += triangulation.NbNodes()

        explorer.Next()

    return {
        "vertices": vertices,   # flat array: [x0,y0,z0, x1,y1,z1, ...]
        "faces": faces,         # flat array: [i0,i1,i2, i3,i4,i5, ...]
    }


def tessellate_for_export(
    solid: cq.Workplane,
    angular_tolerance: float = 0.1,
    linear_tolerance: float = 0.1,
) -> bytes:
    """Export a CadQuery solid to binary STL bytes."""
    # CadQuery has a built-in STL export
    import io
    bio = io.BytesIO()
    cq.exporters.export(solid, bio, exportType="STL",
                        tolerance=linear_tolerance,
                        angularTolerance=angular_tolerance)
    return bio.getvalue()
```

### 5.9 LOD Strategy

| LOD Level | Angular Tol | Linear Tol | Approx Triangles | Use Case |
|-----------|------------|------------|-------------------|----------|
| Preview (fast) | 0.5 rad | 2.0 mm | ~5,000-15,000 | Interactive viewport during param changes |
| Preview (quality) | 0.3 rad | 0.5 mm | ~20,000-50,000 | Viewport after params settle (debounced) |
| Export (STL) | 0.1 rad | 0.1 mm | ~100,000-500,000 | Final STL for 3D printing slicer |

The backend uses the fast preview LOD during active parameter dragging, then upgrades to quality preview 500ms after the last change.

---

## 6. State Management Architecture

### 6.1 Store Architecture

```typescript
// ============================================================
// DESIGN STORE - Aircraft parameters (persisted, undo-able)
// ============================================================
interface DesignStoreState {
  aircraft: AircraftDesign;

  /** Backend connection state */
  backendStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  lastGenerationMs: number;      // how long the backend took to regenerate

  /** Mesh data received from backend */
  meshData: {
    fuselage: MeshData | null;
    wing: MeshData | null;
    tail: MeshData | null;
    landingGear: MeshData | null;
    /** Sectioned parts (for 3D print preview) */
    printParts: MeshData[];
  };

  /** Derived values computed by backend */
  derivedValues: DerivedValues | null;

  /** Validation messages from backend */
  validationMessages: ValidationMessage[];

  /** Mutators */
  setParameter: (path: string, value: unknown) => void;
  loadDesign: (design: AircraftDesign) => void;
  resetToDefaults: () => void;
  changeTailType: (newType: TailType) => void;
  changeFuselageType: (newType: FuselageType) => void;

  /** Backend response handlers */
  setMeshData: (component: string, mesh: MeshData) => void;
  setDerivedValues: (values: DerivedValues) => void;
  setValidationMessages: (messages: ValidationMessage[]) => void;
}

interface MeshData {
  vertices: Float32Array;   // [x0,y0,z0, x1,y1,z1, ...]
  indices: Uint32Array;     // [i0,i1,i2, ...]
  normals?: Float32Array;   // [nx0,ny0,nz0, ...]
}

const useDesignStore = create<DesignStoreState>()(
  subscribeWithSelector(
    temporal(
      immer((set, get) => ({
        aircraft: createDefaultAircraft(),
        backendStatus: 'connecting',
        lastGenerationMs: 0,
        meshData: {
          fuselage: null, wing: null, tail: null,
          landingGear: null, printParts: [],
        },
        derivedValues: null,
        validationMessages: [],

        setParameter: (path, value) => {
          set((state) => {
            setNestedValue(state.aircraft, path, value);
          });
          // Trigger backend update (debounced in the WebSocket layer)
          sendToBackend(get().aircraft);
        },

        changeTailType: (newType) => {
          set((state) => {
            state.aircraft.tail = createDefaultTail(newType);
          });
          sendToBackend(get().aircraft);
        },

        setMeshData: (component, mesh) => set((state) => {
          (state.meshData as any)[component] = mesh;
        }),

        setDerivedValues: (values) => set({ derivedValues: values }),
        setValidationMessages: (msgs) => set({ validationMessages: msgs }),

        // ... other mutators
      })),
      {
        limit: 100,
        partialize: (state) => ({ aircraft: state.aircraft }),
      }
    )
  )
);

// ============================================================
// UI STORE - View state (not persisted, not undo-able)
// ============================================================
interface UIStoreState {
  selectedComponentId: ComponentId | null;
  selectedComponentType: ComponentType | null;
  hoveredComponentId: ComponentId | null;

  viewMode: '3d-perspective' | '3d-orthographic' | 'top' | 'front' | 'side';
  showDimensions: boolean;
  showGrid: boolean;
  showAxes: boolean;
  wireframe: boolean;
  showPrintSections: boolean;     // show sectioning planes and joints
  showSparChannels: boolean;      // highlight spar channels

  showGlobalParams: boolean;
  showComponentParams: boolean;

  displayUnits: 'mm' | 'cm' | 'in';

  selectComponent: (id: ComponentId | null, type: ComponentType | null) => void;
  hoverComponent: (id: ComponentId | null) => void;
  setViewMode: (mode: UIStoreState['viewMode']) => void;
  toggleDimensions: () => void;
  togglePrintSections: () => void;
}
```

### 6.2 WebSocket Communication Layer

```typescript
// frontend/src/api/websocket.ts

class BackendConnection {
  private ws: WebSocket | null = null;
  private pendingUpdate: AircraftDesign | null = null;
  private debounceTimer: number | null = null;

  connect(url: string = 'ws://localhost:8000/ws') {
    this.ws = new WebSocket(url);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      useDesignStore.getState().setBackendStatus('connected');
      // Send current design to get initial mesh
      this.sendDesign(useDesignStore.getState().aircraft);
    };

    this.ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary message: mesh data
        this.handleMeshMessage(event.data);
      } else {
        // JSON message: derived values, validation, etc.
        const msg = JSON.parse(event.data);
        this.handleJsonMessage(msg);
      }
    };

    this.ws.onclose = () => {
      useDesignStore.getState().setBackendStatus('disconnected');
      // Auto-reconnect after 2 seconds
      setTimeout(() => this.connect(url), 2000);
    };
  }

  /** Send design parameters, debounced to avoid overwhelming the backend */
  sendDesign(design: AircraftDesign) {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);

    this.pendingUpdate = design;
    this.debounceTimer = window.setTimeout(() => {
      if (this.ws?.readyState === WebSocket.OPEN && this.pendingUpdate) {
        this.ws.send(JSON.stringify({
          type: 'update_design',
          design: this.pendingUpdate,
        }));
        this.pendingUpdate = null;
      }
    }, 50); // 50ms debounce during active dragging
  }

  private handleMeshMessage(buffer: ArrayBuffer) {
    // Binary protocol: [componentId(1 byte)][vertexCount(4 bytes)][faceCount(4 bytes)]
    //                   [vertices(N*3*4 bytes)][faces(M*3*4 bytes)]
    const view = new DataView(buffer);
    const componentId = view.getUint8(0);
    const vertexCount = view.getUint32(1, true);
    const faceCount = view.getUint32(5, true);

    const verticesStart = 9;
    const verticesEnd = verticesStart + vertexCount * 3 * 4;
    const facesEnd = verticesEnd + faceCount * 3 * 4;

    const vertices = new Float32Array(buffer, verticesStart, vertexCount * 3);
    const faces = new Uint32Array(buffer, verticesEnd, faceCount * 3);

    const componentNames = ['fuselage', 'wing', 'tail', 'landingGear'];
    const name = componentNames[componentId] || 'unknown';

    useDesignStore.getState().setMeshData(name, { vertices, indices: faces });
  }

  private handleJsonMessage(msg: any) {
    switch (msg.type) {
      case 'derived_values':
        useDesignStore.getState().setDerivedValues(msg.values);
        break;
      case 'validation':
        useDesignStore.getState().setValidationMessages(msg.messages);
        break;
      case 'generation_time':
        useDesignStore.getState().setLastGenerationMs(msg.ms);
        break;
      case 'print_parts':
        // Mesh data for individual print sections
        useDesignStore.getState().setPrintParts(msg.parts);
        break;
    }
  }
}

export const backend = new BackendConnection();
```

### 6.3 Backend WebSocket Handler

```python
# backend/api/websocket.py
from fastapi import WebSocket
import asyncio
import time

class DesignSession:
    """Manages a single client's design session."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.current_design: AircraftDesign | None = None
        self.generation_task: asyncio.Task | None = None

    async def handle_message(self, data: dict):
        if data["type"] == "update_design":
            design = AircraftDesign(**data["design"])

            # Cancel any in-flight generation
            if self.generation_task and not self.generation_task.done():
                self.generation_task.cancel()

            # Start new generation in background
            self.generation_task = asyncio.create_task(
                self.generate_and_send(design)
            )

    async def generate_and_send(self, design: AircraftDesign):
        """Generate geometry and send mesh + metadata back to client.

        The backend is stateless: it receives the full AircraftDesign,
        generates geometry, and returns results. No design state is stored
        between requests. This enables Cloud Run multi-tenant concurrency.
        """
        start = time.perf_counter()

        try:
            # Run CadQuery in an isolated thread (CPU-bound, not thread-safe).
            # Each thread gets its own OpenCascade context -- no shared state.
            import anyio
            result = await anyio.to_thread.run_sync(
                lambda: generate_aircraft(design),
                cancellable=True,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000

            # Send mesh data (binary)
            for component_id, mesh in result.meshes.items():
                await self.ws.send_bytes(
                    pack_mesh_binary(component_id, mesh)
                )

            # Send derived values (JSON)
            await self.ws.send_json({
                "type": "derived_values",
                "values": result.derived_values.dict(),
            })

            # Send validation results (JSON)
            await self.ws.send_json({
                "type": "validation",
                "messages": [m.dict() for m in result.validation_messages],
            })

            # Send timing info
            await self.ws.send_json({
                "type": "generation_time",
                "ms": round(elapsed_ms, 1),
            })

        except asyncio.CancelledError:
            pass  # Superseded by a newer request
        except Exception as e:
            await self.ws.send_json({
                "type": "error",
                "message": str(e),
            })
```

### 6.4 State Flow Diagram

```
User Input (slider/dropdown/click)
      │
      ▼
  ┌─────────────┐
  │ Zustand      │
  │ Design Store │──── undo/redo stack (Zundo)
  │ (optimistic) │
  └──────┬──────┘
         │
         ▼ (debounced 50ms)
  ┌──────────────┐            ┌──────────────────────────┐
  │  WebSocket   │  ────────→ │  Python Backend (FastAPI) │
  │  Client      │            │                            │
  │              │  ←──────── │  CadQuery geometry gen     │
  └──────┬──────┘   mesh +   │  Validation                │
         │          derived + │  Derived values            │
         │          validation│  Part sectioning           │
         ▼                    └──────────────────────────┘
  ┌─────────────────────────────────────────┐
  │         React Component Tree            │
  │                                         │
  │  ┌──────────┐  ┌────────────────────┐   │
  │  │ Panels   │  │ Viewport (R3F)     │   │
  │  │ (params, │  │                    │   │
  │  │  derived, │  │ Three.js renders   │   │
  │  │  validation│ │ mesh from backend  │   │
  │  │  print info│ │                    │   │
  │  └──────────┘  │ Dimension overlays  │   │
  │                │ Selection highlight  │   │
  │                └────────────────────┘   │
  └─────────────────────────────────────────┘

  UI Store (selection, hover, view settings) - local only, no backend
```

### 6.5 Undo/Redo

Provided by **Zundo** middleware wrapping the design store. Undo/redo changes the `aircraft` parameters; the WebSocket layer automatically sends the restored parameters to the backend for re-generation.

```typescript
// Access undo/redo
const { undo, redo } = useDesignStore.temporal.getState();

// Keyboard shortcuts
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
      e.preventDefault();
      useDesignStore.temporal.getState().undo();
      // After undo, send restored params to backend
      sendToBackend(useDesignStore.getState().aircraft);
    }
    if (e.ctrlKey && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
      e.preventDefault();
      useDesignStore.temporal.getState().redo();
      sendToBackend(useDesignStore.getState().aircraft);
    }
  };
  window.addEventListener('keydown', handler);
  return () => window.removeEventListener('keydown', handler);
}, []);
```

---

## 7. File Format & Storage

### 7.1 Format Specification

CHENG design files use JSON with the `.cheng` extension. The format is a direct serialization of the `AircraftDesign` Pydantic model, using snake_case field names (Python convention, since the backend is the canonical source).

### 7.2 Complete Example

```json
{
  "version": "1.0.0",
  "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
  "name": "Sport Trainer 1500",
  "created_at": "2026-02-20T14:30:00Z",
  "modified_at": "2026-02-23T09:15:00Z",
  "description": "A 1500mm sport trainer for FDM printing, conventional tail, electric tractor",
  "display_units": "mm",

  "fuselage": {
    "id": "fus-001",
    "type": "conventional",
    "length": 950,
    "cross_sections": [
      { "id": "fcs-001", "station_position": 0.0, "width": 10, "height": 10, "corner_radius": 5, "rotation": 0 },
      { "id": "fcs-002", "station_position": 0.15, "width": 80, "height": 70, "corner_radius": 20, "rotation": 0 },
      { "id": "fcs-003", "station_position": 0.4, "width": 90, "height": 80, "corner_radius": 25, "rotation": 0 },
      { "id": "fcs-004", "station_position": 0.75, "width": 70, "height": 65, "corner_radius": 15, "rotation": 0 },
      { "id": "fcs-005", "station_position": 1.0, "width": 20, "height": 30, "corner_radius": 10, "rotation": 0 }
    ],
    "nose_length": 120,
    "nose_shape": "ogive",
    "tail_length": 200,
    "tail_shape": "tapered",
    "wing_position": 0.28,
    "wing_mounting": "high",
    "wall_thickness": 1.6
  },

  "wing": {
    "id": "wing-001",
    "span": 1500,
    "sections": [
      { "id": "ws-001", "span_position": 0.0, "chord": 230, "airfoil": "clark-y", "twist": 2, "sweep_angle": 0, "dihedral_angle": 3 },
      { "id": "ws-002", "span_position": 1.0, "chord": 160, "airfoil": "clark-y", "twist": -1, "sweep_angle": 0, "dihedral_angle": 3 }
    ],
    "control_surfaces": [
      { "id": "cs-001", "type": "aileron", "parent_id": "wing-001", "span_start": 0.6, "span_end": 0.95, "chord_ratio": 0.25, "max_deflection_up": 25, "max_deflection_down": 20, "hinge_line": "straight" }
    ],
    "incidence": 2,
    "symmetric": true
  },

  "tail": {
    "id": "tail-001",
    "type": "conventional",
    "moment_arm": 550,
    "horizontal_stabilizer": {
      "id": "hstab-001",
      "span": 450,
      "root_chord": 130,
      "tip_chord": 90,
      "airfoil": "naca-0009",
      "sweep_angle": 5,
      "dihedral_angle": 0,
      "incidence": -1,
      "elevator": { "id": "cs-003", "type": "aileron", "parent_id": "hstab-001", "span_start": 0.05, "span_end": 0.95, "chord_ratio": 0.35, "max_deflection_up": 25, "max_deflection_down": 20, "hinge_line": "straight" }
    },
    "vertical_stabilizer": {
      "id": "vstab-001",
      "height": 160,
      "root_chord": 140,
      "tip_chord": 80,
      "airfoil": "naca-0009",
      "sweep_angle": 25,
      "cant_angle": 0,
      "rudder": { "id": "cs-004", "type": "aileron", "parent_id": "vstab-001", "span_start": 0.05, "span_end": 0.95, "chord_ratio": 0.35, "max_deflection_up": 30, "max_deflection_down": 30, "hinge_line": "straight" }
    },
    "v_tail_surfaces": null,
    "v_tail_dihedral": 35
  },

  "propulsion": {
    "type": "electric-tractor",
    "count": 1,
    "motors": [
      { "id": "motor-001", "name": "2212 1400KV", "kv": 1400, "weight": 52, "max_watts": 250, "shaft_diameter": 3.17 }
    ],
    "propellers": [
      { "id": "prop-001", "diameter": 229, "pitch": 114, "blades": 2 }
    ],
    "mounts": [
      { "id": "mount-001", "position_x": 0, "position_y": 0, "position_z": 0, "thrust_angle": 2, "side_angle": 0 }
    ]
  },

  "landing_gear": {
    "type": "belly",
    "main_wheel_diameter": 55,
    "main_wheel_width": 18,
    "main_gear_span": 180,
    "aux_wheel_diameter": 30,
    "strut_height": 80,
    "strut_type": "wire"
  },

  "print_settings": {
    "nozzle_diameter": 0.4,
    "layer_height": 0.2,
    "min_wall_thickness": 1.2,
    "infill_percent": 10,
    "bed_size_x": 220,
    "bed_size_y": 220,
    "bed_size_z": 250,
    "joint_type": "tab-slot",
    "joint_clearance": 0.2,
    "spar_channel_diameter": 6
  }
}
```

### 7.3 File Format Versioning

```python
# backend/models/migration.py

CURRENT_VERSION = "1.0.0"

MIGRATIONS = {
    ("0.1.0", "1.0.0"): lambda data: {
        **data,
        "version": "1.0.0",
        "print_settings": PrintSettings().dict(),
        "landing_gear": LandingGear().dict(),
    },
}

def migrate_design(data: dict) -> dict:
    """Migrate old design files to the current version."""
    while data.get("version") != CURRENT_VERSION:
        old_version = data["version"]
        key = (old_version, CURRENT_VERSION)
        if key not in MIGRATIONS:
            raise ValueError(f"No migration path from {old_version} to {CURRENT_VERSION}")
        data = MIGRATIONS[key](data)
    return data
```

### 7.4 Storage Architecture

The storage layer uses a **`StorageBackend` interface** to abstract over local filesystem and browser-based storage:

```python
# backend/storage/base.py
from abc import ABC, abstractmethod
from pathlib import Path

class StorageBackend(ABC):
    """Abstract storage interface for design persistence."""

    @abstractmethod
    async def save_design(self, design: AircraftDesign, filename: str) -> str:
        """Save a design. Returns an identifier (path or key)."""
        ...

    @abstractmethod
    async def load_design(self, identifier: str) -> AircraftDesign:
        """Load a design by identifier."""
        ...

    @abstractmethod
    async def list_designs(self) -> list[dict]:
        """List all saved designs."""
        ...

    @abstractmethod
    async def delete_design(self, identifier: str) -> bool:
        """Delete a design by identifier."""
        ...


class LocalFileStorage(StorageBackend):
    """Stores designs as .cheng JSON files on the local filesystem.
    Used in CHENG_MODE=local with Docker volume mount."""

    def __init__(self, data_dir: Path):
        self.designs_dir = data_dir / "designs"
        self.designs_dir.mkdir(parents=True, exist_ok=True)

    async def save_design(self, design: AircraftDesign, filename: str) -> str:
        filepath = self.designs_dir / f"{filename}.cheng"
        filepath.write_text(design.model_dump_json(indent=2))
        return str(filepath)

    async def load_design(self, identifier: str) -> AircraftDesign:
        filepath = Path(identifier)
        data = json.loads(filepath.read_text())
        data = migrate_design(data)
        return AircraftDesign(**data)

    async def list_designs(self) -> list[dict]:
        files = sorted(
            self.designs_dir.glob("*.cheng"),
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        return [
            {"name": f.stem, "path": str(f), "modified": f.stat().st_mtime}
            for f in files
        ]

    async def delete_design(self, identifier: str) -> bool:
        Path(identifier).unlink(missing_ok=True)
        return True


class BrowserStorage(StorageBackend):
    """No-op server-side storage for CHENG_MODE=cloud.
    All persistence happens in the browser via IndexedDB.
    The backend only validates and returns design JSON -- it never stores it."""

    async def save_design(self, design: AircraftDesign, filename: str) -> str:
        # In cloud mode, the frontend saves to IndexedDB directly.
        # This endpoint validates the design and returns it.
        return f"browser://{filename}"

    async def load_design(self, identifier: str) -> AircraftDesign:
        raise NotImplementedError("Cloud mode: designs are loaded from browser IndexedDB")

    async def list_designs(self) -> list[dict]:
        return []  # Frontend manages the design list via IndexedDB

    async def delete_design(self, identifier: str) -> bool:
        return True  # Frontend manages deletion via IndexedDB


def create_storage_backend() -> StorageBackend:
    """Factory: create the appropriate storage backend based on CHENG_MODE."""
    import os
    mode = os.environ.get("CHENG_MODE", "local")
    if mode == "cloud":
        return BrowserStorage()
    else:
        data_dir = Path(os.environ.get("CHENG_DATA_DIR", "/data"))
        return LocalFileStorage(data_dir)
```

**Storage by mode:**

| Concern | Local Mode | Cloud Mode |
|---------|-----------|------------|
| Design persistence | `/data/designs/*.cheng` (Docker volume) | Browser IndexedDB |
| Save trigger | Backend writes to filesystem | Frontend writes to IndexedDB |
| Load trigger | Backend reads from filesystem | Frontend reads from IndexedDB |
| Design list | Backend scans `/data/designs/` | Frontend queries IndexedDB |
| Airfoil database | Bundled read-only in image (`/app/backend/data/airfoils/`) | Same (read-only in image) |
| Custom airfoils | `/data/custom_airfoils/` (volume) | Browser IndexedDB (per-user) |
| Shared/published designs | N/A | Future: GCS bucket |

**Frontend IndexedDB storage (cloud mode):**

```typescript
// frontend/src/storage/indexedDB.ts
import { openDB, DBSchema } from 'idb';

interface ChengDB extends DBSchema {
  designs: {
    key: string;                    // design ID
    value: {
      id: string;
      name: string;
      data: AircraftDesign;         // full design JSON
      modifiedAt: string;
      thumbnail?: string;           // base64 viewport screenshot
    };
    indexes: { 'by-modified': string };
  };
  customAirfoils: {
    key: string;
    value: AirfoilProfile;
  };
}

const db = await openDB<ChengDB>('cheng', 1, {
  upgrade(db) {
    const store = db.createObjectStore('designs', { keyPath: 'id' });
    store.createIndex('by-modified', 'modifiedAt');
    db.createObjectStore('customAirfoils', { keyPath: 'id' });
  },
});

export async function saveDesign(design: AircraftDesign): Promise<void> {
  await db.put('designs', {
    id: design.id,
    name: design.name,
    data: design,
    modifiedAt: new Date().toISOString(),
  });
}

export async function loadDesign(id: string): Promise<AircraftDesign> {
  const record = await db.get('designs', id);
  if (!record) throw new Error(`Design ${id} not found`);
  return record.data;
}

export async function listDesigns(): Promise<{ id: string; name: string; modifiedAt: string }[]> {
  return db.getAllFromIndex('designs', 'by-modified');
}
```

### 7.5 Save/Load Endpoints

```python
# backend/api/routes.py
from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse, FileResponse
import json

router = APIRouter()

# Storage backend is injected based on CHENG_MODE
storage = create_storage_backend()

@router.post("/api/design/save")
async def save_design(design: AircraftDesign, filename: str = "untitled"):
    """Save design. In local mode: writes to filesystem.
    In cloud mode: validates and returns (frontend saves to IndexedDB)."""
    identifier = await storage.save_design(design, filename)
    return {"identifier": identifier, "design": design.model_dump()}

@router.post("/api/design/load")
async def load_design(file: UploadFile):
    """Load a .cheng design file (local mode only for file upload).
    Cloud mode: frontend loads from IndexedDB and sends to /api/design/validate."""
    content = await file.read()
    data = json.loads(content)
    data = migrate_design(data)
    design = AircraftDesign(**data)
    return design.model_dump()

@router.post("/api/design/validate")
async def validate_design_endpoint(design: AircraftDesign):
    """Validate and migrate a design JSON (used by cloud mode frontend
    when loading from IndexedDB or importing a file)."""
    return design.model_dump()

@router.get("/api/designs")
async def list_designs():
    """List all saved designs. Local mode: filesystem. Cloud mode: empty
    (frontend manages list via IndexedDB)."""
    return await storage.list_designs()
```

---

## 8. Export Pipeline

### 8.1 STL Export (Primary - 3D Printing)

STL is the primary export format. CadQuery produces watertight, manifold STL meshes directly from B-rep solids -- exactly what 3D printing slicers require.

```python
# backend/export/stl.py
import cadquery as cq
from pathlib import Path

class STLExportOptions(BaseModel):
    resolution: str = "normal"       # draft | normal | fine
    split_parts: bool = True          # export each print section separately
    include_joints: bool = True       # include tab/slot assembly features
    components: list[str] = ["all"]   # which components to export

TOLERANCES = {
    "draft":  {"linear": 1.0, "angular": 0.5},
    "normal": {"linear": 0.2, "angular": 0.2},
    "fine":   {"linear": 0.05, "angular": 0.1},
}

async def export_stl(
    design: AircraftDesign,
    options: STLExportOptions,
) -> list[ExportedFile]:
    """Export aircraft as STL file(s) for 3D printing."""
    tol = TOLERANCES[options.resolution]
    files = []

    # Generate full aircraft geometry
    aircraft = generate_aircraft(design)

    if options.split_parts:
        # Export each print section as a separate STL
        sections = section_for_printing(aircraft, design.print_settings)

        for i, section in enumerate(sections):
            stl_bytes = export_solid_to_stl(
                section.solid,
                linear_tol=tol["linear"],
                angular_tol=tol["angular"],
            )
            files.append(ExportedFile(
                filename=f"{design.name}_{section.component}_{i+1:02d}.stl",
                data=stl_bytes,
                part_name=section.label,
            ))
    else:
        # Export as single STL (assembled)
        stl_bytes = export_solid_to_stl(
            aircraft.assembly_solid,
            linear_tol=tol["linear"],
            angular_tol=tol["angular"],
        )
        files.append(ExportedFile(
            filename=f"{design.name}_complete.stl",
            data=stl_bytes,
            part_name="Complete Aircraft",
        ))

    return files


def export_solid_to_stl(
    solid: cq.Workplane,
    linear_tol: float = 0.2,
    angular_tol: float = 0.2,
) -> bytes:
    """Convert CadQuery solid to binary STL bytes."""
    import io
    bio = io.BytesIO()
    cq.exporters.export(
        solid, bio,
        exportType="STL",
        tolerance=linear_tol,
        angularTolerance=angular_tol,
    )
    return bio.getvalue()
```

**STL Quality Settings:**

| Quality | Linear Tol | Angular Tol | Typical Size | Use Case |
|---------|-----------|------------|--------------|----------|
| Draft | 1.0 mm | 0.5 rad | ~200 KB | Quick check in slicer |
| Normal | 0.2 mm | 0.2 rad | ~2 MB | Standard printing |
| Fine | 0.05 mm | 0.1 rad | ~15 MB | High-detail areas |

**3D Print Sectioning:** Wings exceeding the print bed are automatically split into sections with interlocking joints:

```python
def section_for_printing(
    aircraft: GeneratedAircraft,
    settings: PrintSettings,
) -> list[PrintSection]:
    """Split aircraft into sections that fit the printer bed."""
    sections = []

    # Wing sections
    half_span = aircraft.wing_solid  # one half of the wing
    max_section_length = min(settings.bed_size_x, settings.bed_size_y) - 20  # margin
    wing_span = aircraft.design.wing.span / 2

    if wing_span > max_section_length:
        num_wing_sections = math.ceil(wing_span / max_section_length)
        for i in range(num_wing_sections):
            cut_start = i * max_section_length
            cut_end = min((i + 1) * max_section_length, wing_span)

            section_solid = cut_between_planes(
                half_span, axis="Y", start=cut_start, end=cut_end
            )

            # Add assembly features
            if i > 0:
                section_solid = add_joint_socket(section_solid, "Y", cut_start, settings)
            if i < num_wing_sections - 1:
                section_solid = add_joint_tab(section_solid, "Y", cut_end, settings)

            # Add spar channel
            section_solid = add_spar_channel(
                section_solid,
                settings.spar_channel_diameter,
                chord_ratio=0.25,
            )

            sections.append(PrintSection(
                solid=section_solid,
                component="wing_right",
                label=f"Wing Right Section {i+1}/{num_wing_sections}",
            ))

    # Fuselage sections (similar logic)
    # Tail sections (usually fit in one piece)

    return sections
```

### 8.2 STEP Export

Because CadQuery is built on OpenCascade, STEP export is trivial and first-class:

```python
# backend/export/step.py

async def export_step(design: AircraftDesign) -> bytes:
    """Export aircraft as STEP file for use in other CAD tools."""
    aircraft = generate_aircraft(design)

    import io
    bio = io.BytesIO()
    cq.exporters.export(
        aircraft.assembly_solid,
        bio,
        exportType="STEP",
    )
    return bio.getvalue()
```

### 8.3 3MF Export (Future)

3MF is superior to STL for 3D printing (supports color, materials, multi-part assemblies). CadQuery's OCCT kernel can produce 3MF via third-party libraries.

### 8.4 DXF/SVG Export (2D Patterns - Secondary)

For users who also use laser cutting or foam board construction, the backend can generate 2D flat patterns:

```python
# backend/export/dxf.py

async def export_dxf(design: AircraftDesign) -> bytes:
    """Export 2D flat patterns for laser cutting."""
    patterns = []

    # Wing rib profiles (airfoil cross-sections)
    for section in design.wing.sections:
        coords = get_airfoil_coords(section.airfoil)
        scaled = scale_airfoil(coords, section.chord)
        patterns.append(FlatPattern(
            name=f"Wing Rib at {section.span_position*100:.0f}% span",
            outline=scaled,
        ))

    # Fuselage formers (cross-sections)
    for cs in design.fuselage.cross_sections:
        patterns.append(FlatPattern(
            name=f"Former at {cs.station_position*100:.0f}% station",
            outline=generate_cross_section_outline(cs),
        ))

    return write_dxf(patterns)
```

### 8.5 PDF Export (Dimensioned Drawings)

Three-view dimensioned drawings with annotations:

```
Sheet 1: Three-view (top, front, side) with key dimensions
Sheet 2: Wing planform with airfoil callouts and control surface locations
Sheet 3: Fuselage cross-sections with dimensions
Sheet 4: 3D print parts list with assembly diagram
Sheet 5: Specifications table
```

### 8.6 Export HTTP Endpoints

Exports are generated **entirely in-memory** -- no temp files are written to disk. This is critical for cloud mode where the filesystem is ephemeral and shared across concurrent requests. In local mode, exports can optionally also be saved to the mounted volume.

```python
# backend/api/routes.py
from fastapi.responses import StreamingResponse
import io

@router.post("/api/export/stl")
async def export_stl_endpoint(design: AircraftDesign, options: STLExportOptions):
    """Export STL files. Returns zip if multiple parts.
    All generation happens in-memory (no temp files on disk)."""
    files = await export_stl(design, options)

    if len(files) == 1:
        # Stream single STL directly from memory
        return StreamingResponse(
            io.BytesIO(files[0].data),
            media_type="model/stl",
            headers={"Content-Disposition": f'attachment; filename="{files[0].filename}"'},
        )
    else:
        # Zip multiple STL files in-memory
        zip_bytes = create_zip_in_memory(files)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{design.name}_parts.zip"'},
        )

@router.post("/api/export/step")
async def export_step_endpoint(design: AircraftDesign):
    """Export STEP file. Generated in-memory, streamed as response."""
    step_bytes = await export_step(design)
    return StreamingResponse(
        io.BytesIO(step_bytes),
        media_type="application/step",
        headers={"Content-Disposition": f'attachment; filename="{design.name}.step"'},
    )


def create_zip_in_memory(files: list[ExportedFile]) -> bytes:
    """Create a ZIP archive entirely in memory."""
    import zipfile
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(f.filename, f.data)
    return zip_buffer.getvalue()
```

**Export behavior by mode:**

| Concern | Local Mode | Cloud Mode |
|---------|-----------|------------|
| STL/STEP generation | In-memory via CadQuery `io.BytesIO` | Identical |
| Response delivery | `StreamingResponse` (HTTP) | Identical |
| Optional local save | Can also write to `/data/exports/` | Not available (no persistent disk) |
| Temp files on disk | None (all in-memory) | None |
| Max export size | Limited by container memory (2Gi) | Same |

---

## 9. Validation Engine

### 9.1 Validation Layers

The validation engine runs on the **backend** (Python) and sends results to the frontend via WebSocket.

```
Layer 1: Parameter Range Validation (instant, Pydantic field constraints)
  - Is each parameter within its min/max bounds?
  - Are required fields present?
  - Are enum values valid?
  → Handled automatically by Pydantic Field(ge=, le=, etc.)

Layer 2: Geometric Consistency (fast, custom validators)
  - Do wing sections span from 0.0 to 1.0?
  - Is tip chord <= root chord? (warning, not error)
  - Do control surfaces overlap?
  - Is the moment arm physically possible given fuselage length?

Layer 3: Aerodynamic Feasibility (computed alongside geometry)
  - Is the wing loading reasonable for the category?
  - Is the CG within the acceptable range?
  - Are tail volume coefficients adequate for stability?
  - Is the aspect ratio dangerously high for the structure?
  - Is the control authority sufficient?

Layer 4: 3D Printability (computed after geometry generation)
  - Are wall thicknesses >= printer minimum?
  - Do any parts exceed print bed dimensions?
  - Are overhangs manageable (< 60 degrees without support)?
  - Are joint features properly sized for the printer tolerance?
  - Is estimated print time reasonable?
  - Are spar channels properly aligned across sections?
```

### 9.2 Validation Engine Implementation

```python
# backend/validation/engine.py
from dataclasses import dataclass
from models.aircraft import AircraftDesign, ValidationMessage

@dataclass
class ValidationRule:
    id: str
    name: str
    layer: int  # 1-4
    check: callable  # (AircraftDesign) -> list[ValidationMessage]

RULES: list[ValidationRule] = []

def rule(id: str, name: str, layer: int):
    """Decorator to register a validation rule."""
    def decorator(fn):
        RULES.append(ValidationRule(id=id, name=name, layer=layer, check=fn))
        return fn
    return decorator


# ── Layer 2: Geometric Consistency ──────────────────────────

@rule("wing-sections-ordered", "Wing sections span 0 to 1", layer=2)
def check_wing_sections(d: AircraftDesign) -> list[ValidationMessage]:
    positions = [s.span_position for s in d.wing.sections]
    msgs = []
    if not positions or positions[0] != 0:
        msgs.append(ValidationMessage(
            severity="error", component=d.wing.id, parameter="sections",
            message="First wing section must be at span_position 0 (root)",
        ))
    if not positions or positions[-1] != 1:
        msgs.append(ValidationMessage(
            severity="error", component=d.wing.id, parameter="sections",
            message="Last wing section must be at span_position 1 (tip)",
        ))
    for i in range(1, len(positions)):
        if positions[i] <= positions[i-1]:
            msgs.append(ValidationMessage(
                severity="error", component=d.wing.id, parameter="sections",
                message="Wing sections must be in ascending spanwise order",
            ))
            break
    return msgs


@rule("control-surface-overlap", "No overlapping control surfaces", layer=2)
def check_cs_overlap(d: AircraftDesign) -> list[ValidationMessage]:
    msgs = []
    surfaces = d.wing.control_surfaces
    for i in range(len(surfaces)):
        for j in range(i + 1, len(surfaces)):
            if surfaces[i].span_end > surfaces[j].span_start and \
               surfaces[i].span_start < surfaces[j].span_end:
                msgs.append(ValidationMessage(
                    severity="error", component=surfaces[i].id,
                    parameter="span_start",
                    message=f'Control surface "{surfaces[i].type}" overlaps with "{surfaces[j].type}"',
                ))
    return msgs


# ── Layer 3: Aerodynamic Feasibility ───────────────────────

@rule("cg-range", "CG within acceptable range", layer=3)
def check_cg(d: AircraftDesign) -> list[ValidationMessage]:
    cg = estimate_cg(d)
    mac = compute_mac(d.wing)
    wing_le_x = compute_wing_le_x(d)
    cg_percent = ((cg.x - wing_le_x) / mac) * 100

    if cg_percent < 20:
        return [ValidationMessage(
            severity="warning", component=d.wing.id, parameter="incidence",
            message=f"Estimated CG at {cg_percent:.0f}% MAC - aircraft may be nose-heavy",
            suggestion="Move battery aft or adjust wing position",
        )]
    if cg_percent > 35:
        return [ValidationMessage(
            severity="error", component=d.wing.id, parameter="incidence",
            message=f"Estimated CG at {cg_percent:.0f}% MAC - aircraft will be tail-heavy",
            suggestion="Move battery forward or adjust wing position",
        )]
    return []


@rule("tail-volume", "Adequate tail volume coefficients", layer=3)
def check_tail_volume(d: AircraftDesign) -> list[ValidationMessage]:
    msgs = []
    htvc = compute_htail_volume_coeff(d)
    vtvc = compute_vtail_volume_coeff(d)

    if htvc < 0.3:
        msgs.append(ValidationMessage(
            severity="warning", component=d.tail.id, parameter="moment_arm",
            message=f"Horizontal tail volume ({htvc:.2f}) is low - pitch stability may be inadequate",
            suggestion="Increase tail area or moment arm",
        ))
    if vtvc < 0.02:
        msgs.append(ValidationMessage(
            severity="warning", component=d.tail.id, parameter="moment_arm",
            message=f"Vertical tail volume ({vtvc:.2f}) is low - yaw stability may be inadequate",
        ))
    return msgs


@rule("aspect-ratio-structural", "Aspect ratio structural warning", layer=3)
def check_aspect_ratio(d: AircraftDesign) -> list[ValidationMessage]:
    wing_area = compute_wing_area(d.wing)
    ar = (d.wing.span ** 2) / wing_area
    if ar > 10:
        return [ValidationMessage(
            severity="warning", component=d.wing.id, parameter="span",
            message=f"Aspect ratio {ar:.1f} is high - consider spar reinforcement",
        )]
    return []


# ── Layer 4: 3D Printability ──────────────────────────────

@rule("bed-size-fit", "Parts fit within print bed", layer=4)
def check_bed_fit(d: AircraftDesign) -> list[ValidationMessage]:
    msgs = []
    ps = d.print_settings
    bed_max = max(ps.bed_size_x, ps.bed_size_y)

    # Check if any wing section chord exceeds bed
    for section in d.wing.sections:
        if section.chord > bed_max:
            msgs.append(ValidationMessage(
                severity="error", component=section.id, parameter="chord",
                message=f"Wing chord {section.chord}mm exceeds print bed ({bed_max}mm)",
                suggestion="Reduce chord or increase bed size in print settings",
            ))

    # Check fuselage cross-sections
    for cs in d.fuselage.cross_sections:
        if cs.width > bed_max or cs.height > bed_max:
            msgs.append(ValidationMessage(
                severity="warning", component=cs.id, parameter="width",
                message=f"Fuselage cross-section ({cs.width}x{cs.height}mm) may not fit print bed",
                suggestion="Fuselage may need to be printed in halves (left/right split)",
            ))
    return msgs


@rule("wall-thickness-printable", "Wall thickness is printable", layer=4)
def check_wall_thickness(d: AircraftDesign) -> list[ValidationMessage]:
    min_wall = d.print_settings.nozzle_diameter * 2  # at least 2 perimeters
    msgs = []

    if d.fuselage.wall_thickness < min_wall:
        msgs.append(ValidationMessage(
            severity="error", component=d.fuselage.id, parameter="wall_thickness",
            message=f"Fuselage wall {d.fuselage.wall_thickness}mm < minimum printable {min_wall}mm",
            suggestion=f"Increase to at least {min_wall}mm (2 perimeters at {d.print_settings.nozzle_diameter}mm nozzle)",
        ))
    return msgs


@rule("spar-channel-size", "Spar channel is usable", layer=4)
def check_spar_channel(d: AircraftDesign) -> list[ValidationMessage]:
    msgs = []
    spar_d = d.print_settings.spar_channel_diameter

    if spar_d > 0:
        # Spar channel must be smaller than the thinnest airfoil section
        for section in d.wing.sections:
            profile = get_airfoil_profile(section.airfoil)
            max_thickness_mm = profile.max_thickness_percent / 100 * section.chord
            if spar_d > max_thickness_mm * 0.7:
                msgs.append(ValidationMessage(
                    severity="warning", component=section.id, parameter="chord",
                    message=f"Spar channel ({spar_d}mm) is large relative to airfoil thickness ({max_thickness_mm:.0f}mm)",
                    suggestion="Reduce spar diameter or increase chord",
                ))
    return msgs


# ── Run All Rules ──────────────────────────────────────────

def validate_design(design: AircraftDesign, max_layer: int = 4) -> list[ValidationMessage]:
    """Run all validation rules up to the specified layer."""
    messages = []
    for rule in RULES:
        if rule.layer <= max_layer:
            messages.extend(rule.check(design))
    return messages
```

### 9.3 Validation in the UI

```
┌──────────────────────────────────────────────────┐
│ Validation results appear as:                     │
│                                                   │
│ 1. Inline on parameter fields:                    │
│    [Span: 1500mm] ← red border if error           │
│                                                   │
│ 2. Bottom status bar:                             │
│    ✓ Valid  |  ⚠ 2 warnings  |  ✕ Error           │
│    🖨 3 parts | est. 14h print | 120g filament    │
│                                                   │
│ 3. Expandable validation panel:                   │
│    Click status bar to see all messages            │
│    Each message links to the component             │
│    Clicking selects the component                  │
│                                                   │
│ 4. Print preview mode:                            │
│    Toggle to see sectioning planes on the model    │
│    Each section highlighted in different color      │
│    Joint features shown with emphasis               │
└──────────────────────────────────────────────────┘
```

Layers 1-2 are checked immediately on the frontend (via TypeScript constraint definitions) for instant feedback. Layers 3-4 are computed on the backend and pushed via WebSocket alongside geometry updates.

---

## 10. Plugin / Extension Architecture

> **Note:** The plugin system is a Phase 2+ feature. The architecture is designed so that Phase 1 code does not preclude it.

### 10.1 Plugin Types

```python
# backend/plugins/base.py
from abc import ABC, abstractmethod

class PluginType(str, Enum):
    AIRFOIL_DATABASE = "airfoil-database"
    MATERIAL_DATABASE = "material-database"
    COMPONENT_DATABASE = "component-database"
    EXPORT_FORMAT = "export-format"
    VALIDATION_RULE = "validation-rule"
    TEMPLATE = "template"
    SLICER_PROFILE = "slicer-profile"     # 3D printer slicer presets

class AirfoilDatabasePlugin(ABC):
    @abstractmethod
    def search(self, query: str) -> list[AirfoilSummary]: ...

    @abstractmethod
    def get_profile(self, id: str) -> AirfoilProfile: ...

    @abstractmethod
    def list_all(self) -> list[AirfoilSummary]: ...

class ExportFormatPlugin(ABC):
    @abstractmethod
    def export(self, design: AircraftDesign, options: dict) -> bytes: ...

    @abstractmethod
    def file_extension(self) -> str: ...

class SlicerProfilePlugin(ABC):
    """Generate slicer-specific settings for a given part."""
    @abstractmethod
    def generate_profile(self, part: PrintSection, settings: PrintSettings) -> dict: ...

    @abstractmethod
    def slicer_name(self) -> str: ...  # "PrusaSlicer", "Cura", "OrcaSlicer"
```

### 10.2 Built-in "Plugins" (Phase 1)

In Phase 1, the same interfaces are used internally but without dynamic loading:

- **Built-in airfoil database**: ~50 airfoils stored as JSON/DAT files (Clark Y, NACA 4-digit, SD7037, etc.)
- **Built-in export formats**: STL, STEP, DXF
- **Built-in validation rules**: The rules defined in Section 8
- **Built-in templates**: "Sport Trainer", "Flying Wing", "Glider", "Pylon Racer"
- **Built-in print profiles**: Ender 3 (220x220x250), Prusa MK3S (250x210x210), Bambu P1S (256x256x256)

---

## 11. Phase Breakdown

### 11.1 MVP Architecture (Phase 0)

**Goal:** A working prototype that demonstrates the core loop: change parameters in the browser, see the plane update in real time via CadQuery backend, export STL for 3D printing. **Docker local only (`docker run`).**

**Includes:**

**Deployment:**
- Multi-stage Dockerfile (frontend build + Python runtime)
- `docker run -p 8000:8000 -v ~/.cheng:/data cheng` as the primary launch method
- `docker-compose.yml` for development (backend + frontend hot reload)
- `CHENG_MODE=local` only (cloud mode deferred)

**Backend (Python):**
- FastAPI server with WebSocket endpoint
- Stateless design: all state in frontend Zustand store, backend is a pure function
- Pydantic models for AircraftDesign (simplified: wing + fuselage + tail only)
- CadQuery geometry generation (thread-safe via `anyio.to_thread.run_sync()`):
  - Wing: 2-section loft (root + tip airfoils), NACA 4-digit generator
  - Fuselage: Loft between 3-5 rounded-rect cross-sections
  - Tail: Conventional and V-tail only (simple trapezoidal surfaces)
- Tessellation and binary mesh transfer via WebSocket
- STL export endpoint (single file, normal quality, in-memory generation)
- `StorageBackend` interface with `LocalFileStorage` implementation
- Save/load .cheng JSON files to `/data/designs/` (Docker volume mount)
- Basic derived values: wing area, aspect ratio, estimated CG
- Layer 1+2 validation only (parameter ranges, geometric consistency)
- OpenCascade preload on startup (lifespan event)

**Frontend (React + TypeScript):**
- Vite + React + TypeScript project
- Zustand design store (no undo/redo yet)
- Three.js viewport via React Three Fiber:
  - Renders mesh data received from backend
  - Orbit controls (pan, zoom, rotate)
  - Component click-to-select with yellow highlight
  - Basic dimension annotations (wingspan, fuselage length)
- Right panel: Global Parameters (fuselage type, engines, span, chord, tail type)
- Bottom-left panel: Component-specific parameters (appears on selection)
- WebSocket connection to backend with debounced param updates
- Connection retry with exponential backoff (handles container startup delay)

**Deferred to later phases:**
- Cloud Run deployment (CHENG_MODE=cloud)
- Browser IndexedDB storage
- Undo/redo
- Multiple wing sections (> 2)
- Control surfaces
- Landing gear
- Propulsion configuration
- Print sectioning and assembly joints
- DXF/STEP export
- Layer 3+4 validation
- Desktop packaging (PyInstaller)
- Plugins

**Estimated scope:**
- Backend: ~12 Python files, ~2500 lines (includes storage abstraction + Dockerfile)
- Frontend: ~17 TypeScript files, ~3000 lines (includes connection retry logic)
- DevOps: Dockerfile, docker-compose.yml, .dockerignore

### 11.2 Version 1.0 Architecture

**Goal:** A complete, polished tool that an RC hobbyist can use to design, section, print, and assemble an RC plane. **Adds Cloud Run deployment option.**

**Adds on top of MVP:**

**Deployment:**
- `CHENG_MODE=cloud` support: same Docker image deployed to Google Cloud Run
- `BrowserStorage` backend: frontend saves designs to IndexedDB
- Cloud Run configuration: 2Gi memory, scale-to-zero, concurrency=4
- `gcloud run deploy` or Cloud Build deployment pipeline
- Artifact Registry for container image hosting
- `min-instances=1` option for warm container

**Backend:**
- Full geometry pipeline:
  - Multi-section wing lofting with smooth interpolation between airfoils
  - Fuselage cross-section lofting with nose/tail fairing (ogive, rounded, etc.)
  - Control surface boolean cutouts (aileron, elevator, rudder, flap)
  - All tail configurations (conventional, T-tail, V-tail, cruciform, H-tail)
  - Shell operation for hollow sections (wall thickness)
- 3D print sectioning engine:
  - Automatic part splitting based on print bed dimensions
  - Tab-slot / dowel / tongue-groove joint generation
  - Spar channel cutting (for carbon rod reinforcement)
  - Print orientation hints per part
- Full validation engine (all 4 layers including printability)
- STEP export (in-memory, streamed as HTTP response)
- DXF export (2D rib/former profiles)
- Airfoil database: 50+ bundled profiles with search
- Design templates: 5+ presets
- Concurrent generation with cancellation (thread-safe CadQuery)
- `/api/design/validate` endpoint for cloud mode

**Frontend:**
- Undo/redo (Zundo middleware)
- Print preview mode: see sectioning planes, joint features, spar channels
- Derived values panel: wing area, AR, MAC, CG, tail volumes, print stats
- Keyboard shortcuts
- Design templates gallery
- Export dialog with STL quality and part selection options
- IndexedDB storage layer for cloud mode (save/load/list designs)
- "Backend loading" indicator for cold start handling

**Packaging:**
- Docker image published to Artifact Registry (primary distribution)
- `pip install cheng` (published to PyPI, alternative for non-Docker users)
- Single `cheng serve` command
- Optional: PyInstaller standalone executable for Windows/macOS

**Estimated scope:**
- Backend: ~35 Python files, ~7000 lines (includes storage abstraction, cloud endpoints)
- Frontend: ~45 TypeScript files, ~9000 lines (includes IndexedDB layer, cold start UI)

### 11.3 Future Architecture (Phase 2+)

**Goal:** An extensible platform with community features and advanced simulation.

**Additions:**
- **GCS storage for shared/published designs**: Users can publish designs to a Google Cloud Storage bucket. Public gallery of community designs with search and filtering.
- **Authentication for cloud mode**: Google OAuth or Firebase Auth. User accounts with personal design libraries stored in GCS.
- Plugin system (Python plugin loading, pip-installable plugins)
- Slicer integration: generate per-part slicer profiles (PrusaSlicer, Cura, OrcaSlicer)
- Community template sharing (public gallery backed by GCS)
- 3MF export (multi-part assemblies with color)
- Structural simulation hooks (beam model for wing spar analysis)
- Performance simulation (drag polar estimation, thrust curves, flight envelope)
- Multi-language support (i18n)
- Collaboration: shared design sessions (WebSocket multi-client, Cloud Run with session affinity)
- Build log generator: step-by-step 3D print assembly instructions
- Material database with weight/strength properties
- G-code preview (show print paths per part)
- CDN for static frontend assets (Cloud CDN or Cloudflare)

---

## Appendix A: Project Directory Structure

```
cheng/
├── Dockerfile                        # Multi-stage build (frontend + Python runtime)
├── docker-compose.yml                # Local dev: backend + frontend hot reload
├── .dockerignore                     # Exclude node_modules, __pycache__, etc.
│
├── docs/
│   └── architecture.md              # This document
│
├── backend/                          # Python backend
│   ├── __init__.py
│   ├── __main__.py                  # Entry point: `python -m cheng.backend`
│   ├── server.py                    # FastAPI app creation, lifespan (OCC preload)
│   │
│   ├── models/                      # Pydantic data models (source of truth)
│   │   ├── __init__.py
│   │   ├── aircraft.py              # AircraftDesign and all sub-models
│   │   ├── airfoil.py               # AirfoilProfile, sources
│   │   ├── derived.py               # DerivedValues model
│   │   └── migration.py             # File format versioning
│   │
│   ├── geometry/                    # CadQuery geometry generation
│   │   ├── __init__.py
│   │   ├── airfoil.py               # NACA generators, DAT file parser
│   │   ├── wing.py                  # Wing lofting, control surface cuts
│   │   ├── fuselage.py              # Fuselage lofting, shell
│   │   ├── tail.py                  # Tail configurations
│   │   ├── assembly.py              # Position all components
│   │   ├── sectioning.py            # 3D print part splitting
│   │   ├── joints.py                # Tab-slot, dowel, spar channel
│   │   └── tessellation.py          # B-rep → triangle mesh for preview
│   │
│   ├── api/                         # FastAPI routes
│   │   ├── __init__.py
│   │   ├── routes.py                # REST endpoints (export, save/load)
│   │   ├── websocket.py             # WebSocket handler (real-time preview)
│   │   └── serialization.py         # Binary mesh packing/unpacking
│   │
│   ├── validation/                  # Validation engine
│   │   ├── __init__.py
│   │   ├── engine.py                # Rule runner
│   │   ├── geometric.py             # Layer 2 rules
│   │   ├── aerodynamic.py           # Layer 3 rules
│   │   ├── printability.py          # Layer 4 rules
│   │   └── computations.py          # CG, MAC, tail volume, etc.
│   │
│   ├── storage/                     # Storage abstraction layer
│   │   ├── __init__.py
│   │   ├── base.py                  # StorageBackend ABC interface
│   │   ├── local.py                 # LocalFileStorage (filesystem, Docker volume)
│   │   └── browser.py               # BrowserStorage (no-op, cloud mode)
│   │
│   ├── export/                      # Export pipeline
│   │   ├── __init__.py
│   │   ├── stl.py                   # STL exporter (in-memory)
│   │   ├── step.py                  # STEP exporter (in-memory)
│   │   └── dxf.py                   # DXF flat pattern exporter
│   │
│   ├── data/                        # Static data (bundled in Docker image, read-only)
│   │   ├── airfoils/                # Bundled airfoil .dat files
│   │   └── templates/               # Design templates (JSON)
│   │
│   └── plugins/                     # Plugin system (Phase 2+)
│       ├── __init__.py
│       └── base.py                  # Plugin ABC interfaces
│
├── frontend/                         # React frontend
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── biome.json
│   │
│   └── src/
│       ├── main.tsx                 # App entry point
│       ├── App.tsx                  # Root layout
│       │
│       ├── models/                  # TypeScript interfaces (mirror of Pydantic)
│       │   ├── aircraft.ts
│       │   └── derived.ts
│       │
│       ├── stores/                  # Zustand stores
│       │   ├── designStore.ts       # Aircraft params + backend mesh data
│       │   ├── uiStore.ts           # Selection, view, panel visibility
│       │   └── defaults.ts          # Default aircraft configurations
│       │
│       ├── api/                     # Backend communication
│       │   ├── websocket.ts         # WebSocket client + binary mesh parsing
│       │   ├── http.ts              # REST client (export, save/load)
│       │   └── connection.ts        # Connection retry with exponential backoff
│       │
│       ├── storage/                 # Client-side persistence (cloud mode)
│       │   └── indexedDB.ts         # IndexedDB wrapper for designs + custom airfoils
│       │
│       ├── viewport/                # Three.js / R3F viewport
│       │   ├── Viewport.tsx         # Canvas + camera + controls
│       │   ├── AircraftScene.tsx    # Scene graph (meshes from backend)
│       │   ├── ComponentMesh.tsx    # Single component mesh renderer
│       │   ├── SelectionHighlight.tsx
│       │   ├── DimensionOverlay.tsx
│       │   ├── PrintSectionViz.tsx  # Print section boundaries + joints
│       │   └── materials.ts         # Shared material definitions
│       │
│       ├── panels/                  # UI panels
│       │   ├── GlobalParamsPanel.tsx
│       │   ├── ComponentParamsPanel.tsx
│       │   ├── WingParams.tsx
│       │   ├── TailParams.tsx
│       │   ├── FuselageParams.tsx
│       │   ├── PropulsionParams.tsx
│       │   ├── PrintSettingsPanel.tsx
│       │   ├── DerivedValuesPanel.tsx
│       │   └── ValidationPanel.tsx
│       │
│       ├── components/              # Reusable UI components
│       │   ├── ParameterSlider.tsx
│       │   ├── ParameterDropdown.tsx
│       │   ├── PanelHeader.tsx
│       │   └── Toolbar.tsx
│       │
│       └── utils/
│           ├── units.ts             # Unit conversion
│           ├── math.ts              # Clamp, lerp
│           └── caseConvert.ts       # snake_case <-> camelCase
│
├── pyproject.toml                   # Python project config (uv/pip)
├── README.md
└── LICENSE
```

---

## Appendix B: API Reference

### WebSocket Protocol (`ws://localhost:8000/ws`)

**Client → Server:**
```json
{
  "type": "update_design",
  "design": { /* full AircraftDesign JSON */ }
}
```

**Server → Client (JSON messages):**
```json
{ "type": "derived_values", "values": { /* DerivedValues */ } }
{ "type": "validation", "messages": [ /* ValidationMessage[] */ ] }
{ "type": "generation_time", "ms": 142.5 }
{ "type": "error", "message": "..." }
```

**Server → Client (Binary messages):**
```
Byte layout:
[0]       uint8   component_id  (0=fuselage, 1=wing, 2=tail, 3=gear)
[1..4]    uint32  vertex_count  (little-endian)
[5..8]    uint32  face_count    (little-endian)
[9..]     float32 vertices      (vertex_count * 3 floats: x,y,z,x,y,z,...)
[..]      uint32  faces         (face_count * 3 uints: i,j,k,i,j,k,...)
```

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/export/stl` | Export STL (body: design + options) |
| `POST` | `/api/export/step` | Export STEP (body: design) |
| `POST` | `/api/export/dxf` | Export DXF flat patterns (body: design) |
| `POST` | `/api/design/save` | Save design to local filesystem |
| `POST` | `/api/design/load` | Load design from uploaded file |
| `GET` | `/api/designs` | List saved designs |
| `GET` | `/api/airfoils` | List available airfoils |
| `GET` | `/api/airfoils/{id}` | Get airfoil profile data |
| `GET` | `/api/templates` | List design templates |
| `GET` | `/api/health` | Backend health check |

---

## Appendix C: Key Formulas Reference

### Wing Area (trapezoidal approximation)
```
S = sum over sections i of: 0.5 * (chord[i] + chord[i+1]) * (span[i+1] - span[i]) * halfspan
```

### Mean Aerodynamic Chord
```
MAC = (2/3) * rootChord * (1 + taper + taper^2) / (1 + taper)
where taper = tipChord / rootChord
```

### Aspect Ratio
```
AR = span^2 / wingArea
```

### Horizontal Tail Volume Coefficient
```
V_h = (S_h * l_h) / (S_w * MAC)
where S_h = horizontal tail area, l_h = moment arm, S_w = wing area
Target: 0.35 - 0.70 for trainers
```

### Vertical Tail Volume Coefficient
```
V_v = (S_v * l_v) / (S_w * span)
where S_v = vertical tail area, l_v = moment arm
Target: 0.02 - 0.05 for trainers
```

### Reynolds Number
```
Re = (V * chord) / nu
where V = airspeed (m/s), nu = 1.46e-5 m^2/s (air at 20C)
Typical RC: Re = 50,000 - 500,000
```

### CG Position (rule of thumb)
```
CG should be at 25-33% of MAC from leading edge for conventional tail
CG should be at 15-25% of MAC for canard configurations
```

### 3D Print Weight Estimate
```
weight_grams = volume_mm3 * density_g_per_mm3 * (infill_pct/100 * fill_factor + shell_factor)
For PLA: density = 0.00124 g/mm^3
fill_factor ~ 0.8 (accounts for infill pattern efficiency)
shell_factor = wall_area * wall_thickness * density
```

---

## Appendix D: Technology Version Targets

| Technology | Version | Layer | Notes |
|------------|---------|-------|-------|
| Docker | 24+ | DevOps | Container runtime, multi-stage build |
| docker-compose | 2.x | DevOps | Local development orchestration |
| Google Cloud Run | v2 | DevOps | Cloud deployment target |
| gcloud CLI | 400+ | DevOps | Cloud Run deployment |
| Python | 3.11+ | Backend | Required for CadQuery |
| CadQuery | 2.4+ | Backend | Parametric CAD kernel |
| FastAPI | 0.115+ | Backend | HTTP/WS server |
| Pydantic | 2.x | Backend | Model validation |
| uvicorn | 0.30+ | Backend | ASGI server |
| anyio | 4.x | Backend | Thread-safe async CadQuery execution |
| uv | 0.5+ | Backend | Package manager |
| Ruff | 0.8+ | Backend | Lint + format |
| pytest | 8.x | Backend | Testing |
| Node.js | 22 LTS | Frontend | Build tooling |
| React | 19.x | Frontend | UI framework |
| TypeScript | 5.7+ | Frontend | Type safety |
| Three.js | r170+ | Frontend | 3D rendering |
| @react-three/fiber | 9.x | Frontend | React + Three.js |
| @react-three/drei | 9.x | Frontend | R3F helpers |
| Zustand | 5.x | Frontend | State management |
| Zundo | 2.x | Frontend | Undo/redo |
| Immer | 10.x | Frontend | Immutable updates |
| idb | 8.x | Frontend | IndexedDB wrapper (cloud mode storage) |
| Tailwind CSS | 4.x | Frontend | Styling |
| Radix UI | 1.x | Frontend | UI primitives |
| Vite | 6.x | Frontend | Build tooling |
| Biome | 1.x | Frontend | Lint + format |
| pnpm | 9.x | Frontend | Package manager |
