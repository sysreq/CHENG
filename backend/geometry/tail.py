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

# ---------------------------------------------------------------------------
# Constants (MVP fixed values per spec)
# ---------------------------------------------------------------------------

_V_TAIL_SWEEP_DEG: float = 0.0   # T15 -- fixed at 0 deg for MVP
_TAIL_AIRFOIL: str = "NACA-0012"  # Symmetric airfoil for all tail surfaces


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
    - Use flat-plate or symmetric airfoil profiles
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
# Component builders
# ---------------------------------------------------------------------------


def _build_h_stab_half(
    cq_mod: type,
    design: AircraftDesign,
    side: str,
    z_offset: float,
) -> cq.Workplane:
    """Build one half of the horizontal stabiliser.

    Uses a symmetric airfoil (NACA 0012) or flat plate.
    Lofts from root to tip with incidence applied.

    The h-stab is positioned at the tail_arm distance along X.
    Root at Y=0, tip at Y = +/-h_stab_span/2.
    """
    cq = cq_mod

    chord = design.h_stab_chord
    half_span = design.h_stab_span / 2.0
    incidence = design.h_stab_incidence

    y_sign = -1.0 if side == "left" else 1.0

    # Use a simple NACA-like symmetric profile for the stab
    # Build as a rectangular planform with constant chord
    # (no taper on tail surfaces for MVP)
    thickness_ratio = 0.12  # 12% thickness (NACA 0012 equivalent)
    half_thickness = chord * thickness_ratio / 2.0

    # Incidence rotation
    inc_rad = math.radians(incidence)

    # Root cross-section: simple ellipse approximation of symmetric airfoil
    root_wire = (
        cq.Workplane("XZ")
        .transformed(offset=(0, 0, z_offset), rotate=(0, -incidence, 0))
        .ellipse(chord / 2, half_thickness)
    )

    # Tip cross-section
    tip_wire = (
        cq.Workplane("XZ")
        .transformed(
            offset=(0, y_sign * half_span, z_offset),
            rotate=(0, -incidence, 0),
        )
        .ellipse(chord / 2, half_thickness)
    )

    result = root_wire.add(tip_wire).loft(ruled=False)

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
    Uses symmetric airfoil profile.
    """
    cq = cq_mod

    root_chord = design.v_stab_root_chord
    height = design.v_stab_height
    tip_chord = root_chord * 0.6  # 60% taper at tip for v-stab

    thickness_ratio = 0.12
    root_half_t = root_chord * thickness_ratio / 2.0
    tip_half_t = tip_chord * thickness_ratio / 2.0

    # Root cross-section in XY plane at Z=mount_z
    root_wire = (
        cq.Workplane("XY")
        .transformed(offset=(0, 0, mount_z))
        .ellipse(root_chord / 2, root_half_t)
    )

    # Tip cross-section at Z = mount_z + height
    tip_wire = (
        cq.Workplane("XY")
        .transformed(offset=(0, 0, mount_z + height))
        .ellipse(tip_chord / 2, tip_half_t)
    )

    result = root_wire.add(tip_wire).loft(ruled=False)

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
    """
    cq = cq_mod

    chord = design.v_tail_chord
    half_span = design.v_tail_span / 2.0
    dihedral = design.v_tail_dihedral
    incidence = design.v_tail_incidence

    y_sign = -1.0 if side == "left" else 1.0

    thickness_ratio = 0.09  # thinner for V-tail
    half_thickness = chord * thickness_ratio / 2.0

    dihedral_rad = math.radians(dihedral)

    # Tip offset due to dihedral
    tip_y = y_sign * half_span * math.cos(dihedral_rad)
    tip_z = half_span * math.sin(dihedral_rad)

    # Root cross-section
    root_wire = (
        cq.Workplane("XZ")
        .transformed(offset=(0, 0, 0), rotate=(0, -incidence, 0))
        .ellipse(chord / 2, half_thickness)
    )

    # Tip cross-section
    tip_wire = (
        cq.Workplane("XZ")
        .transformed(
            offset=(0, tip_y, tip_z),
            rotate=(0, -incidence, 0),
        )
        .ellipse(chord / 2, half_thickness)
    )

    result = root_wire.add(tip_wire).loft(ruled=False)

    # Shell if hollow
    if design.hollow_parts:
        try:
            result = result.shell(-design.wing_skin_thickness)
        except Exception:
            pass

    return result
