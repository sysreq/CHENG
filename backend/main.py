"""FastAPI application — entry point for CHENG backend.

Lifespan preloads CadQuery, registers route modules, serves health endpoint,
and mounts static files for the SPA frontend.

Deployment modes (CHENG_MODE env var):
  local (default) — Docker with volume mount; backend disk storage saves designs.
  cloud           — Cloud Run; stateless. Design persistence is handled by the
                    browser (IndexedDB). CORS is opened to all origins so the
                    Cloud Run URL can be reached from any browser.
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
from backend.routes.designs import router as designs_router
from backend.routes.generate import router as generate_router
from backend.routes.export import router as export_router
from backend.routes.info import router as info_router
from backend.routes.presets import router as presets_router
from backend.routes.websocket import router as websocket_router
from backend.storage import get_cheng_mode

logger = logging.getLogger("cheng")

# ---------------------------------------------------------------------------
# Deployment mode
# ---------------------------------------------------------------------------

CHENG_MODE: str = os.environ.get("CHENG_MODE", "local").lower()
"""'local' (default) or 'cloud'.  Controls storage behavior and CORS policy."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup tasks:
    1. Pre-warm CadQuery/OpenCascade kernel (first import takes ~2-4 s)
    2. Ensure /data/tmp directory exists for export temp files
    """
    # Log active mode so operators can confirm deployment configuration
    mode = get_cheng_mode()
    logger.info("CHENG_MODE=%s", mode)

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

    # 3. Ensure designs storage directory exists (local mode only; cloud is stateless)
    if mode == "local":
        designs_dir = Path(os.environ.get("CHENG_DATA_DIR", "/data/designs"))
        try:
            designs_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.info("Cannot create %s — using default storage path", designs_dir)

        # 4. Ensure presets storage directory exists (local mode only)
        presets_dir = designs_dir.parent / "presets"
        try:
            presets_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Presets directory ready: %s", presets_dir)
        except OSError:
            logger.info("Cannot create %s — presets will use module default", presets_dir)
    else:
        logger.info("Cloud mode: skipping persistent storage directory creation")

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
# CORS middleware
# ---------------------------------------------------------------------------
# local mode: allow only the Vite dev server (same host, different port)
# cloud mode: allow all origins — Cloud Run URL changes per project/region and
#             the browser frontend is served from the same container anyway.
# CHENG_CORS_ORIGINS env var lets operators override the default for either mode.
# It supports a comma-separated list, e.g. "https://a.example.com,https://b.example.com"
# or "*" to allow all origins explicitly.
_cors_origins_env: str = os.environ.get("CHENG_CORS_ORIGINS", "")
if _cors_origins_env:
    _allow_origins: list[str] = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    # Wildcard in the explicit override list also disables credentials.
    _allow_all = "*" in _allow_origins
elif CHENG_MODE == "cloud":
    _allow_origins = ["*"]
    _allow_all = True
else:
    _allow_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    _allow_all = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    # allow_credentials must be False when allow_origins=["*"] (browser CORS spec).
    # Starred wildcard and credentials=True together cause a FastAPI RuntimeError.
    allow_credentials=not _allow_all,
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
    """Health check endpoint used by Cloud Run and Docker HEALTHCHECK."""
    return {"status": "ok", "version": "0.1.0", "mode": CHENG_MODE}


# ---------------------------------------------------------------------------
# Static files mount MUST be last — catches all unmatched routes and
# serves index.html for SPA client-side routing.
# ---------------------------------------------------------------------------
_static_dir = Path("static")
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
