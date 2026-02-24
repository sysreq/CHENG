"""POST /api/generate — REST fallback for geometry generation.

Used when WebSocket is unavailable. Returns derived values and warnings.
Mesh data is not included in REST response (use WebSocket for live preview).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.geometry.engine import compute_derived_values
from backend.models import (
    AircraftDesign,
    DerivedValues,
    GenerationResult,
)
from backend.validation import compute_warnings

logger = logging.getLogger("cheng.generate")

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate", response_model=GenerationResult, response_model_by_alias=True)
async def generate(design: AircraftDesign) -> GenerationResult:
    """Compute derived values and validation warnings for a design.

    This is the REST fallback — it returns derived values and warnings
    but does NOT return mesh data. Use the WebSocket /ws/preview for
    interactive 3D preview with mesh.
    """
    try:
        derived_dict = compute_derived_values(design)
        derived = DerivedValues(**derived_dict)
        warnings = compute_warnings(design)

        return GenerationResult(derived=derived, warnings=warnings)

    except Exception as exc:
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
