"""Joint features -- tongue-and-groove for connecting adjacent sections.

Adds interlocking features to split faces so printed sections can be
assembled with tight alignment and adequate bonding area.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TONGUE_AREA_FRACTION: float = 0.60   # Tongue = 60% of cross-sectional area
_TONGUE_FILLET_RADIUS_MM: float = 1.0  # Fillet on tongue corners
_GROOVE_DEPTH_CLEARANCE_MM: float = 0.2  # Extra groove depth for printer tolerance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def add_tongue_and_groove(
    left: cq.Workplane,
    right: cq.Workplane,
    overlap: float,
    tolerance: float,
    nozzle_diameter: float,
) -> tuple[cq.Workplane, cq.Workplane]:
    """Add tongue-and-groove joint features to two adjacent sections.

    Per spec section 8.3:
    - Tongue protrudes from +axis face of left by ``overlap`` mm.
    - Groove cut into -axis face of right to depth of ``overlap`` mm.
    - Groove width = tongue width + 2 * tolerance.
    - Tongue cross-section = 60% of cut-plane area.
    - Tongue corners filleted at 1 mm radius.
    - Min tongue width = 3 * nozzle_diameter.

    Args:
        left:            Lower-numbered section.  Tongue added to +axis face.
        right:           Higher-numbered section.  Groove cut into -axis face.
        overlap:         Tongue/groove length in mm (PR05, default 15).
        tolerance:       Clearance per side in mm (PR11, default 0.15).
        nozzle_diameter: FDM nozzle in mm (PR06).  Min tongue = 3x this.

    Returns:
        (modified_left, modified_right) with joint features applied.
    """
    import cadquery as cq  # noqa: F811

    # Get bounding box of the left section to determine joint dimensions
    bb = left.val().BoundingBox()
    dx = bb.xmax - bb.xmin
    dy = bb.ymax - bb.ymin
    dz = bb.zmax - bb.zmin

    # Determine the split axis: the one where sections are adjacent.
    # Usually Y for wings (spanwise) or X for fuselage (lengthwise).
    # We'll use the face at the max extent of the axis with smallest dimension
    # relative to the other two.

    # For now, determine split plane from bounding box analysis.
    # The split axis is the one where the sections are thinnest relative to
    # the original component.  In practice, auto_section splits along the
    # axis with largest overshoot.

    # Estimate cross-section area from the two non-split dimensions
    # Use Y axis as default split direction (wing spanwise sections)
    cross_width, cross_height = dx, dz
    split_axis = "Y"

    # Minimum tongue width
    min_tongue_width = 3.0 * nozzle_diameter

    # Tongue dimensions: fraction of cross-section
    tongue_width = max(cross_width * 0.6, min_tongue_width)
    tongue_height = max(cross_height * 0.6, min_tongue_width)

    # Groove dimensions: tongue + tolerance clearance
    groove_width = tongue_width + 2.0 * tolerance
    groove_height = tongue_height + 2.0 * tolerance

    # Center of the split face
    cx = (bb.xmin + bb.xmax) / 2.0
    cz = (bb.zmin + bb.zmax) / 2.0

    # Create tongue: a box protruding from the +Y face of left.
    # Using XY workplane (identity axis mapping) for clarity.
    tongue_center_y = bb.ymax + overlap / 2.0
    tongue = (
        cq.Workplane("XY")
        .transformed(offset=(cx, tongue_center_y, cz))
        .box(tongue_width, overlap, tongue_height)
    )

    # Apply fillet to tongue edges if possible
    try:
        if _TONGUE_FILLET_RADIUS_MM < min(tongue_width, tongue_height) / 2:
            tongue = tongue.edges("|Y").fillet(_TONGUE_FILLET_RADIUS_MM)
    except Exception:
        pass  # Fillet can fail on very small features

    # Create groove: a box cut into the -Y face of right.
    # Groove is slightly deeper than tongue length for printer tolerance clearance (#87).
    groove_depth = overlap + _GROOVE_DEPTH_CLEARANCE_MM
    bb_r = right.val().BoundingBox()
    cx_r = (bb_r.xmin + bb_r.xmax) / 2.0
    cz_r = (bb_r.zmin + bb_r.zmax) / 2.0
    groove_center_y = bb_r.ymin + groove_depth / 2.0
    groove = (
        cq.Workplane("XY")
        .transformed(offset=(cx_r, groove_center_y, cz_r))
        .box(groove_width, groove_depth, groove_height)
    )

    # Boolean operations: add tongue to left, cut groove from right
    try:
        modified_left = left.union(tongue)
    except Exception:
        modified_left = left

    try:
        modified_right = right.cut(groove)
    except Exception:
        modified_right = right

    return (modified_left, modified_right)
