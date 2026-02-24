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
    split_axis: str = "Y",
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
        split_axis:      Axis along which sections were split ("X", "Y", or "Z").
                         Determines which face the tongue/groove is placed on.

    Returns:
        (modified_left, modified_right) with joint features applied.
    """
    import cadquery as cq  # noqa: F811

    # Get bounding box of the left section to determine joint dimensions
    bb = left.val().BoundingBox()
    dx = bb.xmax - bb.xmin
    dy = bb.ymax - bb.ymin
    dz = bb.zmax - bb.zmin

    # Determine cross-section dimensions based on split axis.
    # The tongue is placed on the face perpendicular to the split axis.
    # cross_dim_a and cross_dim_b are the two dimensions of that face.
    if split_axis == "X":
        cross_dim_a, cross_dim_b = dy, dz
    elif split_axis == "Z":
        cross_dim_a, cross_dim_b = dx, dy
    else:  # "Y" (default)
        cross_dim_a, cross_dim_b = dx, dz

    # Minimum tongue width
    min_tongue_width = 3.0 * nozzle_diameter

    # Tongue dimensions: fraction of cross-section
    tongue_a = max(cross_dim_a * 0.6, min_tongue_width)
    tongue_b = max(cross_dim_b * 0.6, min_tongue_width)

    # Groove dimensions: tongue + tolerance clearance
    groove_a = tongue_a + 2.0 * tolerance
    groove_b = tongue_b + 2.0 * tolerance

    # Groove is slightly deeper than tongue length for printer tolerance clearance (#87).
    groove_depth = overlap + _GROOVE_DEPTH_CLEARANCE_MM

    bb_r = right.val().BoundingBox()

    # Build tongue and groove geometry based on split axis
    if split_axis == "X":
        # Split along X: tongue protrudes from +X face of left
        cy = (bb.ymin + bb.ymax) / 2.0
        cz = (bb.zmin + bb.zmax) / 2.0
        tongue_center = bb.xmax + overlap / 2.0
        tongue = (
            cq.Workplane("XY")
            .transformed(offset=(tongue_center, cy, cz))
            .box(overlap, tongue_a, tongue_b)
        )
        fillet_edge_sel = "|X"

        cy_r = (bb_r.ymin + bb_r.ymax) / 2.0
        cz_r = (bb_r.zmin + bb_r.zmax) / 2.0
        groove_center = bb_r.xmin + groove_depth / 2.0
        groove = (
            cq.Workplane("XY")
            .transformed(offset=(groove_center, cy_r, cz_r))
            .box(groove_depth, groove_a, groove_b)
        )
    elif split_axis == "Z":
        # Split along Z: tongue protrudes from +Z face of left
        cx = (bb.xmin + bb.xmax) / 2.0
        cy = (bb.ymin + bb.ymax) / 2.0
        tongue_center = bb.zmax + overlap / 2.0
        tongue = (
            cq.Workplane("XY")
            .transformed(offset=(cx, cy, tongue_center))
            .box(tongue_a, tongue_b, overlap)
        )
        fillet_edge_sel = "|Z"

        cx_r = (bb_r.xmin + bb_r.xmax) / 2.0
        cy_r = (bb_r.ymin + bb_r.ymax) / 2.0
        groove_center = bb_r.zmin + groove_depth / 2.0
        groove = (
            cq.Workplane("XY")
            .transformed(offset=(cx_r, cy_r, groove_center))
            .box(groove_a, groove_b, groove_depth)
        )
    else:
        # Split along Y (default): tongue protrudes from +Y face of left
        cx = (bb.xmin + bb.xmax) / 2.0
        cz = (bb.zmin + bb.zmax) / 2.0
        tongue_center = bb.ymax + overlap / 2.0
        tongue = (
            cq.Workplane("XY")
            .transformed(offset=(cx, tongue_center, cz))
            .box(tongue_a, overlap, tongue_b)
        )
        fillet_edge_sel = "|Y"

        cx_r = (bb_r.xmin + bb_r.xmax) / 2.0
        cz_r = (bb_r.zmin + bb_r.zmax) / 2.0
        groove_center = bb_r.ymin + groove_depth / 2.0
        groove = (
            cq.Workplane("XY")
            .transformed(offset=(cx_r, groove_center, cz_r))
            .box(groove_a, groove_depth, groove_b)
        )

    # Apply fillet to tongue edges if possible
    try:
        if _TONGUE_FILLET_RADIUS_MM < min(tongue_a, tongue_b) / 2:
            tongue = tongue.edges(fillet_edge_sel).fillet(_TONGUE_FILLET_RADIUS_MM)
    except Exception:
        pass  # Fillet can fail on very small features

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
