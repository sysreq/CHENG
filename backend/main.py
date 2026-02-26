"""FastAPI application — entry point for CHENG backend.

Lifespan preloads CadQuery, registers route modules, serves health endpoint,
and mounts static files for the SPA frontend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.cleanup import cleanup_tmp_files, periodic_cleanup
from backend.export.package import EXPORT_TMP_DIR
from backend.routes.designs import router as designs_router
from backend.routes.generate import router as generate_router
from backend.routes.export import router as export_router
from backend.routes.info import router as info_router
from backend.routes.presets import router as presets_router
from backend.routes.websocket import router as websocket_router

logger = logging.getLogger("cheng")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup tasks:
    1. Pre-warm CadQuery/OpenCascade kernel (first import takes ~2-4 s)
    2. Ensure /data/tmp directory exists for export temp files
    """
    # 1. CadQuery warm-up with graceful degradation
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

    # 2. Ensure export tmp directory exists (needed outside Docker).
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

    # 3. Ensure designs storage directory exists
    designs_dir = Path("/data/designs")
    try:
        designs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.info("Cannot create /data/designs — using default storage path")

    # 4. Ensure presets storage directory exists
    presets_dir = Path("/data/presets")
    try:
        presets_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Presets directory ready: %s", presets_dir)
    except OSError:
        logger.info("Cannot create /data/presets — presets will use module default")

    # 5. Clean up orphaned temp files from previous runs (#181)
    try:
        deleted = cleanup_tmp_files(tmp_dir)
        if deleted:
            logger.info("Startup cleanup: removed %d orphaned temp file(s)", deleted)
    except Exception:
        logger.warning("Startup temp cleanup failed", exc_info=True)

    # 6. Start periodic cleanup task (runs every 30 min)
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
app.include_router(info_router)
app.include_router(presets_router)
app.include_router(websocket_router)


# ---------------------------------------------------------------------------
# Health check (before static mount so it is not shadowed)
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Static files mount MUST be last — catches all unmatched routes and
# serves index.html for SPA client-side routing.
# ---------------------------------------------------------------------------
_static_dir = Path("static")
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
