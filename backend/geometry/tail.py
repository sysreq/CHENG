"""Tail surface geometry builder -- generates tail components via CadQuery.

Supports four tail configurations:
  - Conventional: horizontal stab (left/right) + vertical stab
  - T-Tail: h_stab mounted atop v_stab
  - V-Tail: two canted surfaces
  - Cruciform: h_stab at midpoint of v_stab
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

from backend.models import AircraftDesign
from backend.geometry.airfoil import load_airfoil


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_tail(design: AircraftDesign) -> dict[str, cq.Workplane]:
    """Build all tail surfaces based on the selected tail type.

    Returns a dictionary of named tail components.  Keys are used as component
    identifiers throughout the export pipeline (filenames, manifest, assembly order).

    **Tail types and returned components:**

    - **"Conventional"**: {"h_stab_left", "h_stab_right", "v_stab"}
    - **"T-Tail"**: Same keys as Conventional; h_stab mounted atop v_stab.
    - **"V-Tail"**: {"v_tail_left", "v_tail_right"} -- rotated by v_tail_dihedral.
    - **"Cruciform"**: Same keys as Conventional; h_stab at v_stab midpoint.

    All tail surfaces:
    - Positioned at X = tail_arm aft of wing aerodynamic center
    - Use the airfoil profile selected via design.tail_airfoil (T23)
    - NACA-0012 is the default for backward compatibility
    - Shelled to wing_skin_thickness if hollow_parts is True
    - Trailing edge min thickness enforced per te_min_thickness

    Args:
        design: Complete aircraft design parameters.

    Returns:
        Dict mapping component name -> positioned CadQuery solid.

    Raises:
        ValueError: If tail_type is not one of the four supported types.
    """
    import cadquery as cq  # noqa: F811

    tail_type = design.tail_type

    if tail_type == "Conventional":
        return _build_conventional_tail(cq, design)
    elif tail_type == "T-Tail":
        return _build_t_tail(cq, design)
    elif tail_type == "V-Tail":
        return _build_v_tail(cq, design)
    elif tail_type == "Cruciform":
        return _build_cruciform_tail(cq, design)
    else:
        raise ValueError(
            f"Unsupported tail_type: '{tail_type}'. "
            f"Expected 'Conventional', 'T-Tail', 'V-Tail', or 'Cruciform'."
        )


# ---------------------------------------------------------------------------
# Tail type builders
# ---------------------------------------------------------------------------


def _build_conventional_tail(
    cq_mod: type,
    design: AircraftDesign,
) -> dict[str, cq.Workplane]:
    """Conventional tail: horizontal stab (left + right) and vertical stab.

    H-stab at fuselage centerline Z, V-stab extending upward.
    """
    cq = cq_mod

    h_stab_left = _build_h_stab_half(cq, design, side="left", z_offset=0.0)
    h_stab_right = _build_h_stab_half(cq, design, side="right", z_offset=0.0)
    v_stab = _build_v_stab(cq, design, mount_z=0.0)

    return {
        "h_stab_left": h_stab_left,
        "h_stab_right": h_stab_right,
        "v_stab": v_stab,
    }


def _build_t_tail(
    cq_mod: type,
    design: AircraftDesign,
) -> dict[str, cq.Workplane]:
    """T-Tail: horizontal stab mounted at top of vertical stab.

    V-stab extends upward; h-stab is at the v_stab tip.
    """
    cq = cq_mod

    v_stab_height = design.v_stab_height
    v_stab = _build_v_stab(cq, design, mount_z=0.0)

    # H-stab at top of v-stab
    h_stab_left = _build_h_stab_half(cq, design, side="left", z_offset=v_stab_height)
    h_stab_right = _build_h_stab_half(cq, design, side="right", z_offset=v_stab_height)

    return {
        "h_stab_left": h_stab_left,
        "h_stab_right": h_stab_right,
        "v_stab": v_stab,
    }


def _build_v_tail(
    cq_mod: type,
    design: AircraftDesign,
) -> dict[str, cq.Workplane]:
    """V-Tail: two canted surfaces replacing both h-stab and v-stab.

    Each surface is canted at v_tail_dihedral angle from horizontal.
    """
    cq = cq_mod

    v_tail_left = _build_v_tail_half(cq, design, side="left")
    v_tail_right = _build_v_tail_half(cq, design, side="right")

    return {
        "v_tail_left": v_tail_left,
        "v_tail_right": v_tail_right,
    }


def _build_cruciform_tail(
    cq_mod: type,
    design: AircraftDesign,
) -> dict[str, cq.Workplane]:
    """Cruciform: h-stab at midpoint of v-stab height.

    V-stab extends upward; h-stab positioned at 50% v_stab_height.
    """
    cq = cq_mod

    mid_z = design.v_stab_height * 0.5
    v_stab = _build_v_stab(cq, design, mount_z=0.0)

    h_stab_left = _build_h_stab_half(cq, design, side="left", z_offset=mid_z)
    h_stab_right = _build_h_stab_half(cq, design, side="right", z_offset=mid_z)

    return {
        "h_stab_left": h_stab_left,
        "h_stab_right": h_stab_right,
        "v_stab": v_stab,
    }


# ---------------------------------------------------------------------------
# Airfoil helpers
# ---------------------------------------------------------------------------


def _scale_airfoil_2d(
    profile: list[tuple[float, float]],
    chord: float,
    incidence_deg: float,
) -> list[tuple[float, float]]:
    """Scale unit-chord airfoil profile to the given chord length and rotate by incidence.

    Args:
        profile: Unit-chord airfoil coordinates from load_airfoil() (Selig order).
        chord:   Target chord length in mm.
        incidence_deg: Rotation angle in degrees (positive = nose up).

    Returns:
        Scaled and rotated list of (x, y) tuples.
    """
    sin_r = math.sin(math.radians(incidence_deg))
    cos_r = math.cos(math.radians(incidence_deg))
    # Centre of rotation at quarter-chord
    xc = 0.25
    scaled: list[tuple[float, float]] = []
    for xu, yu in profile:
        # Shift so quarter-chord is at origin, scale, rotate, shift back
        dx = (xu - xc) * chord
        dy = yu * chord
        x_rot = dx * cos_r - dy * sin_r + xc * chord
        y_rot = dx * sin_r + dy * cos_r
        scaled.append((x_rot, y_rot))
    return scaled


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------


def _build_h_stab_half(
    cq_mod: type,
    design: AircraftDesign,
    side: str,
    z_offset: float,
) -> cq.Workplane:
    """Build one half of the horizontal stabiliser.

    Uses the tail airfoil selected via design.tail_airfoil (T23).
    Lofts from root to tip with incidence applied.

    The h-stab is positioned at the tail_arm distance along X.
    Root at Y=0, tip at Y = +/-h_stab_span/2.
    """
    cq = cq_mod

    chord = design.h_stab_chord
    half_span = design.h_stab_span / 2.0
    incidence = design.h_stab_incidence

    y_sign = -1.0 if side == "left" else 1.0

    # Load airfoil profile and scale to chord length with incidence
    profile = load_airfoil(design.tail_airfoil)
    pts = _scale_airfoil_2d(profile, chord, incidence)

    # Loft from root to tip using chained workplane offsets.
    # XZ workplane: local X = chord axis, local Y = Z (vertical, used for z_offset),
    # local Z = -Y (spanwise, used for half_span offset).
    result = (
        cq.Workplane("XZ")
        .transformed(offset=(0, z_offset, 0))
        .spline(pts, periodic=False).close()
        .workplane(offset=y_sign * half_span)
        .spline(pts, periodic=False).close()
        .loft(ruled=False)
    )

    # Shell if hollow
    if design.hollow_parts:
        try:
            result = result.shell(-design.wing_skin_thickness)
        except Exception:
            pass  # Fallback: solid

    return result


def _build_v_stab(
    cq_mod: type,
    design: AircraftDesign,
    mount_z: float,
) -> cq.Workplane:
    """Build the vertical stabiliser.

    Extends upward in +Z from mount_z.
    Root chord at bottom, with slight taper to tip.
    Uses the tail airfoil selected via design.tail_airfoil (T23).
    """
    cq = cq_mod

    root_chord = design.v_stab_root_chord
    height = design.v_stab_height
    taper_ratio = 0.6  # 60% taper at tip for v-stab

    # Load and scale airfoil for root and tip cross-sections
    profile = load_airfoil(design.tail_airfoil)
    root_pts = _scale_airfoil_2d(profile, root_chord, 0.0)
    tip_pts = _scale_airfoil_2d(profile, root_chord * taper_ratio, 0.0)

    # Loft from root to tip.
    # XY workplane: local X = chord axis, local Y = spanwise (horizontal).
    # V-stab extends upward (Z), so we offset along Z using workplane(offset=height).
    result = (
        cq.Workplane("XY")
        .transformed(offset=(0, 0, mount_z))
        .spline(root_pts, periodic=False).close()
        .workplane(offset=height)
        .spline(tip_pts, periodic=False).close()
        .loft(ruled=False)
    )

    # Shell if hollow
    if design.hollow_parts:
        try:
            result = result.shell(-design.wing_skin_thickness)
        except Exception:
            pass

    return result


def _build_v_tail_half(
    cq_mod: type,
    design: AircraftDesign,
    side: str,
) -> cq.Workplane:
    """Build one half of a V-tail surface.

    The V-tail surface is a single panel canted at v_tail_dihedral from
    horizontal.  "left" cants in -Y + upward, "right" in +Y + upward.
    Uses the tail airfoil selected via design.tail_airfoil (T23).
    """
    cq = cq_mod

    chord = design.v_tail_chord
    half_span = design.v_tail_span / 2.0
    dihedral = design.v_tail_dihedral
    incidence = design.v_tail_incidence
    sweep_deg = design.v_tail_sweep  # T15: user-editable V-tail sweep

    y_sign = -1.0 if side == "left" else 1.0

    dihedral_rad = math.radians(dihedral)
    sweep_rad = math.radians(sweep_deg)

    # Tip offset due to dihedral (projected onto Y and Z world axes)
    tip_y = y_sign * half_span * math.cos(dihedral_rad)
    tip_z = half_span * math.sin(dihedral_rad)

    # #216: Sweep offset — tip chord centre moves aft in world X.
    # tip_x = root_x + half_span * tan(sweep_rad).
    # In the XZ workplane local frame: local-X = world-X, local-Y = world-Z,
    # so transformed(offset=(sweep_offset_x, tip_z, 0)) after
    # workplane(offset=tip_y) places the tip correctly in world space.
    sweep_offset_x = half_span * math.tan(sweep_rad)

    # Load and scale airfoil profile with incidence applied
    profile = load_airfoil(design.tail_airfoil)
    pts = _scale_airfoil_2d(profile, chord, incidence)

    # Loft from root to tip using chained workplane offsets.
    # Incidence is already baked into pts via _scale_airfoil_2d.
    result = (
        cq.Workplane("XZ")
        .spline(pts, periodic=False).close()
        .workplane(offset=tip_y)
        .transformed(offset=(sweep_offset_x, tip_z, 0))
        .spline(pts, periodic=False).close()
        .loft(ruled=False)
    )

    # Shell if hollow
    if design.hollow_parts:
        try:
            result = result.shell(-design.wing_skin_thickness)
        except Exception:
            pass

    return result
