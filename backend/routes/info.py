"""Info route — exposes runtime configuration to the frontend.

GET /api/info returns the current CHENG_MODE so the UI can adapt its
behaviour (e.g. hide "Save design" in cloud mode where storage is stateless).
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.storage import get_cheng_mode

router = APIRouter(prefix="/api", tags=["info"])


@router.get("/info")
async def get_info() -> dict:
    """Return runtime information about the current CHENG deployment.

    Response fields
    ---------------
    mode : str
        ``"local"`` — file-backed Docker container (default).
        ``"cloud"`` — stateless Cloud Run instance; no server-side persistence.
    version : str
        Application version string.
    storage : str
        Human-readable description of the active storage backend.
    """
    mode = get_cheng_mode()
    storage_desc = (
        "LocalStorage (file-based, /data/designs/)"
        if mode == "local"
        else "MemoryStorage (in-memory, ephemeral)"
    )
    return {
        "mode": mode,
        "version": "0.1.0",
        "storage": storage_desc,
    }
