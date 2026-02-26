# CHENG — Parametric RC Plane Generator

## Project Overview
Containerized web app for designing 3D-printable RC aircraft. Users adjust parameters (wingspan, airfoil, tail config) and export sectioned STL files for home FDM printers.

## Canonical Reference
- **`docs/mvp_spec.md`** is the single source of truth for MVP scope. If any other doc conflicts, the spec wins.
- 8 source docs in `docs/`: product_requirements, architecture, implementation, ux_design, aero_parameters, cross_review_aero, cross_review_pm, cross_review_ux

## Tech Stack
- **Backend:** Python 3.11, FastAPI, CadQuery/OpenCascade, uvicorn
- **Frontend:** React 19, TypeScript (strict), Vite 6, Three.js via R3F, Zustand + Zundo + Immer, Radix Primitives, Tailwind CSS 4, pnpm
- **Deployment:** Single Docker container, port 8000. Local mode (volume mount) or Cloud Run (stateless).
- **Storage:** `LocalStorage` (JSON files on Docker volume at `/data/designs/`) or `MemoryStorage` (in-memory, cloud mode)
- **Package management:** uv (Python), pnpm (frontend)

## Key Architecture Decisions
- Single Docker container serves both backend API and frontend static files
- `CHENG_MODE` env var (`local` | `cloud`, default `local`) toggles storage backend and CORS policy
- `StorageBackend` Protocol + `LocalStorage` (file-backed) + `MemoryStorage` (in-memory, cloud) implementations
- `GET /api/info` returns `{mode, version, storage}` — frontend reads this to show mode badge and adapt behaviour
- In cloud mode: browser persists designs via IndexedDB; backend is stateless (no `/data` volume needed)
- CadQuery runs in thread pool with `CapacityLimiter(4)` — shared across REST, WebSocket, export
- WebSocket `/ws/preview` is primary communication channel (binary mesh protocol)
- WebSocket uses `anyio.create_task_group()` with separate reader/generator tasks for non-blocking cancellation
- Temp file cleanup runs at startup + every 30min via `backend/cleanup.py`
- REST endpoints at `/api/*` as fallback
- Export writes temp ZIP to `/data/tmp/`, streams to client, then deletes
- Frontend state in Zustand store with Zundo undo/redo

## Current Scope
- ~56 user-configurable params + 12 derived/read-only values (incl. weight estimates)
- 6 presets: Trainer (1200mm), Sport (1000mm), Aerobatic (900mm), Glider, FlyingWing, Scale + custom save/load
- Export: STL (sectioned), STEP, DXF, SVG + test joint print piece (`/api/export/test-joint`)
- Auto-sectioning with smart split-point optimizer (avoids spar channels + wing junction)
- 8 structural warnings (V01-V08) + 5 aero warnings (V09-V13) + 7 print warnings (V16-V23) + 5 printability warnings (V24-V28) + V29 multi-section + V30 control surfaces + V31 landing gear, all non-blocking
- Bidirectional parameter editing (chord/aspect ratio)
- Per-component print settings, weight estimation, full CG calculator
- Multi-section wings (W08-W11): cranked/polyhedral planforms up to 4 panels
- Control surfaces (C01-C24): ailerons, elevator, rudder, ruddervators, elevons with hinge cuts
- Landing gear (L01-L11): tricycle, taildragger, or none
- Cloud Run deployment: `CHENG_MODE=cloud`, cold start UX (skeleton loader), mode badge in toolbar

## Implementation Status
- **v0.8 (Cloud Deployment):** Complete — CHENG_MODE toggle, MemoryStorage, IndexedDB persistence, Cloud Run config, cold start UX, mode badge. PRs #292-#296.
- All prior milestones (Phase 0 → v0.7.2) complete. See MEMORY.md for full history.
- **App is fully functional:** Geometry, preview, export, validation, Docker, Cloud Run all working.

## Dev Scripts
- `bootup.ps1` — Builds frontend + starts both servers. Use `-r` for backend `--reload`.
- `shutdown.ps1` — Kills processes on ports 8000/5173.
- Run: `powershell -ExecutionPolicy Bypass -File .\bootup.ps1`
- **Env vars:** `CHENG_DATA_DIR` (storage path, default `/data/designs`), `VITE_API_URL` (proxy target, default `http://localhost:8000`), `CHENG_MODE` (`local` | `cloud`, default `local`)

## CadQuery Gotchas
- **XZ Workplane Axis:** local Y = global Z (vertical), local Z = global -Y (spanwise). Use `transformed(offset=(0, z, 0))` for vertical, NOT `(0, 0, z)`
- **Dihedral:** Apply via `.rotate()` AFTER lofting, not translation. Rotate at root attachment point to avoid angling root face.
- **Airfoil rotation:** `z_rot = -(dx * sin_r) + z * cos_r` — positive incidence = nose up
- **Shell face selectors:** Use `solid.faces('<Y').shell(-t)` to leave root face open (right wing), `'>Y'` for left wing
- **Loft:** Must use chained `.workplane(offset=delta).ellipse().loft()` — NOT `.add()` from separate Workplanes
- **Splines:** Use `.spline(pts, periodic=False).close()` for loft cross-sections
- **Shell:** `.shell(-thickness)` often fails on complex lofts — always try/except with fallback
- **Preview:** Tessellate components individually (no boolean union) and disable hollow_parts

## Conventions
- Python: snake_case, Pydantic models, type hints
- TypeScript: strict mode, camelCase
- **API naming:** `CamelModel` base class (Pydantic `alias_generator=to_camel`). Use `model_dump(by_alias=True)` for frontend. Backend storage stays snake_case.
- **Validation:** Canonical module is `backend/validation.py` (V01-V08 structural, V09-V13 aero, V16-V23 print, V24-V28 printability, V29 multi-section wing, V30 control surfaces, V31 landing gear). Never duplicate in engine.py.
- Parameter IDs use subsystem prefixes: G (Global), W (Wing), T (Tail), F (Fuselage), P (Propulsion), PR (Print/Export), D (Derived)
- Pydantic model uses flat structure with snake_case field names matching parameter names

## Testing
- **Backend:** `python -m pytest tests/backend/ -v` (NOT `backend/tests/`)
- **Frontend Vitest:** `cd frontend && pnpm test`
- **Playwright E2E:** `cd frontend && NODE_PATH=./node_modules npx playwright test` (requires app running via `bootup.ps1`)
- E2E targets `localhost:5173` locally (Vite dev), `localhost:8000` in Docker (set `PLAYWRIGHT_BASE_URL`)
- WebSocket binary frame: header(12B) + vertices(N*12) + normals(N*12) + faces(M*12) + JSON trailer (componentRanges, derived, warnings)

## AI Collaboration (Gemini CLI)
- Gemini is used by the developer agent for peer review. See `.claude/agents/developer.md` for the full protocol.
- For ad-hoc queries: `gemini -m flash "prompt"` (syntax/speed) or `gemini -m pro "prompt"` (aero-math/logic)
- Run async: `gemini --output-format json "prompt" > .gemini_res.json &`

## File Search Rules
- NEVER use `find` or `find.exe` for any reason. Use Glob or Grep instead.
- NEVER search from `/`, `C:\`, or any root path.
- The project root is wherever this CLAUDE.md file lives. All searches must be scoped to this directory tree.
- To find a file by name: Glob pattern `**/filename.ts`
- To find content: Grep with the pattern scoped to `./`
