# Parametric RC Plane Generator - Implementation Specification

## Architecture Overview

This is a **containerized web application** with a Python backend and browser-based frontend, deployable both locally via Docker and to Google Cloud Run for multi-user access. The architecture supports two modes: **local** (single user, Docker Compose) and **cloud** (multi-user, Cloud Run).

The primary fabrication method is **FDM 3D printing**. STL is the primary export. All geometry is designed with 3D printability in mind: wall thickness constraints, print orientation guidance, assembly connectors between sectioned parts, and print bed size limits.

```
+--------------------------------------------------+
|  BROWSER (Frontend)                               |
|  +----------------------------------------------+|
|  | React + Three.js + Zustand                    ||
|  | - UI panels (params, component detail, etc.)  ||
|  | - 3D viewport (Three.js, preview mesh)        ||
|  | - SVG annotation overlays                     ||
|  | - IndexedDB autosave (cloud mode)             ||
|  +----------------------------------------------+|
|          |  HTTP REST + WebSocket  |               |
+----------|-------------------------|---------------+
           v                         v
+--------------------------------------------------+
|  DOCKER CONTAINER                                 |
|  +----------------------------------------------+|
|  | FastAPI (stateless backend)                   ||
|  |  - REST: /api/generate, /api/export, etc.    ||
|  |  - WebSocket: /ws/preview (streaming mesh)   ||
|  |  - Health: /health (Cloud Run probes)        ||
|  |  - CHENG_MODE: local | cloud                 ||
|  |                                               ||
|  | CadQuery (OpenCascade kernel)                 ||
|  |  - Parametric solid geometry                  ||
|  |  - NURBS lofting, splines, Boolean ops        ||
|  |  - STL tessellation + export                  ||
|  |  - STEP export (CAD interchange)              ||
|  |  - Thread-safe via anyio.to_thread            ||
|  +----------------------------------------------+|
|  | Static files: ./static/ served at /            ||
+--------------------------------------------------+
           |                         |
     [local mode]             [cloud mode]
     Docker volume            Cloud Run
     /data/ persist           Stateless (no persist)
```

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend Runtime** | Python 3.11+ | CadQuery requirement |
| **CAD Kernel** | CadQuery 2.x (OpenCascade) | Real parametric CAD: NURBS, lofting, Boolean ops, proper STL export |
| **Backend Framework** | FastAPI | Async, WebSocket support, auto-generated OpenAPI docs |
| **Mesh Transfer** | WebSocket (binary) | Stream tessellated mesh to browser in real time |
| **Frontend Bundler** | Vite | Fast HMR, native TS support |
| **Frontend Language** | TypeScript (strict mode) | Type safety for UI and Three.js code |
| **3D Preview** | Three.js | Renders tessellated mesh received from backend |
| **UI Framework** | React 18+ | Component model fits panel architecture |
| **State Management** | Zustand | Lightweight, middleware for undo/redo |
| **Styling** | Tailwind CSS | Utility-first, easy dark theme |
| **Testing** | pytest (backend) + Vitest + Playwright (frontend) | Full stack coverage |
| **Containerization** | Docker (multi-stage build) | Reproducible builds, OpenCascade deps bundled |
| **Orchestration (local)** | Docker Compose | Single-command local dev with hot reload |
| **Deployment (cloud)** | Google Cloud Run | Serverless containers, scale-to-zero, WebSocket support |
| **Storage (local)** | Docker volume at `/data/` | Persistent design storage across restarts |
| **Storage (cloud)** | IndexedDB (browser) | No server-side state, autosave in browser |

---

## 0. DOCKER CONTAINERIZATION & DEPLOYMENT

### 0.1 Dockerfile (Multi-Stage Build)

The application is packaged as a single Docker image with a multi-stage build: the frontend is compiled in a Node.js stage, and the resulting static assets are copied into the Python runtime stage.

```dockerfile
# Dockerfile

# Stage 1: Build frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: Python runtime with CadQuery
FROM python:3.11-slim
# Install OpenCascade dependencies
RUN apt-get update && apt-get install -y libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./static/
COPY airfoils/ ./airfoils/
ENV CHENG_MODE=local
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key decisions:
- **`node:22-alpine`** for the frontend build keeps the build stage small.
- **`python:3.11-slim`** for runtime avoids the full Debian image bloat while still providing `apt-get` for OpenCascade system dependencies (`libgl1-mesa-glx`, `libglib2.0-0`).
- Frontend `dist/` is copied to `./static/` and served by FastAPI's `StaticFiles` mount.
- `airfoils/` directory is copied for the built-in airfoil database.
- `CHENG_MODE=local` is the default; Cloud Run deployments override this to `cloud`.

### 0.2 docker-compose.yml (Local Development)

For local development, Docker Compose runs the backend container with hot-reload volumes and a separate frontend dev server with Vite HMR:

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    ports: ["8000:8000"]
    volumes: ["./backend:/app/backend", "cheng-data:/data"]
    environment: ["CHENG_MODE=local"]
  frontend:
    image: node:22-alpine
    working_dir: /app
    volumes: ["./frontend:/app"]
    ports: ["5173:5173"]
    command: sh -c "corepack enable && pnpm dev --host"
volumes:
  cheng-data:
```

- **`backend`**: Mounts `./backend` for live code changes (uvicorn `--reload` can be added). The `cheng-data` named volume at `/data/` persists saved designs across container restarts.
- **`frontend`**: Runs the Vite dev server with HMR on port 5173. During development the browser connects to the frontend dev server, which proxies API requests to the backend.
- **Production**: A single `docker build . && docker run -p 8000:8000` serves everything (frontend static files baked into the image).

### 0.3 Cloud Run Deployment

#### Build and Push

```bash
# Build the production image
docker build -t gcr.io/PROJECT/cheng .

# Push to Google Container Registry
docker push gcr.io/PROJECT/cheng
```

#### Deploy to Cloud Run

```bash
gcloud run deploy cheng \
  --image gcr.io/PROJECT/cheng \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars CHENG_MODE=cloud
```

#### Cloud Run Service Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Memory** | 2Gi | CadQuery/OpenCascade needs ~500MB-1GB for complex loft operations |
| **CPU** | 2 | Parallel geometry generation for multiple components |
| **Min instances** | 0 | Scale to zero when idle (cost savings) |
| **Max instances** | 10 | Handles concurrent users; each instance serves ~10 users |
| **Concurrency** | 10 | Multiple users per container (CadQuery ops are ~500ms, not long-blocking) |
| **Request timeout** | 3600s | WebSocket connections for real-time preview need long-lived connections |
| **Health check** | `GET /health` | Cloud Run startup and liveness probes hit the `/health` endpoint |

#### Cloud Run Considerations

- **Stateless**: No design state is stored server-side in cloud mode. The frontend Zustand store holds all state, and autosave goes to IndexedDB in the browser.
- **Cold start**: First request to a new instance takes ~5-10s (Python + CadQuery import). Mitigated by `--min-instances 1` for production if cold start latency is unacceptable.
- **WebSocket**: Cloud Run supports WebSocket connections with the 3600s timeout. The `/ws/preview` endpoint works without modification.
- **No persistent storage**: Export endpoints return `StreamingResponse` directly (no temp files on disk). In cloud mode, the `MemoryStorage` backend streams results back to the client without writing to disk.

---

## 1. VIEWPORT / RENDERING ENGINE

The viewport renders a **preview mesh** received from the Python backend. The backend (CadQuery) generates the true parametric solid, tessellates it, and streams the triangle mesh to the browser over WebSocket. Three.js simply displays this mesh.

### 1.1 Scene Setup

Use Three.js with an **orthographic camera** for the primary top-down view. The viewport occupies the central area of the layout (roughly 60% width, full height minus bottom panel).

```typescript
// frontend/src/viewport/SceneManager.ts
import * as THREE from 'three';

export class SceneManager {
  scene: THREE.Scene;
  camera: THREE.OrthographicCamera;
  renderer: THREE.WebGLRenderer;
  componentGroups: Map<string, THREE.Group> = new Map();

  constructor(container: HTMLDivElement) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x2a2a2e);

    // Orthographic camera: frustum sized to fit aircraft + margins
    const aspect = container.clientWidth / container.clientHeight;
    const frustumHeight = 500; // mm, covers typical RC plane
    const frustumWidth = frustumHeight * aspect;
    this.camera = new THREE.OrthographicCamera(
      -frustumWidth / 2, frustumWidth / 2,
      frustumHeight / 2, -frustumHeight / 2,
      0.1, 1000
    );
    // Top-down: camera looks down -Y axis
    this.camera.position.set(0, 500, 0);
    this.camera.up.set(0, 0, -1); // nose points up on screen
    this.camera.lookAt(0, 0, 0);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(this.renderer.domElement);

    // Ambient + directional light for shading
    this.scene.add(new THREE.AmbientLight(0x404040, 1.5));
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(0, 500, 200);
    this.scene.add(dirLight);
  }

  /** Replace mesh for a specific component with data from backend */
  updateComponentMesh(componentId: string, meshData: MeshData) {
    // Remove old group
    const existing = this.componentGroups.get(componentId);
    if (existing) this.scene.remove(existing);

    const group = new THREE.Group();
    group.userData.componentId = componentId;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(meshData.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(meshData.normals, 3));
    geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(meshData.indices), 1));

    const material = new THREE.MeshStandardMaterial({
      color: 0x8899aa,
      roughness: 0.6,
      metalness: 0.1,
    });
    const mesh = new THREE.Mesh(geometry, material);
    group.add(mesh);

    this.scene.add(group);
    this.componentGroups.set(componentId, group);
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }
}

interface MeshData {
  positions: Float32Array;
  normals: Float32Array;
  indices: number[];
}
```

### 1.2 Zoom and Pan

Implement custom zoom/pan on the orthographic camera (not OrbitControls, which adds unwanted rotation):

```typescript
// frontend/src/viewport/PanZoomControls.ts
export class PanZoomControls {
  private zoomLevel = 1;
  private panOffset = new THREE.Vector2(0, 0);
  private isDragging = false;
  private lastMouse = new THREE.Vector2();

  constructor(
    private camera: THREE.OrthographicCamera,
    private domElement: HTMLElement,
    private onUpdate: () => void
  ) {
    domElement.addEventListener('wheel', this.onWheel, { passive: false });
    domElement.addEventListener('pointerdown', this.onPointerDown);
    domElement.addEventListener('pointermove', this.onPointerMove);
    domElement.addEventListener('pointerup', this.onPointerUp);
  }

  private onWheel = (e: WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
    this.zoomLevel *= zoomFactor;
    this.zoomLevel = Math.max(0.1, Math.min(10, this.zoomLevel));
    this.applyZoom();
  };

  private applyZoom() {
    const aspect = this.domElement.clientWidth / this.domElement.clientHeight;
    const halfH = 250 * this.zoomLevel;
    const halfW = halfH * aspect;
    this.camera.left = -halfW + this.panOffset.x;
    this.camera.right = halfW + this.panOffset.x;
    this.camera.top = halfH + this.panOffset.y;
    this.camera.bottom = -halfH + this.panOffset.y;
    this.camera.updateProjectionMatrix();
    this.onUpdate();
  }

  // Middle-mouse or right-mouse drag for pan
  private onPointerDown = (e: PointerEvent) => {
    if (e.button === 1 || e.button === 2) {
      this.isDragging = true;
      this.lastMouse.set(e.clientX, e.clientY);
      this.domElement.setPointerCapture(e.pointerId);
    }
  };

  private onPointerMove = (e: PointerEvent) => {
    if (!this.isDragging) return;
    const dx = e.clientX - this.lastMouse.x;
    const dy = e.clientY - this.lastMouse.y;
    const worldPerPixel = (this.camera.right - this.camera.left) / this.domElement.clientWidth;
    this.panOffset.x -= dx * worldPerPixel;
    this.panOffset.y += dy * worldPerPixel;
    this.lastMouse.set(e.clientX, e.clientY);
    this.applyZoom();
  };

  private onPointerUp = () => {
    this.isDragging = false;
  };

  dispose() {
    this.domElement.removeEventListener('wheel', this.onWheel);
    this.domElement.removeEventListener('pointerdown', this.onPointerDown);
    this.domElement.removeEventListener('pointermove', this.onPointerMove);
    this.domElement.removeEventListener('pointerup', this.onPointerUp);
  }
}
```

### 1.3 Component Hit-Testing and Selection

Use `THREE.Raycaster` on pointer events. Each aircraft component group has a `componentId` in its `userData`.

```typescript
// frontend/src/viewport/SelectionManager.ts
export type ComponentId = 'fuselage' | 'wing-left' | 'wing-right' | 'tail' | 'engine-left' | 'engine-right';

export class SelectionManager {
  private raycaster = new THREE.Raycaster();
  private mouse = new THREE.Vector2();
  hoveredComponent: ComponentId | null = null;
  selectedComponent: ComponentId | null = null;

  constructor(
    private camera: THREE.OrthographicCamera,
    private scene: THREE.Scene,
    private domElement: HTMLElement,
    private onSelectionChange: (id: ComponentId | null) => void,
    private onHoverChange: (id: ComponentId | null) => void
  ) {
    domElement.addEventListener('pointermove', this.onMove);
    domElement.addEventListener('click', this.onClick);
  }

  private pickComponent(e: PointerEvent): ComponentId | null {
    const rect = this.domElement.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.scene.children, true);
    for (const hit of intersects) {
      let obj: THREE.Object3D | null = hit.object;
      while (obj && !obj.userData.componentId) obj = obj.parent;
      if (obj?.userData.componentId) return obj.userData.componentId;
    }
    return null;
  }

  private onMove = (e: PointerEvent) => {
    const id = this.pickComponent(e);
    if (id !== this.hoveredComponent) {
      this.hoveredComponent = id;
      this.onHoverChange(id);
    }
  };

  private onClick = (e: PointerEvent) => {
    if (e.button !== 0) return;
    const id = this.pickComponent(e);
    this.selectedComponent = id;
    this.onSelectionChange(id);
  };
}
```

### 1.4 Highlight Rendering

Two highlight states visible in the mockups:
- **Hover (pre-selection)**: subtle brightness increase via emissive color
- **Selected**: yellow tint (matches mockup screenshots where wing/tail glow yellow)

```typescript
// frontend/src/viewport/HighlightManager.ts
const HIGHLIGHT_YELLOW = new THREE.Color(0xffdd00);
const HOVER_EMISSIVE = new THREE.Color(0x222222);
const DEFAULT_EMISSIVE = new THREE.Color(0x000000);

export function applyHighlight(
  group: THREE.Group,
  state: 'none' | 'hover' | 'selected'
) {
  group.traverse((child) => {
    if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshStandardMaterial) {
      const mat = child.material as THREE.MeshStandardMaterial;
      switch (state) {
        case 'none':
          mat.emissive.copy(DEFAULT_EMISSIVE);
          mat.emissiveIntensity = 1.0;
          break;
        case 'hover':
          mat.emissive.copy(HOVER_EMISSIVE);
          mat.emissiveIntensity = 1.0;
          break;
        case 'selected':
          mat.emissive.copy(HIGHLIGHT_YELLOW);
          mat.emissiveIntensity = 0.4;
          break;
      }
    }
  });
}
```

### 1.5 Dimension Annotation Overlays

The mockups show dimension annotations (300.00mm, 190.00mm, SWEEP: 25 deg) as thin white lines with text overlaid on the viewport. Use an **SVG overlay** positioned absolutely on top of the Three.js canvas.

Rationale: SVG gives crisp text at any zoom, easy leader-line drawing with `<line>` and `<text>`, and DOM-based hit testing for click-to-edit.

```typescript
// frontend/src/viewport/annotations/AnnotationOverlay.tsx
interface Annotation {
  id: string;
  type: 'linear' | 'angle';
  /** World-space endpoints (mm) */
  startWorld: [number, number];
  endWorld: [number, number];
  /** For angle type: arc center and two ray endpoints */
  arcCenter?: [number, number];
  label: string;
  offset: number; // pixels offset from geometry edge
}

function worldToScreen(
  point: [number, number],
  camera: THREE.OrthographicCamera,
  containerRect: DOMRect
): [number, number] {
  const v = new THREE.Vector3(point[0], 0, point[1]);
  v.project(camera);
  return [
    (v.x + 1) / 2 * containerRect.width,
    (-v.y + 1) / 2 * containerRect.height,
  ];
}

export const AnnotationOverlay: React.FC<{
  annotations: Annotation[];
  camera: THREE.OrthographicCamera;
  containerRef: React.RefObject<HTMLDivElement>;
}> = ({ annotations, camera, containerRef }) => {
  const rect = containerRef.current?.getBoundingClientRect();
  if (!rect) return null;

  return (
    <svg className="absolute inset-0 pointer-events-none" width={rect.width} height={rect.height}>
      {annotations.map((ann) => {
        if (ann.type === 'linear') {
          const [sx, sy] = worldToScreen(ann.startWorld, camera, rect);
          const [ex, ey] = worldToScreen(ann.endWorld, camera, rect);
          const mx = (sx + ex) / 2;
          const my = (sy + ey) / 2;
          return (
            <g key={ann.id}>
              <line x1={sx} y1={sy} x2={ex} y2={ey} stroke="#888" strokeWidth={1} />
              <line x1={sx} y1={sy - 4} x2={sx} y2={sy + 4} stroke="#888" strokeWidth={1} />
              <line x1={ex} y1={ey - 4} x2={ex} y2={ey + 4} stroke="#888" strokeWidth={1} />
              <text x={mx} y={my - 6} fill="#ccc" fontSize={12} textAnchor="middle" fontFamily="monospace">
                {ann.label}
              </text>
            </g>
          );
        }
        if (ann.type === 'angle' && ann.arcCenter) {
          const [cx, cy] = worldToScreen(ann.arcCenter, camera, rect);
          const [sx, sy] = worldToScreen(ann.startWorld, camera, rect);
          const [ex, ey] = worldToScreen(ann.endWorld, camera, rect);
          const r = Math.hypot(sx - cx, sy - cy);
          return (
            <g key={ann.id}>
              <path
                d={`M ${sx} ${sy} A ${r} ${r} 0 0 1 ${ex} ${ey}`}
                fill="none" stroke="#888" strokeWidth={1} strokeDasharray="4 2"
              />
              <text x={(sx + ex) / 2} y={(sy + ey) / 2 - 6}
                fill="#ccc" fontSize={11} textAnchor="middle" fontFamily="monospace">
                {ann.label}
              </text>
            </g>
          );
        }
        return null;
      })}
    </svg>
  );
};
```

Annotations are recomputed from **derived dimension data** returned by the backend alongside each geometry update. The backend computes bounding boxes, span, length, and sweep angle, then the frontend positions annotations using `worldToScreen`.

### 1.6 Scene Graph for Different Aircraft Configurations

```
Scene
 +-- fuselageGroup (userData.componentId = 'fuselage')
 +-- wingGroup
 |    +-- wingLeftGroup  (userData.componentId = 'wing-left')
 |    +-- wingRightGroup (userData.componentId = 'wing-right')
 +-- tailGroup (userData.componentId = 'tail')
 |    // Mesh shape depends on tail type (conventional, V-tail, T-tail)
 |    // Backend sends different mesh data per configuration
 +-- engineGroup
      +-- engineLeftGroup  (userData.componentId = 'engine-left')
      +-- engineRightGroup (userData.componentId = 'engine-right')
```

When configuration changes, the backend regenerates the affected component's solid and sends a new tessellated mesh. The frontend replaces the old mesh in the corresponding group. No geometry logic on the frontend -- it only displays what the backend sends.

---

## 2. PARAMETRIC GEOMETRY ENGINE (CadQuery Backend)

All geometry generation runs on the **Python backend** using CadQuery (OpenCascade kernel). This provides real NURBS-based parametric CAD operations: lofting, sweeping, Boolean operations, shelling, filleting, and high-quality STL tessellation.

All dimensions are in **millimeters**. The coordinate system is: **X = right (starboard), Y = forward (nose direction), Z = up**.

### 2.1 Fuselage

#### Cross-Section Profiles and Lofting

CadQuery's `loft()` connects multiple cross-section wires into a smooth solid. Each cross-section is placed on a workplane at a different Y position along the fuselage axis.

```python
# backend/geometry/fuselage.py
import cadquery as cq
import math
from dataclasses import dataclass

@dataclass
class FuselageStation:
    y: float          # position along fuselage axis (mm)
    width: float      # horizontal diameter (mm)
    height: float     # vertical diameter (mm)
    shape: str        # 'ellipse' | 'rounded-rect'
    corner_radius: float = 0.3  # for rounded-rect, 0..1 normalized


@dataclass
class FuselageParams:
    type: str           # 'sport' | 'trainer' | 'racer' | 'pod'
    length: float       # total fuselage length (mm)
    max_width: float
    max_height: float
    nose_fraction: float  # nose length as fraction of total 0..0.3
    tail_fraction: float  # tail taper as fraction of total 0..0.5
    wall_thickness: float  # shell wall thickness for 3D printing (mm), e.g. 1.2


def generate_fuselage_stations(params: FuselageParams) -> list[FuselageStation]:
    """Generate cross-section stations from high-level fuselage params."""
    L = params.length
    stations = []

    # Station positions as fraction of length
    fractions = [0.0, 0.05, 0.15, params.nose_fraction,
                 0.4, 0.6, 0.75, 1.0 - params.tail_fraction, 0.95, 1.0]

    for frac in fractions:
        y = frac * L
        # Width/height envelope: ramp up through nose, hold, taper at tail
        if frac < params.nose_fraction:
            t = frac / params.nose_fraction
            scale = math.sin(t * math.pi / 2)  # smooth sinusoidal ramp
        elif frac > (1.0 - params.tail_fraction):
            t = (frac - (1.0 - params.tail_fraction)) / params.tail_fraction
            scale = math.cos(t * math.pi / 2)
        else:
            scale = 1.0

        w = max(params.max_width * scale, 2.0)  # min 2mm to avoid degenerate
        h = max(params.max_height * scale, 2.0)

        shape = 'rounded-rect' if params.type == 'trainer' else 'ellipse'
        stations.append(FuselageStation(y=y, width=w, height=h, shape=shape))

    return stations


def build_fuselage_solid(params: FuselageParams) -> cq.Workplane:
    """Build the fuselage as a lofted solid using CadQuery."""
    stations = generate_fuselage_stations(params)
    wires = []

    for st in stations:
        if st.shape == 'ellipse':
            wire = (
                cq.Workplane("XZ")
                .workplane(offset=st.y)
                .ellipse(st.width / 2, st.height / 2)
            )
        else:
            # Rounded rectangle using superellipse approximation via CadQuery sketch
            r = st.corner_radius * min(st.width, st.height) / 2
            wire = (
                cq.Workplane("XZ")
                .workplane(offset=st.y)
                .sketch()
                .rect(st.width, st.height)
                .vertices()
                .fillet(r)
                .finalize()
            )
        wires.append(wire)

    # Loft through all cross-sections
    result = wires[0]
    for w in wires[1:]:
        result = result.add(w)
    result = result.loft(ruled=False)

    # Shell for 3D printing (hollow interior, open at tail for electronics access)
    if params.wall_thickness > 0:
        # Shell: remove the tail-most face, keep wall_thickness walls
        result = result.faces(">Y").shell(-params.wall_thickness)

    return result
```

#### Fuselage Type Presets

| Type | Nose Fraction | Tail Fraction | Cross-Section | Notes |
|------|--------------|---------------|---------------|-------|
| `sport` | 0.20 | 0.30 | Ellipse | Rounded nose, gradual taper |
| `trainer` | 0.15 | 0.25 | Rounded-rect | Boxy cabin, gentle lines |
| `racer` | 0.30 | 0.40 | Narrow ellipse | Long nose, aggressive taper |
| `pod` | 0.10 | 0.15 | Ellipse | Short bulge + thin tail boom |

#### 3D Printing Considerations for Fuselage

- **Wall thickness**: `shell()` operation hollows the fuselage with configurable wall thickness (default 1.2mm for FDM)
- **Print orientation**: Fuselage prints upright (nose up) to minimize supports. Flat bottom face added as a base
- **Sectioning**: For fuselages longer than the print bed (typically 220mm), auto-split into sections with alignment pins:

```python
def section_fuselage_for_printing(
    solid: cq.Workplane,
    max_section_length: float = 200.0,  # mm, conservative for 220mm bed
    pin_diameter: float = 3.0,
    pin_depth: float = 5.0,
) -> list[cq.Workplane]:
    """Split fuselage into printable sections with alignment pins."""
    bbox = solid.val().BoundingBox()
    total_length = bbox.ymax - bbox.ymin
    num_sections = math.ceil(total_length / max_section_length)
    section_length = total_length / num_sections

    sections = []
    for i in range(num_sections):
        y_start = bbox.ymin + i * section_length
        y_end = y_start + section_length

        # Cut section using a bounding box
        cutter = (
            cq.Workplane("XZ")
            .workplane(offset=y_start)
            .rect(bbox.xlen + 10, bbox.zlen + 10)
            .extrude(section_length)
        )
        section = solid.intersect(cutter)

        # Add alignment pin holes on the mating face (except first section's front)
        if i > 0:
            # Pin holes on the -Y face
            section = (
                section
                .faces("<Y")
                .workplane()
                .pushPoints([(5, 0), (-5, 0)])
                .hole(pin_diameter, pin_depth)
            )
        if i < num_sections - 1:
            # Pin bosses on the +Y face
            section = (
                section
                .faces(">Y")
                .workplane()
                .pushPoints([(5, 0), (-5, 0)])
                .circle(pin_diameter / 2)
                .extrude(pin_depth)
            )

        sections.append(section)

    return sections
```

### 2.2 Wings

#### Airfoil Profile Handling

Airfoil coordinates are loaded on the backend and used to create CadQuery wires via splines.

```python
# backend/geometry/airfoil.py
import cadquery as cq
from dataclasses import dataclass

@dataclass
class AirfoilProfile:
    name: str
    points: list[tuple[float, float]]  # (x, y) normalized to chord=1.0


def parse_dat_file(content: str) -> AirfoilProfile:
    """Parse Selig-format .dat airfoil file."""
    lines = content.strip().split('\n')
    name = lines[0].strip()
    points = []
    for line in lines[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            try:
                x, y = float(parts[0]), float(parts[1])
                points.append((x, y))
            except ValueError:
                continue
    return AirfoilProfile(name=name, points=points)


def generate_naca4(designation: str, num_points: int = 80) -> AirfoilProfile:
    """Generate NACA 4-digit airfoil coordinates."""
    import math

    m = int(designation[0]) / 100  # max camber
    p = int(designation[1]) / 10   # max camber position
    t = int(designation[2:]) / 100 # max thickness

    def thickness_dist(x: float) -> float:
        return 5 * t * (
            0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2
            + 0.2843 * x**3 - 0.1015 * x**4
        )

    def camber(x: float) -> tuple[float, float]:
        if m == 0 or p == 0:
            return 0.0, 0.0
        if x < p:
            yc = (m / p**2) * (2 * p * x - x**2)
            dyc = (2 * m / p**2) * (p - x)
        else:
            yc = (m / (1 - p)**2) * (1 - 2 * p + 2 * p * x - x**2)
            dyc = (2 * m / (1 - p)**2) * (p - x)
        return yc, dyc

    upper, lower = [], []
    for i in range(num_points + 1):
        beta = i / num_points * math.pi
        x = 0.5 * (1 - math.cos(beta))  # cosine spacing
        yc, dyc = camber(x)
        yt = thickness_dist(x)
        theta = math.atan2(dyc, 1.0)

        upper.append((x - yt * math.sin(theta), yc + yt * math.cos(theta)))
        lower.append((x + yt * math.sin(theta), yc - yt * math.cos(theta)))

    # Combine: upper TE->LE, then lower LE->TE
    points = list(reversed(upper)) + lower[1:]
    return AirfoilProfile(name=f"NACA {designation}", points=points)


def airfoil_to_wire(profile: AirfoilProfile, chord: float, workplane: cq.Workplane) -> cq.Workplane:
    """Convert airfoil profile to a CadQuery wire (closed spline) on the given workplane."""
    # Scale points to chord length
    scaled = [(p[0] * chord, p[1] * chord) for p in profile.points]

    # Create closed spline through airfoil points
    # CadQuery spline takes list of (x, y) tuples on the current workplane
    result = workplane.spline(scaled, includeCurrent=False).close()
    return result
```

#### Wing Panel Generation with CadQuery Loft

A wing panel is generated by placing airfoil wires at root and tip (and optionally intermediate) stations, then lofting between them.

```python
# backend/geometry/wing.py
import cadquery as cq
import math
from dataclasses import dataclass
from .airfoil import AirfoilProfile, airfoil_to_wire

@dataclass
class WingPanelParams:
    span_length: float       # mm, half-span of this panel
    root_chord: float        # mm
    tip_chord: float         # mm
    sweep_angle: float       # degrees, leading edge sweep
    dihedral_angle: float    # degrees
    twist_angle: float       # degrees (washout at tip)
    root_airfoil: AirfoilProfile
    tip_airfoil: AirfoilProfile
    wall_thickness: float    # mm, for shell (0 = solid)

@dataclass
class WingParams:
    panels: list[WingPanelParams]
    tip_shape: str  # 'square' | 'rounded' | 'elliptical'
    is_symmetric: bool  # mirror left/right


def build_wing_panel(params: WingPanelParams, num_span_sections: int = 6) -> cq.Workplane:
    """Build a single wing panel by lofting airfoil sections along the span."""

    sweep_rad = math.radians(params.sweep_angle)
    dihedral_rad = math.radians(params.dihedral_angle)
    twist_rad = math.radians(params.twist_angle)

    sections = []
    for i in range(num_span_sections + 1):
        t = i / num_span_sections  # 0=root, 1=tip

        # Interpolate chord
        chord = params.root_chord + t * (params.tip_chord - params.root_chord)

        # Spanwise position
        span_pos = t * params.span_length

        # Sweep offset (leading edge moves aft)
        sweep_offset = math.tan(sweep_rad) * span_pos

        # Dihedral offset (vertical)
        dihedral_offset = math.tan(dihedral_rad) * span_pos

        # Twist angle at this station
        twist = twist_rad * t

        # Interpolate airfoil points between root and tip profiles
        interp_points = []
        for j in range(len(params.root_airfoil.points)):
            rx, ry = params.root_airfoil.points[j]
            tx, ty = params.tip_airfoil.points[j]
            x = (rx + t * (tx - rx)) * chord
            y = (ry + t * (ty - ry)) * chord
            # Apply twist around quarter-chord
            qc = chord * 0.25
            dx = x - qc
            x_rot = dx * math.cos(twist) - y * math.sin(twist) + qc
            y_rot = dx * math.sin(twist) + y * math.cos(twist)
            interp_points.append((x_rot, y_rot))

        # Create workplane at this span station
        # Airfoil profile lies in XZ plane, extruded along X (spanwise)
        wp = (
            cq.Workplane("XZ")
            .transformed(
                offset=cq.Vector(span_pos, sweep_offset, dihedral_offset),
            )
        )
        wire = wp.spline(interp_points).close()
        sections.append(wire)

    # Loft through all sections
    result = sections[0]
    for s in sections[1:]:
        result = result.add(s)
    result = result.loft(ruled=False)

    # Shell for 3D printing weight reduction
    if params.wall_thickness > 0:
        result = result.shell(-params.wall_thickness)

    return result


def build_full_wing(params: WingParams) -> cq.Workplane:
    """Build the complete wing (both sides if symmetric)."""
    # Build panels end-to-end
    panels = []
    offset_x = 0.0
    for panel_params in params.panels:
        panel = build_wing_panel(panel_params)
        panel = panel.translate((offset_x, 0, 0))
        panels.append(panel)
        offset_x += panel_params.span_length

    # Combine panels
    result = panels[0]
    for p in panels[1:]:
        result = result.union(p)

    # Mirror for left wing
    if params.is_symmetric:
        mirrored = result.mirror("XZ")
        result = result.union(mirrored)

    return result
```

#### Wing Sectioning for 3D Printing

Wings exceeding the print bed are split into sections with interlocking joints:

```python
def section_wing_for_printing(
    solid: cq.Workplane,
    max_section_span: float = 180.0,  # mm
    joint_type: str = 'dovetail',     # 'dovetail' | 'pin' | 'flat'
) -> list[cq.Workplane]:
    """Split wing into printable sections with assembly joints."""
    bbox = solid.val().BoundingBox()
    total_span = bbox.xmax - bbox.xmin
    num_sections = math.ceil(total_span / max_section_span)
    section_span = total_span / num_sections

    sections = []
    for i in range(num_sections):
        x_start = bbox.xmin + i * section_span
        x_end = x_start + section_span

        # Cut section
        cutter = (
            cq.Workplane("YZ")
            .workplane(offset=x_start)
            .rect(bbox.ylen + 10, bbox.zlen + 10)
            .extrude(section_span)
        )
        section = solid.intersect(cutter)

        if joint_type == 'dovetail':
            # Add dovetail tongue on +X face, slot on -X face
            dt_width = 8.0
            dt_depth = 5.0
            dt_taper = 1.5  # mm wider at base than tip

            if i < num_sections - 1:
                # Tongue on +X face
                tongue = (
                    cq.Workplane("YZ")
                    .workplane(offset=x_end)
                    .sketch()
                    .trapezoid(dt_width, dt_depth, 90 - math.degrees(math.atan(dt_taper / dt_depth)))
                    .finalize()
                    .extrude(dt_depth)
                )
                section = section.union(tongue)

            if i > 0:
                # Slot on -X face (matching dovetail cavity)
                slot = (
                    cq.Workplane("YZ")
                    .workplane(offset=x_start)
                    .sketch()
                    .trapezoid(dt_width + 0.3, dt_depth + 0.15, 90 - math.degrees(math.atan(dt_taper / dt_depth)))
                    .finalize()
                    .extrude(-dt_depth)
                )
                section = section.cut(slot)

        elif joint_type == 'pin':
            pin_d = 3.0
            pin_depth = 5.0
            if i < num_sections - 1:
                section = (
                    section.faces(">X").workplane()
                    .pushPoints([(0, 3), (0, -3)])
                    .circle(pin_d / 2).extrude(pin_depth)
                )
            if i > 0:
                section = (
                    section.faces("<X").workplane()
                    .pushPoints([(0, 3), (0, -3)])
                    .hole(pin_d + 0.2, pin_depth)
                )

        sections.append(section)

    return sections
```

#### Tip Shapes

Applied by modifying the outermost loft section:

- **Square**: No modification (default) -- tip chord airfoil simply terminates flat
- **Rounded**: Final loft section scaled to near-zero chord, creating a rounded cap
- **Elliptical**: Multiple intermediate sections with chord following elliptical profile: `chord(t) = tip_chord * sqrt(1 - t^2)` over the last 10% of span

### 2.3 Tail Surfaces

Tail surfaces reuse the wing panel generation code with different parameters. Each tail configuration is composed differently:

```python
# backend/geometry/tail.py
import cadquery as cq
from dataclasses import dataclass
from .wing import build_wing_panel, WingPanelParams
from .airfoil import AirfoilProfile

@dataclass
class ConventionalTailParams:
    h_stab_span: float
    h_stab_chord: float
    h_stab_airfoil: AirfoilProfile
    h_stab_sweep: float
    v_fin_span: float
    v_fin_chord: float
    v_fin_airfoil: AirfoilProfile
    v_fin_sweep: float
    position_y: float  # distance from nose along fuselage axis
    wall_thickness: float

@dataclass
class VTailParams:
    span: float
    chord: float
    dihedral_angle: float  # typically 30-45 degrees
    airfoil: AirfoilProfile
    sweep_angle: float
    position_y: float
    wall_thickness: float

@dataclass
class TTailParams:
    h_stab_span: float
    h_stab_chord: float
    h_stab_airfoil: AirfoilProfile
    h_stab_sweep: float
    v_fin_span: float
    v_fin_chord: float
    v_fin_airfoil: AirfoilProfile
    v_fin_sweep: float
    position_y: float
    wall_thickness: float


def build_conventional_tail(params: ConventionalTailParams) -> cq.Workplane:
    """Horizontal stabilizer + vertical fin."""
    # Horizontal stab (symmetric airfoil, mirrored)
    h_panel = WingPanelParams(
        span_length=params.h_stab_span / 2,
        root_chord=params.h_stab_chord,
        tip_chord=params.h_stab_chord * 0.7,
        sweep_angle=params.h_stab_sweep,
        dihedral_angle=0,
        twist_angle=0,
        root_airfoil=params.h_stab_airfoil,
        tip_airfoil=params.h_stab_airfoil,
        wall_thickness=params.wall_thickness,
    )
    h_stab = build_wing_panel(h_panel)
    h_stab_mirrored = h_stab.mirror("YZ")
    h_stab = h_stab.union(h_stab_mirrored)

    # Vertical fin (single panel, rotated 90 degrees)
    v_panel = WingPanelParams(
        span_length=params.v_fin_span,
        root_chord=params.v_fin_chord,
        tip_chord=params.v_fin_chord * 0.6,
        sweep_angle=params.v_fin_sweep,
        dihedral_angle=0,
        twist_angle=0,
        root_airfoil=params.v_fin_airfoil,
        tip_airfoil=params.v_fin_airfoil,
        wall_thickness=params.wall_thickness,
    )
    v_fin = build_wing_panel(v_panel)
    # Rotate so it extends upward (Z) instead of sideways (X)
    v_fin = v_fin.rotateAboutCenter((0, 1, 0), 0).rotateAboutCenter((0, 0, 1), 90)

    # Combine and position at tail
    result = h_stab.union(v_fin)
    result = result.translate((0, params.position_y, 0))
    return result


def build_v_tail(params: VTailParams) -> cq.Workplane:
    """Two surfaces at dihedral angle meeting at centerline."""
    panel = WingPanelParams(
        span_length=params.span / 2,
        root_chord=params.chord,
        tip_chord=params.chord * 0.7,
        sweep_angle=params.sweep_angle,
        dihedral_angle=params.dihedral_angle,
        twist_angle=0,
        root_airfoil=params.airfoil,
        tip_airfoil=params.airfoil,
        wall_thickness=params.wall_thickness,
    )
    right = build_wing_panel(panel)
    left = right.mirror("YZ")
    result = right.union(left)
    result = result.translate((0, params.position_y, 0))
    return result


def build_t_tail(params: TTailParams) -> cq.Workplane:
    """Vertical fin with horizontal stab mounted on top."""
    # Vertical fin first
    v_panel = WingPanelParams(
        span_length=params.v_fin_span,
        root_chord=params.v_fin_chord,
        tip_chord=params.v_fin_chord * 0.6,
        sweep_angle=params.v_fin_sweep,
        dihedral_angle=0,
        twist_angle=0,
        root_airfoil=params.v_fin_airfoil,
        tip_airfoil=params.v_fin_airfoil,
        wall_thickness=params.wall_thickness,
    )
    v_fin = build_wing_panel(v_panel)
    v_fin = v_fin.rotateAboutCenter((0, 0, 1), 90)

    # Horizontal stab at top of vertical fin
    h_panel = WingPanelParams(
        span_length=params.h_stab_span / 2,
        root_chord=params.h_stab_chord,
        tip_chord=params.h_stab_chord * 0.7,
        sweep_angle=params.h_stab_sweep,
        dihedral_angle=0,
        twist_angle=0,
        root_airfoil=params.h_stab_airfoil,
        tip_airfoil=params.h_stab_airfoil,
        wall_thickness=params.wall_thickness,
    )
    h_stab = build_wing_panel(h_panel)
    h_stab_mirrored = h_stab.mirror("YZ")
    h_stab = h_stab.union(h_stab_mirrored)
    h_stab = h_stab.translate((0, 0, params.v_fin_span))  # place on top of fin

    result = v_fin.union(h_stab)
    result = result.translate((0, params.position_y, 0))
    return result
```

### 2.4 Control Surfaces

Control surfaces (ailerons, elevator, rudder) are created by Boolean-cutting a trailing-edge section from the parent surface.

```python
# backend/geometry/control_surface.py
import cadquery as cq
from dataclasses import dataclass

@dataclass
class ControlSurfaceDef:
    chord_fraction: float   # fraction of chord (e.g., 0.25 = 25%)
    span_start: float       # fraction of span where control surface begins
    span_end: float         # fraction of span where control surface ends
    gap_width: float        # mm gap between fixed and movable surface
    deflection: float       # degrees, for visualization only

def cut_control_surface(
    wing_solid: cq.Workplane,
    surface_def: ControlSurfaceDef,
    wing_bbox: tuple,  # (xmin, xmax, ymin, ymax, zmin, zmax)
) -> tuple[cq.Workplane, cq.Workplane]:
    """
    Cut a control surface from the wing trailing edge.
    Returns (modified_wing, control_surface_piece).
    """
    xmin, xmax, ymin, ymax, zmin, zmax = wing_bbox
    span = xmax - xmin
    chord = ymax - ymin  # approximate

    # Cutting box: covers the trailing edge portion
    cut_x_start = xmin + surface_def.span_start * span
    cut_x_end = xmin + surface_def.span_end * span
    cut_y_start = ymax - surface_def.chord_fraction * chord  # trailing edge region

    cutter = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(cut_x_start, cut_y_start, zmin - 1))
        .rect(cut_x_end - cut_x_start, chord * surface_def.chord_fraction + 1)
        .extrude(zmax - zmin + 2)
    )

    control_piece = wing_solid.intersect(cutter)
    modified_wing = wing_solid.cut(cutter)

    return modified_wing, control_piece
```

### 2.5 3D Printing Design Features

All generated geometry includes features for FDM 3D printing:

```python
# backend/geometry/print_features.py
import cadquery as cq

def add_spar_channels(
    wing_solid: cq.Workplane,
    spar_positions: list[float],  # chord fractions, e.g. [0.25, 0.60]
    spar_diameter: float = 4.0,   # mm, carbon fiber rod diameter
    clearance: float = 0.2,       # mm printing tolerance
) -> cq.Workplane:
    """Add internal channels for carbon fiber spar rods."""
    result = wing_solid
    for pos in spar_positions:
        # Create a cylinder along the span at the given chord position
        # Cut it from the wing solid to leave a channel
        bbox = result.val().BoundingBox()
        channel = (
            cq.Workplane("YZ")
            .transformed(offset=cq.Vector(0, bbox.ymin + pos * (bbox.ymax - bbox.ymin), 0))
            .circle((spar_diameter + clearance) / 2)
            .extrude(bbox.xmax - bbox.xmin + 2)
            .translate((bbox.xmin - 1, 0, 0))
        )
        result = result.cut(channel)
    return result


def add_servo_mount(
    wing_solid: cq.Workplane,
    servo_width: float = 12.0,
    servo_length: float = 23.0,
    servo_depth: float = 11.0,
    position: tuple[float, float, float] = (0, 0, 0),
) -> cq.Workplane:
    """Cut a pocket for a micro servo in the wing."""
    pocket = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(*position))
        .rect(servo_width + 0.4, servo_length + 0.4)  # clearance
        .extrude(-servo_depth)
    )
    # Add mounting tab slots
    tab_slot = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(position[0], position[1], position[2]))
        .rect(servo_width + 6, 2.0)
        .extrude(-1.5)
    )
    result = wing_solid.cut(pocket).cut(tab_slot)
    return result


PRINT_BED_SIZES = {
    'ender3': (220, 220, 250),     # mm (x, y, z)
    'prusa_mk3': (250, 210, 210),
    'bambu_a1': (256, 256, 256),
    'bambu_x1': (256, 256, 256),
    'voron_350': (350, 350, 350),
    'custom': None,  # user specifies
}
```

---

## 3. BACKEND API (FastAPI)

### 3.1 Server Architecture

```python
# backend/main.py
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import anyio

# --- Environment mode ---
CHENG_MODE = os.environ.get("CHENG_MODE", "local")  # "local" or "cloud"

app = FastAPI(title="RC Plane Generator", version="0.1.0")

# Serve the built frontend (static files baked into Docker image)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


# --- Health check for Cloud Run probes ---
@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run startup/liveness probes."""
    return JSONResponse({"status": "healthy", "mode": CHENG_MODE})


# --- REST API for design operations ---

class DesignParams(BaseModel):
    global_params: dict
    fuselage_params: dict
    wing_params: dict
    tail_params: dict
    control_surfaces: list[dict] = []


class GenerateResponse(BaseModel):
    meshes: dict[str, MeshPayload]  # component_id -> mesh data
    derived: dict                    # computed values (wing area, AR, etc.)
    annotations: list[dict]          # dimension annotation data


class MeshPayload(BaseModel):
    positions: list[float]   # flat array [x0,y0,z0, x1,y1,z1, ...]
    normals: list[float]
    indices: list[int]
    vertex_count: int
    triangle_count: int
```

### 3.1.1 Storage Abstraction

The backend uses a `StorageBackend` protocol to abstract file storage. In local mode, designs are persisted to the Docker volume at `/data/`. In cloud mode, no server-side storage is used -- the backend returns data directly to the client via `StreamingResponse`.

```python
# backend/storage.py
import os
from typing import Protocol, runtime_checkable
from pathlib import Path
from io import BytesIO

CHENG_MODE = os.environ.get("CHENG_MODE", "local")


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for design storage backends."""
    def save(self, name: str, data: bytes) -> str: ...
    def load(self, name: str) -> bytes: ...
    def list_designs(self) -> list[dict]: ...
    def delete(self, name: str) -> None: ...


class LocalStorage:
    """Writes designs to /data/ Docker volume (persistent across restarts)."""
    def __init__(self, base_path: str = "/data/designs"):
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: bytes) -> str:
        filepath = self.base / f"{name}.rcplane.json"
        filepath.write_bytes(data)
        return str(filepath)

    def load(self, name: str) -> bytes:
        filepath = self.base / f"{name}.rcplane.json"
        return filepath.read_bytes()

    def list_designs(self) -> list[dict]:
        return [
            {"name": f.stem.replace(".rcplane", ""), "filename": f.name}
            for f in self.base.glob("*.rcplane.json")
        ]

    def delete(self, name: str) -> None:
        filepath = self.base / f"{name}.rcplane.json"
        filepath.unlink(missing_ok=True)


class MemoryStorage:
    """No-op storage for cloud mode. Returns data to client, no server-side persist."""
    def save(self, name: str, data: bytes) -> str:
        return "memory://not-persisted"

    def load(self, name: str) -> bytes:
        raise FileNotFoundError("Cloud mode does not store designs server-side")

    def list_designs(self) -> list[dict]:
        return []

    def delete(self, name: str) -> None:
        pass


def get_storage() -> StorageBackend:
    if CHENG_MODE == "cloud":
        return MemoryStorage()
    return LocalStorage()
```

### 3.1.2 Thread-Safe CadQuery Execution

CadQuery (OpenCascade) is CPU-bound and not async-safe. All CadQuery calls are wrapped in `anyio.to_thread.run_sync()` to avoid blocking the FastAPI event loop, using a capped thread pool to limit concurrent memory usage:

```python
# backend/cadquery_runner.py
import anyio
from functools import partial

# Limit concurrent CadQuery operations to prevent OOM on Cloud Run (2Gi memory)
_cq_limiter = anyio.CapacityLimiter(4)


async def run_cadquery(func, *args, **kwargs):
    """Run a blocking CadQuery function in a thread pool with concurrency limiting."""
    return await anyio.to_thread.run_sync(
        partial(func, *args, **kwargs),
        limiter=_cq_limiter,
    )
```

Usage in endpoints:

```python
# In any async endpoint that calls CadQuery:
from .cadquery_runner import run_cadquery

@router.post("/api/generate")
async def generate_aircraft(params: DesignParams) -> GenerateResponse:
    # CadQuery runs in thread pool, does not block event loop
    fuse_solid = await run_cadquery(build_fuselage_solid, FuselageParams(**params.fuselage_params))
    fuse_mesh = await run_cadquery(tessellate_solid, fuse_solid)
    # ... etc
```

### 3.2 Geometry Generation Endpoint (REST)

For full regeneration triggered by parameter changes:

```python
# backend/api/generate.py
from fastapi import APIRouter
from ..geometry.fuselage import build_fuselage_solid, FuselageParams
from ..geometry.wing import build_full_wing, WingParams
from ..geometry.tail import build_conventional_tail, build_v_tail, build_t_tail
from ..geometry.tessellate import tessellate_solid

router = APIRouter(prefix="/api")


@router.post("/generate")
async def generate_aircraft(params: DesignParams) -> GenerateResponse:
    """Regenerate all aircraft geometry from parameters."""
    meshes = {}

    # Fuselage
    fuse_params = FuselageParams(**params.fuselage_params)
    fuse_solid = build_fuselage_solid(fuse_params)
    meshes['fuselage'] = tessellate_solid(fuse_solid)

    # Wing
    wing_params = WingParams(**params.wing_params)
    wing_solid = build_full_wing(wing_params)
    meshes['wing-left'] = tessellate_solid(wing_solid)  # left half
    meshes['wing-right'] = tessellate_solid(wing_solid)  # right half (mirrored)

    # Tail
    tail_type = params.global_params.get('tail_type', 'conventional')
    tail_solid = build_tail(tail_type, params.tail_params)
    meshes['tail'] = tessellate_solid(tail_solid)

    # Compute derived values
    derived = compute_derived_values(params)
    annotations = compute_annotations(params, derived)

    return GenerateResponse(meshes=meshes, derived=derived, annotations=annotations)


def build_tail(tail_type: str, tail_params: dict):
    if tail_type == 'conventional':
        return build_conventional_tail(ConventionalTailParams(**tail_params))
    elif tail_type == 'v-tail':
        return build_v_tail(VTailParams(**tail_params))
    elif tail_type == 't-tail':
        return build_t_tail(TTailParams(**tail_params))
```

### 3.3 Tessellation (CadQuery Solid to Triangle Mesh)

Convert CadQuery solids to triangle mesh data for Three.js:

```python
# backend/geometry/tessellate.py
import cadquery as cq
from cadquery import exporters
import numpy as np


def tessellate_solid(
    solid: cq.Workplane,
    tolerance: float = 0.1,    # mm, linear deflection
    angular_tolerance: float = 0.1,  # radians
) -> MeshPayload:
    """Tessellate a CadQuery solid into triangle mesh for Three.js preview."""
    # CadQuery/OCC tessellation
    shape = solid.val()
    vertices, triangles = shape.tessellate(tolerance, angular_tolerance)

    # Flatten into arrays
    positions = []
    normals = []
    indices = []

    # vertices is list of Vector, triangles is list of (i0, i1, i2)
    for v in vertices:
        positions.extend([v.x, v.y, v.z])

    for tri in triangles:
        indices.extend(tri)

    # Compute face normals (per-vertex approximation)
    pos_array = np.array(positions).reshape(-1, 3)
    norm_array = np.zeros_like(pos_array)

    idx_array = np.array(indices).reshape(-1, 3)
    for face in idx_array:
        v0, v1, v2 = pos_array[face[0]], pos_array[face[1]], pos_array[face[2]]
        normal = np.cross(v1 - v0, v2 - v0)
        length = np.linalg.norm(normal)
        if length > 1e-10:
            normal /= length
        for idx in face:
            norm_array[idx] += normal

    # Normalize vertex normals
    lengths = np.linalg.norm(norm_array, axis=1, keepdims=True)
    lengths[lengths < 1e-10] = 1.0
    norm_array /= lengths

    return MeshPayload(
        positions=positions,
        normals=norm_array.flatten().tolist(),
        indices=indices,
        vertex_count=len(vertices),
        triangle_count=len(triangles),
    )
```

### 3.4 WebSocket for Real-Time Preview Updates

For interactive parameter changes (slider dragging), use WebSocket to avoid HTTP overhead:

```python
# backend/api/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
import json
import struct
import asyncio
from ..geometry.tessellate import tessellate_solid

# Active generation task -- cancelled if new params arrive before completion
_current_task: asyncio.Task | None = None


@app.websocket("/ws/preview")
async def preview_websocket(websocket: WebSocket):
    await websocket.accept()
    global _current_task

    try:
        while True:
            # Receive params as JSON
            raw = await websocket.receive_text()
            params = json.loads(raw)

            # Cancel previous generation if still running
            if _current_task and not _current_task.done():
                _current_task.cancel()

            # Run geometry generation in thread pool (CadQuery is CPU-bound)
            _current_task = asyncio.create_task(
                generate_and_send(websocket, params)
            )
    except WebSocketDisconnect:
        pass


async def generate_and_send(websocket: WebSocket, params: dict):
    """Generate geometry in thread pool and send binary mesh over WebSocket."""
    loop = asyncio.get_event_loop()

    # Run CadQuery in thread pool to avoid blocking the event loop
    meshes = await loop.run_in_executor(
        None,  # default thread pool
        lambda: generate_all_meshes(params)
    )

    # Send as binary for efficiency
    # Protocol: [component_id_len(u16)][component_id(utf8)][vertex_count(u32)][tri_count(u32)]
    #           [positions(f32[])][normals(f32[])][indices(u32[])]
    for component_id, mesh in meshes.items():
        header = component_id.encode('utf-8')
        # Pack: header_len(2) + header + vertex_count(4) + tri_count(4)
        meta = struct.pack(
            f'<H{len(header)}sII',
            len(header),
            header,
            mesh.vertex_count,
            mesh.triangle_count,
        )
        pos_bytes = struct.pack(f'<{len(mesh.positions)}f', *mesh.positions)
        norm_bytes = struct.pack(f'<{len(mesh.normals)}f', *mesh.normals)
        idx_bytes = struct.pack(f'<{len(mesh.indices)}I', *mesh.indices)

        payload = meta + pos_bytes + norm_bytes + idx_bytes
        await websocket.send_bytes(payload)

    # Send "done" marker as text
    await websocket.send_text(json.dumps({
        "type": "generation_complete",
        "derived": compute_derived_values(params),
        "annotations": compute_annotations_data(params),
    }))
```

### 3.5 STL Export Endpoint

CadQuery provides high-quality STL export directly from the OpenCascade kernel:

```python
# backend/api/export.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import cadquery as cq
from io import BytesIO

router = APIRouter(prefix="/api")


@router.post("/export/stl")
async def export_stl(params: DesignParams, quality: str = "medium"):
    """Export complete aircraft as STL for 3D printing."""
    tolerances = {
        "draft": (0.5, 0.5),
        "medium": (0.1, 0.1),
        "high": (0.02, 0.05),
    }
    linear_tol, angular_tol = tolerances.get(quality, tolerances["medium"])

    # Generate full assembly
    assembly = generate_full_assembly(params)

    # Export to STL bytes
    buffer = BytesIO()
    cq.exporters.export(assembly, buffer, exportType="STL",
                        tolerance=linear_tol, angularTolerance=angular_tol)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=rc_plane.stl"},
    )


@router.post("/export/stl-parts")
async def export_stl_parts(
    params: DesignParams,
    print_bed: str = "ender3",
    quality: str = "medium",
):
    """Export individual printable parts as separate STL files in a ZIP."""
    import zipfile

    assembly = generate_full_assembly(params)
    bed_size = PRINT_BED_SIZES.get(print_bed, (220, 220, 250))

    # Section parts that exceed print bed
    parts = section_for_printing(assembly, params, bed_size)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, (name, part_solid) in enumerate(parts):
            stl_buf = BytesIO()
            cq.exporters.export(part_solid, stl_buf, exportType="STL",
                                tolerance=0.1, angularTolerance=0.1)
            zf.writestr(f"{name}.stl", stl_buf.getvalue())

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=rc_plane_parts.zip"},
    )


@router.post("/export/step")
async def export_step(params: DesignParams):
    """Export as STEP for use in other CAD software."""
    assembly = generate_full_assembly(params)
    buffer = BytesIO()
    cq.exporters.export(assembly, buffer, exportType="STEP")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/step",
        headers={"Content-Disposition": "attachment; filename=rc_plane.step"},
    )
```

### 3.6 Save/Load Endpoints

Save/load uses the `StorageBackend` abstraction. In local mode, designs are persisted to the Docker volume at `/data/`. In cloud mode, the backend does not store designs -- the frontend uses IndexedDB for browser-local persistence.

```python
# backend/api/persistence.py
from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse
import json
from ..storage import get_storage, CHENG_MODE

router = APIRouter(prefix="/api")
storage = get_storage()


@router.post("/designs")
async def save_design(params: DesignParams, name: str):
    """Save design. In local mode, persists to Docker volume /data/.
    In cloud mode, returns acknowledgment (frontend uses IndexedDB)."""
    design_file = {
        "version": 1,
        "name": name,
        "params": params.dict(),
    }
    path = storage.save(name, json.dumps(design_file, indent=2).encode())
    return {"status": "saved", "path": path, "mode": CHENG_MODE}


@router.get("/designs")
async def list_designs():
    """List saved designs. Returns empty list in cloud mode."""
    return storage.list_designs()


@router.get("/designs/{filename}")
async def load_design(filename: str):
    """Load a saved design from server storage (local mode only)."""
    try:
        data = json.loads(storage.load(filename))
        return data
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": "Design not found"})


@router.get("/mode")
async def get_mode():
    """Return the current deployment mode so the frontend can adapt behavior."""
    return {"mode": CHENG_MODE}
```

---

## 4. UI COMPONENT IMPLEMENTATION

### 4.1 Layout Structure

```
+-----------------------------------------------+
|                   VIEWPORT                 | G |
|              (Three.js canvas +            | L |
|               SVG annotations)             | O |
|                                            | B |
|                                            | A |
|                                            | L |
|                                            |   |
|                                            | P |
|                                            | A |
|                                            | R |
|                                            | A |
|                                            | M |
+----------------------------+               | S |
|   COMPONENT DETAIL PANEL   |               |   |
|   (context-sensitive)       |          BTN  |   |
+----------------------------+---------------+---+
```

Use CSS Grid for the overall layout:

```css
/* frontend/src/styles/layout.css */
.app-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  grid-template-rows: 1fr auto;
  height: 100vh;
  background: #1e1e22;
  color: #ccc;
}

.viewport-area {
  grid-column: 1;
  grid-row: 1 / 3;
  position: relative; /* for SVG overlay positioning */
}

.global-params-panel {
  grid-column: 2;
  grid-row: 1;
  padding: 16px;
  border-left: 1px solid #333;
  overflow-y: auto;
}

.component-detail-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 50%;
  background: rgba(30, 30, 34, 0.92);
  backdrop-filter: blur(8px);
  padding: 16px;
  border-top: 1px solid #333;
  border-right: 1px solid #333;
}

.action-button-area {
  grid-column: 2;
  grid-row: 2;
  padding: 16px;
  border-left: 1px solid #333;
  border-top: 1px solid #333;
}
```

### 4.2 Global Parameters Panel

From the mockup (right side panel):

```typescript
// frontend/src/ui/panels/GlobalParametersPanel.tsx
interface GlobalParams {
  fuselageType: 'sport' | 'trainer' | 'racer' | 'pod';
  engines: [number, number];
  wingSpan: number;       // mm
  tailSpan: number;       // mm
  chord: number;          // mm, root chord
  tailType: 'conventional' | 'v-tail' | 't-tail' | 'flying-wing';
}

const GlobalParametersPanel: React.FC = () => {
  const params = useStore((s) => s.globalParams);
  const setParam = useStore((s) => s.setGlobalParam);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold tracking-wider uppercase text-gray-400">
        Global Parameters
      </h2>
      <ParamDropdown
        label="Fuselage"
        value={params.fuselageType}
        options={['sport', 'trainer', 'racer', 'pod']}
        onChange={(v) => setParam('fuselageType', v)}
      />
      <ParamDualInput
        label="Engines"
        values={params.engines}
        onChange={(v) => setParam('engines', v)}
      />
      <ParamNumericInput
        label="Span" value={params.wingSpan}
        min={200} max={3000} step={10} unit="mm"
        onChange={(v) => setParam('wingSpan', v)}
      />
      <ParamNumericInput
        label="Span" value={params.tailSpan}
        min={50} max={1000} step={5} unit="mm"
        onChange={(v) => setParam('tailSpan', v)}
      />
      <ParamNumericInput
        label="Chord" value={params.chord}
        min={30} max={500} step={5} unit="mm"
        onChange={(v) => setParam('chord', v)}
      />
      <ParamDropdown
        label="Tail Type"
        value={params.tailType}
        options={['conventional', 'v-tail', 't-tail', 'flying-wing']}
        onChange={(v) => setParam('tailType', v)}
      />
    </div>
  );
};
```

### 4.3 Component Detail Panel

Shown at bottom-left, content changes based on the selected component. From the mockups:

**Wing selected** (screen2.png): Airfoil dropdown, Sections, Sweep slider+input, Incident slider+input, Tip/Root Ratio.

**Tail selected** (screen3.png): Type dropdown, Dihedral, Angle, Span, Chord, Incident.

```typescript
// frontend/src/ui/panels/ComponentDetailPanel.tsx
const ComponentDetailPanel: React.FC = () => {
  const selectedComponent = useStore((s) => s.selectedComponent);

  if (!selectedComponent) {
    return (
      <div className="component-detail-panel">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">No Selection</p>
        <p className="text-lg text-gray-400">Select a component to configure</p>
      </div>
    );
  }

  return (
    <div className="component-detail-panel">
      <AnimatePresence mode="wait">
        <motion.div
          key={selectedComponent}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.15 }}
        >
          {selectedComponent.startsWith('wing') && <WingDetailPanel />}
          {selectedComponent === 'tail' && <TailDetailPanel />}
          {selectedComponent === 'fuselage' && <FuselageDetailPanel />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
```

### 4.4 Slider + Text Input Combo

```typescript
// frontend/src/ui/controls/SliderInput.tsx
interface SliderInputProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
}

const SliderInput: React.FC<SliderInputProps> = ({ label, value, min, max, step, unit, onChange }) => {
  const [localValue, setLocalValue] = useState(String(value));

  useEffect(() => { setLocalValue(String(value)); }, [value]);

  const commitValue = (v: number) => {
    const clamped = Math.max(min, Math.min(max, v));
    const stepped = Math.round(clamped / step) * step;
    onChange(stepped);
  };

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-gray-400 w-20 text-right shrink-0">{label}:</label>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => commitValue(parseFloat(e.target.value))}
        className="flex-1 h-1 bg-gray-600 rounded appearance-none cursor-pointer accent-gray-400"
      />
      <input type="text" value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={() => {
          const n = parseFloat(localValue);
          if (!isNaN(n)) commitValue(n);
          else setLocalValue(String(value));
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            const n = parseFloat(localValue);
            if (!isNaN(n)) commitValue(n);
          }
        }}
        className="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs text-center text-gray-200"
      />
      {unit && <span className="text-xs text-gray-500 w-6">{unit}</span>}
    </div>
  );
};
```

### 4.5 Airfoil Dropdown with Preview

```typescript
// frontend/src/ui/controls/AirfoilDropdown.tsx
const AirfoilPreview: React.FC<{ profile: AirfoilProfile }> = ({ profile }) => {
  const pathData = profile.points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0] * 80} ${30 - p[1] * 80}`)
    .join(' ') + ' Z';
  return (
    <svg width={80} height={30} className="inline-block ml-2">
      <path d={pathData} fill="none" stroke="#aaa" strokeWidth={0.8} />
    </svg>
  );
};
```

Airfoil data is fetched from the backend: `GET /api/airfoils` returns the list with point data for previews.

### 4.6 Action Button Area

Bottom-right corner. Primary action is STL export for 3D printing:

```typescript
// frontend/src/ui/panels/ActionPanel.tsx
const ActionPanel: React.FC = () => {
  const [showExportMenu, setShowExportMenu] = useState(false);
  const params = useStore((s) => s.design);

  const handleExport = async (format: string) => {
    setShowExportMenu(false);
    const endpoint = `/api/export/${format}`;
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = response.headers.get('Content-Disposition')?.split('filename=')[1] || 'export';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <button
          className="w-full bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium
                     py-2 px-4 rounded transition-colors"
          onClick={() => handleExport('stl')}
        >
          EXPORT STL
        </button>
        <button
          className="w-full mt-1 bg-gray-600 hover:bg-gray-500 text-white text-xs
                     py-1.5 px-4 rounded transition-colors"
          onClick={() => setShowExportMenu(!showExportMenu)}
        >
          More Exports...
        </button>
        {showExportMenu && (
          <div className="absolute bottom-full mb-1 right-0 w-52 bg-gray-700 rounded shadow-lg border border-gray-600 z-10">
            <button className="w-full text-left px-3 py-2 text-sm hover:bg-gray-600"
              onClick={() => handleExport('stl-parts')}>STL Parts (Print-Ready ZIP)</button>
            <button className="w-full text-left px-3 py-2 text-sm hover:bg-gray-600"
              onClick={() => handleExport('step')}>STEP (CAD Interchange)</button>
          </div>
        )}
      </div>
    </div>
  );
};
```

---

## 5. REAL-TIME UPDATE PIPELINE

### 5.1 Architecture

```
Browser UI (param change)
    |
    v
Zustand Store (immediate local state update)
    |
    |-- Debounce 150ms (slider) / 0ms (dropdown/commit)
    v
WebSocket send (JSON params)
    |
    v
Python Backend (FastAPI)
    |-- asyncio.run_in_executor (thread pool)
    v
CadQuery Geometry Generation (~200-800ms)
    |
    v
Tessellation (OCC tessellate ~50-100ms)
    |
    v
WebSocket send (binary mesh data)
    |
    v
Browser: deserialize -> update Three.js BufferGeometry
    |
    v
Render frame
```

### 5.2 Frontend WebSocket Client

```typescript
// frontend/src/api/GeometryClient.ts
export class GeometryClient {
  private ws: WebSocket | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private onMeshUpdate: (componentId: string, mesh: MeshData) => void,
              private onGenerationComplete: (derived: any, annotations: any[]) => void) {}

  connect() {
    this.ws = new WebSocket(`ws://${window.location.host}/ws/preview`);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        // JSON message (generation_complete)
        const msg = JSON.parse(event.data);
        if (msg.type === 'generation_complete') {
          this.onGenerationComplete(msg.derived, msg.annotations);
        }
      } else {
        // Binary mesh data
        this.parseBinaryMesh(event.data as ArrayBuffer);
      }
    };
  }

  /** Send params with debouncing for slider interactions */
  requestGeneration(params: DesignParams, immediate: boolean = false) {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);

    const send = () => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(params));
      }
    };

    if (immediate) {
      send();
    } else {
      this.debounceTimer = setTimeout(send, 150);
    }
  }

  private parseBinaryMesh(buffer: ArrayBuffer) {
    const view = new DataView(buffer);
    let offset = 0;

    // Read component ID
    const headerLen = view.getUint16(offset, true); offset += 2;
    const headerBytes = new Uint8Array(buffer, offset, headerLen);
    const componentId = new TextDecoder().decode(headerBytes); offset += headerLen;

    // Read counts
    const vertexCount = view.getUint32(offset, true); offset += 4;
    const triangleCount = view.getUint32(offset, true); offset += 4;

    // Read positions (float32)
    const posCount = vertexCount * 3;
    const positions = new Float32Array(buffer, offset, posCount); offset += posCount * 4;

    // Read normals (float32)
    const normals = new Float32Array(buffer, offset, posCount); offset += posCount * 4;

    // Read indices (uint32)
    const idxCount = triangleCount * 3;
    const indices = new Uint32Array(buffer, offset, idxCount);

    this.onMeshUpdate(componentId, { positions, normals, indices: Array.from(indices) });
  }

  disconnect() {
    this.ws?.close();
  }
}
```

### 5.3 Debouncing Strategy

| Interaction | Debounce | Rationale |
|------------|----------|-----------|
| Slider dragging | 150ms | CadQuery generation takes 200-800ms; sending every frame would queue up. 150ms batches rapid changes while feeling responsive. |
| Slider release | 0ms (immediate) | Final value should generate immediately |
| Dropdown change | 0ms (immediate) | Discrete change, user expects instant feedback |
| Text input commit (Enter/blur) | 0ms (immediate) | Explicit user action |

### 5.4 Performance Budget

CadQuery on OpenCascade is significantly heavier than raw triangle math. Expected timings on a modern desktop:

| Operation | Estimated Time |
|-----------|---------------|
| Fuselage loft (8 stations, shell) | 200-400ms |
| Wing loft (6 span sections, shell) | 150-300ms |
| Tail generation | 100-200ms |
| Full aircraft regeneration | 400-800ms |
| Tessellation (all components) | 50-100ms |
| WebSocket transfer (~100KB mesh) | <10ms |
| Three.js buffer update + render | <5ms |
| **Total end-to-end** | **~500ms-1s** |

This is perceptible but acceptable for a CAD tool. Mitigations:

1. **Component-level regeneration**: Only regenerate the changed component (wing params only rebuild wing)
2. **Progressive preview**: Send a low-res tessellation first (~50ms), then high-res
3. **Loading indicator**: Show a subtle spinner/progress bar on the viewport during generation
4. **Cancel stale requests**: WebSocket handler cancels in-progress generation when new params arrive

### 5.5 Component-Level Regeneration

Track which params changed and only regenerate affected components:

```python
# backend/api/generate.py
# Map parameter groups to components that need regeneration
PARAM_COMPONENT_MAP = {
    'fuselage_params': ['fuselage'],
    'wing_params': ['wing-left', 'wing-right'],
    'tail_params': ['tail'],
    'global_params.tail_type': ['tail'],
    'global_params.fuselage_type': ['fuselage'],
    'global_params.wing_span': ['wing-left', 'wing-right'],
    'global_params.chord': ['wing-left', 'wing-right'],
    'global_params.tail_span': ['tail'],
}
```

The frontend sends a diff of which params changed. The backend only regenerates the affected components and sends back only those meshes.

---

## 6. AIRFOIL DATABASE

### 6.1 Storage Format

Airfoils stored as `.dat` files on the backend, indexed by a JSON manifest:

```python
# backend/data/airfoils/manifest.json
{
  "airfoils": [
    {
      "id": "naca2412",
      "name": "NACA 2412",
      "category": "semi-symmetric",
      "thickness": 12,
      "file": "naca2412.dat",
      "description": "Good all-around sport/trainer airfoil"
    },
    ...
  ]
}
```

### 6.2 Built-in Database (25 Airfoils)

**Symmetric** (aerobatic, tail surfaces):
- NACA 0006, NACA 0009, NACA 0012

**Flat-bottom** (trainers):
- Clark Y, NACA 6412, Eppler E195

**Semi-symmetric** (sport/general):
- NACA 2412, NACA 4412, Eppler E193, SD7037, MH32

**High-lift** (slow flyers):
- Selig S1223, Eppler E423, AG35

**Laminar flow** (racers/gliders):
- NACA 63-412, RG15, HQ3.0/14

### 6.3 Backend Airfoil API

```python
# backend/api/airfoils.py
from fastapi import APIRouter, UploadFile
from pathlib import Path
import json

router = APIRouter(prefix="/api")
AIRFOIL_DIR = Path(__file__).parent.parent / "data" / "airfoils"


@router.get("/airfoils")
async def list_airfoils():
    """Return all available airfoils with point data for preview."""
    manifest = json.loads((AIRFOIL_DIR / "manifest.json").read_text())
    result = []
    for entry in manifest["airfoils"]:
        dat_path = AIRFOIL_DIR / entry["file"]
        profile = parse_dat_file(dat_path.read_text())
        result.append({
            **entry,
            "points": profile.points,  # for frontend SVG preview
        })
    return result


@router.get("/airfoils/naca/{designation}")
async def generate_naca(designation: str):
    """Generate NACA airfoil on the fly."""
    profile = generate_naca4(designation)
    return {"name": profile.name, "points": profile.points}


@router.post("/airfoils/import")
async def import_airfoil(file: UploadFile):
    """Import a custom .dat airfoil file."""
    content = await file.read()
    profile = parse_dat_file(content.decode('utf-8'))
    # Save to custom airfoil directory (Docker volume in local mode)
    custom_dir = Path("/data/airfoils") if CHENG_MODE == "local" else Path("/tmp/airfoils")
    custom_dir.mkdir(parents=True, exist_ok=True)
    dest = custom_dir / file.filename
    dest.write_text(content.decode('utf-8'))
    return {"name": profile.name, "points": profile.points, "saved_to": str(dest)}
```

---

## 7. EXPORT IMPLEMENTATION

### 7.1 STL Export (Primary -- 3D Printing)

CadQuery/OpenCascade produces high-quality STL directly from the B-Rep solid. This is far superior to exporting from Three.js triangle meshes because:
- Watertight meshes guaranteed (no gaps/non-manifold edges)
- Controllable tessellation quality via tolerance parameters
- Proper normals computed from the actual surface geometry

```python
# backend/export/stl_export.py
import cadquery as cq
from io import BytesIO


def export_stl_assembly(
    assembly: cq.Workplane,
    tolerance: float = 0.1,
    angular_tolerance: float = 0.1,
) -> bytes:
    """Export full assembly as binary STL."""
    buffer = BytesIO()
    cq.exporters.export(
        assembly, buffer,
        exportType="STL",
        tolerance=tolerance,
        angularTolerance=angular_tolerance,
    )
    return buffer.getvalue()


def export_stl_parts(
    parts: dict[str, cq.Workplane],
    tolerance: float = 0.1,
) -> dict[str, bytes]:
    """Export each part as a separate STL (for individual printing)."""
    result = {}
    for name, solid in parts.items():
        buf = BytesIO()
        cq.exporters.export(solid, buf, exportType="STL", tolerance=tolerance)
        result[name] = buf.getvalue()
    return result
```

Quality settings for STL export:

| Quality | Linear Tolerance | Angular Tolerance | Use Case |
|---------|-----------------|-------------------|----------|
| Draft | 0.5mm | 0.5 rad | Quick preview, small file |
| Medium | 0.1mm | 0.1 rad | Standard 3D printing (default) |
| High | 0.02mm | 0.05 rad | High-detail printing, resin |

File size estimates (medium quality):
- Simple aircraft: ~500KB-2MB
- With control surfaces and print features: ~2-5MB

### 7.2 STEP Export

STEP is the universal CAD interchange format. CadQuery supports it natively:

```python
def export_step(assembly: cq.Workplane) -> bytes:
    buffer = BytesIO()
    cq.exporters.export(assembly, buffer, exportType="STEP")
    return buffer.getvalue()
```

This allows users to import the generated aircraft into Fusion 360, FreeCAD, SolidWorks, etc. for further modification.

### 7.3 Print-Ready Parts Export

The most valuable export for 3D printing users. Generates a ZIP file containing:
1. Individual STL files for each printable part (sectioned to fit the print bed)
2. A manifest JSON with print orientation hints and assembly order

```python
# backend/export/print_ready.py
import cadquery as cq
from dataclasses import dataclass

@dataclass
class PrintPart:
    name: str
    solid: cq.Workplane
    print_orientation: str   # 'flat' | 'upright' | 'on-side'
    supports_needed: bool
    estimated_time_min: int  # rough FDM print time estimate
    notes: str


def generate_print_parts(
    params: DesignParams,
    bed_size: tuple[float, float, float] = (220, 220, 250),
) -> list[PrintPart]:
    """Generate all print-ready parts for the aircraft."""
    parts = []

    # Fuselage sections
    fuse_solid = build_fuselage_solid(FuselageParams(**params.fuselage_params))
    fuse_sections = section_fuselage_for_printing(fuse_solid, max_section_length=bed_size[1] - 20)
    for i, section in enumerate(fuse_sections):
        parts.append(PrintPart(
            name=f"fuselage_section_{i+1}",
            solid=section,
            print_orientation='upright',
            supports_needed=False,
            estimated_time_min=estimate_print_time(section),
            notes=f"Fuselage section {i+1} of {len(fuse_sections)}. Print nose-up.",
        ))

    # Wing sections
    wing_solid = build_full_wing(WingParams(**params.wing_params))
    wing_sections = section_wing_for_printing(wing_solid, max_section_span=bed_size[0] - 20)
    for i, section in enumerate(wing_sections):
        parts.append(PrintPart(
            name=f"wing_section_{i+1}",
            solid=section,
            print_orientation='flat',
            supports_needed=True,  # trailing edge overhang
            estimated_time_min=estimate_print_time(section),
            notes=f"Wing section {i+1}. Print trailing-edge up with supports.",
        ))

    # Tail
    tail_solid = build_tail(params.global_params['tail_type'], params.tail_params)
    parts.append(PrintPart(
        name="tail_assembly",
        solid=tail_solid,
        print_orientation='flat',
        supports_needed=True,
        estimated_time_min=estimate_print_time(tail_solid),
        notes="Tail assembly. May need supports for thin sections.",
    ))

    return parts


def estimate_print_time(solid: cq.Workplane, layer_height: float = 0.2) -> int:
    """Rough estimate of FDM print time in minutes."""
    # Volume-based heuristic: ~15 cm^3/hour for FDM at 0.2mm layer height
    volume_mm3 = solid.val().Volume()  # CadQuery returns mm^3
    volume_cm3 = volume_mm3 / 1000
    hours = volume_cm3 / 15
    return int(hours * 60)
```

---

## 8. STATE MANAGEMENT

The backend is **stateless** -- no design state is stored server-side. The frontend Zustand store holds all application state. This is critical for Cloud Run deployment where container instances are ephemeral and may be terminated at any time.

### 8.1 Store Structure

```typescript
// frontend/src/store/types.ts
type DeploymentMode = 'local' | 'cloud';

interface AppState {
  // Design state (serializable, sent to backend)
  design: {
    globalParams: GlobalParams;
    fuselageParams: FuselageParams;
    wingParams: WingParams;
    tailParams: TailParams;
    controlSurfaces: ControlSurfaceDef[];
    printSettings: PrintSettings;
  };

  // UI state (transient, not saved)
  ui: {
    selectedComponent: ComponentId | null;
    hoveredComponent: ComponentId | null;
    viewState: { zoom: number; panX: number; panY: number };
    isGenerating: boolean;       // true while backend is computing
    backendConnected: boolean;   // WebSocket connection status
    exportMenuOpen: boolean;
    deploymentMode: DeploymentMode;  // fetched from GET /mode on startup
  };

  // Derived state (received from backend after generation)
  derived: {
    wingArea: number;
    aspectRatio: number;
    tailVolume: number;
    totalLength: number;
    totalSpan: number;
    annotations: Annotation[];
    printPartCount: number;      // how many parts when sectioned
    estimatedPrintTime: number;  // total minutes
  };
}

interface PrintSettings {
  printBed: 'ender3' | 'prusa_mk3' | 'bambu_a1' | 'bambu_x1' | 'voron_350' | 'custom';
  customBedSize?: [number, number, number];
  wallThickness: number;     // mm (default 1.2)
  jointType: 'dovetail' | 'pin' | 'flat';
  sparDiameter: number;      // mm (default 4.0 for carbon fiber rod)
}
```

### 8.2 Undo/Redo

Implement via Zustand middleware that captures `design` snapshots:

```typescript
// frontend/src/store/undoMiddleware.ts
const MAX_UNDO_STEPS = 50;

interface UndoState {
  past: DesignState[];
  future: DesignState[];
  undo: () => void;
  redo: () => void;
}

// When design state changes, push previous state onto undo stack
// Undo pops from past, pushes current to future
// Redo pops from future, pushes current to past
```

Keyboard shortcuts: `Ctrl+Z` (undo), `Ctrl+Shift+Z` (redo).

### 8.3 Backend Connection State

The store tracks WebSocket connection status and shows a connection indicator in the UI:

```typescript
// frontend/src/api/useBackendConnection.ts
export function useBackendConnection() {
  const setConnected = useStore((s) => s.setBackendConnected);
  const setGenerating = useStore((s) => s.setIsGenerating);

  useEffect(() => {
    const client = new GeometryClient(
      (componentId, mesh) => {
        // Update Three.js scene
        sceneManager.updateComponentMesh(componentId, mesh);
      },
      (derived, annotations) => {
        useStore.getState().setDerived(derived);
        setGenerating(false);
      }
    );

    client.connect();
    setConnected(true);

    // On param changes, send to backend
    const unsub = useStore.subscribe(
      (s) => s.design,
      (design) => {
        setGenerating(true);
        client.requestGeneration(design);
      },
      { equalityFn: shallow }
    );

    return () => { unsub(); client.disconnect(); };
  }, []);
}
```

---

## 9. DATA PERSISTENCE

### 9.1 Save/Load File Format

Design files are JSON. Storage location depends on deployment mode:

```json
{
  "version": 1,
  "name": "My Trainer V2",
  "created_at": "2026-02-23T10:30:00Z",
  "modified_at": "2026-02-23T14:45:00Z",
  "params": {
    "global_params": { "fuselage_type": "trainer", "tail_type": "conventional", ... },
    "fuselage_params": { "length": 400, "max_width": 60, ... },
    "wing_params": { ... },
    "tail_params": { ... },
    "print_settings": { "print_bed": "ender3", "wall_thickness": 1.2, ... }
  },
  "custom_airfoils": [
    { "name": "My Custom", "file": "my_custom.dat" }
  ]
}
```

File extension: `.rcplane.json`

| Mode | Storage Location | Mechanism |
|------|-----------------|-----------|
| **Local** | `/data/designs/` (Docker volume) | Backend `LocalStorage` writes to persistent Docker volume |
| **Cloud** | Browser IndexedDB | Frontend saves directly; no server roundtrip |

### 9.2 Autosave

Autosave behavior adapts to the deployment mode:

**Local mode**: The frontend sends periodic autosave requests to the backend via `POST /api/designs` every 10 seconds if the design has changed. The backend writes to the Docker volume at `/data/designs/_autosave.rcplane.json`.

```python
# Backend autosave endpoint (local mode only)
@router.post("/api/autosave")
async def autosave(params: DesignParams):
    storage = get_storage()
    storage.save("_autosave", json.dumps({"params": params.dict()}, indent=2).encode())
    return {"status": "ok"}
```

**Cloud mode**: The frontend saves to IndexedDB directly, bypassing the backend entirely. This ensures designs survive browser refreshes without requiring server-side state.

```typescript
// frontend/src/persistence/indexeddb.ts
const DB_NAME = 'cheng-designs';
const STORE_NAME = 'designs';

export async function autosaveToIndexedDB(design: DesignState): Promise<void> {
  const db = await openDB(DB_NAME, 1, {
    upgrade(db) {
      db.createObjectStore(STORE_NAME, { keyPath: 'name' });
    },
  });
  await db.put(STORE_NAME, {
    name: '_autosave',
    params: design,
    modified_at: new Date().toISOString(),
  });
}

export async function loadAutosaveFromIndexedDB(): Promise<DesignState | null> {
  const db = await openDB(DB_NAME, 1);
  const result = await db.get(STORE_NAME, '_autosave');
  return result?.params ?? null;
}
```

On app startup, the frontend checks for autosave (from the backend in local mode, from IndexedDB in cloud mode) and prompts the user to restore.

---

## 10. TESTING APPROACH

### 10.1 Backend Unit Tests (pytest)

```python
# backend/tests/test_geometry.py
import pytest
import cadquery as cq
from geometry.fuselage import build_fuselage_solid, FuselageParams
from geometry.wing import build_wing_panel, WingPanelParams
from geometry.airfoil import generate_naca4, parse_dat_file


class TestFuselage:
    def test_basic_fuselage_is_solid(self):
        params = FuselageParams(
            type='sport', length=400, max_width=60, max_height=50,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=0,
        )
        solid = build_fuselage_solid(params)
        assert solid.val().Volume() > 0
        assert solid.val().isValid()

    def test_shelled_fuselage_has_less_volume(self):
        params_solid = FuselageParams(
            type='sport', length=400, max_width=60, max_height=50,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=0,
        )
        params_shell = FuselageParams(
            type='sport', length=400, max_width=60, max_height=50,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=1.2,
        )
        vol_solid = build_fuselage_solid(params_solid).val().Volume()
        vol_shell = build_fuselage_solid(params_shell).val().Volume()
        assert vol_shell < vol_solid

    def test_fuselage_length_matches_param(self):
        params = FuselageParams(
            type='sport', length=400, max_width=60, max_height=50,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=0,
        )
        solid = build_fuselage_solid(params)
        bbox = solid.val().BoundingBox()
        assert abs((bbox.ymax - bbox.ymin) - 400) < 5  # within 5mm tolerance


class TestWing:
    @pytest.fixture
    def naca0012(self):
        return generate_naca4('0012')

    def test_wing_panel_is_valid_solid(self, naca0012):
        params = WingPanelParams(
            span_length=500, root_chord=200, tip_chord=100,
            sweep_angle=0, dihedral_angle=0, twist_angle=0,
            root_airfoil=naca0012, tip_airfoil=naca0012,
            wall_thickness=0,
        )
        solid = build_wing_panel(params)
        assert solid.val().isValid()
        assert solid.val().Volume() > 0

    def test_wing_span_matches_param(self, naca0012):
        params = WingPanelParams(
            span_length=500, root_chord=200, tip_chord=100,
            sweep_angle=0, dihedral_angle=0, twist_angle=0,
            root_airfoil=naca0012, tip_airfoil=naca0012,
            wall_thickness=0,
        )
        solid = build_wing_panel(params)
        bbox = solid.val().BoundingBox()
        assert abs((bbox.xmax - bbox.xmin) - 500) < 5

    def test_sweep_offsets_tip(self, naca0012):
        params = WingPanelParams(
            span_length=500, root_chord=200, tip_chord=100,
            sweep_angle=30, dihedral_angle=0, twist_angle=0,
            root_airfoil=naca0012, tip_airfoil=naca0012,
            wall_thickness=0,
        )
        solid = build_wing_panel(params)
        bbox = solid.val().BoundingBox()
        # With 30deg sweep over 500mm span, tip LE moves ~289mm aft
        import math
        expected_offset = math.tan(math.radians(30)) * 500
        # The bounding box Y extent should be larger than root chord alone
        assert (bbox.ymax - bbox.ymin) > 200 + expected_offset * 0.5


class TestAirfoil:
    def test_naca_symmetric(self):
        profile = generate_naca4('0012')
        assert len(profile.points) > 50
        # Check symmetry: upper and lower y values should mirror
        mid_idx = len(profile.points) // 2
        for i in range(min(10, mid_idx)):
            upper_y = profile.points[i][1]
            lower_y = profile.points[-(i+1)][1]
            assert abs(upper_y + lower_y) < 0.01

    def test_naca_max_thickness(self):
        profile = generate_naca4('0015')
        y_vals = [abs(p[1]) for p in profile.points]
        max_t = max(y_vals) * 2
        assert abs(max_t - 0.15) < 0.02

    def test_dat_file_parsing(self):
        dat_content = "NACA 0012\n1.0 0.0013\n0.5 0.06\n0.0 0.0\n0.5 -0.06\n1.0 -0.0013\n"
        profile = parse_dat_file(dat_content)
        assert profile.name == "NACA 0012"
        assert len(profile.points) == 5


class TestSectioning:
    def test_fuselage_sectioning_creates_multiple_parts(self):
        params = FuselageParams(
            type='sport', length=600, max_width=60, max_height=50,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=0,
        )
        solid = build_fuselage_solid(params)
        sections = section_fuselage_for_printing(solid, max_section_length=200)
        assert len(sections) >= 3  # 600mm / 200mm = 3 sections

    def test_all_sections_are_valid(self):
        params = FuselageParams(
            type='sport', length=400, max_width=60, max_height=50,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=1.2,
        )
        solid = build_fuselage_solid(params)
        sections = section_fuselage_for_printing(solid, max_section_length=200)
        for section in sections:
            assert section.val().isValid()
            assert section.val().Volume() > 0


class TestSTLExport:
    def test_stl_export_produces_bytes(self):
        params = FuselageParams(
            type='sport', length=300, max_width=50, max_height=40,
            nose_fraction=0.2, tail_fraction=0.3, wall_thickness=0,
        )
        solid = build_fuselage_solid(params)
        stl_bytes = export_stl_assembly(solid)
        assert len(stl_bytes) > 84  # STL header is 80 + 4 bytes minimum
```

### 10.2 Backend API Tests (pytest + httpx)

```python
# backend/tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_generate_endpoint(client):
    params = {
        "global_params": {"fuselage_type": "sport", "tail_type": "conventional",
                          "wing_span": 800, "tail_span": 200, "chord": 150},
        "fuselage_params": {"length": 400, "max_width": 60, "max_height": 50,
                           "nose_fraction": 0.2, "tail_fraction": 0.3, "wall_thickness": 1.2},
        "wing_params": {"panels": [{"span_length": 400, "root_chord": 150, "tip_chord": 80,
                                     "sweep_angle": 5, "dihedral_angle": 3, "twist_angle": -2}],
                        "tip_shape": "rounded", "is_symmetric": True},
        "tail_params": {"h_stab_span": 200, "h_stab_chord": 80},
    }
    response = await client.post("/api/generate", json=params)
    assert response.status_code == 200
    data = response.json()
    assert 'meshes' in data
    assert 'fuselage' in data['meshes']


@pytest.mark.asyncio
async def test_stl_export(client):
    params = { ... }  # same as above
    response = await client.post("/api/export/stl", json=params)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/octet-stream'
    assert len(response.content) > 84


@pytest.mark.asyncio
async def test_airfoil_list(client):
    response = await client.get("/api/airfoils")
    assert response.status_code == 200
    airfoils = response.json()
    assert len(airfoils) >= 15  # built-in database
    assert all('points' in a for a in airfoils)
```

### 10.3 Frontend Visual Regression Tests (Playwright)

```typescript
// frontend/tests/visual/viewport.spec.ts
import { test, expect } from '@playwright/test';

test('default aircraft renders correctly', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('canvas');
  // Wait for WebSocket generation to complete
  await page.waitForFunction(() =>
    !document.querySelector('[data-testid="generating-indicator"]')
  , { timeout: 5000 });
  await expect(page.locator('.viewport-area')).toHaveScreenshot('default-aircraft.png', {
    maxDiffPixelRatio: 0.02,
  });
});

test('V-tail configuration renders correctly', async ({ page }) => {
  await page.goto('/');
  await page.selectOption('[data-testid="tail-type-dropdown"]', 'v-tail');
  await page.waitForFunction(() =>
    !document.querySelector('[data-testid="generating-indicator"]')
  , { timeout: 5000 });
  await expect(page.locator('.viewport-area')).toHaveScreenshot('v-tail-aircraft.png', {
    maxDiffPixelRatio: 0.02,
  });
});
```

### 10.4 Performance Benchmarks

```python
# backend/tests/test_performance.py
import pytest
import time
from geometry.fuselage import build_fuselage_solid, FuselageParams
from geometry.wing import build_wing_panel, WingPanelParams
from geometry.airfoil import generate_naca4
from geometry.tessellate import tessellate_solid


def test_full_generation_under_2_seconds():
    """Full aircraft generation should complete in under 2 seconds."""
    naca2412 = generate_naca4('2412')
    start = time.perf_counter()

    # Fuselage
    fuse = build_fuselage_solid(FuselageParams(
        type='sport', length=400, max_width=60, max_height=50,
        nose_fraction=0.2, tail_fraction=0.3, wall_thickness=1.2,
    ))

    # Wing
    wing = build_wing_panel(WingPanelParams(
        span_length=400, root_chord=150, tip_chord=80,
        sweep_angle=5, dihedral_angle=3, twist_angle=-2,
        root_airfoil=naca2412, tip_airfoil=naca2412,
        wall_thickness=0.8,
    ))

    # Tessellate
    tessellate_solid(fuse)
    tessellate_solid(wing)

    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"Full generation took {elapsed:.2f}s, expected < 2.0s"


def test_tessellation_under_200ms():
    """Tessellation alone should be fast."""
    naca0012 = generate_naca4('0012')
    solid = build_wing_panel(WingPanelParams(
        span_length=500, root_chord=200, tip_chord=100,
        sweep_angle=0, dihedral_angle=0, twist_angle=0,
        root_airfoil=naca0012, tip_airfoil=naca0012,
        wall_thickness=0,
    ))

    start = time.perf_counter()
    mesh = tessellate_solid(solid)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2, f"Tessellation took {elapsed:.3f}s"
    assert mesh.triangle_count > 100
```

### 10.5 Docker Build & Container Tests

CI builds the Docker image and validates it starts correctly:

```yaml
# .github/workflows/docker-test.yml (excerpt)
- name: Build Docker image
  run: docker build -t cheng-test .

- name: Run container and health check
  run: |
    docker run -d --name cheng-test -p 8000:8000 cheng-test
    # Wait for startup (target: <10s to healthy)
    for i in $(seq 1 20); do
      if curl -sf http://localhost:8000/health; then
        echo "Healthy after ${i}s"
        break
      fi
      sleep 1
    done
    # Validate health response
    curl -sf http://localhost:8000/health | jq -e '.status == "healthy"'

- name: Container startup time benchmark
  run: |
    START=$(date +%s%N)
    docker run --rm -d --name cheng-bench -p 8001:8000 cheng-test
    while ! curl -sf http://localhost:8001/health > /dev/null 2>&1; do sleep 0.5; done
    END=$(date +%s%N)
    ELAPSED=$(( (END - START) / 1000000 ))
    echo "Container startup: ${ELAPSED}ms"
    # Target: <10s (10000ms)
    [ $ELAPSED -lt 10000 ] || (echo "FAIL: startup took ${ELAPSED}ms, target <10000ms" && exit 1)
    docker stop cheng-bench
```

### 10.6 Cloud Run Integration Tests

Deploy to a staging Cloud Run service and run smoke tests:

```bash
# scripts/cloud-run-smoke-test.sh

# Deploy to staging
gcloud run deploy cheng-staging \
  --image gcr.io/PROJECT/cheng:$SHA \
  --memory 2Gi --cpu 2 \
  --min-instances 0 --max-instances 1 \
  --set-env-vars CHENG_MODE=cloud \
  --region us-central1

# Get service URL
URL=$(gcloud run services describe cheng-staging --region us-central1 --format 'value(status.url)')

# Health check
curl -sf "$URL/health" | jq -e '.status == "healthy" and .mode == "cloud"'

# API smoke test: generate endpoint responds
curl -sf -X POST "$URL/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"global_params":{"tail_type":"conventional"},"fuselage_params":{"type":"sport","length":400,"max_width":60,"max_height":50,"nose_fraction":0.2,"tail_fraction":0.3,"wall_thickness":1.2},"wing_params":{"panels":[],"tip_shape":"square","is_symmetric":true},"tail_params":{}}' \
  | jq -e '.meshes | keys | length > 0'

# Mode endpoint returns cloud
curl -sf "$URL/mode" | jq -e '.mode == "cloud"'

# Cleanup staging
gcloud run services delete cheng-staging --region us-central1 --quiet
```

---

## 11. PHASE BREAKDOWN WITH EFFORT ESTIMATES

### Phase 1: MVP (5-6 weeks)

Goal: Working containerized app -- Dockerfile + docker-compose for local deployment. Python backend with CadQuery generates geometry, browser UI with Three.js renders preview, STL export works.

| Task | Description | Estimate |
|------|-------------|----------|
| Project scaffolding | Python package (FastAPI + CadQuery), Vite + React frontend, dev server | 3 days |
| **Dockerfile (multi-stage)** | Frontend build stage + Python runtime stage, OpenCascade deps | 2 days |
| **docker-compose.yml** | Backend + frontend dev services, Docker volume for `/data/` | 1 day |
| Backend: fuselage generation | CadQuery lofted fuselage with presets, shell for 3D printing | 4 days |
| Backend: wing generation | Airfoil spline, loft, taper/sweep, shell | 5 days |
| Backend: tail (conventional) | H-stab + V-fin using wing panel code | 2 days |
| Backend: tessellation + WebSocket | Binary mesh streaming to frontend | 3 days |
| Backend: STL export endpoint | CadQuery STL export with quality settings | 1 day |
| **Backend: health check + CHENG_MODE** | `/health` endpoint, `CHENG_MODE` env var, storage abstraction | 1 day |
| Frontend: viewport (Three.js) | Scene, orthographic camera, pan/zoom, render | 3 days |
| Frontend: mesh receive + display | WebSocket client, binary parsing, BufferGeometry update | 2 days |
| Frontend: component selection + highlight | Raycaster hit-testing, yellow highlight | 2 days |
| Frontend: global parameters panel | Right-side panel matching mockup | 2 days |
| Frontend: component detail panel | Wing + tail panels with sliders/dropdowns | 3 days |
| Frontend: SVG dimension annotations | Length + span overlays | 2 days |
| State management + save/load | Zustand store, backend persistence API, Docker volume persist | 2 days |
| Integration + debugging | End-to-end pipeline testing, Docker build verification | 3 days |
| **Total MVP** | | **~41 days** |

**MVP Deliverable**: User runs `docker compose up`, opens browser at `localhost:5173` (dev) or `localhost:8000` (production), adjusts parameters, sees aircraft update in viewport, exports STL for 3D printing. Designs persist in Docker volume.

### Phase 2: Version 1.0 (5-7 weeks)

Goal: Cloud Run deployment, CI/CD pipeline, full feature set, multi-user concurrency.

| Task | Description | Estimate |
|------|-------------|----------|
| **Cloud Run deployment** | `gcloud run deploy`, configure memory/CPU/concurrency/timeout | 2 days |
| **CI/CD pipeline** | GitHub Actions: build Docker image, run tests, push to GCR, deploy to Cloud Run | 3 days |
| **Multi-user concurrency testing** | Load test with 10 concurrent users on Cloud Run, validate thread pool limits | 2 days |
| **IndexedDB autosave (cloud mode)** | Frontend persists to IndexedDB when `CHENG_MODE=cloud` | 2 days |
| **Thread-safe CadQuery runner** | `anyio.to_thread.run_sync()` with capacity limiter | 1 day |
| V-tail and T-tail geometry | Additional tail configurations | 3 days |
| Control surface cutting | Boolean-cut ailerons/elevator/rudder | 4 days |
| Airfoil database (25 built-in) | DAT files, manifest, API, frontend dropdown with preview | 3 days |
| NACA generator | 4-digit on-the-fly generation, frontend input | 2 days |
| Custom DAT import | File upload, validation, storage | 1 day |
| Wing sectioning for printing | Auto-split with dovetail/pin joints | 4 days |
| Fuselage sectioning for printing | Auto-split with alignment pins | 3 days |
| Spar channels + servo mounts | 3D printing internal features | 3 days |
| Print-ready parts export (ZIP) | Individual STLs + manifest with print hints | 3 days |
| STEP export | CadQuery native STEP export | 1 day |
| Print bed size selector | UI for choosing printer, custom dimensions | 1 day |
| Undo/redo | Zustand middleware, keyboard shortcuts | 2 days |
| Component-level regeneration | Only rebuild changed components | 3 days |
| Angle annotations (sweep arc) | SVG arc annotations matching mockup | 2 days |
| Loading indicator | Spinner/progress during backend generation | 1 day |
| Polish: transitions, dark theme | Framer Motion, consistent styling | 3 days |
| **Total 1.0** | | **~50 days** |

### Phase 3: Future Enhancements

| Feature | Description | Priority |
|---------|-------------|----------|
| **Kubernetes/GKE deployment** | For larger scale beyond Cloud Run limits (>10 instances) | High |
| **CDN for static assets** | Cloud CDN or Cloudflare in front of Cloud Run for frontend assets | High |
| Flying wing configuration | Blended wing-body, no separate fuselage | High |
| Progressive preview | Low-res mesh first, then high-res | Medium |
| Engine nacelle geometry | Parametric motor mount + cowl | Medium |
| 3D orbit view toggle | Perspective camera option | Medium |
| Weight & CG estimation | Volume * material density | Medium |
| G-code preview integration | Show print orientation in viewport | Low |
| Multi-material support | Different wall thickness per component | Low |
| Landing gear geometry | Fixed/retract options | Low |
| Custom airfoil import via URL | Fetch from airfoiltools.com | Low |
| Plugin API | User-defined geometry generators in Python | Low |

---

## Appendix A: Directory Structure

```
cheng/
  Dockerfile                      # Multi-stage build (frontend + Python runtime)
  docker-compose.yml              # Local development (backend + frontend dev server)
  .dockerignore                   # Exclude node_modules, __pycache__, .git, etc.

  backend/
    main.py                       # FastAPI app entry point, health check, static serving
    storage.py                    # StorageBackend protocol, LocalStorage, MemoryStorage
    cadquery_runner.py            # Thread-safe CadQuery execution with anyio
    requirements.txt              # Python dependencies (pinned)

    api/
      generate.py                 # POST /api/generate (full regen, uses cadquery_runner)
      export.py                   # POST /api/export/stl, /stl-parts, /step (StreamingResponse)
      airfoils.py                 # GET /api/airfoils, POST /api/airfoils/import
      persistence.py              # POST /api/designs, GET /api/designs, GET /api/mode
      websocket.py                # WS /ws/preview

    geometry/
      airfoil.py                  # DAT parser, NACA generator
      fuselage.py                 # Cross-section lofting, presets, shelling
      wing.py                     # Wing panel lofting, taper/sweep/twist
      tail.py                     # Conventional/V-tail/T-tail builders
      control_surface.py          # Boolean-cut trailing edge surfaces
      print_features.py           # Spar channels, servo mounts, sectioning
      tessellate.py               # CadQuery solid -> triangle mesh for Three.js

    export/
      stl_export.py               # STL export (binary, quality settings)
      step_export.py              # STEP export
      print_ready.py              # Print-ready parts ZIP generation

    tests/
      test_geometry.py            # Unit tests: fuselage, wing, tail, airfoil
      test_api.py                 # API integration tests
      test_performance.py         # Benchmark tests
      test_docker.py              # Docker build + health check tests
      test_cloud_run.py           # Cloud Run integration smoke tests
      conftest.py                 # Shared fixtures

  airfoils/
    manifest.json                 # Airfoil index
    naca0012.dat                  # Individual DAT files
    naca2412.dat
    clark_y.dat
    ...

  frontend/
    package.json
    pnpm-lock.yaml
    index.html
    src/
      main.tsx                    # React entry point
      App.tsx                     # Root component with layout grid

      api/
        GeometryClient.ts         # WebSocket client for mesh streaming
        RestClient.ts              # HTTP client for export, save/load, airfoils
        useBackendConnection.ts    # React hook: connect + sync store <-> backend

      viewport/
        SceneManager.ts         # Three.js scene, camera, renderer
        PanZoomControls.ts      # Zoom/pan on orthographic camera
        SelectionManager.ts     # Raycaster-based component picking
        HighlightManager.ts     # Hover/selection visual feedback
        annotations/
          AnnotationOverlay.tsx # SVG overlay for dimension annotations

      ui/
        panels/
          GlobalParametersPanel.tsx
          ComponentDetailPanel.tsx
          WingDetailPanel.tsx
          TailDetailPanel.tsx
          FuselageDetailPanel.tsx
          ActionPanel.tsx
        controls/
          SliderInput.tsx
          ParamNumericInput.tsx
          ParamDropdown.tsx
          AirfoilDropdown.tsx
        layout/
          AppLayout.tsx         # CSS Grid root layout
          ConnectionIndicator.tsx
          GeneratingSpinner.tsx

      store/
        store.ts                # Zustand store definition
        types.ts                # State type definitions
        undoMiddleware.ts       # Undo/redo stack

      persistence/
        indexeddb.ts            # IndexedDB autosave/restore (cloud mode)
        autosave.ts             # Mode-aware autosave logic (local vs cloud)

    tests/
      visual/                   # Playwright visual regression
      components/               # Component unit tests (Vitest)

  scripts/
    cloud-run-smoke-test.sh     # Cloud Run staging deploy + smoke test
    docker-health-check.sh      # Docker container health validation

  .github/
    workflows/
      ci.yml                    # Build, test, push Docker image
      deploy.yml                # Deploy to Cloud Run on main merge
```

## Appendix B: Key Dependencies

### Python (backend)

```txt
# backend/requirements.txt
cadquery>=2.4
fastapi>=0.115
uvicorn[standard]>=0.30
numpy>=1.26
pydantic>=2.0
anyio>=4.0
```

```toml
# pyproject.toml
[project]
name = "cheng"
requires-python = ">=3.11"
dependencies = [
    "cadquery>=2.4",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "numpy>=1.26",
    "pydantic>=2.0",
    "anyio>=4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]
```

### JavaScript (frontend)

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "three": "^0.170.0",
    "@types/three": "^0.170.0",
    "zustand": "^5.0.0",
    "framer-motion": "^11.0.0",
    "idb": "^8.0.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "tailwindcss": "^4.0.0",
    "vitest": "^2.0.0",
    "@playwright/test": "^1.48.0"
  }
}
```

## Appendix C: Coordinate System Convention

```
        Z (up)
        |
        |
        |_______ X (starboard/right)
       /
      /
     Y (forward/nose)
```

- All dimensions in **millimeters**
- Aircraft nose points in +Y direction
- Right wing extends in +X direction
- Up is +Z
- Origin is at the aircraft datum (typically nose or CG)

This matches CadQuery's default XYZ orientation and engineering convention for aircraft.

## Appendix D: Launching the Application

### Local Development (Docker Compose)

```bash
# Start both backend and frontend dev server
docker compose up

# Backend:  http://localhost:8000  (API + health check)
# Frontend: http://localhost:5173  (Vite dev server with HMR)
```

### Local Production (Single Container)

```bash
# Build the production image
docker build -t cheng .

# Run with persistent storage
docker run -p 8000:8000 -v cheng-data:/data -e CHENG_MODE=local cheng

# Open http://localhost:8000
```

### Cloud Run Deployment

```bash
# Build, push, and deploy
docker build -t gcr.io/PROJECT/cheng .
docker push gcr.io/PROJECT/cheng

gcloud run deploy cheng \
  --image gcr.io/PROJECT/cheng \
  --memory 2Gi --cpu 2 \
  --min-instances 0 --max-instances 10 \
  --set-env-vars CHENG_MODE=cloud

# Service URL printed by gcloud
```

### Health Check

```bash
# Verify the application is running
curl http://localhost:8000/health
# {"status": "healthy", "mode": "local"}
```
