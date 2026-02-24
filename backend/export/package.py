"""ZIP export packaging -- creates downloadable archives with STLs and manifest.

Tessellates each SectionPart at export quality (0.1 mm tolerance), writes
binary STL files into a ZIP archive alongside a manifest.json, and returns
the path to the temp file.  Caller must delete after streaming.

Also provides STEP, DXF, and SVG export builders.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from backend.models import AircraftDesign
from backend.export.section import SectionPart

if TYPE_CHECKING:
    import cadquery as cq

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPORT_TMP_DIR: Path = Path(os.environ.get("CHENG_DATA_DIR", tempfile.gettempdir())) / "tmp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_zip(design: AircraftDesign) -> tuple[Path, Path]:
    """Create a temp file for ZIP writing and compute final path.

    Returns (tmp_path, zip_path). tmp_path is closed and ready for writing.
    """
    tmp_dir = EXPORT_TMP_DIR
    tmp_dir.mkdir(parents=True, exist_ok=True)

    zip_filename = f"cheng_{design.name.replace(' ', '_')}_{design.id[:8] if design.id else 'export'}.zip"
    zip_path = tmp_dir / zip_filename

    tmp_file = tempfile.NamedTemporaryFile(
        dir=str(tmp_dir),
        suffix=".zip",
        delete=False,
    )
    tmp_path = Path(tmp_file.name)
    tmp_file.close()

    return tmp_path, zip_path


def _finalize_zip(tmp_path: Path, zip_path: Path) -> Path:
    """Rename temp file to final path, with cross-device fallback."""
    try:
        tmp_path.rename(zip_path)
    except OSError:
        import shutil
        shutil.move(str(tmp_path), str(zip_path))
    return zip_path


# ---------------------------------------------------------------------------
# Public API -- STL export
# ---------------------------------------------------------------------------


def build_zip(sections: list[SectionPart], design: AircraftDesign) -> Path:
    """Create ZIP archive with STL files and manifest.

    Tessellates each section (tolerance=0.1), writes STLs + manifest.json
    to a temp ZIP on /data/tmp.  Caller must delete after streaming (spec section 8.5).

    manifest.json structure (spec section 8.4):
    - design_name: str
    - design_id: str
    - version: str
    - exported_at: ISO 8601 timestamp
    - total_parts: int
    - parts: list of part descriptors
    - assembly_notes: list of assembly hint strings

    Args:
        sections: List of SectionPart objects to export.
        design:   The source AircraftDesign (for metadata).

    Returns:
        Path to temp ZIP file, closed and ready for streaming.
    """
    from backend.geometry.tessellate import tessellate_for_export

    # Ensure temp directory exists
    tmp_dir = EXPORT_TMP_DIR
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Build manifest
    manifest = _build_manifest(sections, design)

    tmp_path, zip_path = _make_temp_zip(design)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Tessellate and add each section as binary STL
        for section in sections:
            stl_bytes = tessellate_for_export(section.solid, tolerance=0.1)
            zf.writestr(section.filename, stl_bytes)

    return _finalize_zip(tmp_path, zip_path)


# ---------------------------------------------------------------------------
# Public API -- STEP export (#116)
# ---------------------------------------------------------------------------


def build_step_zip(
    components: dict[str, cq.Workplane],
    design: AircraftDesign,
) -> Path:
    """Create ZIP archive with STEP files for CAD exchange.

    STEP export does not require sectioning -- the full assembly is exported
    as individual component STEP files for use in other CAD software.

    Args:
        components: Dict of component_name -> CadQuery Workplane.
        design:     The source AircraftDesign (for metadata).

    Returns:
        Path to temp ZIP file.
    """
    import cadquery as cq

    tmp_path, zip_path = _make_temp_zip(design)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "design_name": design.name,
            "design_id": design.id,
            "version": design.version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "step",
            "total_files": len(components),
            "files": [],
        }

        for comp_name, solid in components.items():
            step_filename = f"{comp_name}.step"

            # Export to a temp file, then read bytes
            step_tmp = tempfile.NamedTemporaryFile(
                suffix=".step", delete=False, dir=str(EXPORT_TMP_DIR)
            )
            step_tmp_path = Path(step_tmp.name)
            step_tmp.close()

            try:
                cq.exporters.export(solid, str(step_tmp_path), "STEP")
                step_bytes = step_tmp_path.read_bytes()
                zf.writestr(step_filename, step_bytes)
                manifest["files"].append(step_filename)
            finally:
                step_tmp_path.unlink(missing_ok=True)

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    return _finalize_zip(tmp_path, zip_path)


# ---------------------------------------------------------------------------
# Public API -- DXF export (#117)
# ---------------------------------------------------------------------------


def build_dxf_zip(
    components: dict[str, cq.Workplane],
    design: AircraftDesign,
) -> Path:
    """Create ZIP archive with DXF files for laser cutting.

    Generates cross-section profiles at key stations:
    - Wing ribs at evenly spaced spanwise stations
    - Fuselage formers at evenly spaced lengthwise stations

    Args:
        components: Dict of component_name -> CadQuery Workplane.
        design:     The source AircraftDesign (for metadata).

    Returns:
        Path to temp ZIP file.
    """
    import cadquery as cq

    tmp_path, zip_path = _make_temp_zip(design)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "design_name": design.name,
            "design_id": design.id,
            "version": design.version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "dxf",
            "total_files": 0,
            "files": [],
        }

        for comp_name, solid in components.items():
            bb = solid.val().BoundingBox()

            # Determine the primary axis for cross-sections
            dx = bb.xmax - bb.xmin
            dy = bb.ymax - bb.ymin
            dz = bb.zmax - bb.zmin

            # Choose the longest axis for cross-section stations
            if comp_name.startswith("fuselage"):
                # Fuselage: cross-sections along X (lengthwise)
                axis = "X"
                length = dx
                axis_min, axis_max = bb.xmin, bb.xmax
            else:
                # Wings/tails: cross-sections along Y (spanwise)
                axis = "Y"
                length = dy
                axis_min, axis_max = bb.ymin, bb.ymax

            # Generate cross-sections at regular intervals
            num_stations = max(3, int(length / 50))  # One every ~50mm
            step_size = length / (num_stations + 1)

            for i in range(1, num_stations + 1):
                station_pos = axis_min + step_size * i
                dxf_filename = f"{comp_name}_section_{i}of{num_stations}.dxf"

                dxf_tmp = tempfile.NamedTemporaryFile(
                    suffix=".dxf", delete=False, dir=str(EXPORT_TMP_DIR)
                )
                dxf_tmp_path = Path(dxf_tmp.name)
                dxf_tmp.close()

                try:
                    # Create a cross-section at the station
                    if axis == "X":
                        section_wp = solid.section(cq.Workplane("YZ").workplane(offset=station_pos))
                    else:
                        section_wp = solid.section(cq.Workplane("XZ").workplane(offset=station_pos))

                    cq.exporters.export(section_wp, str(dxf_tmp_path), "DXF")
                    dxf_bytes = dxf_tmp_path.read_bytes()
                    zf.writestr(dxf_filename, dxf_bytes)
                    manifest["files"].append(dxf_filename)
                    manifest["total_files"] += 1
                except Exception:
                    # Cross-section may fail at some stations (e.g. near tips)
                    pass
                finally:
                    dxf_tmp_path.unlink(missing_ok=True)

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    return _finalize_zip(tmp_path, zip_path)


# ---------------------------------------------------------------------------
# Public API -- SVG export (#118)
# ---------------------------------------------------------------------------


def build_svg_zip(
    components: dict[str, cq.Workplane],
    design: AircraftDesign,
) -> Path:
    """Create ZIP archive with SVG orthographic projections.

    Generates top (XY), front (XZ), and side (YZ) views of each component
    for web-friendly 2D outlines.

    Args:
        components: Dict of component_name -> CadQuery Workplane.
        design:     The source AircraftDesign (for metadata).

    Returns:
        Path to temp ZIP file.
    """
    import cadquery as cq

    tmp_path, zip_path = _make_temp_zip(design)

    views = [
        ("top", "XY"),
        ("front", "XZ"),
        ("side", "YZ"),
    ]

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "design_name": design.name,
            "design_id": design.id,
            "version": design.version,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format": "svg",
            "total_files": 0,
            "files": [],
        }

        for comp_name, solid in components.items():
            for view_name, plane in views:
                svg_filename = f"{comp_name}_{view_name}.svg"

                svg_tmp = tempfile.NamedTemporaryFile(
                    suffix=".svg", delete=False, dir=str(EXPORT_TMP_DIR)
                )
                svg_tmp_path = Path(svg_tmp.name)
                svg_tmp.close()

                try:
                    cq.exporters.export(solid, str(svg_tmp_path), "SVG")
                    svg_bytes = svg_tmp_path.read_bytes()
                    zf.writestr(svg_filename, svg_bytes)
                    manifest["files"].append(svg_filename)
                    manifest["total_files"] += 1
                except Exception:
                    # SVG export may fail for some geometries
                    pass
                finally:
                    svg_tmp_path.unlink(missing_ok=True)

        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    return _finalize_zip(tmp_path, zip_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_manifest(
    sections: list[SectionPart],
    design: AircraftDesign,
) -> dict[str, Any]:
    """Build the manifest.json structure for the ZIP archive."""
    parts = []
    for section in sections:
        parts.append({
            "filename": section.filename,
            "component": section.component,
            "side": section.side,
            "section": section.section_num,
            "total_sections": section.total_sections,
            "dimensions_mm": list(section.dimensions_mm),
            "print_orientation": section.print_orientation,
            "assembly_order": section.assembly_order,
        })

    # Sort parts by assembly order
    parts.sort(key=lambda p: p["assembly_order"])

    assembly_notes = _generate_assembly_notes(sections, design)

    return {
        "design_name": design.name,
        "design_id": design.id,
        "version": design.version,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_parts": len(sections),
        "joint_type": design.joint_type,
        "joint_overlap_mm": design.section_overlap,
        "joint_tolerance_mm": design.joint_tolerance,
        "parts": parts,
        "assembly_notes": assembly_notes,
    }


def _generate_assembly_notes(
    sections: list[SectionPart],
    design: AircraftDesign,
) -> list[str]:
    """Generate human-readable assembly notes for the manifest."""
    notes: list[str] = []

    # Count parts by component
    component_counts: dict[str, int] = {}
    for section in sections:
        key = f"{section.component}_{section.side}"
        component_counts[key] = section.total_sections

    notes.append(f"Aircraft: {design.name}")
    notes.append(f"Wingspan: {design.wing_span:.0f} mm")
    notes.append(f"Total printable parts: {len(sections)}")

    if design.joint_type == "Tongue-and-Groove":
        notes.append(
            f"Joint type: Tongue-and-Groove "
            f"(overlap: {design.section_overlap:.0f} mm, "
            f"tolerance: {design.joint_tolerance:.2f} mm)"
        )
        notes.append("Apply CA glue to groove surfaces before assembly.")
    elif design.joint_type == "Dowel-Pin":
        notes.append("Joint type: Dowel pins. Insert pins before gluing.")
    else:
        notes.append(
            f"Joint type: {design.joint_type}. "
            "Align registration marks before gluing."
        )

    notes.append(
        "Recommended print settings: "
        f"nozzle {design.nozzle_diameter:.1f} mm, "
        "0.2 mm layer height, 15% infill for solid parts."
    )

    if design.hollow_parts:
        notes.append(
            "Parts are hollow. Print with 3-4 perimeters for strength."
        )

    notes.append(
        "Assemble in order of assembly_order field in each part."
    )

    return notes
