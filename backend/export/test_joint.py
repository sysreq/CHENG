"""Generate test joint pieces for print-fit verification.

Produces two small printable blocks (plug/tongue and socket/groove)
that exactly replicate the joint geometry used in production section joints.
This lets users verify their printer's tolerance before the full build.

Two-piece assembly for Tongue-and-Groove:
  - plug: 40mm wide x section_overlap deep x 40mm tall — tongue protrudes from +Y face
  - socket: 40mm wide x (section_overlap + 10mm buffer) deep x 40mm tall — groove in -Y face

The +10mm buffer on the socket block prevents the groove (which is section_overlap + 0.2mm deep)
from punching through the back wall of the socket.  The buffer provides a solid back face
so users can verify that the tongue does not bottom out prematurely.

The tongue/groove profile exactly matches production joints (same add_tongue_and_groove()
call), so if joints.py geometry changes, the test piece automatically reflects the change.
"""
from __future__ import annotations

import json
import logging
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

logger = logging.getLogger("cheng.test_joint")

# Test piece footprint — small enough to print in < 30 min
_TEST_PIECE_WIDTH_MM = 40.0   # X and Z dimensions of each block face

# Extra depth added to the socket block so the groove (overlap + 0.2mm clearance)
# does not punch through the back wall.  10mm provides a visible back face.
_SOCKET_BACK_WALL_MM = 10.0


def generate_test_joint_pieces(
    section_overlap: float,
    joint_tolerance: float,
    nozzle_diameter: float,
    joint_type: str = "Tongue-and-Groove",
) -> tuple[cq.Workplane, cq.Workplane]:
    """Generate plug (tongue) and socket (groove) test pieces.

    For Tongue-and-Groove:
      - Plug: 40 x section_overlap x 40 mm with tongue on the +Y face.
      - Socket: 40 x (section_overlap + 10mm) x 40 mm with groove in the -Y face.
        The extra 10mm ensures the groove does not punch through the back wall.

    For other joint types (Dowel-Pin, Flat-with-Alignment-Pins):
      - Returns two plain blocks with no joint geometry.
      - These joint types are not yet geometrically simulated; the blocks demonstrate
        the footprint only.  The manifest explains this limitation.

    Uses split_axis="Y" to match the most common production joint orientation.

    Args:
        section_overlap:  Tongue/groove length in mm (PR05, default 15).
        joint_tolerance:  Clearance per side in mm (PR11, default 0.15).
        nozzle_diameter:  FDM nozzle in mm (PR06, default 0.4).
        joint_type:       Joint type string (PR10, default "Tongue-and-Groove").

    Returns:
        (plug_solid, socket_solid) — two CadQuery Workplanes ready for STL export.
    """
    import cadquery as cq

    w = _TEST_PIECE_WIDTH_MM
    depth = section_overlap
    socket_depth = depth + _SOCKET_BACK_WALL_MM  # avoids groove punch-through

    if joint_type == "Tongue-and-Groove":
        return _generate_tongue_and_groove(
            width=w,
            plug_depth=depth,
            socket_depth=socket_depth,
            overlap=depth,
            tolerance=joint_tolerance,
            nozzle_diameter=nozzle_diameter,
        )
    else:
        # Non-simulated joint types: return plain blocks with same footprint
        # The manifest (built by build_test_joint_zip) explains the limitation.
        plug_block = (
            cq.Workplane("XY")
            .box(w, depth, w)
            .translate((0, depth / 2.0, 0))
        )
        socket_block = (
            cq.Workplane("XY")
            .box(w, socket_depth, w)
            .translate((0, depth + socket_depth / 2.0, 0))
        )
        return plug_block, socket_block


def _generate_tongue_and_groove(
    width: float,
    plug_depth: float,
    socket_depth: float,
    overlap: float,
    tolerance: float,
    nozzle_diameter: float,
) -> tuple[cq.Workplane, cq.Workplane]:
    """Create plug + socket using the production add_tongue_and_groove() function.

    Plug block:   Y = [0, plug_depth]
    Socket block: Y = [plug_depth, plug_depth + socket_depth]

    add_tongue_and_groove() with split_axis="Y":
      - Adds tongue protruding from plug's +Y face (at Y = plug_depth)
      - Cuts groove into socket's -Y face (at Y = plug_depth)

    The groove depth is (overlap + 0.2mm), which is fully contained within socket_depth
    (= overlap + 10mm), leaving a solid 9.8mm back wall.
    """
    import cadquery as cq
    from backend.export.joints import add_tongue_and_groove

    plug_block = (
        cq.Workplane("XY")
        .box(width, plug_depth, width)
        .translate((0, plug_depth / 2.0, 0))
    )

    socket_block = (
        cq.Workplane("XY")
        .box(width, socket_depth, width)
        .translate((0, plug_depth + socket_depth / 2.0, 0))
    )

    try:
        plug_with_joint, socket_with_joint = add_tongue_and_groove(
            plug_block,
            socket_block,
            overlap=overlap,
            tolerance=tolerance,
            nozzle_diameter=nozzle_diameter,
            split_axis="Y",
        )
    except Exception as exc:
        logger.warning(
            "add_tongue_and_groove failed for test joint: %s — returning plain blocks", exc
        )
        plug_with_joint = plug_block
        socket_with_joint = socket_block

    # Attempt text labels on the +Z (top) face — nice-to-have, skip on failure
    plug_labeled = _try_label_plug(plug_with_joint, tolerance)
    socket_labeled = _try_label_socket(socket_with_joint, overlap)

    return plug_labeled, socket_labeled


def _try_label_plug(solid: cq.Workplane, joint_tolerance: float) -> cq.Workplane:
    """Attempt to emboss tolerance value on the top (+Z) face.

    CadQuery's .text() method requires a font and can fail in some builds.
    Always returns a valid solid (falls back to unmodified solid on any error).
    """
    try:
        return (
            solid
            .faces(">Z")
            .workplane()
            .text(
                f"TOL {joint_tolerance:.2f}mm",
                fontsize=4.0,
                distance=-0.4,
                cut=True,
            )
        )
    except Exception:
        return solid


def _try_label_socket(solid: cq.Workplane, section_overlap: float) -> cq.Workplane:
    """Attempt to emboss overlap depth on the top (+Z) face.

    Falls back to unmodified solid on any error.
    """
    try:
        return (
            solid
            .faces(">Z")
            .workplane()
            .text(
                f"OVL {section_overlap:.0f}mm",
                fontsize=4.0,
                distance=-0.4,
                cut=True,
            )
        )
    except Exception:
        return solid


def build_test_joint_zip(
    section_overlap: float,
    joint_tolerance: float,
    nozzle_diameter: float,
    tmp_dir: Path,
    joint_type: str = "Tongue-and-Groove",
) -> Path:
    """Generate both test joint pieces and package them into a ZIP file.

    Tessellates plug and socket individually (export-quality tolerance 0.1mm),
    writes them as binary STL into a ZIP together with a manifest.json.
    Caller must delete the returned file after streaming.

    Args:
        section_overlap:  Tongue/groove depth in mm.
        joint_tolerance:  Clearance per side in mm.
        nozzle_diameter:  FDM nozzle diameter in mm.
        tmp_dir:          Directory to write the temp ZIP into.
        joint_type:       Joint type string (e.g. "Tongue-and-Groove").

    Returns:
        Path to the temp ZIP file.
    """
    from backend.geometry.tessellate import tessellate_for_export

    tmp_dir.mkdir(parents=True, exist_ok=True)

    plug_solid, socket_solid = generate_test_joint_pieces(
        section_overlap=section_overlap,
        joint_tolerance=joint_tolerance,
        nozzle_diameter=nozzle_diameter,
        joint_type=joint_type,
    )

    # Tessellate both pieces to binary STL bytes
    plug_stl = tessellate_for_export(plug_solid, tolerance=0.1)
    socket_stl = tessellate_for_export(socket_solid, tolerance=0.1)

    # Rough print-time estimate (mm³/s at 60mm/s × 0.2mm layer × 0.4mm nozzle)
    _PRINT_RATE_MM3_PER_S = 60.0 * 0.2 * 0.4
    socket_depth = section_overlap + _SOCKET_BACK_WALL_MM
    piece_volume_mm3 = _TEST_PIECE_WIDTH_MM * _TEST_PIECE_WIDTH_MM * (section_overlap + socket_depth)
    estimated_minutes = round(piece_volume_mm3 / _PRINT_RATE_MM3_PER_S / 60.0, 0)

    is_simulated = joint_type == "Tongue-and-Groove"
    instructions = (
        "Print both files. Plug has the tongue; Socket has the groove. "
        "They should slide together with light hand pressure. "
        "If too tight: increase joint_tolerance. If too loose: decrease it."
        if is_simulated else
        f"Joint type '{joint_type}' is not yet geometrically simulated. "
        "These blocks show the correct footprint. Tongue-and-Groove test pieces "
        "are always available for mechanical fit verification."
    )

    manifest = {
        "type": "test_joint",
        "joint_type": joint_type,
        "joint_simulated": is_simulated,
        "joint_tolerance_mm": joint_tolerance,
        "section_overlap_mm": section_overlap,
        "nozzle_diameter_mm": nozzle_diameter,
        "block_size_mm": [_TEST_PIECE_WIDTH_MM, section_overlap, _TEST_PIECE_WIDTH_MM],
        "files": ["test_joint_plug.stl", "test_joint_socket.stl"],
        "instructions": instructions,
        "estimated_print_minutes": estimated_minutes,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    # Write to a temp file then rename for atomicity
    tmp_file = tempfile.NamedTemporaryFile(
        dir=str(tmp_dir),
        suffix=".zip",
        delete=False,
    )
    tmp_path = Path(tmp_file.name)
    tmp_file.close()

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_joint_plug.stl", plug_stl)
        zf.writestr("test_joint_socket.stl", socket_stl)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    # #260: use a per-request unique filename to prevent concurrent-export collisions
    unique_suffix = uuid.uuid4().hex[:8]
    final_path = tmp_dir / f"cheng_test_joint_{unique_suffix}.zip"
    try:
        tmp_path.rename(final_path)
    except OSError:
        import shutil
        shutil.move(str(tmp_path), str(final_path))

    return final_path
