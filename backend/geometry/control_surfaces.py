"""Control surface geometry — boolean-subtraction cuts for ailerons, elevator,
rudder, ruddervators, and elevons.

Architecture (from v0.7_aero_guidance.md §2.1):
  1. Build the parent solid (wing or tail) as normal.
  2. Compute the hinge line in 3D space.
  3. Build a "cutter" solid — a box along the hinge line that captures the
     control surface volume plus the 0.5 mm per-side hinge gap.
  4. parent.cut(cutter) → fixed surface (stays attached to aircraft).
  5. Build the control surface solid directly from a separate geometry.
  6. Return both as separate cq.Workplane objects.

Never boolean-union control surfaces with the parent — they are separate STL
parts assembled onto the aircraft via piano-wire hinge pins.

ALL boolean cuts are wrapped in try/except.  If CadQuery fails, the original
solid is returned unchanged and the control surface solid is None.

Hinge gap: 0.5 mm per side (1.0 mm total) — allows free rotation after FDM
printing without binding.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import cadquery as cq

from backend.models import AircraftDesign

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HINGE_GAP = 0.5  # mm per side
PIN_HOLE_DIAMETER_FALLBACK = 1.5  # mm — used when model doesn't expose pin param
PIN_POSITIONS = [0.2, 0.5, 0.8]  # fraction of control surface span

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def cut_aileron(
    wing_solid: "cq.Workplane",
    design: AircraftDesign,
    side: str,
) -> tuple["cq.Workplane", "cq.Workplane | None"]:
    """Cut aileron from one wing half.

    Args:
        wing_solid: The wing half CadQuery solid (already in final position).
        design:     Aircraft design parameters.
        side:       "left" or "right" — determines Y sign.

    Returns:
        (wing_body, aileron) — wing_body has aileron removed; aileron is the
        separate control surface.  If CadQuery cut fails, returns
        (original_solid, None).
    """
    import cadquery as cq  # noqa: F811

    if not design.aileron_enable:
        return wing_solid, None

    try:
        root_chord = design.wing_chord
        tip_chord = root_chord * design.wing_tip_root_ratio
        half_span = design.wing_span / 2.0
        y_sign = -1.0 if side == "left" else 1.0

        aileron_chord_frac = design.aileron_chord_percent / 100.0
        y_inboard = (design.aileron_span_start / 100.0) * half_span
        y_outboard = (design.aileron_span_end / 100.0) * half_span
        aileron_span = y_outboard - y_inboard

        if aileron_span <= 0:
            logger.warning("Aileron span is zero or negative — skipping cut.")
            return wing_solid, None

        # Chord at midspan (for cutter sizing)
        y_mid_frac = ((y_inboard + y_outboard) / 2.0) / half_span
        chord_at_mid = root_chord + (tip_chord - root_chord) * y_mid_frac

        # Hinge line X position: from LE, distance = chord*(1-aileron_frac)
        # The cutter includes the gap, so it starts at x_hinge - HINGE_GAP
        x_hinge_mid = chord_at_mid * (1.0 - aileron_chord_frac)
        cutter_chord = chord_at_mid * aileron_chord_frac + HINGE_GAP

        # Wing max thickness ≈ 12% of mean chord for Z sizing
        mean_chord = (root_chord + tip_chord) / 2.0
        wing_max_thickness = mean_chord * 0.12 * 3.0  # 3x over-size for clean cut

        # Cutter center in aircraft coordinates.
        # Y center is at (y_inboard + y_outboard)/2 * y_sign (spanwise).
        cutter_x_center = x_hinge_mid + (cutter_chord / 2.0) - HINGE_GAP
        cutter_y_center = y_sign * (y_inboard + y_outboard) / 2.0

        cutter = (
            cq.Workplane("XY")
            .transformed(offset=(cutter_x_center, cutter_y_center, 0.0))
            .box(cutter_chord, aileron_span, wing_max_thickness)
        )

        # Cut aileron from wing body
        wing_body = wing_solid.cut(cutter)

        # Build aileron solid: same cutter volume minus the gap
        # Aileron starts at x_hinge + HINGE_GAP (forward of hinge gap)
        ail_chord = chord_at_mid * aileron_chord_frac - HINGE_GAP
        if ail_chord <= 0:
            ail_chord = chord_at_mid * aileron_chord_frac

        ail_x_center = x_hinge_mid + HINGE_GAP + (ail_chord / 2.0)

        aileron_solid = (
            cq.Workplane("XY")
            .transformed(offset=(ail_x_center, cutter_y_center, 0.0))
            .box(ail_chord, aileron_span - HINGE_GAP * 2, wing_max_thickness)
        )
        # Intersect with original wing solid to get proper airfoil cross-section
        aileron_solid = aileron_solid.intersect(wing_solid)

        # Add hinge pin holes through aileron
        aileron_solid = _add_hinge_pin_holes(
            cq, aileron_solid,
            x_pin=x_hinge_mid + HINGE_GAP,
            y_inboard=y_sign * y_inboard,
            y_outboard=y_sign * y_outboard,
            span_axis="Y",
            thickness=wing_max_thickness,
            y_sign=y_sign,
            design=design,
        )

        return wing_body, aileron_solid

    except Exception as exc:
        logger.warning("Aileron cut failed (%s %s): %s — returning original solid.", side, "aileron", exc)
        return wing_solid, None


def cut_elevator(
    h_stab_solid: "cq.Workplane",
    design: AircraftDesign,
    side: str,
) -> tuple["cq.Workplane", "cq.Workplane | None"]:
    """Cut elevator from one h-stab half.

    Args:
        h_stab_solid: The h-stab half CadQuery solid (in final position).
        design:       Aircraft design parameters.
        side:         "left" or "right".

    Returns:
        (h_stab_body, elevator) or (original_solid, None) on failure.
    """
    import cadquery as cq  # noqa: F811

    if not design.elevator_enable:
        return h_stab_solid, None

    try:
        h_stab_chord = design.h_stab_chord
        elevator_chord_frac = design.elevator_chord_percent / 100.0
        x_hinge = h_stab_chord * (1.0 - elevator_chord_frac)

        half_h_stab = design.h_stab_span / 2.0
        y_elev = (design.elevator_span_percent / 100.0) * half_h_stab
        y_sign = -1.0 if side == "left" else 1.0

        # H-stab thickness ≈ 12% of chord * 3 for oversized cutter
        h_stab_thickness = h_stab_chord * 0.12 * 3.0
        elevator_span = y_elev

        cutter_chord = h_stab_chord * elevator_chord_frac + HINGE_GAP
        cutter_x_center = x_hinge + (cutter_chord / 2.0) - HINGE_GAP
        cutter_y_center = y_sign * elevator_span / 2.0

        cutter = (
            cq.Workplane("XY")
            .transformed(offset=(cutter_x_center, cutter_y_center, 0.0))
            .box(cutter_chord, elevator_span, h_stab_thickness)
        )

        h_stab_body = h_stab_solid.cut(cutter)

        # Build elevator
        elev_chord = h_stab_chord * elevator_chord_frac - HINGE_GAP
        if elev_chord <= 0:
            elev_chord = h_stab_chord * elevator_chord_frac

        elev_x_center = x_hinge + HINGE_GAP + (elev_chord / 2.0)

        elevator_solid = (
            cq.Workplane("XY")
            .transformed(offset=(elev_x_center, cutter_y_center, 0.0))
            .box(elev_chord, elevator_span - HINGE_GAP * 2, h_stab_thickness)
        )
        elevator_solid = elevator_solid.intersect(h_stab_solid)

        return h_stab_body, elevator_solid

    except Exception as exc:
        logger.warning("Elevator cut failed (%s): %s — returning original solid.", side, exc)
        return h_stab_solid, None


def cut_rudder(
    v_stab_solid: "cq.Workplane",
    design: AircraftDesign,
) -> tuple["cq.Workplane", "cq.Workplane | None"]:
    """Cut rudder from vertical stabilizer.

    The v-stab extends vertically in +Z.  The rudder cut removes the aft
    portion of the fin from z_rudder_start to v_stab_height.

    Returns:
        (v_stab_body, rudder) or (original_solid, None) on failure.
    """
    import cadquery as cq  # noqa: F811

    if not design.rudder_enable:
        return v_stab_solid, None

    try:
        v_stab_root_chord = design.v_stab_root_chord
        tip_chord_v = v_stab_root_chord * 0.6  # 60% taper (matches tail.py)
        rudder_chord_frac = design.rudder_chord_percent / 100.0
        v_stab_height = design.v_stab_height

        z_rudder_start = v_stab_height * (1.0 - design.rudder_height_percent / 100.0)
        rudder_height = v_stab_height - z_rudder_start

        # Average chord over rudder height
        z_mid = z_rudder_start + rudder_height / 2.0
        chord_at_z_mid = v_stab_root_chord + (tip_chord_v - v_stab_root_chord) * (z_mid / v_stab_height)
        x_hinge_mid = chord_at_z_mid * (1.0 - rudder_chord_frac)

        v_stab_thickness = chord_at_z_mid * 0.12 * 3.0

        cutter_chord = chord_at_z_mid * rudder_chord_frac + HINGE_GAP
        cutter_x_center = x_hinge_mid + (cutter_chord / 2.0) - HINGE_GAP

        # V-stab is in XY plane (Z vertical), cutter extends through Z
        cutter = (
            cq.Workplane("XZ")
            .transformed(offset=(cutter_x_center, z_rudder_start + rudder_height / 2.0, 0.0))
            .box(cutter_chord, rudder_height, v_stab_thickness)
        )

        v_stab_body = v_stab_solid.cut(cutter)

        # Build rudder solid
        rud_chord = chord_at_z_mid * rudder_chord_frac - HINGE_GAP
        if rud_chord <= 0:
            rud_chord = chord_at_z_mid * rudder_chord_frac

        rud_x_center = x_hinge_mid + HINGE_GAP + (rud_chord / 2.0)

        rudder_solid = (
            cq.Workplane("XZ")
            .transformed(offset=(rud_x_center, z_rudder_start + rudder_height / 2.0, 0.0))
            .box(rud_chord, rudder_height - HINGE_GAP * 2, v_stab_thickness)
        )
        rudder_solid = rudder_solid.intersect(v_stab_solid)

        return v_stab_body, rudder_solid

    except Exception as exc:
        logger.warning("Rudder cut failed: %s — returning original solid.", exc)
        return v_stab_solid, None


def cut_ruddervators(
    v_tail_left: "cq.Workplane",
    v_tail_right: "cq.Workplane",
    design: AircraftDesign,
) -> tuple[
    "cq.Workplane",
    "cq.Workplane",
    "cq.Workplane | None",
    "cq.Workplane | None",
]:
    """Cut ruddervators from V-tail surfaces.

    Per aero guidance §2.6: build in flat frame (before dihedral rotation),
    cut there, then rotate both parent and control surface together.

    Since the V-tail solids passed in are already rotated (from tail.py),
    we use the same box-intersect approach used for ailerons/elevator, treating
    the V-tail surface as if it were a horizontal/flat surface in its local
    coordinate system.

    Args:
        v_tail_left:  Left V-tail solid (already positioned/rotated).
        v_tail_right: Right V-tail solid.
        design:       Aircraft design.

    Returns:
        (v_tail_left_body, v_tail_right_body, ruddervator_left, ruddervator_right)
        On failure, returns original solids with None control surfaces.
    """
    import cadquery as cq  # noqa: F811

    if not design.ruddervator_enable:
        return v_tail_left, v_tail_right, None, None

    rvv_left, rudv_left = _cut_single_ruddervator(cq, v_tail_left, design, side="left")
    rvv_right, rudv_right = _cut_single_ruddervator(cq, v_tail_right, design, side="right")

    return rvv_left, rvv_right, rudv_left, rudv_right


def cut_elevons(
    wing_solid: "cq.Workplane",
    design: AircraftDesign,
    side: str,
) -> tuple["cq.Workplane", "cq.Workplane | None"]:
    """Cut elevon from flying-wing half.

    Elevons are structurally identical to ailerons — a spanwise plain-flap
    cut from the wing.  The key difference is that elevons serve both aileron
    and elevator function (handled by radio mixing, not geometry).

    Args:
        wing_solid: Wing half CadQuery solid.
        design:     Aircraft design parameters.
        side:       "left" or "right".

    Returns:
        (wing_body, elevon) or (original_solid, None) on failure.
    """
    import cadquery as cq  # noqa: F811

    if not design.elevon_enable:
        return wing_solid, None

    try:
        root_chord = design.wing_chord
        tip_chord = root_chord * design.wing_tip_root_ratio
        half_span = design.wing_span / 2.0
        y_sign = -1.0 if side == "left" else 1.0

        elevon_chord_frac = design.elevon_chord_percent / 100.0
        y_inboard = (design.elevon_span_start / 100.0) * half_span
        y_outboard = (design.elevon_span_end / 100.0) * half_span
        elevon_span = y_outboard - y_inboard

        if elevon_span <= 0:
            logger.warning("Elevon span is zero or negative — skipping cut.")
            return wing_solid, None

        y_mid_frac = ((y_inboard + y_outboard) / 2.0) / half_span
        chord_at_mid = root_chord + (tip_chord - root_chord) * y_mid_frac
        x_hinge_mid = chord_at_mid * (1.0 - elevon_chord_frac)
        cutter_chord = chord_at_mid * elevon_chord_frac + HINGE_GAP
        mean_chord = (root_chord + tip_chord) / 2.0
        wing_max_thickness = mean_chord * 0.12 * 3.0

        cutter_x_center = x_hinge_mid + (cutter_chord / 2.0) - HINGE_GAP
        cutter_y_center = y_sign * (y_inboard + y_outboard) / 2.0

        cutter = (
            cq.Workplane("XY")
            .transformed(offset=(cutter_x_center, cutter_y_center, 0.0))
            .box(cutter_chord, elevon_span, wing_max_thickness)
        )

        wing_body = wing_solid.cut(cutter)

        elev_chord = chord_at_mid * elevon_chord_frac - HINGE_GAP
        if elev_chord <= 0:
            elev_chord = chord_at_mid * elevon_chord_frac

        elev_x_center = x_hinge_mid + HINGE_GAP + (elev_chord / 2.0)

        elevon_solid = (
            cq.Workplane("XY")
            .transformed(offset=(elev_x_center, cutter_y_center, 0.0))
            .box(elev_chord, elevon_span - HINGE_GAP * 2, wing_max_thickness)
        )
        elevon_solid = elevon_solid.intersect(wing_solid)

        return wing_body, elevon_solid

    except Exception as exc:
        logger.warning("Elevon cut failed (%s): %s — returning original solid.", side, exc)
        return wing_solid, None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cut_single_ruddervator(
    cq_mod: type,
    v_tail_solid: "cq.Workplane",
    design: AircraftDesign,
    side: str,
) -> tuple["cq.Workplane", "cq.Workplane | None"]:
    """Cut ruddervator from a single V-tail surface."""
    import cadquery as cq  # noqa: F811

    try:
        v_tail_chord = design.v_tail_chord
        half_span = design.v_tail_span / 2.0
        rudv_chord_frac = design.ruddervator_chord_percent / 100.0
        y_sign = -1.0 if side == "left" else 1.0
        dihedral_rad = math.radians(design.v_tail_dihedral)

        # Ruddervator spans from inboard to tip of V-tail surface
        y_inboard = half_span * (1.0 - design.ruddervator_span_percent / 100.0)
        y_outboard = half_span
        rudv_span = y_outboard - y_inboard

        if rudv_span <= 0:
            return v_tail_solid, None

        x_hinge = v_tail_chord * (1.0 - rudv_chord_frac)
        v_tail_thickness = v_tail_chord * 0.09 * 3.0

        cutter_chord = v_tail_chord * rudv_chord_frac + HINGE_GAP
        cutter_x_center = x_hinge + (cutter_chord / 2.0) - HINGE_GAP

        # For V-tail: spanwise axis is tilted. Use cutter in local XY frame
        # (before dihedral).  Project midpoint to 3D Y/Z position.
        y_mid_local = (y_inboard + y_outboard) / 2.0
        y_3d = y_sign * y_mid_local * math.cos(dihedral_rad)
        z_3d = y_mid_local * math.sin(dihedral_rad)

        # Spanwise extent in 3D
        rudv_span_y = rudv_span * math.cos(dihedral_rad)
        rudv_span_z = rudv_span * math.sin(dihedral_rad)
        # Use a box along the spanwise projection
        rudv_span_3d = math.sqrt(rudv_span_y**2 + rudv_span_z**2)

        cutter = (
            cq.Workplane("XY")
            .transformed(offset=(cutter_x_center, y_3d, z_3d))
            .box(cutter_chord, rudv_span_y + HINGE_GAP, v_tail_thickness)
        )

        v_tail_body = v_tail_solid.cut(cutter)

        rud_chord = v_tail_chord * rudv_chord_frac - HINGE_GAP
        if rud_chord <= 0:
            rud_chord = v_tail_chord * rudv_chord_frac

        rud_x_center = x_hinge + HINGE_GAP + (rud_chord / 2.0)

        rudv_solid = (
            cq.Workplane("XY")
            .transformed(offset=(rud_x_center, y_3d, z_3d))
            .box(rud_chord, rudv_span_y - HINGE_GAP * 2, v_tail_thickness)
        )
        rudv_solid = rudv_solid.intersect(v_tail_solid)

        return v_tail_body, rudv_solid

    except Exception as exc:
        logger.warning(
            "Ruddervator cut failed (%s): %s — returning original solid.", side, exc
        )
        return v_tail_solid, None


def _add_hinge_pin_holes(
    cq_mod: type,
    solid: "cq.Workplane",
    x_pin: float,
    y_inboard: float,
    y_outboard: float,
    span_axis: str,
    thickness: float,
    y_sign: float,
    design: AircraftDesign,
) -> "cq.Workplane":
    """Add hinge pin holes (cylinders along Z through control surface).

    3 holes evenly spaced at 20%, 50%, 80% of the control surface span.
    Hole diameter = hinge_pin_diameter + 2 * joint_tolerance.

    Returns the solid with holes cut, or the original solid if any cut fails.
    """
    import cadquery as cq  # noqa: F811

    pin_diameter = PIN_HOLE_DIAMETER_FALLBACK + 2.0 * design.joint_tolerance
    pin_radius = pin_diameter / 2.0

    try:
        result = solid
        for frac in PIN_POSITIONS:
            # Interpolate along control surface span
            y_pin = y_inboard + frac * (y_outboard - y_inboard)
            pin_hole = (
                cq.Workplane("XY")
                .transformed(offset=(x_pin, y_pin, 0.0))
                .circle(pin_radius)
                .extrude(thickness * 2, both=True)
            )
            try:
                result = result.cut(pin_hole)
            except Exception:
                pass  # Individual pin hole failure is non-fatal

        return result

    except Exception as exc:
        logger.warning("Hinge pin holes failed: %s — returning solid without holes.", exc)
        return solid
