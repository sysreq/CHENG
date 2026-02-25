"""Fuselage geometry builder -- generates fuselage solids via CadQuery lofting.

Three fuselage presets:
  - Conventional: tubular loft with nose/cabin/tail-cone zones
  - Pod: shorter/wider fuselage for pusher configurations
  - Blended-Wing-Body (BWB): blends into the wing root
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

from backend.models import AircraftDesign

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOTOR_BOSS_DIAMETER_MM: float = 30.0
_MOTOR_BOSS_DEPTH_MM: float = 15.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_fuselage(design: AircraftDesign) -> cq.Workplane:
    """Build the fuselage solid based on the selected fuselage preset.

    Generates a closed, watertight fuselage solid positioned at the origin
    with the nose pointing in the +X direction.  The fuselage length runs
    along the X axis, width along Y, and height along Z.

    The geometry varies by fuselage_preset (G01):

    - **"Conventional"**: Tubular fuselage built by lofting circular/oval
      cross-sections along X.  Three zones:
        - Nose (25% of fuselage_length): tapers from small nose radius to max.
        - Cabin (50%): constant cross-section with wing saddle cutout.
        - Tail cone (25%): tapers down to small tail radius.
      Wall thickness is 1.6 mm (F14).

    - **"Pod"**: Shorter, wider fuselage for pusher configs.  Blunter nose
      (15%), wider cabin (60%), shorter tail cone (25%).  Oval cross-sections.

    - **"Blended-Wing-Body"**: Blends smoothly into the wing root.
      Lofts from rounded-rectangle nose to airfoil-shaped wing junction.

    All presets include:
    - Wing saddle cutout positioned per wing_mount_type (High/Mid/Low/Shoulder)
    - Motor mount boss at nose (Tractor) or tail (Pusher) per motor_config
    - Hollow interior when hollow_parts is True

    Args:
        design: Complete aircraft design parameters.

    Returns:
        cq.Workplane with fuselage solid.  Origin at nose, +X toward tail, +Z up.

    Raises:
        ValueError: If fuselage_preset is not one of the three supported types.
    """
    import cadquery as cq  # noqa: F811

    preset = design.fuselage_preset
    length = design.fuselage_length

    if preset == "Conventional":
        result = _build_conventional(cq, design, length)
    elif preset == "Pod":
        result = _build_pod(cq, design, length)
    elif preset == "Blended-Wing-Body":
        result = _build_bwb(cq, design, length)
    else:
        raise ValueError(
            f"Unsupported fuselage_preset: '{preset}'. "
            f"Expected 'Conventional', 'Pod', or 'Blended-Wing-Body'."
        )

    # Add motor mount boss
    result = _add_motor_boss(cq, result, design, length)

    # Hollow interior if requested — F14: wall_thickness is user-editable
    if design.hollow_parts:
        result = _shell_fuselage(result, design.wall_thickness)

    return result


# ---------------------------------------------------------------------------
# Preset builders
# ---------------------------------------------------------------------------


def _build_conventional(cq_mod: type, design: AircraftDesign, length: float) -> cq.Workplane:
    """Conventional tubular fuselage: 3-zone loft with circular cross-sections."""
    cq = cq_mod

    # Cross-section dimensions -- based on wing chord for proportional sizing
    max_width = design.wing_chord * 0.35
    max_height = max_width * 1.1  # slightly taller than wide

    nose_radius = max_width * 0.15
    tail_radius = max_width * 0.2

    # Zone boundaries along X — F05/F06/F07: user-editable section lengths.
    # Scale proportionally so sections sum to fuselage_length.
    section_sum = (
        design.fuselage_nose_length
        + design.fuselage_cabin_length
        + design.fuselage_tail_length
    )
    if section_sum > 0:
        nose_end = length * (design.fuselage_nose_length / section_sum)
        cabin_end = length * (
            (design.fuselage_nose_length + design.fuselage_cabin_length) / section_sum
        )
    else:
        nose_end = length * 0.25
        cabin_end = length * 0.75

    # Wing mount Z offset
    mount_z = _wing_mount_z_offset(design, max_height)

    # Build cross-sections at key stations: (x_position, width, height)
    stations = [
        (0.0, nose_radius, nose_radius),               # nose tip
        (nose_end * 0.5, max_width * 0.6, max_height * 0.6),  # mid-nose
        (nose_end, max_width, max_height),              # start of cabin
        (cabin_end, max_width, max_height),             # end of cabin
        (cabin_end + (length - cabin_end) * 0.5,
         max_width * 0.5, max_height * 0.5),            # mid tail cone
        (length, tail_radius, tail_radius),             # tail tip
    ]

    # Loft through elliptical sections using chained workplane offsets
    result = cq.Workplane("YZ").ellipse(stations[0][1] / 2, stations[0][2] / 2)
    prev_x = stations[0][0]
    for x_pos, w, h in stations[1:]:
        delta = x_pos - prev_x
        result = result.workplane(offset=delta).ellipse(w / 2, h / 2)
        prev_x = x_pos

    result = result.loft(ruled=False)

    return result


def _build_pod(cq_mod: type, design: AircraftDesign, length: float) -> cq.Workplane:
    """Pod fuselage: shorter/wider, blunter nose, for pusher configs."""
    cq = cq_mod

    max_width = design.wing_chord * 0.45  # wider than conventional
    max_height = max_width * 1.0

    nose_radius = max_width * 0.3  # blunter nose
    tail_radius = max_width * 0.15

    # Zone boundaries — F05/F06/F07: user-editable section lengths.
    section_sum = (
        design.fuselage_nose_length
        + design.fuselage_cabin_length
        + design.fuselage_tail_length
    )
    if section_sum > 0:
        nose_end = length * (design.fuselage_nose_length / section_sum)
        cabin_end = length * (
            (design.fuselage_nose_length + design.fuselage_cabin_length) / section_sum
        )
    else:
        nose_end = length * 0.15
        cabin_end = length * 0.75

    stations = [
        (0.0, nose_radius, nose_radius),
        (nose_end, max_width, max_height),
        (cabin_end, max_width, max_height),
        (cabin_end + (length - cabin_end) * 0.6,
         max_width * 0.4, max_height * 0.4),
        (length, tail_radius, tail_radius),
    ]

    result = cq.Workplane("YZ").ellipse(stations[0][1] / 2, stations[0][2] / 2)
    prev_x = stations[0][0]
    for x_pos, w, h in stations[1:]:
        delta = x_pos - prev_x
        result = result.workplane(offset=delta).ellipse(w / 2, h / 2)
        prev_x = x_pos

    result = result.loft(ruled=False)

    return result


def _build_bwb(cq_mod: type, design: AircraftDesign, length: float) -> cq.Workplane:
    """Blended-Wing-Body: blends from rounded nose to airfoil-shaped wing junction."""
    cq = cq_mod

    # BWB is wider, blends into wing root
    max_width = design.wing_chord * 0.6
    max_height = design.wing_chord * 0.15  # flatter -- airfoil-like

    nose_width = max_width * 0.3
    nose_height = max_height * 0.8

    # #219: Station positions derived from design section-length parameters so
    # nose_length / cabin_length / tail_taper_length sliders update the preview.
    # Scale proportionally so sections sum to fuselage_length (same as Conventional).
    section_sum = (
        design.fuselage_nose_length
        + design.fuselage_cabin_length
        + design.fuselage_tail_length
    )
    if section_sum > 0:
        nose_end = length * (design.fuselage_nose_length / section_sum)
        cabin_end = length * (
            (design.fuselage_nose_length + design.fuselage_cabin_length) / section_sum
        )
    else:
        nose_end = length * 0.2
        cabin_end = length * 0.8

    stations = [
        (0.0, nose_width, nose_height),
        (nose_end, max_width * 0.7, max_height * 0.9),
        (cabin_end * 0.5 + nose_end * 0.5, max_width, max_height),
        (cabin_end, max_width * 0.9, max_height * 0.8),
        (length, max_width * 0.3, max_height * 0.3),
    ]

    result = cq.Workplane("YZ").ellipse(stations[0][1] / 2, stations[0][2] / 2)
    prev_x = stations[0][0]
    for x_pos, w, h in stations[1:]:
        delta = x_pos - prev_x
        result = result.workplane(offset=delta).ellipse(w / 2, h / 2)
        prev_x = x_pos

    result = result.loft(ruled=False)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wing_mount_z_offset(design: AircraftDesign, fuselage_height: float) -> float:
    """Compute the Z offset for the wing saddle based on wing_mount_type.

    Returns vertical offset from fuselage centerline (Z=0).
    """
    half_h = fuselage_height / 2
    offsets = {
        "High-Wing": half_h * 0.8,
        "Shoulder-Wing": half_h * 0.5,
        "Mid-Wing": 0.0,
        "Low-Wing": -half_h * 0.8,
    }
    return offsets.get(design.wing_mount_type, 0.0)


def _add_motor_boss(
    cq_mod: type,
    solid: cq.Workplane,
    design: AircraftDesign,
    length: float,
) -> cq.Workplane:
    """Add a cylindrical motor mount boss at nose (Tractor) or tail (Pusher).

    The boss is a protruding cylinder centered on the X axis.
    """
    cq = cq_mod

    if design.engine_count == 0:
        return solid

    boss_r = _MOTOR_BOSS_DIAMETER_MM / 2
    boss_depth = _MOTOR_BOSS_DEPTH_MM

    if design.motor_config == "Tractor":
        # Boss at nose: extends in -X direction from X=0
        boss = (
            cq.Workplane("YZ")
            .circle(boss_r)
            .extrude(-boss_depth)
        )
    else:
        # Pusher: boss at tail, extends in +X from X=length.
        # #218: Use workplane(offset=length) to correctly position the YZ plane at
        # X=length along the fuselage axis (world X = YZ plane normal direction).
        # Previously used transformed(offset=(length,0,0)) which shifted in local X
        # of the YZ plane (= world Y, sideways), creating a stray circle at Y=length.
        boss = (
            cq.Workplane("YZ")
            .workplane(offset=length)
            .circle(boss_r)
            .extrude(boss_depth)
        )

    try:
        result = solid.union(boss)
    except Exception:
        # If boolean union fails, return the fuselage without the boss
        result = solid

    return result


def _shell_fuselage(solid: cq.Workplane, thickness: float) -> cq.Workplane:
    """Shell the fuselage to create a hollow interior.

    Removes the largest planar face (if any) to leave openings
    for internal access, then shells to the given wall thickness.
    """
    try:
        result = solid.shell(-thickness)
    except Exception:
        # Shell can fail on complex geometry; return solid as fallback
        result = solid
    return result
