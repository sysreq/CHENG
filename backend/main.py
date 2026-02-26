"""FastAPI application — entry point for CHENG backend.

Lifespan preloads CadQuery, registers route modules, serves health endpoint,
and mounts static files for the SPA frontend.

CHENG_MODE environment variable controls storage behaviour:
  local (default) — LocalStorage writes JSON files to /data/designs/
  cloud           — MemoryStorage keeps designs in-memory (stateless backend)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.cleanup import cleanup_tmp_files, periodic_cleanup
from backend.export.package import EXPORT_TMP_DIR
from backend.routes.designs import router as designs_router, set_storage as set_design_storage
from backend.routes.generate import router as generate_router
from backend.routes.export import router as export_router
from backend.routes.presets import router as presets_router, set_storage as set_preset_storage
from backend.routes.websocket import router as websocket_router
from backend.storage import LocalStorage, MemoryStorage

logger = logging.getLogger("cheng")

# ---------------------------------------------------------------------------
# CHENG_MODE — choose storage backend at startup
# ---------------------------------------------------------------------------

CHENG_MODE = os.environ.get("CHENG_MODE", "local").lower()


def _create_design_storage():
    """Instantiate the appropriate design storage backend based on CHENG_MODE."""
    if CHENG_MODE == "cloud":
        logger.info("CHENG_MODE=cloud — using MemoryStorage for designs (stateless backend)")
        return MemoryStorage()
    else:
        data_dir = os.environ.get("CHENG_DATA_DIR", "/data/designs")
        logger.info("CHENG_MODE=%s — using LocalStorage for designs at %s", CHENG_MODE, data_dir)
        return LocalStorage(base_path=data_dir)


def _create_preset_storage():
    """Instantiate the appropriate preset storage backend based on CHENG_MODE."""
    if CHENG_MODE == "cloud":
        logger.info("CHENG_MODE=cloud — using MemoryStorage for presets (session-scoped)")
        return MemoryStorage()
    else:
        data_dir = os.environ.get("CHENG_DATA_DIR", "/data/designs")
        parent = str(Path(data_dir).parent)
        presets_dir = str(Path(parent) / "presets")
        logger.info("CHENG_MODE=%s — using LocalStorage for presets at %s", CHENG_MODE, presets_dir)
        return LocalStorage(base_path=presets_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup tasks:
    1. Configure storage backend based on CHENG_MODE
    2. Pre-warm CadQuery/OpenCascade kernel (first import takes ~2-4 s)
    3. Ensure /data/tmp directory exists for export temp files
    """
    # 1. Configure storage backends (designs and presets are separate namespaces)
    design_storage = _create_design_storage()
    preset_storage = _create_preset_storage()
    set_design_storage(design_storage)
    set_preset_storage(preset_storage)

    # 2. CadQuery warm-up with graceful degradation
    try:
        import cadquery as cq

        cq.Workplane("XY").box(1, 1, 1)  # warm up OpenCascade kernel
        logger.info("CadQuery preloaded successfully")
    except ImportError:
        logger.warning(
            "CadQuery not installed — geometry and export endpoints will return errors. "
            "Install with: pip install cadquery"
        )
    except Exception as exc:
        logger.warning("CadQuery warm-up failed: %s — geometry may be slow on first request", exc)

    # 3. Ensure export tmp directory exists (needed outside Docker).
    # Use the authoritative EXPORT_TMP_DIR constant from the export module so
    # this path is always in sync with where exports actually write (#262, #276).
    tmp_dir = EXPORT_TMP_DIR
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Export tmp directory ready: %s", tmp_dir)
    except OSError:
        # On Windows or non-Docker, the directory may not be writable.
        # Fall back to system temp — the export module handles this via EXPORT_TMP_DIR.
        logger.info("Cannot create %s — export will use module default", tmp_dir)

    # 4. Ensure designs storage directory exists (local mode only)
    if CHENG_MODE != "cloud":
        designs_dir = Path(os.environ.get("CHENG_DATA_DIR", "/data/designs"))
        try:
            designs_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.info("Cannot create %s — using default storage path", designs_dir)

    # 5. Ensure presets storage directory exists (local mode only — cloud is
    #    a stateless ephemeral environment; presets stored in /data/ would not
    #    persist across container instances)
    if CHENG_MODE != "cloud":
        presets_dir = Path("/data/presets")
        try:
            presets_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Presets directory ready: %s", presets_dir)
        except OSError:
            logger.info("Cannot create /data/presets — presets will use module default")

    # 6. Clean up orphaned temp files from previous runs (#181)
    # In cloud mode the export tmp dir uses the system temp directory, which
    # Cloud Run's container filesystem allows, so cleanup still runs.
    try:
        deleted = cleanup_tmp_files(tmp_dir)
        if deleted:
            logger.info("Startup cleanup: removed %d orphaned temp file(s)", deleted)
    except Exception:
        logger.warning("Startup temp cleanup failed", exc_info=True)

    # 7. Start periodic cleanup task (runs every 30 min)
    async with anyio.create_task_group() as tg:
        tg.start_soon(periodic_cleanup, tmp_dir)
        yield
        tg.cancel_scope.cancel()


app = FastAPI(title="CHENG", version="0.1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS middleware for development (Vite dev server at localhost:5173)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API route registration
# ---------------------------------------------------------------------------
app.include_router(designs_router)
app.include_router(generate_router)
app.include_router(export_router)
app.include_router(presets_router)
app.include_router(websocket_router)


# ---------------------------------------------------------------------------
# Health check (before static mount so it is not shadowed)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0", "mode": CHENG_MODE}


# ---------------------------------------------------------------------------
# Mode endpoint — lets the frontend discover cloud vs local mode
# ---------------------------------------------------------------------------


@app.get("/api/mode")
async def get_mode() -> dict:
    """Return the current CHENG_MODE so the frontend can adjust behaviour.

    In cloud mode the frontend uses IndexedDB for local persistence instead
    of the server-side design API.
    """
    return {"mode": CHENG_MODE}


# ---------------------------------------------------------------------------
# Static files mount MUST be last — catches all unmatched routes and
# serves index.html for SPA client-side routing.
# ---------------------------------------------------------------------------
_static_dir = Path("static")
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
