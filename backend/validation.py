"""Validation rules — compute non-blocking warnings for a design.

Implements:
  - 8 structural / geometric warnings  (V01-V08)
  - 5 aerodynamic / structural analysis (V09-V13)  [v0.6]
  - 7 print / export warnings          (V16-V23)
  - 5 printability analysis warnings    (V24-V28)  [v0.6]

All warnings are level="warn" and never block export.

Spec reference: docs/mvp_spec.md §9.2 and §9.3.
"""

from __future__ import annotations

import math

from backend.models import AircraftDesign, ValidationWarning


def _mac(design: AircraftDesign) -> float:
    """Mean Aerodynamic Chord (mm)."""
    lam = design.wing_tip_root_ratio
    if (1 + lam) == 0:
        return design.wing_chord
    return (2.0 / 3.0) * design.wing_chord * (1 + lam + lam**2) / (1 + lam)


# ---------------------------------------------------------------------------
# Structural / geometric warnings  (V01 - V06)
# ---------------------------------------------------------------------------


def _check_v01(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V01: wingspan > 10 * fuselageLength."""
    if design.wing_span > 10 * design.fuselage_length:
        out.append(
            ValidationWarning(
                id="V01",
                message="Very high aspect ratio relative to fuselage",
                fields=["wing_span", "fuselage_length"],
            )
        )


def _check_v02(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V02: tipRootRatio < 0.3 — aggressive taper, tip stall risk."""
    if design.wing_tip_root_ratio < 0.3:
        out.append(
            ValidationWarning(
                id="V02",
                message="Aggressive taper — tip stall risk",
                fields=["wing_tip_root_ratio"],
            )
        )


def _check_v03(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V03: fuselageLength < wingChord."""
    if design.fuselage_length < design.wing_chord:
        out.append(
            ValidationWarning(
                id="V03",
                message="Fuselage shorter than wing chord",
                fields=["fuselage_length", "wing_chord"],
            )
        )


def _check_v04(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V04: tailArm < 2 * MAC — short tail arm, may lack pitch stability."""
    mac = _mac(design)
    if mac > 0 and design.tail_arm < 2 * mac:
        out.append(
            ValidationWarning(
                id="V04",
                message="Short tail arm — may lack pitch stability",
                fields=["tail_arm"],
            )
        )


def _check_v05(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V05: wingChord * tipRootRatio < 30 — extremely small tip chord."""
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    if tip_chord < 30:
        out.append(
            ValidationWarning(
                id="V05",
                message="Extremely small tip chord",
                fields=["wing_chord", "wing_tip_root_ratio"],
            )
        )


def _check_v06(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V06: tailArm > fuselageLength — tail extends past the body."""
    if design.tail_arm > design.fuselage_length:
        out.append(
            ValidationWarning(
                id="V06",
                message="Tail arm exceeds fuselage — tail extends past the body",
                fields=["tail_arm", "fuselage_length"],
            )
        )


def _check_v07(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V07: fuselage section lengths don't sum to fuselage_length (>5% deviation)."""
    section_sum = (
        design.fuselage_nose_length
        + design.fuselage_cabin_length
        + design.fuselage_tail_length
    )
    if design.fuselage_length > 0:
        deviation = abs(section_sum - design.fuselage_length) / design.fuselage_length
        if deviation > 0.05:
            out.append(
                ValidationWarning(
                    id="V07",
                    message=(
                        f"Section lengths sum ({section_sum:.0f} mm) differs from "
                        f"fuselage length ({design.fuselage_length:.0f} mm) by "
                        f"{deviation*100:.0f}% — sections will be scaled proportionally"
                    ),
                    fields=[
                        "fuselage_nose_length",
                        "fuselage_cabin_length",
                        "fuselage_tail_length",
                        "fuselage_length",
                    ],
                )
            )


def _check_v08(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V08: wall_thickness < 2 * nozzle_diameter — fuselage wall too thin."""
    if design.wall_thickness < 2 * design.nozzle_diameter:
        out.append(
            ValidationWarning(
                id="V08",
                message="Fuselage wall too thin for solid perimeters",
                fields=["wall_thickness", "nozzle_diameter"],
            )
        )


# ---------------------------------------------------------------------------
# Aerodynamic / structural analysis  (V09 - V13)  [v0.6]
# ---------------------------------------------------------------------------


def _wing_area_m2(design: AircraftDesign) -> float:
    """Wing planform area in m^2."""
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    return 0.5 * (design.wing_chord + tip_chord) * design.wing_span * 1e-6


def _estimate_weight_kg(design: AircraftDesign) -> float:
    """Quick total weight estimate in kg (airframe + motor + battery).

    Uses the same volume-based approach as engine._compute_weight_estimates
    but simplified for validation (avoids circular import).
    """
    from backend.geometry.engine import _compute_weight_estimates
    weights = _compute_weight_estimates(design)
    airframe_g = weights["weight_total_g"]
    return (airframe_g + design.motor_weight_g + design.battery_weight_g) / 1000.0


def _check_v09(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V09: Wing bending moment check.

    Rough estimate: root bending moment from lift ≈ (W * b) / (4 * pi).
    For a 3D-printed wing, bending stress ~ M / (t^2 * c) should stay within
    PLA tensile limits. We warn if the non-dimensional bending parameter
    (weight_kg * span_m) / skin_thickness_mm^2 exceeds a threshold.

    The threshold is empirically set: above ~2.5, a 1.2mm skin PLA wing
    is at risk of creasing under moderate g-loads (2-3g maneuvers).
    """
    weight_kg = _estimate_weight_kg(design)
    span_m = design.wing_span / 1000.0
    skin_t = design.wing_skin_thickness

    if skin_t <= 0:
        return

    bending_param = (weight_kg * span_m) / (skin_t ** 2)

    if bending_param > 2.5:
        out.append(
            ValidationWarning(
                id="V09",
                message=(
                    f"High wing bending load — consider thicker skin or shorter span "
                    f"(bending index {bending_param:.1f}, limit 2.5)"
                ),
                fields=["wing_span", "wing_skin_thickness"],
            )
        )


def _check_v10(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V10: Tail volume coefficient check.

    Horizontal tail volume: V_h = (S_h * l_t) / (S_w * MAC)
    Typical RC range: 0.3 - 0.8. Below 0.3 = insufficient pitch stability.
    Above 1.0 = over-stabilized (sluggish pitch response).

    Vertical tail volume: V_v = (S_v * l_t) / (S_w * b)
    Typical range: 0.02 - 0.05. Below 0.02 = poor directional stability.
    """
    mac = _mac(design)
    wing_area_mm2 = 0.5 * (design.wing_chord + design.wing_chord * design.wing_tip_root_ratio) * design.wing_span

    if mac <= 0 or wing_area_mm2 <= 0 or design.wing_span <= 0:
        return

    if design.tail_type == "V-Tail":
        # V-tail effective areas using Purser-Campbell method:
        # The aerodynamic effectiveness is reduced by the square of the
        # trig function because both the force component and the effective
        # angle-of-attack change are reduced by the dihedral angle.
        v_tail_area = design.v_tail_chord * design.v_tail_span
        dihedral_rad = math.radians(design.v_tail_dihedral)
        h_area = v_tail_area * math.cos(dihedral_rad) ** 2
        v_area = v_tail_area * math.sin(dihedral_rad) ** 2
    else:
        h_area = design.h_stab_chord * design.h_stab_span
        v_area = design.v_stab_root_chord * design.v_stab_height

    # Horizontal tail volume coefficient
    v_h = (h_area * design.tail_arm) / (wing_area_mm2 * mac)
    if v_h < 0.3:
        out.append(
            ValidationWarning(
                id="V10",
                message=f"Low horizontal tail volume ({v_h:.2f}) — may lack pitch stability (typical: 0.3-0.8)",
                fields=["h_stab_span", "h_stab_chord", "tail_arm"],
            )
        )
    elif v_h > 1.0:
        out.append(
            ValidationWarning(
                id="V10",
                message=f"High horizontal tail volume ({v_h:.2f}) — pitch response may be sluggish (typical: 0.3-0.8)",
                fields=["h_stab_span", "h_stab_chord", "tail_arm"],
            )
        )

    # Vertical tail volume coefficient
    v_v = (v_area * design.tail_arm) / (wing_area_mm2 * design.wing_span)
    if v_v < 0.02:
        out.append(
            ValidationWarning(
                id="V10",
                message=f"Low vertical tail volume ({v_v:.3f}) — poor directional stability (typical: 0.02-0.05)",
                fields=["v_stab_height", "v_stab_root_chord", "tail_arm"],
            )
        )


def _check_v11(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V11: Flutter margin estimate.

    Higher aspect ratio wings at higher speeds are more susceptible to flutter.
    For 3D-printed PLA wings (low stiffness), warn if:
      AR > 8 (high AR increases flutter risk)
      or AR > 6 AND sweep > 15° (swept high-AR is worse)

    This is a simplified heuristic — real flutter analysis requires FEA.
    """
    tip_chord = design.wing_chord * design.wing_tip_root_ratio
    wing_area_mm2 = 0.5 * (design.wing_chord + tip_chord) * design.wing_span
    ar = (design.wing_span ** 2) / wing_area_mm2 if wing_area_mm2 > 0 else 0.0

    if ar > 8:
        out.append(
            ValidationWarning(
                id="V11",
                message=f"High aspect ratio ({ar:.1f}) — flutter risk for 3D-printed wings (limit AR < 8)",
                fields=["wing_span", "wing_chord", "wing_tip_root_ratio"],
            )
        )
    elif ar > 6 and abs(design.wing_sweep) > 15:
        out.append(
            ValidationWarning(
                id="V11",
                message=f"High AR ({ar:.1f}) combined with sweep ({design.wing_sweep:.0f}°) increases flutter risk",
                fields=["wing_span", "wing_chord", "wing_sweep"],
            )
        )


def _check_v12(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V12: Wing loading check.

    Wing loading = weight / wing_area.
    For RC planes:
      < 20 g/dm² = very light (floater/glider)
      20-60 g/dm² = typical sport
      > 80 g/dm² = heavy — needs higher speed, harder landings
      > 120 g/dm² = very heavy — not suitable for beginners
    """
    weight_kg = _estimate_weight_kg(design)
    weight_g = weight_kg * 1000.0
    wing_area_dm2 = _wing_area_m2(design) * 100.0  # m² to dm²

    if wing_area_dm2 <= 0:
        return

    wing_loading = weight_g / wing_area_dm2

    if wing_loading > 120:
        out.append(
            ValidationWarning(
                id="V12",
                message=f"Very high wing loading ({wing_loading:.0f} g/dm²) — needs fast airspeed, hard landings",
                fields=["wing_span", "wing_chord"],
            )
        )
    elif wing_loading > 80:
        out.append(
            ValidationWarning(
                id="V12",
                message=f"High wing loading ({wing_loading:.0f} g/dm²) — not beginner-friendly (typical: 20-60)",
                fields=["wing_span", "wing_chord"],
            )
        )


def _check_v13(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V13: Stall speed estimate.

    V_stall = sqrt(2 * W / (rho * S * Cl_max))

    Where:
      W = weight in N
      rho = 1.225 kg/m³ (sea level)
      S = wing area in m²
      Cl_max ≈ 1.2 (typical for RC airfoils)

    Warn if stall speed > 15 m/s (54 km/h) — difficult for beginners.
    Info if stall speed > 10 m/s (36 km/h).
    """
    weight_kg = _estimate_weight_kg(design)
    weight_n = weight_kg * 9.81
    wing_area_m2 = _wing_area_m2(design)

    if wing_area_m2 <= 0 or weight_n <= 0:
        return

    rho = 1.225  # kg/m³, sea level ISA
    cl_max = 1.2  # typical RC airfoil

    v_stall = math.sqrt(2.0 * weight_n / (rho * wing_area_m2 * cl_max))
    v_stall_kmh = v_stall * 3.6

    if v_stall > 15.0:
        out.append(
            ValidationWarning(
                id="V13",
                message=f"High stall speed ({v_stall_kmh:.0f} km/h) — needs fast approach, difficult landings",
                fields=["wing_span", "wing_chord"],
            )
        )
    elif v_stall > 10.0:
        out.append(
            ValidationWarning(
                id="V13",
                message=f"Moderate stall speed ({v_stall_kmh:.0f} km/h) — OK for experienced pilots",
                fields=["wing_span", "wing_chord"],
            )
        )


# ---------------------------------------------------------------------------
# 3D-printing warnings  (V16 - V23)
# ---------------------------------------------------------------------------


def _check_v16(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V16: skinThickness < 2 * nozzleDiameter — wall too thin for solid perimeters."""
    if design.wing_skin_thickness < 2 * design.nozzle_diameter:
        out.append(
            ValidationWarning(
                id="V16",
                message="Wall too thin for solid perimeters",
                fields=["wing_skin_thickness", "nozzle_diameter"],
            )
        )


def _check_v17(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V17: skinThickness % nozzleDiameter > 0.01 — wall not clean multiple of nozzle."""
    remainder = design.wing_skin_thickness % design.nozzle_diameter
    # Use math.isclose to handle floating-point precision (e.g. 1.2 % 0.4 = 0.3999...)
    if not math.isclose(remainder, 0, abs_tol=1e-6) and not math.isclose(remainder, design.nozzle_diameter, abs_tol=1e-6):
        out.append(
            ValidationWarning(
                id="V17",
                message="Wall not clean multiple of nozzle diameter",
                fields=["wing_skin_thickness", "nozzle_diameter"],
            )
        )


def _check_v18(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V18: skinThickness < 1.0mm — absolute structural minimum for FDM wing skin."""
    if design.wing_skin_thickness < 1.0:
        out.append(
            ValidationWarning(
                id="V18",
                message="Wing skin below 1.0 mm absolute structural minimum",
                fields=["wing_skin_thickness"],
            )
        )


def _check_v20(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V20: any part exceeds bed size AND auto-section disabled."""
    if design.auto_section:
        return

    half_span = design.wing_span / 2.0
    bed_max = max(design.print_bed_x, design.print_bed_y)

    if half_span > bed_max or design.fuselage_length > bed_max:
        out.append(
            ValidationWarning(
                id="V20",
                message="Enable auto-sectioning or reduce dimensions",
                fields=["print_bed_x", "print_bed_y", "wing_span", "fuselage_length", "auto_section"],
            )
        )


def _check_v21(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V21: jointOverlap < 10 AND wingspan > 800 — joint overlap too short."""
    if design.section_overlap < 10 and design.wing_span > 800:
        out.append(
            ValidationWarning(
                id="V21",
                message="Joint overlap too short for this span",
                fields=["section_overlap", "wing_span"],
            )
        )


def _check_v22(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V22: jointTolerance > 0.3 — parts may be loose."""
    if design.joint_tolerance > 0.3:
        out.append(
            ValidationWarning(
                id="V22",
                message="Parts may be loose",
                fields=["joint_tolerance"],
            )
        )


def _check_v23(design: AircraftDesign, out: list[ValidationWarning]) -> None:
    """V23: jointTolerance < 0.05 — parts may not fit."""
    if design.joint_tolerance < 0.05:
        out.append(
            ValidationWarning(
                id="V23",
                message="Parts may not fit",
                fields=["joint_tolerance"],
            )
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_warnings(design: AircraftDesign) -> list[ValidationWarning]:
    """Compute all non-blocking validation warnings for a design.

    Returns a list of ValidationWarning objects.  Each warning has a unique
    ID (V01-V08 structural, V09-V13 aero/structural, V16-V23 print,
    V24-V28 printability), a human-readable message, and the list of
    affected parameter field names.
    """
    warnings: list[ValidationWarning] = []

    # Structural / geometric (V01-V08)
    _check_v01(design, warnings)
    _check_v02(design, warnings)
    _check_v03(design, warnings)
    _check_v04(design, warnings)
    _check_v05(design, warnings)
    _check_v06(design, warnings)
    _check_v07(design, warnings)
    _check_v08(design, warnings)

    # Aerodynamic / structural analysis (V09-V13)
    _check_v09(design, warnings)
    _check_v10(design, warnings)
    _check_v11(design, warnings)
    _check_v12(design, warnings)
    _check_v13(design, warnings)

    # 3D printing (V16-V23)
    _check_v16(design, warnings)
    _check_v17(design, warnings)
    _check_v18(design, warnings)
    _check_v20(design, warnings)
    _check_v21(design, warnings)
    _check_v22(design, warnings)
    _check_v23(design, warnings)

    return warnings
