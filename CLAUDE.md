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

## MVP Scope
- 33 user-configurable params + 8 derived/read-only values
- 3 presets: Trainer (1200mm), Sport (1000mm), Aerobatic (900mm)
- STL export only (STEP/DXF deferred to 1.0)
- Auto-sectioning with tongue-and-groove joints
- 6 structural warnings (V01-V06) + 7 print warnings (V16-V23), all non-blocking

## Implementation Status
- **Phase 0 (Scaffold):** Complete — project structure, models, types, stores, presets
- **Phase 1 (Parallel):** Complete — 4 tracks merged (Backend API, Geometry Engine, Frontend Core, Frontend Panels)
- **Phase 2 (Integration):** Complete — WebSocket, generate, export routes wired. 166 tests passing.
- **Phase 3 (Polish):** Not started — Docker build, acceptance criteria, bug fixes
- **App is functional:** Backend generates CadQuery geometry, sends binary mesh via WebSocket, frontend renders in Three.js

## Dev Scripts
- `startup.ps1` — Builds frontend + starts both servers. Use `-r` for backend `--reload`.
- `shutdown.ps1` — Kills processes on ports 8000/5173.
- Run: `powershell -ExecutionPolicy Bypass -File .\startup.ps1`

## CadQuery Gotchas
- **Loft:** Must use chained `.workplane(offset=delta).ellipse().loft()` — NOT `.add()` from separate Workplanes
- **Splines:** Use `.spline(pts, periodic=False).close()` for loft cross-sections
- **Shell:** `.shell(-thickness)` often fails on complex lofts — always try/except with fallback
- **Preview:** Tessellate components individually (no boolean union) and disable hollow_parts

## Conventions
- Python: snake_case, Pydantic models, type hints
- TypeScript: strict mode, camelCase
- Parameter IDs use subsystem prefixes: G (Global), W (Wing), T (Tail), F (Fuselage), P (Propulsion), PR (Print/Export), D (Derived)
- Pydantic model uses flat structure with snake_case field names matching parameter names

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