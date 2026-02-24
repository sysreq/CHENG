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
from backend.export.section import auto_section, create_section_parts
from backend.export.joints import add_tongue_and_groove
from backend.export.package import build_zip, EXPORT_TMP_DIR
from backend.models import AircraftDesign, ExportRequest

logger = logging.getLogger("cheng.export")

router = APIRouter(prefix="/api", tags=["export"])


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


def _export_blocking(design: AircraftDesign) -> Path:
    """Synchronous export pipeline — runs in thread pool.

    1. Assemble aircraft components
    2. Auto-section each component for print bed
    3. Add tongue-and-groove joints between adjacent sections
    4. Build ZIP with tessellated STLs + manifest
    """
    # 1. Assemble
    components = assemble_aircraft(design)

    # 2. Auto-section each component
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

        # 3. Add joints between adjacent sections
        for i in range(len(section_parts) - 1):
            try:
                left_solid, right_solid = add_tongue_and_groove(
                    section_parts[i].solid,
                    section_parts[i + 1].solid,
                    overlap=design.section_overlap,
                    tolerance=design.joint_tolerance,
                    nozzle_diameter=design.nozzle_diameter,
                )
                section_parts[i].solid = left_solid
                section_parts[i + 1].solid = right_solid
            except Exception as exc:
                logger.warning(
                    "Joint creation failed for %s sections %d-%d: %s",
                    comp_name, i, i + 1, exc,
                )

        all_sections.extend(section_parts)
        assembly_order += len(section_parts)

    # 4. Build ZIP
    return build_zip(all_sections, design)
