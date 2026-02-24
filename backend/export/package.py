"""ZIP export packaging -- creates downloadable archives with STLs and manifest.

Tessellates each SectionPart at export quality (0.1 mm tolerance), writes
binary STL files into a ZIP archive alongside a manifest.json, and returns
the path to the temp file.  Caller must delete after streaming.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.models import AircraftDesign
from backend.export.section import SectionPart

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPORT_TMP_DIR: Path = Path(os.environ.get("CHENG_DATA_DIR", tempfile.gettempdir())) / "tmp"


# ---------------------------------------------------------------------------
# Public API
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

    # Create temp ZIP file
    zip_filename = f"cheng_{design.name.replace(' ', '_')}_{design.id[:8] if design.id else 'export'}.zip"
    zip_path = tmp_dir / zip_filename

    # Use a temporary file to avoid partial writes.
    # Explicitly close before opening with ZipFile to avoid PermissionError
    # on Windows where open file handles block re-opening (#88).
    tmp_file = tempfile.NamedTemporaryFile(
        dir=str(tmp_dir),
        suffix=".zip",
        delete=False,
    )
    tmp_path = Path(tmp_file.name)
    tmp_file.close()

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Tessellate and add each section as binary STL
        for section in sections:
            stl_bytes = tessellate_for_export(section.solid, tolerance=0.1)
            zf.writestr(section.filename, stl_bytes)

    # Rename to final path (atomic on same filesystem)
    try:
        tmp_path.rename(zip_path)
    except OSError:
        # Cross-device fallback: copy and delete
        import shutil
        shutil.move(str(tmp_path), str(zip_path))

    return zip_path


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
