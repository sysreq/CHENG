"""GET /api/info — Returns deployment mode and app metadata.

Reads the CHENG_MODE environment variable (default: "local").
Used by the frontend to display the mode badge in the toolbar.

Issue #149 (CHENG_MODE toggle), #152 (Mode badge)
"""

from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["info"])

_VALID_MODES = {"local", "cloud"}


@router.get("/info")
async def get_info() -> dict:
    """Return deployment mode and app version.

    Returns:
        mode: "local" or "cloud" (default: "local")
        version: app version string
    """
    raw = os.environ.get("CHENG_MODE", "local").strip().lower()
    mode = raw if raw in _VALID_MODES else "local"
    return {"mode": mode, "version": "0.1.0"}
