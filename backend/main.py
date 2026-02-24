"""FastAPI application — entry point for CHENG backend.

Lifespan preloads CadQuery, registers route modules, serves health endpoint,
and mounts static files for the SPA frontend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routes.designs import router as designs_router

logger = logging.getLogger("cheng")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload CadQuery on startup — first import takes ~2-4 s.

    Running a trivial box operation warms up the OpenCascade kernel so the
    first real /api/generate request doesn't pay the cold-start penalty.
    """
    try:
        import cadquery as cq

        cq.Workplane("XY").box(1, 1, 1)  # warm up OpenCascade kernel
        logger.info("CadQuery preloaded successfully")
    except ImportError:
        logger.warning("CadQuery not available — geometry endpoints will not work")
    yield


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

# Phase 2 routes — import routers when they are implemented
# from backend.routes.generate import router as generate_router
# from backend.routes.export import router as export_router
# from backend.routes.websocket import router as websocket_router
# app.include_router(generate_router)
# app.include_router(export_router)
# app.include_router(websocket_router)


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
