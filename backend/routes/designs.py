"""Design CRUD routes — GET/POST/DELETE /api/designs.

Uses dependency injection for the StorageBackend so that tests can
swap in a temporary directory.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.models import AircraftDesign, DesignSummary
from backend.storage import StorageBackend, create_storage_backend

router = APIRouter(prefix="/api/designs", tags=["designs"])

# ---------------------------------------------------------------------------
# Dependency: default storage backend
# ---------------------------------------------------------------------------

_default_storage: StorageBackend | None = None


def _get_storage() -> StorageBackend:
    """FastAPI dependency returning the active StorageBackend.

    On first call the backend is created by ``create_storage_backend()``, which
    reads ``CHENG_MODE`` (and ``CHENG_DATA_DIR`` for local mode) from the
    environment.  Tests may call ``set_storage()`` to inject a different backend.
    """
    global _default_storage  # noqa: PLW0603
    if _default_storage is None:
        _default_storage = create_storage_backend()
    return _default_storage


def set_storage(storage: StorageBackend) -> None:
    """Override the default storage backend (used by tests and main.py)."""
    global _default_storage  # noqa: PLW0603
    _default_storage = storage


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[DesignSummary], response_model_by_alias=True)
async def list_designs(storage: StorageBackend = Depends(_get_storage)) -> list[DesignSummary]:
    """Return summaries of all saved designs, sorted newest first."""
    raw = storage.list_designs()
    return [DesignSummary(**d) for d in raw]


@router.post("", status_code=201)
async def save_design(
    design: AircraftDesign,
    storage: StorageBackend = Depends(_get_storage),
) -> dict:
    """Save a design.  Assigns a UUID if the id field is missing or empty.

    If an id is provided and already exists, the design is overwritten
    (upsert semantics per spec section 6.1).
    """
    if not design.id:
        design.id = str(uuid4())
    storage.save_design(design.id, design.model_dump())
    return {"id": design.id}


@router.get("/{design_id}", response_model=AircraftDesign, response_model_by_alias=True)
async def load_design(
    design_id: str,
    storage: StorageBackend = Depends(_get_storage),
) -> AircraftDesign:
    """Load a saved design by id.  Returns 404 if not found."""
    try:
        data = storage.load_design(design_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design not found: {design_id}")
    return AircraftDesign(**data)


@router.delete("/{design_id}", status_code=204)
async def delete_design(
    design_id: str,
    storage: StorageBackend = Depends(_get_storage),
) -> Response:
    """Delete a saved design.  Returns 404 if not found."""
    try:
        storage.delete_design(design_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design not found: {design_id}")
    return Response(status_code=204)
