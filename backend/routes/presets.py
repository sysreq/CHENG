"""Custom presets CRUD routes — GET/POST/DELETE /api/presets.

Uses a StorageBackend instance for storing custom presets.
In local mode: LocalStorage at /data/presets/ (injected by main.py).
In cloud mode: MemoryStorage — presets are session-scoped (injected by main.py).

Follows same dependency injection pattern as designs.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.models import AircraftDesign, PresetSummary, SavePresetRequest
from backend.storage import LocalStorage, MemoryStorage, StorageBackend

router = APIRouter(prefix="/api/presets", tags=["presets"])

# ---------------------------------------------------------------------------
# Dependency: preset storage backend
# ---------------------------------------------------------------------------

_default_storage: StorageBackend | None = None


def _get_storage() -> StorageBackend:
    """FastAPI dependency returning the preset storage backend.

    The backend is normally injected at startup by main.py via set_storage().
    Falls back to auto-detecting from CHENG_MODE when not injected (e.g. in
    tests that only configure the design storage).
    """
    global _default_storage  # noqa: PLW0603
    if _default_storage is None:
        cheng_mode = os.environ.get("CHENG_MODE", "local").lower()
        if cheng_mode == "cloud":
            _default_storage = MemoryStorage()
        else:
            data_dir = os.environ.get("CHENG_DATA_DIR", "/data/designs")
            parent = str(Path(data_dir).parent)
            presets_dir = str(Path(parent) / "presets")
            _default_storage = LocalStorage(base_path=presets_dir)
    return _default_storage


def set_storage(storage: StorageBackend | None) -> None:
    """Override the default preset storage (called by main.py and tests)."""
    global _default_storage  # noqa: PLW0603
    _default_storage = storage


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[PresetSummary], response_model_by_alias=True)
async def list_presets(
    storage: StorageBackend = Depends(_get_storage),
) -> list[PresetSummary]:
    """Return summaries of all saved custom presets, sorted newest first."""
    raw = storage.list_designs()  # reuses same file listing logic
    # Map modified_at -> created_at for preset semantics
    return [
        PresetSummary(
            id=d["id"],
            name=d.get("name", "Untitled Preset"),
            created_at=d.get("modified_at", ""),
        )
        for d in raw
    ]


@router.get("/{preset_id}", response_model_by_alias=True)
async def get_preset(
    preset_id: str,
    storage: StorageBackend = Depends(_get_storage),
) -> dict:
    """Load a single custom preset's full data. Returns 404 if not found."""
    try:
        data = storage.load_design(preset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")
    return data


@router.post("", status_code=201)
async def save_preset(
    request: SavePresetRequest,
    storage: StorageBackend = Depends(_get_storage),
) -> dict:
    """Save current design parameters as a named custom preset.

    Generates a UUID, stores the design data with preset metadata,
    and returns the id and name.
    """
    preset_id = str(uuid4())
    now = datetime.now(tz=timezone.utc).isoformat()

    # Store the full design data plus preset metadata
    preset_data = request.design.model_dump()
    preset_data["preset_id"] = preset_id
    preset_data["preset_name"] = request.name
    preset_data["created_at"] = now
    # Override the name field so list_designs picks it up
    preset_data["name"] = request.name

    storage.save_design(preset_id, preset_data)

    return {"id": preset_id, "name": request.name}


@router.delete("/{preset_id}", status_code=204)
async def delete_preset(
    preset_id: str,
    storage: StorageBackend = Depends(_get_storage),
) -> Response:
    """Delete a custom preset. Returns 404 if not found."""
    try:
        storage.delete_design(preset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")
    return Response(status_code=204)
