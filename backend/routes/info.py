"""GET /api/info -- Returns deployment mode and app metadata.

Reads the CHENG_MODE environment variable (default: "local").
Used by the frontend to display the mode badge in the toolbar.

Issue #149 (CHENG_MODE toggle), #152 (Mode badge)
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["info"])

_VALID_MODES = {"local", "cloud"}


@router.get("/info")
async def get_info(request: Request) -> dict:
    """Return deployment mode and app version.

    Reads CHENG_MODE from the environment (default: "local").
    The version is sourced dynamically from the FastAPI app metadata.

    Returns:
        mode: "local" or "cloud" (default: "local")
        version: app version string from main.py
    """
    raw = os.environ.get("CHENG_MODE", "local").strip().lower()
    mode = raw if raw in _VALID_MODES else "local"
    return {"mode": mode, "version": request.app.version}
