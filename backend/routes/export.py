"""POST /api/export -- STL export as streaming ZIP.

Generates geometry, auto-sections for print bed, adds joints,
packages as ZIP with manifest, and streams to client.
Temp file on /data/tmp is deleted after streaming (spec section 8.5).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.geometry.engine import assemble_aircraft, _cadquery_limiter
from backend.export.section import auto_section, create_section_parts, SectionPart
from backend.export.joints import add_tongue_and_groove
from backend.export.package import build_zip, EXPORT_TMP_DIR
from backend.models import (
    AircraftDesign,
    ExportRequest,
    ExportPreviewPart,
    ExportPreviewResponse,
)

logger = logging.getLogger("cheng.export")

router = APIRouter(prefix="/api", tags=["export"])

# ---------------------------------------------------------------------------
# Assembly cache -- avoid running CadQuery twice for preview + download
# ---------------------------------------------------------------------------

_assembly_cache: dict[str, dict] = {}
_MAX_CACHE = 4


def _design_cache_key(design: AircraftDesign) -> str:
    """Compute a hash key for caching assembled components."""
    return hashlib.md5(design.model_dump_json().encode()).hexdigest()


def _get_or_assemble(design: AircraftDesign) -> dict:
    """Return cached assembled components or run assemble_aircraft."""
    key = _design_cache_key(design)
    if key in _assembly_cache:
        logger.debug("Assembly cache hit for key %s", key[:8])
        return _assembly_cache[key]

    components = assemble_aircraft(design)

    # Evict oldest entry if cache is full
    if len(_assembly_cache) >= _MAX_CACHE:
        _assembly_cache.pop(next(iter(_assembly_cache)))

    _assembly_cache[key] = components
    return components


def clear_assembly_cache() -> None:
    """Clear the assembly cache (useful for testing)."""
    _assembly_cache.clear()


# ---------------------------------------------------------------------------
# Shared sectioning logic
# ---------------------------------------------------------------------------


def _generate_sections(design: AircraftDesign) -> list[SectionPart]:
    """Assemble aircraft and auto-section all components for the print bed.

    This is the shared traversal logic used by both preview and export.
    Returns a list of SectionPart objects (with solids) ready for further
    processing (joints for export, metadata extraction for preview).
    """
    components = _get_or_assemble(design)

    all_sections: list[SectionPart] = []
    assembly_order = 1

    for comp_name, solid in components.items():
        # Determine side from component name
        if "left" in comp_name:
            side = "left"
        elif "right" in comp_name:
            side = "right"
        else:
            side = "center"

        # Determine component category
        comp_category = comp_name.split("_")[0]
        if comp_category in ("h", "v"):
            comp_category = comp_name.replace("_left", "").replace("_right", "")

        pieces = auto_section(
            solid,
            bed_x=design.print_bed_x,
            bed_y=design.print_bed_y,
            bed_z=design.print_bed_z,
        )

        section_parts = create_section_parts(
            comp_category,
            side,
            pieces,
            start_assembly_order=assembly_order,
        )

        all_sections.extend(section_parts)
        assembly_order += len(section_parts)

    return all_sections


# ---------------------------------------------------------------------------
# Bed fit check -- rotation-aware
# ---------------------------------------------------------------------------


def _fits_on_bed(
    dimensions_mm: tuple[float, float, float],
    bed_x: float,
    bed_y: float,
    bed_z: float,
) -> bool:
    """Check if a part fits on the print bed, considering 90-degree rotation.

    The part can be rotated on the XY plane (swapping X and Y dimensions),
    but Z (height) is always fixed against bed_z.
    """
    dx, dy, dz = dimensions_mm
    fits_xy = (dx <= bed_x and dy <= bed_y) or (dx <= bed_y and dy <= bed_x)
    return fits_xy and dz <= bed_z


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/export")
async def export_stl(request: ExportRequest) -> FileResponse:
    """Generate sectioned STL files and stream as ZIP.

    Pipeline: assemble -> auto-section -> joints -> tessellate -> ZIP -> stream.
    """
    design = request.design

    # Ensure tmp dir exists (may not exist outside Docker)
    EXPORT_TMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Run the blocking export pipeline in a thread with the CadQuery limiter
        zip_path = await anyio.to_thread.run_sync(
            lambda: _export_blocking(design),
            limiter=_cadquery_limiter,
            abandon_on_cancel=True,
        )
    except Exception as exc:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    filename = f"{design.name.replace(' ', '_')}_export.zip"

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(lambda: zip_path.unlink(missing_ok=True)),
    )


@router.post("/export/preview")
async def export_preview(request: ExportRequest) -> ExportPreviewResponse:
    """Preview the sectioned parts without generating files.

    Runs the same assemble + auto_section pipeline but skips joints,
    tessellation and ZIP packaging. Returns part metadata and bed-fit info.
    """
    design = request.design

    try:
        parts_meta = await anyio.to_thread.run_sync(
            lambda: _preview_blocking(design),
            limiter=_cadquery_limiter,
            abandon_on_cancel=True,
        )
    except Exception as exc:
        logger.exception("Export preview failed")
        raise HTTPException(
            status_code=500, detail=f"Export preview failed: {exc}"
        ) from exc

    bed = (design.print_bed_x, design.print_bed_y, design.print_bed_z)
    fits = sum(1 for p in parts_meta if p.fits_bed)
    exceeds = len(parts_meta) - fits

    return ExportPreviewResponse(
        parts=parts_meta,
        total_parts=len(parts_meta),
        bed_dimensions_mm=bed,
        parts_that_fit=fits,
        parts_that_exceed=exceeds,
    )


# ---------------------------------------------------------------------------
# Blocking pipelines (run in thread pool)
# ---------------------------------------------------------------------------


def _preview_blocking(design: AircraftDesign) -> list[ExportPreviewPart]:
    """Synchronous preview pipeline: assemble + section only (no joints/ZIP)."""
    section_parts = _generate_sections(design)

    all_parts: list[ExportPreviewPart] = []
    for sp in section_parts:
        fits = _fits_on_bed(
            sp.dimensions_mm,
            design.print_bed_x,
            design.print_bed_y,
            design.print_bed_z,
        )
        all_parts.append(
            ExportPreviewPart(
                filename=sp.filename,
                component=sp.component,
                side=sp.side,
                section_num=sp.section_num,
                total_sections=sp.total_sections,
                dimensions_mm=sp.dimensions_mm,
                print_orientation=sp.print_orientation,
                assembly_order=sp.assembly_order,
                fits_bed=fits,
            )
        )

    return all_parts


def _export_blocking(design: AircraftDesign) -> Path:
    """Synchronous export pipeline -- runs in thread pool.

    1. Assemble aircraft components + auto-section (shared with preview)
    2. Add tongue-and-groove joints between adjacent sections
    3. Build ZIP with tessellated STLs + manifest
    """
    # 1. Shared assemble + section
    all_sections = _generate_sections(design)

    # 2. Add joints between adjacent sections (grouped by component+side)
    # Group sections by (component, side) to find adjacent pairs
    from collections import defaultdict
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for idx, sp in enumerate(all_sections):
        groups[(sp.component, sp.side)].append(idx)

    for (_comp, _side), indices in groups.items():
        # Sections within a group are already in order by section_num
        sorted_indices = sorted(indices, key=lambda i: all_sections[i].section_num)
        for j in range(len(sorted_indices) - 1):
            i_left = sorted_indices[j]
            i_right = sorted_indices[j + 1]
            try:
                left_solid, right_solid = add_tongue_and_groove(
                    all_sections[i_left].solid,
                    all_sections[i_right].solid,
                    overlap=design.section_overlap,
                    tolerance=design.joint_tolerance,
                    nozzle_diameter=design.nozzle_diameter,
                )
                all_sections[i_left].solid = left_solid
                all_sections[i_right].solid = right_solid
            except Exception as exc:
                logger.warning(
                    "Joint creation failed for %s_%s sections %d-%d: %s",
                    _comp,
                    _side,
                    all_sections[i_left].section_num,
                    all_sections[i_right].section_num,
                    exc,
                )

    # 3. Build ZIP
    return build_zip(all_sections, design)
