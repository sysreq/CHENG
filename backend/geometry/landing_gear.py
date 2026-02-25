"""Landing gear geometry builder.

Generates CadQuery solids for tricycle and taildragger landing gear configurations.
Returns a dict of named components; returns empty dict when landing_gear_type == 'None'.

Coordinate system (aircraft frame):
  Origin: nose
  +X: aft (toward tail)
  +Y: starboard (right wing)
  +Z: up

Component IDs (WebSocket trailer keys):
  gear_main_left   — left main strut + wheel
  gear_main_right  — right main strut + wheel
  gear_nose        — nose gear strut + wheel (Tricycle only)
  gear_tail        — tail wheel (Taildragger only)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_wheel(cq_mod: type, diameter: float) -> "cq.Workplane | None":
    """Build a torus-shaped wheel using revolve.

    Uses revolve of a circular profile about an offset axis — this is more
    reliable than cq.Workplane.torus() across CadQuery versions.

    The wheel axis is +Y (spanwise), so it rolls along the fuselage X axis.
    Major radius = diameter/2, minor radius (tire cross-section) = width/2
    where width = min(diameter * 0.25, 10 mm).

    Returns None if CadQuery operation fails.
    """
    cq = cq_mod
    try:
        major_r = diameter / 2.0
        width = min(diameter * 0.25, 10.0)
        minor_r = width / 2.0

        # Build torus: revolve a circle (in XZ plane, offset from Y axis by major_r)
        # around the Y axis.  The resulting torus has its rolling axis along Y.
        wheel = (
            cq.Workplane("XZ")
            .transformed(offset=(major_r, 0, 0))
            .circle(minor_r)
            .revolve(360, (0, 0, 0), (0, 1, 0))
        )
        return wheel
    except Exception:
        # Fallback: simple cylinder as a degenerate wheel shape
        try:
            width = min(diameter * 0.25, 10.0)
            wheel = (
                cq.Workplane("XZ")
                .circle(diameter / 2.0)
                .extrude(width)
                .translate((0, -width / 2.0, 0))
            )
            return wheel
        except Exception:
            return None


def _build_strut(
    cq_mod: type,
    height: float,
    track_half: float,
    y_sign: float,
) -> "cq.Workplane | None":
    """Build one main gear strut (left or right).

    The strut runs from the fuselage bottom mount point (origin of local frame)
    diagonally DOWN and outward to the axle center at:
      (0, y_sign * track_half, -height)  in the local/aircraft frame.

    Strut cross-section: 4mm wide (X-axis, chordwise) × 2mm thick (Y-axis, spanwise).
    The strut length is the hypotenuse sqrt(track_half^2 + height^2).

    Construction approach:
    1. Extrude the cross-section downward (-Z direction) to produce a downward strut.
    2. Rotate around the X-axis to tilt the strut tip outward (±Y direction).

    Rotation derivation:
    - Start direction: (0, 0, -1) — extrude downward along -Z.
    - After Rx(θ): (0, sin(θ), -cos(θ)).
    - For right gear (y_sign=+1): tip at (0, +sin(tilt), -cos(tilt)) → θ = +tilt_angle.
    - For left gear  (y_sign=-1): tip at (0, -sin(tilt), -cos(tilt)) → θ = -tilt_angle.
    - So rotation angle = y_sign * tilt_angle around X axis.

    Returns None if CadQuery operation fails.
    """
    cq = cq_mod
    try:
        strut_width = 4.0   # chordwise (X)
        strut_thick = 2.0   # spanwise (Y)
        strut_length = math.sqrt(track_half ** 2 + height ** 2)
        # Outward tilt angle from vertical (-Z axis)
        tilt_angle = math.degrees(math.atan2(track_half, height))

        # Build strut: extrude downward (-Z direction) by strut_length.
        # The solid occupies z=0 (top/mount end) to z=-strut_length (bottom/axle end).
        strut = (
            cq.Workplane("XY")
            .rect(strut_width, strut_thick)
            .extrude(-strut_length)  # negative = downward (-Z)
        )

        # Rotate to tilt outward in ±Y direction.
        # Rx(y_sign * tilt_angle): (0,0,-1) → (0, ±sin(tilt), -cos(tilt))
        # This tips the strut bottom toward (0, ±track_half, -height).
        strut = strut.rotate((0, 0, 0), (1, 0, 0), y_sign * tilt_angle)

        return strut
    except Exception:
        return None


def _build_nose_strut(
    cq_mod: type,
    height: float,
) -> "cq.Workplane | None":
    """Build the nose gear strut (vertical, no outward tilt).

    The nose strut is a simple vertical rectangular extrusion downward.
    4mm × 2mm cross-section, extrudes straight down (-Z) by `height`.
    Top face at Z=0 (fuselage bottom), bottom face at Z=-height.

    Returns None if CadQuery operation fails.
    """
    cq = cq_mod
    try:
        strut_width = 4.0
        strut_thick = 2.0
        strut = (
            cq.Workplane("XY")
            .rect(strut_width, strut_thick)
            .extrude(-height)  # negative = downward (-Z)
        )
        return strut
    except Exception:
        return None


def _assemble_main_gear_unit(
    cq_mod: type,
    strut: "cq.Workplane",
    wheel: "cq.Workplane",
    height: float,
    track_half: float,
    y_sign: float,
) -> "cq.Workplane | None":
    """Translate strut and wheel to final positions and union them.

    After the strut is built (extrude -Z) and rotated:
    - Strut mount end is at approximately (0, 0, 0).
    - Strut axle end is at approximately (0, y_sign*track_half, -height).

    The wheel was built in the XZ plane, centered at (major_r, 0, 0) before revolve,
    so after revolve it is centered at the origin with its rolling axis = Y.
    We translate the wheel to the axle center (0, y_sign*track_half, -height).

    Returns None if union fails.
    """
    cq = cq_mod
    try:
        # Translate wheel to axle center.
        # Axle center after strut rotation: (0, y_sign*track_half, -height).
        wheel_positioned = wheel.translate((0.0, y_sign * track_half, -height))

        # Union strut (already rotated) + positioned wheel.
        gear_unit = strut.union(wheel_positioned)
        return gear_unit
    except Exception:
        # If union fails, return the strut alone (still useful for visualization)
        try:
            return strut
        except Exception:
            return None


def _assemble_nose_gear_unit(
    cq_mod: type,
    strut: "cq.Workplane",
    wheel: "cq.Workplane",
    height: float,
) -> "cq.Workplane | None":
    """Assemble nose gear strut + wheel.

    Nose gear is centered on Y=0 (aircraft centerline).
    Wheel center at (0, 0, -height).
    """
    cq = cq_mod
    try:
        wheel_positioned = wheel.translate((0.0, 0.0, -height))
        gear_unit = strut.union(wheel_positioned)
        return gear_unit
    except Exception:
        try:
            return strut
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_landing_gear(
    design: AircraftDesign,
) -> "dict[str, cq.Workplane | None]":
    """Generate landing gear geometry.

    Returns a dict of named CadQuery components. Returns empty dict when
    landing_gear_type == 'None' (default) — zero behavior change for existing designs.

    Keys returned:
      'gear_main_left'  — left main strut + wheel (Tricycle + Taildragger)
      'gear_main_right' — right main strut + wheel (Tricycle + Taildragger)
      'gear_nose'       — nose gear (Tricycle only)
      'gear_tail'       — tail wheel (Taildragger only)

    All positions are in the aircraft coordinate frame (origin at nose, +X aft, +Z up).
    Landing gear components are NOT unioned with the fuselage — they are separate
    components for independent tessellation and viewport selection.

    All CadQuery operations are wrapped in try/except: failed ops return None
    (graceful degradation, never raises).
    """
    if design.landing_gear_type == "None":
        return {}

    try:
        import cadquery as cq  # noqa: F811
    except ImportError:
        return {}

    components: dict[str, "cq.Workplane | None"] = {}

    # Shared geometry parameters
    height = design.main_gear_height
    track_half = design.main_gear_track / 2.0
    main_wheel_dia = design.main_wheel_diameter
    fuse_len = design.fuselage_length

    # X position of main gear axle (aft of nose)
    main_gear_x = fuse_len * (design.main_gear_position / 100.0)

    # ── Main Gear Left ─────────────────────────────────────────────────
    left_strut = _build_strut(cq, height, track_half, y_sign=-1.0)
    left_wheel = _build_wheel(cq, main_wheel_dia)

    if left_strut is not None and left_wheel is not None:
        left_unit = _assemble_main_gear_unit(
            cq, left_strut, left_wheel, height, track_half, y_sign=-1.0
        )
    elif left_strut is not None:
        left_unit = left_strut
    else:
        left_unit = None

    if left_unit is not None:
        try:
            components["gear_main_left"] = left_unit.translate((main_gear_x, 0.0, 0.0))
        except Exception:
            components["gear_main_left"] = left_unit
    else:
        components["gear_main_left"] = None

    # ── Main Gear Right (mirror of left: y_sign = +1) ──────────────────
    right_strut = _build_strut(cq, height, track_half, y_sign=+1.0)
    right_wheel = _build_wheel(cq, main_wheel_dia)

    if right_strut is not None and right_wheel is not None:
        right_unit = _assemble_main_gear_unit(
            cq, right_strut, right_wheel, height, track_half, y_sign=+1.0
        )
    elif right_strut is not None:
        right_unit = right_strut
    else:
        right_unit = None

    if right_unit is not None:
        try:
            components["gear_main_right"] = right_unit.translate((main_gear_x, 0.0, 0.0))
        except Exception:
            components["gear_main_right"] = right_unit
    else:
        components["gear_main_right"] = None

    # ── Nose Gear (Tricycle only) ───────────────────────────────────────
    if design.landing_gear_type == "Tricycle":
        nose_height = design.nose_gear_height
        nose_wheel_dia = design.nose_wheel_diameter

        # Nose gear X position: approximately 15% of fuselage from nose
        nose_gear_x = fuse_len * 0.15

        nose_strut = _build_nose_strut(cq, nose_height)
        nose_wheel = _build_wheel(cq, nose_wheel_dia)

        if nose_strut is not None and nose_wheel is not None:
            nose_unit = _assemble_nose_gear_unit(cq, nose_strut, nose_wheel, nose_height)
        elif nose_strut is not None:
            nose_unit = nose_strut
        else:
            nose_unit = None

        if nose_unit is not None:
            try:
                components["gear_nose"] = nose_unit.translate((nose_gear_x, 0.0, 0.0))
            except Exception:
                components["gear_nose"] = nose_unit
        else:
            components["gear_nose"] = None

    # ── Tail Wheel (Taildragger only) ───────────────────────────────────
    if design.landing_gear_type == "Taildragger":
        tail_wheel_dia = design.tail_wheel_diameter
        tail_gear_x = fuse_len * (design.tail_gear_position / 100.0)

        # Tail wheel rests on the ground; no separate height param.
        # The wheel center is at Z = -tail_wheel_dia/2 (sitting on ground plane Z=0).
        tail_wheel = _build_wheel(cq, tail_wheel_dia)

        if tail_wheel is not None:
            try:
                # Position: at tail gear X, centered on Y=0, wheel bottom touches ground
                tail_wheel_positioned = tail_wheel.translate(
                    (tail_gear_x, 0.0, -(tail_wheel_dia / 2.0))
                )
                components["gear_tail"] = tail_wheel_positioned
            except Exception:
                components["gear_tail"] = tail_wheel
        else:
            components["gear_tail"] = None

    return components
