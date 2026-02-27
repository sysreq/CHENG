"""
backend/mass_properties.py

Mass properties module for CHENG dynamic stability analysis.

Provides:
- MassProperties dataclass: resolved mass, CG position, and moments of inertia
- estimate_inertia(): component build-up inertia estimation
- resolve_mass_properties(): applies MP01-MP07 overrides or falls back to estimates

All internal computation is in SI units (kg, m, kg·m²).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from backend.models import AircraftDesign, DerivedValues


# ---------------------------------------------------------------------------
# MassProperties dataclass
# ---------------------------------------------------------------------------

@dataclass
class MassProperties:
    """Resolved mass properties for an aircraft design.

    Overridden fields (from MP01-MP07) are used directly.
    Non-overridden fields are estimated via the component build-up method.

    All positions in mm (matching CHENG coordinate system).
    All inertias in kg·m² (SI).
    """

    mass_g: float
    """Total aircraft mass in grams."""

    cg_x_mm: float
    """CG longitudinal position from nose (mm)."""

    cg_z_mm: float
    """CG vertical offset (mm, positive = up from wing plane)."""

    cg_y_mm: float
    """CG lateral offset (mm, positive = starboard). Nominally 0 for symmetric designs."""

    ixx_kg_m2: float
    """Roll moment of inertia about body X-axis (kg·m²)."""

    iyy_kg_m2: float
    """Pitch moment of inertia about body Y-axis (kg·m²). Typically > Ixx."""

    izz_kg_m2: float
    """Yaw moment of inertia about body Z-axis (kg·m²). Typically largest."""

    ixx_estimated: bool
    """True when Ixx is a geometric estimate; False when MP05 override is active."""

    iyy_estimated: bool
    """True when Iyy is a geometric estimate; False when MP06 override is active."""

    izz_estimated: bool
    """True when Izz is a geometric estimate; False when MP07 override is active."""


# ---------------------------------------------------------------------------
# Component build-up inertia estimation
# ---------------------------------------------------------------------------

def _get(derived: "Union[DerivedValues, dict]", key: str, default: float = 0.0) -> float:
    """Get a value from a DerivedValues object or dict."""
    if isinstance(derived, dict):
        return float(derived.get(key, default))
    return float(getattr(derived, key, default))


def estimate_inertia(
    design: "AircraftDesign",
    derived: "Union[DerivedValues, dict]",
) -> tuple[float, float, float]:
    """Estimate moments of inertia via a component build-up method.

    Uses simplified geometric shapes for each major component:
    - Wing: thin uniform plate (each half, reflected)
    - Fuselage: solid cylinder approximation
    - Tail: thin uniform plate at distance l_t from CG
    - Motor: point mass at nose

    Args:
        design: Aircraft design parameters.
        derived: Backend-computed derived values (used for weight estimates).

    Returns:
        (Ixx, Iyy, Izz) moments of inertia in kg·m².

    Physical constraints satisfied:
        - Ixx < Iyy < Izz for conventional layouts (roll < pitch < yaw)
        - All values positive
    """
    # ── Component masses (SI) ──────────────────────────────────────────────
    # Use derived.weight_* for geometry-based estimates.
    m_wing_kg = _get(derived, "weight_wing_g") / 1000.0
    m_tail_kg = _get(derived, "weight_tail_g") / 1000.0
    m_fus_kg = _get(derived, "weight_fuselage_g") / 1000.0
    m_motor_kg = design.motor_weight_g / 1000.0
    m_battery_kg = design.battery_weight_g / 1000.0

    # Total for distribution of electronics.
    # weight_total_g (airframe geometry) + motor + battery = full aircraft mass.
    # Subtract all known structural/propulsion components to get residual
    # electronics (servos, ESC, receiver, wiring).
    m_total_kg = (_get(derived, "weight_total_g") + design.motor_weight_g + design.battery_weight_g) / 1000.0
    m_avionics_kg = max(0.0, m_total_kg - m_wing_kg - m_tail_kg - m_fus_kg
                        - m_motor_kg - m_battery_kg)

    # ── Key geometric dimensions (SI, metres) ─────────────────────────────
    b_m = design.wing_span / 1000.0          # Full span [m]
    b_half_m = b_m / 2.0                     # Semi-span [m]
    c_m = design.wing_chord / 1000.0         # Root chord [m]
    L_m = design.fuselage_length / 1000.0    # Fuselage length [m]
    l_t_m = design.tail_arm / 1000.0         # Tail moment arm [m]

    # Fuselage cross-section radius estimate
    if design.fuselage_preset == "Pod":
        r_fus_m = (design.wing_chord * 0.45) / 2000.0
    elif design.fuselage_preset == "Blended-Wing-Body":
        r_fus_m = (design.wing_chord * 0.35) / 2000.0
    else:  # Conventional
        r_fus_m = (design.wing_chord * 0.35) / 2000.0

    # Motor position from nose (respects tractor vs. pusher configuration).
    # Tractor: motor at ~5% of fuselage length (nose).
    # Pusher:  motor at ~95% of fuselage length (tail).
    if getattr(design, "motor_config", "Tractor") == "Pusher":
        x_motor_m = L_m * 0.95
    else:
        x_motor_m = L_m * 0.05

    # Battery position from nose
    x_battery_m = L_m * design.battery_position_frac

    # CG position from nose — used to compute motor/battery moment arms.
    # NOTE: derived["estimated_cg_mm"] is wing-LE-referenced (see engine._compute_cg
    # docstring: "CG distance aft of wing root LE").  We cannot convert it to
    # nose-referenced here without knowing wing_x.  Use a fixed-fraction estimate
    # of 30% fuselage length, which matches the engine fallback and gives
    # physically plausible arm lengths for inertia estimation purposes.
    cg_x_m = L_m * 0.30

    # ── Wing contribution ─────────────────────────────────────────────────
    # Model each half as a slender rod with distributed mass along the span.
    # For a uniform rod of mass m and length L: I_end = (1/3)*m*L²
    # For span axis: I_xx ~ sum of thin disk slices

    # Roll (Ixx): wing mass distributed along span
    # Both halves: I_roll = 2 * (1/3) * (m_wing/2) * b_half² = (1/3)*m_wing*b_half²
    I_wing_roll = (1.0 / 3.0) * m_wing_kg * b_half_m ** 2

    # Pitch (Iyy): wing mass distributed along chord direction
    # Model as thin plate: I_pitch = (1/12)*m*c²
    I_wing_pitch = (1.0 / 12.0) * m_wing_kg * c_m ** 2

    # Yaw (Izz): perpendicular to wing plane (combines span and chord contributions)
    I_wing_yaw = I_wing_roll + I_wing_pitch

    # ── Fuselage contribution ─────────────────────────────────────────────
    # Solid cylinder approximation: mass m, length L, radius r
    # I_roll (about long axis) = (1/2) * m * r²
    # I_pitch (about lateral axis) = (1/12) * m * (L² + 3r²)
    # Note: for a fuselage, the long axis is X, lateral is Y
    I_fus_roll = 0.5 * m_fus_kg * r_fus_m ** 2  # Ixx for fuselage
    I_fus_pitch = (1.0 / 12.0) * m_fus_kg * (L_m ** 2 + 3.0 * r_fus_m ** 2)  # Iyy

    # ── Tail contribution ─────────────────────────────────────────────────
    # Point mass at distance l_t from CG adds m*l_t² to Iyy and Izz
    # (the tail is behind the CG, contributes to pitch and yaw inertia)
    I_tail_pitch = m_tail_kg * l_t_m ** 2  # added to Iyy
    I_tail_yaw = m_tail_kg * l_t_m ** 2    # added to Izz

    # ── Motor contribution ────────────────────────────────────────────────
    # Point mass at x_motor_m from nose, at distance from nose-referenced CG
    x_motor_from_cg = abs(x_motor_m - cg_x_m)
    I_motor_pitch = m_motor_kg * x_motor_from_cg ** 2  # added to Iyy

    # ── Battery contribution ──────────────────────────────────────────────
    x_battery_from_cg = abs(x_battery_m - cg_x_m)
    I_battery_pitch = m_battery_kg * x_battery_from_cg ** 2

    # ── Avionics contribution ─────────────────────────────────────────────
    # Residual electronics (servos, ESC, receiver) are distributed inside the
    # fuselage near the CG.  Model as a fuselage-like cylinder of the same
    # cross-section so we reuse r_fus_m:
    #   Ixx_avionics ≈ (1/2) * m * r²   (compact roll inertia)
    #   Iyy_avionics ≈ (1/12) * m * (L² + 3r²)  (distributed along fuselage)
    I_avionics_roll = 0.5 * m_avionics_kg * r_fus_m ** 2
    I_avionics_pitch = (1.0 / 12.0) * m_avionics_kg * (L_m ** 2 + 3.0 * r_fus_m ** 2)

    # ── Assemble totals ───────────────────────────────────────────────────
    ixx = I_wing_roll + I_fus_roll + I_avionics_roll
    iyy = I_wing_pitch + I_fus_pitch + I_tail_pitch + I_motor_pitch + I_battery_pitch + I_avionics_pitch
    izz = I_wing_yaw + I_fus_pitch + I_tail_yaw + I_motor_pitch + I_battery_pitch + I_avionics_pitch

    # Ensure minimum plausible values and physical ordering constraint
    # (small floating point errors can break Ixx < Iyy < Izz in degenerate cases)
    ixx = max(ixx, 1e-6)
    iyy = max(iyy, ixx * 1.01)  # Iyy > Ixx for typical configs
    izz = max(izz, iyy * 1.01)  # Izz > Iyy for typical configs

    return ixx, iyy, izz


# ---------------------------------------------------------------------------
# Mass properties resolver (entry point)
# ---------------------------------------------------------------------------

def resolve_mass_properties(
    design: "AircraftDesign",
    derived: "Union[DerivedValues, dict]",
) -> MassProperties:
    """Resolve mass properties, applying MP01-MP07 overrides where set.

    Each override field is applied independently: if MP05 (Ixx override) is
    set but MP06 (Iyy) is not, Ixx uses the override and Iyy is estimated.

    Args:
        design: Aircraft design (may have mass property override fields set).
        derived: Computed derived values (provides weight and CG estimates).

    Returns:
        MassProperties with fully resolved values.
    """
    # ── Mass (MP01) ────────────────────────────────────────────────────────
    if design.mass_total_override_g is not None:
        mass_g = float(design.mass_total_override_g)
    else:
        # weight_total_g from derived covers airframe only (wing + tail + fuselage).
        # Motor and battery are separate design fields — add them for total aircraft mass.
        airframe_g = _get(derived, "weight_total_g")
        mass_g = airframe_g + design.motor_weight_g + design.battery_weight_g

    # ── CG position (MP02-MP04) ────────────────────────────────────────────
    if design.cg_override_x_mm is not None:
        cg_x_mm = float(design.cg_override_x_mm)
    else:
        # NOTE: derived["estimated_cg_mm"] is wing-LE-referenced (distance aft of
        # wing root LE), not nose-referenced.  MassProperties.cg_x_mm is defined
        # as nose-referenced.  We cannot convert without knowing wing_x here, so
        # use 30% of fuselage length from nose — consistent with the conventional
        # RC "balance at 25-30% MAC" rule and the engine's own fallback.
        cg_x_mm = design.fuselage_length * 0.30

    if design.cg_override_z_mm is not None:
        cg_z_mm = float(design.cg_override_z_mm)
    else:
        cg_z_mm = 0.0

    if design.cg_override_y_mm is not None:
        cg_y_mm = float(design.cg_override_y_mm)
    else:
        cg_y_mm = 0.0

    # ── Moments of inertia (MP05-MP07) ────────────────────────────────────
    # Always compute the estimate so we can fall back per-axis.
    ixx_est, iyy_est, izz_est = estimate_inertia(design, derived)

    if design.ixx_override_kg_m2 is not None:
        ixx = float(design.ixx_override_kg_m2)
        ixx_estimated = False
    else:
        ixx = ixx_est
        ixx_estimated = True

    if design.iyy_override_kg_m2 is not None:
        iyy = float(design.iyy_override_kg_m2)
        iyy_estimated = False
    else:
        iyy = iyy_est
        iyy_estimated = True

    if design.izz_override_kg_m2 is not None:
        izz = float(design.izz_override_kg_m2)
        izz_estimated = False
    else:
        izz = izz_est
        izz_estimated = True

    return MassProperties(
        mass_g=mass_g,
        cg_x_mm=cg_x_mm,
        cg_z_mm=cg_z_mm,
        cg_y_mm=cg_y_mm,
        ixx_kg_m2=ixx,
        iyy_kg_m2=iyy,
        izz_kg_m2=izz,
        ixx_estimated=ixx_estimated,
        iyy_estimated=iyy_estimated,
        izz_estimated=izz_estimated,
    )
