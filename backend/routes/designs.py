"""Design CRUD routes — GET/POST/DELETE /api/designs.

Also provides import/export endpoints for design portability between cloud
and local modes (Issue #156):
  POST /api/designs/import  — Upload a .cheng JSON file; saves it and returns id.
  GET  /api/designs/{id}/download — Download a stored design as a .cheng JSON file.

Uses dependency injection for the StorageBackend so that tests can
swap in a temporary directory.
"""

from __future__ import annotations

import json
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

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


@router.post("/import", status_code=201)
async def import_design(
    file: UploadFile,
    storage: StorageBackend = Depends(_get_storage),
) -> dict:
    """Import a design from an uploaded .cheng JSON file.

    Validates that the uploaded content is a valid AircraftDesign, assigns a
    fresh UUID (to avoid collision with existing designs), saves it to the
    active storage backend, and returns ``{"id": "<new-uuid>"}``.

    Accepts files up to 1 MB.  Returns 400 for invalid JSON or schema errors.
    Returns 507 if the storage backend is at capacity (cloud mode only).
    """
    MAX_BYTES = 1 * 1024 * 1024  # 1 MB

    # Read and size-check the upload
    raw_bytes = await file.read(MAX_BYTES + 1)
    if len(raw_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is too large (max 1 MB).",
        )

    # Parse JSON
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {exc}",
        )

    # Validate against AircraftDesign schema
    try:
        design = AircraftDesign(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid design file: {exc}",
        )

    # Always assign a fresh UUID to prevent id collisions when importing
    # a design that was originally saved under a different backend instance.
    design.id = str(uuid4())

    try:
        storage.save_design(design.id, design.model_dump())
    except MemoryError as exc:
        raise HTTPException(status_code=507, detail=str(exc))

    return {"id": design.id}


@router.get("/{design_id}/download")
async def download_design(
    design_id: str,
    storage: StorageBackend = Depends(_get_storage),
) -> Response:
    """Download a stored design as a .cheng JSON file.

    Returns the design data as ``application/json`` with a
    ``Content-Disposition: attachment`` header so that browsers trigger a
    file-save dialog.  The filename is derived from the design name.

    Returns 404 if the design does not exist.
    """
    try:
        data = storage.load_design(design_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design not found: {design_id}")

    # Build a safe filename from the design name
    raw_name: str = data.get("name", "design") or "design"
    # Replace non-alphanumeric chars (except hyphens/underscores) with underscores
    safe_name = re.sub(r"[^\w\-]", "_", raw_name).strip("_") or "design"
    filename = f"{safe_name}.cheng"

    return Response(
        content=json.dumps(data, indent=2).encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


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
