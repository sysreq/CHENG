# CHENG — Parametric RC Plane Generator

## Project Overview
Containerized web app for designing 3D-printable RC aircraft. Users adjust parameters (wingspan, airfoil, tail config) and export sectioned STL files for home FDM printers.

## Canonical Reference
- **`docs/mvp_spec.md`** is the single source of truth for MVP scope. If any other doc conflicts, the spec wins.
- 8 source docs in `docs/`: product_requirements, architecture, implementation, ux_design, aero_parameters, cross_review_aero, cross_review_pm, cross_review_ux

## Tech Stack (MVP)
- **Backend:** Python 3.11, FastAPI, CadQuery/OpenCascade, uvicorn
- **Frontend:** React 19, TypeScript (strict), Vite 6, Three.js via R3F, Zustand + Zundo + Immer, Radix Primitives, Tailwind CSS 4, pnpm
- **Deployment:** Single Docker container, port 8000, local only (no Cloud Run in MVP)
- **Storage:** JSON files on Docker volume at `/data/designs/`
- **Package management:** uv (Python), pnpm (frontend)

## Key Architecture Decisions
- Single Docker container serves both backend API and frontend static files
- CadQuery runs in thread pool with `CapacityLimiter(4)` — shared across REST, WebSocket, export
- WebSocket `/ws/preview` is primary communication channel (binary mesh protocol)
- REST endpoints at `/api/*` as fallback
- `StorageBackend` Protocol + `LocalStorage` implementation
- Export writes temp ZIP to `/data/tmp/`, streams to client, then deletes
- Frontend state in Zustand store with Zundo undo/redo

## Current Scope
- 39 user-configurable params + 8 derived/read-only values
- 3 presets: Trainer (1200mm), Sport (1000mm), Aerobatic (900mm)
- Export: STL (sectioned), STEP, DXF, SVG
- Auto-sectioning with tongue-and-groove joints
- 8 structural warnings (V01-V08) + 7 print warnings (V16-V23), all non-blocking
- Bidirectional parameter editing (chord/aspect ratio)
- Per-component print settings (wing, tail, fuselage)

## Implementation Status
- **Phase 0 (Scaffold):** Complete — project structure, models, types, stores, presets
- **Phase 1 (Parallel):** Complete — 4 tracks merged (Backend API, Geometry Engine, Frontend Core, Frontend Panels)
- **Phase 2 (Integration):** Complete — WebSocket, generate, export routes wired. 166 tests passing.
- **Phase 3 (Polish):** Complete — issues #39-#82 fixed. 228 backend + 42 frontend + 7 E2E tests.
- **Phase 4 (Bugfix):** Complete — issues #83-#115 fixed. Backend/geometry fixes, frontend UX polish, responsive layout.
- **v0.2 (Export Formats):** Complete — STEP/DXF/SVG export, export preview, aero-audit fixes. 271 tests.
- **v0.3 (Advanced Params):** Complete — 6 params promoted, fuselage panel, bidirectional editing, per-component print settings, 8 UX fixes. 283+53+7 tests.
- **App is fully functional:** Geometry, preview, export, validation, Docker all working

## Dev Scripts
- `startup.ps1` — Builds frontend + starts both servers. Use `-r` for backend `--reload`.
- `shutdown.ps1` — Kills processes on ports 8000/5173.
- Run: `powershell -ExecutionPolicy Bypass -File .\startup.ps1`
- **Env vars:** `CHENG_DATA_DIR` (storage path, default `/data/designs`), `VITE_API_URL` (proxy target, default `http://localhost:8000`)

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
- **Validation:** Canonical module is `backend/validation.py` (V01-V08 structural, V16-V23 print). Never duplicate in engine.py.
- Parameter IDs use subsystem prefixes: G (Global), W (Wing), T (Tail), F (Fuselage), P (Propulsion), PR (Print/Export), D (Derived)
- Pydantic model uses flat structure with snake_case field names matching parameter names

## Testing
- **Backend:** `python -m pytest tests/backend/ -v` (NOT `backend/tests/`)
- **Frontend Vitest:** `cd frontend && pnpm test`
- **Playwright E2E:** `cd frontend && NODE_PATH=./node_modules npx playwright test` (requires app running via `startup.ps1`)
- E2E targets `localhost:5173` locally (Vite dev), `localhost:8000` in Docker (set `PLAYWRIGHT_BASE_URL`)
- WebSocket binary frame: header(12B) + vertices(N*12) + normals(N*12) + faces(M*12) + JSON trailer (componentRanges, derived, warnings)

## AI Collaboration Protocol (Gemini CLI)
Use Gemini as a stateless "Staff Engineer" for deep context and validation.

### Workflow:
1. **Research & Audit:** Use Gemini for queries involving web search or full-repo analysis.
2. **Asynchronous Reasoning:** Command: `gemini --output-format json "prompt" > .gemini_res.json &`
3. **Complex Logic:** Use Gemini Pro to verify math or advanced algorithms(e.g., lift-induced drag coefficients or center of pressure shifts).
4. **Context Expansion:** Summarize large dependencies (like the CadQuery source) and save to `docs/context_cache/`.

### Usage Pattern:
Run the command via your terminal execution capability:
- Use `run_in_background: true` when calling Gemini.
- Continue with other tasks. Use `/bashes` to monitor status.
- **Topological Audit Example:** `gemini "Review this CadQuery lofting logic for self-intersection: [PASTE_CODE]"`

### Constraints:
- Use Gemini Flash (`-m flash`) for speed/syntax.
- Use Gemini Pro (`-m pro`) for aero-math/logic.
- **No Infinite Loops:** Agents must not call each other in a recursive loop without user intervention.

### Formatting Guidelines:
- State: "Consulting Gemini for [TASK DETAILS]"
- Summarize findings from `.gemini_res.json` before applying code changes.