"""POST /api/export — STL export as streaming ZIP.

Generates geometry, auto-sections for print bed, adds joints,
packages as ZIP with manifest, and streams to client.
Temp file on /data/tmp is deleted after streaming (spec §8.5).
"""

from __future__ import annotations

import logging
from pathlib import Path

import anyio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.geometry.engine import assemble_aircraft, _cadquery_limiter
from backend.export.section import auto_section, auto_section_with_axis, create_section_parts
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

    # Ensure tmp dir exists (may not exist outside Docker)
    EXPORT_TMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Run the blocking export pipeline in a thread with the CadQuery limiter
        zip_path = await anyio.to_thread.run_sync(
            lambda: _export_blocking(design, export_format),
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
    tessellation and ZIP packaging.  Returns part metadata and bed-fit info.
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
        raise HTTPException(status_code=500, detail=f"Export preview failed: {exc}") from exc

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


def _preview_blocking(design: AircraftDesign) -> list[ExportPreviewPart]:
    """Synchronous preview pipeline — assemble + section only (no joints/ZIP)."""
    components = assemble_aircraft(design)

    all_parts: list[ExportPreviewPart] = []
    assembly_order = 1

    for comp_name, solid in components.items():
        if "left" in comp_name:
            side = "left"
        elif "right" in comp_name:
            side = "right"
        else:
            side = "center"

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

        for sp in section_parts:
            dx, dy, dz = sp.dimensions_mm
            fits = (
                dx <= design.print_bed_x
                and dy <= design.print_bed_y
                and dz <= design.print_bed_z
            )
            all_parts.append(ExportPreviewPart(
                filename=sp.filename,
                component=sp.component,
                side=sp.side,
                section_num=sp.section_num,
                total_sections=sp.total_sections,
                dimensions_mm=sp.dimensions_mm,
                print_orientation=sp.print_orientation,
                assembly_order=sp.assembly_order,
                fits_bed=fits,
            ))

        assembly_order += len(section_parts)

    return all_parts


def _export_blocking(design: AircraftDesign, export_format: str = "stl") -> Path:
    """Synchronous export pipeline -- runs in thread pool.

    Routes to the appropriate export handler based on format.
    """
    # 1. Assemble
    components = assemble_aircraft(design)

    if export_format == "step":
        return build_step_zip(components, design)
    elif export_format == "dxf":
        return build_dxf_zip(components, design)
    elif export_format == "svg":
        return build_svg_zip(components, design)
    else:
        return _export_stl_blocking(design, components)


def _export_stl_blocking(design: AircraftDesign, components: dict) -> Path:
    """STL export pipeline: auto-section -> joints -> tessellate -> ZIP.

    1. Auto-section each component for print bed (with split axis tracking, #163)
    2. Add tongue-and-groove joints between adjacent sections
    3. Recompute dimensions after joints (#166)
    4. Build ZIP with tessellated STLs + manifest
    """
    all_sections = []
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
        comp_category = comp_name.split("_")[0]  # "wing", "fuselage", "h", "v"
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

        # Add joints between adjacent sections
        for i in range(len(section_parts) - 1):
            try:
                left_solid, right_solid = add_tongue_and_groove(
                    section_parts[i].solid,
                    section_parts[i + 1].solid,
                    overlap=design.section_overlap,
                    tolerance=design.joint_tolerance,
                    nozzle_diameter=design.nozzle_diameter,
                    split_axis=section_parts[i].split_axis,
                )
                section_parts[i].solid = left_solid
                section_parts[i + 1].solid = right_solid
                # Recompute dimensions after joint features (#166)
                section_parts[i].recompute_dimensions()
                section_parts[i + 1].recompute_dimensions()
            except Exception as exc:
                logger.warning(
                    "Joint creation failed for %s sections %d-%d: %s",
                    comp_name, i, i + 1, exc,
                )

        all_sections.extend(section_parts)
        assembly_order += len(section_parts)

    # Build ZIP
    return build_zip(all_sections, design)
