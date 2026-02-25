"""POST /api/export -- multi-format export as streaming ZIP.

Generates geometry, auto-sections for print bed, adds joints,
packages as ZIP with manifest, and streams to client.
Temp file on /data/tmp is deleted after streaming (spec section 8.5).
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import Path

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.geometry.engine import assemble_aircraft, _cadquery_limiter
from backend.export.section import auto_section, auto_section_with_axis, create_section_parts, SectionPart
from backend.export.joints import add_tongue_and_groove
from backend.export.package import build_zip, build_step_zip, build_dxf_zip, build_svg_zip, EXPORT_TMP_DIR
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

        # Use auto_section_with_axis to get split axis info (#163)
        pieces_with_axis = auto_section_with_axis(
            solid,
            bed_x=design.print_bed_x,
            bed_y=design.print_bed_y,
            bed_z=design.print_bed_z,
        )
        pieces = [p[0] for p in pieces_with_axis]
        split_axes = [p[1] for p in pieces_with_axis]

        section_parts = create_section_parts(
            comp_category,
            side,
            pieces,
            start_assembly_order=assembly_order,
            split_axes=split_axes,
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
async def export_design(request: ExportRequest) -> FileResponse:
    """Generate export files and stream as ZIP.

    Pipeline varies by format:
    - stl: assemble -> auto-section -> joints -> tessellate -> ZIP -> stream
    - step: assemble -> STEP export -> ZIP -> stream (no sectioning)
    - dxf: assemble -> cross-sections -> DXF -> ZIP -> stream
    - svg: assemble -> orthographic projections -> SVG -> ZIP -> stream
    """
    design = request.design
    export_format = request.format
    export_test_joint = getattr(request, "export_test_joint", False)

    # Ensure tmp dir exists (may not exist outside Docker)
    EXPORT_TMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Run the blocking export pipeline in a thread with the CadQuery limiter
        zip_path = await anyio.to_thread.run_sync(
            lambda: _export_blocking(design, export_format, export_test_joint),
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


def _export_blocking(design: AircraftDesign, export_format: str = "stl", export_test_joint: bool = False) -> Path:
    """Synchronous export pipeline -- runs in thread pool.

    Routes to the appropriate export handler based on format.
    """
    if export_test_joint:
        return _export_test_joint_blocking(design)

    components = _get_or_assemble(design)

    if export_format == "step":
        return build_step_zip(components, design)
    elif export_format == "dxf":
        return build_dxf_zip(components, design)
    elif export_format == "svg":
        return build_svg_zip(components, design)
    else:
        return _export_stl_blocking(design)


def _export_test_joint_blocking(design: AircraftDesign) -> Path:
    """Export a simple 20x20x10 block split in half with a tongue-and-groove joint."""
    import cadquery as cq

    # 1. Create a 20x20x10 block and split it along Y axis (lengthwise)
    # The left block will be Y < 0, right block will be Y > 0
    # Left block (Y from -10 to 0)
    left_solid = (
        cq.Workplane("XY")
        .transformed(offset=(0, -5, 5))
        .box(20, 10, 10)
    )
    # Right block (Y from 0 to 10)
    right_solid = (
        cq.Workplane("XY")
        .transformed(offset=(0, 5, 5))
        .box(20, 10, 10)
    )

    # 2. Add tongue and groove joint
    left_solid, right_solid = add_tongue_and_groove(
        left_solid,
        right_solid,
        overlap=design.section_overlap,
        tolerance=design.joint_tolerance,
        nozzle_diameter=design.nozzle_diameter,
        split_axis="Y",
    )

    # 3. Create SectionParts
    sp1 = SectionPart(
        solid=left_solid,
        filename="test_joint_left.stl",
        component="test_joint",
        side="left",
        section_num=1,
        total_sections=2,
        dimensions_mm=(20, 10, 10),
        print_orientation="flat",
        assembly_order=1,
        split_axis="Y",
    )
    sp2 = SectionPart(
        solid=right_solid,
        filename="test_joint_right.stl",
        component="test_joint",
        side="right",
        section_num=2,
        total_sections=2,
        dimensions_mm=(20, 10, 10),
        print_orientation="flat",
        assembly_order=2,
        split_axis="Y",
    )
    sp1.recompute_dimensions()
    sp2.recompute_dimensions()

    # 4. ZIP and return
    return build_zip([sp1, sp2], design)


def _export_stl_blocking(design: AircraftDesign) -> Path:
    """STL export pipeline: shared section -> joints -> recompute dims -> ZIP.

    1. Auto-section via shared _generate_sections (with split axis, #163)
    2. Add tongue-and-groove joints between adjacent sections
    3. Recompute dimensions after joints (#166)
    4. Build ZIP with tessellated STLs + manifest
    """
    all_sections = _generate_sections(design)

    # Group sections by (component, side) to find adjacent pairs for joints
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for idx, sp in enumerate(all_sections):
        groups[(sp.component, sp.side)].append(idx)

    for (_comp, _side), indices in groups.items():
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
                    split_axis=all_sections[i_left].split_axis,
                )
                all_sections[i_left].solid = left_solid
                all_sections[i_right].solid = right_solid
                # Recompute dimensions after joint features (#166)
                all_sections[i_left].recompute_dimensions()
                all_sections[i_right].recompute_dimensions()
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
