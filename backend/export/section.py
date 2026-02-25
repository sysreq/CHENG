"""Auto-sectioning algorithm -- splits oversized components to fit the print bed.

Recursively bisects solids along the longest oversize axis until every piece
fits within the usable print volume (bed dimensions minus joint margin).

v0.7 (Issue #147): Smart split-point optimizer -- avoids internal features
(wing root attachment zone, near-tip region, fuselage wing-mount saddle)
by searching offsets [0, +10, -10, +20, -20] mm from the midpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq
    from backend.models import AircraftDesign

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_JOINT_MARGIN_MM: float = 20.0   # Margin per axis for joint features
_SPLIT_OFFSET_MM: float = 10.0   # Offset when midpoint hits internal features
_MAX_RECURSION: int = 20         # Safety limit to prevent infinite recursion
_MIN_SEGMENT_MM: float = 30.0    # Minimum section length after splitting

# Avoidance zone dimensions (mm)
_ROOT_ZONE_MM: float = 15.0      # Wing root attachment region from root face
_PANEL_BREAK_ZONE_MM: float = 8.0  # Panel break attachment region (±)
_TIP_ZONE_MM: float = 30.0       # Near-tip region from tip face
_FUSE_WING_ZONE_MM: float = 20.0  # Fuselage wing-mount saddle (±)

_AXIS_NAMES = {0: "X", 1: "Y", 2: "Z"}

# Offsets to try in order: midpoint first, then ±10mm, ±20mm
_SEARCH_OFFSETS = [0.0, 10.0, -10.0, 20.0, -20.0]


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
    # ── Issue #147: Smart split metadata ────────────────────────────────
    split_position_mm: float = 0.0   # absolute coordinate of the split plane
    avoidance_zone_hit: bool = False  # True if optimizer moved from ideal midpoint

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
    design: AircraftDesign | None = None,
    component: str = "",
) -> list[cq.Workplane]:
    """Recursively split a solid into sections that fit on the print bed.

    Algorithm (spec section 8.2):
    1. Usable volume = (bed - 20 mm margin) per axis.
    2. If solid fits, return [solid].
    3. Find axis with largest overshoot.
    4. Bisect using smart split optimizer (or midpoint when design=None).
    5. Recurse on each half.

    Args:
        solid:  CadQuery Workplane to section.
        bed_x/y/z: Print bed dimensions in mm (PR01/02/03).
        design: Aircraft parameters for smart split optimization. When None,
            falls back to pure midpoint (backward compatible).
        component: Component name ('wing', 'fuselage', etc.) for zone selection.
            Ignored when design=None.

    Returns:
        List of solids, each fitting within usable bed volume.

    Raises:
        ValueError: If bed dimensions minus margin <= 0.
        RuntimeError: If splitting fails after 20 recursion levels.
    """
    results = auto_section_with_meta(
        solid, bed_x, bed_y, bed_z, design=design, component=component
    )
    return [item[0] for item in results]


def auto_section_with_axis(
    solid: cq.Workplane,
    bed_x: float,
    bed_y: float,
    bed_z: float,
    design: AircraftDesign | None = None,
    component: str = "",
) -> list[tuple[cq.Workplane, str]]:
    """Like auto_section but also returns the split axis for each section.

    Args:
        solid:  CadQuery Workplane to section.
        bed_x/y/z: Print bed dimensions in mm.
        design: Aircraft parameters for smart split optimization. When None,
            falls back to pure midpoint (backward compatible).
        component: Component name for avoidance zone selection.

    Returns:
        List of (solid, split_axis) tuples. split_axis is "X", "Y", or "Z"
        indicating which axis the section was cut along. For unsplit solids,
        the axis defaults to "Y".
    """
    full = auto_section_with_meta(solid, bed_x, bed_y, bed_z, design=design, component=component)
    return [(item[0], item[1]) for item in full]


def auto_section_with_meta(
    solid: cq.Workplane,
    bed_x: float,
    bed_y: float,
    bed_z: float,
    design: AircraftDesign | None = None,
    component: str = "",
) -> list[tuple[cq.Workplane, str, float, bool]]:
    """Like auto_section_with_axis but also returns split metadata (Issue #147).

    Args:
        solid:  CadQuery Workplane to section.
        bed_x/y/z: Print bed dimensions in mm.
        design: Aircraft parameters for smart split optimization. When None,
            falls back to pure midpoint (backward compatible).
        component: Component name for avoidance zone selection.

    Returns:
        List of (solid, split_axis, split_position_mm, avoidance_zone_hit) tuples.
        split_axis: "X", "Y", or "Z".
        split_position_mm: Absolute coordinate of the split plane (0.0 if not split).
        avoidance_zone_hit: True if the optimizer moved the split from midpoint.
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

    # Compute full-component bounding box ONCE at the top level and pass it
    # through recursion so that avoidance zones stay stable (Gemini #1/#7 fix).
    comp_bb = solid.val().BoundingBox()
    comp_bbox = (comp_bb.xmin, comp_bb.ymin, comp_bb.zmin,
                 comp_bb.xmax, comp_bb.ymax, comp_bb.zmax)

    return _recursive_section(
        cq, solid, usable_x, usable_y, usable_z, depth=0,
        design=design, component=component, comp_bbox=comp_bbox,
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


def _is_in_zone(pos: float, zones: list[tuple[float, float]]) -> bool:
    """Return True if pos falls inside any of the avoidance zones."""
    return any(z_min <= pos <= z_max for (z_min, z_max) in zones)


def _compute_avoidance_zones(
    design: AircraftDesign,
    component: str,
    axis: int,
    comp_axis_min: float,
    comp_axis_max: float,
) -> list[tuple[float, float]]:
    """Return list of (zone_min, zone_max) avoidance zones for the split axis.

    IMPORTANT: ``comp_axis_min`` / ``comp_axis_max`` must be the bounding-box
    extents of the *full* component (not a sub-piece), so that zone positions
    remain stable across recursive splits.  The zones are expressed as absolute
    coordinates along the same axis, so they can be compared directly against
    any candidate split position (even one inside a sub-piece).

    Wing (axis=1, spanwise Y):
        - Zone A: Both ends of the full-component extent, ±ROOT_ZONE_MM.
          (covers left-wing root at max-Y and right-wing root at min-Y alike)
        - Zone B: Panel break positions ±PANEL_BREAK_ZONE_MM (if wing_sections > 1).
        - Zone C: Near-tip regions at BOTH extremes (TIP_ZONE_MM inward).

    Fuselage (axis=0, fore-aft X):
        - Zone D: Wing-mount saddle ±FUSE_WING_ZONE_MM around the absolute
          saddle position (wing_x_frac * fuselage_length from axis_min).
    """
    zones: list[tuple[float, float]] = []

    # Normalise component names: "wing_left" / "wing_right" → "wing"
    comp = component.lower()
    if "wing" in comp and "stab" not in comp:
        comp = "wing"

    if comp == "wing" and axis == 1:  # Y-axis (spanwise)
        # Zone A: Root attachment — protect BOTH ends of the full-component span.
        # Right wing: root is at comp_axis_min (Y≈0), tip at comp_axis_max.
        # Left  wing: root is at comp_axis_max (Y≈0), tip at comp_axis_min (negative).
        # By adding zones at both ends we handle both orientations correctly.
        zones.append((comp_axis_min, comp_axis_min + _ROOT_ZONE_MM))
        zones.append((comp_axis_max - _ROOT_ZONE_MM, comp_axis_max))

        # Zone B: panel break positions (requires wing_sections + panel_break_positions)
        wing_sections = getattr(design, "wing_sections", 1)
        if wing_sections > 1:
            panel_break_positions = getattr(design, "panel_break_positions", [])
            span_extent = comp_axis_max - comp_axis_min
            for frac in panel_break_positions:
                # Scale break fraction over the full-component extent
                break_absolute = comp_axis_min + (frac / 100.0) * span_extent
                zones.append((
                    break_absolute - _PANEL_BREAK_ZONE_MM,
                    break_absolute + _PANEL_BREAK_ZONE_MM,
                ))

        # Zone C is now incorporated into Zone A (both ends protected).
        # The tip zone is the same as the "other end" root zone above.

    elif comp == "fuselage" and axis == 0:  # X-axis (fore-aft)
        # Zone D: wing-mount saddle.
        # The saddle is at wing_x_frac * fuselage_length measured from the
        # component's own bounding-box start (comp_axis_min).
        try:
            from backend.geometry.engine import _WING_X_FRACTION
            wing_x_frac = _WING_X_FRACTION.get(design.fuselage_preset, 0.30)
        except (ImportError, AttributeError):
            wing_x_frac = 0.30

        # Absolute saddle position: comp_axis_min + wing_x_frac * full_span
        full_span = comp_axis_max - comp_axis_min
        saddle_absolute = comp_axis_min + wing_x_frac * full_span
        zones.append((saddle_absolute - _FUSE_WING_ZONE_MM, saddle_absolute + _FUSE_WING_ZONE_MM))

    return zones


def _find_smart_split_position(
    solid: cq.Workplane,
    axis: int,
    design: AircraftDesign | None = None,
    component: str = "",
    comp_axis_min: float | None = None,
    comp_axis_max: float | None = None,
) -> tuple[float, bool]:
    """Find the optimal split position along the given axis.

    Starts at midpoint. If midpoint falls within an avoidance zone, tries
    offsets in order: +10mm, -10mm, +20mm, -20mm. Falls back to midpoint if
    all offsets also hit avoidance zones (or if design=None).

    Avoidance zones (active when design is provided):
        - Wing (axis=1): root attachment at both ends (15mm), panel breaks (±8mm)
        - Fuselage (axis=0): wing-mount saddle (±20mm)

    Zones are computed from ``comp_axis_min``/``comp_axis_max`` (the FULL
    component's bounding-box extent, not the current sub-piece's extent).
    This ensures zone positions remain stable across recursive splits.
    If not provided, falls back to the current solid's own bbox (correct only
    for non-recursive callers such as tests).

    Minimum segment enforcement: candidates that would produce a section
    shorter than _MIN_SEGMENT_MM (30mm) are discarded. If no valid candidate
    remains after filtering, midpoint is returned as-is.

    Args:
        solid:          CadQuery solid being split (the current sub-piece).
        axis:           0=X, 1=Y, 2=Z.
        design:         Aircraft parameters (for avoidance zones). None = pure midpoint.
        component:      Component name ('wing', 'fuselage', etc.) for zone selection.
        comp_axis_min:  Full-component bounding-box minimum along axis (from root call).
        comp_axis_max:  Full-component bounding-box maximum along axis (from root call).

    Returns:
        Tuple of (split_position_mm, avoidance_zone_hit).
        split_position_mm: Absolute coordinate along axis for the split plane.
        avoidance_zone_hit: True if the split was moved away from the midpoint
            to avoid a feature zone.
    """
    bb = _get_bounding_box(solid)
    axis_min = bb[axis]          # current sub-piece min (for midpoint + min-segment)
    axis_max = bb[axis + 3]      # current sub-piece max (for midpoint + min-segment)
    midpoint = (axis_min + axis_max) / 2.0

    # When no design is available, fall back to pure midpoint (backward compat)
    if design is None:
        return midpoint, False

    # Use the full-component bounds for zone computation if provided;
    # fall back to the current solid's bounds (caller is responsible for passing these).
    cmin = comp_axis_min if comp_axis_min is not None else axis_min
    cmax = comp_axis_max if comp_axis_max is not None else axis_max

    # Build avoidance zones from the full-component bounding-box coordinates
    zones = _compute_avoidance_zones(design, component, axis, cmin, cmax)

    # No zones for this component/axis combination — use midpoint directly
    if not zones:
        return midpoint, False

    # Build candidate positions: midpoint of the CURRENT PIECE + search offsets
    candidates = [midpoint + off for off in _SEARCH_OFFSETS]

    # Filter to positions that leave at least _MIN_SEGMENT_MM on both sides
    # of the CURRENT piece (not the full component).
    valid_candidates = [
        c for c in candidates
        if axis_min + _MIN_SEGMENT_MM <= c <= axis_max - _MIN_SEGMENT_MM
    ]

    # If the minimum-segment filter removes everything, fall back to midpoint
    if not valid_candidates:
        return midpoint, False

    # Score each candidate: 0.0 = outside all zones (best), >0 = inside a zone
    def _score(pos: float) -> float:
        for z_min, z_max in zones:
            if z_min <= pos <= z_max:
                # Distance to nearest zone boundary (smaller = closer to clean exit)
                return min(abs(pos - z_min), abs(pos - z_max))
        return 0.0  # outside all zones: best possible score

    best = min(valid_candidates, key=_score)
    # avoidance_zone_hit is True when we successfully moved away from midpoint
    moved = abs(best - midpoint) > 1e-6
    return best, moved


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
    last_split_pos: float = 0.0,
    last_zone_hit: bool = False,
    design: AircraftDesign | None = None,
    component: str = "",
    comp_bbox: tuple[float, float, float, float, float, float] | None = None,
) -> list[tuple[cq.Workplane, str, float, bool]]:
    """Recursively split solid until all pieces fit the usable volume.

    Returns list of (solid, split_axis, split_position_mm, avoidance_zone_hit)
    tuples where:
        split_axis: axis of the most recent split ("X", "Y", or "Z").
        split_position_mm: absolute coordinate of the split plane that produced
            this section (0.0 for the root call if no split was needed).
        avoidance_zone_hit: True if the optimizer moved the split from midpoint.

    Args:
        cq_mod:    The cadquery module.
        solid:     CadQuery solid to split.
        usable_x/y/z: Usable bed dimensions (bed minus margin).
        depth:     Current recursion depth.
        last_split_axis: Axis of the most recent split (propagated to leaves).
        last_split_pos: Split coordinate that produced the current fragment
            (propagated to leaves so callers can read the cut position).
        last_zone_hit: Whether the split producing this fragment was adjusted.
        design:    Aircraft parameters for smart split optimization (optional).
        component: Component name for avoidance zone selection (optional).
        comp_bbox: Full-component bounding box (xmin,ymin,zmin,xmax,ymax,zmax)
            from the root invocation. Passed unchanged through recursion so that
            avoidance zones are computed against the whole component, not sub-pieces.
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
        return [(solid, last_split_axis, last_split_pos, last_zone_hit)]

    # Find axis with largest overshoot
    axis = overshoot.index(max(overshoot))
    axis_name = _AXIS_NAMES[axis]

    # Extract full-component bounding-box extents along this axis
    comp_axis_min = comp_bbox[axis] if comp_bbox else None
    comp_axis_max = comp_bbox[axis + 3] if comp_bbox else None

    # Determine split position using smart optimizer (or midpoint fallback)
    split_pos, zone_hit = _find_smart_split_position(
        solid, axis, design=design, component=component,
        comp_axis_min=comp_axis_min, comp_axis_max=comp_axis_max,
    )

    # Try bisecting at the chosen position
    actual_split_pos = split_pos
    try:
        lower, upper = _bisect_solid(cq_mod, solid, axis, split_pos)

        # Check for degenerate results (empty solids)
        lower_dims = _get_dimensions(lower)
        upper_dims = _get_dimensions(upper)

        if min(lower_dims) < 0.1 or min(upper_dims) < 0.1:
            # Degenerate -- try midpoint + offset as fallback
            bb = _get_bounding_box(solid)
            midpoint = (bb[axis] + bb[axis + 3]) / 2.0
            actual_split_pos = midpoint + _SPLIT_OFFSET_MM
            lower, upper = _bisect_solid(cq_mod, solid, axis, actual_split_pos)
    except Exception:
        # If bisection fails, try with offset from midpoint
        try:
            bb = _get_bounding_box(solid)
            midpoint = (bb[axis] + bb[axis + 3]) / 2.0
            actual_split_pos = midpoint + _SPLIT_OFFSET_MM
            lower, upper = _bisect_solid(cq_mod, solid, axis, actual_split_pos)
        except Exception:
            # Last resort: try the other direction
            bb = _get_bounding_box(solid)
            midpoint = (bb[axis] + bb[axis + 3]) / 2.0
            actual_split_pos = midpoint - _SPLIT_OFFSET_MM
            lower, upper = _bisect_solid(cq_mod, solid, axis, actual_split_pos)

    # Recurse on each half — propagate the split position and full-component bbox
    result: list[tuple[cq.Workplane, str, float, bool]] = []
    result.extend(
        _recursive_section(
            cq_mod, lower, usable_x, usable_y, usable_z, depth + 1,
            last_split_axis=axis_name,
            last_split_pos=actual_split_pos,
            last_zone_hit=zone_hit,
            design=design, component=component, comp_bbox=comp_bbox,
        )
    )
    result.extend(
        _recursive_section(
            cq_mod, upper, usable_x, usable_y, usable_z, depth + 1,
            last_split_axis=axis_name,
            last_split_pos=actual_split_pos,
            last_zone_hit=zone_hit,
            design=design, component=component, comp_bbox=comp_bbox,
        )
    )

    return result


def create_section_parts(
    component: str,
    side: str,
    sections: list[cq.Workplane],
    start_assembly_order: int = 1,
    split_axes: list[str] | None = None,
    split_positions: list[float] | None = None,
    avoidance_hits: list[bool] | None = None,
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
        split_positions: Optional list of absolute split-plane coordinates per section.
            If not provided, defaults to 0.0 for all sections.
        avoidance_hits: Optional list of avoidance_zone_hit flags per section.
            If not provided, defaults to False for all sections.

    Returns:
        List of SectionPart objects with metadata.
    """
    total = len(sections)
    parts: list[SectionPart] = []

    if split_axes is None:
        split_axes = ["Y"] * total
    if split_positions is None:
        split_positions = [0.0] * total
    if avoidance_hits is None:
        avoidance_hits = [False] * total

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

        idx = i - 1
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
            split_axis=split_axes[idx] if idx < len(split_axes) else "Y",
            split_position_mm=split_positions[idx] if idx < len(split_positions) else 0.0,
            avoidance_zone_hit=avoidance_hits[idx] if idx < len(avoidance_hits) else False,
        ))

    return parts
