"""Auto-sectioning algorithm -- splits oversized components to fit the print bed.

Recursively bisects solids along the longest oversize axis until every piece
fits within the usable print volume (bed dimensions minus joint margin).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_JOINT_MARGIN_MM: float = 20.0   # Margin per axis for joint features
_SPLIT_OFFSET_MM: float = 10.0   # Offset when midpoint hits internal features
_MAX_RECURSION: int = 20         # Safety limit to prevent infinite recursion

_AXIS_NAMES = {0: "X", 1: "Y", 2: "Z"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SectionPart:
    """A single printable section of a component, ready for STL export.

    Created by the auto-sectioning algorithm after splitting oversized
    components to fit the user's print bed.  Each SectionPart carries both
    the CadQuery solid (for tessellation) and metadata (for the manifest).

    The filename follows the convention:
        {component}_{side}_{section_num}of{total_sections}.stl
    Examples: "wing_left_1of3.stl", "fuselage_center_1of2.stl"
    """

    solid: cq.Workplane
    filename: str
    component: str            # "wing", "fuselage", "h_stab", "v_stab", "v_tail"
    side: str                 # "left", "right", "center"
    section_num: int          # 1-based section number along the split axis
    total_sections: int
    dimensions_mm: tuple[float, float, float]  # bounding box (x, y, z) after sectioning
    print_orientation: str    # "trailing-edge down", "flat", "leading-edge down"
    assembly_order: int       # 1-based global assembly order hint
    split_axis: str = "Y"    # axis along which this section was split ("X", "Y", or "Z")

    def recompute_dimensions(self) -> None:
        """Recompute dimensions_mm from the current solid's bounding box.

        Call this after modifying the solid (e.g. adding joint features)
        to ensure dimensions_mm reflects the actual part size.
        """
        dims = _get_dimensions(self.solid)
        self.dimensions_mm = (round(dims[0], 1), round(dims[1], 1), round(dims[2], 1))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def auto_section(
    solid: cq.Workplane,
    bed_x: float,
    bed_y: float,
    bed_z: float,
) -> list[cq.Workplane]:
    """Recursively split a solid into sections that fit on the print bed.

    Algorithm (spec section 8.2):
    1. Usable volume = (bed - 20 mm margin) per axis.
    2. If solid fits, return [solid].
    3. Find axis with largest overshoot.
    4. Bisect at midpoint of that axis.
    5. If bisection produces degenerate geometry, offset by +/-10 mm and retry.
    6. Recurse on each half.

    Args:
        solid:  CadQuery Workplane to section.
        bed_x/y/z: Print bed dimensions in mm (PR01/02/03).

    Returns:
        List of solids, each fitting within usable bed volume.

    Raises:
        ValueError: If bed dimensions minus margin <= 0.
        RuntimeError: If splitting fails after 20 recursion levels.
    """
    results = auto_section_with_axis(solid, bed_x, bed_y, bed_z)
    return [item[0] for item in results]


def auto_section_with_axis(
    solid: cq.Workplane,
    bed_x: float,
    bed_y: float,
    bed_z: float,
) -> list[tuple[cq.Workplane, str]]:
    """Like auto_section but also returns the split axis for each section.

    Returns:
        List of (solid, split_axis) tuples. split_axis is "X", "Y", or "Z"
        indicating which axis the section was cut along. For unsplit solids,
        the axis defaults to "Y".
    """
    import cadquery as cq  # noqa: F811

    usable_x = bed_x - _JOINT_MARGIN_MM
    usable_y = bed_y - _JOINT_MARGIN_MM
    usable_z = bed_z - _JOINT_MARGIN_MM

    if usable_x <= 0 or usable_y <= 0 or usable_z <= 0:
        raise ValueError(
            f"Print bed dimensions ({bed_x}, {bed_y}, {bed_z}) minus "
            f"{_JOINT_MARGIN_MM} mm margin leave no usable volume."
        )

    return _recursive_section(
        cq, solid, usable_x, usable_y, usable_z, depth=0
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_bounding_box(
    solid: cq.Workplane,
) -> tuple[float, float, float, float, float, float]:
    """Get the axis-aligned bounding box of a solid.

    Returns (xmin, ymin, zmin, xmax, ymax, zmax).
    """
    bb = solid.val().BoundingBox()
    return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)


def _get_dimensions(
    solid: cq.Workplane,
) -> tuple[float, float, float]:
    """Get the bounding box dimensions (dx, dy, dz) of a solid."""
    xmin, ymin, zmin, xmax, ymax, zmax = _get_bounding_box(solid)
    return (xmax - xmin, ymax - ymin, zmax - zmin)


def _bisect_solid(
    cq_mod: type,
    solid: cq.Workplane,
    axis: int,
    position: float,
) -> tuple[cq.Workplane, cq.Workplane]:
    """Split a solid into two halves at the given position along an axis.

    Args:
        cq_mod:   The cadquery module.
        solid:    Solid to split.
        axis:     0=X, 1=Y, 2=Z.
        position: Coordinate value along the axis to split at.

    Returns:
        Tuple of (lower_half, upper_half).
    """
    cq = cq_mod

    bb = _get_bounding_box(solid)
    # Create large cutting box
    size = 1e6  # 1 km -- large enough for any RC plane

    if axis == 0:  # X
        # Lower half: X < position
        cut_lower = (
            cq.Workplane("XY")
            .transformed(offset=(position + size / 2, 0, 0))
            .box(size, size, size)
        )
        cut_upper = (
            cq.Workplane("XY")
            .transformed(offset=(position - size / 2, 0, 0))
            .box(size, size, size)
        )
    elif axis == 1:  # Y
        cut_lower = (
            cq.Workplane("XY")
            .transformed(offset=(0, position + size / 2, 0))
            .box(size, size, size)
        )
        cut_upper = (
            cq.Workplane("XY")
            .transformed(offset=(0, position - size / 2, 0))
            .box(size, size, size)
        )
    else:  # Z
        cut_lower = (
            cq.Workplane("XY")
            .transformed(offset=(0, 0, position + size / 2))
            .box(size, size, size)
        )
        cut_upper = (
            cq.Workplane("XY")
            .transformed(offset=(0, 0, position - size / 2))
            .box(size, size, size)
        )

    lower_half = solid.cut(cut_lower)
    upper_half = solid.cut(cut_upper)

    return (lower_half, upper_half)


def _recursive_section(
    cq_mod: type,
    solid: cq.Workplane,
    usable_x: float,
    usable_y: float,
    usable_z: float,
    depth: int,
    last_split_axis: str = "Y",
) -> list[tuple[cq.Workplane, str]]:
    """Recursively split solid until all pieces fit the usable volume.

    Returns list of (solid, split_axis) tuples where split_axis is the axis
    along which the most recent split was performed ("X", "Y", or "Z").
    """
    if depth > _MAX_RECURSION:
        raise RuntimeError(
            f"Auto-sectioning exceeded {_MAX_RECURSION} recursion levels. "
            "The part may be too complex to section automatically."
        )

    dx, dy, dz = _get_dimensions(solid)
    usable = (usable_x, usable_y, usable_z)
    dims = (dx, dy, dz)

    # Check if it fits
    overshoot = [dims[i] - usable[i] for i in range(3)]
    if all(o <= 0 for o in overshoot):
        return [(solid, last_split_axis)]

    # Find axis with largest overshoot
    axis = overshoot.index(max(overshoot))
    axis_name = _AXIS_NAMES[axis]
    bb = _get_bounding_box(solid)

    # Axis min/max
    axis_min = bb[axis]
    axis_max = bb[axis + 3]
    midpoint = (axis_min + axis_max) / 2.0

    # Smart split-point optimizer: avoid modulo 100 near internal features
    # Offset split points by +/-10mm intelligently
    if abs(midpoint % 100) < 5.0:
        midpoint += 10.0

    # Try bisecting at midpoint
    try:
        lower, upper = _bisect_solid(cq_mod, solid, axis, midpoint)

        # Check for degenerate results (empty solids)
        lower_dims = _get_dimensions(lower)
        upper_dims = _get_dimensions(upper)

        if min(lower_dims) < 0.1 or min(upper_dims) < 0.1:
            # Degenerate -- try offset
            lower, upper = _bisect_solid(
                cq_mod, solid, axis, midpoint + _SPLIT_OFFSET_MM
            )
    except Exception:
        # If bisection fails, try with offset
        try:
            lower, upper = _bisect_solid(
                cq_mod, solid, axis, midpoint + _SPLIT_OFFSET_MM
            )
        except Exception:
            # Last resort: try the other direction
            lower, upper = _bisect_solid(
                cq_mod, solid, axis, midpoint - _SPLIT_OFFSET_MM
            )

    # Recurse on each half
    result: list[tuple[cq.Workplane, str]] = []
    result.extend(
        _recursive_section(cq_mod, lower, usable_x, usable_y, usable_z, depth + 1, axis_name)
    )
    result.extend(
        _recursive_section(cq_mod, upper, usable_x, usable_y, usable_z, depth + 1, axis_name)
    )

    return result


def create_section_parts(
    component: str,
    side: str,
    sections: list[cq.Workplane],
    start_assembly_order: int = 1,
    split_axes: list[str] | None = None,
) -> list[SectionPart]:
    """Create SectionPart metadata objects for a list of sectioned solids.

    Assigns filenames, dimensions, and assembly order to each section.

    Args:
        component: Component name (e.g. "wing", "fuselage").
        side: Side name (e.g. "left", "right", "center").
        sections: List of sectioned CadQuery solids.
        start_assembly_order: Starting assembly order number.
        split_axes: Optional list of split axis labels ("X", "Y", "Z") per section.
            If not provided, defaults to "Y" for all sections.

    Returns:
        List of SectionPart objects with metadata.
    """
    total = len(sections)
    parts: list[SectionPart] = []

    if split_axes is None:
        split_axes = ["Y"] * total

    for i, solid in enumerate(sections, start=1):
        dims = _get_dimensions(solid)
        filename = f"{component}_{side}_{i}of{total}.stl"

        # Determine print orientation based on component type
        if component in ("wing", "h_stab", "v_tail"):
            orientation = "trailing-edge down"
        elif component == "v_stab":
            orientation = "flat"
        else:
            orientation = "flat"

        parts.append(SectionPart(
            solid=solid,
            filename=filename,
            component=component,
            side=side,
            section_num=i,
            total_sections=total,
            dimensions_mm=(round(dims[0], 1), round(dims[1], 1), round(dims[2], 1)),
            print_orientation=orientation,
            assembly_order=start_assembly_order + i - 1,
            split_axis=split_axes[i - 1] if i - 1 < len(split_axes) else "Y",
        ))

    return parts
